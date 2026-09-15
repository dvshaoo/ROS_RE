# Mercury LoginApp Key / Session Handshake

## Executive Finding

**The client's random Blowfish key never leaves the process through any channel this
project can find, decryption of the LoginReply's 20-byte body is unconditional (no
plaintext fallback exists in the code), and the outbound LogOnParams path uses RSA only
with zero involvement of the Blowfish filter.** Byte-for-byte accounting of the genuine
273-byte outbound request (already established in earlier passes: 15-byte header + 256-byte
RSA ciphertext + 2-byte footer = 273 exactly, no room left over) independently confirms
the key is not transmitted outbound. Combined with the already-proven facts that (a) no
inbound Mercury message precedes LoginReply and (b) the one key-update mechanism
(`0x32ef9816`) is strictly server→client and only protects messages *after* the one that
carries it, this creates a genuine, evidence-supported **paradox**: the code provides no
mechanism by which a real server could ever encrypt a *first* LoginReply's 20-byte body
usefully for a client it has never exchanged key material with. This document reports
that paradox honestly rather than resolving it with a guess — see "Remaining Hypotheses."
**A newly-found architectural detail this pass**: the `EncryptionFilter` class exposes a
full public interface (constructor pair, destructor pair, a generic encrypt/decrypt
method reachable via **virtual dispatch only**, a send/recv-shaped wrapper, and a
block-size accessor returning the constant `8`) — consistent with a real, general-purpose
`Mercury::PacketFilter`-style interface, not a bespoke one-off mechanism invented for
LoginReply alone. This strengthens confidence that the underlying cryptographic
machinery is genuine and general, even though this specific field's real-world usage
remains unresolved from client-side evidence alone.

## Client Random Key Generation

Unchanged from `MERCURY_KEY_STATE_LIFECYCLE.md`/`MERCURY_PRE_LOGIN_KEY_ESTABLISHMENT.md`,
cited not repeated: `RAND_bytes(this+0x11, 4)` inside `0x988cf8`, reached via
`0x917070`→`0x93a620`, regenerated fresh on every `logOnBegin` (proven live in the prior
pass by two different garbled results from the same unrestarted process).

## Random Key Data Flow — Phase 6, Fully Traced

Starting from the exact object (`this+0x10`/`+0x11`, the `EncryptionFilter`'s own SSO
string storage holding the 4 random bytes), every use of that storage was classified by
examining **all five methods of the class's vtable** (`0x37dd3a0`) plus the three known
`BF_set_key` call sites:

| Use | Function | What it does with the key bytes | Leaves the object? |
|---|---|---|---|
| Constructor (random) | `0x988cf8` | `RAND_bytes` writes directly into `this+0x11`; `BF_set_key` reads it back to build `BF_KEY` | No — stays in `this` |
| Constructor (explicit string) | `0x9889e8` | Copies a caller-supplied string into `this+0x10/+0x18`; `BF_set_key` reads it | No |
| Re-key method | `0x988be8` | Re-reads the object's *own* already-stored string; `BF_set_key` again | No |
| Destructor (vtable slot 0) | `0x988ecc` | Frees `BF_KEY` (`this+0x30`); does **not** touch or read the raw key string at all | No |
| Deleting destructor (vtable slot 1) | `0x988f1c` | Frees `BF_KEY`, then frees the string's heap buffer *if long-form* (never applicable to the 4-byte default, which is always SSO) — a pure deallocation, not a transmission | No |
| Encrypt/decrypt (vtable slot 2) | `0x988f68` → `0x98924c` (this pass corrects an earlier off-by-`0x10` mislabeling of this function's own entry point) | Reads `BF_KEY` (`this+0x30`, the *expanded* schedule, not the raw 4 bytes) and calls `BF_ecb_encrypt` in a CBC loop, in place on a caller-supplied buffer | No — only the *expanded* `BF_KEY` schedule is used, never the raw bytes directly, and the *output* is the caller's own ciphertext/plaintext buffer, not the key |
| Send/recv wrapper (vtable slot 3) | `0x989444` → `0x98924c` (direct, non-virtual `BL`) | Same as above — a thin argument-shuffling wrapper around the identical decrypt/encrypt body | No |
| Block-size accessor (vtable slot 4) | `0x989700` | `mov w0, #8; ret` — returns the constant `8`, touches no object state at all | No |

**No method of the class reads the raw key bytes for any purpose other than feeding them,
locally, into `BF_set_key`'s key-schedule expansion.** No method serializes, logs, copies
to another object, or writes the raw bytes to any buffer that Mercury's framing/socket
code could ever transmit.

**Cross-check against the actual outbound wire bytes**: the genuine 273-byte LogOnParams
request (`MERCURY_WIRE_CAPTURE.md`, re-verified this pass) accounts for **every single
byte** as `15-byte header + 256-byte RSA-OAEP ciphertext + 2-byte footer = 273`, with zero
bytes unaccounted for. There is no room in the actual wire format for a 4-byte (or any
other length) key field to have been appended and simply gone unnoticed.

**PHASE 6 ANSWER — the strongest negative conclusion this evidence supports**: **the four
random bytes never leave the client process.** This is proven by (a) exhaustive
enumeration of every function that can read the object's key storage (all 5 vtable
methods plus the 3 `BF_set_key` callers, none of which transmit it), and (b) independent,
byte-exact accounting of the only outbound message sent before a LoginReply could ever be
received, which has no unexplained bytes to carry it.

## Outbound Encryption Path — Phase 1 / Phase 7

```
OUTBOUND (LogOnParams):
  LogOnParams fields (flags, 3 strings, digest, numeric field)
    -> RSA-OAEP encrypt (0x9d8014/0x9d8018, PublicKey-based -- CONFIRMED in
       LOGONPARAMS_SERIALIZATION.md, unchanged)
    -> Mercury bundle framing (flags, msgID, length, footer)
    -> socket sendto()

  ** NO EncryptionFilter / Blowfish call exists anywhere on this path. **
  Confirmed by: (a) LogOnParams::addToStream's own fully-disassembled body (prior
  session's work) contains no reference to the EncryptionFilter class or BF_* functions,
  and (b) BF_set_key's three callers (this pass and the prior one, exhaustively
  enumerated) never touch any LogOnParams-related object or field.

INBOUND (LoginReply):
  socket recvfrom()
    -> Mercury bundle framing / message-ID dispatch (0xFF = "Reply")
    -> Nub::handleMessage reply-ID correlation
    -> LoginHandler::onLoginReply
         -> read 4-byte replyID, 1-byte status, THEN:
         -> 0x989600 (Blowfish-CBC decrypt, UNCONDITIONAL -- see below) applied to the
            20-byte body
         -> [only if >=5 bytes remain]: 0x32ef9816 magic check -> optional key REPLACEMENT
            for future messages (already fully reversed, unchanged from f99a292)
```

**New finding this pass, directly relevant to Phase 7's "asymmetry" question**:
`0x989600` (the function `onLoginReply` calls to decrypt its 20-byte body) contains **no
check of the filter's `this+0x2c` "encryption enabled" flag anywhere in its body** —
unlike the *other* decrypt implementation (`0x98924c`, reached via the class's own vtable
slot 2/3), which explicitly checks that flag first and takes a distinct "filter
disabled/invalid" path if it is clear (`cbz w8, ...` at the top of `0x98924c`). **This
means `onLoginReply`'s call to `0x989600` always attempts real Blowfish decryption on the
20-byte body — there is no code path by which this specific field could ever be sent or
interpreted as plaintext.** This directly rules out one plausible-sounding hypothesis
(that a real server might send this field unencrypted for a first exchange) as
**contradicted by the client's own code**, not merely unproven.

**The confirmed asymmetry**: outbound `LogOnParams` uses RSA exclusively; inbound
`LoginReply`'s 20-byte body uses Blowfish exclusively, unconditionally, under a key that
(per the data-flow trace above) the server has no way to have learned. These two
encryption mechanisms are architecturally and functionally **disjoint** in this client —
they do not share key material, do not share code paths, and serve what appear to be
different purposes (RSA protects the one-time credential submission; Blowfish is
structured for ongoing, replaceable session-level protection).

## Genuine LogOnParams Structure — Phase 2

Re-examined multiple genuine captures already in this project's evidence base (server
logs from `MERCURY_MESSAGE_ID_TRACE.md`, `MERCURY_REPLY_ID_TRACE.md`, and this pass's own
two-attempt experiment's underlying capture) for any plaintext byte that changes between
connections **and** is not already explained:

| Byte range | Behavior across captures | Explanation |
|---|---|---|
| `[0:4]` `01 00 00 04` | **Constant** across every capture this project has ever taken | Fixed Mercury framing (flags=1, msgID=0) |
| `[4]` `01` | **Constant** | Fixed protocol byte (already documented, unresolved semantic beyond "constant") |
| `[5:7]` | **Changes every single packet**, incrementing by exactly 1 per retry, confirmed across every session this project has captured (values freely span from small numbers up through `0x7600`+-range in long-running emulator sessions) | The already-confirmed reply-ID/retry counter (`MERCURY_REPLY_ID_TRACE.md`) — **not** newly correlated with the Blowfish key this pass; its role is fully explained already |
| `[7:11]` `00 00 00 00` | **Constant** | Fixed padding/reserved field |
| `[11:15]` `2b 00 00 00` | **Constant** (`=43`) | Confirmed hardcoded RSA-plaintext-length constant (`LOGONPARAMS_SERIALIZATION.md`) |
| `[15:271]` (256 bytes) | **Fully different every single packet**, including between different retries of the *same* login attempt | RSA-OAEP ciphertext — expected to look fully random regardless of plaintext, by design of OAEP padding; **no correlation with the Blowfish key can be claimed or ruled out from ciphertext alone**, since OAEP-encrypted output is indistinguishable from random without the private key |
| `[271:273]` `02 00` | **Constant** | Fixed footer |

**No byte outside the RSA ciphertext correlates with, or could plausibly encode, a 4-byte
value that changes per-connection the way the Blowfish key does** — every non-ciphertext
byte range is either fully constant or is the already-explained retry counter. **This is
a direct, evidence-based negative result, not an assumption**: if the client were sending
its Blowfish key in cleartext anywhere in this packet, it would have to appear in one of
these unchanging or already-explained ranges, and it does not.

**Regarding the RSA ciphertext itself**: this pass does **not** claim to know whether the
4-byte key is or is not inside the RSA-encrypted plaintext, because that plaintext is
provably unrecoverable without the matching private key (this project has never possessed
or attempted to obtain the real production private key, consistent with this project's
standing scope limits). What **is** provable, from the client-side code alone (Phase 6),
is that **no code path exists that reads the `EncryptionFilter`'s key and writes it into
the `LogOnParams` object or its serialization buffer** — meaning even if a determined
attacker fully decrypted the RSA ciphertext, this project's own static analysis says they
would **not** find the Blowfish key there, because nothing in the client ever puts it
there. This is stated as a structural/code-flow fact, independent of the (unrecoverable)
ciphertext content.

## LoginReply Structure — Phase 3

Re-confirmed from `LOGIN_REPLY_RECORD.md`, `MERCURY_LOGIN_REPLY_BODY_TRACE.md`, and this
pass's own re-reading of `onLoginReply`'s decoder code, now with the corrected
understanding that the 20 bytes are **always** Blowfish-decrypted before being
interpreted:

- **16 bytes**: loaded as a single 128-bit value (`ldr q0`/`str q0`) into
  `LoginHandler_this+0x50`. Structurally consistent with **two 8-byte `Mercury::Address`
  records** (this project's long-standing hypothesis from `build_login_reply_record()`),
  each internally `{4-byte IP, 2-byte port, 2-byte pad}` per the address-to-string helper
  (`0x981c0c`) this project has independently confirmed elsewhere operates on exactly this
  8-byte shape. **Not independently re-verified this pass** which of the two 8-byte halves
  (if they differ) plays which role — flagged UNKNOWN, unchanged from two passes ago.
- **4 bytes**: a trailing `uint32` stored separately at `LoginHandler_this+0x60`
  (`0x938258`). Purpose still not independently decoded (candidate: session/connection
  identifier, per this project's long-standing but unconfirmed guess).
- **No checksum, version, or flags field was found within the 20 bytes** — the entire
  structure is consumed as the two address records plus the one trailing value, with no
  spare bytes for anything else (16+4=20 exactly).
- **Number of addresses represented**: two 8-byte records are read, but this project has
  **not** proven whether the client treats them as "primary + fallback BaseApp address" or
  some other pairing (e.g., "internal + external address," a common BigWorld pattern for
  NAT traversal) — flagged UNKNOWN.

## BaseApp Address Decode

Unchanged from the prior two passes: `ServerConnection::checkScriptBaseAppAddr` processes
the decoded address via the same `0x981c0c` address-to-string routine used project-wide,
confirming the field layout above is structurally consistent, but the *decrypted content*
is garbage for every test this project has run, since the key used to decrypt it (the
random default) is never the key the sending server would need to have used.

## Server/Client Key Ownership — Phase 5

Evaluating the five offered hypotheses strictly against evidence gathered (this pass and
all prior ones), not architectural plausibility alone:

- **(A) client generates key → sends key to server through an existing protected
  mechanism**: **CONTRADICTED** by Phase 6's exhaustive negative trace — no code path
  sends the key anywhere, and the only outbound message before any reply is fully
  accounted for byte-for-byte with no room for it.
- **(B) server generates a key → client receives it through another mechanism**:
  **PARTIALLY SUPPORTED** — the `0x32ef9816` mechanism is a genuine, real,
  fully-reversed server→client key-installation channel. **However**, it is proven to only
  take effect for messages *after* the one carrying it (§ "Outbound Encryption Path"),
  so it cannot explain how a server-installed key could ever have been used for the very
  first LoginReply's own body — unless the real protocol simply does not expect the first
  LoginReply's body to be meaningfully decryptable (see D).
- **(C) client and server derive the same key independently**: **NOT SUPPORTED** — the
  key is proven to be drawn from a CSPRNG (`RAND_bytes`) with no derivation from any
  fixed, shared, or negotiable input (no seed, timestamp, or credential feeds into it,
  per the fully-traced `0x988cf8` constructor) — there is nothing for a server to
  independently derive.
- **(D) the 4-byte random key is only a temporary local filter key and LoginReply is not
  supposed to be encrypted under it in the way we currently assume**: **PARTIALLY
  SUPPORTED, but directly CONTRADICTED in one specific respect** — this pass's new finding
  that `0x989600` unconditionally attempts Blowfish decryption (no "disabled/plaintext"
  path exists) rules out the simplest version of this hypothesis ("the body might just be
  sent in the clear"). A more specific version survives: **the 20-byte body in a
  connection's very first LoginReply may not be meant to decode into a real, immediately-
  useful BaseApp address at all** — for example, if the genuine protocol's first LoginReply
  exists mainly to carry a `0x32ef9816` key-update block (establishing a shared key for
  **all subsequent** communication), with the 20-byte address field being a structurally
  required but functionally disposable/retry-triggering placeholder for that specific
  exchange, and the *real* BaseApp address arriving via a **later** message once a shared
  key is established. This project has not captured any such later-message evidence.
- **(E) another mechanism**: not ruled out, but no evidence points to a specific
  alternative beyond what (B)/(D) already describe.

**No single hypothesis is fully proven.** (A) and (C) are confidently ruled out. (B) is
proven as a real mechanism but insufficient alone. (D), in its more specific form, is the
hypothesis most consistent with the combination of "unconditional decryption" (ruling out
plaintext) and "server can never learn the client's first-message key" (ruling out any
single-message solution) — but it requires assuming a *second* LoginReply-class message
this project has never observed, which is not itself proven.

## Evidence Matrix

| Question | Answer | Evidence | Confidence |
|---|---|---|---|
| Does the 4-byte key ever leave the client? | No | Exhaustive vtable + `BF_set_key`-caller audit; byte-exact outbound packet accounting | CONFIRMED |
| Does outbound `LogOnParams` use Blowfish at all? | No | `LogOnParams::addToStream` disassembly (prior session) + `BF_set_key` caller audit (this pass) | CONFIRMED |
| Can the 20-byte LoginReply body ever be sent/received as plaintext? | No | `0x989600` has no "enabled" gate, unlike its sibling `0x98924c` | CONFIRMED |
| Is there a byte in genuine `LogOnParams` captures correlating with a changing 4-byte value outside the RSA ciphertext? | No | Byte-range comparison across multiple genuine captures | CONFIRMED (for all non-ciphertext bytes) |
| Does the RSA ciphertext itself contain the key? | Unknown, unrecoverable without the private key | N/A — explicitly out of scope | UNKNOWN by design, not investigated |
| Is `0x32ef9816`'s key-update the only server→client key path? | Yes | Whole-binary literal search, one occurrence (prior pass, re-confirmed) | CONFIRMED |
| Can that key update ever protect the SAME message's own body? | No | Instruction-order proof: decrypt (`0x938234`) precedes the magic-constant check (`0x938278`) | CONFIRMED |
| Is the `EncryptionFilter` class a general-purpose filter interface, not LoginReply-specific? | Yes | Full 5-method vtable audit this pass shows a generic ctor/dtor/encrypt-decrypt/accessor shape | STRONGLY SUPPORTED |
| Does a genuine server-side LoginReply capture exist in this repository? | **No** | Explicit search of `scratch/`, `mitm/captures/`, and every `06_trace/*.md` document this pass | CONFIRMED ABSENT |

## Genuine LoginReply Capture — Explicit Search Result (Phase 4)

Searched `scratch/` (all `.pcap`, `strace`, and logcat captures across this entire
project), `mitm/captures/`, and every existing `06_trace/*.md` document for a genuine,
real-server-originated LoginReply. **None exists.** Every LoginReply this project has
ever observed being processed by the client was sent by this project's own local test
server (`mitm/local_baseapp_capture.py`), using structures this project itself
constructed (Attempts A through H). **This is stated explicitly, not glossed over**: this
project has never captured real ROS production server traffic for this message type, and
this document does not fabricate one. All conclusions above rest on client-side code
analysis and this project's own local test traffic only.

## Remaining Hypotheses (Ranked By Evidence Support)

1. **A genuine LoginReply's first exchange establishes a new key via `0x32ef9816` for use
   by later messages, and its own 20-byte body is not meant to be meaningfully decodable
   on this first exchange** — most consistent with all proven facts, but requires an
   unobserved second message to complete the picture.
2. **The real protocol never actually relies on a client-generated Blowfish key for
   LoginApp communication at all**, and the 20-byte body's Blowfish decryption is
   effectively a vestigial/legacy code path from a shared BigWorld codebase that a real
   NetEase/ROS server never triggers usefully (i.e., real servers might rely on the
   `checkScriptBaseAppAddr`'s "call script" branch — the one this project's tests never
   take, since no Python scripting layer is active — for the actual, correct address,
   with the native decode path serving only as a fallback / different purpose). **Not
   independently investigated this pass** — the "call script" branch of
   `checkScriptBaseAppAddr` has never been disassembled in this project's history.
3. **A separate, not-yet-found handshake path exists outside the LoginApp
   request/reply this project has focused on** (e.g., a prior TCP/HTTP-based session
   negotiation via NetEase's own UniSDK/MPay layer, observed only as opaque HTTPS traffic
   in this project's MITM captures) that pre-establishes shared key material before the
   Mercury-level exchange even begins. **Plausible given this project's own captures
   show extensive UniSDK/MPay HTTPS traffic before any Mercury packet is ever sent**, but
   not traced to any Blowfish-key content this pass.

## SINGLE NEXT EXPERIMENT

**Disassemble `ServerConnection::checkScriptBaseAppAddr`'s "call script" branch** (the
one this project's tests have never exercised, since no Python UI-scripting layer is
active in this test environment) to determine whether it represents an **entirely
separate, non-Blowfish-dependent path** by which a real client/server pair might exchange
the actual BaseApp address — for example, via a Python-level callback that could receive
address data through a different channel than the native 20-byte decrypt path this
project has been analyzing. **This experiment requires no new packet bytes to be
invented** — it is pure static disassembly of code this project has already located
(`0x93a1fc`–`0x93a220`ish, the `cbz`/`ldr` branch this project's own traces have
consistently shown taking the "not call script" path) but never read the *other* side of.
This is the highest-information-gain next step because it could either (a) confirm
hypothesis 2 above with direct evidence, or (b) rule it out cleanly, without requiring any
speculative packet construction, brute-forcing, or assumption about unobserved server
behavior.

## FINAL REPORT

```text
KEY SOURCE: OpenSSL RAND_bytes(4), generated locally by the client, fresh per login attempt.
KEY LEAVES CLIENT: NO -- proven by exhaustive audit of all 5 EncryptionFilter vtable
  methods, all 3 BF_set_key callers, and byte-exact accounting of the only outbound
  message (LogOnParams) sent before any reply could arrive.
OUTBOUND ENCRYPTION: RSA-OAEP only, for LogOnParams's credential fields. The Blowfish
  EncryptionFilter is never invoked anywhere on the outbound path.
LOGINREPLY ENCRYPTION: Blowfish-CBC, UNCONDITIONAL (no plaintext fallback exists in the
  code) for the 20-byte body, using whatever key is currently cached -- which, for any
  first-ever LoginReply, can only be the client's own unknowable random default.
REAL SERVER RESPONSE CAPTURE: DOES NOT EXIST in this repository. Every LoginReply this
  project has processed was sent by its own local test server. This is stated explicitly.
CURRENT BLOCKER: The client's code provides no mechanism by which a real server could
  ever produce a USEFULLY decryptable first LoginReply body, given the key is never
  transmitted and decryption cannot be bypassed. Resolving this requires either genuine
  reference traffic (unavailable) or disassembling the untested "call script" branch of
  checkScriptBaseAppAddr, which may represent an entirely separate address-delivery path.
HIGHEST-VALUE NEXT EXPERIMENT: Static disassembly of checkScriptBaseAppAddr's "call
  script" branch (no new packets, no guessing, no brute-forcing) to determine whether a
  non-Blowfish-dependent address-delivery path exists.
```
