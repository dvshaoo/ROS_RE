# ROS v1117219 — Mercury LoginReply Validation Trace (Correction Pass)

**Result up front — this pass corrects a material misinterpretation from the previous
session and narrows, rather than fully answers, the central question.** Full disassembly
of `0x937df0`–`0x937f0c` shows it does **not** parse or validate the content of an
incoming reply. It **(re)builds and serializes an outgoing `LogOnParams`-shaped bundle**
(confirmed: it calls directly into `LogOnParams::addToStream`'s own body) and reports
`Mercury::REASON_CORRUPTED_PACKET` only if **that serialization/send attempt itself**
fails. The previous document's characterization of this function as "the validation stage
that rejects our reply" is **corrected here, not carried forward as fact.** The tight,
reproducible timing correlation between our reply's arrival and this failure firing
(sub-2ms to ~12ms, 1:1, every time) remains real and is documented — but the *mechanism*
connecting the two is now **UNKNOWN** rather than the "Nub-level packet validation"
characterization asserted previously. No candidate reply packet was fabricated in this
pass, because the evidence does not support deriving one — see §5 for why.

## Phase 1 — Full Disassembly of `0x937df0`–`0x937f0c` (Corrected)

### Function Signature (from register usage)

```
this = x0 → x20   (a "connection/context" object)
arg1 = x1 → x21   (an output BinaryOStream / Mercury Bundle, NOT the received reply)
```

### Annotated Pseudocode

```cpp
// 0x937df0
void ??? ::rebuildAndResendLogOnParams(Context* this /*x20*/, BinaryOStream* outBundle /*x21*/)
{
    // this->pInner is a shared/ref-counted "context" struct at this+0x18
    Inner* inner = this->pInner;                       // x8 = [x20+0x18]

    // A ref-counted LogOnParams-like object cached at inner+0x40
    LogOnParams* params = inner->cachedLogOnParams;     // x19 = [x8+0x40]
    if (params) params->incRef();                       // atomic refcount++ at params+8

    // --- Reserve 4 bytes in the OUTPUT bundle and write a FIXED CONSTANT ---
    // This is the SAME vtable[0x10] "reserve(n)" WRITE pattern documented in
    // LOGONPARAMS_SERIALIZATION.md for LogOnParams::addToStream itself - confirming
    // outBundle is being WRITTEN INTO, not read from.
    uint8_t* slot = outBundle->reserve(4);              // vtable[0x10](outBundle, 4)
    *(uint32_t*)slot = 0x2b;                             // CONFIRMED: literal constant 43

    // --- Call LogOnParams::addToStream directly ---
    Inner* inner2 = this->pInner;                        // reloaded
    void* pKeyThing = inner2->someResource + 0xf30;       // x3 = [inner2+0x48] + 0xf30
    bool ok = LogOnParams_addToStream(                    // bl 0x9d8018  (see Phase 4)
                  /* this  */ params,                     // x0 = x19
                  /* stream*/ outBundle,                  // x1 = x21
                  /* flags */ 1,                           // w2 = 1 (literal)
                  /* pKey  */ pKeyThing);                  // x3

    if (!(ok & 1)) {
        // --- FAILURE PATH ---
        log_warning("...");                                // bl 0x1cad604, generic fixed string at 0x2a48f58 ("id %d\n"-adjacent rodata - a generic diagnostic, not itself the MainApp::poll line)
        ConnObj* conn = this->pInner;                       // reloaded again: [x20+0x18]
        conn->state_0x65 = 2;                                // CONFIRMED: same offset used by handleMessage's own error paths
        char* buf = conn + 0x68;
        strcpy_n(buf, "Mercury::", 9);                       // bl 0x83f8a8
        strcat_n(buf, "REASON_CORRUPTED_PACKET", 23);         // bl 0x83fbd8
        // loop: flush/notify any registered listeners (vtable dispatch via conn+0x98/+0x88)
        conn->state_0x64 = 1;                                 // CONFIRMED: "failed" flag, same offset as handleMessage
    }

    if (params) params->decRef();                           // atomic refcount-- , dtor if 0
    return;
}
```

### Answers To Phase 1's Specific Questions

1. **`this` object**: a "context/connection" struct (`x20`), reached via `this+0x18` for
   an inner resource block — **not** directly the incoming-reply buffer.
2. **Input stream/buffer object**: `x21` is an **output** `BinaryOStream`/Bundle — it is
   being written into (`reserve()` + direct stores), not read from. **This is the single
   most important correction**: there is no "input packet parsing" in this function at all.
3. **Reads before the failure branch**: none of the incoming reply's bytes are read here.
   The only "read" is `inner->cachedLogOnParams` (a pointer field), not packet data.
4. **vtable methods called**: `vtable[0x10]` on the output stream (`reserve(n)`,
   write-side — same slot/semantics as in `LogOnParams::addToStream` itself), plus two
   generic ref-count vtable calls (destructor pattern) and a notify-listeners loop
   (`conn+0x98`/`+0x88` vtable dispatch) in the failure path.
5. **Values read from the incoming packet**: **none, by this function.**
6. **Success vs. failure determination**: the return value of the direct
   `LogOnParams::addToStream` call (`bl 0x9d8018`), tested via `tbnz w0,#0`.
7. **Success path**: skips straight to cleanup/refcount-decrement and returns — no further
   action is visible in this function on success (the actual `sendto()` of the rebuilt
   bundle, if any, would happen inside `addToStream`'s own call chain or a caller not
   examined here).
8. **After success returns**: only refcount bookkeeping and `ret` — nothing else in this
   function's body.

## Phase 2 — Caller Chain

| Target | Direct callers found |
|---|---|
| `0x937df0` (this function) | **None** (confirmed via the project's standard `BL` scan across all of `.text`) |
| `0x9d8018` (`addToStream`, 4 bytes past the entry point identified in prior sessions) | **Exactly one**: `0x937e54` — i.e., this function |
| `0x9d8014` (the address previously assumed to be `addToStream`'s entry) | **None** — unchanged from prior sessions |
| `0x937128` (the "register Mercury reply/timeout handler" utility already confirmed for `baseAppLogin` in earlier sessions) | Three: `0x937d5c`, `0x938818` (confirmed `baseAppLogin` sender, prior session), and a new one, `0x939ce4` (not investigated further this pass) |

`0x937df0` having **zero** direct callers means it is invoked indirectly — most plausibly
as a stored callback (its two-argument signature matches the `std::function<void()>`-style
manager/invoke pair pattern this project has documented elsewhere, e.g. in
`BASEAPP_LOGIN_SERIALIZATION.md`'s analysis of a similar tracker object). The immediately
preceding function (`0x937d90`–`0x937de4`) has the shape of a matching destructor/manager
for the same closure, consistent with this theory, but **the actual wiring (where the
function pointer is stored, and what triggers its invocation) was not traced in this
pass** — flagged as UNKNOWN, not asserted.

**A separate, adjacent function (`0x937d2c`–`0x937d8c`) calls `0x937128` with a literal,
hardcoded `w4 = 0xa` (10) and a 5.0-second timeout.** Given this project's own wire-capture
evidence (`MERCURY_WIRE_CAPTURE.md`) independently and repeatedly confirmed the client
retries **exactly 10 times**, this is a strong numerical correlation: **STRONGLY
SUPPORTED, not proven**, that this `10` is the maximum-retry-count parameter for the
LoginApp request. No other candidate explanation for this specific literal was found or is
proposed.

## Phase 3 — Expected Packet Structure: NOT DERIVABLE From This Function

**This is the honest, load-bearing conclusion of this pass.** The task asked to
reconstruct the expected `LoginReply` structure from this validation function. Having
fully disassembled it, **it does not read or validate the received reply's bytes at all**
— it is an outgoing-bundle (re)builder. Therefore **no field table can be produced from
this function**, and none is fabricated here. What this function's failure tells us is
narrower than previously stated: *some* condition — tightly correlated with our reply's
arrival, but not shown to depend on the reply's specific byte content — causes this
outgoing-rebuild-and-resend routine to be invoked and to fail. The actual code that reads
our 22 reply bytes and decides they are unacceptable (if any exists as a distinct step)
has **not been located** by this pass.

## Phase 4 — `0x9d8018` Fully Resolved

- `0x9d8014`: the address previously assumed to be `LogOnParams::addToStream`'s entry
  point (identified in the session that produced `LOGONPARAMS_SERIALIZATION.md`, via a
  string xref landing inside this address range). Confirmed in this pass to still have
  **zero** direct callers.
- `0x9d8018`: **4 bytes later.** This pass finds its **one and only** direct caller in the
  entire binary: `0x937e54`, inside the function analyzed above.
- **Conclusion**: `0x9d8018` **is** the real, live call-through entry point for
  `LogOnParams::addToStream` used by native code — not a different, misidentified
  function. The 4-byte gap corresponds to a single instruction
  (`bl #0x7d8ea0`, a stack-protector/probe call, per `LOGONPARAMS_SERIALIZATION.md`'s
  original disassembly) that sits between the two addresses; direct callers skip it,
  landing at `0x9d8018`, while `0x9d8014` itself may only be reached by fall-through from
  a preceding block (not identified) or not be a real independent entry point at all. This
  does **not** change any field-level finding in `LOGONPARAMS_SERIALIZATION.md` about the
  body of `addToStream` (flags/string/digest layout, RSA-OAEP encryption) — those
  findings are about the function's *body*, which is unaffected by which exact address is
  the "true" entry.
- **Arguments followed at `0x937e54`** (this pass's new finding): `this=params` (a cached
  `LogOnParams` object, obtained from a context field, refcounted — **not** newly
  constructed from scratch each retry), `stream=outBundle` (the output being built for
  this send/resend), `flags=1` (a literal, not the `0xFF` "use stored flags" sentinel
  documented in `LOGONPARAMS_SERIALIZATION.md` §2 — meaning this call path always forces
  flag bit 0 set, i.e. always includes the 16-byte digest field per that document's §4),
  `pKey=<context+0x48>+0xf30` (the RSA public key resource, reused from cached context
  rather than reloaded from the asset path each time).

## Phase 5 — Correlation With The Genuine 273-Byte Request

- **The `0x2b` (43) field, confirmed as a literal compiler-emitted constant, not a
  computed value.** This upgrades `PLAY_TO_BASEAPP_CAPTURE.md` §2's prior "STRONG
  EVIDENCE" label (which speculated this might be a *data-dependent* plaintext length) to
  **CONFIRMED**: the value `43` is hardcoded (`mov w8, #0x2b`) in the code that writes it,
  not computed from any string length at runtime. It happens to also be plausible as "the
  plaintext length before OAEP padding," but its presence in the wire capture is now known
  to be a **fixed protocol constant** for this message shape, not evidence about the
  specific credentials being sent.
- **The `0xa` (10) retry-count correlation**: see Phase 2 — STRONGLY SUPPORTED link to the
  wire-confirmed 10-retry behavior.
- **Request sequence number, RSA/decrypted content, account/session identifiers, any
  nonce**: **not newly investigated this pass** — this function does not touch any of
  these (it only rebuilds the bundle using the cached `LogOnParams` object and a constant
  flag), so it provides no new evidence about them. No claim is made either way.
- **Reply correlation ID**: **not found in this function** — consistent with §3's
  conclusion that this function never inspects reply content.

## Phase 6 — A/B/C Experiment: Not Run This Pass, With Reason Given

The task's Phase 6 asked for a third condition (**C**, an "evidence-derived candidate")
alongside the existing NO_REPLY/REPLY conditions. **No candidate C was constructed**,
because Phases 1–5 did not produce field-level evidence to derive one from — the function
examined does not validate reply content, so there is nothing evidence-based to change
about the reply bytes. Constructing a new candidate here would mean guessing, which the
task explicitly forbids. The existing A/B data (NO_REPLY vs. the current 22-byte reply,
from `MERCURY_POST_RECV_DISPATCH_TRACE.md`) stands unchanged and is not re-run
redundantly in this pass.

## CONFIRMED

- `0x937df0`–`0x937f0c` builds/serializes an **outgoing** `LogOnParams`-shaped bundle by
  calling directly into `LogOnParams::addToStream`'s body — it does not parse or validate
  incoming reply bytes.
- `0x9d8018` (not `0x9d8014`) is the real, single, live call-through entry point for
  `LogOnParams::addToStream`, with exactly one caller in the whole binary: `0x937e54`.
- The `0x2b` (43) field written by this function is a hardcoded literal constant, not a
  computed value — confirming (not merely suggesting) it is a fixed protocol constant.
- `Mercury::REASON_CORRUPTED_PACKET` is reported by this function specifically when its
  own call to `LogOnParams::addToStream` returns failure — a **send-side** encoding
  failure signal, by this function's own logic.
- The `MainApp::poll` warning (this same string) follows every successful `recvfrom(181)`
  read of our reply within 1–12ms, every single time, in the capture examined.
- `0x937df0` itself has zero direct callers (confirmed via the standard `BL` scan) —
  it is invoked indirectly.

## STRONGLY SUPPORTED

- The hardcoded `w4=0xa` (10) argument to `0x937128` from the adjacent function
  `0x937d2c`–`0x937d8c` is the maximum-retry-count parameter for the LoginApp login
  request, given the exact numerical match to the independently wire-confirmed 10-retry
  behavior.
- Something about receiving our reply (its mere arrival, not necessarily its specific
  byte content — not distinguished by this pass) triggers this rebuild-and-resend routine
  to run and fail, given the extremely tight and consistent timing correlation.

## UNKNOWN

- **The exact mechanism connecting "a reply arrives" to "this rebuild-and-resend function
  executes."** No direct or indirect call edge from the already-disassembled
  `handleMessage`/`onLoginReply` function (`0x938070`–`0x938724`) into this function or its
  likely-adjacent manager/destructor was found; the connection must be through
  virtual/callback dispatch not resolved by this pass's available tools.
- Whether **any** code in this client actually reads/validates the specific byte content
  of our 22-byte reply, as opposed to the Nub-level machinery simply treating any
  unexpected/unrecognized inbound data as a signal to abandon the current attempt and
  restart it (which would fail regardless of what specific bytes we sent, as long as they
  don't match whatever the client expects at a much earlier stage than this function).
- Why `LogOnParams::addToStream`'s call from this specific rebuild path fails (returns
  false) when triggered this way — e.g., whether the cached `LogOnParams` object or RSA
  key resource is in an unexpected state at this point in execution.
- Whether `LoginHandler::onLoginReply` executes at any point — **still not observed,
  still not claimed**, in either direction.

## Next Blocker

The concrete next question, now correctly scoped: **what code, if any, reads our reply's
22 bytes for their content** (as opposed to the outgoing-bundle-rebuild function analyzed
here, which does not)? The most promising untried lead is the manager/destructor-shaped
function immediately preceding this one (`0x937d90`–`0x937de4`) and the retry-registration
function at `0x937d2c`–`0x937d8c` — resolving how these three functions
(`0x937d2c`, `0x937d90`, `0x937df0`) are wired together (e.g., as a `std::function`
manager/destroy/invoke triple) would establish *when* the rebuild-and-resend path fires
relative to actual reply processing, which is the missing link this pass could not close.
