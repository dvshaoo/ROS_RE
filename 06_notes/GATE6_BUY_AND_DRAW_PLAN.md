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
