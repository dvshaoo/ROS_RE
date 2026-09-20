# Handoff to ChatGPT — Store buy, Supply/draws, remaining hall items (2026-09-20)

Written for: an engineer/agent continuing the ROS (com.netease.chiji, Android arm64) LAN private-server project with no prior context.
Read first: `CLAUDE.md` (standing rules: local/LAN only, zero guesswork — verify by live memory / decrypted scripts / Ghidra, commit often, update notes with every change + live test,
record negative results, never claim fixed from one run), then this file, `06_notes/GATE6_BUY_AND_DRAW_PLAN.md`, `06_notes/HALL_NAVIGATION_CHECKLIST.md`,
`06_notes/GHIDRA_PACKET_PARSER_TRACE.md` (Checkpoints 20g-20j at the end).

## State (all committed, last commits 0c58ba9 / 46f834b)
- Login -> BaseApp -> Athlete lobby works with ZERO script errors on a fresh login (only a harmless `_loadDefaultScene ... SetLoadingProcess` timing race sometimes). Root cause of the old messy hall was
  `UIMain.on_enter` aborting on two BASE-only attributes; fixed by sending `onPersonalRecommendStateUpdated` (idx 754) and `syncMonthPayRebateSpecialAwardInfo({'awards': {}})` (idx 768).
- Top bar: diamond = freeYuanbao+payYuanbao, coin slot = `currencyList` id 213; dev balance 999999/999999 set in `scratch/gen_stream_v3.py` (regenerate `data/athlete_mobile_stream.bin` after edits).
- Nickname `Dev | Raysoo` (`ROS_BASE_NICKNAME`). The new-player guide overlay clears with one tap on START.
- Tools: `tools/script_index.py|script_query.py|script_disas.py` (decrypt/search client scripts; disassembly OPCODES ARE UNRELIABLE — only names/consts are), `scratch/dump_code_consts.py`,
  `tools/load_table.py` (client data tables from APK `assets.npk`, plain-text Python literals), `scratch/dump_athlete_methods.py` (client-method table, idx = wire index),
  `scratch/dump_athlete_base_methods.py` (1393 base methods, `06_notes/athlete_base_methods_table.txt`), `scratch/fresh_run.sh`, `scratch/supply_test.sh`.
- Server: `mitm/local_baseapp_capture.py`. It now decodes client bundles (`parse_upstream_messages`: `flags(2)` + `[id 0xfa..0xfd][len16][payload]` + `seq(4)`; payload[0] = exposed method index)
  and answers exposed method 0xdd (= `queryAvailableSupplement`) with `onQueryAvailableSupplement` (client idx 392).

## Open problems (priority order)
1. **Supply page tabs empty / DRAW does nothing.** The reply reaches the client (STAR tab now shows DRAW prices) but the boxes stay "敬请期待" (coming soon) and DRAW sends nothing.
   `UISupplyPackage._initBoxWidget` chooses a handler from `supplement_utils.getSupplementKind(id)` (NORMAL/TIME_LIMIT/WEAPON...); the numeric `SupplementKindEnum` values are built by `initEnums`.
   Blocker: cannot read function bodies. **Recommended first task:** finish the NeoX opcode map for the disassembler (align stdlib modules present in `04_obb/extracted/script.npk` with their public Python 2.7
   bytecode; the partial map is in `scratch/disassemble_targets.py` ENC/DEC). Then read `getSupplementKind`, `_initBoxWidget`, `iSupplement.onQueryAvailableSupplement`, the `*SupplementFilter`s
   and fix the record set/shape. Limits: one method message <= 65,535 B (2-byte length); `ROS_SUPPLEMENT_PER_KIND`, `ROS_SUPPLEMENT_SLIM` control what is sent.
2. **openSupplyBox / draws:** once a box is selectable, press DRAW, capture the new `UPSTREAM CALL` line (method index + args), map it to the base table (openSupplyBox 467, openMultipleSupplyBox 469,
   free 468), implement it (deduct currency with `onYBUpdated` 203 / `onCurrencyUpdated` 204, choose prizes from the record's SUPPLEMENT_LIST PROP_ID/PROBABILITY in `data_supplement`
   (assets.npk member `9e1c8652`), reply `onOpenSupplyBox(INT32 id, PYTHON appearanceIDs, BOOL)` idx 387 / `onMultiOpenSupplyBox` 389 / failures 390-391), then the other draws
   (Lucky Carnival 897-908, `requestDtsLTDoLottery` 313/314, `getLuckyTurnPropReward` 1125/1283/1284, Xmas/April-fool/Halloween lotteries; list in GATE6 plan).
3. **Store:** SUGGESTED/PACKS/LOOKS tabs empty, FIREARMS lists items but skin purchase fails, TOP-UP shows "USD" (should be PHP). Same method: capture the upstream call, answer
   `queryAvailableMallGoods*` (526-528) and `buyMallGood` (517-521) from the client tables (`data_mall_goods`, `data_mall.NN`; find member sigs by content, the path hash is unknown).
4. **Daily login popup:** "388 Gold Claimable" cannot be claimed (needs the claim upstream call + reply).
5. **Gate 5 (START -> island, no timer/plane):** see `06_notes/GATE5_START_TO_ISLAND_PLAN.md` (`matchBattleGround` 96 -> `transferToBattleServer` -> BattleAccount/Avatar).
6. Other: Depot 2nd Back crash (`refreshTransformPanel` None), My Page `ID: 0`, RushHour banner, non-root/LAN beta readiness (server currently finds the session key via root memory scan).

## 2026-09-20 continuation: opcode-map correction (verified)
- The old `scratch/disassemble_targets.py` permutation was from a different NeoX build and silently produced plausible but false listings (for example it decoded the argument load in `getSupplementKind` as `RAISE_VARARGS`). Do not use that legacy permutation.
- Verified this client's anchors from small, structurally unambiguous functions: NeoX `93=LOAD_FAST`, `155=LOAD_GLOBAL`, `96=LOAD_ATTR`, `131=CALL_FUNCTION`, `104=STORE_FAST`, `148=POP_JUMP_IF_FALSE`, `74=RETURN_VALUE`, `23=BINARY_SUBSCR`, plus fused `94=LOAD_CONST+RETURN_VALUE` and fused `160=LOAD_FAST(varnames[oparg>>8])+LOAD_ATTR(names[oparg&0xff])`. `57=POP_TOP`, `66=BINARY_MODULO`, and `77=STORE_MAP` were then verified in `_initBoxWidget`.
- `tools/script_disas.py` now caches filename -> NPK signature in `scratch/script_module_sigs.json`; repeat queries take about one second instead of decrypting the whole NPK for roughly two minutes. Importing the disassembler no longer runs its old Athlete ad-hoc main routine.
- Readable ground truth now obtained: `getSupplementKind(id)` returns `legacyProperties.getSupplementData(id).KIND` or `-1`; `iSupplement.onQueryAvailableSupplement` splits the incoming dict with per-kind filters; `UISupplyPackage._initBoxWidget` accepts only NORMAL, TIME_LIMIT and WEAPON and otherwise uses its empty-box path.

## Rules of the road
- Every change: live test -> notes (include negative results, correct wrong old claims) -> atomic commit. Replicate before claiming fixed.
- Do NOT commit `mitm/mitm_serve.py` or `mitm/captures/SERVE_B.txt` (Gemini's unreviewed edits). Do NOT reboot LDPlayer; if the VM dies the user restarts it, then reapply
  `iptables -t nat` DNAT (tcp 80/443/8443, udp 25000/20013 -> 172.16.1.2 same port).
- Use ONE adb: `C:\LDPlayer\LDPlayer9\adb.exe` (`ADB_PATH`). Git-Bash mangles backslashes in inline python: write scripts to files. Screen taps are landscape 1920x1080.
- Start server: `ROS_ATHLETE_USE_STREAM_FILE=1 ROS_AUTO_ENTER_HALL=1 ADB_PATH=... python -u mitm\local_baseapp_capture.py > scratch\server_redpoints.out`
  (force-stop the game before restarting the server). Test loop: `scratch/supply_test.sh <label>` (fresh login, clear guide, open Supply, screenshot each tab, print upstream calls + script errors).
