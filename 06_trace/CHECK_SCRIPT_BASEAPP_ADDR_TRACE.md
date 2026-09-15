# `ServerConnection::checkScriptBaseAppAddr` — Complete Trace

## Executive Finding

**`checkScriptBaseAppAddr` is a notification/logging layer, not an alternate address
source.** Both its "call script" and "not call script" branches converge on the exact
same subsequent call (`0x93a404`, passing `LoginHandler_this` itself, not address data),
which in turn dispatches to what is very likely the real "create `BaseAppLoginRequest`"
step (`0x9387cc`). The optional Python-script callback, when a scripting layer is active
(never the case in this project's own test environment), receives a **temporary,
stack-local copy** of the decoded address purely for informational/extensibility
purposes — its return value is discarded (only used for C++ temporary-object cleanup, not
fed back into anything). **This directly and conclusively answers the task's central
question: there is no separate mechanism here that can provide or override the BaseApp
address.** The address actually used for the BaseApp connection is the one already
decoded from the 20-byte LoginReply body and stored at `LoginHandler_this+0x50` *before*
`checkScriptBaseAppAddr` is ever called — confirming, per this task's instruction #14,
that **the LoginReply key/encryption paradox documented in the immediately preceding pass
(`MERCURY_LOGINAPP_KEY_HANDSHAKE.md`) remains the actual, unresolved blocker.**

## Function Identification

- **Entry point (real prologue)**: `0x93a134` (`sub sp, sp, #0xa0`). A short helper
  destructor-shaped stub sits immediately before it (`0x93a108`–`0x93a130`, an unrelated
  small function, not part of `checkScriptBaseAppAddr` itself — confirmed by its own
  `ret` at `0x93a130` before the real prologue begins).
- **Confirmed via the exact log string this project has observed live**:
  `"ServerConnection::checkScriptBaseAppAddr not call script, script addr=%s\n"`
  (`0x2a49653`), with its one and only cross-reference at `0x93a230`, inside this
  function — matching this project's live logcat capture in every prior pass.
- **Signature** (recovered from register usage): `checkScriptBaseAppAddr(this=x0→x21,
  arg1=x1→x20, addrObj=x2→x19)`.
- **Three call sites** in the whole binary: `0x938578` (inside the confirmed
  `LoginHandler::onLoginReply`/`handleMessage` cluster — this is the one this project has
  directly observed firing live in every successful test), plus `0x939238` and
  `0x939304` (a different code region, not investigated this pass — see Unknowns).

## The Confirmed Call Site (`0x938578`, inside `onLoginReply`)

```
0x938544: ldr x0, [x19, #0x48]     ; x0 = *(LoginHandler_this+0x48) -- the shared
                                     ;   "resource object" this project has referenced
                                     ;   throughout (holds the cached EncryptionFilter
                                     ;   at +0x148) -- becomes checkScriptBaseAppAddr's
                                     ;   OWN "this"
0x93854c: str x19, [sp, #0x28]      ; sp+0x28 = LoginHandler_this (stored to the stack)
0x938560: ldr x8, [x21, #0x10]      ; x8 = a 4-byte-ish field from x21 (the ALREADY-
                                     ;   DECODED address data -- x21 here is the same
                                     ;   register holding LoginHandler_this+0x50-derived
                                     ;   data from earlier in onLoginReply)
0x938564: stur x8, [x29, #-0x60]    ; copy into a FRESH local stack variable
0x938568: ldr q0, [x21]              ; q0 = the 16-byte address data (SAME data already
                                     ;   stored at LoginHandler_this+0x50, per
                                     ;   LOGIN_REPLY_RECORD.md / MERCURY_LOGIN_REPLY_BODY
                                     ;   _TRACE.md)
0x93856c: stur q0, [x29, #-0x70]      ; copy 16 bytes into a fresh local (a TEMPORARY,
                                     ;   stack-local COPY, not a reference to +0x50 itself)
0x938570: add x1, sp, #0x28           ; arg1 = &(the just-stored LoginHandler_this pointer)
0x938574: sub x2, x29, #0x70            ; addrObj = &(the fresh local 24-byte copy)
0x938578: bl #0x93a134                    ; checkScriptBaseAppAddr(...)
```

**CONFIRMED**: `arg1` is a pointer-to-pointer whose target is `LoginHandler_this` itself
— **not** address data. `addrObj` (the third argument) points to a **freshly-made,
stack-local copy** of the 24 bytes (16+4+... see below) already resident at
`LoginHandler_this+0x50`/`+0x60`, made specifically for this call.

## Full Disassembly and Branch Structure (`0x93a134`–`0x93a41c`)

```
0x93a154: adrp x24, #0x390f000
0x93a164: ldr x24, [x24, #0x800]     ; x24 = a GLOBAL pointer (Python/script-engine
                                       ;   singleton reference)
0x93a16c: ldr x8, [x24]               ; dereference once more
0x93a170: cbz x8, #0x93a224           ; NULL -> "not call script" (this project's tests:
                                       ;   ALWAYS taken -- no scripting layer is active)
0x93a174: ldrb w8, [x21, #8]           ; this(+0x48 resource obj)+8 -- a one-shot flag
0x93a178: cbz w8, #0x93a224            ; clear -> also "not call script"
```

**Both conditions must hold** for the script-callback path to run at all: a live
script-engine singleton AND a per-connection one-shot flag. **CONFIRMED, not assumed**,
via every logcat capture this project has ever taken: this test environment (a bare
native APK with no active Python UI-scripting layer) always takes the "not call script"
branch — matching the literal log line `"not call script"` observed on every single run.

### Branch A — "Call Script" (`0x93a17c`–`0x93a220`, never exercised in this project's
### tests, but fully reversed statically)

```
0x93a17c: mov x0, x19                  ; x0 = addrObj (the temp copy)
0x93a180: strb wzr, [x21, #8]           ; clear the one-shot flag (never re-notify twice)
0x93a184: bl #0x981c0c                  ; address -> string (for logging)
0x93a194: bl #0x1cadbb4                  ; LOG the address (a DIFFERENT message than the
                                          ;   "not call script" branch's own log text --
                                          ;   not independently read this pass, flagged
                                          ;   UNKNOWN exact wording)
0x93a198: ldr x22, [x20]                 ; x22 = *(arg1) = LoginHandler_this
0x93a1a0-b0: refcount-increment on x22    ;   (LoginHandler_this is a refcounted object)

; --- build a callback/closure object (0x30 = 48 bytes) ---
0x93a1cc: bl #0x7e0d60                    ; operator new(0x30)
0x93a1e4: add x1, x21, #0x1a0               ; x1 = (resource_obj)+0x1a0 -- CANDIDATE: a
                                             ;   registered Python callable/PyObject* field
                                             ;   (not independently confirmed this pass)
0x93a1e8: stp x21, x22, [x0, #8]             ; new_obj+0x08 = resource_obj,
                                             ;   new_obj+0x10 = LoginHandler_this
0x93a1ec: str x8, [x0]                        ; new_obj+0x00 = a vtable (tool addr
                                             ;   0x37d7728 -- a distinct, small
                                             ;   closure/delegate class, not otherwise
                                             ;   identified this pass)
0x93a1f0: str x9, [x0, #0x28]                  ; new_obj+0x28 = the 4/8-byte tail field
0x93a1f4: stur q0, [x0, #0x18]                   ; new_obj+0x18..+0x28 = the 16-byte
                                                  ;   address data COPY
0x93a204: bl #0x94e420                             ; <<< THE ACTUAL SCRIPT-INVOKING CALL,
                                                    ;   args: (result_buf=sp+0x20,
                                                    ;   pyCallable=resource_obj+0x1a0,
                                                    ;   [closure obj implicitly available
                                                    ;   via the stack]) -- signature not
                                                    ;   fully resolved this pass
0x93a208-220: RAII cleanup of 0x94e420's return value (a temporary object/string) --
              standard C++ destructor dispatch, THE RETURN VALUE IS DISCARDED, never
              read for content, never assigned anywhere, never used to modify the
              address data or any LoginHandler field.
```

**CONFIRMED**: the script callback, if invoked, is handed a **copy** of the address data
wrapped in a throwaway closure object, purely so a registered Python callable can be
*informed* of the decoded address (an extensibility/observer hook — matching classic
BigWorld script-binding design, where native events are mirrored into Python for UI/game
logic to react to, e.g. displaying a "connecting to BaseApp..." message). **Its return
value is never consumed for anything beyond generic C++ temporary cleanup.** There is no
instruction anywhere in this branch that writes back into `LoginHandler_this+0x50`,
`+0x60`, or any other address-holding field.

### Branch B — "Not Call Script" (`0x93a224`–`0x938244`, the branch this project's tests
### always take)

```
0x93a224: mov x0, x19                  ; x0 = addrObj (same temp copy)
0x93a228: bl #0x981c0c                  ; address -> string
0x93a238: bl #0x1cadbb4                  ; LOG "not call script, script addr=%s"
                                          ;   (the exact string this project has observed
                                          ;   live in every test)
0x93a23c: ldr x0, [x20]                  ; x0 = *(arg1) = LoginHandler_this  -- IDENTICAL
                                          ;   value to Branch A's x22
0x93a240: bl #0x93a404                    ; IDENTICAL call to Branch A's own eventual
                                          ;   continuation
0x93a244: b #0x93a368                      ; join common cleanup/return
```

### Convergence — Both Branches Call The Same Next Step With The Same Argument

**CONFIRMED, the single most important structural fact in this trace**: after either
branch, execution reaches `bl #0x93a404` with **`x0 = LoginHandler_this`** in both cases
(Branch A via `x22`, Branch B via a fresh `ldr x0, [x20]` — both reading the exact same
`*(arg1)` value). **The address data itself is never passed to `0x93a404` at all** — only
the `LoginHandler` object is.

## `0x93a404` — Confirmed To Be A Completion/State-Check Function, Not An Address Consumer

```
0x93a410: mov x19, x0                  ; x19 = LoginHandler_this
0x93a414: ldr w8, [x19, #0x80]          ; w8 = *(this+0x80) -- a pending-operations
                                          ;   counter/flag (not independently named)
0x93a418: cmp w8, #0
0x93a41c: b.le #0x93a46c                 ; <=0 -> "proceed" path; >0 -> "still pending
                                          ;   /error" path
```

**"Still pending/error" path** (`w8 > 0`, `0x93a420`–`0x93a468`): writes a **generic
failure-state string** into `this+0x68` (the SAME `+0x64`/`+0x65`/`+0x68` state-reporting
convention this project has confirmed used for `REASON_CORRUPTED_PACKET` and other
failures elsewhere in this exact class), runs the same "notify registered listeners" loop
pattern seen throughout this project's prior work, and sets `+0x64=1` ("failed"). **This
branch does not touch address data at all.**

**"Proceed" path** (`w8 <= 0`, `0x93a46c`+): allocates a new `0x78`-byte (120-byte)
object and calls `bl #0x9387cc` with `x1 = LoginHandler_this`. Given this address's
numeric proximity to the already-confirmed `handleMessage`/`onLoginReply` cluster
(`0x938070`–`0x938724`) and the fact that this is the **only** remaining unexplored step
in the observed sequence before `Nub::recreateListeningSocket` fires for the BaseApp
connection (confirmed live in every prior pass's logcat, always appearing immediately
after `checkScriptBaseAppAddr`'s own log line), **`0x9387cc` is the strongest available
candidate for the actual "construct `BaseAppLoginRequest` / initiate BaseApp Nub setup"
step** — **not independently disassembled this pass** (out of scope for this task's
specific question, which is fully answered without it — see Unknowns).

## Data-Flow of `LoginHandler_this+0x50`

Combining this pass's findings with the already-confirmed decode step
(`MERCURY_LOGIN_REPLY_BODY_TRACE.md`, `0x93825c`/`0x938260`):

```
1. onLoginReply reads the 20-byte LoginReply body, Blowfish-decrypts it (0x989600),
   and stores it as 16 bytes (q0, this+0x50) + 4 bytes (this+0x60)   [CONFIRMED, prior pass]
2. onLoginReply later (0x938560-0x93856c) makes a FRESH STACK-LOCAL COPY of this same
   16+4/8 byte data, specifically for the checkScriptBaseAppAddr call               [CONFIRMED, this pass]
3. checkScriptBaseAppAddr operates ONLY on that temporary copy -- for logging (both
   branches) and, if a script layer is active, for one-way notification (Branch A only) [CONFIRMED, this pass]
4. Neither branch of checkScriptBaseAppAddr writes back to this+0x50/+0x60, or to any
   other LoginHandler field                                                        [CONFIRMED, this pass -- no such instruction exists in either branch]
5. checkScriptBaseAppAddr's only externally-visible effect (beyond logging and the
   optional, return-value-discarded script notification) is calling 0x93a404(this=
   LoginHandler_this), which checks an unrelated pending-operations counter and, if
   clear, proceeds to 0x9387cc (candidate: the real BaseApp-connection-initiating step) [CONFIRMED (0x93a404's own logic) / STRONGLY SUPPORTED (0x9387cc's role, not disassembled)]
6. The ADDRESS DATA actually used by whatever 0x9387cc does must therefore be read
   AGAIN, separately, directly from LoginHandler_this+0x50/+0x60 -- since it is never
   passed as an argument anywhere in the checkScriptBaseAppAddr/0x93a404 call chain     [INFERRED from elimination -- not directly observed inside 0x9387cc, since that
                                                                                          function was not disassembled this pass; flagged as the one remaining structural
                                                                                          assumption in this otherwise fully-traced chain]
```

**Answering the task's Phase 8 question directly**: `+0x50` is **not** merely an
intermediate/throwaway value — it is the **persistent, canonical storage** for the
decoded address data, read at least twice (once implicitly for the
`checkScriptBaseAppAddr` temp-copy, and, by strong inference, again by whatever
`0x9387cc` does to actually initiate the BaseApp connection). It is most consistent with
**two `Mercury::Address` structures** (16 bytes) **plus a separate trailing value** (the
4/8-byte field at `+0x60`), matching this project's long-standing hypothesis — this pass
did not find new evidence to revise that structural characterization, only to confirm
`+0x50` is genuinely load-bearing rather than transient.

## Search For Related Strings/Constants

Searched the binary for every live cross-reference near `checkScriptBaseAppAddr` and its
neighbors for the terms the task requested:

| Term | Found | Notes |
|---|---|---|
| `checkScriptBaseAppAddr` | Yes, `0x2a49653` | The only log string bearing this exact name; already fully accounted for above |
| `BaseApp` | Yes, in `"Unable to connect to BaseApp: A NAT or firwall error may have occured?"` (`0x2a5c62c`-ish, already documented in prior passes) and `"sending base app request to %s "` (`0x2a49141`, prior pass) | Both already covered in `MERCURY_LOGIN_REPLY_KEY_TRACE.md`/`MERCURY_ACTIVE_DECRYPT_TRACE.md`; not re-derived |
| `Address` | The address-to-string helper `0x981c0c` (unnamed directly, but functionally confirmed) | No new named string found this pass |
| `script` | Only within `"not call script, script addr=%s"` | No separate "script error"/"script callback" diagnostic string was found near this function |
| `Python` | **None found** anywhere near this function or its neighbors | The scripting mechanism is inferred from code shape (a global engine-singleton check + a one-shot flag + closure construction), not from any literal "Python" string — **flagged UNKNOWN as a naming assumption**; this project has not proven the script engine is specifically CPython/the BigWorld PyScript binding, only that *some* optional external-callback mechanism exists |
| `LoginApp` | Already extensively documented elsewhere (`ServerConnection::logOnBegin conneting to ... for loginAPP`) | Not re-derived |
| `server address` | No distinct literal string found | The address itself is never logged as a labeled "server address" string; only via the generic `%s` substitution pattern already covered |

**No new, previously-unknown constant or string was found that suggests a hidden
alternate-address mechanism.**

## Confidence Summary

| Conclusion | Confidence |
|---|---|
| `checkScriptBaseAppAddr`'s real entry is `0x93a134` | CONFIRMED |
| The "call script" gate requires both a global engine pointer and a one-shot per-connection flag | CONFIRMED |
| This project's tests always take the "not call script" branch | CONFIRMED (matches every logcat capture) |
| Branch A (call script) only logs and optionally notifies a script callback with a **copy** of the address | CONFIRMED |
| Branch A's script-callback return value is discarded, never used to alter the address | CONFIRMED |
| Both branches converge on `0x93a404(this=LoginHandler_this)`, **not** address data | CONFIRMED |
| `0x93a404` checks an unrelated pending-operations counter, unrelated to address content | CONFIRMED |
| `0x9387cc` is the real "initiate BaseApp connection" step | STRONGLY SUPPORTED, not disassembled this pass |
| `LoginHandler_this+0x50`/`+0x60` is genuinely load-bearing (read again later, not just transient) | STRONGLY SUPPORTED via elimination, not directly observed inside `0x9387cc` |
| The exact identity of the "script engine" (Python/CPython specifically) | UNKNOWN — inferred from code shape only, no literal string confirms it |
| The two other call sites (`0x939238`, `0x939304`) | UNKNOWN — not investigated this pass |
| The exact vtable/class of the closure object built in Branch A | UNKNOWN — located (`0x37d7728`-ish) but not further identified |

## Unresolved Questions

- What `0x9387cc` actually does — not disassembled this pass, since the task's central
  question (does the script path provide an alternate address) is already fully answered
  without it.
- The two other `checkScriptBaseAppAddr` call sites (`0x939238`, `0x939304`) — could be a
  periodic re-check, a different message type's handler, or dead/reused code; not
  investigated, flagged as a gap.
- The exact contents of `resource_object+0x1a0` (the candidate Python-callable field) and
  the precise signature/behavior of `0x94e420` (the script-invocation call) — reversed
  only as far as necessary to establish that its result is discarded.
- Whether the "call script" path, if it *were* active, could theoretically be made to
  matter through some other, indirect mechanism (e.g., a Python callback that itself
  calls back into native code to change state) — no evidence either way was found, and
  this project's own test environment cannot exercise this path to check empirically
  (no scripting layer active).

## CONCLUSION:
`checkScriptBaseAppAddr` validates and *logs* the already-decoded LoginReply address
(and, only if a scripting layer is active — never the case in this project's tests —
notifies a registered Python callback with a disposable copy of it). It does not
validate the address for correctness in any rejecting sense either (no `cmp`/bounds-check
against the address content was found in either branch) — "validating" here means
"logging/reporting," not "gatekeeping."

## CHECK_SCRIPT_PATH:
Confirmed present, confirmed never exercised in this project's tests (no scripting layer
active), and confirmed — by full disassembly — to be a one-way notification hook whose
return value is discarded, not an address source or override mechanism.

## BASEAPP_ADDRESS_SOURCE:
The 20-byte LoginReply body, Blowfish-decrypted and stored at `LoginHandler_this+0x50`/
`+0x60` *before* `checkScriptBaseAppAddr` is ever called. No alternate source exists on
this call path.

## CAN_LOGINREPLY_BE_BYPASSED:
No. Both branches of `checkScriptBaseAppAddr` lead to the identical next step using the
identical (non-address) argument; the actual BaseApp address is never replaced,
supplemented, or overridden by the script mechanism.

## CURRENT_BLOCKER:
Unchanged from `MERCURY_LOGINAPP_KEY_HANDSHAKE.md`: the client provides no mechanism by
which a real server could produce a usefully decryptable first LoginReply body, since the
Blowfish key never leaves the client and decryption cannot be bypassed or substituted —
confirmed once more here, since the one remaining unexplored avenue (a script-side
address override) has now been ruled out.

## HIGHEST-VALUE_NEXT_EXPERIMENT:
Static disassembly of `0x9387cc` (the candidate "create `BaseAppLoginRequest`" step) to
confirm it re-reads `LoginHandler_this+0x50`/`+0x60` directly, closing the one remaining
structural inference in this trace — though this would not, by itself, resolve the
already-identified key paradox, only complete the address-data-flow picture for its own
sake.
