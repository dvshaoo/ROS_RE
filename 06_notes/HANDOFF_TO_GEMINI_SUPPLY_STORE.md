# Handoff to Gemini — Supply/Store/draws (2026-09-20)

Written for: an engineer/agent continuing the ROS (com.netease.chiji, Android arm64) LAN private-server project with no prior context.
Read first: `CLAUDE.md` (rules: local/LAN only, zero guesswork, live-test -> notes -> atomic commit, record negative results),
then `06_notes/HANDOFF_TO_CHATGPT_STORE_DRAW.md` (full state + tools + how to run), `06_notes/GATE6_BUY_AND_DRAW_PLAN.md` (all findings, newest at the end).

## State
Lobby works with 0 script errors, real currency (999999/999999), nickname `Dev | Raysoo`. Last commits: 6519b1a (notes), 380a8fc, 932b315, be5ee07.
The server decodes client bundles and answers `queryAvailableSupplement` (exposed method 0xdd) with `onQueryAvailableSupplement` (client idx 392, records from
APK `assets.npk` table `9e1c8652`, see `tools/load_table.py`; records are flattened by `_supplement_runtime_record`).

## THE open problem
Supply tabs stay empty ("敬请期待" boxes on STAR, blank SUPREME/VEHICLE/LOOKS) and DRAW sends nothing, although the reply arrives with valid records (ids 1 kind 1 and 2 kind 2 are the only
current general boxes). Ruled out (live): record size/count, record shape (raw vs flattened), reply timing (0 s and 0.7 s), KIND default (schema default = 1).
Verified from corrected disassembly: STAR filter = kind {1,2}; `getSupplementKind(id)` = `legacyProperties.getSupplementData(id).KIND` or -1; unknown kind -> `_initBoxWidget_emptyBox`.
Prime hypothesis: `legacyProperties.getSupplementData(id)` is falsy in this client because the supplement data module is skipped/not loaded.

## Your first tasks
1. Check `common/shared/lib/gametoolslib/properties/__init__.py`: `load_all_data_modules` uses `g_import_py_list_client_skip` (modules NOT loaded by the client) and `normalLoad`
   (non-lazy set); `init(data_path, static, is_lazy)` vs `lazyInit/lazyInitAsync` (called from `UILogin._delay_on_enter`). Find the CONTENTS of `g_import_py_list_client_skip`/`normalLoad`
   (module-level constants; helper `scratch/find_list_const.py` was being written — recreate it, list constants of that module) and whether `data_supplement` is skipped or lazy-not-yet-loaded.
   Disassembler: `PYTHONIOENCODING=utf-8 python tools/script_disas.py '<path>' <func>` (corrected opcode map; garbled `??neox` lines are only args, names/consts are reliable).
2. If it is a lazy/timing issue, find what triggers the lazy load (`lazyInitAsync` after login) and why it is not reached with our server; if it is a skip list, find how the real server side enables it.
3. Then: capture the DRAW call (`UPSTREAM CALL` log lines), implement `openSupplyBox` (base 467) + rewards (see plan file), then Store (`queryAvailableMallGoods*`, `buyMallGood`), daily claim, START->island.
Test loop: `scratch/supply_test.sh <label>` (DO NOT touch the emulator while it runs — the user's taps once invalidated a run).

## Rules
- DO NOT use the client hotfix channel (`iProxy.sendHotfix` -> `tps.run_hotfix` exec) or any server->client code-execution path: the tool permission layer refused it and it was backed out.
- Don't commit `mitm/mitm_serve.py` / `mitm/captures/SERVE_B.txt`. Don't reboot LDPlayer; if the VM dies the user restarts it, then reapply the 5 iptables DNAT rules
  (tcp 80/443/8443, udp 25000/20013 -> 172.16.1.2 same port). One adb only: `C:\Users\Raysoo\Downloads\..` no — `C:\LDPlayer\LDPlayer9\adb.exe` (`ADB_PATH`).
- Git-Bash mangles backslashes in inline python: write scripts to files. Every change: live test -> notes (incl. negatives) -> atomic commit; replicate before claiming fixed.
