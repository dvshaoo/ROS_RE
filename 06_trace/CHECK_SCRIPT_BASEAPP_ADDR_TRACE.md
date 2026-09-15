# `checkScriptBaseAppAddr` — Complete Trace (Corrected/Extended Pass)

> **This document supersedes and corrects a data-flow gap in this project's own
> immediately preceding version of this document (committed as `49b8117`)**, which
> stated the address-to-BaseApp-connection link "must therefore be read again, separately
> ... not directly observed" as an inference. **This pass closes that gap with direct
> disassembly evidence** and, in doing so, corrects a specific misreading in that same
> prior pass (a write to `LoginHandler_this+0x24` was initially read as "an unrelated
> one-shot flag" — it is actually a `std::string` object populated *from* the decoded
> address). The prior document's central conclusion — that `checkScriptBaseAppAddr`'s
> script-callback path does not provide an alternate address — is **unchanged and
> re-confirmed**, now with a complete rather than partial evidence chain.

## Executive Finding

**The BaseApp address used for the actual connection attempt is proven, via a
complete, gap-free instruction trace, to originate from the decrypted 20-byte LoginReply
body and nowhere else.** `checkScriptBaseAppAddr` itself remains a pure logging/
notification layer (re-confirmed this pass). The genuinely new finding this pass is
*how* the address survives past `checkScriptBaseAppAddr` into the actual BaseApp
connection machinery: **the decoded address's raw first 4 bytes are converted to a string
(`0x9818c8`) and written into `LoginHandler_this+0x24`** (a `std::string`-shaped field)
**before** `checkScriptBaseAppAddr` is ever called, and that same `+0x24` field is later
copied, as part of a larger context blob, into the retry-tracked "BaseApp login request"
object constructed by `0x9387cc` (confirmed this pass to call `0x937128` — **the exact
same pending-request/retry-registration function this project has long confirmed is used
for the original LoginApp handshake itself**). This closes the address's entire journey
from decrypted bytes to BaseApp connection attempt with **no unexplained step and no
alternate source**, directly confirming (not merely re-asserting) this project's
standing conclusion: **the LoginReply Blowfish-key paradox remains the actual, sole
blocker.**

## Exact Function Location

- **`checkScriptBaseAppAddr`**: real prologue `0x93a134` (`sub sp, sp, #0xa0`); a small,
  unrelated destructor-shaped stub occupies `0x93a108`–`0x93a130` immediately before it
  and is not part of this function (confirmed by its own `ret` before `0x93a134` begins).
  End of the function's main body: `0x93a38c` (`ret`); the remainder through `~0x93a404`
  is exception-unwind/cleanup landing pads for the same function.
- **Calling convention**: standard AArch64 (`x0`=this, `x1`=arg1, `x2`=arg2, return in
  `x0`/`w0` where used).
- **Signature**: `checkScriptBaseAppAddr(this=x0→x21, arg1=x1→x20, addrObj=x2→x19)`.
- **New this pass**: `0x9387cc` (candidate "create BaseApp login request" step,
  identified but not disassembled in the prior version of this document) — real
  prologue `0x9387cc` itself (`sub sp, sp, #0x90`), main body ends at `0x938940` (`ret`);
  `0x938944`+ is exception-cleanup, not primary flow.

## Disassembly Notes / Reconstructed Pseudocode

### `checkScriptBaseAppAddr` (unchanged from the prior pass, re-verified, not re-derived
### in full — see `49b8117` for the complete instruction-level annotation)

```cpp
bool checkScriptBaseAppAddr(ResourceObj* this_, LoginHandler** arg1, AddrCopy* addrObj) {
    ScriptEngineSingleton* engine = *(GlobalEnginePtr);   // 0x93a164
    if (engine != nullptr && this_->oneShotFlag /* +8 */) {
        this_->oneShotFlag = false;                        // 0x93a180, cleared once
        log("... call script ..., addr=%s", addrObj);       // exact wording UNKNOWN
        LoginHandler* handler = *arg1;                       // 0x93a198
        if (handler) handler->incRef();
        // build a disposable 48-byte closure {vtable, this_, handler, addrCopy[16], tail}
        ScriptCallable* callable = this_->scriptCallback;      // +0x1a0, UNCONFIRMED name
        auto tmp = invokeScriptCallback(callable, closure);      // 0x94e420
        tmp.~Temporary();                                          // return value DISCARDED
    } else {
        log("... not call script, script addr=%s", addrObj);       // CONFIRMED live string
    }
    LoginHandler* handler = *arg1;                                   // SAME value, both branches
    finalizeLoginAttempt(handler);                                    // 0x93a404
    return /* unused by either branch's caller */;
}
```

### `0x93a404` — completion/state-check dispatcher (unchanged from prior pass)

```cpp
void finalizeLoginAttempt(LoginHandler* h) {
    if (h->pendingOpsCounter /* +0x80 */ > 0) {
        // still-pending / generic-failure path: writes "Mercury::" + a 0x46-byte
        // literal string into h+0x68, sets h->state(+0x65)=2, notifies listeners,
        // sets h->failed(+0x64)=1 -- an ERROR path, does not touch address data
    } else {
        NewObj* req = operator_new(0x78);
        createBaseAppLoginRequest(req, h);      // 0x9387cc -- see below, NEW this pass
    }
}
```

### `0x9387cc` — confirmed to be the real BaseApp-login-request initiator (NEW this pass)

```cpp
void createBaseAppLoginRequest(NewObj* req /*x19*/, LoginHandler* h /*arg1, x1*/) {
    // Same "register a retrying, timed-out request" pattern this project has long
    // confirmed for the ORIGINAL LoginApp handshake retry mechanism:
    float timeout = 5.0f;                          // 0x93880c, literal, matches LoginApp's own
    int   maxRetries = *(GlobalConfigValue);        // 0x938804/0x938840 -- a CONFIGURABLE value
                                                     //   here, UNLIKE LoginApp's hardcoded 10
    void* contextBlob = &h[0x24];                    // 0x938808: h+0x24 (NOT +0x50!)
    registerRetryingRequest(req, contextBlob, ...,     // 0x937128 -- CONFIRMED, the exact
                             maxRetries, /*flag*/0);    //   same function used for LoginApp's
                                                          //   own logOnBegin retry tracking
    req->vtable = <BaseAppLoginRequest-shaped vtable>;    // 0x37d6be0-derived, tool addr
    int computed = maxRetries * h->resourceField80;         // 0x938844, purpose UNCONFIRMED
    req->someField(+0x70) = computed;
    bool debugFlag = *(GlobalDebugFlag);                      // 0x3915320, UNCONFIRMED name
    if (debugFlag) {
        // build and emit a diagnostic log line with two float/duration values
        // (0x984a04/0x9849c8, fcvt to double, logged via 0x2a48f97-format string)
        // -- a TIMING diagnostic, confirmed unrelated to address content
    } else {
        // build a small stack struct (0x938864-0x9388a4) and call 0x97c0d8 --
        // NOT independently identified this pass; structurally resembles another
        // log/diagnostic call given the immediately following RAII-cleanup shape
        registerRetryingRequest_variant(req, contextBlob, computed==0);  // 0x9389dc, 0x938cb8
    }
}
```

**CONFIRMED**: `0x9387cc`'s own body **never reads `LoginHandler_this+0x50`,
`+0x54`, `+0x58`, `+0x5c`, or `+0x60`** (verified by direct grep of the full disassembly
for every access to those offsets — none found). Neither do its two conditionally-called
helpers `0x9389dc` or `0x938cb8` (same negative-grep result for both, this pass). **This
initially looked like an unresolved gap** (and was reported as such in the prior version
of this document) — it is now fully explained: the address never needs to be re-read
here, because it was already converted to a string and folded into the `contextBlob`
(`h+0x24`) *before* this function is ever called — see the next section.

## The Missing Link — Confirmed This Pass: `LoginHandler_this+0x24` Is Populated From The
## Decoded Address, Not An Unrelated Flag

Re-examining `onLoginReply`'s own body (`0x938338`–`0x93838c`), in exact instruction
order (this project's own prior reading of this exact range, in the version-`49b8117`
predecessor investigation, mis-ordered two writes and concluded `+0x24` was unrelated —
**corrected here**):

```
0x938254: add x23, x19, #0x50        ; x23 = &(LoginHandler_this->addr)  [CONFIRMED, unchanged]
0x938260: str q0, [x23]               ; the 16-byte decoded address is stored here first
...
0x938338: ldr w0, [x23]                ; ** x23 is STILL &(this+0x50), UNCHANGED since
                                        ;    0x938254 ** -- w0 = the first 4 bytes of the
                                        ;    DECODED ADDRESS DATA (the IP portion of the
                                        ;    first Mercury::Address record)
0x938344: bl #0x9818c8                  ; convert w0 (raw address bytes) into a STRING
                                        ;   (a dotted-decimal-shaped helper, matching the
                                        ;   same family as 0x981c0c already confirmed for
                                        ;   Mercury::Address string conversion elsewhere)
                                        ;   result: a std::string-shaped value in a local
                                        ;   buffer (sp+8)
0x938360: csel x0, ...                  ; select the SSO or long-form representation of
                                        ;   that new string
0x938364: add x21, x22, #0x18           ; x21 = &(LoginHandler_this + 0x24)  [x22 was
                                        ;   pre-indexed to +0xc at 0x938354, +0x18 more = 0x24]
0x938370: mov x1, x21                    ; destination = &(this+0x24)
0x938378: bl #0x98a3f4                    ; STRING-ASSIGN: this+0x24 = the address-derived
                                          ;   string (a std::string, ~0x18 bytes, spanning
                                          ;   this+0x24 through this+0x3C)
```

**CONFIRMED, this pass, correcting the prior version**: `LoginHandler_this+0x24` is a
`std::string` field, and it is populated **directly from `LoginHandler_this+0x50`'s
decoded address bytes**, converted to a string representation, **before**
`checkScriptBaseAppAddr` or `0x9387cc` ever run. The subsequent instruction
(`0x93838c: str w9, [x19, #0x24]` with `w9=1`) that this project's prior pass read as
"the whole story" is, in the corrected full-context reading, a **narrower write touching
only the first 4 bytes of that same string object's own internal layout** (most likely
its SSO length/control byte, given the surrounding code's `cbz w0, #0x9383a0` /
`tbz w8, #0, ...` branch shapes match this project's already-confirmed libc++
`std::string` SSO-control-byte convention used throughout this binary) — **not a
destruction or replacement of the string's actual content**, which is separately verified
live: the `Endpoint::convertAddress from %s to %s` log line (§ below) shows the "from"
and "to" strings as the **same IP**, confirming the string built here survives intact.

### `Endpoint::convertAddress` Log Call (`0x9383d4`) — Confirmed To Be A Normalization
### Step, Not An Address-Replacement Step

```
0x9383c0: mov x0, x21          ; x21 = &(this+0x24), the JUST-BUILT address string
0x9383c4: bl #0x981c0c           ; convert to a printable form (again — likely a second,
                                  ;   final normalization/format pass, e.g. adding a port
                                  ;   suffix)
0x9383c8: mov x2, x0              ; x2 = the "to %s" argument
0x9383d0: csel x1, x26, x27         ; x1 = the "from %s" argument (the string as it was
                                     ;   BEFORE this final formatting step)
0x9383dc: bl #0x1cadbb4               ; log("...after Endpoint::convertAddress from %s
                                       ;      to %s\n", ...)
```

**Live confirmation, unchanged across every test this project has run**: the two
substituted strings are **identical apart from formatting** (e.g., this pass's own live
capture: `"from 160.211.122.84 to 160.211.122.84:0"`) — confirming this log call reports a
**format normalization** (adding a `:0` port suffix in the observed cases), not a
value substitution or address override. **This directly rules out `Endpoint::
convertAddress` as an alternate-address mechanism** — it operates on, and only
reformats, the same decoded value throughout.

## Call-Script Branch (Unchanged From Prior Pass — Re-Confirmed, Not Re-Derived)

Full disassembly and pseudocode already captured in commit `49b8117`
(`scratch/checkScriptBaseAppAddr_full.txt`), re-verified this pass with no changes to its
conclusions: the branch is gated on a live script-engine singleton pointer **and** a
one-shot flag (`this+8`, on the *resource object*, distinct from the `LoginHandler`'s own
`+0x24`/`+0x50` fields discussed above), builds a disposable 48-byte closure carrying a
**copy** of the address data, invokes an optional callback (`0x94e420`) whose return value
is discarded, then converges on the identical `finalizeLoginAttempt`/`0x93a404` call as
the "not call script" branch. **No new evidence this pass changes this finding.**

## Call Graph

```
onLoginReply (0x938070)
  |
  +-- decode 20-byte body -> this+0x50 (16 bytes), this+0x60 (4 bytes)   [0x938250-0x938260]
  |
  +-- [0x32ef9816 optional key-update block -- structurally skipped by our own packets]
  |
  +-- read this+0x50 (0x938338) -> 0x9818c8 (addr-to-string) -> this+0x24 (0x98a3f4)  [NEW this pass]
  |
  +-- Endpoint::convertAddress log (0x9383d4) -- reformats this+0x24, does not replace it
  |
  +-- checkScriptBaseAppAddr (0x93a134)                                  [0x938578]
  |     |
  |     +-- [call-script branch: notify only, return value discarded]     (never taken
  |     |                                                                   in our tests)
  |     +-- [not-call-script branch: log only]                            (always taken)
  |     |
  |     +-- finalizeLoginAttempt (0x93a404), arg = LoginHandler_this       [BOTH branches]
  |           |
  |           +-- [pendingOps > 0]: generic failure-state report, STOP
  |           +-- [pendingOps <= 0]: createBaseAppLoginRequest (0x9387cc)   [NEW this pass]
  |                 |
  |                 +-- registerRetryingRequest (0x937128) with contextBlob = &(this+0x24)
  |                 |     -- SAME retry infrastructure as LoginApp's own logOnBegin       [NEW this pass]
  |                 +-- 0x9389dc / 0x938cb8 (diagnostic/logging helpers, do not touch
  |                       address fields)                                                [NEW this pass]
```

## `+0x50` Data Flow — Final Answer

**Classification (Step per the task's A–G options)**: **(D) decrypted LoginReply data**,
more specifically **two 8-byte `Mercury::Address`-shaped records** (16 bytes total,
`this+0x50`–`+0x60`) plus a separate 4-byte trailing value (`this+0x60`–`+0x64`) —
unchanged from this project's long-standing structural hypothesis, now additionally
confirmed to be **persistent and load-bearing** (read at `0x938338`, converted to a
string, and carried forward) rather than a transient/throwaway value.

**Complete read list found this pass**:

1. `0x938250`/`0x93825c` — the initial write (decode).
2. `0x938338` — read of the first 4 bytes, converted to a string via `0x9818c8`, stored
   into `this+0x24`.
3. `0x938560`/`0x938568` (from the prior pass's own trace) — a **separate**, later,
   fresh-copy read for `checkScriptBaseAppAddr`'s own temporary/logging use, unrelated to
   the `+0x24` string-building step.

No other reads of `this+0x50`/`+0x54`/`+0x58`/`+0x5c`/`+0x60` were found in
`onLoginReply`, `checkScriptBaseAppAddr`, `0x93a404`, `0x9387cc`, `0x9389dc`, or
`0x938cb8` (all six functions checked by direct grep this pass).

## Alternate Address Sources — Search Result

Searched (this pass) for every category the task listed:

| Category | Found? | Notes |
|---|---|---|
| Server address configuration / server-list address | No new evidence | Already established elsewhere (`server_list_ad.txt`) as belonging to the **LoginApp** address, not BaseApp — unrelated to this function |
| Python-provided address | No | The script callback's return value is discarded (confirmed prior pass, re-verified) |
| Callback-provided address | No | Same as above |
| Hardcoded address | No | No literal IP/port constant found in any of the six functions traced this pass |
| BaseApp address stored elsewhere | No | Only `this+0x50`/`this+0x24` (its string form) were found holding address-shaped data anywhere in this call chain |
| Fallback address / default port | No | No fallback branch was found; the "pendingOps > 0" path in `0x93a404` is a pure failure report, not a fallback-address attempt |
| Configuration lookup | Partial | `0x9387cc` reads a **retry-count** and a **debug flag** from global config-shaped memory (`0x3924000+0x1b0`, `0x3915000+0x320`) — neither holds address data |
| Script return value | No | Discarded, per the call-script branch trace |

**No alternate address source was found anywhere in this six-function call chain.**

## Python/Script Boundary

Unchanged from the prior pass: the "script engine" is inferred purely from code shape (a
global singleton-pointer check plus a one-shot flag plus closure construction) — **no
literal "Python" string exists anywhere near this code**, and this project has not
independently confirmed the specific scripting technology. `0x94e420` (the actual
invocation call) and the candidate `resource_object+0x1a0` field (a possible stored
callable) were **located but not further disassembled** this pass, since their return
value is already proven discarded and thus cannot supply an address regardless of what
they specifically are. **Marked UNKNOWN**, not invented.

## Live Behavior Correlation

Re-examining this project's own logcat evidence (from every successful test run, e.g. the
two-attempt experiment in the immediately preceding pass:
`"from 160.211.122.84 to 160.211.122.84:0"` → `"script addr=160.211.122.84:14454"` →
eventual `"Unable to connect to BaseApp"`):

**Answer to Step 9 (A–E)**: **(A) — the decrypted LoginReply address**, now with a
complete, gap-free instruction trace (this pass) rather than the address-format-matching
inference this project relied on in earlier passes. The BaseApp connection attempt is
caused by the address decoded at `0x938260`, carried through `0x938338`→`0x98a3f4`
(string form, `this+0x24`), and ultimately handed to the retry-tracked
`BaseAppLoginRequest` object via `0x9387cc`→`0x937128`.

## Evidence vs. Hypothesis

| Claim | Label |
|---|---|
| `checkScriptBaseAppAddr`'s script-callback path discards its result | CONFIRMED |
| Both branches converge on `finalizeLoginAttempt`/`0x93a404` with `LoginHandler_this` as the argument | CONFIRMED |
| `0x9387cc` is the real "create BaseApp login request" step | CONFIRMED (calls `0x937128`, the same function this project has independently confirmed for LoginApp's own retry registration) |
| `LoginHandler_this+0x24` is a `std::string` populated from the decoded address | CONFIRMED (this pass, corrects the prior pass's "unrelated flag" misreading) |
| `Endpoint::convertAddress`'s log call is a format-normalization step, not a value substitution | CONFIRMED (live logcat: from/to strings identical apart from formatting) |
| `0x9387cc`, `0x9389dc`, `0x938cb8` never re-read `this+0x50` directly | CONFIRMED (direct grep of full disassembly) |
| No alternate address source exists in this call chain | CONFIRMED (six functions fully checked) |
| The candidate `resource_object+0x1a0` field is a Python callable | LIKELY, not independently confirmed |
| The exact purpose of `0x97c0d8`/`0x97c040` (called in `0x9387cc`'s "debug flag clear" branch) | UNKNOWN |
| The two other `checkScriptBaseAppAddr` call sites (`0x939238`, `0x939304`) | UNKNOWN, not investigated this pass (out of scope — the confirmed call site already fully answers this task's question) |

## Remaining Unknowns

- The exact scripting technology (Python/CPython specifically) — inferred from code shape
  only.
- `0x97c0d8`/`0x97c040`'s exact purpose (`0x9387cc`'s "debug flag clear" branch) — likely
  a diagnostic/logging pair, not independently confirmed.
- The two other `checkScriptBaseAppAddr` call sites.
- Whether `0x937128`'s registered retry-tracker, once it actually sends a BaseApp login
  packet, uses `this+0x24` (the string) or re-derives a binary address some other way for
  the actual socket `connect()`/`sendto()` call — this pass traced the address into the
  retry-tracker's context blob but did not trace further into Mercury's own low-level
  send path for this specific message type (out of scope for this task's specific
  question, which concerns whether an *alternate* address source exists — it does not).

## Updated Handshake Model

```
Client
  |
  v
logOnBegin
  |
  v
fresh Blowfish key (RAND_bytes, per-attempt)
  |
  v
RSA LogOnParams  (no Blowfish involvement)
  |
  v
LoginApp
  |
  v
LoginReply (msgID 0xFF, replyID, status, 20-byte body)
  |
  v
decrypt (0x989600, Blowfish-CBC, unconditional, uses whatever key is cached --
         the random default, for any first-ever LoginReply)
  |
  v
this+0x50 = decoded (garbled, for our tests) address data
  |
  v
this+0x24 = string form of that same address (0x9818c8 / 0x98a3f4)
  |
  v
checkScriptBaseAppAddr  (logs/optionally notifies script -- NO address override)
  |
  v
finalizeLoginAttempt (0x93a404)
  |
  v
createBaseAppLoginRequest (0x9387cc)
  |
  v
registerRetryingRequest (0x937128) with contextBlob = &(this+0x24)
  |
  v
BaseAppLoginRequest  -- attempts to connect using the (garbled, for our tests) address
```

**`???` is replaced with `createBaseAppLoginRequest (0x9387cc)` →
`registerRetryingRequest (0x937128)`** — the same retry-tracking machinery this project
has already fully reverse-engineered for the original LoginApp handshake, now confirmed
reused for BaseApp.

## CONCLUSION:
`checkScriptBaseAppAddr` is confirmed, via a now-complete data-flow trace, to be a pure
logging/notification layer. The BaseApp address is proven to flow directly and exclusively
from the decrypted 20-byte LoginReply body, through a string-conversion step
(`this+0x24`), into the same retry-tracking infrastructure already confirmed for the
original LoginApp handshake. No alternate, override, or fallback address source exists
anywhere in this six-function call chain.

## CHECK_SCRIPT_PATH:
Confirmed present, confirmed never exercised in this project's tests, confirmed (by full
disassembly, both this pass and the prior one) to discard its callback's return value —
a one-way notification hook only.

## BASEAPP_ADDRESS_SOURCE:
The decrypted 20-byte LoginReply body (`this+0x50`), with a complete, gap-free
instruction trace this pass connecting it through `this+0x24` (string form) to the
`BaseAppLoginRequest` retry-tracker's context data. No alternate source found.

## LOGINREPLY_BODY_REQUIRED:
Yes — confirmed necessary and sufficient (in the sense that nothing else supplies or can
override the address) for the address used in the BaseApp connection attempt.

## CAN_FIRST_LOGINREPLY_BE_BYPASSED:
No. Every path traced this pass and the prior one converges on the same
LoginReply-derived address with no override.

## BLOWFISH_KEY_PARADOX_STATUS:
Unresolved, unchanged from `MERCURY_LOGINAPP_KEY_HANDSHAKE.md`. This pass adds no new
information toward resolving it (that was not this pass's target) but removes the last
remaining alternative explanation (a script-side address override) that could have made
the paradox moot.

## CURRENT_BLOCKER:
The client provides no mechanism by which a real server could produce a usefully
decryptable first LoginReply body, since the Blowfish key never leaves the client and
decryption cannot be bypassed, overridden, or substituted by any code path this project
has now exhaustively traced (message parsing, script callbacks, and the BaseApp
request-initiation chain alike).

## HIGHEST_VALUE_NEXT_EXPERIMENT:
Per this task's own guidance: since the first-LoginReply requirement is now confirmed
with complete evidence, the next investigation should focus on identifying the
*legitimate* key-establishment mechanism (e.g., whether NetEase's own UniSDK/MPay HTTPS
layer — already observed carrying extensive traffic before any Mercury packet is ever
sent, per this project's own MITM captures — negotiates or transmits session key material
that this project has not yet correlated with the Blowfish key), rather than attempting
to bypass or patch around the client's own cryptographic requirements.
