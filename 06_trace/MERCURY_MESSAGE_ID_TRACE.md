# ROS v1117219 — Mercury Message ID & Dispatch Table Trace

> **SUPERSEDED (2026-09-15, see `MERCURY_REPLY_ID_TRACE.md`)**: this document's "Next
> Blocker" and every `replyID = UNKNOWN` / "correct 4-byte reply ID value ... UNKNOWN"
> statement below is now resolved, not silently removed. The reply ID is the same 2-byte
> plaintext sequence counter already documented at outgoing request wire offset `[5:7]`
> (see `MERCURY_WIRE_CAPTURE.md`), zero-extended to 4 bytes — no separate generation or
> lookup mechanism was needed. Echoing it back, followed by a 1-byte status code (`=1`)
> and the existing 20-byte body, gets the client all the way to directly-confirmed
> execution of `LoginHandler::onLoginReply`. All CONFIRMED findings below about the
> message-ID/dispatch-table layer remain correct and unaffected; only the "what replyID
> value is needed" question is updated.

**Result up front**: Using a live `/proc/<pid>/mem` dump of the client's own in-memory
message dispatch table (not guesswork), this pass identifies the exact wire structure of
a Mercury packet after the 2-byte flags field, confirms message ID **255 (0xFF)** is the
client's own, code-named **"Reply"** entry — matching BigWorld's well-known
`Mercury::REPLY_MESSAGE_ID` convention — and, through two rounds of live A/B validation,
progressively eliminates every framing/bundle-corruption rejection seen in prior passes.
The final constructed candidate (**Attempt F**) is **fully accepted** at both the
packet-flags layer and the bundle/message-header layer — a first in this entire
investigation — and fails only at a much deeper, precisely-named layer:
`Mercury::Nub::handleMessage(...): Couldn't find handler for reply id 0x00000000`. This is
real, measured forward progress, not a guess that happened to work: every field in Attempt
F's structure is either directly read from the client's live memory or arithmetically
derived from two independent rejection messages. `LoginHandler::onLoginReply` is **still
not observed to execute** — the new, precise blocker is finding the correct 4-byte
**reply ID** value, which must correlate with something in the client's own outgoing
273-byte request. That correlation is the next concrete, bounded target and is not yet
resolved.

## Objective

Starting from the confirmed boundary in commit `0cd33ee` (flags=0x0001 accepted;
message ID read as 1 byte at wire offset 2; ID 172 collided with an unrelated
"longEntityMessage" definition requiring 272 bytes), determine the correct message ID
and full wire structure for a LoginApp→client LoginReply, using the client's own
implementation as the only source of truth — no brute-forcing, no generic-BigWorld-docs
guessing.

## Phase 1 — Disassembly of `processOrderedPacket` and `Bundle::iterator::unpack`

### `Nub::processOrderedPacket`

No fixed single "prologue" address was cleanly isolated — this function is large
(spans roughly `0x990b00`–`0x991780`+) and handles ordering/ack/sequence-number
bookkeeping in addition to per-message dispatch. The specific, relevant slice is the
message-ID table lookup at `0x990d44`–`0x990d74`:

```
0x990d44: sub x0, x29, #0xa0
0x990d48: bl  #0x983b10          ; peek the CURRENT byte at the stream's read position
                                  ;   (a 4-instruction helper: buf=[[x0]+[x0+0xa]]+0x60,
                                  ;   ldrb w0,[buf] -- confirmed: the message ID is a
                                  ;   single byte at wire offset = stream position)
0x990d4c: mov x8, x19             ; x19 = this (Nub-shaped object)
0x990d50: ldr x24, [x8, #0x40]    ; x24 = message dispatch table BASE (CONFIRMED, see Phase 2)
0x990d54: mov x19, x22
0x990d58: and w22, w0, #0xff      ; w22 = message ID (0-255)
0x990d5c: mov x21, x8
0x990d60: add x1, x24, x22, lsl #5  ; x1 = table_base + msgID*32  -- 32-BYTE ENTRIES, DIRECT INDEX
0x990d64: mov x23, x1
0x990d68: ldr x8, [x23, #0x10]!   ; x8 = *(entry+0x10); x23 becomes entry+0x10 (pre-index)
0x990d6c: cbz x8, #0x9910d4       ; NULL -> message ID has no registered entry at all
0x990d70: sub x0, x29, #0xa0
0x990d74: bl  #0x983b24           ; entry is registered -> call Bundle::iterator::unpack
```

Three distinct discard-reason format strings were found (all with live xrefs), confirming
three distinct failure branches after this lookup:

| Format string (rodata) | Meaning |
|---|---|
| `"...Discarding bundle after hitting unhandled message id %d\n"` (`0x2a5dc7d`) | ID has **no** table entry at all (the `cbz x8,...` branch at `0x990d6c` taken true) |
| `"...Discarding bundle due to corrupted header for message id "` (`0x2a5dcd7`) | ID **is** registered, but `Bundle::iterator::unpack` failed to parse its declared header/payload shape — **this is what fired for both our msgID=172 and (initially) msgID=255 tests** |
| `"...Discarding rest of bundle since chain too short for data "` (`0x2a5dd35`) | A length-accounting mismatch after a message was otherwise successfully parsed |

### `Bundle::iterator::unpack` (prologue `0x983b24`)

```
0x983b3c: ldrh w22, [x19, #0x20]   ; this-object field
0x983b40: ldrh w23, [x19, #0xa]    ; w23 = current stream read position
0x983b44: mov x21, x1              ; x21 = arg1 = the TABLE ENTRY pointer (unmodified,
                                    ;   i.e. entry+0x00, NOT the pre-indexed +0x10 the
                                    ;   caller used for its own null-check)
...
0x983ba8: add x9, x2, #0x60        ; x2 = underlying buffer object; +0x60 = wire-data start
                                    ;   (SAME offset confirmed in Nub::processFilteredPacket,
                                    ;   0x98fa68, for the flags field -- consistent: the
                                    ;   whole raw UDP payload begins at object+0x60)
0x983bac: ldrb w8, [x9, x8]        ; peek current byte (redundant re-derivation of msgID)
...
0x983cc8: ldr x1, [x21, #8]        ; x1 = *(entry+0x08)  -- CONFIRMED: the message's NAME
                                    ;   STRING POINTER (the "%s" in every log line: this is
                                    ;   what printed "longEntityMessage" and later "Reply")
0x983ccc: ldrh w2, [x19, #0xa]     ; w2 = stream position (the "at %d")
0x983cd0: adrp x0, #0x2a5b000      ; "...Not enough data on stream at %d for payload
0x983cd8: add  x0, x0, #0x6b5      ;  (%d left, needed %d)\n"
0x983cd4: sub  w3, w9, w11         ; w3 = actual remaining bytes ("left") -- see Phase 5
                                    ;   for the exact, confirmed off-by-2 footer correction
0x983cdc: bl   #0x1cad604
```

## Phase 2 — The Message ID Dispatch Table (Located Live, Not Guessed)

Rather than continuing to trace generic static "registration constructor" code (which
turned out to build multiple unrelated per-interface tables throughout the binary, making
static attribution slow and error-prone), this pass used the project's already-established
live-instrumentation capability (root `adb shell`, `/proc/<pid>/mem` reads) to read the
**actual, live table** directly:

1. Temporarily reused the existing `DEBUG_BADFLAGS` toggle (see `mitm/local_baseapp_capture.py`)
   to make the client reprint `Nub(0x76384d2d4000)::processFilteredPacket(...)`, capturing
   a genuine live Nub object pointer for that run's process (PID `5626`).
2. `su 0 dd if=/proc/5626/mem bs=1 skip=$((0x76384d2d4000+0x40)) count=8` — read the
   **table base pointer** stored at `this+0x40`: `0x76387511b000`.
3. Confirmed via `/proc/5626/maps` this address falls inside an anonymous
   `[anon:libc_malloc]` heap region — **CONFIRMED: this is a heap-allocated array, not a
   fixed static address**, explaining why earlier static-only relocation scanning
   (`.rela.dyn` search for `R_AARCH64_RELATIVE` entries pointing at
   `LoginHandler::onLoginReply`, `0x938070`) found nothing: the table is built and
   populated by the client's own C++ static initializers at process startup, not baked
   into the ELF's relocation data.
4. Dumped the full `256 * 32 = 8192`-byte table in one `dd` read and parsed it offline.

### Table Entry Format (32 bytes, CONFIRMED)

| Offset | Width | Field | Evidence |
|---|---|---|---|
| `+0x00`, low byte | 1 | Message ID (0–255) | Matches the table's own array index for every entry checked |
| `+0x00`, byte 1 | 1 | Variable-length flag (0 = fixed, 1 = variable) | Entries 0–4 have byte1=0; entries 5, 172, 255 (all confirmed variable-length messages) have byte1=1 |
| `+0x00`, bytes 4-7 (high32) | 4 | Fixed payload length (if flag=0) **or** number of bytes used for the length prefix (if flag=1) | Entry172 (variable) = 2 → matched a live-observed 2-byte length prefix exactly (see Phase 5); Entry255 (variable) = 4 → matched a live-observed 4-byte length prefix exactly |
| `+0x08` | 8 | Pointer to the message's name string (C string, e.g. `"longEntityMessage"`, `"Reply"`) | Directly read and printed by the client's own log calls (`ldr x1,[x21,#8]` in `Bundle::iterator::unpack`) |
| `+0x10` | 8 | "Registered" pointer — non-null test for `cbz` in `processOrderedPacket`; for msgID 255 this equals the **live Nub object's own address** (self-reference); for other IDs it is some other, not-yet-classified handler-shaped pointer | Read live: entry255's `+0x10` field == `0x76384d2d4000`, the exact printed Nub pointer for that run |
| `+0x18` | 8 | Always observed `0x0` in every entry checked | Not yet explained; flagged UNKNOWN |

**228 of 256 IDs were registered** (non-null `+0x10`) in the live dump — this table is a
large, general **client-receive interface**, not a small Login-only table; it appears to
be shared across all server connection types (BaseApp/CellApp entity messages together
with Mercury-level housekeeping messages like ID 255).

### Message ID 255 = "Reply"

```
entry255 raw:    ff 01 00 00 04 00 00 00 | 54 08 c6 05 00 00 00 00 | 00 40 2d 4d 38 76 00 00 | 00...
                 msgID=0xff, varflag=1,    namePtr -> "Reply"           handlerPtr = live Nub
                 lenfield(high32)=4                                    pointer itself
```

**CONFIRMED**: message ID 255 is variable-length with a **4-byte length prefix**, named
`"Reply"`, and its "handler" is the Nub object itself — i.e., it is not dispatched to a
generic named `MessageHandler` the way other messages are; it is consumed directly by
Nub-level reply-correlation logic. This matches BigWorld's documented convention that
`Mercury::REPLY_MESSAGE_ID` (255) is a protocol-level reserved ID used for **any** reply to
**any** request, regardless of which application-level interface (LoginApp, BaseApp,
CellApp) the original request belonged to — CONFIRMED here specifically for this client
binary's own compiled table, not asserted from external documentation alone.

## Phase 3 — Re-Reading the Genuine 273-Byte Request Under the New Model

The already-confirmed request bytes (e.g. `01 00 00 04 01 24 5a 01 00 00 00 2b 00 00 00
...`) can now be partially re-read:

- `[0:2]` = `01 00` → **flags = 0x0001** (CONFIRMED — same field, same interpretation, as
  the reply direction; this is a Nub/packet-level field, not direction-specific).
- `[2]` = `00` → message ID **0** in whatever table the **outgoing LoginInterface** uses.

**IMPORTANT CAVEAT, stated plainly**: the table this pass dumped and analyzed
(`this+0x40` on the Nub handling the LoginApp connection) is used for **decoding messages
the client receives**. It is very likely a *different* table (or at least a differently
enumerated ID space) from whatever table the client's own LoginInterface uses to *encode*
its own outgoing `LogOnParams` request — Mercury interfaces are normally defined and
numbered independently per direction/purpose. **This pass does NOT claim the outgoing
request's message ID 0 has any relationship to the receive-table's own (unrelated) entry
0.** No further attempt was made to fully decode the remaining request bytes
(`04 01 24 5a 01 00 00 00 2b 00 00 00...`) under the new model beyond the flags field —
correctly decoding them would require finding and dumping the **outgoing** interface's own
table, which was not done this pass (see Next Blocker).

## Phase 4 — `LoginHandler::onLoginReply`'s Own Message ID: Not Resolved This Pass

A static search for `LoginHandler::onLoginReply` (`0x938070`) as a raw 8-byte pointer
value anywhere in the file, and as a `R_AARCH64_RELATIVE` relocation target in
`.rela.dyn`, both returned **zero matches**. Combined with Phase 2's finding that the
dispatch table is a **heap-allocated, runtime-populated structure**, this negative result
is now explained rather than mysterious: static relocation scanning cannot find a pointer
that is only ever written by executing code at startup, never stored as a link-time
constant. Locating `onLoginReply`'s actual registered ID would require either (a) tracing
the specific static-initializer call that registers it (analogous to the `longEntityMessage`
registration constructor found at `0x80e690`–`0x80e77c`, calling `bl 0x98b30c` per message),
matched by searching for a xref to `LoginHandler::onLoginReply`'s address as an argument to
that same registration function, or (b) a live-memory search for a table entry whose
`+0x10` "handler" pointer resolves to an object whose vtable ultimately calls
`0x938070`. **Neither was completed this pass** — flagged as the honest gap, not
papered over.

## Phase 5 — Minimal Valid Reply: Built, Tested, and Progressively Corrected Live

### Attempt E (first candidate under the new model)

```
[2 bytes] flags       = 0x0001
[1 byte]  msgID       = 0xFF (255, "Reply")
[4 bytes] length      = 4  (LE)
[4 bytes] replyID     = 0  (placeholder, deliberately not guessed further)
```
11 bytes total, **no footer**.

**Live result**: `Bundle::iterator::unpack( Reply ): Not enough data on stream at 2 for
payload (2 left, needed 4)`. The name **"Reply"** in this message — where the previous
pass's test showed **"longEntityMessage"** — is itself direct confirmation that the
msgID=0xFF byte was read and correctly matched to table entry 255.

### The footer arithmetic (CONFIRMED, not assumed)

Comparing this rejection's numbers against the previous pass's msgID=172 rejection
(`06_trace/MERCURY_REPLY_DISPATCH_TRACE.md` §6g: 24-byte packet, "17 left, needed 272"):

| Test | Packet size | Header consumed (flags+msgID+lengthprefix) | Naively expected "left" | Actually reported "left" | Discrepancy |
|---|---|---|---|---|---|
| msgID 172 (§6g) | 24 | 2+1+2 = 5 | 24−5 = 19 | 17 | exactly **−2** |
| msgID 255, Attempt E | 11 | 2+1+4 = 7 | 11−7 = 4 | 2 | exactly **−2** |

**CONFIRMED**: both independent tests show the same exact −2 discrepancy. The only
explanation consistent with both is that **the last 2 bytes of every packet are reserved
for a mandatory trailing footer and are excluded from the payload's available-byte
count**, regardless of message type. This is not a new guess about packet *content* — it
is a mechanical deduction from two independently observed, code-generated numbers.

### Attempt F (footer-corrected candidate) — current default in `mitm/local_baseapp_capture.py`

```
[2 bytes] flags       = 0x0001
[1 byte]  msgID       = 0xFF (255, "Reply")
[4 bytes] length      = 4  (LE)
[4 bytes] replyID     = 0  (placeholder, deliberately not guessed further)
[2 bytes] footer      = 0x0000
```
13 bytes total.

**Live result (PID `6884`, full 10-retry capture)**: **zero** `REASON_CORRUPTED_PACKET`
warnings, **zero** `Bundle::iterator::unpack` errors, **zero**
`Nub::processOrderedPacket` discard messages — for the first time in this entire
investigation, every single one of the 10 retries passes packet-flags validation AND
bundle/message-header validation cleanly. The only warning is a **new, much more specific,
much deeper** one:

```
[WARNING] Mercury::Nub::handleMessage( 172.16.1.2:25000 ): Couldn't find handler for reply id 0x00000000 (maybe it timed out?)
```

Login still ultimately fails after 10 attempts with the same
`RetryingRequest::handleException`/`REASON_TIMER_EXPIRED` outcome as every prior test —
but the **reason** has moved from a framing/corruption rejection to a **reply-correlation**
rejection: the client accepts the packet as a well-formed "Reply" message and attempts to
match its 4-byte reply ID (currently our placeholder `0`) against its table of pending
requests, and fails to find one, exactly as expected for a fabricated placeholder value.

### Confidence-Labeled Field Table (current best understanding)

| Offset | Size | Field | Status |
|---|---|---|---|
| 0–1 | 2, LE | Flags | **CONFIRMED** (`= 0x0001`) |
| 2 | 1 | Message ID | **CONFIRMED** (`= 0xFF`, "Reply"/`REPLY_MESSAGE_ID`) |
| 3–6 | 4, LE | Length prefix (byte count of what follows, excluding footer) | **CONFIRMED** structurally (width and presence); the *value* `4` is our own choice for this minimal probe, not a discovered constant |
| 7–10 | 4, LE | Reply ID (must match the client's own pending request) | **CONFIRMED** as a required, distinct field (via the exact "Couldn't find handler for reply id" wording and width match); **UNKNOWN** what value is correct |
| 11–12 | 2 | Footer | **CONFIRMED** to exist and be excluded from payload-length accounting; exact required content **UNKNOWN** beyond "0x0000 does not itself cause rejection" |
| (beyond) | ? | Actual LoginReply-specific payload (BaseApp address, session key, etc.) | **UNKNOWN** — not yet reached, since the reply-ID mismatch is reported and processing stops before any further payload would be inspected |

## Phase 6 — Live A/B Validation Summary

| Attempt | flags | msgID | Structure | Result |
|---|---|---|---|---|
| D (prior pass) | 0x0001 | *(none — raw LoginReplyRecord bytes)* | 24 bytes, no msgID framing | `Bundle::iterator::unpack( longEntityMessage )`: corrupted header, msgid **172** (accidental collision with our own payload's leftover byte) |
| E (this pass) | 0x0001 | 0xFF | 11 bytes, no footer | `Bundle::iterator::unpack( Reply )`: corrupted header — footer arithmetic revealed |
| F (this pass, current default) | 0x0001 | 0xFF | 13 bytes, footer added | **No framing/corruption errors at all.** New rejection: `Couldn't find handler for reply id 0x00000000` |

Per the task's explicit instruction, no further speculative field was added after Attempt
F succeeded at clearing the framing layer — this document stops here to report the new
layer precisely, rather than guessing a reply-ID value with no evidence behind it.

## CONFIRMED

- Wire structure after the already-confirmed 2-byte flags field:
  `[1-byte message ID][message-type-dependent header][payload][2-byte mandatory footer]`.
- Message ID is read as a single byte, used as a direct index (`× 32`) into a
  heap-allocated, 256-entry dispatch table pointed to by `(Nub object)+0x40`.
- Each 32-byte table entry contains, at minimum: a packed `{id, variable-length-flag}` at
  `+0x00` low bytes, a fixed-length-or-length-prefix-width value at `+0x00` high 4 bytes, a
  name-string pointer at `+0x08`, and a "handler" pointer at `+0x10`.
- Message ID **255 (0xFF)** is named `"Reply"` in this table, uses a 4-byte length prefix,
  and its handler field self-references the Nub object — this is the code-confirmed
  message ID for Mercury replies of any kind, including (by architectural necessity, though
  not yet directly observed) LoginReply.
- The last 2 bytes of every tested packet are a mandatory footer, excluded from the
  payload-length accounting used in "not enough data" error messages (confirmed via
  matching arithmetic across two independent, unrelated test packets).
- A candidate reply using this structure (`flags=1, msgID=0xFF, 4-byte length=4, 4-byte
  replyID=0, 2-byte footer`) is **fully accepted** by both `Nub::processFilteredPacket`
  and `Nub::processOrderedPacket`/`Bundle::iterator::unpack` — zero corruption errors
  across 10 retries, a first in this investigation.
- The next, deeper rejection is generated by `Mercury::Nub::handleMessage`, which reports
  "Couldn't find handler for reply id 0x00000000" — a reply-ID correlation failure, not a
  framing/corruption failure.

## STRONGLY SUPPORTED

- The dispatch table dumped and analyzed here is a general client-receive interface
  (228/256 IDs registered) shared across connection types, not a small Login-specific
  table — msgID 255's universal "Reply" role is consistent with this.
- The outgoing 273-byte LogOnParams request's own message ID byte (`[2] = 0x00`) belongs
  to a *separate* interface/table (the outgoing LoginInterface) than the one dumped here,
  given Mercury's per-direction interface convention — not directly cross-checked this
  pass.

## UNKNOWN

- The correct 4-byte reply ID value the client expects — this is the concrete, precisely
  scoped next blocker.
- Where/how the client assigns and stores the reply ID for its own outgoing LogOnParams
  request (candidates not yet checked: the 2-byte "counter" field at request bytes `[5:7]`,
  zero-extended; a value generated inside the `0x937128`/`0x937d2c` pending-request-tracker
  cluster identified in earlier sessions; a value embedded in the RSA-encrypted portion,
  which would make it unrecoverable without decryption).
- Whether the length-prefix value (`4`, our own choice) and the footer content (`0x0000`,
  our own choice) are actually required to be specific values, or whether any value that
  doesn't trigger a length-accounting mismatch is accepted — not distinguished, since no
  test varied them independently.
- The full LoginReply-specific payload shape (BaseApp address, session key, etc.) — not
  reached yet.
- `LoginHandler::onLoginReply`'s own registered message ID and its exact static
  registration site — not located this pass (Phase 4).
- Whether `LoginHandler::onLoginReply` executes at any point — **still not observed, still
  not claimed.**

## Next Blocker

Find the value (or the mechanism that computes it) for the 4-byte reply ID the client
expects echoed back in a msgID=255 "Reply" packet, correlating with its own outgoing
LogOnParams request. The most promising untried lead, consistent with not guessing: locate
where the client's own pending-request tracker (the `0x937128`/`0x937d2c` cluster
identified in `06_trace/MERCURY_LOGINREPLY_VALIDATION_TRACE.md`) generates or stores this
ID, ideally by reading it live from memory the same way this pass located the message
dispatch table — via a live `/proc/<pid>/mem` read of the relevant tracker object, rather
than a static guess.
