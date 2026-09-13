# BLOCKED.md — Open Questions / Gaps (Instead of Guessing)

## Rule: Unknowns go here, NOT invented values. Leo or extraction resolves these.

### GATE 1 — PATCH VERSION CHECK
- **[RESOLVED 2026-09-13] `ZeroDivisionError` (L1285) / `TypeError: unhashable dict` (L1299) / missing `_updated` (L1308)**: fixed by T15 plist schema (string `file_list` + `<name>_updated/_size/_md5` tail keys + protocol-2 `{}` total_list). Live-verified: no traceback, boot reaches `properties.init()`. See `DECISIONS.md` T15 entry.
- **[RESOLVED 2026-09-13] force-Patch + patchVersion (T16/T17a/T17b)**: driver mapped, clearing input live-verified, patch gate CLEARED. See `DECISIONS.md` T17b entry. Planted `patchVersion`=`1.0.0.en` persists on device; do NOT delete (regression will re-trigger the force path).
- **[BLOCKED-006]**: server-list schema (`server_list_ad.txt` loops 404)
  - **Symptom**: post-patch boot loops `GET /server_list_ad.txt` → 404 → alarms 41001/1000/111/112/113; same for `notice_pc_hw.txt`
  - **What's needed (T2 trace-before-fix)**: driver map of server-list subsystem — request builder (URL/host per channel), response parser (module:line), decoded model → callback → client state. AGENT.md T05 (`ServerListURL`, `getServerList`) is the intake; cite dex/bytecode, capped excerpts.
  - **Status**: open; assigned next to AntiGravity as T18.
- **[BLOCKED-007]**: UniSDK/drpf guest-auth endpoints + POST fields (AGENT.md T02–T04, still open from intake)
  - **Status**: open; static dex scan, no live guessing.
- **[BLOCKED-008]**: LVU "verified" terminal enum for update_birthday/update_email/update_consent responses (T19)
  - **Proven so far (live, emulator-5554)**: (1,1)=minor-pending-consent (email page / confirm loop); (0,0) on email=restart at birthday; (2,2)=hard fail (channelLoginFail code 1, minaStatus 2); omitted login fields (defaults 0/4) do NOT suppress panels.
  - **Bytecode facts**: query-result switch on minor {0,1,2,3} loops uniformly (`e/b/d` 0x3ccee0); default → alert dialog. e/b/c state machine (keys 2-5 @0x3cc968) unmapped — decode it next, or capture original-server update_birthday response for an adult birthday.
  - **Also open**: UILogin.py game-side LVU trigger (member sig 0xc6a16d1c in OBB script.npk; AES-ECB with MASTER_SPEC key did not decrypt `scratch/uilogin.raw` — member framing/crypto differs; toolchain `C:/tools/re` not on this machine).

### GENERAL — DATA FORMAT UNCERTAINTIES
- **[BLOCKED-002]**: Exact format of `file_list` in plist JSON tail
  - Code expects list of strings (file names), but JSON parsing may convert to dicts
  - T14 analysis: `_filesToPatch = info.get('file_list', [])` then `for fileName in filesToPatch:` expects strings
  - Need to verify: should `file_list` be `["filename"]` or `[{"name": "filename", "size": N, "md5": "..."}]`?
  
- **[BLOCKED-003]**: Exact format of `total_list` response
  - `downloadTotalList()` calls `_fetch_http_data('1117219/total_list')` then `zlib.decompress()` then `cPickle.loads()`
  - Returns dict that is then used in size/patch calculations
  - `co_consts[8]` = `1.0629911572472126` and `co_consts[9]` = `100` used in function (purpose unclear without source)
  - Need to extract full source to determine expected dict keys and types

### EXTRACTION DEBT
- **[BLOCKED-004]**: Full `ResourcePatcher.py` source not saved to disk
  - T13/T14 analyzed bytecode (48,715 bytes decrypted from `script.npk` entry `0x4CC04A3F`, offset `0x0276C580`)
  - But source not persisted to `05_entities/out/` or elsewhere
  - Need to extract and save for future reference without re-discovering same functions

### HOW TO RESOLVE BLOCKED ITEMS
- **Extraction**: Use `neox_decrypt.py` + AES key `w5q6^C04SW!@e}ad` to decrypt `script.npk` entries
- **Bytecode disassembly**: Use Python `dis` module on extracted `.pyc` files
- **Live session**: Frida attach to emulator PID to dump runtime execution, or use MITM logcat with detailed tracing
- **Do NOT guess**: If a value isn't in the source or MASTER_SPEC, STOP and write it to BLOCKED.md

---
*Per rule §5 (INTake): Unknowns go to BLOCKED.md instead of guessing.*
*Per rule §0.5-T5: Reference or it didn't happen. `reference/original/` being empty means gate parity is UNDECIDABLE.*
*Per rule §0.5-T4: Single-function recovery allowed only when remaining opcode work demonstrably larger than problem at hand.*
*Last updated: 2026-09-13*