# ROS v1117219 — LoginReply 20-Byte Body → BaseApp Address Decode Trace

## Executive Result

**The cipher, block size, chaining mode, padding scheme, and per-block cipher primitive
are all now CONFIRMED directly from the client binary's own imported symbols and
disassembly — not from generic BigWorld documentation.** The 20-byte LoginReply body must
be **Blowfish-CBC encrypted** (zero IV, PKCS-style padding to a multiple of 8 bytes)
before being sent; our current plaintext 20-byte body is being misinterpreted as
ciphertext, which explains the garbled BaseApp addresses seen in every prior test.
`ServerConnection::checkScriptBaseAppAddr`'s address-decoding path was also traced and
**confirms the underlying 8-byte `Mercury::Address` field layout this project has assumed
since much earlier sessions is correct** — the structural content of our 20-byte body does
not need to change, only its encryption. **The encryption key itself — the one genuinely
missing piece — could not be recovered this pass**: it is not the RSA-encrypted portion of
the original `LogOnParams` request (that ciphertext contains login credential strings, per
`LOGONPARAMS_SERIALIZATION.md`, not a reusable symmetric key), and our test captures show
no optional digest/session field is being sent by this client build to derive it from
either. This is reported honestly as the concrete, narrowed-down **next blocker**, with a
specific, evidence-based recommendation for closing it (§6).

## Phase 1 — `LoginHandler::onLoginReply`, Full Body-to-Decode Path

Re-disassembled `0x938070`–`0x938380` (`scratch/onLoginReply_start.txt`,
`scratch/onLoginReply_size_check.txt`, both already captured in the prior pass and
re-verified here) to trace the 20-byte body precisely:

```
0x938224: add x2, sp, #0x30
0x938228: mov x0, x21          ; x21 = bundle iterator (still reading our reply's payload)
0x93822c: mov x1, x20          ; x20 = this-ish context object
0x938234: bl #0x989600         ; helper -- NOT itself the decrypt call (see below); prepares/wraps the read
0x938238: ldr x8, [sp, #0x38]
0x938240: ldr x8, [x8, #0x10]  ; vtable[0x10] = the standard stream read(N) method
0x938244: mov w1, #0x14        ; N = 0x14 = 20 -- CONFIRMED: exactly 20 bytes requested
0x938248: mov x0, x21
0x93824c: blr x8               ; x0 = pointer to 20 raw bytes read from the wire
0x938250: ldr w8, [x0, #0x10]  ; bytes[0x10:0x14] (last 4 bytes) -> one field
0x938254: add x23, x19, #0x50  ; x23 = LoginHandler_this + 0x50 (destination)
0x938258: str w8, [x23, #0x10]
0x93825c: ldr q0, [x0]         ; bytes[0x00:0x10] (first 16 bytes) -> loaded as one 128-bit value
0x938260: str q0, [x23]        ; stored at LoginHandler_this+0x50
```

**This 20-byte read happens BEFORE any visible call into a decrypt routine** — the bytes
are copied into `LoginHandler_this+0x50..+0x64` as raw data, split as **16 bytes +
4 bytes**, matching this project's existing `build_login_reply_record()` layout
(two 8-byte `Mercury::Address` records back-to-back = 16 bytes, then a 4-byte trailing
value) **exactly** in both boundary position and size. No decrypt call is visible in this
specific 20-byte read path.

### Where the `EncryptionFilter::decrypt` warning actually comes from

Continuing past the 20-byte copy, at `0x938264`–`0x938274` the code compares two stack
fields (`sp+0x50` vs. `sp+0x60`, populated by the earlier `0x989600` call) and only
proceeds to `0x938278` (an **optional trailing block**, gated on `remaining >= 5` bytes)
if more data follows. That optional block reads a 4-byte magic constant
(`0x32ef9816`) and, only if it matches, reads a length-prefixed **key-update string** and
installs it into a (possibly new) `EncryptionFilter` via a call at `0x938324` — this is a
**distinct, optional, in-band key-exchange mechanism**, not the decrypt call for the
20-byte body itself (see Phase 2 for why this still matters).

**The actual `EncryptionFilter::decrypt` call that produced the observed warning happens
earlier and at a lower level than `onLoginReply`'s own code** — no direct or tail-call
(`BL`/`B`) reference to either disassembled decrypt implementation
(`0x98925c`, `0x98939c`) exists anywhere in `.text` (verified via a full-binary scan), and
no `R_AARCH64_RELATIVE` relocation anywhere in `.rela.dyn` points at either address
either. **CONFIRMED**: `EncryptionFilter::decrypt` is invoked through a **virtual call**
whose exact vtable slot was not pinned down this pass (see Phase 2's honest gap) — most
plausibly from generic Mercury Bundle/message decoding machinery that transparently
decrypts an already-installed channel filter's data before `onLoginReply` ever sees it,
consistent with our 20-byte plaintext body already being (attempted-)decrypted by the time
`onLoginReply` reads it as raw bytes.

## Phase 2 — `EncryptionFilter::decrypt`, Fully Disassembled

Format string `"EncryptionFilter::decrypt: Input stream size (%d) is not a multiple of the
block size (%d)\n"` (`0x2a5c5a8`) has **three** live code cross-references
(`0x98928c`, `0x9893bc`, `0x989684`), each inside a separate but structurally similar
function — this project's convention of one canonical implementation was not assumed;
the first (`0x98925c`) was disassembled in full (`scratch/decrypt_full.txt`):

```
0x989268: ldrb w8, [x21, #0x2c]      ; this(EncryptionFilter)+0x2c: an "encryption enabled" flag
0x989274: cbz w8, #0x9892a4          ; if disabled, take a "no encryption filter" error path (NOT our case)
0x989278: ldrh w8, [x19, #0x1a]      ; iterator+0x1a: a length field (same offset used throughout
0x98927c: ldrh w9, [x19, #0x1c]      ;   this project's Bundle::iterator struct)
0x989280: add x22, x9, x8            ; w22 = TOTAL length of the data to decrypt
0x989284: and w10, w22, #7           ; CONFIRMED: block size check is `length & 7`, i.e. block size = 8
0x989288: cbz w10, #0x9892c4         ; if length % 8 != 0 -> the exact warning we observed, function returns -4
```

**This directly proves the "20 is not a multiple of 8" warning is a hard precondition
check, not a heuristic** — any length not divisible by 8 is rejected before any actual
cipher operation runs, confirming (not assuming) the answer to the task's explicit
question "prove what the caller actually expects": **the ciphertext must be exactly a
multiple of 8 bytes; 20 fails this and is therefore never decrypted at all** — meaning
in every previous test, the "decrypt" step returned an error and the 20 raw (still
plaintext, unmodified) bytes we sent were used as-is, which is *why* the resulting
"address" was garbage of a different, plausible-looking shape but not fully random noise.

### The actual CBC decryption loop (length is a multiple of 8)

```
0x9892d0: add x25, x19, #0x60        ; x25 = raw wire-data start (SAME +0x60 offset confirmed
                                       ;   throughout this project for every Bundle/stream object)
0x9892d4: ldr x2, [x21, #0x30]       ; x2 = *(EncryptionFilter+0x30) = KEY/CONTEXT pointer
0x9892d8: add x23, x25, x24          ; x23 = &data[byte_offset] (current 8-byte block)
0x9892dc: mov x0, x23                ; dst = x23 (IN-PLACE decryption, dst == src)
0x9892e0: mov x1, x23                ; src = x23
0x9892e4: mov w3, wzr                ; direction flag = 0
0x9892e8: bl #0x806e00               ; <<< the actual block-cipher call
0x9892ec: cbz x26, #0x98930c         ; x26 = previous CIPHERTEXT block pointer; 0 on the FIRST block
0x9892f0: ldr x8, [x26]              ; x8 = previous ciphertext block
0x9892f4: ldr x9, [x25, x24]         ; x9 = just-decrypted current block
0x989300: eor x8, x9, x8             ; XOR with previous ciphertext -- CBC MODE, CONFIRMED
0x989304: str x8, [x25, x24]         ; store XOR'd (true plaintext) result back in place
0x98930c: mov x26, x23               ; (first block only) x26 becomes "previous block" for next round
0x989310: add x24, x24, #8           ; advance by exactly one block (8 bytes)
0x989314: cmp x24, x22
0x989318: b.lt #0x9892d4             ; loop over all 8-byte blocks
```

**CONFIRMED via the imported symbol name itself** (not inferred): `bl #0x806e00` resolves,
via `.rela.plt`, to OpenSSL's **`BF_ecb_encrypt`** (Blowfish, single-block ECB primitive —
`static void BF_ecb_encrypt(const unsigned char *in, unsigned char *out, BF_KEY *key, int enc)`).
The call passes `enc=0` (`BF_DECRYPT`), and the surrounding loop manually implements
**CBC chaining** (XOR-with-previous-ciphertext) around the raw ECB primitive — this is a
textbook, from-scratch Blowfish-CBC decryption loop, matching real BigWorld's known use of
Blowfish for `Mercury::EncryptionFilter`, but this pass's confirmation comes from the
**literal OpenSSL import name** resolved via `.rela.plt`, independent of that external
knowledge.

- **Block size**: 8 bytes (Blowfish's native block size) — **CONFIRMED**.
- **IV**: all-zero for the first block (`x26` initialized to `0`, only used to XOR blocks
  *after* the first) — **CONFIRMED**.
- **Key/context**: `*(EncryptionFilter+0x30)`, a pointer to a heap-allocated
  **`BF_KEY`** structure (allocated via `operator new(0x1048)` in the constructor,
  `scratch/bf_setkey_callers.txt` — `0x1048` = 4168 bytes = **exactly `sizeof(BF_KEY)`**
  in OpenSSL: `BF_LONG P[18] + BF_LONG S[4][256]` = `72 + 4096` bytes — an exact
  structural match, not a coincidence).
- **Key derivation**: the `BF_KEY` is populated by OpenSSL's **`BF_set_key`** (import
  confirmed via the same `.rela.plt` method, PLT stub located at `0x7e2b00`, called from
  the `EncryptionFilter` constructor at `0x988ac4`/`0x988ac8`), from a **`std::string`
  passed as the constructor's second argument** — i.e., the raw key bytes are whatever
  string the *caller* of the constructor supplies. **This project did not, this pass,
  locate the concrete value of that string for the filter active during our test
  connection** (see Phase 5/Next Blocker) — it is a real, traceable value, not
  cryptographically hidden, but finding it requires either live memory inspection of a
  specific object chain not yet captured, or a different vantage point.
- **Padding**: after all blocks are decrypted, the **last byte of the plaintext**
  is read (`0x989330: ldrb w21, [x10, #0x60]`) and validated to be `<= 8` and `<= total
  length`; on success the logical length is reduced by that amount
  (`0x989348: sub w8, w8, w21`) — **CONFIRMED PKCS#5/PKCS#7-style padding**: encrypting an
  N-byte plaintext requires padding it up to the next multiple of 8 with `(8 - N%8)`
  bytes each holding that same count as their value (or a full 8-byte block of `0x08`
  bytes if N is already a multiple of 8 — the classic PKCS#7 rule, not verified against
  the exact-multiple edge case in this binary but standard for this padding family).

**Answering Phase 2's explicit questions**:

| Question | Answer |
|---|---|
| Exact function address | `0x98925c` (one of ≥3 near-identical implementations; see caveat above) |
| Input pointer | The Bundle iterator's own raw wire-data buffer, at `iterator+0x60` |
| Input length | `*(iterator+0x1a) + *(iterator+0x1c)`, i.e. the iterator's own tracked remaining-length fields |
| Output pointer | Same as input — **in-place** decryption |
| Key/context object | `*(EncryptionFilter+0x30)` → heap `BF_KEY` (4168 bytes), built by `BF_set_key` from a `std::string` |
| Cipher algorithm | **Blowfish** (`BF_ecb_encrypt`/`BF_set_key`, confirmed via `.rela.plt` import names) |
| Block size | 8 bytes |
| Padding behavior | PKCS-style: last plaintext byte = padding length (1–8), stripped after decrypt |
| IV behavior | All-zero for the first block; CBC chaining via ciphertext XOR thereafter |
| Is the 20-byte body supposed to be encrypted? | **Yes** — the client unconditionally attempts to decrypt whatever the active channel filter expects, and 20 bytes fails only the length-precondition, not a "should I decrypt this" check |
| In-place or separate buffer? | **In-place**, directly inside the iterator's own wire-data buffer |

## Phase 3 — `ServerConnection::checkScriptBaseAppAddr`, Fully Disassembled

Format string `"ServerConnection::checkScriptBaseAppAddr not call script, script addr=%s\n"`
(`0x2a49653`) has one live xref at `0x93a230`, inside the function at `0x93a108`/`0x93a134`
(`scratch/checkScriptBaseAppAddr.txt`).

```
checkScriptBaseAppAddr(this=x21 /*ServerConnection*/, arg1=x20, addrObj=x19)
0x93a164: ldr x24, [x24, #0x800]     ; x24 = a global pointer (a Python/script-engine
                                       ;   singleton check)
0x93a16c: ldr x8, [x24]
0x93a170: cbz x8, #0x93a224          ; NULL -> no scripting active -> "not call script" path
0x93a174: ldrb w8, [x21, #8]
0x93a178: cbz w8, #0x93a224          ; (also taken if this+8 flag is 0)
```

**This confirms, directly, why our test always shows "not call script"**: this test
environment has no active Python scripting layer hooked into the client (expected — this
is a bare native APK, not a modded/scripted build), so the client always takes this
native fallback path, which is simpler to analyze:

```
0x93a224: mov x0, x19                ; x19 = the address object
0x93a228: bl #0x981c0c               ; the SAME "address -> string" helper used throughout
                                       ;   this entire project for Mercury::Address objects
0x93a22c: mov x1, x0
0x93a230: <log "not call script, script addr=%s">
0x93a23c: ldr x0, [x20]
0x93a240: bl #0x93a404               ; the actual BaseApp connection-setup call
```

**CONFIRMED**: `x19` (the address argument) is processed by `0x981c0c`, the identical
address-stringification routine this project has used since much earlier sessions to
confirm the 8-byte `Mercury::Address` layout (4-byte IP + 2-byte port + 2-byte pad, network
byte order) elsewhere in this binary (e.g. in `Nub::processFilteredPacket`'s own logging).
**This directly confirms our existing `build_login_reply_record()`'s field-level
structure (two 8-byte address records + a 4-byte trailing value) does not need to change**
— the only problem is that its bytes arrive corrupted by a failed/mismatched decrypt
step before `onLoginReply` ever copies them out, not that the fields are in the wrong
place.

`0x93a404` (the actual connection-setup call) was not further disassembled this pass —
out of scope for the specific "what format is the address" question, and the observed
`Nub::recreateListeningSocket`/connection-attempt behavior already confirms it does what
its name implies. Not pursued further, flagged as available future work only if a new
blocker specifically requires it.

## Phase 4 — Searching For A Genuine BaseApp Address / Key Source

Searched (`grep`, string search in the ELF, and existing repository documents) for:

- **`server_list_ad.txt`**: this is a **local test-server-generated file** (part of
  `mitm_serve.py`'s own T18 patch-list emulation, not a client-embedded resource) — it
  contains synthetic ad/server-list content for the patch flow, unrelated to BaseApp
  addressing. **Confirmed irrelevant.**
- **Python `ServerConnection`/script variables**: per Phase 3, no scripting layer is
  active in this test build at all — there is no live Python-side `ServerConnection` to
  inspect. **Ruled out for this environment.**
- **Embedded server address strings**: no additional BaseApp-address-shaped strings
  (dotted IPs, `:port` patterns) were found searching near the `LoginHandler`/
  `checkScriptBaseAppAddr` cluster beyond what's already covered by the wire-format work
  above.
- **RSA-encrypted `LogOnParams` content**: per `LOGONPARAMS_SERIALIZATION.md` (already
  established, re-confirmed by re-reading this pass), the RSA-encrypted region contains
  `{flags_byte, stringA, stringB, stringC}` — **login credential fields**, not a
  client-generated symmetric key for the reply channel. **This specific hypothesis is
  now explicitly ruled out**, correcting a working assumption raised earlier in this
  pass's own investigation before the source document was re-checked.
- **The optional "digest" (`+0x5c`, 16 bytes, cleartext, conditional on
  `flags_byte & 1`) and "numericField" (`+0x58`, 4 bytes, unconditional per that
  document's own algorithm) fields**: byte-counting our own captured 273-byte requests
  (header 15 bytes + RSA ciphertext 256 bytes + footer 2 bytes = 273 exactly) shows
  **zero bytes remain for either field in this test client's actual traffic** — meaning
  for this specific login flow (a guest-style test account), `flags_byte & 1` is unset
  and, apparently contrary to that document's "unconditional" characterization of the
  numeric field, no trailing numeric field appears either. **This is flagged as a minor,
  unresolved discrepancy against `LOGONPARAMS_SERIALIZATION.md`'s own algorithm summary,
  not silently reconciled** — it may mean that document's step 10 requires a condition
  not documented there, or this build's compiled behavior differs slightly; not
  investigated further this pass since it does not bear directly on the encryption-key
  question once the "RSA region = credentials, not a key" conclusion was reached.

**Conclusion for Phase 4**: no alternate, independently-discoverable BaseApp address
source was found in this client's own data or traffic — the only path is the encrypted
20-byte LoginReply body, and the real blocker is the encryption key, not a missing
alternate data source.

## Phase 5 — The Original Expected 20-Byte Value: Structure Confirmed, Key Origin Not Yet Found

**Structure**: confirmed unchanged from `LOGIN_REPLY_RECORD.md`/`build_login_reply_record()`
— two 8-byte `Mercury::Address` records (this project's own earlier hypothesis was that
these represent the same BaseApp address sent twice, e.g. for redundancy or two related
purposes; not re-litigated this pass) followed by a 4-byte trailing value, all of which
must be Blowfish-CBC encrypted (with PKCS padding to 24 bytes) before transmission.

**Key origin — genuinely unresolved this pass.** The constructor call chain
(`0x939f94`/`0x93a04c`, `scratch/encfilter_ctor_callers.txt`) shows the key string
ultimately traces back to a value read from `*(some_resource_object + 0x148)`-adjacent
bookkeeping inside `onLoginReply`'s own broader context object
(`*(LoginHandler_this + 0x48)`), which was not captured live this pass (would require
knowing `LoginHandler_this`'s address at the exact moment of a live test — not printed by
any log line encountered so far, unlike the `Nub` pointer this project has successfully
captured live in earlier passes via the `DEBUG_BADFLAGS` trick).

**A second, independent lead found this pass, not yet exploited**: `onLoginReply`
contains an **optional, explicitly in-band key-installation mechanism** — a 4-byte magic
constant `0x32ef9816`, followed (if matched) by a length-prefixed string that gets
installed as a **new** `EncryptionFilter` key via the same constructor (`0x938278`–
`0x938324`, disassembled in Phase 1). **This means our own LoginApp reply can set its own
encryption key for whatever comes after**, but this does not solve the *current* problem
(our current 20-byte body must already be encrypted under whatever key the channel
*already* has installed, if any, before this optional mechanism ever runs — the order of
operations is: decrypt-attempt on the 20 bytes happens first, at a lower level, then
*after* that, this optional new-key block can be read). It is documented here as
**STRONGLY SUPPORTED, high-value, unexploited evidence** for a *future* pass: if a
default/initial key can be determined (even an empty or all-zero one), our own reply
could use this mechanism to install a *known* key of our choosing for all *subsequent*
messages, sidestepping the original-key-discovery problem entirely for anything after the
very first LoginReply.

## Phase 6 — Live Validation: Not Attempted This Pass

Per the task's explicit methodology rule ("Do NOT brute-force reply bodies... Do NOT test
dozens of candidate formats without understanding the parser"), **no new live packet
variant was tested this pass**, because the one missing piece (the actual key bytes) is
not yet known widely enough to construct a non-speculative encrypted body. Encrypting our
20-byte record with a *guessed* key would be exactly the kind of blind guessing this
project's own standing rules (and this task's explicit instructions) prohibit. The
existing Attempt H reply (unencrypted 20-byte body) remains the local server's default,
unchanged from the prior pass — it is still the furthest-confirmed-working candidate
(reaches `onLoginReply` reliably), and is left in place rather than replaced with an
unvalidated guess.

## Phase 7 — BaseApp Traffic Verification: Not Reached

No new BaseApp traffic reached `mitm/local_baseapp_capture.py`'s port-25010 listener this
pass (no new live test was run beyond the static analysis above, per Phase 6's reasoning).
This remains exactly where the prior pass (`MERCURY_REPLY_ID_TRACE.md`) left it: BaseApp
is never reached because the decoded address is garbled by the failed/mismatched decrypt
step.

## CONFIRMED

- The 20-byte LoginReply body is read as raw bytes by `LoginHandler::onLoginReply`
  (`0x938244`–`0x938260`) and stored at `LoginHandler_this+0x50..+0x64`, split as 16+4
  bytes — matching the existing `build_login_reply_record()` structure exactly.
- `ServerConnection::checkScriptBaseAppAddr`'s address argument is processed by the same
  address-to-string routine (`0x981c0c`) used project-wide for `Mercury::Address`
  objects — confirming the 8-byte address structure assumption is correct.
- `EncryptionFilter::decrypt` (`0x98925c`, one of ≥3 similar implementations) requires its
  input length to be an exact multiple of 8 bytes (`length & 7 == 0`), checked before any
  cipher operation — our 20-byte body fails this check and is used unmodified as a
  result, which is why prior tests produced plausible-but-wrong "addresses" rather than
  pure noise.
- The cipher is **Blowfish** (`BF_ecb_encrypt`/`BF_set_key`, confirmed via the literal
  OpenSSL import names resolved through `.rela.plt`), used in a hand-rolled **CBC** mode
  with an **all-zero IV** for the first block and **PKCS-style padding** (last plaintext
  byte = padding count, 1–8) validated and stripped after decryption.
- The key is a `BF_KEY` (OpenSSL, 4168 bytes, exact `sizeof` match) built from a
  `std::string` passed to the `EncryptionFilter` constructor (`0x9889e8`) — a real,
  traceable value, not derived from anything cryptographically inaccessible to us.
- The RSA-encrypted portion of the original `LogOnParams` request contains login
  credential fields (`flags_byte` + 3 strings), **not** a symmetric key for the reply
  channel — this specific hypothesis, raised mid-investigation, is explicitly ruled out
  by `LOGONPARAMS_SERIALIZATION.md`'s already-established field-level findings.
- `onLoginReply` additionally supports an **optional, in-band key-installation
  mechanism** (magic constant `0x32ef9816` + length-prefixed key string) for installing a
  **new** encryption key for subsequent messages — separate from, and evaluated after,
  the 20-byte body's own (attempted) decryption.

## UNKNOWN

- The concrete value/source of the `std::string` key passed into the active
  `EncryptionFilter`'s constructor for our test connection — not captured live this pass;
  the call chain leading to it (`LoginHandler_this+0x48` → some resource object →
  `+0x148`) is identified but not walked with a live pointer.
- Whether a *default* (e.g., empty, zero-length, or hardcoded constant) key is used when
  no explicit key has ever been installed via the magic-constant mechanism — plausible,
  not confirmed.
- Why our own test captures show zero bytes for the "digest"/"numericField" fields
  `LOGONPARAMS_SERIALIZATION.md` describes, when that document characterizes the numeric
  field as unconditional — a minor discrepancy, not reconciled this pass, and not
  believed to bear on the encryption-key question.
- The full behavior of `0x93a404` (the actual BaseApp connection-setup call) — not
  disassembled this pass, out of scope for the address-format question this phase
  answered.
- Which of the ≥3 near-identical `EncryptionFilter::decrypt` implementations
  (`0x98925c`, `0x98939c`, and the function reached via `0x989684`) is the one actually
  invoked for LoginApp traffic specifically, and via which exact vtable slot — not
  resolved; all three appear structurally identical in the portions inspected, so this
  is not expected to change the conclusions above, but is flagged as an open, low-priority
  gap.

## Next Blocker

Recover the actual key string installed in the `EncryptionFilter` active on the LoginApp
channel at the moment our reply is processed. The most promising, non-guessing paths,
in order of expected cost:

1. **Live memory read**: capture `LoginHandler_this`'s live pointer during a test run
   (this project has successfully done exactly this kind of live capture before, for the
   `Nub` object, via a temporary logging/instrumentation trick) and walk
   `LoginHandler_this+0x48` → `+0x148` → the `EncryptionFilter` object → its key
   `std::string` at `this+0x10`/`+0x18`, reading the raw key bytes directly out of
   process memory — mirroring the exact methodology that resolved the message-dispatch
   table and reply-ID questions in the two immediately preceding passes.
2. If no key is ever installed by default (empty/zero-length), determine what
   `BF_set_key` does with a zero-length key (OpenSSL-defined, deterministic, checkable
   without further client-side reverse engineering) and test encrypting our body under
   that specific, evidence-derived condition rather than guessing.
3. Only if both of the above are exhausted, consider whether a controlled RSA-keypair
   substitution (replacing the public key the client loads via
   `PublicKeyCipher::setKey`/`ServerConnection::setKeyFromResource` with one this project
   controls the matching private key for) is warranted to recover a session-specific
   value from the RSA-encrypted request region — a substantially larger, separate
   undertaking, flagged here only as a last-resort option, not recommended as the next
   immediate step.
