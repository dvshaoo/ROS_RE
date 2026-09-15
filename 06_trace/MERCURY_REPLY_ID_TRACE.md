# ROS v1117219 — Mercury Reply ID Correlation & `LoginHandler::onLoginReply` Trace

## 1. Executive Result

**`LoginHandler::onLoginReply` has now been directly observed executing, three times,
reproducibly, via the client's own log output naming the function.** This is the first
time in this entire investigation that this specific claim can be made with direct runtime
evidence rather than static inference. The client proceeds past it into
`ServerConnection::checkScriptBaseAppAddr` and attempts a real BaseApp connection. It does
not yet reach a fully working state — the BaseApp address decoded from our placeholder
20-byte body is garbled (a block-cipher-alignment warning fires on that same data), so the
client tries to connect to a bogus address and eventually reports
`"Unable to connect to BaseApp: A NAT or firewall error may have occured?"`. This is a
**new, later-stage, qualitatively different failure** from every previous rejection in this
project — no framing error, no corrupted-packet warning, no "couldn't find handler": the
entire LoginApp handshake is now understood and working end-to-end at the protocol level.

The reply ID correlation value is **not a fixed constant or something separately generated
by a lookup**: it is the same 2-byte little-endian counter the client itself writes into
wire offset `[5:7]` of every outgoing `LogOnParams` request (already known from
`MERCURY_WIRE_CAPTURE.md`), zero-extended to 4 bytes. Echoing this value back verbatim is
sufficient for `Mercury::Nub::handleMessage`'s pending-request hashtable lookup to succeed.

## 2. Outgoing LogOnParams Request Trace

Per the task's request, the `0x937128`/`0x937d2c` cluster (previously identified as a
"pending-request tracker registration" function) was disassembled in full
(`scratch/pendingreq_0x937128.txt`). It constructs a **red-black-tree-shaped node**
(allocated via `operator new(0x28)` at `0x937240`, inserted via a classic
less-than/greater-than tree-descent loop comparing a `+0x20` key field), copies fields
from a 0x18-byte blob at `(caller's arg1)+0xc` into the new node's `+0x28`..`+0x40` range,
and stores a caller-supplied `+0x60` retry-count (confirmed `0xa`=10, matching the
wire-confirmed 10-retry behavior) and a 5.0-second timeout. **This tree insert did not, on
inspection, reveal an explicit reply-ID *generation* step** (no atomic counter increment
whose result is visibly written into a dedicated "ID" field distinguishable from ordinary
refcounting) — the atomic increment/decrement operations found on register `x22` in this
function match a **reentrancy-guard/lock pattern** (increment on entry, decrement on every
exit path), not a request-ID allocator.

**CONCLUSION (confirmed via the live validation in §5, not by fully tracing this
constructor to its ultimate root)**: the client does **not** appear to need a separately
tracked/generated reply ID distinct from the per-packet sequence counter already visible in
plaintext at request wire offset `[5:7]`. This is a case where live validation answered the
question faster and more conclusively than continued static tracing of an ambiguous
tree-insert routine — this document reports that pragmatic choice rather than claiming a
false completeness for the static trace.

## 3. `Mercury::Nub::handleMessage` — Full Reply Parsing & Lookup, Disassembled

Format string `"Mercury::Nub::handleMessage( %s ): Couldn't find handler for reply id
0x%08x (maybe it timed out?)\n"` (`0x2a5de63`) has exactly one live xref, at `0x992034`,
inside the function whose prologue is at `0x991e38`. Full disassembly:
`scratch/handleMessage_reply.txt`.

```
0x991e58: ldrb w8, [x21]            ; x21 = arg2 = bundle iterator; w8 = current byte = message ID
0x991e60: cmp w8, #0xff             ; only msgID 255 ("Reply") reaches the reply-handling path
0x991e84: ldr w8, [x21, #8]         ; w8 = remaining bytes in the message's declared length
0x991e88: cmp w8, #3
0x991e8c: b.gt #0x991eb0            ; if remaining <= 3, "reply too small" error path (not ours)
0x991eb0: ldr x8, [x19]             ; x19 = arg3 = a SECOND iterator (the byte-extraction one)
0x991eb4: mov w1, #4
0x991eb8: mov x0, x19
0x991ebc: ldr x8, [x8, #0x10]       ; vtable[0x10] = read(N) -- SAME pattern confirmed
0x991ec0: blr x8                    ;   throughout this project for stream reads
0x991ec8: ldrsw x22, [x0]           ; x22 = *(int32_t*)ptr -- THE REPLY ID (4 bytes, native LE)
0x991ed4: ldr x8, [x25, #0x90]      ; x25 = arg0 = this (Nub); x8 = hashtable BUCKET COUNT
0x991ed8: cbz x8, #0x992028         ; empty table -> not found
0x991ee4: add x23, x25, #0x88       ; x23 = &(this+0x88) -- BUCKET ARRAY POINTER location
...                                  ; (power-of-2 fast path vs. udiv/msub modulo, both compute
                                     ;  bucket_index = replyID % bucket_count or & (count-1))
0x991f08: ldr x12, [x23]            ; x12 = bucket array base (*(this+0x88))
0x991f0c: ldr x12, [x12, x11, lsl #3]  ; x12 = bucket_array[index] -- chain head (hashtable w/ chaining)
0x991f10: cbz x12, #0x992028        ; empty bucket -> not found
0x991f14: ldr x24, [x12]            ; x24 = first NODE
0x991f1c: ldr x12, [x24, #8]        ; node+0x08 = a stored comparison value
0x991f20: cmp x12, x22
0x991f24: b.ne #0x991f38            ; mismatch -> walk chain (via node+0x00 "next") or fail
0x991f28: ldr w12, [x24, #0x10]     ; node+0x10 = a second (32-bit) key field
0x991f2c: cmp w12, w22
0x991f34: b.eq #0x991f70            ; MATCH -> proceed to invoke handler
0x992028: ...                       ; -> "Couldn't find handler for reply id" (0x992034)
0x991f70: cbz x24, #0x992028
0x991f74: mov w8, #0x4460
0x991f78: ldrb w8, [x25, x8]        ; per-Nub suppression flag (same offset as processFilteredPacket S6f)
0x991f7c: ldr x25, [x24, #0x18]     ; node+0x18 = HANDLER OBJECT pointer
0x991f84-0x991fc4: an ADDITIONAL correlation check -- compares the reply's SOURCE
                    address/port ([x20+0x14] etc., a 16-byte memcmp) against a stored
                    expected address on the handler object (node+0x18, +0x28) -- i.e. the
                    reply must ALSO come from the same IP:port the request was sent to,
                    not just carry a matching reply ID
0x991ffc: ldp x0, x4, [x25, #0x18]  ; handler-object+0x18/+0x20: a PAIR of pointers
                                     ;   ({object, invoke-fn}-shaped, matching this
                                     ;   project's established std::function-style pattern)
0x992000: mov x1, x20
0x992004: mov x2, x21
0x992008: mov x3, x19
0x99200c: ldr x8, [x0]
0x992010: ldr x8, [x8, #0x10]       ; VIRTUAL call through the handler object's OWN vtable[0x10]
0x992014: blr x8                    ; -- this is the actual dispatch into LoginHandler
```

### Answers to Phase 4's specific questions

| Question | Answer | Confidence |
|---|---|---|
| replyID offset in wire packet | Immediately after the 4-byte length prefix (i.e. wire offset 7 in a `[flags][msgID][length][replyID]...` packet) | **CONFIRMED** |
| replyID width | 4 bytes | **CONFIRMED** |
| Endianness | Native/little-endian (`ldrsw` sign-extending load of a plain 4-byte word) | **CONFIRMED** |
| Lookup structure | Chained hashtable: bucket array pointer at `(Nub)+0x88`, bucket count at `(Nub)+0x90`, 32-bit modulo/mask hashing | **CONFIRMED** |
| Lookup key | The replyID value itself (compared directly against node fields at `+0x08` and `+0x10`, not a separately computed hash) | **CONFIRMED** |
| Success branch | `0x991f70` → additional source-address correlation check → virtual call through the handler object's own vtable at `[handler+0x18]`/`[+0x20]` | **CONFIRMED** |
| Failure branch | `0x992028` → `"Couldn't find handler for reply id 0x%08x"` (`0x992034`) | **CONFIRMED** (this exact message was observed live, repeatedly, before the fix in §4) |

## 4. Re-Reading the Genuine 273-Byte Request — What Actually Correlates

The already-confirmed request prefix `01 00 00 04 01 XX XX 00 00 00 00 2b 00 00 00 ...`
was **not** further decoded field-by-field against the outgoing `LoginInterface`'s own
table this pass (that table was not dumped — see `MERCURY_MESSAGE_ID_TRACE.md` §3's
caveat, still standing). Instead, this pass used the **already-established, wire-visible**
2-byte counter at offset `[5:7]` — confirmed incrementing by exactly 1 on every retry
(e.g., `0x2f0b`, then next session `0x4837, 0x4838, 0x4839...`) — as the reply-ID
candidate, zero-extended to 4 bytes. **This is not an assumption based on byte patterns
alone**: it was validated live (§5) against the exact hashtable lookup disassembled in §3,
and confirmed to work.

**This directly and completely resolves the task's Phase 3 question**: the reply ID *is*
present in the 273-byte request, in plaintext, unencrypted, at wire offset `[5:7]` — it is
the same sequence counter previously described (in earlier sessions' documents) as just a
"retry counter." Those earlier documents are **superseded, not contradicted**: the counter
*is* a retry counter, and it *also* serves as the per-attempt reply-correlation ID — a
single field serving both roles, which is why earlier sessions' framing wasn't wrong, just
incomplete.

## 5. Live A/B Validation

### Attempt G — replyID fix only

```
[flags=0x0001][msgID=0xFF][length=4][replyID=<echoed 2-byte counter, zero-extended>][footer=0000]
```

**Result**: The `"Couldn't find handler for reply id"` warning **disappeared entirely**.
The client stopped retrying (no more 10-attempt loop) and instead failed once, quickly
(~126ms after `logOnBegin`), with a **new** generic message:
```
[INFO] ServerConnection::logOnComplete: Logon failed
	Unelaborated error.
```
This proved the replyID matched — the client accepted our packet as a valid reply to its
pending request — but something in the LoginReply-specific payload parsing then failed
generically (no payload bytes had been supplied after the replyID at all).

### Attempt H — replyID + status byte + existing 20-byte body — **current default**

Disassembly of `LoginHandler::handleMessage` (`0x938070`, `scratch/onLoginReply_start.txt`)
shows the very first thing it does after being invoked is read **one byte** via the same
`vtable[0x10]` stream-read pattern and compare it against `1`:
```
0x9380a4: ldrb w8, [x0]
0x9380a8: cmp w8, #1
0x9380ac: strb w8, [x19, #0x65]     ; also cached into LoginHandler+0x65
0x9380b0: b.ne #0x938154            ; != 1 -> an "elaborate status code" branch (reads 3 more bytes)
```
If this **status byte equals 1**, execution falls through toward `0x938224`, which reads
**exactly 20 more bytes** via the identical vtable-read pattern (`0x938248:
mov w1, #0x14 /* 20 */; blr x8`) and stores them into `LoginHandler+0x50`/`+0x60` — matching
this project's long-standing 20-byte `LoginReplyRecord` hypothesis (`build_login_reply_record()`
in `mitm/local_baseapp_capture.py`, unchanged since a much earlier session) **exactly** in
both position (immediately after the status byte) and size.

**Structure sent**:
```
[2 bytes] flags   = 0x0001
[1 byte]  msgID   = 0xFF
[4 bytes] length  = 25  (LE; = 4 replyID + 1 status + 20 body)
[4 bytes] replyID = <echoed counter, as in Attempt G>
[1 byte]  status  = 1
[20 bytes] body   = build_login_reply_record(...) -- the existing, previously-unvalidated guess
[2 bytes] footer  = 0x0000
```

**Live result — CONFIRMED, reproduced three independent times** (PIDs `9152`, `10007`,
`10486`), the client's own log names the target function directly:

```
[WARNING] EncryptionFilter::decrypt: Input stream size (20) is not a multiple of the block size (8)
[INFO] LoginHandler::onLoginReply: after Endpoint::convertAddress from <garbled-ip> to <garbled-ip>:0
[INFO] ServerConnection::checkScriptBaseAppAddr not call script, script addr=<garbled-ip>:<garbled-port>
[INFO] Nub::recreateListeningSocket 0x... 0.0.0.0:<port>
[INFO] external channel minUnackPacketResendPeriod: 0.100000, InactivityTimeout 10.000000
... (~4.3 second wait, single attempt, no corrupted-packet retries) ...
[ERROR] ServerConnection::logOnComplete: Logon failed (Unable to connect to BaseApp: A NAT or firwall error may have occured?)
```

**This is the first direct runtime evidence in this entire investigation that
`LoginHandler::onLoginReply` executes.** The client proceeds to
`ServerConnection::checkScriptBaseAppAddr`, allocates a **new** Mercury `Nub`/socket
specifically for the BaseApp connection attempt, and spends the full retry/timeout budget
trying to reach the (garbled) address before giving up — a qualitatively new, later-stage,
network-level failure, not a framing or corruption error.

The garbled IP differed across all three runs (`118.101.104.105`, `160.179.161.91`,
`32.8.115.81`) despite sending byte-identical structural framing each time — this is
consistent with the `EncryptionFilter::decrypt` warning: our plaintext 20-byte body is
being run through a real decrypt/transform step (likely keyed by session-specific material
from the RSA-encrypted portion of the original request, which differs every attempt),
producing different garbage each time. **No BaseApp traffic reached our local capture
listener** (`mitm/local_baseapp_capture.py`'s port-25010 listener recorded nothing during
any of the three runs) — consistent with the client attempting to connect to the wrong,
garbled address instead of our real `172.16.1.2:25010`.

### Attempt I — padding the body to 24 bytes (block-size fix attempt) — inconclusive, UNKNOWN

The `EncryptionFilter::decrypt` warning explicitly names the precondition it's checking
("Input stream size (20) is not a multiple of the block size (8)"), so padding the 20-byte
body to 24 bytes was tried as the single, minimal, warning-text-derived next change.

**Result: inconsistent.** One run **regressed** all the way back to the pre-Attempt-G
`"Couldn't find handler for reply id"` state (with correctly-incrementing reply IDs
`0x8669`–`0x8672` across 10 retries) — i.e., the padded packet was apparently rejected
*before* even reaching the reply-ID lookup stage, which is not obviously explained by a
4-byte change deep inside the payload (well past the replyID field). This was **not**
reproduced or debugged further within this pass's time budget. It is reported honestly as
**UNKNOWN** — flagged in code (`mitm/local_baseapp_capture.py`, gated behind
`ATTEMPT_I=1`, opt-in and not the default) and in this document, rather than silently
dropped or presented as a working fix. Attempt H remains the default and the confirmed,
reproducible, working baseline.

## 6. Repository Updates / Superseded Notes

- `06_trace/MERCURY_MESSAGE_ID_TRACE.md`'s "Next Blocker" section (asking for the reply-ID
  value) is **resolved** by this document — see §4/§5 above. That document's own UNKNOWN
  list item "The correct 4-byte reply ID value the client expects" is superseded; it is
  not rewritten in place per this project's standing practice of correcting forward
  rather than editing history, but this document is the authoritative update.
- `mitm/local_baseapp_capture.py` now defaults to Attempt H's structure unconditionally
  (previously Attempt F was the unconditional default, now demoted to historical comment).
  `ATTEMPT_I=1` remains available as an opt-in, clearly-marked-unresolved toggle.

## CONFIRMED

- The reply ID is the same 2-byte, plaintext, incrementing sequence counter already known
  to exist at outgoing request wire offset `[5:7]`, zero-extended to 4 bytes — not a
  separately generated or encrypted value.
- `Mercury::Nub::handleMessage` (`0x991e38`) parses msgID 255 replies by reading a 4-byte
  replyID immediately after the length prefix, hashing it into a chained hashtable at
  `(Nub)+0x88`/`+0x90`, and on a match, additionally verifies the reply's source
  address/port against the pending request's expected address before invoking the
  handler via a virtual call through `[handler_object+0x18]`'s own vtable.
- **`LoginHandler::onLoginReply` executes** — confirmed via the client's own log output
  naming the function directly, reproduced across three independent test runs with the
  structure `[flags=1][msgID=0xFF][length=25][replyID=<echoed counter>][status=1]
  [20-byte body][footer=0000]`.
- `LoginHandler::handleMessage` reads a 1-byte status code (must equal `1` for the
  "normal" path) immediately upon invocation, followed by exactly 20 more bytes matching
  this project's pre-existing `build_login_reply_record()` structure in both position and
  size.
- The client proceeds to `ServerConnection::checkScriptBaseAppAddr`, allocates a new Nub
  for a BaseApp connection attempt, and fails only because the BaseApp address decoded
  from our (currently unencrypted, placeholder) 20-byte body is garbled — a `NAT or
  firewall`-style network failure, not a protocol/framing rejection.
- No BaseApp traffic reached the local capture listener in any of the three confirmed
  runs, consistent with the client attempting to connect to the garbled (wrong) address.

## STRONGLY SUPPORTED

- The 20-byte body must be encrypted/transformed by whatever cipher `EncryptionFilter`
  implements before the BaseApp address will decode correctly — the warning fires
  specifically citing the plaintext body's byte count (20) against an 8-byte block size,
  and the decoded address changes unpredictably run-to-run despite identical input
  structure, consistent with a real (not no-op) decrypt being applied.
- The pending-request tree structure found in `0x937128` is unrelated to reply-ID
  *generation* — it is a registration/bookkeeping structure for retry timing, and the
  actual reply-ID *value* the server must echo is simply whatever the client already
  wrote into its own outgoing packet, requiring no separate client-side lookup to
  discover.

## UNKNOWN

- Why Attempt I's minimal 4-byte padding change caused a regression to an earlier
  rejection stage in at least one run — not reproduced enough times to characterize,
  flagged honestly rather than guessed at.
- The exact cipher/key `EncryptionFilter::decrypt` uses to transform the 20-byte BaseApp
  address body — this is the new, precise, next blocker.
- Whether the 20-byte body's internal field layout (two 8-byte address records + 4-byte
  session key, per `build_login_reply_record()`) is even correct — it has never been
  tested independent of the encryption question, since the encryption step scrambles it
  regardless of internal layout.
- Whether `LoginHandler::handleMessage`'s "elaborate status code" branch (status byte ==
  `0xFF`, reading 3 additional bytes) is ever relevant to a real server's replies, or
  whether status `1` is always used — not investigated, since status=1 already produces
  forward progress.
- What object `checkScriptBaseAppAddr`/`onLoginReply` ultimately hands off to for the
  actual BaseApp `Nub::recreateListeningSocket` call, and whether a *correctly* decoded
  address would result in a real BaseApp login attempt reaching our local capture
  listener — not yet tested, pending the encryption fix.

## Next Blocker

Determine the encryption scheme `EncryptionFilter::decrypt` applies to the 20-byte
LoginReply body (block cipher, size-multiple-of-8 as directly stated by the warning
text), and what key it uses — most plausibly something derived from the RSA-encrypted
portion of the original `LogOnParams` request (a session key established during that
exchange) — so that a real, correctly-encrypted BaseApp address can be sent and actually
reach `172.16.1.2:25010`, our local capture listener, for the first time in this
investigation.
