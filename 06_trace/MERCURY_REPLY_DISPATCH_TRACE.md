# ROS v1117219 — Live Mercury Reply Dispatch Trace

**Result up front**: neither success condition A nor C was fully achieved. Partial progress
on A: `LoginHandler::onLoginReply`/`handleMessage`'s exact function boundary is now
CONFIRMED (not just "somewhere around" an address, as in prior passes), and its full
internal behavior re-verified. However, the mechanism that **calls** it — the actual
Mercury dispatch path from raw UDP bytes to this handler — could not be traced by any of
five independent static methods tried, each producing a clean, reproducible negative
result. This is reported as a genuine architectural finding (virtual/indirect dispatch,
consistent with BigWorld's known handler-interface design), not a failure to look.

## 1. Confirmed: `LoginHandler::onLoginReply`/`handleMessage` Function Boundary

Built a systematic inventory of function prologues (`stp x29, x30, [sp, ...]`, both
pre-indexed and post-indexed forms) across the whole `ServerConnection`/`LoginHandler`
code cluster (`0x936000`–`0x93d000`), yielding **75 function starts**. Cross-checked each
function's own outgoing calls to confirm content matches expected behavior.

- **Function**: `0x938070`–`0x938724` (1716 bytes) — **CONFIRMED BY BINARY** to be
  `LoginHandler::handleMessage`/`onLoginReply` (merged/inlined, as found in prior passes):
  contains the exact xref to `"sending base app request to %s "` at `0x9384a8` (previously
  found at `~0x9384a0`, now pinned to the exact instruction), reads a 20-byte record via
  `bl 0x989600`, and calls out only to generic runtime/string helpers
  (`0x8078f0`, `0x9898e0`, `0x83f8a8`, `0x981c0c`, `0x1cadbb4`, `0x7ed3b0`, etc.) — **no
  calls to any other function in the 75-entry cluster**, consistent with a leaf-style
  message handler that does its own field parsing inline rather than delegating to sibling
  `ServerConnection` methods.
- This refines (not contradicts) the boundary used in `LOGIN_REPLY_MERCURY_ENVELOPE.md` and
  earlier passes — the function is confirmed to end at `0x938724` (a `ret` immediately
  precedes the next function's prologue), narrower than the informal "0x938100-0x938940"
  range quoted loosely in earlier documents.

## 2. Exhaustive (and Exhausted) Search For This Function's Caller

Five independent methods were tried to find what calls `0x938070`. **All five returned
zero hits**, each cross-validated against a known-good positive control to rule out tooling
bugs:

| Method | Result | Sanity check |
|---|---|---|
| Direct `BL` (relative call) scan across all of `.text` (22MB) | 0 hits | Same method found the 2 known callers of `BaseAppLoginRequest::initNetwork` (`0x9388d8`, `0x94ceac`) correctly when re-run in the same session — the tool works |
| Direct `B` (tail-call / unconditional branch) scan | 0 hits | — |
| Raw 8-byte absolute-pointer scan across the entire file (for a literal vtable entry) | 0 hits | Same method found real RTTI/typeinfo pointer chains in earlier sessions |
| `R_AARCH64_RELATIVE` relocation addend scan across all of `.rela.dyn` (looking for a relocated vtable slot whose *addend*, not literal bytes, encodes the target) | 0 hits | — |
| 4-byte relative-offset scan across all of `.data.rel.ro` (testing the hypothesis that this build uses LLVM "relative vtables", where a slot stores `target − slot_address` as an `int32` rather than an absolute pointer) | 0 hits | — |

The same five methods were also run against `LogOnParams::addToStream` (`0x9d8014`) and the
address `0x93bcc8` (a nearby function that formats a log line using the literal string
`"ServerConnection::logOnBegin"` as one of its arguments — found via the same
ADRP+ADD-with-wide-window technique that worked in earlier sessions). **Both also returned
zero hits across all five methods.**

### 2.1 Conclusion

**STRONG EVIDENCE**: these three functions (`handleMessage`, `addToStream`, and the
`0x93bcc8` log-formatting routine) are invoked through a call mechanism this project's
toolset cannot statically resolve — most likely genuine **C++ virtual dispatch** through a
vtable whose layout does not match either the standard Itanium absolute-pointer vtable
format or LLVM's relative-vtable format, at least not in a way a straightforward slot-value
scan can find. This is architecturally **expected and unsurprising** for
`handleMessage`/`onLoginReply`: BigWorld's Mercury design specifies that per-message
handlers (`Mercury::InputMessageHandler`/`ReplyMessageHandler`) are invoked polymorphically
by the generic `Nub` dispatch code specifically so that many unrelated message types can
share one dispatch loop — this is not a code obfuscation technique, it is the normal shape
of the framework these classes were confirmed (via RTTI, in earlier sessions) to belong to.

**What this means practically**: finding the vtable itself (rather than a slot-value scan)
would require locating the `LoginHandler` **constructor** — the code that sets the object's
first field to the vtable's address — which requires yet another anchor. This was not
pursued further in this pass because it is a materially larger sub-investigation (finding
an un-stringed constructor is exactly as hard as finding an un-stringed call site,
circularly), and because the task's own item 6 authorizes documenting the blocker instead
of continuing indefinitely down one static-analysis avenue.

## 3. Working Backward From Confirmed-Live Code (Task Item 3)

Per the task's suggestion, starting from definitely-live anchors instead:

- **`ServerConnection::logOnBegin`**: the string `"ServerConnection::logOnBegin"` has real
  xrefs (found via the proven wide-window ADRP+ADD scan), but only inside the `0x93bcc8`
  log-formatting function discussed above — which itself has no found callers either (§2).
  This means even the "obviously live" `logOnBegin` could only be reached transitively
  through the same unresolved indirect-call boundary. No independent, directly-callable
  `logOnBegin` entry point was found in this pass.
- **The request send path**: fully traced in prior sessions
  (`BASEAPP_LOGIN_SERIALIZATION.md`, `LOGONPARAMS_SERIALIZATION.md`) up through
  `LogOnParams::addToStream`'s body and the RSA encryption call — this remains valid,
  unaffected by this pass's findings.
- **The timeout/retry path**: `Mercury::REASON_TIMER_EXPIRED` is confirmed (via live
  `logcat`, not statically) as the outcome when no accepted reply arrives — this was
  already established in `PLAY_TO_BASEAPP_CAPTURE.md` and is unchanged here.

## 4. Reply/Request ID — Not Located This Pass

Task item 4 asked for the exact field/width/offset/byte-order of the 32-bit reply/request
ID implied by the `"Couldn't find handler for reply id 0x%08x"` string
(`LOGIN_REPLY_MERCURY_ENVELOPE.md` §2). That string itself was already shown, in the
previous pass, to have **zero static callers** (same phenomenon documented here at greater
depth) — so its containing function (presumably `Mercury::Nub::handleMessage`, the
*generic* dispatcher, a **different, more central function than the `LoginHandler`-specific
`0x938070` traced in §1**) could not be located either, by the same five methods. **This
field's lifecycle (where it's generated, stored, and compared) remains entirely UNKNOWN** —
not guessed at, left explicitly open.

## 5. Instrumentation Attempts (Task Items 6–7)

No new dynamic instrumentation was attempted in this pass beyond what
`LOGIN_REPLY_MERCURY_ENVELOPE.md` §4 already covers and ruled out (host `libc.so` hook —
wrong module; raw-address ARM64 `libc.so` hook — installed but never fires). Per task item
7's suggestion to look for "a translated/JIT-visible function" or a boundary "outside the
inaccessible ARM64 mapped pages": the **Java/JNI boundary** was considered but not
attempted — `ServerConnection::logOnBegin` and the Mercury receive loop run entirely inside
native code with no round-trip through Java between the UDP send and the eventual
`logOnComplete` callback (confirmed by the fact the entire cycle, send-to-timeout, is
bounded by two adjacent native log lines with no intervening JNI-tagged logcat activity in
any capture so far) — so a JNI-boundary hook would not observe anything in between.

**Concrete recommendation for the next session (not attempted here, named per task item
6)**: Frida's **`Stalker`** engine, rather than `Interceptor`, instruments the CPU's actual
executed instruction stream at runtime instead of patching a fixed address ahead of time.
Since NativeBridge's translated code genuinely executes as x86_64 instructions on the real
CPU (just not the ones visible at the ARM64 library's mapped file offsets), `Stalker`
attached to the relevant thread during a login attempt could, in principle, observe the
real control flow and any syscalls it makes (including the eventual `sendto`/`recvfrom` at
the kernel boundary, which are real x86_64 `syscall` instructions regardless of how the
calling code was translated) without needing to know the ARM64-space address in advance.
This was not attempted in this pass — it requires meaningfully different Frida script
architecture than the `Interceptor`-based scripts already written, and is a bounded,
self-contained task recommended as the next concrete step.

## 6. Answers To The Task's Success Conditions

- **A (exact live code path to `onLoginReply`)**: **partially met**. The handler function
  itself is now precisely bounded and re-confirmed (§1), but the dispatch path *to* it
  (UDP receive → validation → reply-id lookup → handler invocation) remains unresolved —
  confirmed to be virtual/indirect dispatch, but the vtable/constructor was not located.
- **B (exact rejection reason for our reply)**: **not met**. No new reply variant was
  tested this pass (task explicitly asked not to brute-force further), and no new
  packet-level evidence was obtained to distinguish rejection stages.
- **C (a working instrumentation point after NativeBridge, before dispatch)**: **not met**,
  but a concrete, reasoned candidate (`Stalker`-based syscall tracing) is named in §5 for
  the next session, distinct from the already-ruled-out `Interceptor`-based approaches.

## 6a. 2026-09-14 (Stalker follow-up) — Condition C Partially Advanced

A follow-up pass (`06_trace/MERCURY_STALKER_RUNTIME_TRACE.md`) used Frida Stalker
(call-summary mode) on the exact thread (`TID 16424`, identified via `logcat` tagging) that
runs `ServerConnection::logOnBegin`. This **positively identified**
`/system/lib64/arm64/nb/libtcb.so` as NativeBridge's real, executable (`r-x`), file-backed
JIT translation cache — new information superseding this document's earlier assumption
that translated code lives only in anonymous/unidentifiable memory. Login-attempt-specific
execution bursts were also confirmed to correlate in time (±1s) with `logOnBegin` and the
`REASON_TIMER_EXPIRED` timeout.

However, **semantic attribution to specific `libclient.so` functions (including
`handleMessage`/`onLoginReply` itself) was not achieved** — the dominant observed
addresses are Houdini's own generic block-dispatch machinery, shared by all ARM64 execution
on that thread (including likely UI/script activity unrelated to Mercury), and
`onCallSummary` only reports translated x86_64 addresses, never the original ARM64 program
counter. Condition C (a working post-NativeBridge, pre-dispatch instrumentation point) is
therefore still **not fully met**, but meaningfully advanced: `libtcb.so` is now a known,
concrete target for future finer-grained Stalker configurations (e.g. `compile` events) —
see `MERCURY_STALKER_RUNTIME_TRACE.md` §7 for the specific next steps.

## 6b. 2026-09-14 (compile-event follow-up) — Attribution Gap Confirmed, Not Closed

`06_trace/MERCURY_STALKER_COMPILE_TRACE.md` tested `Stalker`'s `compile` event directly
(the concrete next step named in §6a) and confirmed, from ~200 real parsed events, that it
reports the same translated x86_64 address space as `call` events — no original ARM64 PC is
exposed by this API in this environment. A live-`Java.perform()` test also cleanly ruled
out a new, evidence-motivated alternative hypothesis (Mercury UDP I/O via
`java.net.DatagramSocket`) by leaving hooks active through a full confirmed login attempt
with zero invocations. The dispatch path to `LoginHandler::onLoginReply` remains
**UNKNOWN** — every reasonably-available static and dynamic method attempted across three
passes has been exhausted without result; the next genuinely different avenue is a
kernel/wire-level packet capture (named in `MERCURY_STALKER_COMPILE_TRACE.md` §9) rather
than further in-process instrumentation.

## 6c. 2026-09-14 (socket-read pass) — Major Update: Reply Confirmed Delivered To Process

`06_trace/MERCURY_SOCKET_READ_TRACE.md` used `strace` (kernel-level `ptrace`-based syscall
tracing on TID `16424`) — a boundary not previously tried, and one that works independently
of the NativeBridge/Houdini limitations that blocked every Frida-based attempt documented
above. Result: the client's `recvfrom(181, ...)` syscall **directly and repeatably returns
our exact 22-byte reply**, on all 10 retries, with a symmetric no-reply control showing the
same call return nothing (`EAGAIN`) when nothing is sent.

**This resolves part of §6b's open question**: the reply **is** read by the application
process — this was previously unknown and is now CONFIRMED. What remains unresolved is
unchanged in kind but now more precisely located: the dispatch/parsing path *after* the
`recvfrom()` return (i.e., whatever code decides to accept or discard the 22 bytes) is still
not observed by any method tried. `LoginHandler::onLoginReply` is still not confirmed to
execute. `strace`-based tracing (e.g. attempting `-k` for stack traces, or `ltrace`) is
named as the next concrete avenue, since `strace` is now proven to work where Stalker did
not.

## 6d. 2026-09-14 (post-recv pass) — `REASON_CORRUPTED_PACKET` Confirmed, With a Correction

`06_trace/MERCURY_POST_RECV_DISPATCH_TRACE.md` found the client's own log output naming
the exact rejection reason (`Mercury::REASON_CORRUPTED_PACKET`), confirmed via a clean A/B
(fires 11/11 times with a reply sent, 0/0 without), and traced it to a real, live function
at `0x937df0`–`0x937f0c` — found via a direct static cross-reference to the
`"REASON_CORRUPTED_PACKET"` string, unlike the many dead-code Mercury strings in §2/§3
above. This function sits immediately adjacent to the confirmed `handleMessage` function
and writes to the same `ServerConnection` offsets.

**Correction to §2**: that section reported zero direct callers of `LogOnParams::addToStream`
(`0x9d8014`) across five methods. This pass found a real caller targeting `0x9d8018` — 4
bytes past that entry point — from the newly-found function at `0x937df0`. This resolves the
"why no callers" puzzle without changing any of `LOGONPARAMS_SERIALIZATION.md`'s confirmed
field-level findings about `addToStream`'s body.

## 6e. 2026-09-14 (validation-trace correction pass) — `0x937df0` Is NOT A Reply Validator

`06_trace/MERCURY_LOGINREPLY_VALIDATION_TRACE.md` fully disassembled `0x937df0`–`0x937f0c`
(§6d above only covered its failure branch) and found **§6d's "validation function"
framing was incorrect**. The function does not read or validate the incoming reply's
bytes at all — its vtable[0x10] calls are `reserve(n)` WRITE operations, and it calls
directly into `LogOnParams::addToStream`'s body (`0x9d8018`, confirmed as that function's
one and only caller in the binary) to **rebuild and resend an outgoing `LogOnParams`
bundle**. `REASON_CORRUPTED_PACKET` is reported when this outgoing serialization call
itself fails — a send-side signal, not evidence about what our reply contains. The
A/B timing correlation (11/11 vs 0/0) remains valid; only the causal explanation is
corrected. `0x937df0` has zero direct callers of its own and must be invoked via
indirect/virtual dispatch — the mechanism connecting reply-receipt to this function
running is UNKNOWN and is the new next blocker. See that document for full corrected
pseudocode, the `0x9d8018` caller-argument trace, and the `0xa`-retry-count correlation
found in an adjacent function.

## 6f. 2026-09-14 (indirect-dispatch trace pass) — BREAKTHROUGH: `Nub::processFilteredPacket` Found, Bad-Flags Cause Confirmed Byte-For-Byte

**This pass answers Phase 2/Phase 4/Phase 5's central question directly and resolves §6e's
"next blocker".** Rather than chasing `0x937df0`'s indirect caller (which this pass's
evidence now shows is very likely the wrong lead entirely — see the negative result at the
end of this section), a fresh `strace -f -tt -T -e trace=network,desc` capture (no `-i`
this time, so no Houdini-trampoline problem) plus a full `adb logcat -d` pull over the same
login attempt surfaced a **second, previously-unseen log line that fires immediately before
`MainApp::poll`'s warning, on the exact same thread, every single time**:

```
[WARNING] Nub(0x7638491fa000)::processFilteredPacket( 172.16.1.2:25000 ): received packet with bad flags 10ac
[WARNING] MainApp::poll: poll returned unexpectedly (REASON_CORRUPTED_PACKET).
```

This repeats for all 10 retries, then on the 10th is followed by a third, previously-unseen
line: `[WARNING] MainApp::poll: disconnected since we have too may corruptted packet`
(sic, both typos are in the client's own binary string) — this is the actual, named give-up
condition, and it fires after exactly 10 occurrences, matching the `0xa` retry-count literal
found in §6e's `0x937d2c`.

### The byte-for-byte confirmation

Our current 22-byte test reply (`ac10010261b20000ac10010261b20000785634120000`) begins with
bytes `ac 10`. Read as a little-endian `uint16` (matching the disassembly below), that is
**exactly `0x10ac`** — the literal value the log line reports. This is not a coincidental
match: it is the field the code actually reads, at the exact offset, printed with `%x`.
**CONFIRMED**: the first two bytes of our reply are being read and rejected as a Mercury
packet "flags" field.

### Disassembly: `Nub::processFilteredPacket` (prologue `0x98fa30`, log call at `0x98fa9c`)

Found via the project's standard method: the combined printf-style format string
`"Nub(%p)::processFilteredPacket( %s ): received packet with bad flags %x\n"` lives at
`0x2a5d23d` in `.rodata`; `xrefs()` found exactly one direct `ADRP+ADD` reference to that
exact address, at `0x98fa9c`, inside the function whose prologue is at `0x98fa30`.

```
0x98fa30: sub sp, sp, #0x150            ; prologue
...
0x98fa58: mov x20, x2                    ; x20 = arg2 = the received-packet-shaped object
0x98fa5c: add x26, sp, #0x20
0x98fa60: mov x24, x20
0x98fa64: str x8, [x26]                  ; stack-protector cookie
0x98fa68: ldrh w9, [x24, #0x60]!         ; w9 = *(uint16_t*)(packet_obj + 0x60)  -- THE FLAGS FIELD
0x98fa6c: mov x27, x3                    ; x27 = arg3 (unused in excerpt)
0x98fa70: mov x21, x1                    ; x21 = arg1 (an Address-shaped object -> "%s" via 0x981c0c)
0x98fa74: mov x19, x0                    ; x19 = this (the Nub object -> "%p")
0x98fa78: cmp w9, #0x400
0x98fa7c: b.lo #0x98fab0                 ; if flags < 0x400 (unsigned), flags are IN RANGE -> detailed bit checks
0x98fa80: mov w8, #0x4460
0x98fa84: ldrb w8, [x19, x8]             ; per-Nub suppression byte at this+0x4460
0x98fa88: cbnz w8, #0x98fb2c             ; if set, skip logging (silently count and drop)
0x98fa8c: mov x0, x21
0x98fa90: bl #0x981c0c                   ; Address::c_str()-shaped helper -> x0 = "172.16.1.2:25000"
0x98fa94: ldrh w3, [x24]                 ; w3 = the SAME flags field again (x24 now == packet_obj+0x60)
0x98fa98: mov x2, x0                     ; x2 = address string (the "%s")
0x98fa9c: adrp x0, #0x2a5d000            ; x0 = format string "Nub(%p)::processFilteredPacket(...)"
0x98faa0: add x0, x0, #0x23d
0x98faa4: mov x1, x19                    ; x1 = this (the "%p")
0x98faa8: bl #0x1cad7ac                  ; generic varargs log call
0x98faac: b #0x98fb2c                    ; -> drop the packet, bump stats counters, return
```

**CONFIRMED**: `flags = *(uint16_t*)(packet_obj + 0x60)`, and the packet is rejected as
"bad flags" whenever `flags >= 0x400` (1024) — i.e., any bit at position 10 or higher is
set. Given the byte-for-byte match above, **`packet_obj + 0x60` corresponds to offset 0 of
the raw UDP payload we sent** — meaning the object at `x20`/`x24` wraps the wire bytes
starting after a fixed `0x60`-byte C++ object header (vtable/refcount/buffer-management
fields), and the Mercury **wire packet itself begins with a 2-byte little-endian flags
field**, consistent with BigWorld's publicly documented Mercury packet format (flagged as
**PLAUSIBLE** cross-reference to general BigWorld/Mercury protocol knowledge, not something
this disassembly alone proves) where low bits like `FLAG_HAS_REQUESTS` (`0x1`),
`FLAG_IS_FRAGMENT` (`0x4`), `FLAG_HAS_SEQUENCE_NUMBER` (`0x8`), `FLAG_IS_RELIABLE` (`0x10`)
etc. are defined, and `0x400` is one past the highest legitimate flag bit.

**Independent corroboration from our own genuine captured traffic**: every 273-byte
client→server `LogOnParams` request in `MERCURY_WIRE_CAPTURE.md` begins with bytes `01 00`
— as the same little-endian `uint16`, that is **flags = 0x0001**, comfortably under the
`0x400` threshold, with only bit 0 set. **STRONGLY SUPPORTED**: `0x0001` is a real,
client-emitted, protocol-legal flags value for this packet family (it is what the game's
own client sends as a request), making it the most evidence-grounded candidate first byte
pair for a reply, in sharp contrast to our current candidate's `0xac 0x10`, which was never
derived from any protocol evidence (it was reverse-encoding a BaseApp IP/port guess into
what should have been the packet's framing field).

### What this means for `0x937df0` (§6c–§6e)

This pass's timing/location evidence makes it **UNKNOWN, leaning unlikely**, that
`0x937df0` is on the causal path from "reply received" to
"`REASON_CORRUPTED_PACKET` logged":

- `Nub::processFilteredPacket` (`0x98fa30`, this pass) and `0x937df0` (§6c–§6e) are in
  **completely different regions of the binary** (`0x98f000` region vs. `0x937000`
  region) with no call edge found between them in either direction so far.
- The bad-flags rejection log line fires **within ~10–24ms of `recvfrom()` returning**
  (same poll cycle). The next `sendto()` retry (which is what `0x937df0`'s
  `LogOnParams::addToStream` rebuild would immediately precede, per §6e) fires
  **~0.4 seconds later** — a different, much longer timescale, consistent with
  `0x937df0` being the routine **periodic retry-resend build step** (which runs on its own
  ~0.4s timer regardless of whether a reply arrived at all — recall the NO_REPLY control in
  `MERCURY_POST_RECV_DISPATCH_TRACE.md` also produced exactly 10 evenly-spaced `sendto()`
  calls with no replies whatsoever), **not** a direct reaction to the bad-flags rejection.
- The most likely honest explanation for §6d's original 11/11-vs-0/0 A/B correlation:
  **`Nub::processFilteredPacket`'s bad-flags rejection is what actually produces the count
  match** (it only fires when a reply arrives to be rejected), and `0x937df0` firing
  `REASON_CORRUPTED_PACKET` under a completely unrelated trigger (its own
  `addToStream`-encode failure) was a **coincidental reuse of the same generic state
  string/flags on the connection object**, not evidence of a shared code path. This
  supersedes §6e's framing of `0x937df0` as "the mechanism" and should be read as: two
  distinct pieces of code both write similar failure state, and this pass's new evidence
  identifies which one is actually triggered by our reply's arrival.
- This is reported as **UNKNOWN, not CONFIRMED**, because no direct evidence yet proves
  `0x937df0` is *never* reached in this scenario — only that its trigger conditions
  (identified in §6e as an outgoing-bundle-serialization failure) do not obviously connect
  to a receive-side bad-flags rejection, and the timing better matches an independent retry
  timer.

### Answering the Task's Success Criteria

- **(C) Exact function that receives/consumes the 22-byte LoginReply before any
  callback**: **CONFIRMED** — `Nub::processFilteredPacket` (`0x98fa30`–at least `0x98fb74`),
  called on the same thread immediately after `recvfrom()` returns, reading the packet's
  flags field at object-offset `+0x60` (= wire offset 0) before any Login-specific parsing
  is attempted.
- **(D) Exact reason the reply arrival causes rejection**: **CONFIRMED** — the reply's
  first two bytes, interpreted as a little-endian `uint16` "flags" field, evaluate to
  `0x10ac`, which fails the `flags < 0x400` validity check inside
  `Nub::processFilteredPacket`, before the packet reaches any BaseApp-address or
  LoginReply-specific logic.
- **(A) Exact caller/invocation mechanism of `0x937df0`**: still not established — see the
  negative result above. Given (C)/(D) are now answered with strong, byte-level evidence,
  and given `0x937df0` no longer appears to be on the relevant causal path, further
  pursuit of its indirect caller is a **lower-value** next step than validating a
  flags-corrected reply candidate (see Recommended Next Experiment).
- **(B) Exact object/vtable/callback slot containing `0x937df0`**: not established, same
  reasoning as (A).

### Recommended Next Experiment (highest-value next observation)

Change **only** the first two bytes of the local server's 22-byte reply from `ac 10` to
`01 00` (i.e., `flags = 0x0001`, the value our own genuine client traffic uses) and rerun
the capture. This is not a brute-force guess: it is the single, minimal, evidence-derived
change directly indicated by this pass's disassembly (the exact failing field, exact
offset, exact threshold) and corroborated by genuine captured traffic (not fabricated). If
`Nub::processFilteredPacket`'s "bad flags" warning disappears and a **different**,
new rejection reason appears further downstream, that is real forward progress and should
be traced next rather than treated as final success. If the warning disappears with **no**
new warning at all for 10 retries followed by the existing timeout behavior, that would
suggest the flags field alone was gating all downstream processing and the packet is now
passing far enough to reach length/footer checks (`x20+0x1a`/`x20+0x1c`, seen at
`0x98faf4` in this pass's disassembly, flagged **UNKNOWN** as to their exact meaning) —
which would then be the next concrete target.

## 6g. 2026-09-14 (validation experiment) — Flags Fix Confirmed Live; New, Deeper Rejection Stage Found

Following §6f's "Recommended Next Experiment" exactly: the local LoginApp responder
(`mitm/local_baseapp_capture.py`) was changed to **prepend** `struct.pack('<H', 0x0001)`
(the genuine flags value taken from our own captured client requests) to the existing
20-byte `LoginReplyRecord` body, making the reply 24 bytes instead of 22
(`0100ac10010261b20000ac10010261b20000785634120000`). This is not a new blind guess — it
is the single, minimal change §6f's disassembly pointed to. A fresh device run (PID
`21283`, new `strace`+`logcat` capture) was performed to observe the result.

### Result: the predicted rejection is GONE

**CONFIRMED**: across the entire 10-retry capture window, the
`Nub::processFilteredPacket(...): received packet with bad flags ...` line **never
appears again** (it appeared in every single one of the prior 10/10 retries in §6f's
capture with the old reply). This directly confirms §6f's disassembly-derived hypothesis:
the first two bytes of the wire payload are read and validated as a Mercury packet flags
field, and `0x0001` passes that check where `0x10ac` did not.

### Result: a new, deeper, distinct rejection now fires

The client did **not** proceed to a successful login — it now fails at the **next stage
of Mercury bundle parsing**, with a clear, different, and equally concrete log chain,
repeating once per retry for all 10 retries and then giving up exactly as before:

```
[ERROR] Bundle::iterator::unpack( longEntityMessage ): Not enough data on stream at 2 for payload (17 left, needed 272)
[ERROR] Bundle::iterator::unpack: Got corrupted message header
[ERROR] Nub::processOrderedPacket( 172.16.1.2:25000 ): Discarding bundle due to corrupted header for message id 172
[WARNING] MainApp::poll: poll returned unexpectedly (REASON_CORRUPTED_PACKET).
```

...followed, after the 10th occurrence, by the same give-up line as §6f
(`MainApp::poll: disconnected since we have too may corruptted packet`), and then the
final outcome:

```
[ERROR] RetryingRequest::handleException( login ): Final attempt of 10 has failed (REASON_TIMER_EXPIRED), aborting
[ERROR] ServerConnection::logOnComplete: Logon failed (Mercury::REASON_TIMER_EXPIRED)
```

This is genuine forward progress, not a cosmetic change: the rejection point moved from
the earliest possible framing check (packet-level flags) to a **later, bundle-content**
check (per-message header parsing inside the bundle), exactly the kind of "different,
specific next rejection reason" the task asked to trace rather than guessing blindly
further.

### Static confirmation: the message-ID field, byte-for-byte

`Nub::processOrderedPacket` (live xref confirmed at `0x991250`, format string
`"Nub::processOrderedPacket( %s ): Discarding bundle due to..."` at `0x2a5dc7d`) and
`Bundle::iterator::unpack`'s two error paths (live xrefs confirmed at `0x983b78` for the
"Not enough data..." message, format string at `0x2a5b5a1`; `0x983cd0`/`0x983ce0` for
"Got corrupted message header", format string at `0x2a5b717`) were disassembled. Prologue
at `0x983b24`/`0x983b30`:

```
0x983b3c: ldrh w22, [x19, #0x20]     ; w22 = *(uint16_t*)(this+0x20)  -- a stream-shaped object's field
0x983b40: ldrh w23, [x19, #0xa]      ; w23 = *(uint16_t*)(this+0xa)   -- current read position
0x983b98: ldr  x2,  [x19]            ; x2 = underlying buffer pointer
0x983ba8: add  x9,  x2, #0x60        ; x9 = buffer + 0x60  -- SAME +0x60 wire-data-start offset
                                      ;   confirmed in Nub::processFilteredPacket (S6f)
0x983bac: ldrb w8,  [x9, x8]         ; w8 = *(uint8_t*)(wire_data + current_position)
                                      ;   ONE BYTE read -- this is the "message id"
```

**CONFIRMED**: the message ID is read as a **single byte**, at stream position 2 — i.e.
**wire offset 2, immediately following the 2-byte flags field** — matching the log's
"at 2" and matching our payload's byte value at that exact position: our 24-byte reply's
third byte (index 2) is `0xac` = **172 decimal**, exactly the "message id 172" reported.
This is not a new hypothesis; it is a direct, byte-identical confirmation of a
mechanically predictable consequence of §6f's finding (we never removed or replaced the
leftover raw `LoginReplyRecord` bytes after the flags field, so whatever byte happened to
be there was always going to be read as a message ID).

**PLAUSIBLE, not investigated further this pass**: message ID 172 apparently resolves,
via this client's message/interface definition tables, to an unrelated message named
`longEntityMessage` requiring a fixed 272-byte payload — almost certainly an incidental
ID collision with some large entity-replication message defined elsewhere in the game's
message tables, not a meaningful signal about the LoginReply format. Chasing the message
ID table itself is a much larger, separate research task and was not pursued here.

### Field Table Update (supersedes any earlier guesses)

| Offset | Size | Field | Status | Evidence |
|---|---|---|---|---|
| 0–1 | 2 bytes, LE | Mercury packet flags | **CONFIRMED** | `Nub::processFilteredPacket` (`0x98fa30`), byte-for-byte match in two independent runs (§6f reject, §6g accept) |
| 2 | 1 byte | Message ID | **CONFIRMED** (as a field boundary/width); **UNKNOWN** (as to which ID(s) are valid for a LoginReply) | `Bundle::iterator::unpack`/`Nub::processOrderedPacket` (`0x983b24`), byte-for-byte match to logged "message id 172" |
| 3+ | ? | Message-specific payload, shape depends on message ID | **UNKNOWN** | Not reached — the client fails before ever parsing anything at this offset as LoginReply-specific content |
| (end) | 2 bytes | Footer (previously assumed `00 00`) | **UNKNOWN, now lower-confidence** | Never validated in any test so far — every test has failed before reaching a footer check |

### What This Means For `0x937df0` (§6c–§6e) — Reinforces §6f's Negative Result

Neither `Nub::processFilteredPacket` nor `Bundle::iterator::unpack`/`Nub::processOrderedPacket`
are anywhere near `0x937df0`'s code region (`0x983xxx`/`0x98fxxx`/`0x991xxx` vs. `0x937xxx`).
Two independent, evidence-confirmed rejection stages have now been fully explained without
any involvement of `0x937df0`. **§6f's negative result stands and is strengthened**:
`0x937df0` is very likely an unrelated periodic retry-rebuild routine, not part of the
reply-rejection causal chain.

### Recommended Next Experiment

The message ID must be a value this client's LoginApp-reply handling code recognizes as
valid before any LoginReply-specific fields can be inspected. Finding that valid ID
requires locating the client's Login-related message ID definitions (most plausibly
inside the already-confirmed `LoginHandler`/`handleMessage` cluster or an associated
interface/message-table constant, not yet searched for this specific purpose) — this is
now the single highest-value next static target, since it is a small, bounded search (one
constant) rather than a broad guess.

## 7. Files/Evidence

- `scratch/find_recvfrom_plt.py`, `scratch/hook_recvfrom_raw.js` — reused from the previous
  pass, unchanged.
- No new scratch scripts were needed for §6a–§6e — all work was done via direct Python
  analysis of `03_lib/libclient_arm64.so` using the existing `scratch/xref_lib.py`
  utilities, run interactively (not saved as standalone scripts, since each query built on
  the previous one's exact output).
- §6f (this pass): `scratch/phase3_strace.txt` (fresh `strace -f -tt -T -e
  trace=network,desc -p <pid>` capture, TID `20216`, FD `198`, PID `20126`),
  `scratch/full_logcat_p3.txt` (`adb logcat -d -v time` pulled immediately after, containing
  the full `Nub::processFilteredPacket`/`MainApp::poll: disconnected...` log lines),
  `scratch/processFilteredPacket_full.txt` (disassembly dump of `0x98f900`–`0x98fc00` via
  `xref_lib.print_disasm`), `scratch/server_phase3.log` (local LoginApp/BaseApp responder
  log for this run).
- §6g (validation experiment): `mitm/local_baseapp_capture.py` (reply changed to prepend
  `flags=0x0001`, 22→24 bytes), `scratch/phase3f_strace.txt` (PID `21283`),
  `scratch/full_logcat_p3f.txt` (contains the new `Bundle::iterator::unpack`/
  `Nub::processOrderedPacket`/`RetryingRequest::handleException` chain),
  `scratch/unpack_msgid_full.txt` (disassembly of `0x983a80`–`0x983ce0`), `scratch/server_phase3e.log`
  (server log showing the 24-byte reply actually sent). Note: two stray Python server
  processes from earlier turns were found still bound to port 25000 mid-experiment,
  causing one confusing false-negative run (the client received an old, unpatched reply
  from a stale process) before all were killed via PowerShell `Stop-Process` and a single
  clean instance restarted — flagged here so this operational hazard is not repeated.
