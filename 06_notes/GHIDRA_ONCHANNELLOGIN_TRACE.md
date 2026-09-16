# Ghidra trace: entity+0x140 dispatcher / onChannelLogin path

## Objective

Use Ghidra 12.1.3 (headless, hybrid alongside the project's Capstone-based
`scratch/xref_lib.py`) to push past two walls the hand-rolled toolkit could
not resolve on its own:

1. Find the real caller of `FUN_00a4c540` (static offset `0x94c540`, the
   entity+0x140 generic RPC dispatcher), previously characterized only as
   "reached via virtual dispatch/register-indexed call, caller unknown."
2. Re-examine the wire-format assumptions behind the `Account.onChannelLogin`
   live experiments (E2E-028, E2E-037), which produced zero observable
   effect across 37+ passes.

## Ghidra project / binary info

- Ghidra 12.1.3 PUBLIC, headless mode, direct `java` invocation (bypassing
  `analyzeHeadless.bat`, which has a bug where passing `-analyze` corrupts
  argument parsing in this version — analysis runs by default and the flag
  does not exist).
- Binary: `03_lib/libclient_arm64.so` (same file `scratch/xref_lib.py` has
  always targeted).
- Project: `scratch/ghidra_project/ROS_RE.gpr` (not committed — excluded via
  `.gitignore`, regenerate locally via `-import` if needed).
- **Ghidra imageBase = `0x100000`.** CONFIRMED: every static address this
  project has established (via the Capstone toolkit / live E2E evidence)
  must be looked up in Ghidra at `imageBase + staticOffset`, not at the raw
  offset. Cross-validated against 4 independent anchors (`0x938070` =
  `LoginHandler::onLoginReply`, matched by exact log-string content;
  `0x94c540` = entity dispatcher; `0x989600` / `0x98924c` = the two
  Blowfish/EncryptionFilter decrypt variants, matched by exact
  `BF_ecb_encrypt`-chaining logic and the enabled-flag check difference
  already documented) — all 4 matched perfectly.

## Finding 1: `FUN_00a4c540` decompiled in full

**Finding:** `0x94c540` is `ClientVarLenMessageHandler::handleMessage` (name
inferred from its own log string, not RTTI symbol — RTTI/mangled names for
this class are not retained in the binary's symbol table, see Finding 3).
Full decompiled logic:

```c
void FUN_00a4c540(long param_1,undefined8 param_2,long param_3,long *param_4)
{
  lVar8 = *(long *)(*(long *)(param_3 + 0x10) + 0x4458);
  if (*(long *)(lVar8 + 0x140) != 0) {
    uVar2 = *(undefined4 *)(param_3 + 8);
    if (*PTR_DAT_03a15320 == '\0') {
      pcVar7 = *(code **)(param_1 + 8);
      plVar1 = (long *)(lVar8 + ((long)*(ulong *)(param_1 + 0x10) >> 1));
      if ((*(ulong *)(param_1 + 0x10) & 1) != 0) {
        pcVar7 = *(code **)(pcVar7 + *plVar1);
      }
      (*pcVar7)(plVar1,param_4,uVar2);
      iVar4 = (**(code **)(*param_4 + 0x18))(param_4);
      if (iVar4 != 0) {
        FUN_01dad7ac("ClientVarLenMessageHandler::handleMessage Handler for "
                     "ClientMessage (header.length%d) did not consume all "
                     "data, remain %d bytes\n", uVar2, uVar5);
      }
    } else {
      /* alternate dispatch path via FUN_00a7bfa8/FUN_00a7c0d8 -- some kind
         of async/queued dispatch, not yet analyzed in detail */
    }
  }
}
```

**Ghidra evidence:** Callers via direct call-type cross-reference: **zero**
(`[No direct call-type references found]`), matching the prior
Capstone-toolkit conclusion exactly.

**Live E2E evidence:** E2E-025/029 established this function only reads
`entity+0x140` and does nothing when it's zero (the observed gate).

**Relationship:** Confirms, does not change, the prior finding — but now
backed by full Ghidra decompilation instead of hand-disassembled Capstone
output.

**Confidence:** CONFIRMED (decompilation + 4-anchor address cross-validation).

## Finding 2 (RETRACTED): "method-index SSO encoding" was a misread — this is the standard Itanium PMF representation, not wire-controlled

**Original claim (WRONG, retracted):** An earlier pass of this
investigation characterized the `param_1+0x10` field in `FUN_00a4c540` as a
libc++ `std::string`-style SSO discriminator, and proposed that live
`onChannelLogin` tests had been sending the wrong wire byte (`2` instead of
`4`) as a result.

**Correction:** On closer reading, this bit pattern —
`plVar1 = lVar8 + (value >> 1)`, gated by `(value & 1) != 0` triggering one
more indirection through a vtable-like lookup — is the textbook **Itanium
C++ ABI pointer-to-member-function representation**: bit 0 distinguishes a
direct function pointer (bit0=0) from a virtual-dispatch byte-offset
(bit0=1, real offset derived from the remaining bits). This value is a
**field of the per-message handler struct (`param_1`), which is a static
data structure compiled into the binary** (built at compile time from the
`.def`-derived method table), **not something populated from wire data at
all**. There is no live wire byte that "should have been" `4` instead of
`2` — that theory does not apply to this field.

**Impact:** This retracts the "next actionable experiment" from the
original version of this finding. **No live test was run against the wrong
theory** — caught before spending an E2E pass on it. The real blocker
remains what Finding 4 already identified: `FUN_00a4c540` no-ops entirely
whenever `entity+0x140 == 0`, regardless of what wire bytes are sent for
the method body, because the whole per-message dispatch block is gated
behind that single pointer check before the PMF-style method invocation
is ever reached.

**Confidence:** CONFIRMED (Itanium ABI PMF calling-convention pattern is
unambiguous once correctly identified).

## Finding 2b: chasing the +0x140 SETTER's real trigger — dead end via direct-callee tracing

**Finding:** The setter `FUN_00a3a5e4` (`*(param_1+0x140) = param_2`, then
conditionally invokes a pending callback via `*(param_1+0x150)`, then calls
`FUN_00a473d0(param_1)`) has, like the dispatcher itself, **zero direct
call-type callers** (`INDIRECTION`/`DATA`-only refs to a vtable slot at
`0x33f4a80`, no preceding RTTI label, nothing takes that slot's address
directly — the same virtual-dispatch-with-unfindable-constructor pattern as
`FUN_00a4c540`'s own vtable slot).

Its callee `FUN_00a473d0` (touches `param_1[0x27]+0x4210`, `param_1[0x29]`,
`param_1[0x2a]`, `param_1[0x28]` — a mutex-guarded pooled-buffer allocate/
reuse pattern) **does** have real, direct, non-virtual callers findable via
Ghidra (`UNCONDITIONAL_CALL` type at static offsets `0x93d110`, `0x93a558`,
`0x94d4a0`, plus the setter's own tail-call at `0x93a61c`).

**Ghidra evidence:** `scratch/ghidra_setter_callers.txt`,
`scratch/ghidra_deep140.txt`, `scratch/ghidra_callsites_473d0.txt`,
`scratch/ghidra_caller_strings.txt`. String-literal extraction from the 3
non-setter callers' containing functions shows they are unrelated generic
NeoX engine startup/config code (`"Initializing client...."`,
`neox.xml`/filesystem/shader-cache config parsing) — **not**
BigWorld/entity/networking code.

**Relationship:** `FUN_00a473d0` is a **shared, generic pooled-buffer
allocator** reused throughout the binary for unrelated purposes (engine
init, and separately, by the +0x140 setter with a different-typed
`param_1`). Chasing its callers does not reveal what triggers the +0x140
setter — this is a dead end.

**Confidence:** CONFIRMED dead end (the 3 callers' purpose is unambiguous
from their string literals).

**Next actionable step:** Static analysis (both the original Capstone
toolkit and this Ghidra hybrid session) has now independently hit the same
wall twice — the setter's real caller is virtual-dispatch-only with no
resolvable construction site. The next step that could plausibly break this
open is **dynamic instrumentation**: hook `FUN_00a3a5e4` (static
`0x93a5e4`) at runtime on the local test client and log its call stack the
moment it fires (if it ever does) during a real login attempt. This is
local, non-destructive, read-only observation of our own test client
talking to our own local server — not a bypass of any production security
control. Not yet attempted this session.

## Finding 3: symbol-table keyword search is a dead end for game classes

**Finding:** A keyword search (Account/Avatar/Character/Lobby/Player/
CreatePlayer/Match/onLogin/onEnter/onChannelLogin/createBasePlayer/
enableEntities/handshake, case-insensitive) across all ~500-capped matching
symbols in the binary's symbol table returned **zero** BigWorld/game-logic
class names. Every hit was generic third-party static-library noise
(OpenSSL `SSL_do_handshake`, OpenLDAP `ldap_matchingrule*`, PhysX
`platformMismatch`/`onMeshIndexFormatChange`, LibRaw, OpenEXR, HarfBuzz) or
unrelated Java video-player JNI callbacks (`Java_..._CCPlayer_...`,
`NativeOnLogin` — a video-player login callback, not BigWorld's).

**Ghidra evidence:** `ghidra_symbols_clean.txt` (63 lines after filtering
out ~1900-character `boost::spirit`/`boost::wave` template-instantiation
symbol names that were separately blowing up token limits on read).

**Relationship:** Confirms the game-logic C++ classes (Account, Avatar,
Entity subclasses, etc.) are **not retained as demangled/exported symbols**
in this binary the way bundled static libraries are — consistent with
BigWorld's typical build stripping RTTI type-name strings for game-specific
entity classes while leaving third-party libs' symbols intact. A
keyword/name-based approach cannot find these classes; only structural
(vtable layout, string xrefs, offset-pattern) approaches can.

**Confidence:** CONFIRMED (exhaustive search of all matching symbols, capped
list fully reviewed).

## Finding 4: `0x94c540`'s vtable slot located (partial resolution of the caller question)

**Finding:** A full any-reference-type (not just call-type) search plus a
raw byte-pattern scan found exactly one genuine data reference to
`FUN_00a4c540`, at address `0x38d7cb8` (a `data.rel.ro`-style pointer table
entry, value = the function's address). A sibling entry
`PTR_FUN_038d7ca8` sits 16 bytes earlier (2 pointer-slots before it). No
RTTI typeinfo symbol was found immediately preceding either slot. The other
2 raw-search hits (`0x33175d0`, `0x33f7368`) are ordinary `.eh_frame`/FDE
unwind-table entries referencing the function's start address for stack
unwinding, not call sites.

**Ghidra evidence:** `scratch/ghidra_vtable_callers.txt` and
`scratch/ghidra_vtable_inspect.txt` (full any-type reference scan + raw
8-byte pattern scan of all initialized memory blocks + neighbor-symbol
inspection).

**Relationship:** `0x38d7cb8` is very likely the actual C++ vtable slot for
`ClientVarLenMessageHandler::handleMessage` (the class name inferred from
the function's own log string). Nothing in the binary takes the *address*
of this vtable slot directly (`references TO this slot address: [none]`),
meaning the object that carries this vtable pointer is constructed via a
path Ghidra's static analysis doesn't surface as a direct reference (e.g.
the vtable pointer is written once at object-construction time via a
computed/indirect store, or the object is a global static initialized by
`.init_array` — neither has been traced yet). This is genuine C++ virtual
dispatch, not an artifact of incomplete analysis — it explains, at the
tooling level, why the Capstone-based static toolkit's dozens of prior
passes never found a caller via any disassembly-based method.

**Confidence:** STRONGLY SUPPORTED (the vtable slot itself is CONFIRMED via
2 independent methods — reference scan and raw byte scan agreeing — but the
object/constructor that uses this vtable remains UNKNOWN).

## Finding 5: fresh live E2E pass reproduces the exact same blocker, plus a new unifying hypothesis

**Finding:** After the Ghidra-phase corrections above, a fresh live E2E pass
was run against a freshly-restarted server (root DNAT rules and server key
cache reset after an LDPlayer reboot). Result: **identical to every prior
pass** — `ServerConnection::logOnBegin` → `LoginHandler::onLoginReply`
reached, `Nub::recreateListeningSocket` fires for a new "external channel,"
and then **nothing**. No packet ever arrives at the fake BaseApp UDP
listener (`:25010`). This is not a regression and not an improvement —
today's Ghidra findings did not change this outcome, as expected (Finding 2
retraction explains why the "corrected encoding" theory was never actually
applicable here).

**New data point:** attempting to Frida-attach to the live client process
(`com.netease.chiji`, SELinux permissive, frida-server running as root)
during this session **crashed the frida-server connection outright**
(`unable to connect to remote frida-server: closed`) — despite frida-server
successfully enumerating 97 *other* system processes normally, and despite
adb confirming the target process was alive throughout. This is consistent
with the client having some form of runtime anti-instrumentation/anti-
tamper check specific to itself (not a generic Android/frida-server
compatibility problem, since every other process was attachable-in-
principle).

**Hypothesis (INFERRED, not yet tested):** The BaseApp-channel blocker that
has resisted 38+ E2E passes across every wire-format/timing/encoding theory
tried so far may not be a protocol bug at all. A client-side anti-tamper
check (root detection, iptables OUTPUT-redirect detection, or detection of
the modified/instrumented LDPlayer environment itself) could be silently
causing the client to abandon BaseApp channel setup after accepting the
LoginApp reply, regardless of whether the wire format is byte-perfect. This
would explain: (a) why no combination of tried packet formats has ever
produced observable movement past this exact point, (b) why the
`entity+0x140` gate is never set despite the dispatcher and its setter
being otherwise unremarkable in Ghidra, and (c) the frida-attach crash
above.

**Confidence:** INFERRED / UNCONFIRMED — this is a hypothesis raised by
today's evidence, not a proven root cause. It has NOT been tested (e.g. by
comparing behavior against a non-rooted, non-redirected, non-instrumented
reference environment, which is the natural next diagnostic).

**Next actionable experiment (highest priority, supersedes the retracted
Finding 2 experiment):** Determine whether the block is environment-
dependent rather than protocol-dependent. Options, roughly in order of
effort: (1) search the binary (Ghidra string/xref search for
"frida"/"xposed"/"su"/"magisk"/root-marker file paths, or for `ptrace`
self-attach calls, a common anti-frida trick) for anti-tamper logic near
the BaseApp channel setup path; (2) if found, characterize what it does on
detection (silent no-op vs. explicit disconnect) to confirm/refute this
hypothesis without needing a clean reference device.

**Follow-up performed this session (partial, inconclusive):** A binary-wide
string search did find genuine root-detection code: a JNI bridge function
`FUN_01cfaa90` that calls into the Java layer's `isDeviceRooted()` method
and returns its boolean result. Its only found direct (non-virtual) caller,
`FUN_01ceef8c`, is a tiny `void`-returning wrapper that calls it back-to-
back with an unrelated init function (`FUN_01cf95d4()`) and **discards the
returned boolean** — it does not visibly branch on the result itself. This
is consistent with a **telemetry-only** root check (reported to analytics,
not used to gate behavior at this call site) rather than an active
connection-blocking anti-tamper gate, though the boolean could still be
consumed as a side effect inside `FUN_01cfaa90` itself (not yet checked) or
forwarded to a live NetEase backend service this local test setup doesn't
reach. **This does not confirm or refute the Finding 5 hypothesis** — it
only shows that *a* root-detection mechanism exists in the binary; whether
*that specific one* (or a different one) gates the BaseApp channel remains
unknown. Not pursued further this session given time already invested.

## Dead ends

- Symbol-table keyword search for game-logic class names (Finding 3).
- Call-type-only cross-reference search for `0x94c540`'s caller (confirms,
  doesn't add to, the prior Capstone-toolkit finding).

## Next actionable experiments (priority order)

1. **Live-test `Account.onChannelLogin` with the corrected SSO-style
   method-index encoding** (byte `4` instead of `2` for real index 2) — see
   Finding 2. Concrete, low-risk, directly implied by this session's most
   important finding. Requires user approval to resume live emulator
   testing (paused for the Ghidra pivot).
2. Trace `.init_array`/global-constructor entries to find what constructs
   the object living at/near `0x38d7cb8`'s vtable, to finally identify
   `0x94c540`'s real caller by construction site rather than call site.
3. Identify `PTR_DAT_03a15320` (the flag checked as `*PTR_DAT_03a15320 ==
   '\0'` to pick between the direct-dispatch and
   `FUN_00a7bfa8`/`FUN_00a7c0d8` "alternate async/queued dispatch" path
   inside `0x94c540`) and cross-reference it against the debug-flag globals
   already documented in E2E-038 Task 1.
