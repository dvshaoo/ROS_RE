# Handoff to ChatGPT — Draw inventory/currency, Equip, female character, SUPREME supply (2026-09-21)

Written for: an engineer/agent continuing the ROS (com.netease.chiji, Android arm64) LAN private-server project with no prior context.
Read first: `CLAUDE.md`, `06_notes/HANDOFF_TO_CHATGPT_STORE_DRAW.md` (tools/how to run), `06_notes/GATE6_BUY_AND_DRAW_PLAN.md` (all findings, newest at the end).
Rules: local/LAN only, zero guesswork (decrypted scripts / live memory / Ghidra), live test -> notes (incl. negatives) -> atomic commit; do not commit `mitm/mitm_serve.py` /
`mitm/captures/SERVE_B.txt`; do not reboot LDPlayer (if the VM dies the user restarts it, then re-apply the 5 iptables DNAT rules tcp 80/443/8443, udp 25000/20013 -> 172.16.1.2);
do NOT use the client hotfix channel (`iProxy.sendHotfix`); one adb `C:\LDPlayer\LDPlayer9\adb.exe`; write scripts with backslashes to files (Git-Bash mangles them); the user must not touch the emulator during scripted tests.

## What works now (all committed; last commits 69c25ab + this session's)
- Login -> lobby, 0 script errors. Supply page: STAR / LOOKS / VEHICLE / FIREARMS tabs render from `onQueryAvailableSupplement` (ALL 248 `data_supplement` records, 11 fields, 39 KB, fragmented — the client DROPS datagrams > ~1472 B;
  `send_entity_method` now fragments big calls). "Previous" lists all old events.
- Draw: `openSupplyBox` (wire 0xda, base 467) / `openMultipleSupplyBox` (0xdc, 469) are answered by `handle_upstream_calls` with `onOpenSupplyBox` (client idx 387) / `onMultiOpenSupplyBox` (389).
  Prizes: pool = box GUARANTEE_LIST + SUPPLEMENT_LIST prop ids, each EXPANDED through the weighted `RandomItem` containers of the hall-prop table (assets.npk member `5081e268`, `_expand_prop`), so results show real items (verified live on LOOKS: Aurora dress, Ocean Camo parachute, hair).
  Diamonds: cost from `CURRENCY_OPTION` -> `onYBUpdated` (idx 203) with dev balance kept in `_dev_yb` (needs live verification).

## TODO (user's requests, priority order)
1. **Inventory grant after a draw.** Prizes are only displayed; nothing is added. The client entity `iDtsAppearancePackage` (entity_0464) has base method `addDtsAppearanceItem(INT32, INT32, PYTHON, INT32)` (server side) and CLIENT methods
   `onAddDtsAppearanceItem(ITEM_ID, INT32, INT32, ITEM_ID, ITEM_UUID, ITEM_ID)` (runtime idx 335), `onUpdateDtsAppearanceItemNumber` (339), `onUpdateRecentGotPropIDList` (340), `onDelDtsAppearance*`. Property `dtsAppearancePackage` (DTS_APPEARANCE_PACKAGE3, stream idx 242) holds `itemList`/`layoutInfo`.
   Need: what an item record/ITEM_ID/ITEM_UUID look like (see `entities\iDtsAppearancePackage.py` names via `python tools/script_query.py entities/iDtsAppearancePackage.py ""`, and the DEF `ITEM_ID`/`ITEM_UUID` types in `05_entities/out/entities_types_0x32DEC.xml`), then send `onAddDtsAppearanceItem` per prize and keep a server-side inventory so a re-login keeps it (write to a JSON file; the createBasePlayer stream can carry `dtsAppearancePackage`).
2. **Currency deduction check.** Draw 10x on LOOKS uses currency id 9 (COLOUR_DIAMOND, top-bar shows a colour-diamond counter "0"). Only YUANBAO(2) is charged now; add `onCurrencyUpdated` (idx 204, `INT32 id, INT64 val, INT32 src`) for other ids, and check the header balance changes after a draw (`scratch/draw_test2.sh`).
3. **Equip clothes.** Item wear/equip flow: client method `onNotifyEquipedAppearance` (idx 356) / `onNotifyEquipAppearanceFailed` (358) and lists `onUpdateDtsWearableAppearanceList` (344) etc.; UI: Depot (`ui\UIDtsAppearance*`). Find the exposed base call the Depot sends (`UPSTREAM CALL` log lines), mirror the real server reply (`tools/script_disas.py` on `entities/iDtsAppearance*.py`).
4. **Female character.** `Athlete.updateBaseCharacter(INT32 charType)`: 10002 = male, 10005 = female (CLAUDE.md sect. 4); currently fixed at `ROS_BASE_CHAR_TYPE` default 10002 in `send_character_creation_response_chain`. Try 10005 (env `ROS_BASE_CHAR_TYPE=10005`) and check the hall model + equip/appearance load; the user reports the female character is broken.
5. **SUPREME SUPPLY (monthly, KIND 7) shows a black page.** `UIMonthlySupplyPackage` calls `supplement_utils.getCurrentMonthSupplementID()` = device clock vs `data_month_supplement_param` (assets.npk `5c64e12a`, `462e4a27`), latest END_TIME 2021.12.30, so nothing is "current" in 2026.
   Ideas: patch the table the client loads (`legacyProperties.iterMonthSupplementParamData`; the client reads assets.npk from `/sdcard/Android/data/com.netease.chiji/files/netease/h45na/assets.npk`, identical to the APK copy, md5 44d291cc...) with an entry whose START/END covers today, or re-issue the MITM CA/cert valid back to 2018 and set the emulator clock to 2021. Not tried.
6. Remaining draws: free draw (0xdb), Lucky Carnival (897-908), event lotteries (see GATE6 plan list), Store (`queryAvailableMallGoods*` 526-528, `buyMallGood` 517-521), daily claim (388 gold), Gate 5 START -> island (`GATE5_START_TO_ISLAND_PLAN.md`).

## Practical
- Server: `ROS_ATHLETE_USE_STREAM_FILE=1 ROS_AUTO_ENTER_HALL=1 ADB_PATH=C:\LDPlayer\LDPlayer9\adb.exe python -u mitm\local_baseapp_capture.py > scratch\server_redpoints.out` (force-stop the game before restarting the server).
- Tests: `scratch/tab_test.sh <label>` (all tabs), `scratch/draw_test2.sh <label>` (STAR + LOOKS 10x draws). The "Skip" button on VEHICLE/FIREARMS pages is at the position of DRAW 10x — never tap it blindly. Pages can be white for 20-30 s while 3D scenes load.
- Decrypt/inspect client scripts: `PYTHONIOENCODING=utf-8 python tools/script_disas.py '<path>' <func>`; names/consts via `tools/script_query.py`, `scratch/dump_code_consts.py`, `scratch/find_callers.py`; tables: `tools/load_table.py`.
