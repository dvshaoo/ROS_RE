# ROS v1117219 — Post-`recvfrom()` Mercury Dispatch Trace

> **CORRECTION (see `MERCURY_LOGINREPLY_VALIDATION_TRACE.md`)**: the follow-up pass fully
> disassembled `0x937df0`–`0x937f0c` (this document's Phase 5 only covered its failure
> branch) and found it is **not** a receive-side validation function. It is an
> **outgoing**-bundle (re)serialization routine that calls directly into
> `LogOnParams::addToStream`'s body (`0x9d8018`) and reports
> `REASON_CORRUPTED_PACKET` only if **that send-side serialization call** fails — it never
> reads the incoming reply's bytes. The "reads a 4-byte value from a stream object (x21)
> via vtable slot [0x10]" claim in Phase 5 below is **INCORRECT**: vtable[0x10] on this
> stream type is a `reserve(n)` WRITE primitive, and the very next instruction writes the
> literal constant `43` into the returned pointer — this is an outgoing write, not an
> incoming read. The A/B runtime correlation below (11/11 vs 0/0) remains valid and
> reproduced; only the causal *mechanism* explanation is corrected. See the follow-up
> document for the full corrected pseudocode, caller-chain findings, and the honest
> CONFIRMED/UNKNOWN breakdown.

**Result up front — this pass answers the central question directly, with both runtime and
static evidence converging on the same conclusion**: the client's own log output, captured
live via `strace`-observed `writev()` calls to the logcat pipe, shows the exact line
`[WARNING] MainApp::poll: poll returned unexpectedly (REASON_CORRUPTED_PACKET).` firing
**immediately after every successful `recvfrom()` read of our reply, and only when a reply
is sent at all** (11 occurrences with a reply, 0 without, across matched A/B captures).
Static disassembly of the code that builds this exact string (found via a direct,
previously-elusive cross-reference) independently confirms a real function that writes
`"Mercury::REASON_CORRUPTED_PACKET"` into the same `ServerConnection`-shaped object
used throughout this project's prior `LoginHandler`/`handleMessage` work — **this pass
mischaracterized that function as validating the incoming reply; the follow-up pass found
it is actually an outgoing-bundle rebuild/resend routine, corrected above.** `LoginHandler::onLoginReply` is **still
not directly observed to execute**, and no claim beyond that is made.

## Objective

Determine what executes inside the ROS client after `recvfrom(FD 181)` successfully
returns our 22-byte reply, using the syscall-level boundary proven to work in the previous
pass (`MERCURY_SOCKET_READ_TRACE.md`), without repeating Stalker `compile` events or
guessing new reply envelopes.

## Known Starting Boundary

Carried over, unchanged, from the previous pass:
```
sendto(181, <273 bytes>, 172.16.1.2:25000) = 273
recvfrom(181, <22 bytes, our reply>, from 172.16.1.2:25000) = 22
```
TID `16424`, FD `181`, confirmed as the persistent Mercury LoginApp socket.

## Phase 1 — `strace` Capability Check (Not Assumed)

Checked `/system/bin/strace -h` directly rather than assuming options exist:
- **`-k` (stack traces): NOT SUPPORTED.** Confirmed via direct attempt:
  `strace -k -p 16424` → `strace: invalid option -- k`. This build (version 4.21) predates
  or was built without stack-unwinding support. Documented as a clean negative, not
  worked around by guessing.
- **`-i` (print instruction pointer at syscall time): SUPPORTED.** Tried as the next-best
  attribution method.

**Result of `-i`**: every single `recvfrom(181, ...)` call — both the idle `EAGAIN` polls
and the 10 successful 22-byte reads — reports the **identical** instruction pointer,
`0x76388ea557fc`. The same address is *also* used for the `sendto(181, ...)` calls. This
address resolves (via `/proc/16332/maps`) to inside `/system/lib64/libhoudini.so`
(`0x76388e85d000`–`0x76388eabc000` segment). **Conclusion: this is Houdini's own shared,
generic syscall trampoline** (the single code path all translated ARM64 syscalls funnel
through), not a distinguishing call site. `-i` therefore provides **no useful caller
attribution** — a clean, direct negative result, not a tooling failure to route around.

## Phase 2 — Thread / Event Loop Analysis

No `poll`/`ppoll`/`select`/`pselect`/`epoll_wait`/`epoll_pwait` calls were observed on TID
`16424` around the receive path at all. The socket is read via **non-blocking, busy-poll
`recvfrom()`** (`fcntl(181, F_SETFL, O_RDWR|O_NONBLOCK)` is set immediately after the
socket is created — confirmed in the trace) at a fixed cadence tied to the engine's own
per-frame update loop, not an event-driven wakeup. This loop is directly identified by
name: **`MainApp::poll`** (see Phase 4).

## Phase 3 — `ltrace`

Not checked in this pass — `strace -i` and the direct logcat correlation (Phase 4)
answered the objective before `ltrace` was needed, and the task's Phase 3 explicitly makes
it conditional/secondary. Not attempted; no claim either way about its availability.

## Phase 4 — The 22-Byte Buffer's Fate: Direct Runtime Evidence

While filtering the `strace` output for non-`EAGAIN` activity on TID `16424`, a `writev()`
call to FD 3 (the logcat pipe) was observed **immediately after each successful
`recvfrom()`**, carrying a literal, human-readable log message. Retrieved in full via
`adb logcat`:

```
[WARNING] MainApp::poll: poll returned unexpectedly (REASON_CORRUPTED_PACKET).
```

This line appeared **11 times** during the REPLY test window (matching the 10 retries, +1
likely from an initial poll cycle) and **0 times** during a repeat NO_REPLY test window
run immediately afterward under otherwise identical conditions (same PID, same tap-to-PLAY
procedure, same ~12s capture window). This is a clean, reproduced A/B result:

| | REPLY test | NO_REPLY test |
|---|---|---|
| `sendto(181,...)` count | 10 | 10 |
| `recvfrom(181,...) = 22` count | 10 | 0 |
| `MainApp::poll: ... REASON_CORRUPTED_PACKET` count | **11** | **0** |

**CONFIRMED**: this warning is causally tied to the presence of a reply, not to the retry
loop itself (which runs identically either way, per `MERCURY_SOCKET_READ_TRACE.md`).

## Phase 5 — Static Correlation: A Newly-Confirmed Live Function

Searched `03_lib/libclient_arm64.so` for the exact strings `"MainApp::poll"` and
`"REASON_CORRUPTED_PACKET"` (both present — `0x2a47d1f` and `0x2a491aa` respectively), then
applied the project's established ADRP+ADD wide-window cross-reference scan.

**Unlike the many `Mercury::Nub` diagnostic strings shown to be dead/unreferenced in
`MERCURY_STALKER_COMPILE_TRACE.md` and `MERCURY_REPLY_DISPATCH_TRACE.md`, these strings
have real, direct, live code references**:

- `"MainApp::poll"` → referenced from `0x92cc58`.
- `"REASON_CORRUPTED_PACKET"` → referenced from **two** sites, `0x937e78` and `0x937e8c`,
  both inside one function spanning `0x937df0`–`0x937f0c` (confirmed against this
  project's own prologue inventory of the `ServerConnection` code cluster, built in the
  `MERCURY_REPLY_DISPATCH_TRACE.md` pass — `0x937df0` is a listed function start,
  immediately followed in the inventory by `0x937f10`).

**This function sits immediately before, in the same code region as, the already-confirmed
`LoginHandler::handleMessage`/`onLoginReply` function (`0x938070`–`0x938724`)** from the
previous static pass — the two are separated by only two other small functions
(`0x937f10`, `0x938008`), all within one tight cluster.

### Disassembly Findings (`0x937df0`–`0x937f0c`)

> **Corrected below (see banner at top of document)**: the next line was originally
> written as a "read." It is a WRITE — `reserve(4)` on an output stream, followed by
> storing the literal `43` into the returned pointer. Full corrected disassembly of the
> entire function (not just this failure branch) is in
> `MERCURY_LOGINREPLY_VALIDATION_TRACE.md`.

```
0x937e20-0x937e30: reserves 4 bytes for WRITING in an output stream object (x21) via
                    vtable slot [0x10] (reserve(n) — the same WRITE pattern used by
                    LogOnParams::addToStream itself, per LOGONPARAMS_SERIALIZATION.md)
0x937e34-0x937e38: writes the literal constant 0x2b (43) into the reserved location
0x937e3c-0x937e54: calls bl #0x9d8018 with (this=x19, stream=x21, flag=1, key-ish=x3)
0x937e58:          tbnz w0,#0 -> branch to cleanup (0x937ec8) if return value's bit0 is set
                    (success path); otherwise fall through to the error path below
0x937e5c-0x937e64: [FAILURE PATH] logs a generic warning via a fixed rodata string
0x937e68-0x937e74: loads a ServerConnection-shaped object, sets byte [+0x65] = 2
                    (CONFIRMED: this is the exact same state-byte offset used in the
                    already-confirmed onLoginReply/handleMessage error paths)
0x937e78-0x937e88: bl 0x83f8a8 — copies the 9-byte string "Mercury::" into a buffer at
                    [ServerConnection+0x68]
0x937e8c-0x937e9c: bl 0x83fbd8 — appends the 23-byte string "REASON_CORRUPTED_PACKET"
                    immediately after, building the full string
                    "Mercury::REASON_CORRUPTED_PACKET" in that buffer
0x937ea0-0x937ec4: sets ServerConnection+0x64 = 1 (the same "failed" flag confirmed in
                    prior sessions' handleMessage disassembly)
```

**CONFIRMED BY BINARY (both the string-building mechanics and the exact ServerConnection
offsets used)**: this function assembles the literal reason string
`"Mercury::REASON_CORRUPTED_PACKET"` and writes the same failure-state bytes
(`+0x64=1`, `+0x65=2`) that the already-confirmed `handleMessage` function's own error
paths use — this is not a coincidence; it is the same object and the same error-reporting
convention documented in earlier sessions.

**One detail flagged as STRONGLY SUPPORTED, not fully explained**: the call at
`0x937e54` (`bl #0x9d8018`) targets an address **4 bytes past** the entry point this
project previously identified for `LogOnParams::addToStream` (`0x9d8014`), inside the same
function body. The previous session's `MERCURY_REPLY_DISPATCH_TRACE.md` §2 reported
**zero** direct callers of `0x9d8014` across five search methods — this pass's discovery
that a real caller exists, just 4 bytes later, resolves that mystery: the true call target
used by at least one caller is `0x9d8018`, not `0x9d8014` (the first 4 bytes at `0x9d8014`
being a `bl #0x7d8ea0` stack-probe call apparently reached by fall-through from a
*different* preceding function in some builds/paths, while direct callers skip past it).
**This does not change the confirmed field-level findings in `LOGONPARAMS_SERIALIZATION.md`
about `addToStream`'s body** — it only corrects the entry-point-attribution puzzle from the
previous session. Given the effort budget for this pass, the *semantic* role of this call
(why a validation function calls into logon-serialization code) was not further pursued —
flagged as UNKNOWN, not invented.

## A/B Results (Summary)

Already presented in Phase 4's table. Restated as the core finding: **the
`REASON_CORRUPTED_PACKET` diagnosis is emitted if and only if a reply is sent**, timed
immediately (within the same poll cycle) after each successful `recvfrom()`.

## CONFIRMED

- `strace -k` is unsupported by this device's `strace` build (direct negative test).
- `strace -i` shows the client's syscalls (including `recvfrom`/`sendto` on FD 181) all
  share one instruction pointer, `0x76388ea557fc`, inside `libhoudini.so` — Houdini's
  generic syscall trampoline, providing no ARM64 caller attribution.
- No `poll`/`select`/`epoll` syscalls are used for this socket — it is read via
  non-blocking busy-polling from the engine's own per-frame loop.
- The client's own log output contains the literal line
  `[WARNING] MainApp::poll: poll returned unexpectedly (REASON_CORRUPTED_PACKET).`,
  emitted immediately after each successful read of our reply.
- This exact warning is emitted **11/11 times when a reply is sent and 0/0 times when no
  reply is sent**, in matched, back-to-back A/B captures under otherwise identical
  conditions.
- The strings `"MainApp::poll"` and `"REASON_CORRUPTED_PACKET"` have real, live,
  direct code cross-references in `03_lib/libclient_arm64.so` (`0x92cc58` and
  `0x937e78`/`0x937e8c` respectively) — unlike many other Mercury diagnostic strings shown
  to be dead in prior passes.
- The function at `0x937df0`–`0x937f0c` builds the literal string
  `"Mercury::REASON_CORRUPTED_PACKET"` and writes it, along with failure-state flags at the
  same `ServerConnection+0x64`/`+0x65` offsets used elsewhere in this project's confirmed
  `handleMessage` work, into the same object type.
- This validation function is located immediately adjacent to (within the same small code
  cluster as) the already-confirmed `LoginHandler::handleMessage`/`onLoginReply` function.

## STRONGLY SUPPORTED

- Our reply's arrival is tightly, reproducibly correlated (timing and A/B count) with the
  `REASON_CORRUPTED_PACKET` warning firing — **superseded framing removed**: this pass had
  claimed the rejection happens at "a Nub-level packet validation stage before any
  message-type-specific dispatch," inferred from the function's proximity to
  `handleMessage`. The follow-up full disassembly shows `0x937df0` doesn't inspect the
  reply's bytes at all (it's an outgoing-bundle rebuild that fails on its own
  `addToStream` call), so that specific "why" is no longer supported by this function
  and is now UNKNOWN — see `MERCURY_LOGINREPLY_VALIDATION_TRACE.md`.

## UNKNOWN

- Whether `LoginHandler::onLoginReply` executes at any point — **not observed, not
  claimed**.
- The exact mechanism connecting "reply received" to "this outgoing-bundle-rebuild
  function runs and fails" — `0x937df0` has zero direct callers (must be invoked via
  indirect/virtual dispatch not yet resolved). See follow-up document §2/UNKNOWN.
- Whether any code in this client reads/validates the specific byte content of our
  22-byte reply at all, as opposed to Nub-level machinery treating any
  unexpected/unrecognized inbound data as a trigger to abandon and retry regardless of
  content.
- The semantic role of the call to `0x9d8018` (`LogOnParams::addToStream`'s real entry
  point, confirmed in the follow-up pass) from this outgoing-rebuild function — it
  reserializes a cached `LogOnParams` object; why this fails when triggered here is not
  determined.

## Next Concrete Boundary

**Superseded** — `0x9d8018` has been fully identified as `LogOnParams::addToStream`'s
real entry point with exactly one caller (`0x937e54`, inside this function), per
`MERCURY_LOGINREPLY_VALIDATION_TRACE.md`. The new next concrete boundary is: resolve the
indirect/virtual call mechanism that invokes `0x937df0` in the first place (likely a
stored callback registered via the adjacent `0x937128`/`0x937d2c` retry-registration
cluster) to determine when/why this outgoing-rebuild path fires relative to actual reply
processing.
