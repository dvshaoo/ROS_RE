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

## Finding 2 (NEW, high-value): method-index is libc++ SSO-encoded, not raw

**Finding:** The "method index" argument (`param_1+0x10`) is not a plain
integer. It is encoded exactly like a libc++ `std::string` short-string-
optimization discriminator:

- bit 0 = 0 → short/inline form → real index = `value >> 1`
- bit 0 = 1 → long form → one more indirection (`pcVar7 = *(pcVar7 + *plVar1)`)
  before use.

**Ghidra evidence:** Literal decompiled expression
`plVar1 = lVar8 + ((long)*(ulong*)(param_1+0x10) >> 1)`, gated by
`(*(ulong*)(param_1+0x10) & 1) != 0` for the alternate path — this is the
textbook libc++ `__is_long()`/`__get_short_size()` bit-layout pattern, not
something the original hand-disassembly had flagged.

**Live E2E evidence:** E2E-028 and E2E-037 sent a **literal byte `2`** as
the assumed method index for `Account.onChannelLogin`, on the theory that
method index 2 in the `.def`-derived method table corresponds to
`onChannelLogin`. Both experiments produced **zero observable effect**
across 3 wire-format variants and a 407-packet retry flood.

**Relationship:** Under this newly-discovered encoding, a raw byte `2`
(binary `10`, bit0=0) decodes to real index `2 >> 1 = 1` — **method index 1,
not 2**. This is a direct, concrete, previously-unknown explanation for why
every prior `onChannelLogin` wire-format experiment silently dispatched to
the wrong method (or no bound method at all) instead of failing loudly or
succeeding. The correctly-encoded short-form byte for real index 2 would be
`(2 << 1) | 0 = 4`.

**Confidence:** STRONGLY SUPPORTED (mechanism is confirmed via
decompilation; the causal link to why past live tests silently failed is
INFERRED, not yet re-tested live).

**Next actionable experiment:** Re-run the `ONCHANNELLOGIN_VARIANT` live
test in `mitm/local_baseapp_capture.py` using method-index byte `4` instead
of `2` (and, generally, `(realIndex << 1)` for any short-form index up to
127). This has NOT yet been tested live — requires user approval to resume
emulator testing.

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
