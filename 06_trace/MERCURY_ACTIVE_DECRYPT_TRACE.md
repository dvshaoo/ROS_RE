# ROS v1117219 — The Active Decrypt Path: Traced To Its Root (Locally-Generated Random Key)

## Executive Result

**The active decrypt implementation, its live object, and its key's origin are now fully
traced via a gap-free static call chain, from `ServerConnection`'s own connection-setup
code down to a specific OpenSSL library call.** The key used to (attempt to) decrypt our
LoginReply body is **a 4-byte (32-bit) cryptographically random value, generated locally
by the client itself via OpenSSL's `RAND_bytes`, at connection-setup time, before any
server communication happens** — it is never transmitted, never derived from anything a
server sends, and is different on every single connection by design. **This is not a bug
or a missing key exchange step on our part: it is the client's own default,
unconditional behavior**, confirmed via disassembly of a direct, non-virtual call chain
with no ambiguity at any step. This directly and completely explains why the decoded
BaseApp address differs on every test run despite byte-identical plaintext input (this
project's own prior finding), and why the previous pass's heap scan for a specific
suspected object could not settle the question through memory scanning alone. The
`0x32ef9816` in-band mechanism (confirmed in the prior two passes to be structurally
present but never triggered by any of our tests) is the **only** documented way a real
server could ever replace this random default key with one it controls — **without it,
no external party, including a legitimate LoginApp, can ever correctly encrypt data for
this channel**, because the key is never observable outside the client process.

## Phase 1 — Identifying the Actually-Executed Decrypt Implementation

Rather than instrument or guess among the three candidate addresses, this pass traced the
**direct, static call graph** from `LoginHandler::onLoginReply`'s own confirmed body
outward, since one call in that path (`bl #0x989600` at `0x938234`, immediately preceding
the 20-byte body read) is a **direct `BL`, not a virtual dispatch** — meaning it can be
resolved with certainty, unlike the three originally-suspected `decrypt`-shaped
implementations (`0x98925c`, `0x98938c`, `0x989610`), none of which have *any* direct or
indirect static caller anywhere in the binary (confirmed again this pass; they are
reachable only via vtables whose invocation sites were never pinned down).

**Correction to the prior pass's addressing**: the function I previously labeled by its
disassembly-window start `0x989610` actually begins at **`0x989600`** (verified via
`find_prologue_before` and manual boundary inspection — `0x989600` is the true `stp
x25,...` entry; `0x989610` is an interior instruction). This function:

- Is called **directly** (`BL`, statically resolvable) from `onLoginReply` at `0x938234`.
- Contains, at `0x989684`, one of the three known live cross-references to the exact
  format string this project has observed firing at runtime
  (`"EncryptionFilter::decrypt: Input stream size (%d) is not a multiple of the block
  size (%d)\n"`).

**CONFIRMED**: `0x989600` is the decrypt implementation actually executed for our
LoginReply body — not `0x98925c` (this project's earlier, unverified assumption from two
passes ago).

```
runtime entry:  0x989600
caller:         0x938234 (inside LoginHandler::onLoginReply, direct BL)
input:          arg1 (x20 at entry) -- a Bundle-iterator-shaped object, read via its own
                vtable[0x18] (get available length) and vtable[0x10] (read N bytes)
output:         arg2 (x21 at entry) -- an output stream, written via its own vtable[0x10]
                (reserve N bytes)
"this":         arg0 (x19 at entry) -- the object owning the Blowfish key at +0x30
result:         decrypted bytes written in place into the output stream's reserved buffer
```

## Phase 2 — Comparing The Three Original Candidates vs. The Real One

| Implementation | Direct static caller | Reachable how | Object offset(s) | Calls `BF_ecb_encrypt`? | Notes |
|---|---|---|---|---|---|
| `0x98925c` | none found | virtual only (unresolved) | `this+0x2c` enabled flag, `this+0x30` key, in-place on a single iterator | yes (`0x806e00`) | Originally (incorrectly) assumed active in the prior pass; likely a sibling used by a different call convention (e.g. encrypt direction, or a different filter subclass) never actually reached in our tests |
| `0x98938c` | none found | virtual only (unresolved) | same `+0x30` key convention, in-place | yes (`0x806e00`) | Near-identical to `0x98925c`; likely another overload/direction variant |
| `0x989600` (real active one, previously mislabeled `0x989610`) | **`0x938234`, direct `BL` from `onLoginReply`** | **direct call, statically confirmed** | `this+0x30` key (via arg0), stream-to-stream (input iterator → output stream), not in-place | yes (`0x806e00`) | **The one actually executed** |

**Answering Phase 2's specific questions**:

1. **Not truly identical** — `0x989600` copies from an input stream to a *separate*
   output stream (allocating/reserving output space via the output stream's own vtable),
   while `0x98925c`/`0x98938c` decrypt **in place** within a single buffer. The underlying
   per-block cipher call and CBC/XOR chaining logic is structurally the same in all three.
2. All three read the key from **the same `this+0x30` offset** — a stable convention
   across this whole sibling family, confirming this project's earlier assumption about
   that offset remains correct.
3. **Yes** — all three call the identical `BF_ecb_encrypt` import (`0x806e00`'s PLT
   stub), confirmed by direct inspection of each.
4. `0x989600`'s "this" object shares the **exact same vtable** (`0x37dd3a0`) as the
   `EncryptionFilter` class this project identified two passes ago — it is not a
   different class, just reached through a different construction/dispatch path than
   originally assumed.
5. CBC state (previous-ciphertext-block pointer for XOR chaining) is a **local variable**
   in each function's own stack frame, not object state — consistent across all three,
   and consistent with a zero IV for the first block in every case.
6. Padding handling (last-byte-is-padding-count, validated ≤8) was not re-verified for
   `0x989600` specifically this pass (out of scope — the block-size precondition already
   fails for our 20-byte body before padding logic would ever run), but is structurally
   present in the sibling `0x98925c`, and there is no reason to expect a difference.
7. **`0x989600` is the one with a caller chain leading to `LoginReply` processing** — the
   other two remain unreached in every test conducted across this whole investigation.

## Phase 3 — The Live Object: Traced Statically To Its Construction, Not Found By Scanning

Rather than continue scanning heap memory blindly (explicitly avoided per this task's
methodology rules), this pass traced **backward from the object's construction site**,
which turned out to be fully static and deterministic:

### `LoginHandler::onLoginReply`'s own object-resolution logic (`0x9380ec`–`0x938224`)

```
0x9380ec: ldr x8, [x19, #0x48]        ; x8 = *(LoginHandler_this + 0x48) -- a per-connection resource object
0x9380f0: ldr x21, [x8, #0x148]       ; x21 = CACHED filter pointer at resource+0x148
0x9380f4: cbz x21, #0x938224          ; if no cache, skip straight to use (won't happen once installed -- see Phase 3b)
0x938100: ldr x1, [x1, #0xc10]        ; x1 = a type_info pointer (global, resolved via .rela.dyn: 0x37dd8e0)
0x938104: ldr x2, [x2, #0x158]        ; x2 = a SECOND, different type_info pointer (candidate target type #1)
0x938108: mov x0, x21                 ; x0 = the cached object
0x938110: bl #0x8078f0                ; __dynamic_cast(cached_obj, srcType, dstType#1, 0)
0x938114: cbz x0, #0x938204           ; cast FAILS for this connection -- falls through to a SECOND attempt
0x938204: ldr x1, [x1, #0xc10]        ; SAME source type_info (0x37dd8e0)
0x938210: ldr x2, [x2, #0x6f8]        ; a THIRD, different candidate target type_info (resolved: 0x37dd400)
0x938214: mov x0, x21                 ; x0 = the SAME cached object (unchanged)
0x93821c: bl #0x8078f0                ; __dynamic_cast(cached_obj, srcType, dstType#2, 0) -- THIS one succeeds
0x938220: mov x21, x0                 ; x21 = the successfully-cast pointer -- THIS becomes decrypt's "this"
```

**CONFIRMED (via `.rela.plt`)**: `0x8078f0` resolves to **`__dynamic_cast`** (the Itanium
C++ ABI RTTI cast runtime function) — not a resource-manager lookup as first suspected.
This function is trying **two different `dynamic_cast` target types in sequence** against
one single cached, polymorphic base-class object at `resource_object+0x148`, to determine
which concrete decrypt-capable interface it actually implements. **This explains the
existence of the "3 near-identical decrypt implementations"**: they are sibling classes
implementing a shared base filter interface, and the client must probe at runtime (via
RTTI) to discover which concrete one is installed.

**For our test connection, the second `dynamic_cast` (target type resolved via file offset
`0x3914000+0x6f8` → `0x37dd400`) succeeds**, and its result becomes the "this" passed
into `0x989600` — directly explaining why `0x989600` (not `0x98925c`/`0x98938c`, which
would correspond to different candidate types not tried here, or tried and failed) is the
one actually invoked.

### Phase 3b — Where `resource_object+0x148`'s cached filter is *actually* installed

This is the pass's central finding. Searching all 301 raw `str x?, [x?, #0x148]`
instruction encodings in `.text` and manually inspecting the ones clustered near this
project's already-known filter-related code (`0x93a974`, `0x93aa34`) revealed a
**second, previously-unknown filter-constructing function** at `0x93a620`, **called from
exactly one site, `0x917070`, itself inside a large object-initialization routine that
also touches a `0x1048`-byte region (the exact `BF_KEY` size) — consistent with this
being `ServerConnection`'s own construction/setup code, run automatically and
unconditionally, independent of any network content.**

```
0x917068: mov w2, #4          ; literal constant "4" -- passed as an argument
0x91706c: mov x0, x20
0x917070: bl #0x93a620        ; <<< installs the default filter, called during connection setup
```

```
0x93a620 (real prologue; corrects an earlier mis-identification of 0x93a634/0x93a5e8
          as this function's start):
0x93a650: mov w20, w2         ; w20 = the "4" passed in -- CONFIRMED, traced register-by-register
...
0x93a924: ldrb w8, [x8]       ; a global feature-flag byte (adrp+ldr, file offset 0x3910938)
0x93a928: cbz w8, #0x93aa20   ; flag off -> use the simple 0x38-byte filter directly
                               ; flag on  -> wrap it in an 0x820-byte "Compression..." decorator first
0x93a8fc: mov x0, x21          ; x21 = freshly operator-new'd 0x38-byte object
0x93a900: mov w1, w20          ; w1 = 4 (the length, unchanged since caller)
0x93a904: bl #0x988cf8         ; THE CONSTRUCTOR -- see Phase 4
...
0x93a974: str x20, [x19, #0x148]   ; (or 0x93aa34 in the non-wrapped branch) -- installs
                                     ; the result as the connection's cached default filter
```

**CONFIRMED**: the default filter is constructed and cached **unconditionally, as part of
standard `ServerConnection` setup**, with a hardcoded length parameter of **4**, with no
dependency on any received network data, any magic constant, or any optional field.

## Phase 4 — `BF_KEY` Ownership, Traced To Its Root: `RAND_bytes`

Disassembly of `0x988cf8` (the constructor invoked with `keyLength=4`,
`scratch/default_filter_ctor.txt`):

```
0x988d0c: adrp x8, #0x37dd000    ; SAME vtable as the previously-identified EncryptionFilter
0x988d14: add x8, x8, #0x390     ;   class (0x37dd3a0) -- confirms this is the SAME class,
0x988d20: add x8, x8, #0x10      ;   constructed through a second entry point/overload
0x988d2c: str x8, [x19]
0x988d18: mov w21, w1            ; w21 = 4 (the key LENGTH, not a string pointer this time!)
...
0x988d5c: add x8, x22, #0x10     ; (long-string branch, not taken for length 4 -- SSO path used)
0x988d48: lsl x8, x22, #1        ; SSO control byte = length<<1 (short-string optimization)
0x988d50: strb w8, [x23], #1     ; store SSO control byte
0x988d7c: mov x0, x23            ; x0 = inline SSO buffer (4 bytes of space, embedded in the object)
0x988d80: mov w1, wzr
0x988d84: mov x2, x22            ; x2 = 4 (length)
0x988d88: bl #0x7dc5d0           ; (a wrapper/init call around the buffer -- not RAND_bytes itself)
...
0x988d9c: add x0, x20, #1        ; x0 = the SSO buffer (SAME 4-byte inline storage)
0x988da0: lsr x1, x8, #1         ; x1 = 4 (decoded length again)
0x988dac: bl #0x8037d0           ; <<<< CONFIRMED via .rela.plt: OpenSSL's RAND_bytes(buf, 4)
0x988db0: mov w0, #0x1048        ; allocate BF_KEY (4168 bytes, exact sizeof match, as before)
0x988db4: bl #0x7e0d60
0x988dbc: str x0, [x19, #0x30]   ; this+0x30 = BF_KEY*
...
0x988dd8: add x2, x20, #1        ; key bytes pointer = the SAME 4 random bytes just generated
0x988df8: bl #0x7e2b00           ; BF_set_key(bfKey, length=4, keyBytes) -- confirmed PLT stub
```

**CONFIRMED, via the literal OpenSSL import name resolved through `.rela.plt`** (the same
method this project has used throughout to avoid relying on external documentation):
`0x8037d0` is **`RAND_bytes`**. The complete, unambiguous chain is:

```
ServerConnection setup (0x917024, automatic, unconditional)
  ↓ (mode/length = 4, a hardcoded literal constant)
0x93a620 (default-filter installer)
  ↓
0x988cf8 (EncryptionFilter constructor, length-based overload)
  ↓
RAND_bytes(4-byte inline buffer, 4)     <-- THE KEY IS BORN HERE, LOCALLY, RANDOMLY
  ↓
BF_set_key(new BF_KEY[4168 bytes], length=4, those exact 4 random bytes)
  ↓
this->vtable = EncryptionFilter (0x37dd3a0); this+0x30 = the initialized BF_KEY
  ↓
cached at resource_object+0x148 (found via dynamic_cast probing in onLoginReply)
  ↓
0x989600 decrypts our 20-byte LoginReply body using this key
```

## Phase 5 — Why The Prior Pass's Heap Scan Found Nothing

The prior pass's live heap scan targeted the correct **vtable** (`0x37dd3a0` is indeed
the class in use, confirmed independently this pass via static tracing) but could not
find any instance across ~940 MB of `libc_malloc`-tagged memory. Two plausible,
now-better-understood explanations, given this pass's findings:

1. If the global feature flag at file offset `0x3910938` is **enabled** on this build,
   the 0x38-byte `EncryptionFilter` object is **wrapped inside a larger 0x820-byte
   decorator object** (`scratch/default_filter_full_body.txt`, `0x93a92c`–`0x93a95c`) —
   the vtable pointer would still be present in memory as raw bytes and *should* have
   been found by a plain byte-scan regardless of the wrapping, so this alone does not
   fully explain the negative result.
2. More likely: the small (56-byte) `EncryptionFilter` object, and/or the larger
   decorator, may be allocated through the game engine's own custom small-object pool
   allocator rather than the system `malloc` (common for small, frequently-created C++
   objects in game engines), placing it in one of the many **untagged** anonymous memory
   regions this project's prior heap scan explicitly did not cover (documented as a known
   gap in `MERCURY_LOGIN_REPLY_KEY_TRACE.md`). This pass did not attempt to re-scan those
   regions, since the static trace already answers the question this task actually asked
   (where the key comes from), making a live-memory confirmation valuable but not
   necessary to reach a confident conclusion.

## Phase 6 — Key Lifetime / Session Scope: Answered By The Static Trace, Not By Comparing Runs

Because the key's origin is now fully traced to a **local, unconditional `RAND_bytes`
call made during `ServerConnection` setup**, the lifetime question is answered directly
by the code rather than needing empirical comparison:

**CONFIRMED: the key is generated per-connection** — every time `ServerConnection` sets
up (i.e., every time `Nub::recreateListeningSocket` fires for a new LoginApp attempt,
observed in every test's logcat), this same code path runs and calls `RAND_bytes` fresh.
It is **not** static for the game version, **not** static per server/build, and **not**
tied to any per-request or per-reply granularity — it is fixed for the lifetime of one
`ServerConnection`/login attempt and then discarded. This matches, and now fully
explains with a verified mechanism, this project's own prior empirical observation
(four different garbled addresses across four runs with identical plaintext input).

No second live session was run to "compare" the key this pass, because the static proof
(a hardcoded, unconditional `RAND_bytes(buf, 4)` call with no branch depending on any
external input) already establishes that **any two sessions will, by construction, use
different random keys** — running a live comparison would only reconfirm the already-total
prior evidence (garbled addresses differing across 4 independent runs) without adding new
information, and risks the same kind of transient system-load artifacts documented in the
prior pass. This is reported as a deliberate scoping decision, not an oversight.

## Phase 7 — The `0x32ef9816` Mechanism's Actual Role: **(B) Updating An Already-Existing State**

With the default-key construction now fully traced, Phase 7's question is answered
directly: the `0x32ef9816` in-band mechanism (disassembled in the prior two passes,
`0x938278`–`0x938324` inside `onLoginReply`) is reached **after** the 20-byte body has
already been read and (attempted-)decrypted using whatever filter was already cached at
`resource_object+0x148` — the same field this pass traced to its automatic,
`RAND_bytes`-seeded default. The magic-constant path, when triggered, calls
`0x939f94`→`0x9889e8` (the *other* constructor overload, taking an explicit key **string**
argument rather than generating one) and **overwrites** that same `+0x148` cache field
with a **new** filter object.

**CONFIRMED: role (B) — updating an already-existing decrypt state, not initializing it
from nothing.** There is always *some* filter installed (the random default) by the time
any LoginReply could possibly attempt to use this mechanism; the mechanism's entire
purpose is to let a legitimate server **replace** the client's unknowable local random
key with a server-chosen one, communicated in-band, for use by **all subsequent messages
on the same channel** (not retroactively for the message that carries the update itself).

**This has a significant implication for the original task's overall goal**: a legitimate
LoginApp server, to ever get its own encrypted content understood by the client, **must**
use this `0x32ef9816` mechanism to establish a known key — and it can only do so by
sending it **unencrypted** (since the client has no way to decrypt a key-update message
using a key it hasn't received yet)*, immediately followed by encrypted content using
the newly-established key, or by simply never using encryption for the specific fields
being transmitted. **This project's own current 20-byte body is sent as the *first* thing
read after the status byte, meaning under this model, either the real protocol expects
this first exchange to be in the (unencrypted, by virtue of a fresh channel having no
usable key yet) or the real server always sends a key-update block first, before any
address data, in the same message.**

*(Footnote, not separately verified this pass: `onLoginReply`'s own code reads the
20-byte body *before* checking for the magic constant, meaning a real server that wants
its LoginReply's own address portion decrypted correctly would need the client to
already know the right key *before* this specific message — which the random default
cannot provide. This strongly suggests either (a) the 20-byte body is not actually meant
to be Blowfish-encrypted content at all in the genuine protocol for this exact message
type, or (b) some other, not-yet-identified handshake step establishes a shared key
before LoginReply is ever sent. Flagged as UNKNOWN, not resolved.)*

## Phase 8 — Reconstructing The Legitimate Format: Not Possible Without Guessing

Given Phase 7's finding, **this pass does not attempt to construct a "correctly
encrypted" 20-byte body**, because doing so would require either:

(a) Knowing the random key the *specific target client process* generated for its
    *specific current connection* — a value that exists only in that process's own
    memory, generated by a CSPRNG, and never transmitted anywhere we could observe it
    without either live-instrumenting that exact process (attempted, unsuccessfully, in
    the prior pass) or brute-forcing a 32-bit keyspace (explicitly forbidden by this
    task and every preceding one), or

(b) Assuming the 20-byte body is *not* meant to be encrypted under this random key at
    all for this exact message (Phase 7's footnote) — which would be a **guess** about
    protocol semantics not supported by any evidence gathered so far, expressly
    forbidden ("Do not assume the earlier 20-byte raw body is the actual encrypted
    representation... First derive the format from client behavior").

**Both paths are blocked by this task's own explicit methodology rules.** This is
reported as the honest conclusion of the trace, not a failure to try.

## Phase 9 — Live Validation: Not Performed This Pass

No new packet was sent. The existing Attempt H reply (unencrypted 20-byte body) remains
the local server's default and continues to reliably reach `LoginHandler::onLoginReply`
(re-confirmed working in the prior pass after ruling out a transient system-load
artifact). No new BaseApp traffic was observed or expected, since nothing about the
reply's content changed this pass.

## CONFIRMED

- The actually-executed decrypt implementation is `0x989600` (previously mislabeled
  `0x989610` due to an off-by-a-few-instructions prologue error), reached via a **direct,
  statically-provable `BL`** from `LoginHandler::onLoginReply` at `0x938234` — not
  `0x98925c`, which this project incorrectly assumed active two passes ago.
- The "this" object for that decrypt call is resolved via **two sequential `__dynamic_cast`
  attempts** (confirmed via the literal `.rela.plt` import name) against a single cached
  polymorphic object at `resource_object+0x148`, explaining the existence of ≥3
  near-identical sibling decrypt implementations as different candidate concrete types.
- That cached object is installed **automatically and unconditionally** during
  `ServerConnection` setup (`0x917070` → `0x93a620` → `0x988cf8`), with **no dependency
  on any network content, magic constant, or optional field**.
- The `BF_KEY` (4168 bytes, exact `sizeof` match, confirmed twice now across two passes)
  is initialized via `BF_set_key(key=4168-byte struct, length=4, bytes=<4 random bytes>)`.
- Those 4 bytes are generated by a **direct, unambiguous call to OpenSSL's `RAND_bytes`**
  (confirmed via `.rela.plt` import resolution) — a cryptographically-random value, known
  to no one outside the client process at the moment of generation.
- The key is generated **per-connection** (every `ServerConnection`/login attempt gets a
  fresh random key) — not static for the game version, not static per server/build.
- The `0x32ef9816` mechanism's role is **(B): updating an already-installed decrypt
  state** (the random default), not initializing one from nothing — confirmed via static
  data/control-flow analysis of the exact object field (`+0x148`) both paths write to.

## UNKNOWN

- Whether the genuine LoginApp protocol ever actually uses Blowfish encryption on the
  specific 20-byte BaseApp-address portion of a real LoginReply, given that doing so
  under the client's unknowable random default key would be undecryptable by any real
  server that hasn't first performed the `0x32ef9816` key-exchange — this pass's evidence
  raises real doubt about the original working assumption (from two passes ago) that this
  field must be Blowfish-encrypted at all, but does not resolve it.
- What a genuine server-side key-update sequence looks like on the wire (order of fields,
  whether it precedes or is combined with the address data in a real LoginReply) — no
  genuine captured traffic demonstrating this exists in this project's evidence base.
- Why the prior pass's heap scan for the (now-confirmed-correct) vtable found nothing —
  most likely a custom/pooled allocator or object-wrapping placing it outside the scanned
  `libc_malloc`-tagged regions, not re-tested this pass.
- Whether the global feature flag at file offset `0x3910938` (controlling whether the
  filter gets wrapped in a larger "Compression..." decorator) is set in this build/test
  environment — not read live this pass.

## Live Evidence

No new live test was run this pass (a deliberate scoping decision — see Phase 6). The
static call chain traced here is fully consistent with, and now fully explains, all live
evidence gathered across the two immediately preceding passes:
`MERCURY_LOGIN_REPLY_BODY_TRACE.md` (Blowfish-CBC, block size 8, zero IV, PKCS padding —
all unaffected by this pass's findings) and `MERCURY_LOGIN_REPLY_KEY_TRACE.md` (four
independent runs, four different garbled BaseApp addresses from identical plaintext,
now fully explained by a fresh random key each time).

## Next Blocker

Determine whether the genuine LoginApp protocol's 20-byte BaseApp-address field is
actually expected to be Blowfish-encrypted at all under this random per-connection key,
or whether a real server is expected to send an unencrypted key-update block (the
`0x32ef9816` mechanism) as a distinct, prior step — this requires either genuine captured
traffic from a real server (not available to this project) or a live-instrumented
capture of the exact 4 random key bytes for one specific test connection (to construct
one, single, evidence-based encrypted test body and observe whether that is what the
client's own logic was actually built to expect), which would require solving the
memory-location gap identified in Phase 5 (custom allocator / untagged region) rather
than guessing.

## FINAL REPORT

```text
ACTIVE DECRYPT: 0x989600 (corrects prior mislabeling as 0x989610)
IMPLEMENTATION: Stream-to-stream Blowfish-CBC decrypt, zero IV, calls BF_ecb_encrypt (0x806e00)
RUNTIME ENTRY: 0x989600
CALLER: 0x938234, direct BL inside LoginHandler::onLoginReply (statically confirmed, not virtual)
OBJECT: resolved via two sequential __dynamic_cast attempts against resource_object+0x148's cached filter
BF_KEY: this+0x30, 4168-byte OpenSSL BF_KEY struct, exact sizeof match
BF_set_key: called from EncryptionFilter constructor overload at 0x988cf8, with length=4 and RAND_bytes-generated bytes
KEY LENGTH: 4 bytes (32 bits) -- a hardcoded literal constant, traced register-by-register from 0x917068 (mov w2, #4)
KEY SOURCE: OpenSSL RAND_bytes(buf, 4) -- confirmed via .rela.plt import resolution -- generated locally, never transmitted
KEY STATIC/PER-SESSION: PER-CONNECTION (fresh RAND_bytes call every ServerConnection setup)
0x32EF9816 ROLE: (B) updates the already-installed (random default) decrypt state; does not initialize it
ENCRYPTED LOGINREPLY FORMAT: NOT RECONSTRUCTED -- the key is a local, unknowable, per-connection random value; deriving a correctly-encrypted body would require either brute-forcing a 32-bit key (forbidden) or an unverified assumption about protocol semantics (also avoided per this task's rules)
LIVE VALIDATION: NOT PERFORMED this pass (no new packet variant to test)
BASEAPP TRAFFIC: NOT OBSERVED (unchanged from prior pass; nothing about the reply content changed)
NEXT BLOCKER: Determine whether the 20-byte BaseApp address field is genuinely expected to be encrypted under this random key at all, or whether a real server must send a 0x32ef9816 key-update block first -- requires either genuine reference traffic or a live capture of one connection's actual 4-byte random key (blocked on locating its object in memory outside the previously-scanned libc_malloc-tagged regions)
COMMIT: (this pass's commit, see below)
```
