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

## 7. Files/Evidence

- `scratch/find_recvfrom_plt.py`, `scratch/hook_recvfrom_raw.js` — reused from the previous
  pass, unchanged.
- No new scratch scripts were needed this pass — all work was done via direct Python
  analysis of `03_lib/libclient_arm64.so` using the existing `scratch/xref_lib.py`
  utilities, run interactively (not saved as standalone scripts, since each query built on
  the previous one's exact output).
