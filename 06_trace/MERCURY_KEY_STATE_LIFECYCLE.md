# ROS v1117219 — Complete Blowfish Key-State Lifecycle for the LoginApp Channel

## Executive Result

**The complete crypto-state lifecycle is now traced end-to-end via static analysis alone,
with no ambiguity requiring new live instrumentation.** The client's `EncryptionFilter`
starts every connection with a locally-generated, throwaway 32-bit random key (confirmed
in the prior pass). This pass fully reverses the `0x32ef9816` mechanism and proves it is a
**genuine, functioning key-replacement channel embedded inside the LoginReply message
itself**: a plain 4-byte magic-number check, followed (on match) by a length-prefixed
string read **directly from the wire, byte-for-byte, with no transformation**, which is
then handed to the **exact same constructor** that builds the random-key filter — meaning
a real server *can* legitimately install its own chosen key, **within the very same
LoginReply message** that carries the (BaseApp-address) data the key would protect,
**provided that data comes after the key-update block in wire order.** This corrects an
earlier, much older session's document (`LOGIN_REPLY_RECORD.md`/`MERCURY_PACKET_MAP.md`),
which had inferred `0x32ef9816` was merely an "interface/entity-defs fingerprint" unrelated
to any key — that inference is now shown to be incomplete: the bytes gated by that
constant are **provably, mechanically** consumed as Blowfish key material, not diagnostic
text. For our own test traffic specifically, static proof (not runtime observation) shows
decryption **always** uses the original random default key, because our packets are
exactly one byte too short to structurally reach the key-update block at all.

## Diagram

```text
ServerConnection
    |
    v
EncryptionFilter construction (0x917070 -> 0x93a620 -> 0x988cf8)
    |
    +--> RAND_bytes(buf = this+0x11 [inline SSO storage], len = 4)
    |       |                (return value DISCARDED, never checked)
    |       v
    |   BF_set_key(BF_KEY* = this+0x30, len=4, data=this+0x11)
    |       |
    |       v
    |   default key (installed unconditionally, before any network content)
    |
    v
LoginApp communication (our 273-byte LogOnParams request)
    |
    v
LoginReply  (msgID=0xFF, replyID, status=1, 20-byte body, [optional trailing block])
    |
    v
onLoginReply
    |
    +--> read 4 bytes; compare to 0x32ef9816  (only if >=5 bytes remain after the body)
    |       |
    |       +-- NO MATCH  -> key-update skipped entirely (OUR test traffic: always this path)
    |       |
    |       +-- MATCH     -> read 1(+3) length-prefixed bytes -> read N key bytes verbatim
    |                          |
    |                          v
    |                        0x939f94 (get-or-replace cached filter)
    |                          |
    |                          v
    |                        0x9889e8 (EncryptionFilter ctor, STRING overload)
    |                          |
    |                          v
    |                        BF_set_key(BF_KEY*, len=N, data=wire bytes, UNTRANSFORMED)
    |                          |
    |                          v
    |                        cached at resource_object+0x148 (REPLACES the random default,
    |                          for all messages AFTER this one)
    |
    v
0x989600 (decrypt for the 20-byte body -- ALWAYS runs BEFORE the 0x32ef9816 check,
          per wire order -- see "1. DEFAULT KEY GENERATION" / "9." below)
    |
    v
active Blowfish decrypt (uses whatever key was cached BEFORE this message arrived --
                          for a first-ever LoginReply, this is the random default,
                          UNLESS a prior message already installed a real one)
    |
    v
BaseApp address (garbled, for our tests, since no key-update has ever preceded them)
```

## 1. Default Key Generation

Re-confirmed from the prior pass, with two additional details this pass verified:

- **Destination buffer**: `this+0x11` — the object's *own inline SSO string storage*
  (`this+0x10` is the SSO control/length byte; `+0x11` is the first data byte),
  **not** a separate temporary buffer. `RAND_bytes` writes its output directly into the
  filter object's permanent key-string field.
- **Requested length**: `4`, a hardcoded literal traced register-by-register from the
  connection-setup call site (`0x917068: mov w2, #4`) through `0x93a620` and `0x988cf8`.
- **Return-value handling**: **CONFIRMED discarded, unchecked.** The instruction
  immediately following the `RAND_bytes` call (`0x988db0: mov w0, #0x1048`) overwrites
  `w0` (RAND_bytes's own return register) before it could ever be tested — there is no
  `cmp`/`cbz` on RAND_bytes's result anywhere in this function. A `RAND_bytes` failure
  (extremely rare, but part of its real contract) would go completely unnoticed.
- **Instruction-by-instruction confirmation that the SAME 4 bytes reach `BF_set_key`**:
  `0x988dd8: add x2, x20, #1` recomputes the identical address (`this+0x11`) as the key
  pointer for `BF_set_key`, one word later. No copy, no XOR, no re-derivation — the bytes
  `RAND_bytes` wrote are read back verbatim.
- **BF_KEY storage**: `this+0x30`, pointer to a freshly `operator new(0x1048)`-allocated
  buffer (4168 bytes, exact `sizeof(BF_KEY)` match, re-confirmed).
- **Do the raw 4 key bytes remain in the object after `BF_set_key`?** **CONFIRMED YES** —
  nothing in this constructor (or the sibling constructor `0x9889e8`) zeroes, clears, or
  overwrites the object's own `this+0x10..+0x14` SSO string storage after `BF_set_key`
  consumes it. The plaintext key remains resident in the object's memory for the object's
  entire lifetime, alongside the expanded `BF_KEY` schedule.

## 2. Key Storage / Writes — Complete Table

Searched all `str x?, [x?, #0x30]` encodings restricted to the confirmed filter-class
code cluster (`0x988000`–`0x99a000`, 36 raw hits; unrestricted whole-binary search found
301, dominated by unrelated classes coincidentally using the same offset and was not
pursued further, per this task's "do not repeat unfocused scanning" guidance).

| Write Site | Enclosing Function | Trigger | Source of Key | Key Length | Before/After LoginReply |
|---|---|---|---|---|---|
| `0x988ad4` | `0x9889e8` (ctor, string overload) | Called via `0x939f94`, itself called from onLoginReply's `0x32ef9816` block (`0x938324`) OR (per `encfilter_ctor_callers.txt`) any other future caller of `0x939f94` not found in this binary | Caller-supplied `std::string&` — for our traced path, read verbatim from the wire | Variable (4–56 bytes, validated) | **AFTER** — only reachable once a LoginReply's key-update block has been parsed |
| `0x988dbc` | `0x988cf8` (ctor, length overload) | Called via `0x93a620`, itself called from `0x917070` — **automatic `ServerConnection` setup**, confirmed unconditional | `RAND_bytes(4)` — locally generated | Fixed at 4 (hardcoded literal in the caller) | **BEFORE** — installed before any network content is ever processed |
| `0x988c00` | `0x988be8` ("re-key from existing string" method — this pass's new finding) | **No static or virtual caller found anywhere in the binary** | The object's *own, already-stored* key string (`this+0x10/+0x18`) — re-derives `BF_KEY` without taking a new string argument | Whatever length is already stored | **UNKNOWN** — not reached by any path this project has traced; may be dead code, reached via a vtable slot not yet mapped, or used by a different (BaseApp/CellApp) subsystem entirely |
| `0x990d14`, `0x98ba58`/`0x98ba80`/`0x98ba90`/`0x98baa0`/`0x98baac`, `0x98db94`, `0x98e678`, `0x98eb48`, `0x98ef68`, `0x99xxxx` cluster (23 more sites) | not individually resolved | not investigated | not investigated | not investigated | **UNKNOWN** — flagged, not chased further; these fall in the same broad code region but were not confirmed to belong to the `EncryptionFilter` class specifically, and pursuing all 23 was judged out of proportion to this task's actual question (which is answered by the two confirmed rows above) |

**`0x988be8` is a genuinely new, second setter this pass identified** (not found in the
prior two passes) — a method that takes only `this` and re-runs key expansion from
whatever string is *already* in the object. Since it has zero discoverable callers, it is
reported as present-but-unreached, not asserted to be part of the live LoginReply flow.

## 3. Full Reversal of the `0x32ef9816` Mechanism

### The gating condition (before the magic-constant check is even attempted)

```
0x938264: ldr w8, [sp, #0x50]     ; stream position after the 20-byte body read
0x938268: ldr w9, [sp, #0x60]     ; total message length
0x93826c: sub w8, w8, w9
0x938270: cmp w8, #5
0x938274: b.lt #0x938338          ; if FEWER than 5 bytes remain after the body, skip
                                    ; the ENTIRE key-update block unconditionally
```

**CONFIRMED**: our own test replies (`length=25` exactly = 4-byte replyID + 1-byte status
+ 20-byte body, with **zero** bytes left over) fail this precondition **by construction**
— not by chance, not dependent on packet content, purely by declared length. **This is a
mathematically certain, static proof that our own test traffic can never reach the
key-update path**, making Phase 5/6's live-capture hypothesis test unnecessary: there is
no ambiguity to resolve empirically.

### The magic-constant comparison (Phase 3, steps 1–2)

```
0x938278: ldr x8, [sp, #0x38]      ; x8 = the Bundle-iterator object still reading this message
0x938284: ldr x8, [x8, #0x10]       ; vtable[0x10] = the same read(N) method used for every
0x938288: mov w1, #4                 ;   other field in this message (status byte, 20-byte body)
0x93828c: mov x0, x21
0x938290: blr x8                     ; x0 = pointer to 4 freshly-read wire bytes
0x938294: ldr w8, [x0]               ; w8 = those 4 bytes, interpreted as one 32-bit word
0x938298: mov w9, #0x9816
0x93829c: movk w9, #0x32ef, lsl #16  ; w9 = the literal constant 0x32ef9816
0x9382a0: cmp w8, w9
0x9382a4: b.ne #0x938328             ; mismatch -> skip to cleanup, no key update
```

**Field/offset being compared**: the **next 4 bytes of the message**, immediately
following the 20-byte address body — i.e., wire offset `4(replyID)+1(status)+20(body) =
25` relative to the start of the msgID=255 payload. **Not** a field at a fixed object
offset, and **not** derived from anything already parsed — it is read fresh from the wire
each time, exactly like every other field in this message.

### On match: the exact bytes consumed, their lengths, and boundaries (Phase 3, steps 3–5)

```
0x9382a8-0x9382b8: read(1) -> w22 = one length byte
0x9382c0: cmp w22, #0xff
0x9382c4: b.ne #0x9382f0             ; if w22 != 0xFF, w22 IS the final length (0-254)
0x9382c8-0x9382ec: [w22==0xFF only] read(3) more bytes, compose a 24-bit little-endian
                    extended length into w22 via two `bfi` (bit-field-insert) instructions
                    -- IDENTICAL encoding to the "write_bw_string" length-prefix scheme
                    this project already confirmed for LogOnParams's own string fields
                    (LOGONPARAMS_SERIALIZATION.md §4) -- CONFIRMED reused here verbatim.
0x9382f0-0x938300: read(w22) -> x0 = pointer to exactly w22 bytes -- THE KEY MATERIAL,
                    read directly from the wire in one call, no intermediate buffering.
```

**Every transformation checked and found ABSENT**: no endian conversion (the bytes are
used as-is; the *length prefix* uses the project's standard little-endian bitfield
composition, but the *key bytes themselves* are untouched), no XOR, no arithmetic, no
hashing, no key derivation function of any kind. The only operation performed is a
**direct memory copy**:

```
0x938304: mov x8, x0
0x938308: cbz x8, #0x93831c          ; empty/null key data -> skip the copy, skip the update
0x93830c: sxtw x2, w22                ; length
0x938310: sub x0, x29, #0x70           ; destination = a local (stack) std::string object
0x938314: mov x1, x8                    ; source = the wire bytes just read
0x938318: bl #0x83f8a8                   ; string-assign: local_string.assign(wireBytes, length)
                                           ; -- the SAME string-construction helper this
                                           ;    project has already confirmed elsewhere
                                           ;    (e.g. Mercury::REASON_CORRUPTED_PACKET's
                                           ;    own string-building code)
```

### The setter that ultimately updates the filter (Phase 3, step 6)

```
0x93831c: ldr x0, [x19, #0x48]         ; x0 = *(LoginHandler_this+0x48) -- the SAME
                                          ;   per-connection resource object whose +0x148
                                          ;   field holds the cached filter (Phase 3 of the
                                          ;   prior pass, MERCURY_ACTIVE_DECRYPT_TRACE.md)
0x938320: sub x1, x29, #0x70              ; x1 = &(local_string) -- the new key, wire-sourced
0x938324: bl #0x939f94                     ; get-or-replace the connection's cached filter,
                                              ;   using this NEW key string -- this is THE
                                              ;   EXACT SAME function this project already
                                              ;   confirmed constructs EncryptionFilter
                                              ;   instances via 0x9889e8 (the string-taking
                                              ;   constructor overload)
```

**CONFIRMED**: `0x939f94`/`0x9889e8` is genuinely, mechanically the same key-installation
machinery for both the wire-sourced key-update path and (in the prior pass's earlier,
now-superseded understanding) any other explicit-string caller. There is no separate,
special "apply key update" function distinct from the ordinary filter constructor.

### Resulting key length (Phase 3, step 7)

**CONFIRMED VARIABLE, not fixed at 4 bytes.** The length comes directly from the
wire-supplied length prefix (1 byte, 0–254, or a 24-bit extended form via the `0xFF`
escape), then validated by the **same** range check found in both constructors
(`(length - 4) > 0x34` → reject, i.e. valid range is exactly **4 to 56 bytes**, matching
real Blowfish's documented 32–448-bit key range exactly). A server-supplied key can
therefore be any length in that range — it is not constrained to match the 4-byte
default.

## 4. The Trigger: Answered Definitively — (A) Part of LoginReply

Mapping the full message:

```
Mercury packet
  -> flags (0x0001), msgID (0xFF, "Reply")
  -> reply header: 4-byte length prefix, 4-byte replyID
  -> 1-byte status (must be 1 for the "normal" path this project has already validated)
  -> 20-byte body (BaseApp address record)
  -> [ONLY IF >=5 bytes remain]:
       -> 4-byte magic constant (0x32ef9816)
       -> length-prefixed key string
  -> 0x32ef9816 condition: gates the key string parse, nothing else
  -> key update: calls 0x939f94/0x9889e8 with the wire-sourced key
```

**CONFIRMED: (A) — the key-update block is part of the SAME LoginReply message**, appended
after the mandatory reply-header/status/body fields, gated purely by whether the overall
declared message length leaves room for it. **(B) another Mercury message, (C) a separate
packet, (D) generated locally, and (F) another ServerConnection path are all explicitly
ruled out** by this direct trace — there is no code path reading this key material from
anywhere other than the current message's own iterator. **(E) obtained from LoginApp
before LoginReply** is also ruled out for *this specific* key-update mechanism (it is read
live, in-message), though it does not preclude some entirely separate, earlier handshake
step this project has not looked for (see Unknowns).

## 5. Runtime Correlation — Not Performed, By Deliberate, Justified Choice

Per this task's own instruction ("use runtime instrumentation only where static analysis
cannot prove the flow"): every question Phase 5 asks for is **already answered with
certainty by the static trace above**, specifically:

- The `remaining >= 5` check (§3) is a **pure length comparison with no data dependency**
  — given our reply's exact, self-chosen byte count (25), the outcome is provable by
  arithmetic alone, not by observation.
- `0x989600` (decrypt) is called **before** the `0x32ef9816` check is ever reached in
  `onLoginReply`'s own instruction sequence (`0x938234` precedes `0x938278`+) — meaning
  even *if* our reply carried a key-update block, decrypting the 20-byte body would
  **still** use whatever key was cached *before* this message arrived, never the
  in-message update. This is a **wire-order fact**, not something that needs a live
  process to confirm.

Running a live capture would only reconfirm these already-certain facts at the cost of
repeating this project's prior heap-scanning difficulties (documented in
`MERCURY_LOGIN_REPLY_KEY_TRACE.md`) for no new information. This is reported as a
deliberate scoping decision, consistent with the task's own stated priority ("the
priority is NOT make it work... the priority is trace the crypto-state lifecycle").

## 6. Hypothesis Test (Phase 6) — Answered By Construction, Not Observation

**Does LoginReply decrypt use the original random key, or has the key already been
replaced before decrypt?**

**PROVEN: the original random key is used, for every test this project has ever sent**,
by two independent, compounding certainties:

1. Our replies never satisfy the `remaining >= 5` precondition (§3), so the key-update
   parse code is structurally unreachable — no key-update ever happens as a result of
   anything we've sent.
2. Even in a hypothetical message that *did* include a key-update block, `onLoginReply`'s
   own instruction order calls decrypt (`0x938234`) **before** reaching the key-update
   check (`0x938278`+) — so a same-message key update could never retroactively affect
   that same message's own body decryption regardless.

No live capture of `decrypt_this`/`decrypt_this->vtable`/`decrypt_this+0x30` was performed,
because the answer does not depend on any runtime value — it follows from the client's
own fixed instruction ordering, which is not something that varies between runs.

## 7. Server-Side Correspondence

Searched this repository's own MITM/proxy server code (`mitm/local_baseapp_capture.py`)
and prior trace documents for any existing server-side Blowfish/key-update
implementation. **None exists** — this project's local test LoginApp responder sends a
plain, unencrypted 20-byte body and has never implemented the `0x32ef9816` mechanism.

**A genuine discrepancy with an earlier session's document was found and is corrected
here, not silently overwritten**: `06_trace/LOGIN_REPLY_RECORD.md` (line 39) and
`06_trace/MERCURY_PACKET_MAP.md` (lines 157–160) both state, from a much earlier pass
(before this project's `EncryptionFilter`/Blowfish investigation began), that
`0x32ef9816` is **"INFERRED... an interface/entity-defs fingerprint hash... do NOT treat
0x32ef9816 as a session key or account ID"**, and characterize the length-prefixed strings
read afterward as **likely diagnostic/error text**, explicitly flagged UNKNOWN at the
time. **This pass's full instruction-level trace shows that inference was incomplete**:
the bytes gated by `0x32ef9816` are not logged, not discarded, and not used for any
fingerprint comparison — they are read into a `std::string`, handed directly to the exact
same constructor (`0x939f94`/`0x9889e8`) already proven (independently, via the
`RAND_bytes`/`BF_set_key` chain) to build `Blowfish` `EncryptionFilter` objects, and that
constructor's own key-length validation logic runs on them. **This is not consistent with
"diagnostic text"** — it is a real, mechanically-verified key-material field. The older
documents' uncertainty is resolved, not contradicted in spirit (they correctly flagged it
as unresolved rather than asserting a false certainty) — this document supersedes their
specific "not a session key" claim with direct evidence.

**No server key was invented, guessed, or brute-forced.** No production authentication,
anti-cheat, or DRM mechanism was targeted or bypassed. All analysis in this pass was
static disassembly of the client binary already present in this repository, plus review
of this project's own local test server code — no new device interaction, network
traffic, or live process was used this pass.

## 8. What Is Proven

- The default key's full lifecycle: `RAND_bytes(4)` → `BF_set_key` → resident in
  `this+0x30`/`this+0x10`, installed unconditionally during `ServerConnection` setup,
  before any network content.
- The `0x32ef9816` mechanism is a real, functioning in-band key-replacement channel:
  magic constant → length-prefixed key (4–56 bytes, Blowfish's real valid range) → direct,
  untransformed wire-to-string copy → the same constructor used for the default key.
  This is a genuine correction of an earlier session's incomplete "fingerprint hash"
  characterization.
- The key-update block, when present, is part of the **same** LoginReply message as the
  20-byte body, appended after it, gated by a pure length precondition.
- For every test this project has sent, decryption of the 20-byte body **provably** uses
  the original, locally-generated random default key — both because our packets are too
  short to trigger a key update, and because `onLoginReply`'s own code decrypts the body
  *before* it would ever check for a key update in the same message.
- A second, previously-unknown key-refresh method (`0x988be8`) exists in the same class,
  taking no new key argument (re-derives `BF_KEY` from the object's own current string) —
  present in the binary but with no discoverable caller.

## 9. What Is Still Unknown

- Whether a genuine production server's LoginReply is actually structured as
  `[status][20-byte body][key-update block]` (key update *after* the data it can't yet
  protect) — this project's own client-side evidence proves this ordering exists in the
  parser, but not what a *real* server does with it, or whether the 20-byte body is ever
  meaningfully protected by Blowfish in practice for this specific message.
- Whether `0x988be8` (the no-argument re-key method) is ever actually invoked by any
  code path, and if so, by what triggers it.
- The purpose and callers of the 23 additional `+0x30` write sites in the broader
  `0x988000`–`0x99a000` cluster not individually investigated this pass.
- Whether any earlier handshake step (before LoginReply) also carries key material via a
  different mechanism — not searched for this pass, since the question this task posed
  was fully answered without needing to look further.

## 10. Next Blocker

There is no blocker for *this task's* stated goal (establishing the crypto-state
lifecycle) — it is fully established. The blocker that remains, carried over unchanged
from the prior pass and *not* newly created by this one, is: **whether it is even
meaningful to try to make the client decode a correct BaseApp address at all**, given that
doing so for the *very first* LoginReply a connection ever receives would require
already knowing a random key that only exists in that specific client process's memory —
this pass's finding that the key-update mechanism only takes effect for *subsequent*
messages does not change that fact for a single-message exchange. Any further attempt to
"make it work" would require either brute-forcing a 32-bit keyspace or fabricating an
assumption about production server behavior neither of which this project's rules permit.

## FINAL REPORT

```text
ACTIVE KEY AT DECRYPT: The original, locally-generated random default key -- PROVEN by
  construction for every test this project has sent (packets too short to trigger a
  key update, and decrypt runs before the key-update check even in messages that could).
KEY ORIGIN: OpenSSL RAND_bytes(4), called unconditionally during ServerConnection setup,
  independent of any network content.
KEY LENGTH: Default = 4 bytes (32 bits), hardcoded. Server-installable range (via the
  0x32ef9816 mechanism) = 4 to 56 bytes, matching Blowfish's real valid key-length range.
KEY STORAGE: EncryptionFilter object, this+0x30 (BF_KEY*, 4168-byte OpenSSL struct) and
  this+0x10/+0x18 (the raw key bytes, retained as the object's own std::string,
  confirmed never cleared after BF_set_key).
KEY UPDATE FUNCTION: 0x939f94 (get-or-replace cached filter) -> 0x9889e8 (EncryptionFilter
  constructor, string-argument overload) -- the SAME constructor family as the default
  key, not a separate mechanism.
0x32EF9816 MEANING: A literal magic-number marker inside LoginReply gating an optional,
  in-band Blowfish-key-replacement block. Corrects an earlier session's characterization
  of this as a non-key "fingerprint hash" -- proven, via direct trace to BF_set_key, to
  be genuine key material.
KEY UPDATE TRIGGER: A 4-byte field read immediately after the 20-byte LoginReply body,
  compared for exact equality against 0x32ef9816; only reachable if the message's
  declared length leaves >=5 bytes after the body.
KEY UPDATE INPUT: A length-prefixed byte string (1-byte length, 0xFF-escaped to a 3-byte
  extended length -- identical encoding to LogOnParams's own string fields), read directly
  from the same message, immediately following the magic constant.
KEY UPDATE TRANSFORMATION: NONE -- a direct, byte-for-byte copy from the wire into a
  std::string, then into BF_set_key. No XOR, hashing, or derivation of any kind.
LOGINREPLY CRYPTO STATE: For a message carrying its own key-update block, the 20-byte
  body (read and decrypted earlier in wire order) is NEVER protected by that same
  block's key -- only messages arriving AFTER a key update benefit from it.
SERVER-SIDE CORRESPONDENCE: None implemented in this project's own local test server.
  An earlier session's documents mischaracterized 0x32ef9816 as unrelated to any key --
  corrected here with direct evidence, not silently overwritten.
PROOF LEVEL: Static disassembly, register-by-register and instruction-by-instruction,
  for every claim in this report. No live instrumentation was needed or performed this
  pass -- every question the task posed was answerable with certainty from the binary's
  own fixed code paths and this project's own chosen packet lengths.
CURRENT BLOCKER: Unchanged from the prior pass -- correctly encrypting a FIRST LoginReply
  for a connection is not achievable without either brute-forcing a 32-bit key (forbidden)
  or unverified assumptions about real server behavior (also avoided). This is now known
  to be a property of the protocol's own design (key updates only protect future
  messages), not a gap in this project's understanding.
NEXT EXPERIMENT: None recommended that would not require guessing or brute-forcing.
  If pursued further, the highest-value NEW static target (not attempted this pass) would
  be finding 0x988be8's caller(s), if any exist via a vtable slot not yet mapped.
COMMIT: (this pass's commit, see below)
```
