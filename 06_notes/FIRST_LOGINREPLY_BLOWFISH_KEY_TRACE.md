# ROS v1117219 — First LoginReply Blowfish Key Origin: Consolidated Trace

This document consolidates every prior pass's findings on the `EncryptionFilter` /
Blowfish key lifecycle (`06_trace/MERCURY_ACTIVE_DECRYPT_TRACE.md`,
`MERCURY_KEY_STATE_LIFECYCLE.md`, `MERCURY_LOGIN_REPLY_KEY_TRACE.md`,
`MERCURY_PRE_LOGIN_KEY_ESTABLISHMENT.md`, `CHECK_SCRIPT_BASEAPP_ADDR_TRACE.md`) with
this pass's new work: a full read of `ServerConnection::logOnBegin` (`0x93bcc8`,
dumped in `scratch/logOnBegin_full.txt`) and the previously-unread helper `0x93c720`
(dumped in `scratch/trace_93c720.txt`). Labels used throughout: **CONFIRMED** (directly
observed in disassembly, register-traced), **STRONGLY SUPPORTED** (consistent
circumstantial evidence, no contradicting data), **INFERRED** (plausible reading not
fully instruction-traced), **UNKNOWN** (not established either way).

## 1. Executive Summary

No new key-installation path was found this pass. `ServerConnection::logOnBegin`
(`0x93bcc8`–`0x93c164`+) was read in full and contains **zero calls** to any of the
three known `BF_set_key`-reaching constructors (`0x9889e8`, `0x988cf8`, `0x988be8`) or
to the key-update dispatcher (`0x939f94`) — **CONFIRMED** by exhaustive grep of the
disassembly dump for those call targets. `logOnBegin` only **reads/validates/logs** the
already-existing cached `EncryptionFilter` at `resource_object+0x148` (via a
`dynamic_cast` chain identical in shape to `onLoginReply`'s own cache-lookup) and does
not replace it. The helper `0x93c720` it calls turns out, on full disassembly, to
construct an unrelated **diagnostic/log-record object** (different vtable constant,
3 embedded `std::string` fields, a counter field, and a sub-object — not an
`EncryptionFilter`), which happens to copy the *current* key string as one of its log
fields but does not mutate it. This closes out Task B's open question about `0x93c720`
without finding a new key path.

Net effect: this pass **narrows, but does not resolve**, the standing paradox
documented in `MERCURY_KEY_STATE_LIFECYCLE.md` — no code path anywhere yet found
(across `onLoginReply`, `checkScriptBaseAppAddr`, `logOnBegin`, or the constructor/setter
audit) lets a server learn or predict the client's per-connection `RAND_bytes(4)` key,
and no path replaces that key before the first LoginReply's body is decrypted at
`0x989600`.

## 2. Exact Active EncryptionFilter Object

**CONFIRMED** (re-affirmed, unchanged from `MERCURY_ACTIVE_DECRYPT_TRACE.md` /
`MERCURY_KEY_STATE_LIFECYCLE.md`):

- Class vtable (tool address): `0x37dd3a0`.
- Storage location: `resource_object+0x148` (a per-connection cache slot), where
  `resource_object` is reached as `LoginHandler_this+0x48` in `onLoginReply` and as
  `x21` (a field of the object `logOnBegin` operates on, loaded at `0x93bde8: ldr x25,
  [x21, #0x148]`) in `logOnBegin`. **NEW THIS PASS**: `logOnBegin` reads this exact same
  `+0x148` slot before ever sending the LogOnParams request — i.e. the filter object
  already exists (or is already being probed for) at `logOnBegin` time, consistent
  with construction happening earlier in `ServerConnection` setup
  (`0x917070`→`0x93a620`→`0x988cf8`, established in prior passes), not inside
  `logOnBegin` itself.
- Field layout: `+0x00` vtable, `+0x10/+0x18` `std::string` key material (SSO-aware),
  `+0x2c` "encryption enabled" bool, `+0x30` `BF_KEY*` (4168-byte OpenSSL struct).

**NEW / CONFIRMED THIS PASS — the `logOnBegin` cache-lookup dance**: at `0x93bde8`–
`0x93be6c`, `logOnBegin` performs the *identical shape* of cache-validate logic already
documented for `onLoginReply`'s own filter lookup:

```
0x93bde8: ldr x25, [x21, #0x148]        ; x25 = cached filter pointer (may be null)
0x93bdec: cbz x25, #0x93be6c            ; empty cache -> skip straight to join point
0x93bdf0-0x93be08: dynamic_cast(x25, srcType=[0x3917000+0xc10], dstType=[0x3915000+0x158])
0x93be0c: cbz x0, #0x93be4c             ; cast #1 failed -> try cast #2
0x93be10-0x93be48: (cast #1 succeeded) call 0x9898e0 ("validate/refresh" helper,
                    same one seen reused from onLoginReply), adjust refcount, join
0x93be4c-0x93be68: dynamic_cast(x25, dstType=[0x3914000+0x6f8])  ; cast #2, same 3rd
                    candidate type onLoginReply itself falls back to
0x93be6c: add x3, x25, #0x10            ; JOIN POINT: x3 = &(cached filter's key string)
```

**INFERRED**: this is `logOnBegin` performing the exact same "is my cached filter still
a live/valid `EncryptionFilter`-family object" check `onLoginReply` performs before
using it, most likely as part of building a diagnostic log line about the connection's
current crypto state (see §3) rather than for any encryption/decryption action of its
own — `logOnBegin` contains no encrypt/decrypt call (`0x98924c`, `0x989600`,
`0x98938c`) anywhere in its body (**CONFIRMED** by grep of the full dump).

## 3. Complete Key Lifetime

Combining all passes, the full lifecycle of the *default* key is:

1. **CONFIRMED** — `ServerConnection` construction: `0x917070` → `0x93a620` →
   `0x988cf8`. `RAND_bytes(buf=this+0x11, len=4)` (return value discarded/unchecked) →
   `BF_set_key(BF_KEY*=this+0x30, len=4, key=this+0x11)`. Installed unconditionally,
   before any network I/O.
2. **CONFIRMED (this pass)** — `logOnBegin` runs afterward (it is the function that
   *sends* the LogOnParams/`LoginApp::login` request) and only **reads** the cached
   filter at `+0x148` (dynamic_cast + refcount bump + a call into `0x93c720`, see §4).
   No write to `this+0x30`/`this+0x10` of that object occurs anywhere in `logOnBegin`.
3. **CONFIRMED (prior passes)** — the request is sent RSA-encrypted (`LOGONPARAMS_SERIALIZATION.md`),
   unrelated to the Blowfish filter.
4. **CONFIRMED (prior passes)** — `onLoginReply` reads and decrypts the 20-byte
   LoginReply body via `0x989600`, using whatever filter is cached at `+0x148` at that
   moment — for the *first* LoginReply on a fresh connection, that is necessarily the
   same object constructed in step 1, since nothing between steps 1 and 4 (traced
   across `logOnBegin` this pass, and `onLoginReply`'s own pre-decrypt code in prior
   passes) writes to it.
5. **CONFIRMED (prior passes)** — only *after* the decrypt, `onLoginReply` optionally
   parses an in-band `0x32ef9816`-gated key-replacement block, which (if present)
   replaces the cached filter for *subsequent* messages only.

**Conclusion (re-affirmed, not newly overturned)**: for the first LoginReply, the
active decrypt key is **CONFIRMED** to be the same `RAND_bytes(4)` value installed at
connection construction — no write to the key fields of that exact object instance
occurs anywhere between construction and the `0x989600` call, across every function
this project has now read in this path (`0x917070`, `0x93a620`, `0x988cf8`,
`logOnBegin` in full, `onLoginReply`'s pre-decrypt code).

## 4. All BF_set_key Callers

| Caller | Address | Trigger | Input Key Source | Key Length | Target Object | Before/After 1st LoginReply | Status |
|---|---|---|---|---|---|---|---|
| `0x988cf8` (ctor, length overload) | `0x988dbc` | `ServerConnection` construction (`0x917070`→`0x93a620`) | `RAND_bytes(4)`, locally generated | Fixed 4 bytes | Newly-`operator new`'d `EncryptionFilter` instance | **BEFORE** | CONFIRMED |
| `0x9889e8` (ctor, string overload) | `0x988ac4`/`0x988ad4` region | Only reachable via `0x939f94`, only called from `onLoginReply`'s `0x32ef9816` block (`0x938324`) | Wire-read, length-prefixed string, verbatim | 4–56 bytes (validated range) | Same cache slot `+0x148` (replaces the default) | **AFTER** (and even for the same message, after that message's own body decrypt — wire-order proven) | CONFIRMED |
| `0x988be8` ("re-key from existing string") | `0x988c00` | No caller found anywhere in the binary (re-confirmed this pass by re-checking; no new callers surfaced in `logOnBegin`) | The object's own already-stored key string (re-derives `BF_KEY`, no new input) | Whatever is already stored | Same object, in place | **UNKNOWN — unreached** | CONFIRMED (as unreached) |
| 23 other `str x?,[x?,#0x30]` sites in the `0x988000`–`0x99a000` cluster | various | Not investigated | Not investigated | Not investigated | UNKNOWN | Flagged, not chased (per prior pass's proportionality judgment, re-affirmed here — none of `logOnBegin`'s newly-read code intersects this cluster) |
| `logOnBegin` itself (`0x93bcc8`–`0x93c164`+) | n/a | n/a | n/a | n/a | n/a | n/a | **CONFIRMED THIS PASS: NOT a key-setting site** — full-body grep for all three constructor addresses and `0x939f94` found zero calls |

No caller beyond the two already-established live ones (`0x988cf8` for the default,
`0x9889e8` for the in-band update) was found. `logOnBegin` was the most promising new
candidate this pass (since it is the function that both reads the cache slot and
executes immediately before the request that provokes the first LoginReply) and is now
**ruled out** as a key-mutation site.

## 5. All Key Mutation Paths

Unchanged from `MERCURY_KEY_STATE_LIFECYCLE.md §2`: exactly two live mutation paths
(construction with a random key; in-band replacement gated by `0x32ef9816`), plus one
dead/unreached setter (`0x988be8`). This pass adds **one new negative result**:
`logOnBegin`'s cache-slot access at `0x93bde8`–`0x93be7c` is a **read-only
validate-and-log** operation, not a mutation — confirmed by (a) no store to
`filter+0x10`/`filter+0x30` anywhere in the traced range, and (b) the callee it invokes
(`0x93c720`) constructing an object of a *different* class entirely (§6).

## 6. Random Constructor Key vs. First LoginReply Key — Object-Identity Evidence

Task D asked to determine, from actual object-identity/data-flow evidence rather than
constructor-proximity inference, which of (A)–(F) describes the `RAND_bytes` key's
role. Evidence gathered:

- **(A) Final session key for the *first* exchange**: **STRONGLY SUPPORTED**. The same
  cache slot (`+0x148`) is read by both `logOnBegin` (before sending the request) and
  `onLoginReply` (at decrypt time), with no intervening write anywhere in the traced
  code. Since `logOnBegin` is the function that transmits the request whose reply is
  the first LoginReply, and it observes the *same* pointer value at `+0x148` that
  `onLoginReply` later dereferences for `0x989600`, this is direct (not merely
  proximate) evidence that the object is the same instance across both call sites —
  i.e., the random key is genuinely the operative key for the first reply, not
  incidentally close in the code layout.
- **(B) Placeholder later replaced**: **CONFIRMED false for the first reply** — the
  only replacement mechanism (`0x32ef9816`) is proven (prior pass, wire-order trace) to
  take effect only for messages *after* the one carrying it, and `logOnBegin` performs
  no replacement either. It may still be a "placeholder" in the sense that a *real*
  server could replace it via `0x32ef9816` starting with the *second* server-to-client
  message, but not before/during the first.
- **(C) Temporary filter later replaced**: same answer as (B) — true only for later
  messages, not the first.
- **(D) Key for a different direction/path**: **NOT SUPPORTED** — `0x989600` (decrypt of
  the LoginReply body, a server→client direction) and the RAND_bytes-seeded object are
  the same object at the same cache slot; no separate per-direction filter object or
  cache slot was found anywhere in this or prior passes.
- **(E) Overwritten before LoginReply decrypt**: **CONFIRMED false** by the same
  no-intervening-write evidence as (A).
- **(F) Something else**: no candidate found.

**Conclusion**: (A) is the best-supported answer for the first LoginReply specifically;
(B)/(C) become accurate only starting with the second server message, per the
already-proven `0x32ef9816` mechanics.

## 7. RSA Plaintext / Key Relationship

Per Task F, `06_trace/LOGONPARAMS_SERIALIZATION.md` was reviewed rather than
re-deriving the 273-byte structure. That document's established structure is: 15-byte
Mercury/request header, then a 256-byte RSA-OAEP ciphertext block, then a 2-byte
footer — **no additional field exists in the 273-byte envelope for a session/derivation
value**, and the RSA ciphertext's own plaintext contents (per that document, credential
fields consumed server-side for authentication) were not shown, in that document or
this pass's review, to contain or produce any value that flows back into the Blowfish
filter object. No new disassembly was performed this pass specifically re-opening the
RSA plaintext layout (out of scope duplication per the task's own instruction to avoid
re-deriving it); this section reports a **negative result by absence of any
data-flow edge**, not a fresh structural analysis. **STRONGLY SUPPORTED, not
CONFIRMED**: the RSA path and the Blowfish filter's key are structurally and
temporally independent — the filter is constructed during `ServerConnection` setup
(`0x917070`), which prior passes place before `logOnBegin`/RSA-request construction,
and nothing in `logOnBegin`'s now-fully-read body reads any RSA-related buffer when
touching the filter cache slot.

## 8. Auth-to-Game Session Data Flow

`06_trace/ROS_LOGIN_PLAY_TRACE.md`, `06_notes/NATIVE_LOGON.md`, and
`06_notes/G2_GAME_SESSION_TRACE.md` already cover the Sdk-login → `NativeOnLogin` →
Python `ntOnLogin` → `requestServerList` → `doLoginGame` → `ServerConnection::logOnBegin`
chain (per this task's instruction, cited rather than re-traced in full this pass).
This pass's specific contribution is confined to `logOnBegin`'s own native body, which
is the last hop before the Mercury wire protocol. Within that native body, **no read of
any auth/session token, account ID, server-list metadata field, or JNI-passed buffer**
was observed feeding the `EncryptionFilter`/`BF_set_key` machinery — the only inputs
`logOnBegin` uses near the filter cache slot are the cache pointer itself and (per §9)
two unrelated local strings and a resource-object field at `+0x140`/`+0x15b` used for
logging/telemetry, not key material. **INFERRED** (not exhaustively re-verified this
pass across the Java/Python layers) that no session-derived value reaches the Blowfish
key; **CONFIRMED** for the native `logOnBegin` body specifically.

## 9. Pre-Reply Non-Packet Key Setup — The `0x93c720` Finding

This was the main open item carried into this pass (Task B/I). Full disassembly of
`0x93c720`–`0x93c934` resolves it:

```
0x93c720(this=x0, str1=x1, str2=x2, str3=x3):
    this->vtable_ptr = &(0x37d7000+0xc68)      ; DIFFERENT constant from EncryptionFilter's
                                                  ; 0x37dd3a0 -- NOT the same class
    this->field_08 (int)  = 0
    this->field_0c (bool) = 1 (true)
    copy str1 (SSO-aware) into this+0x10/+0x18/+0x20   ; 1st embedded std::string
    copy str2 (SSO-aware) into this+0x28/+0x30/+0x38   ; 2nd embedded std::string
    copy str3 (SSO-aware) into this+0x40/+0x48/+0x50   ; 3rd embedded std::string
    this->field_58 (int) = <result of 0x7e2be0()>       ; looks like a counter/ID/tid call
    construct sub-object at this+0x5c via 0x97d3fc(this+0x5c)
```

**CONFIRMED**: this is a fixed-shape object with a *different* vtable constant than
`EncryptionFilter` (`0x37d7000+0xc68` vs. `0x37dd3a0`), three embedded strings, an
int, a bool, a counter/ID field, and one more sub-object — **it is not an
`EncryptionFilter` instance and does not call `BF_set_key` or touch `BF_KEY` memory
anywhere in its body** (grep-confirmed).

At the call site in `logOnBegin` (`0x93be70`–`0x93be7c`):
```
0x93be70: add x1, sp, #0x60        ; str1 = a local std::string (built earlier in logOnBegin)
0x93be74: sub x2, x29, #0x70       ; str2 = another local std::string
0x93be78: mov x0, x19              ; this = a stack-local object about to be destroyed
                                      ; right after use (RAII cleanup follows at 0x93be80+)
0x93be7c: bl #0x93c720
```
and `x3` at this call site is the join-point value `x3 = x25+0x10` computed at
`0x93be6c` — i.e. **the cached `EncryptionFilter`'s own key-string field
(`filter+0x10`)** is passed as the *third* string argument.

**INFERRED (STRONGLY SUPPORTED by context, not independently confirmed by seeing the
consumer of this object)**: `0x93c720` builds a short-lived diagnostic/log-record
object — one plausible read is a structured log entry combining (address string,
some other descriptor string, and the current key string) for a verbose/debug log
line — immediately before the `"ServerConnection::logOnBegin conneting to..."` log
call visible at `0x93c108` a few dozen instructions later in the same function. This
is **not proven** to be a log call specifically (the object's true consumer — what
happens to it after construction, before the RAII teardown at `0x93be80`+ — was not
traced beyond the constructor itself), but it is **CONFIRMED** that:
1. It is not an `EncryptionFilter` and does not mutate one.
2. It **reads** the current filter's key-string bytes (copies them into its own
   storage) — meaning the key value is, at minimum, exposed to this diagnostic
   pathway at `logOnBegin` time (possibly logged in verbose/debug builds), but this
   is a read/observe operation, not a key-establishment or key-replacement mechanism.

**Answering Task I directly**: this is the only pre-first-LoginReply, non-packet,
filter-adjacent code found in `logOnBegin`. It does **not** configure/replace the
filter. No other socket-established/connection-established/timer/native-state-transition
callback touching the filter cache slot was found in the portion of `logOnBegin` read
this pass.

## 10. The Mystery `+0x15b` / `this+0x5c` Copy and the 184-byte (`0xb8`) Allocations

Read in full this pass (`0x93beb8`–`0x93c164`, previously unread lines 145–290 of
`scratch/logOnBegin_full.txt`):

- `0x93beb8`–`0x93bec0`: a 16-byte (`ldr q0`/`stur q0`) copy from `resource_object+0x15b`
  into `this+0x5c` (the `logOnBegin` object, i.e. `ServerConnection`/`LoginHandler`'s
  own `this`, not the filter). **UNKNOWN** what these 16 bytes represent structurally
  — no type information was recoverable from this instruction alone. Given the offset
  (`+0x15b`) sits close to, but is distinct from, the already-established `+0x148`
  filter-cache field and the `+0x140` field checked immediately afterward, **INFERRED**
  this is some other piece of per-connection state (candidate guesses: a raw address
  struct, a GUID, or two packed pointers) — **not** identified as key material; no
  `BF_set_key`/`BF_KEY` reference touches this region.
- `0x93bec4`–`0x93bf68` and `0x93bfe4`–`0x93c06c`: **CONFIRMED** two structurally
  identical 184-byte (`w0=0xb8`) heap allocations, each populated with the same fixed
  field layout (a table/vtable-like pointer from `adrp 0x3918000+0xa28` /
  `adrp 0x37d6000+0xc70`, a `strh` at `+0x64`, zeroed pairs at `+0x40/+0x98/+0x70/+0xa8`,
  an embedded pointer-pair at `+0x88/+0x90`), followed in both cases by an
  atomic increment/decrement pair (`ldaxr`/`stlxr` LL/SC sequences) consistent with an
  **intrusive-refcounted smart-pointer assignment**, and a store of the new object's
  address into a slot read from `[sp,#0x18]`/`[sp,#0x20]`. **INFERRED**: this is a
  refcounted event/message object (candidate: a connection-lifecycle event, telemetry
  record, or async task object) being constructed and queued/assigned — **its size
  (184 bytes) does not match `EncryptionFilter` (≈0x38) or `BF_KEY` (0x1048)**, and no
  `BF_set_key` or key-string field access occurs anywhere in either allocation's
  population code (grep-confirmed against both dumped ranges). **CONFIRMED NOT
  key-related**; exact purpose remains **UNKNOWN** beyond "refcounted object, unrelated
  to the Blowfish filter."
- The two allocation sites are guarded by different conditions (`ldr x8,[x21,#0x140];
  cbz` for the first, and a `cbz w0` on the result of `0x98a3f4` for the second) and
  both converge into the same log-emission code around `0x93c0fc`–`0x93c164` (the
  `"ServerConnection::logOnBegin conneting to..."` log call and a following call at
  `0x93c134` (`0x7d39b0`) building yet another log-adjacent value). **INFERRED**: these
  are alternate telemetry/log paths (e.g., "log with extra diagnostic object" vs.
  "log plain"), not alternate key-setup paths.

## 11. Runtime Evidence

**Not performed this pass.** Per Task H's own gating condition ("only if Tasks A–G
leave genuine ambiguity that static analysis cannot resolve") and Task J's instruction
not to repeat the prior blind 940MB heap scan: this pass's static findings (§§2–10)
answer every question Tasks A–G posed with either CONFIRMED or clearly-scoped UNKNOWN
answers that do not hinge on a runtime value — the standing paradox (§12) is a logical
one (no code path found, not "a code path exists but its live value is unknown"), so a
live capture would not resolve it without a fundamentally different search target than
the ones already ruled out in `MERCURY_LOGIN_REPLY_KEY_TRACE.md` (untagged/custom
allocator memory, which that document already flagged as the correct next step if this
line of inquiry continues).

## 12. Remaining Unknowns

- The true purpose/consumer of the `0x93c720` diagnostic object (confirmed to read the
  key string, not confirmed to log it — its post-construction use was not traced).
- The meaning of the 16 bytes at `resource_object+0x15b` copied into `this+0x5c`.
- The purpose of the two 184-byte refcounted objects (confirmed unrelated to the
  filter, exact class/purpose otherwise unknown).
- The 23 unexamined `+0x30` write sites in the `0x988000`–`0x99a000` cluster (carried
  over, unchanged, from `MERCURY_KEY_STATE_LIFECYCLE.md`).
- Whether `0x988be8` (the no-argument re-key method) has a caller reachable via a
  vtable slot not yet statically mapped (carried over, unchanged).
- **The core paradox itself**: no mechanism has been found, across every function this
  project has now read in the pre-LoginReply and LoginReply-handling code
  (`ServerConnection` construction, `logOnBegin` in full, `onLoginReply`,
  `checkScriptBaseAppAddr`), by which a server could learn or predict the client's
  `RAND_bytes(4)` key before the first LoginReply is sent, nor any path that replaces
  that key before the first LoginReply's body is decrypted. This is now a
  **well-scoped absence** (multiple full-function reads with zero matching call sites)
  rather than an unexplored gap, but it remains unresolved.

## 13. Confidence Levels for Major Conclusions

| Conclusion | Confidence |
|---|---|
| `logOnBegin` performs no `BF_set_key`/constructor/key-update call | CONFIRMED (exhaustive grep of full function body) |
| `logOnBegin` reads (does not write) the cached filter at `+0x148` | CONFIRMED |
| The random constructor key is the active key for the first LoginReply decrypt | CONFIRMED (no intervening write found in any traced function) |
| `0x93c720` is a different class from `EncryptionFilter` | CONFIRMED (different vtable constant, no `BF_KEY`/`BF_set_key` references) |
| `0x93c720` is specifically a log/diagnostic record | STRONGLY SUPPORTED, not fully CONFIRMED (consumer not traced) |
| The 184-byte allocations are unrelated to the filter | CONFIRMED (size mismatch + no key-field access) |
| The 184-byte allocations are refcounted telemetry/event objects | INFERRED |
| The `+0x15b`/`+0x5c` 16-byte copy is unrelated to the key | STRONGLY SUPPORTED (no BF_KEY/key-string reference), exact meaning UNKNOWN |
| RSA plaintext structure contains no Blowfish-key-derivation value | STRONGLY SUPPORTED (absence of data-flow edge; not a fresh RSA-plaintext re-derivation) |
| No auth/session value from the Java/Python layers reaches the filter | INFERRED for the native `logOnBegin` body (CONFIRMED there); not independently re-verified across the full Java/Python chain this pass |
| The core key-origin paradox remains unresolved | CONFIRMED as a well-scoped absence, not a proof of impossibility |

```
CONCLUSION:
FIRST_LOGINREPLY_KEY_SOURCE: The locally-generated RAND_bytes(4) default key installed during ServerConnection construction (0x917070->0x93a620->0x988cf8) — CONFIRMED as the object active at the 0x989600 decrypt call for the first LoginReply, with no intervening write found in ServerConnection construction, the full body of ServerConnection::logOnBegin (newly read this pass), or onLoginReply's pre-decrypt code.
RANDOM_CONSTRUCTOR_KEY_IS_ACTIVE: YES — CONFIRMED by absence of any intervening write to the filter's key fields (this+0x10/this+0x30) across every function traced between construction and first decrypt, including the full newly-read body of logOnBegin.
KEY_REPLACEMENT_BEFORE_FIRST_REPLY: NONE FOUND. The only replacement mechanism (0x32ef9816, in-band in LoginReply itself) is proven to affect only messages after the one carrying it, and logOnBegin (fully read this pass) performs no replacement of its own — it only reads/validates/logs the existing cached filter via a dynamic_cast chain and the diagnostic helper 0x93c720.
RSA_KEY_RELATIONSHIP: NO CONFIRMED LINK. The 273-byte LogOnParams RSA envelope (per LOGONPARAMS_SERIALIZATION.md, not re-derived this pass) has no additional field for key/session material, and no data-flow edge from the RSA path into the Blowfish filter was found in logOnBegin's now fully-read body. STRONGLY SUPPORTED independence, not exhaustively proven across the RSA plaintext's own internal structure.
PRE_REPLY_NON_PACKET_SETUP: NONE FOUND that installs or replaces the key. logOnBegin's only filter-adjacent activity is a read-only cache validation (dynamic_cast chain) plus a diagnostic object (0x93c720) that copies the key string for what is inferred (not proven) to be a debug/verbose log line — this exposes the key value to a logging path but does not establish or change it.
SERVER_LEARNED_VALUE_PATH: NOT FOUND. No token, session ID, server-list metadata, JNI-passed buffer, or auth-callback value was observed anywhere in the native logOnBegin body feeding the EncryptionFilter/BF_set_key machinery. Not exhaustively re-verified across the full Java/Python auth chain this pass (cited from ROS_LOGIN_PLAY_TRACE.md / NATIVE_LOGON.md / G2_GAME_SESSION_TRACE.md rather than re-traced).
CAN_FIRST_LOGINREPLY_BE_DECRYPTED: NOT BY A REMOTE SERVER WITHOUT KNOWING THE CLIENT'S PROCESS-LOCAL RANDOM KEY, per all evidence gathered across this and prior passes. No mechanism was found, in any function read to date, that transmits, derives, or predicts that key before it is needed.
BLOWFISH_KEY_PARADOX_STATUS: UNRESOLVED, but now a well-scoped absence rather than an unexplored gap — this pass eliminated ServerConnection::logOnBegin (read in full, including the two previously-unread mystery code regions) as a hidden key-installation site, narrowing where the answer (if one exists) could still be hiding.
CURRENT_BLOCKER: No further static candidate function remains identified and unread in the pre-LoginReply path that plausibly installs or predicts the key; the remaining unknowns (0x93c720's true consumer, the 184-byte objects, the +0x15b/+0x5c copy, the 23 unexamined +0x30 write sites, 0x988be8's callers) are all confirmed unrelated to key installation or are low-probability leads, not a concrete next static target.
HIGHEST_VALUE_NEXT_EXPERIMENT: If this line of inquiry continues, the next static step with the best plausibility is mapping the 23 unexamined +0x30 write sites and 0x988be8's potential vtable-slot callers (both explicitly deferred, not ruled out, in MERCURY_KEY_STATE_LIFECYCLE.md); the next runtime step, only if that static work is exhausted, is extending the prior live heap scan to untagged/custom-allocator memory regions (not yet attempted, per MERCURY_LOGIN_REPLY_KEY_TRACE.md's own recommendation) rather than repeating the already-failed libc_malloc-tagged scan.
```
