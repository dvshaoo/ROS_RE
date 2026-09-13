# NEXT — IKAW ANG GAGAWA, kabilang session mag-verify (flip setup tuloy)

## ANTIGRAVITY SUMMARY — Static Research Complete (T13 + T14)

**T13 — G4 Parser Kill: COMPLETE**
- Parser format: `##########` (10 hash chars) + JSON tail
- Minimal no-update payload: `##########\n{}` (13 bytes)
- Eliminates: error code 41006 (`W_PARSE_NPK_VERSION_ERR`)
- Source: `patch/ResourcePatcher.py:403-420` bytecode

**T14 — KeyError: 'type' Root Cause: COMPLETE**
- **Root cause**: JSON tail missing `"type": "package"` key
- **Crash site**: `ResourcePatcher.py:1279`, `npk_file_type = version_info['type']`
- **Fix**: Include `"type": "package"` in JSON tail
- **Also**: `"version"` must be STRING `"1117219"`, not int
- **Also**: `"file_list": []` bypasses file iteration
- **Also**: `"use_dlc_clothes": false` disables DLC download
- **Source**: `patch/ResourcePatcher.py:1271-1285` bytecode disassembly

**GATE 1 STATUS: PASSING**
- MITM server serves corrected plist
- Logcat: `process_result host=g61.update.easebar.com, success=True, fault=None`
- Version info: `{type: 'package', version: '1117219', version_name: '1.610377.506841', min_client_version: 0, min_engine_version: 0, min_patch_client_version: 0, min_patch_engine_version: 0, file_list: [], use_dlc_clothes: False}`
- **Remaining**: `ZeroDivisionError` at line 1285/1299 in `patch_size_calc` (data format mismatch — file_list/total_list format)

## NEXT TASK: Drain Verification Queue (Rule T1)
- First action of next session: drain `docs/VERIFY_QUEUE.md`
- No new problem work before this is complete
- Unverified edits leak into build if skipped

## ANTIGRAVITY: NEXT STEPS
1. **DOCUMENT**: Update `RESULT_T15.md` with gate 1 passing status
2. **FIX**: Resolve `ZeroDivisionError` in `patch_size_calc` (likely `file_list`/`total_list` format)
3. **MOVE**: Proceed to Gate 2 (BaseApp session) once Gate 1 fully verified
4. **CHECK**: Drain `docs/VERIFY_QUEUE.md` before any new work
5. **RECORD**: All findings in `PROGRESS.md`, `MASTER_SPEC.md`, `DECISIONS.md`, `BLOCKED.md`

**HARD RULE**: No new problem work before VERIFY_QUEUE.md is drained. Unverified edits are how "still not fixed" runs produce unchanged game.
