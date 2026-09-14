# ROS v1117219 — `baseAppLogin` Mercury Message: Binary Analysis

This replaces the "Not Completed" placeholder version of this document. Method is identical
to `LOGONPARAMS_SERIALIZATION.md`: ADRP/ADD string cross-referencing, direct `BL` call-graph
tracing, and function prologue/epilogue boundary identification in
`03_lib/libclient_arm64.so` (file offset == vaddr in this build for `.text`/`.rodata`).

## 1. Function Boundaries Located

| Function (inferred role) | Address range | How found | Confidence |
|---|---|---|---|
| `BaseAppExtInterface` method-table registration (static init) | `0x80c600`–`0x80cb00`+ | direct disassembly of the code block containing the `baseAppLogin` string xref | CONFIRMED |
| `ServerConnection`-level login-request orchestrator (retry gate + allocates request object) | `0x93a404`–`0x93a494` | `BL` callers of the next function down | CONFIRMED location; role INFERRED from field usage (`+0x80` retry counter, `+0x64`/`+0x65` state bytes matching `LoginHandler`'s own offsets) |
| `BaseAppLoginRequest`-build-and-send function (registers reply/timeout handler, calls `initNetwork`) | `0x9387cc`–`0x938940` | `BL` caller of `initNetwork`; single direct caller found | CONFIRMED |
| `BaseAppLoginRequest::initNetwork(Mercury::Nub*, bool)` | `0x9389dc`–`0x938c30` | xref of string `"BaseAppLoginRequest::initNetwork recreateListeningSocket for %d failed"` (`0x2a48fdd`) | CONFIRMED |
| Reply-handler / pending-request tracker constructor (`Mercury::ReplyMessageHandler`-style wrapper, not the wire payload) | `0x937128`–`0x9372dc` | direct callee of the build-and-send function above | CONFIRMED location; STRONG EVIDENCE for role (registers into a linked list keyed by timeout, matches BigWorld's request-timeout bookkeeping pattern) |
| A 24-byte context-block initializer, embedded inside a separately-allocated 184-byte (`0xb8`) polymorphic object | `~0x93bedc`–`0x93bf64` | traced backward from the 24-byte read at `0x937188`–`0x937194` (`x2 = arg+0x24`) to its write site | CONFIRMED write site exists; UNKNOWN what this 184-byte object actually is (candidate: a `Mercury::Bundle`/`Channel` wrapper, or the `BaseAppLoginRequest` object itself under a different allocation path than the `0x78`-byte one seen at the orchestrator level — **two different allocation sizes were found in two different code paths, not reconciled in this pass**) |

ARMv7 cross-check: **not performed** in this pass either — flagged as a repeat follow-up.

## 2. CONFIRMED: Message Framing (from the interface registration table)

The `BaseAppExtInterface` method table is built by a uniform call
`bl 0x98b30c(interfaceObj, nameString, lengthStyle, lengthParam, extraDataPtr)`, repeated
once per method, in the exact string order documented in `MERCURY_PACKET_MAP.md`. Reading
`lengthStyle` (`w2`) and `lengthParam` (`w3`) directly from each call site gives a
**complete, confirmed length-encoding table** for the whole interface (see
`MERCURY_PACKET_MAP.md` §2 for the full table). For `baseAppLogin` specifically:

```
w2 (lengthStyle) = 1   → VARIABLE_LENGTH_MESSAGE
w3 (lengthParam) = 2   → the message body is prefixed by a 2-byte (uint16) length field
```

This is a **materially different framing** from `authenticate` (fixed, 4 bytes) or
`avatarUpdateImplicit`/`avatarUpdateExplicit` (fixed, 24/32 bytes) registered immediately
next to it in the same table — i.e. this is not a guess or a default, it is a deliberate,
distinct choice for this one message, consistent with `baseAppLogin` needing to carry
variable-length credential data (as `LogOnParams` did for the LoginApp leg).

**CONFIRMED BY BINARY**: `baseAppLogin` = `[u16 bodyLength][bodyLength bytes of payload]`
inside the Mercury message header. The internal structure of those `bodyLength` bytes was
**not** recovered in this pass (see §4).

## 3. CONFIRMED: Send Orchestration & Retry Behavior

Traced the full call chain from the `ServerConnection`-level orchestrator down to socket
setup:

```
0x93a404  orchestrator(this=ServerConnection*)
    reads  this+0x80          -- retry/attempt counter
    IF this+0x80 > 0:
        writes this+0x65 = 2               -- error/state byte
        appends a fixed ~0x46-byte (70) error string into a buffer at this+0x68
        (uses the exact string-copy pattern confirmed in LOGONPARAMS_SERIALIZATION.md)
        writes this+0x64 = 1                -- "failed" state flag
        RETURN (no send attempted)
    ELSE (first attempt):
        newObj = operator_new(0x78)          -- 120-byte object
        bl 0x9387cc(newObj, this)
        this->[0x80] += 1                    -- increment retry counter
```

**CONFIRMED**: the client only attempts to send `baseAppLogin` **once** per
`ServerConnection` lifetime under normal flow — a second call to this orchestrator (e.g. on
a stall/retry from a higher layer) immediately fails locally with a state byte set to `1`
and logs an error, **without re-sending**. This means a local BaseApp prototype gets exactly
one shot at replying before the client gives up and reports failure — there is no
client-driven retransmission of `baseAppLogin` to lean on.

Inside `0x9387cc`:

```
0x9387cc  buildAndSend(newObj, sc=ServerConnection*)
    x3 = <baseAppLogin InterfaceElement handle>     -- global @ 0x457a210, set up by the
                                                        registration code in §2
    x2 = sc + 0x24                                   -- 24-byte context block (see §5)
    s1 = 5.0f                                        -- CONFIRMED float literal: request timeout
    w4 = <global int>                                -- purpose not traced (candidate: retry
                                                        count limit or priority)
    bl 0x937128(newObj, sc, x2, x3, s0, s1, w4, w5=0)  -- registers reply/timeout handler
    IF w5 & 1: <debug log call>                        -- not taken on the observed path (w5=0)
    bl 0x9389dc(newObj, sc, ...)                       -- BaseAppLoginRequest::initNetwork:
                                                          opens a UDP socket in port range
                                                          0x861-0xe321 (2145-58145), CONFIRMS
                                                          the port-scan range already
                                                          documented in MERCURY_LOGIN_FLOW.md
    <timing/debug log calls>
    return
```

**CONFIRMED**: a 5.0-second timeout is registered for the `baseAppLogin` reply
(`fmov s1, #5.0` at `0x93880c`), tracked via a linked-list "pending request" structure
(`0x937128`). This is infrastructure for detecting a non-responding BaseApp, not part of the
wire payload.

## 4. UNKNOWN: The Actual `baseAppLogin` Body Fields

Despite locating the entire send-orchestration chain above, **the specific code that calls
a `BinaryOStream`-style vtable writer (the `ldr x8,[xN]; ldr x8,[x8,#offset]; blr x8` pattern
used throughout `LogOnParams::addToStream`) to populate the `baseAppLogin` message body was
not located in this pass.** Every function traced in §1 either (a) sets up bookkeeping
objects (reply handler, retry counter, socket), or (b) performs debug/telemetry logging —
none of them write field data into a Mercury bundle.

**Explicit, honest status**: no field-level table can be produced for `baseAppLogin`'s body
in this pass, beyond the framing confirmed in §2. Two credible explanations, neither
confirmed:

1. The actual field-writing call is a **`blr` through a function pointer** resolved at
   runtime from the 184-byte object found in §1's last row (`0x93bedc` allocation) — its
   vtable slot layout was not decoded, and vtable-dispatched writes are, by construction,
   invisible to a `bl`-target scan.
2. The body may be **very small or even empty** — if the Mercury `Channel` established
   after the LoginApp exchange already carries session-level authentication (e.g. the
   channel itself uses symmetric encryption keyed by material from the `LoginReplyRecord`,
   see §5), `baseAppLogin`'s explicit payload could legitimately just be a session
   confirmation/nonce rather than a full credential re-submission. This is INFERRED, not
   confirmed either way.

## 5. Cross-Check: `LoginReplyRecord` Fields → `baseAppLogin` Consumption

Traced whether the `Mercury::Address`-sized record `LoginHandler::onLoginReply` writes to
`ServerConnection+0x50`/`+0x60` (see `LOGIN_REPLY_RECORD.md`) flows into the `baseAppLogin`
send path via the 24-byte context block at `+0x24`:

- **Result: they do NOT overlap.** The 24-byte block read at `0x937188`–`0x937194`
  (`ServerConnection+0x24` through `+0x3B`) is a **completely different offset range** from
  the Address record at `+0x50`/`+0x60`.
- What actually happens at `+0x24`/`+0x34` (CONFIRMED, traced directly): inside
  `onLoginReply`, at `0x93838c`, the code writes a literal `1` into `ServerConnection+0x24`,
  and at `0x938398` it copies the **first 4 bytes of the just-read Address**
  (`ldr w8,[x19,#0x50]` → `str w8,[x19,#0x34]`) into `+0x34`. Given the surrounding log
  string is `"LoginHandler::onLoginReply: change baseAddr from %s to %s"`, this strongly
  suggests `+0x34` is a **backup of the previous/old BaseApp address**, kept only so the
  log line can print `"from %s to %s"` — **not a session key**, and not part of what gets
  sent to BaseApp. This resolves an open question from `LOGIN_REPLY_RECORD.md` v1 (the
  ambiguity around what `+0x60`/nearby fields hold).
- **No evidence was found in this pass that a distinct "SessionKey" field from
  `LoginReplyRecord` is threaded into `baseAppLogin`.** This does not prove no session key
  exists — it means the specific 24-byte block consumed by the login-request builder is
  provably NOT the same memory the Address reply populated. The session key, if one exists,
  must live elsewhere in `ServerConnection` (untraced) or inside the 184-byte object from
  §1/§4 (also untraced).

**Answer to the explicit "is SessionKey validation actually required" question**:
**UNKNOWN, leaning toward NOT PROVEN NECESSARY.** No code path was found in this pass that
reads a "session key"-labeled field out of the LoginApp reply and writes it into the
`baseAppLogin` body. This is not the same as proving no such requirement exists (BaseApp
could still validate the connecting UDP address/port against what LoginApp told it,
entirely out-of-band from the message body) — but nothing in the client binary's traced
paths shows the client re-transmitting a server-issued secret back to BaseApp for
verification.

## 5a. 2026-09-14 (third pass) — `BaseAppLoginRequest` Object Layout Recovered

Follow-up work fully decoded the constructor at `0x937128` field-by-field (register/data-flow
tracing of every `str`/`stur` into the newly-allocated object, `x20` inside that function).
This supersedes the vague "184-byte object, role unknown" note from the previous pass —
that 184-byte/`0xb8` object was investigated further and **ruled out**: tracing its
containing function backward (prologue at `0x93bcc8`) showed it takes two string-pointer
arguments copied into local `std::string` buffers before the 184-byte allocation, which is
the signature of a **formatted log-message constructor**, not `BaseAppLoginRequest`. That
object is **not relevant to `baseAppLogin`** and is corrected here rather than left as an
open lead.

The **actual** `BaseAppLoginRequest`/request object is the one allocated by the orchestrator
at `0x93a470` (`operator new(0x78)`, 120 bytes) and constructed by `0x937128`. Its layout,
CONFIRMED BY BINARY from the constructor body:

```
BaseAppLoginRequest (120 bytes, allocated at 0x93a470, constructed at 0x937128):
+0x00-0x0F  std::function<void()>-shaped pair (manager-fn ptr + invoke-fn ptr) — matches the
            mangled string "...BaseAppLoginRequest13setNubAndSendE...3$_4...allocator...Fvv..."
            found at rodata 0x2a4b757, i.e. a lambda-backed void() reply/completion callback
+0x10       u32, initialized to 0                              (state/refcount candidate)
+0x18       ptr, = the ServerConnection* passed as arg1          (back-pointer, CONFIRMED)
+0x20       u64, initialized to 0
+0x28-0x37  16 bytes, VERBATIM COPY of ServerConnection+0x24..+0x33
+0x38-0x3F  8 bytes,  VERBATIM COPY of ServerConnection+0x34..+0x3B
+0x40       ptr, = baseAppLogin InterfaceElement handle (loaded from global @ 0x457a210)
+0x48       u32, initialized to 0
+0x4c       u8,  initialized to 0
+0x50       f32, = a global float constant (purpose not traced)
+0x54       f32, = 5.0 (the reply timeout, CONFIRMED literal)
+0x58       u64, initialized to 0
+0x60       u32, = a global int constant (purpose not traced)
```

**Epistemically important caveat**: this object's shape (leading callback pair, back-pointer,
InterfaceElement handle, timeout floats, and it being registered into a linked list keyed by
timeout — see original `0x937128` disassembly) matches a **Mercury pending-request /
reply-timeout tracker**, i.e. bookkeeping for "what to do when BaseApp replies or 5s
elapses" — **not** necessarily a staging buffer for the wire payload. The 24-byte block
copied from `ServerConnection+0x24..+0x3B` into `+0x28..+0x3F` could be:
(a) opaque context data returned to the reply callback (never sent over the wire), or
(b) the actual pre-serialized login payload later copied into the Mercury bundle by code not
yet located.
**Both remain possible; neither is confirmed.** Do not read this layout as proof that these
24 bytes are transmitted to BaseApp.

## 5b. What The 24-Byte Source Region Contains (partial)

Of `ServerConnection+0x24` through `+0x3B` (6 × 4-byte words), only 2 of 6 were
characterized in prior/this work, both from `LoginHandler::onLoginReply`:

| Offset | Content | Confidence |
|---|---|---|
| `+0x24` | `u32`, written `= 1` immediately after the Address is parsed | CONFIRMED BY BINARY (write site); INFERRED meaning (state/flag) |
| `+0x28` | UNKNOWN | UNKNOWN |
| `+0x2c` | UNKNOWN | UNKNOWN |
| `+0x30` | UNKNOWN | UNKNOWN |
| `+0x34` | `u32`, copy of the first 4 bytes of the new BaseApp Address (`[this+0x50]`) | CONFIRMED BY BINARY (write site); STRONG EVIDENCE it exists only for the "change baseAddr from %s to %s" log line, not for transmission |
| `+0x38` | UNKNOWN | UNKNOWN |

A broad, unscoped search for writes to these offsets across all of `.text` was attempted and
**abandoned as unproductive**: this offset range (0x24–0x3c relative to any base register)
is an extremely common compiler-generated pattern (object zero-initialization,
exception-handling scaffolding) that recurs thousands of times across unrelated classes in
this 22MB `.text` section, making a blind scan unable to isolate the correct writes without
first knowing the exact `ServerConnection`/`LoginHandler` constructor address. An attempt to
locate that constructor via RTTI typeinfo reconstruction (searching for pointers to the
`N4neox8bwclient12LoginHandlerE` mangled-name string at rodata `0x2a4b2f0`, then following
the Itanium typeinfo→vtable chain) did not converge to a verifiable class vtable in the time
available — the candidate location found had a zero-filled predecessor field, inconsistent
with a real `__class_type_info` vtable slot, and was discarded rather than reported as fact.

**Honest conclusion**: 4 of the 6 words in this block remain UNKNOWN. This is a genuine
limit of static-only, symbol-free analysis reached in this pass, not an oversight — the next
section names the concrete next step.

## 6. Summary Table

| Item | Confidence |
|---|---|
| `baseAppLogin` message ID exists, registered as method #0 (first) in `BaseAppExtInterface` | CONFIRMED BY BINARY |
| Framing: VARIABLE_LENGTH_MESSAGE with 2-byte length prefix | CONFIRMED BY BINARY |
| Send happens at most once per `ServerConnection` (no client-side retry) | CONFIRMED BY BINARY |
| 5.0-second reply timeout registered around the send | CONFIRMED BY BINARY |
| Port-range 0x861–0xe321 socket bind on the client side for this connection | CONFIRMED BY BINARY (matches prior report) |
| `BaseAppLoginRequest` object full layout (120 bytes, §5a) | CONFIRMED BY BINARY |
| Whether the 24-byte `ServerConnection+0x24..0x3B` block is the wire payload or just callback context | UNKNOWN — both remain plausible |
| Exact field layout of the message body | UNKNOWN |
| Whether a LoginApp session key is re-sent inside the body | UNKNOWN (no evidence found either way; the two characterized sub-fields of the 24-byte block — a state flag and an address-backup-for-logging — are provably unrelated to a session key; the other 4 of 6 sub-fields are UNKNOWN) |
| The earlier "184-byte object" lead from the previous pass | RULED OUT — identified as an unrelated log-message constructor, not part of the `baseAppLogin` path |
