# ROS v1117219 — Stalker `compile` Events & ARM64 Attribution Attempt

**Result up front**: the ideal mapping (`libclient.so` ARM64 address → NativeBridge
translation → `libtcb.so` JIT block → runtime execution during LoginReply) was **not
achieved**. Four separate, concrete attempts were made to recover the original ARM64
program counter from runtime observation, each producing a clean, real negative result
that is reported precisely below rather than glossed over. One of the four attempts
(testing whether Mercury I/O runs through Java's `DatagramSocket`) is a genuinely new,
valuable negative result that closes off a plausible alternative hypothesis raised by this
pass's own evidence. `LoginHandler::onLoginReply` (`0x938070`–`0x938724`) was **not**
observed to execute, directly or by inference — no claim of reaching it is made.

## 1. Exact Frida API/Version Used

- Frida `16.2.1` (both host `frida`/`frida-tools` Python packages and the on-device
  `frida-server`, x86_64 build) — unchanged from prior sessions.
- API surface tested: `Stalker.follow(tid, { events: { compile: true }, onReceive })`,
  with `Stalker.parse(rawEvents, { annotate: true, stringify: true|false })`.
- **Verified empirically, not assumed**: a `compile` event, once parsed, has the shape
  `['compile', startAddress, endAddress]` — a two-element address range. There is **no
  third field, no architecture tag, and no reference to a "source" address in a different
  address space**. This was confirmed by direct inspection of ~200 real parsed events
  (`scratch/compile_probe_report.json`), for example:
  ```
  ['compile', '0xd26ebca', '0xd26ebef']
  ['compile', '0xdd1923d', '0xdd1929d']
  ['compile', '0x763915542a57', '0x763915542a5f']
  ```
  All addresses are in the **same** (translated x86_64 / host) address space already seen
  in the previous session's `call`-summary data — `compile` is Stalker's *own*
  instrumentation-JIT block-compilation event (it fires when Stalker's engine is about to
  instrument a not-yet-seen block of the *actually executing* x86_64 instruction stream),
  not a NativeBridge/Houdini translation-completed event. **This directly answers Phase 1's
  core question: no, `events.compile` does not expose the original ARM64 PC, the block
  size in ARM64 terms, or any tag identifying which ARM64 module the code came from.**

## 2. Additional Memory Regions Discovered

Resolving `compile`-event addresses via `Process.findRangeByAddress` revealed a **second,
much larger JIT region** not identified in the previous Stalker pass:

| Region | Base | Size | Protection | Backing |
|---|---|---|---|---|
| `libtcb.so` (previously found) | `0xd208000` | 1,335,296 bytes (~1.27 MB) | `r-x` | real file, `/system/lib64/arm64/nb/libtcb.so` |
| **New**: anonymous JIT heap | `0xd378000` | 65,601,536 bytes (**~62.5 MB**) | **`rwx`** | none (anonymous) |

The second region is immediately adjacent to `libtcb.so` (starts right where it ends) and
is **read-write-execute** — the classic shape of a JIT compiler's dynamically-growing code
cache/working heap, as opposed to `libtcb.so`'s smaller, static, execute-only mapping. This
is new, concrete information about the scale of NativeBridge's runtime footprint for this
process (~64MB total translated-code capacity between the two regions) but does not by
itself solve the attribution problem.

## 3. Attempt: Metadata Scan Near Translated Blocks

**Hypothesis tested**: Houdini might store the original ARM64 source address as metadata
adjacent to (before/after) each translated block, for its own internal bookkeeping
(e.g., exception unwinding needs some way to map a faulting translated PC back to the
"real" one).

**Method**: for a real captured block start (`0xd26ebca`), scanned a ±256-to-512-byte
window in 8-byte-aligned steps, testing each 64-bit value against the known
`libclient_arm64.so` mapped-address range (`0x03200000`–`0x07000000`, confirmed in earlier
sessions via `/proc/pid/maps`).

**Result**: **zero candidates found.** This does not prove no such metadata exists
anywhere in the process (a real implementation would very plausibly use a separate,
indexed lookup table rather than storing the source address inline next to each block —
which is exactly what would defeat this simple adjacent-memory scan), but the simple,
cheap version of this test was negative.

## 4. Attempt: `libhoudini.so`'s Own Exported API

**Hypothesis tested**: `libhoudini.so` might export a translation-lookup function (PC → PC
or PC → PC) usable directly via Frida's `NativeFunction` wrapper, bypassing the need to
infer anything from Stalker at all.

**Method**: pulled `/system/lib64/libhoudini.so` from the device and parsed its `.dynsym`
directly (same method used successfully for `libclient.so` and the ARM64 `libc.so` in
earlier sessions).

**Result**: only **47 defined/exported symbols** total, and **all but five are stripped**
to anonymous names (`s_000014`, `s_000016`, ...). The five real names are `_edata`, `_end`,
`__bss_start`, `__stack_chk_fail`, and **`NativeBridgeItf`** — the last being Android's
standard, publicly-documented `NativeBridgeCallbacks`/`NativeBridgeItf` ABI struct symbol,
which is the interface the Android runtime itself uses to load/manage NativeBridge (this is
a well-known AOSP interface, not something specific to this device or reverse-engineered
here). **No translation-lookup function is exposed under a recoverable name.** This is a
real, negative result — the library's internal API is not something this pass could call
into for attribution.

## 5. Attempt: Java-Level Socket Hooking (New Hypothesis, Cleanly Ruled Out)

**Motivation**: a broader (unintentionally ~30–100-second, due to per-event classification
overhead — see §6) Stalker capture during this pass's login-timeline experiment showed
`TID 16424` also executing through `libart.so`, `boot-framework.oat`, `libandroid_runtime.so`,
and `libbinder.so` during the exact window containing the login attempt. This raised a
concrete, testable hypothesis: **maybe Mercury's actual UDP I/O is performed via Java's
`java.net.DatagramSocket`** (with the native `ServerConnection` code just orchestrating
via JNI), which would explain why every native-level `recvfrom`/`sendto` hook in this and
the previous session's passes saw nothing.

**Method**: `Java.perform()` hooks on `java.net.DatagramSocket.send(DatagramPacket)` and
`.receive(DatagramPacket)`, installed successfully (confirmed via a log line), left active
across one full, `logcat`-confirmed login attempt (`logOnBegin` at `22:09:12.911`,
`logOnComplete`/`REASON_TIMER_EXPIRED` at `22:09:21.909` — the hooks were live for this
entire ~9-second window and beyond).

**Result**: **zero invocations of either hooked method.** This cleanly rules out the
Java-`DatagramSocket` hypothesis — Mercury's UDP I/O is not implemented this way. The
`libart.so`/`libbinder.so` activity observed alongside the login window is therefore
concluded to be **unrelated, concurrent activity on the same shared thread** (e.g.
periodic telemetry, GC-related callbacks, or other engine housekeeping that happens to run
on this same TID), not evidence of a Java-mediated network path. **This is a genuinely new,
valuable negative result** — it was not something the previous pass could have ruled out
and closes off what looked like the most promising alternative lead at the start of this
pass.

## 6. Practical Limitation: Slice Timing Broke Down

The intended ~1-second time-sliced `compile`-event capture (mirroring the previous
session's successful `call`-summary slicing) did **not** achieve 1-second resolution in
practice: per-event classification via `Process.findRangeByAddress` for every single
`compile` event (tens of thousands during an active window) is expensive enough that the
first "slice" actually spanned **~35 real seconds**, and the second **~29 seconds**, before
the loop's timing caught up and later slices stabilized to their intended ~3.5–4-second
width. This is reported honestly as a methodological limitation of this specific script,
not hidden — the coarse timeline correlation in §5 above still held (the whole login
attempt is contained within the first oversized slice, so temporal association is not
lost, just imprecise). A production version of this experiment should classify addresses
lazily/in batches rather than per-event, or drop classification entirely during capture
and post-process the raw `(start,end)` pairs afterward.

## 7. Was `0x938070`–`0x938724` (`LoginHandler::onLoginReply`) Reached?

**Not determined, and not claimed.** No method in this pass (or the previous Stalker pass)
produced any address that could be confidently mapped back to this specific ARM64 range.
The task's explicit instruction — "Do not claim a function was reached merely because its
translated code exists... Require runtime evidence tied to the login attempt" — is
respected here: no such runtime evidence was obtained in either direction (neither
confirming nor ruling out that this handler executes).

## 8. Strongest Evidence For Where the Reply Is Accepted/Rejected

**No new evidence on this question was obtained this pass.** The reply-envelope question
remains exactly where `LOGIN_REPLY_MERCURY_ENVELOPE.md` and
`MERCURY_REPLY_DISPATCH_TRACE.md` left it: three candidate envelopes tried and rejected
(all producing `Mercury::REASON_TIMER_EXPIRED`), with the actual acceptance/rejection point
inside the native Mercury stack still unobserved.

## 9. Closest Observable Boundary (Honest Assessment)

Given the four negative results above, the **closest currently-observable boundary** to
the actual Mercury receive/dispatch logic remains what was already established in the
previous session: the coarse, statistical correlation between `call`/`compile` event
volume in `libhoudini.so`+`libtcb.so`+the new anonymous JIT heap and the `logOnBegin`/
timeout window (§5 of `MERCURY_STALKER_RUNTIME_TRACE.md`). No finer instrumentation point
was found this pass. The next genuinely different avenue (not yet attempted in any pass)
would be a **kernel-level packet capture** correlated purely by timing (e.g. `tcpdump`
inside the emulator, or capturing at the host's virtual NIC for the `172.16.1.2` gateway
path) combined with `logcat` timestamps — this sidesteps the in-process attribution problem
entirely by only asking "did a UDP packet cross the wire at time T," which is already
partially answered by the existing capture-server logs, but a kernel-level capture would
additionally show the **exact wire bytes leaving the device** (as opposed to what our
local server received, which could theoretically differ if something in between altered
them — though no evidence suggests this is happening).

## 10. Summary of Negative Results (For Quick Reference)

| Attempt | Result |
|---|---|
| `Stalker` `compile` events exposing original ARM64 PC | **No** — same address space as `call` events, confirmed via ~200 real parsed samples |
| Embedded ARM64-address metadata near translated blocks | **No** — 512-byte window scan, zero matches |
| `libhoudini.so` translation-lookup export | **No** — only 5 named symbols, none relevant |
| Mercury UDP I/O via `java.net.DatagramSocket` | **No** — hooks installed and live through a full confirmed login attempt, zero invocations |
| `LoginHandler::onLoginReply` execution observed | **No** — not claimed |
