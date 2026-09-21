# Gate 6 plan — Store buy + every "draw" (lottery / supply box) — 2026-09-20

User goal: buying in the Store and every draw/gacha feature must work. Status: RESEARCH; nothing implemented yet.

## Verified facts
- The server DOES receive client bundles: `DECRYPTED (...)` lines in `mitm/local_baseapp_capture.py` output (an earlier "UPSTREAM RECV" grep was the wrong pattern).
  Decrypted bundle layout seen: `58 00` header then messages `[id 0xfa..0xfd][len uint16 LE][payload]`, payload = `[method-idx byte(s)][args]`
  (e.g. `fd 15 00 | 67 | 13 "AppearanceRecommend"` = method 0x67 with a length-prefixed string; `fb 05 00 | 0b 08 00 00 00` = method 0x0b, INT32 8).
  Those samples are telemetry-style calls, not mall/draw calls.
- Athlete method descriptor vector `EntityType[51]+0x160` = 1393 records of 0x68 bytes, std::string name at +0. Names (index in that vector) for the features to implement:
  buy: buyMallGood 517, buyMultipleMallGood 518, buySuitMallGood 519, buyMallGoodUseHallProp 520, giftMallGood 521/524, queryAvailableMallGoods 526,
  queryAvailableMallGoodsByType 527, queryAvailableMallGoodsForAppearanceMall 528, composeItem 271, requestDecompose* 269/270, buyRosMatchTeamMallGoods 703.
  draw: openSupplyBox 467, openSupplyBoxFree 468, openMultipleSupplyBox 469, kofOpenSupplyBox 304/305, requestDtsLTDoLottery 313/314, onDoLuckyLottery 897,
  onOpenLuckyCarnival 898, getLuckyTurnPropReward 1125/1283/1284, doRookie/Normal/AdvanceXmasActivity2020Lottery 1104-1106, requestDtsAprilFoolDoLottery 1222/1223,
  reqDrawHalloween2019Box 1232, requestSign3rdAnniversaryLottery 1061, playXmas2018Lottery 285, lotteryBet 576.
  Full list: `06_notes/athlete_base_methods_table.txt` (regenerate with `scratch/dump_athlete_base_methods.py 0x160`; needs a logged-in client).
- Client replies come back as client methods (server -> client) whose runtime indices are in `scratch/athlete_methods_full.txt` (dump_athlete_methods.py):
  e.g. `onQueryAvailableMallGoods`, `_showMallResult` path in `ui\UIMall.py`.

## UNKNOWN (must be derived, not guessed)
1. Which of the 1393 base methods are exposed to the client, and the wire method-id encoding for client->server calls (bundle header 0xfa..0xfd + index).
   The descriptor flags at +0x18 (6 vs 2) do not say "Exposed"; other candidate vectors: `+0x178` (3796 B = 949 ints), `+0x108` (208 B = 52 ints).
   Plan: press one known action (Store tab, supply box) with a packet log, correlate bundle payloads with the exposed index list.
2. Argument formats: use the def XML (`05_entities/out/Athlete.def.xml` + interface XMLs) and the runtime DataType tree (like `dump_runtime_types.py`).
3. Reply semantics: for draws, the reply RPC (result + reward list + updated currency/inventory) and which client method updates the inventory UI.
4. Goods/price tables for the mall and the drop tables for draws live in the client's data (script.npk / tables); the server must reproduce them (not guessed).

## Suggested order
1. Build the upstream decoder (bundle -> exposed index -> method name -> typed args) and log every client call with names. This also unlocks Gate 5 (START).
2. Store: answer `queryAvailableMallGoods*`, then `buyMallGood` (deduct currency by `onCurrencyUpdated`/`onYBUpdated` (201-204), add item).
3. Draws: `openSupplyBox*`, lucky carnival, then the event lotteries. Verify each with a live tap + logcat + inventory check; add peso pricing last.

## Supply box (draw) — findings 2026-09-20 (first slice)
- Live: SUPPLY opens a page with tabs STAR / SUPREME / LOOKS / VEHICLE / FIREARMS SUPPLY and a "DRAW 1x 100" + "Skip" overlay; the prize area is empty and tapping DRAW
  or Skip sends NOTHING to the server (0 non-keepalive bundles), no script error (`scratch/supply1..4.png`). The only bundle on open is a telemetry call
  (method byte 0x67, string "MallAdvancedSupplementVehicle").
- Why (scripts): `entities\iSupplement.py`. `availSupplementDict` (client attribute) is filled ONLY by the server RPC
  `onQueryAvailableSupplement(PYTHON availSupplementDict)` (entity_0315 client method, runtime idx 392 in the Athlete client-method table). The client then splits it by
  `supplement_utils.getSupplementKind(id)` (general/advance/vehicle/weapon/brave-book/month/kof/hero/anniversary/time-limit/blackFriday2020 dicts). With no
  reply the lists stay empty and the DRAW handler never sends. `Athlete.openSupplyBox` (client side, iSupplement) checks `availSupplementDict`, currency and coupons,
  then calls `self.base.openSupplyBox(...)` (base idx 467 in the 1393-entry table; also 468 openSupplyBoxFree, 469 openMultipleSupplyBox).
- Server replies the client understands (entity_0315 ClientMethods): `onOpenSupplyBox(INT32 supplementID, PYTHON appearanceIDs, BOOL isWatchAd)` idx 387,
  `onOpenFreeSupplyBox(INT32, PYTHON)` 388, `onMultiOpenSupplyBox(INT32, PYTHON)` 389, `onOpenSupplyBoxFailed(INT32, STRING, INT32, INT32)` 390,
  `onMultiOpenSupplyBoxFailed` 391, `onQueryAvailableSupplement(PYTHON)` 392.
- BLOCKER: supplement definitions (ids, kind, prices, probabilities, `PROP_ID_LIST`, guarantee lists) are read via `getSupplementData` -> `legacyProperties`, i.e. the
  client's `assets/data/properties` tables inside the OBB/NPK (not in script.npk). To build a correct `availSupplementDict` (keys = real supplement ids; value tuple shape
  unknown) and a drop table, we must extract those tables from the OBB (`main/patch.1117219.com.netease.chiji.obb`, ~3.4 GB; `04_obb/obb_extract` has 1.7 GB extracted
  but a grep for `SupplementData`/`SUPPLEMENT_LIST` found nothing, so the tables are compressed/serialised) or read them from the live process. Not guessed.
- Next: locate + decode `assets/data/properties` (see the client log line `[trouger] properties.init()... assets/data/properties`), dump the Supplement table, then
  (1) send `onQueryAvailableSupplement` with real ids after enterHall, (2) implement `openSupplyBox` (+ currency deduction via 201-204 and the item grant),
  (3) reply `onOpenSupplyBox`. Same table source is needed for the Store goods list (`MallGoods`) and prices/peso.

## Supply box — progress (2026-09-20, later)
- **Data tables found and readable:** APK `assets.npk` (NXPK, zlib members; index = header+0x14, 28-byte entries) holds the client tables as PLAIN-TEXT Python literals
  (`data = {id: {'type':..., 'value': {...}}}`), NOT the OBB. `tools/load_table.py` reads/dumps them (`--dump` -> `scratch/assets_dump/<sig>.bin`). Member signatures are a hash of the path
  (algorithm not yet identified: crc32/adler/fnv/murmur/djb2/sdbm/oat/bkdr all failed against script.npk pairs, see `scratch/find_npk_hash.py`); tables are identified by content:
  `9e1c8652` = `data_supplement` (248 supplement boxes: 121 OneSupplementBoxWithGuarantee, 114 AllSupplementBoxWithGuarantee, 7 OneSupplementBox, 1 AllSupplementBox; KIND values
  2,3,4,5,6,7,99,101,102,103,201,202, None). `ui` listing of table file names: member `5390b52a` (`data_mall_goods.py`, `data_lottery.py`, `data_mall.NN.py` ... present in that XML).
- **Upstream call decode (new):** decrypted client packet = `flags(2)` + messages `[id 0xfa..0xfd][len16][payload]` + `seq(4)`; payload[0] = exposed method index. Verified live:
  `fa 01 00 dd` = method 0xdd (221) with no args = `queryAvailableSupplement` (sent every time a Supply tab opens). `0x67` = telemetry(string), `0x2f` = UI-enter telemetry, `0x0f`, `0x20`, `0x7d` also telemetry-like.
  `mitm/local_baseapp_capture.py`: `parse_upstream_messages` / `handle_upstream_calls` log each new (method,len) as `UPSTREAM CALL: ...` and answer 0xdd with
  `Athlete.onQueryAvailableSupplement` (idx 392; payload = pickle-0 dict {supplementID: table record}, `ROS_SUPPLEMENT_PER_KIND`, default 2 per (type,KIND) = 22 records, 59.5 KB, fragmented fine).
- **Live result:** before the reply every Supply tab was empty and DRAW/Skip did nothing. After it, the STAR SUPPLY tab renders its real UI (DRAW 1x 288/2888 diamonds, DRAW 10x, FREE +10 star,
  star-ticket header) but both boxes show "敬请期待" (coming soon), so no supplement is selected and DRAW still sends nothing; SUPREME / VEHICLE / LOOKS stay blank and FIREARMS shows "DRAW 1x 1"
  with a Skip overlay (screens `scratch/tab_*.png`, `scratch/draw_star.png`). No script errors. So the reply channel works; the RECORD SET/SHAPE is still wrong for the per-tab filters
  (`generalSupplementFilter`/`advanceSupplementFilter`/`vehicleSupplementFilter` use `supplement_utils.getSupplementKind` against SupplementKindEnum whose numeric values are unknown).
- Next: (1) find `SupplementKindEnum` values (defined via a helper in `common/shared` consts) or bisect by sending one KIND at a time and noting which tab fills; (2) send ALL records of a
  kind (real server sends every online one) and check the boxes; (3) once a box is selectable, tap DRAW, capture the exposed index/args of openSupplyBox, implement it (deduct currency with
  onYBUpdated 203, pick prizes from SUPPLEMENT_LIST PROP_ID/PROBABILITY, reply onOpenSupplyBox 387 with appearanceIDs); (4) same approach for mall goods (data_mall_goods) and lotteries.

## Supply box — negative results & limits (2026-09-20, late)
- **A method message is capped at 65,535 bytes**: `send_entity_method` uses a 2-byte length for method index 392 (w1 = 58 < 64). Sending all 243 online records (706 KB pickled)
  failed with `OSError 10040` (datagram too large, and the length field would overflow anyway). Fragmenting (`send_mercury_message`) does not lift the per-message length cap; a longer
  variable-length form (escape value + wider length) is NOT verified. `ROS_SUPPLEMENT_SLIM=1` (default) keeps only scalar keys (+ small `CURRENCY_OPTION`); `ROS_SUPPLEMENT_PER_KIND` (default 2) limits records.
- **More/slimmer records did not fill any tab** (53 records, 42 KB, all KINDs, ids 1..; `scratch/sup4_tab*.png`): STAR still shows two "敬请期待" empty boxes, SUPREME/VEHICLE/LOOKS blank,
  FIREARMS shows "DRAW 1x 1". So record COUNT/SIZE is not the blocker.
- What the STAR page does (`ui\UISupplyPackage.py`): `onQueryAvailableSupplement(availSupplement)` -> `sorted(availSupplement.keys())` -> assigns up to two boxes (`box1`, `box2`) ->
  `_initBoxWidget(boxName, supplementID, supplementInfo)` which picks a handler by `supplement_utils.getSupplementKind(supplementID)`: NORMAL_SUPPLEMENT -> `_initBoxWidget_generalBox`,
  TIME_LIMIT_SUPPLEMENT -> `_initBoxWidget_timeLimitBox`, WEAPON_SUPPLEMENT -> ..., otherwise `_initBoxWidget_emptyBox` (the "coming soon" box we see). `getSupplementKind` reads
  `getSupplementData(id)['KIND']` from the client's own tables (`legacyProperties`), and the numeric values of `SupplementKindEnum` are created by `initEnums` (not readable statically).
  Hypotheses to test: (a) the dict handed to the page is pre-filtered by `iSupplement.generalSupplementFilter` and none of our ids maps to NORMAL/TIME_LIMIT because the KIND the client sees
  differs from the KIND in `data_supplement`; (b) `legacyProperties` supplement data is not loaded in this client state; (c) values must contain extra dynamic keys added by the real server.
- **Tooling gap:** the disassembler (`tools/script_disas.py` / `scratch/disassemble_targets.py`) has an incomplete NeoX opcode map (opcodes 160 etc. unresolved, garbled listings), so function bodies
  cannot be read; only NAMES/CONSTS are reliable (`scratch/dump_code_consts.py <file> <funcs>`). Completing the opcode map (e.g. by aligning known stdlib modules that are also in script.npk with
  their public Python 2.7 bytecode) would let us read `getSupplementKind`, `_initBoxWidget`, `iSupplement.onQueryAvailableSupplement` exactly and stop guessing. This is the recommended next step.

## Supply box — continuation (2026-09-20, opcode + record-shape pass)
- Corrected the disassembler for this client build enough to read the blocker functions. The previous legacy NeoX permutation was wrong for this build. `_initBoxWidget` dispatches NORMAL to `_initBoxWidget_generalBox`, and both TIME_LIMIT and WEAPON to `_initBoxWidget_timeLimitBox`. `iSupplement.onQueryAvailableSupplement` filters the incoming dict by the client table's `KIND` before forwarding each dict to its active page.
- Both box initializers read dynamic server fields `NAME`, `CURRENCY_ID`, `BUY_TIMES_PRICE`, `CURRENT_DISCOUNT`; `_selectBox` additionally reads `BUY_MULTIPLE_TIMES_PRICE`. The raw `data_supplement` row only contains the nested `CURRENCY_OPTION` variant. Added `_supplement_runtime_record` to flatten all three currency-option variants found in the table and apply the schema-declared `KIND` default `1`. Unit evidence: id 1 normalizes to `CURRENCY_ID=(2,202)`, `BUY_TIMES_PRICE=(5,50)`, `BUY_MULTIPLE_TIMES_PRICE=(50,500)`; the 21-record slim payload is 16,981 B.
- **Negative live result (`codex_shape1`, five tabs):** reply arrived on every tab and flattened price/currency variants rendered, but STAR still showed two "coming soon" boxes; SUPREME/LOOKS bodies remained blank; VEHICLE/FIREARMS showed draw controls without box content. Tapping DRAW on the live FIREARMS page produced no upstream call. Fresh-login count was 1 SCRIPT ERROR, the already-known `_loadDefaultScene -> SetLoadingProcess` timing race; no Supply traceback. Screens: `scratch/codex_shape1_tab280.png` through `tab695.png`.
- Therefore the raw-vs-flattened record shape was a real defect but is not the remaining selection blocker. Next evidence needed: exact live `SupplementKindEnum` values / runtime `legacyProperties.getSupplementData(id).KIND` for the candidate ids, or a controlled one-id probe, before changing the record set again.

## Supply box — ground truth from the corrected disassembler (2026-09-20, Claude)
- `SupplementKindEnum` values (module-level `initEnums` defaults in `common/shared/shared_const.py`, read with `tools/script_disas.py ... '<module>'`, run with `PYTHONIOENCODING=utf-8`):
  NORMAL=1, TIME_LIMIT=2, GUARANTEE=3, GUARANTEE_VEHICLE=4, WEAPON=5, BRAVE_BOOK_CHEST=6, MONTH=7, WHIS_POOL=8, KOF=99, HERO=9, SPRING_FESTIVAL_MONTH=10,
  ANNIVERSARY_CLOTH=101, ANNIVERSARY_WEAPON=102, ANNIVERSARY_VEHICLE=103, THIRD_ANNIVERSARY=201, BLACK_FRIDAY_2020=202. Table rows without `KIND` default to 1 (schema default).
- Tab -> filter (iSupplement.onQueryAvailableSupplement, `dict(filter(<x>Filter, availSupplementDict.items()))` over `(id, value)` tuples, id = tuple[0]):
  STAR = general (KIND 1,2), SUPREME = advance (3), VEHICLE = vehicle (4), FIREARMS = weapon (5), MONTH = 7, etc. The filter calls `supplement_utils.getSupplementKind(id)` =
  `legacyProperties.getSupplementData(id).KIND` (or -1 when the data object is falsy).
- `UISupplyPackage.onQueryAvailableSupplement`: sorts ids, splits by `getSupplementIsPreviousBox` (previous-box list vs current list), fills `box1` / `box2` from the CURRENT list with
  `_initBoxWidget(name, id, info)`; unknown kind -> `_initBoxWidget_emptyBox` = the "敬请期待" (coming soon) box we see.
- Data check (`tools/load_table.py`, member `9e1c8652`): the only current (IS_PREVIOUS_BOX unset) general boxes are id 1 (OneSupplementBox, KIND 1) and id 2 (AllSupplementBox, KIND 2) -> exactly box1/box2.
  They are in every payload we sent, yet STAR shows two empty boxes. So the most likely cause is that `legacyProperties.getSupplementData(id)` is falsy/None in this client (kind -1 -> emptyBox), NOT the
  record shape or size. `getSupplementData` is not defined in any script (generated by the `properties` loader `common/shared/lib/gametoolslib/properties/__init__.py`, which loads `data_*`/`types_*` files in FIRST_LOAD stages).
- NEXT diagnostic (not done yet): confirm what the client's properties loader has for supplements. Options: (a) find how the loader locates `data_supplement` (DataPath / ResourceManager, tables vs properties dir,
  `assets/data/tables_beta`) and whether our patched/empty hash check leaves it unloaded; (b) an in-client probe: the client contains a debug Python console (`ui\UIDebugCommand`, opened via `UIDebugEntrance`, F6 key does
  nothing in the hall) — enabling it would let us run `legacyProperties.getSupplementData(1)` directly; (c) read the live Python object from process memory.
- Also observed: pressing F6 (adb keyevent 135) in the hall does nothing; `systemJumpPanel` (Athlete client method idx 1096) has no script implementation in the index; `iGMAdmin` is anti-cheat/log upload, not code execution.

## Supply — negative result: reply delay is NOT the cause (2026-09-20, late, Claude)
- Added `ROS_SUPPLEMENT_REPLY_DELAY` (seconds; the `queryAvailableSupplement` reply is sent from a timer). With 0.7 s delay and 53 records (44,380 B) the STAR tab STILL shows two "敬请期待" boxes and
  the other tabs stay blank; no script error (screens `scratch/now1.png`, `scratch/now2.png`; the auto-tab screenshots `sup5_tab*.png` are INVALID — the user navigated during the run and they show the Profile page).
- Remaining hypothesis: `legacyProperties.getSupplementData(id)` is falsy in this client (kind -1 -> emptyBox). Verified facts: ids 1 (kind 1) and 2 (kind 2) are the only current general boxes and
  are always sent; `_initBoxWidget` -> `kind2HandleFunc[kind]` (NORMAL/TIME_LIMIT/WEAPON) else `_initBoxWidget_emptyBox`. `properties.init(data_path)` uses `ResourceManager.openSection` on the
  `assets/data/properties` tree (in assets.npk: `data/properties/supplement/data_supplement.py` exists). Whether the loader (lazy: `lazyInitAsync` from `UILogin._delay_on_enter`) actually loaded
  supplement data is unknown. Next: read `properties.load_all_data_modules` / `lazyInit` bodies with the corrected disassembler and check what `is_lazy`/`FIRST_LOAD_STAGE*` skip; or probe the live
  Python object (memory) for `legacyProperties` module dict; or bring up the debug console (`ui\UIDebugCommand`).

## Diagnostic idea NOT pursued (2026-09-20): client hotfix channel
- `iProxy.sendHotfix(INT32 proxyID, STRING md5, STRING hotfix)` (client method idx 11) -> `tps.onProxyDataDownloadComplete` -> `cPickle.loads(zlib.decompress(hotfix))` -> `tps.run_hotfix(source, md5, compiled)`
  = `compile(source,'hotfix','exec')` + exec in `__main__` (when proxyID == `const.PROXY_KEY_HOTFIX`, value not read; `PROXY_KEY_HOTFIX_COMPILED` variant uses marshal). It would let us run read-only
  probes inside the client (e.g. `legacyProperties.getSupplementData(1)`), but it is a server->client code-execution path, the tool permission layer refused it, and it was backed out (nothing committed).
  Safer alternatives to identify why the Supply boxes are empty: read `properties.load_all_data_modules` behaviour statically, inspect process memory, or ask the user to enable the client's own debug console.

## Supply — ROOT CAUSE FOUND: oversize datagram (2026-09-21, Claude) — STAR tab now works
- The `onQueryAvailableSupplement` reply was sent by `send_entity_method` as ONE UDP datagram (44-59 KB). The client drops any datagram above ~1472 B (Checkpoint 20:
  `EncryptionFilter::recv` illegal wastage), so the reply was NEVER processed although the server logged "replied". All the record-shape/size/timing/KIND experiments were therefore meaningless.
- Fix: `send_entity_method` now routes any call with `1+len(lenfield)+len(payload) > 1468` through `send_mercury_message` (fragment bundle, like createBasePlayer). 44 KB -> 31 fragments.
- LIVE: STAR SUPPLY now renders fully (STAR SUPPLY + ELITE SUPPLY boxes, item previews, "Previous" button, DRAW 1x 5/50, DRAW 10x 50/500) with 53 slim records (`scratch/sup6_tab280.png`).
- Disassembler fixes (`scratch/disassemble_targets.py` DEC map): 32=ROT_TWO, 58=STORE_SUBSCR, 103=JUMP_ABSOLUTE, 33=POP_BLOCK; `UISupplyPackage.onQueryAvailableSupplement` is now fully readable
  (sorted by `getSupplementSortKey`, previous-box split by `getSupplementIsPreviousBox`, boxes filled with `_initBoxWidget`). Tools: `scratch/raw_code.py`, `scratch/module_lists.py`, `scratch/find_list_const.py`, `scratch/memgrep.sh` (memory scan: NOT useful, script strings are not stored plainly).
- Remaining: SUPREME/LOOKS/VEHICLE/FIREARMS tabs, then DRAW (`openSupplyBox`).

## Supply DRAW works (first slice) — 2026-09-21
- Live decode: DRAW sends exposed method `0xda` = `openSupplyBox` (base idx 467), args `INT32 supplementID, INT32 currencyID, ARRAY<INT32> (4-byte count), BOOL`; DRAW 10x sends `0xdc` = `openMultipleSupplyBox`
  (469). Wire method index = base index - 249 in this region (queryAvailableSupplement 470 -> 0xdd, both live-verified); 468 openSupplyBoxFree -> 0xdb.
- Server (`handle_upstream_calls`): replies `onOpenSupplyBox(INT32 id, PYTHON prizeList, BOOL)` idx 387 / `onMultiOpenSupplyBox(INT32 id, PYTHON prizeList)` idx 389. Prize ids = random choice among the record's
  own `GUARANTEE_LIST[].GUARANTEE_PROP_ID` and `SUPPLEMENT_LIST[].PROP_ID` (real drop weights are in the prop-group tables, not decoded). Records also carry `NEXT_BUY_TIMES_PRICE` (read by `_showSupplementResult`).
- LIVE (`scratch/dr1_after1.png`): the result screen renders with real names/models (Dark Hood, Red Hood, Flyswatter - Dark Scissors, Bacpack - Bloody Hand Lv.3, plus two placeholder Chinese box names) and "Buy Another 95".
  The client re-sent the call (3 replies for 1 tap) — retransmission handling not yet checked. NOT done: currency deduction, inventory grant, free draw (0xdb), stats/guarantee counters.
- Remaining Supply tabs: SUPREME (black), LOOKS (white), VEHICLE (needs "Skip" intro tap) — next.

## Supply tabs status (2026-09-21, live, `scratch/tab_test.sh`, screens `scratch/tb2_tab*.png`, `scratch/clean_*.png`)
- WORKING: **STAR** (kinds 1/2: STAR + ELITE boxes), **LOOKS** (Aurora, DRAW 300/2880), **VEHICLE** (Angel of Darkness, DRAW 30/270), **FIREARMS** (Red Hood, DRAW 10/95). DRAW 1x/10x replies render real result screens
  (names/models from the client's own tables). VEHICLE needed the CURRENT (non-previous) boxes: the server now always sends every `IS_PREVIOUS_BOX`-unset record of each KIND and only `ROS_SUPPLEMENT_PER_KIND` previous ones.
- The "Skip" button seen on VEHICLE/FIREARMS pages is the same screen position as DRAW 10x: tapping it blindly performs a 10x draw. Do not tap it in automated tests (tab_test.sh no longer does).
- NOT WORKING: **SUPREME** = `UIMonthlySupplyPackage` (KIND 7 monthly supply). It is blank/black because `supplement_utils.getCurrentMonthSupplementID()` uses the DEVICE clock against
  `data_month_supplement_param` (`assets.npk` members `5c64e12a`, `462e4a27`), whose latest END_TIME is 2021.12.30 (id 9765) — no month is "current" in 2026. Not fixable from the server RPCs.
  Options (none done): (a) set the emulator clock to <= 2021-12 (breaks TLS: our server cert `mitm/srv.crt` and CA V3 are valid only from 2026-09-12; would need a re-issued CA/cert valid back to 2018 and re-installing the CA on the device);
  (b) serve a patched `data_month_supplement_param` through the client's patch/resource path; (c) accept as a time-limited event.
- Also seen: a running emulator can go black and vanish from adb (LDPlayer VM dies); the user restarts it; then re-apply the 5 iptables DNAT rules.
- Still TODO for draws: currency deduction (`onYBUpdated` 203), inventory grant, free draw (0xdb), guarantee counters, real drop weights, retransmitted duplicate calls (client sent the same draw 3x).

## Supply: ALL events (incl. ended) now shown — 2026-09-21
- `supplement_avail_payload` now sends ALL 248 records of `data_supplement` (no online/offline/in-sale filter, no per-kind cap; `ROS_SUPPLEMENT_ALL=0` restores the old filtered mode) using only the 11 fields the UIs read from the server dict
  (NAME, CURRENCY_ID, BUY_TIMES_PRICE, NEXT_BUY_TIMES_PRICE, BUY_MULTIPLE_TIMES_PRICE, CURRENT_DISCOUNT, KIND, IS_PREVIOUS_BOX, SORT_KEY, PURCHASE_LIMIT_NUM, CONTINUE_LOTTERY_TIMES): 39,368 B, under the 65,535 B method limit
  (one message; fragmented over ~27 packets).
- LIVE: STAR / LOOKS / VEHICLE / FIREARMS still render; the "Previous" panel now lists many old events (VEHICLE: Classic Wedding Car, Hovering Car, Summer Bicycle, Fiery Hunting, Sparrow, Orca ...,
  scrollable) instead of two (`scratch/prev_open.png`). A page can show white for ~20-30 s while its 3D scene loads.
- SUPREME (monthly) still blank: needs a "current month" by device clock (see previous section).

## Draw prizes: containers no longer shown (2026-09-21)
- User saw container items after FIREARMS/VEHICLE draws ("小红帽礼盒（打包）", "Classic Supply (2021.02.03)", "全载具随机"). Cause: the pool included consolation entries (currency, tickets, fragments, packed gift boxes).
- Prop tables (assets.npk): `5081e268` chest props (RandomItem/GiftBag), `c656e064` general props (CurrencyPropType, Fragment, MultiUseProp, GiftBag, head/frame/nameplate...), `a2f095a2` clothes/body/decoration, `190f0c0a` weapon skins,
  `b8749560` vehicle appearance (e.g. 142058), `8f4932f0` battleground prop appearance (103982). `mitm/local_baseapp_capture.py`: `_expand_prop` opens RandomItem (weighted) and GiftBag (all entries);
  `ROS_DRAW_COSMETIC_ONLY=1` (default) rerolls (<=40x) any result containing CurrencyPropType/Fragment/MultiUseProp/BravaBook*/DtsHeroPropType/CrazyCarnivalPropType. `scratch/prize_audit.py`: 240 draws over boxes 1/15/105/9329
  -> only appearance types (a few GiftBag/BigSpeaker for box 1). Live server log: FIREARMS 1x -> `[1112323]`, `charged 10 diamonds -> balance 999809`. (Screenshots of that run are invalid: blind taps hit the controls screen/daily popup.)

## Inventory grant, first slice (ChatGPT implemented, Claude live-verified server side) — 2026-09-21
- `grant_appearance_prizes` (mitm/local_baseapp_capture.py): after each draw, persist prizes in `data/player_inventory.json` (uuid/number/info{'ex_tm':0}/layout per item id), send
  `onAddDtsAppearanceItem(ITEM_ID, ARRAY<ITEM_DATA_CONVERT{uuid BLOB, number INT32, info PY_DICT, layout INT32}>, INT32 itemSrc, INT32 number)` (client idx 335) and `onUpdateRecentGotPropIDList` (340),
  then regenerate the createBasePlayer stream (`scratch/gen_stream_v3.py` now encodes `dtsAppearancePackage.itemList` = ITEM_DATA3{uuid, itemID, number, info}) so the inventory survives re-login.
  Decrypted client body requires `changedItemList[0].info['ex_tm']`.
- LIVE (dw4 run): draws persisted 9 item ids, stream regenerated each time (no server error), and no client script error / datatype error in logcat after the draws. NOT yet verified: that the items really show in Depot / can be equipped
  (the run's screenshots are invalid — blind taps landed on the daily-login popup). Next: open Depot > Looks after a draw and after re-login.
