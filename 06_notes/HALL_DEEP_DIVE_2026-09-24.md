# HALL LOBBY DEEP DIVE — static-only map (no game run required)

> Date: 2026-09-24
> Method: `tools/script_query.py` over `scratch/script_index.txt` (1.4M lines, decrypted `script.npk` names/consts) + `scratch/athlete_methods_full.txt` (1131 live methods, type 51) + `05_entities/out/*.xml` DEFs + `mitm/local_baseapp_capture.py` (server impl).
> Note: `UIMain.py:1265/1594/2453`, `Athlete.py:275/365/656`, `iWeekendPush.py:66` line numbers are live-logcat traceback citations from notes, not decrypted source. Opcodes from `script_disas.py` are unreliable; names/consts/widget paths are reliable.
> Query recipe (slash vs backslash matters — use bare lowercase): `python tools/script_query.py uimain anchor`, `python tools/script_query.py uisupplycontroller btn`, `python tools/script_query.py uimallcontroller btn`, `python tools/script_query.py uimodes "solo|dual|start|hallTeamData"`.

Related: `06_notes/HALL_NAVIGATION_CHECKLIST.md`, `06_notes/GHIDRA_PACKET_PARSER_TRACE.md` (Cp14/18/20/20d/20j), `scratch/STORE_AND_SUPPLY_ISSUES.md`, `06_notes/GATE5_START_TO_ISLAND_PLAN.md`, `06_notes/GATE6_BUY_AND_DRAW_PLAN.md`, `06_notes/LUCKY_CARNIVAL_COMING_SOON.md`.

---

## 0. Lobby entry chain (keep this order)

```
showSelectCharacter([]) [1083]  -- struct.pack('<I',0), creates Scene GameObject via _loadDefaultScene()->HALL_BASE_SCENE
 -> onCreateCharacter(True,"") [1084]
 -> onRoleCreateSuc(10002=MALE / 10005=FEMALE) [1085]
 -> updateBaseCharacter [1087] -> updateBaseNickname("Survivor") [1088]
 -> enterHall(True) [1091] -> _realEnterHall (Athlete.py:656 GameObject.Find('Scene').GetComponent('SceneSystem').loadHallScene)
 -> UIMgr.py:967 enterHallUI -> UIMain.on_enter -> UIModes.on_enter (405) -> _refresh_members (627) -> _init_ui_visibilities (636)
```

* Wire: Athlete 1131 methods → `div=(1131+192)/255=5, threshold=57, msgID=128+w1, width=2B if w1<64 else 1B` (CLAUDE.md §5).
* `showSelectCharacter` DEF: `05_entities/out/Athlete.def.xml:826 ARRAY<STRING>`; `enterHall:852 BOOL`; `transferToBattleServer:860 (STRING,INT32,KEY_NAME,BLOB,UINT32)`.
* `onCreate` chain over 143 interfaces via `safesuper`: `iHallTeam.py:45 hallTeamData={}`, `Athlete.py:365 timerRefreshMSToken=None`. `iWeekendPush.py:66 set(rewardsCanGet)-set(weekendPushRewardsHaveGotten=None)` aborts the whole chain if the stream leaves that prop as None → both attrs missing → `onBecomeNonPlayer:445` crash → `App CMD 31`. Fixed by v3 stream (`scratch/gen_stream_v3.py` → `data/athlete_mobile_stream.bin`, 454/832 props, fragment ~1459B).
* `onBecomePlayer:275 extconfigs.getServiceAccessPoint:50 TypeError None['__getitem__']` aborts rest of init → avatar refresh skipped. Visiting Rank/Depot re-runs `displayAll` → avatar appears. This is PRIORITY 0 (avatar-missing-until-Ranked).
* Stage order in `mitm/local_baseapp_capture.py:1681 hall_state_rpcs / 1754 late_rpcs / 1821 run_baseapp_stage_machine()` — see §8.

---

## 1. Hall shell — `ui\UIMain.py` (79 anchor consts, 101 start/mode/invite consts)

Left menu `anchor-middle-left/entry/`: `mall (+badge/tishi)` → UIMallController, `supply` → UISupplyController, `friend`, `change_clothes (+badge)` → UIDtsAppearanceMainController (Depot), `team (+badge)`, `brave_book (+badge/badge_num)`, `activities (+badge)`, `competition`, `hero`. Plus `anchor-middle-left/entry-event`, `anchor-midlle-right/Panel_2` (typo is in client).

Top bar: `anchor-upper-left/profile (+ButtonCharge/ButtonExchange/panel_latin)` = My Page (shows ID:0), `btn_quest (+countdown)`, `ui_quest`, `ui_personality_package`, `qixi`, `red_packet`, `groupphoto_share/share`. `anchor-upper-right/invite`, `anchor-upper-right/return`, `common-entry/panel_activity|panel_annual|panel_activity_2`. Currency bar: `CurrencyWidget, MallCurrencyType, YUANBAO, setCurrencyWithOwned, onCurrencyChanged, freeYuanbao/payYuanbao` (`ui\UIMainSourse.py`: `freeYuanbao, getCurrencyAmount, payYuanbao`).

Right column: `anchor-bottom-right/btn_airship (+img_reddot/panel_coming/panel_finish/panel_ready)` = RushHour tank, `btn_season (+img_reddot)`, `new_type_gold_battle/occupation/ported_battle/wild_battle`. Checklist canon (`HALL_NAVIGATION_CHECKLIST.md:20-23`): Right = Daily Special Offer | Activity | Super Carnival | Monthly Offer | Racing | Ranked | friends.

Bottom/center: `b_start, start, Start, setStartGameVisible` = START; `mode, mode_btn, onMatchModeChange, onSubModesEnterEvent` = Ranked selector; `anchor-center/member-{}/player-info/btn_guide, member-1/player-info`; `anchor-bottom-left/ButtonFriend|ButtonEnail/chat/btn_ccvoice|btn_ccvoice_lis|btn_quick_message`; `anchor-upper-right/invite, b_invite, Invite, INVITE_JOIN_TEAM, onInviteFriendEvent` = Invite 0/0.

Model/avatar: `_init_self_model, _display_member_model, createDressModelAsync, resetCharacterModel, setMainModelVisible, model_area, dts_show_model_path, onLoadPlayerModel, onModelClick`.

Script files: `ui\UIMain.py`, `ui\main\UIModes.py` (13 start/mode consts: `CAN_START|GameStart|RANKED|Start|b_start|dual|solo|hallTeamData|mode_btn`), `ui\UIMainBattleGround.py`, `ui\UIMainBattleGroundTeam.py`, `ui\UIMainBattleGroundInvite.py` (30 invite consts: `inviteHallTeamPlayer, dlg/btn_invite_confirm, dlg/btn_weixin_invite`), `ui\UIMainNewFunctionGuide.py` (187 names, see §7), `ui\main\UIMainFunctionEntrance.py` (`entance_list_fixed/dynamic, doUIJump, JUMP_DESTINATION`), `ui\main\UIMainActivityRightTop.py`, `ui\main\HallTheme.py`.

---

## 2. START / Mode / Team — `UIModes`, `UISubModesEnter`, `iHallTeam`

`ui\main\UIModes.py`: `solo|dual, NUM_TO_MODE_STR, RANKED|FPS_MODE|WILD_MODE|YUANBAO_BATTLE, mode_single|mode_lover|mode_btn, start|GameStart|CAN_START, onEnterTeam|onFormTeam|onLeaveTeam|onUnformTeam|onReadyEvent|onMemberUpdate, UISubModesEnter|UIWildModeMain|changeHallTeamModeSetting|hallTeamData`.

`ui\UISubModesEnter.py` (21): `btn_start, mode-panel/btn-1|btn-2|btn-4|btn-5 (+mode-panel_v/), TEAM_SIZE_SOLO|DUAL|QUAD|FIVE, RANKED, changeHallTeamMapGroup|changeHallTeamModeSetting|changeHallTeamType, hallTeamData`. This is the Ranked/mode-select page.

`entities\iHallTeam.py` (595 names): `hallTeamData, onEnterHallTeam, onInvitedToHallTeam, inviteHallTeamPlayer, matchBattleGround, syncHallTeamModeSetting, teamThemeData|themeID|hallThemeID`, mode enums `FPS|WILD|GOLD_BATTLE|YUANBAO_BATTLE|HERO|TRAIN|CAMP_WAR|NEXT_GEN|SINGLE`.

Client RPCs (`athlete_methods_full.txt`): `[54] onEnterHallTeam, [55] syncHallTeamMatchingRandom, [56] onInvitedToHallTeam, [57] addHallTeamMember, [58] delHallTeamMember, [59] onLeaveHallTeam (KNOWN INEFFECTIVE — reads same missing hallTeamData, iHallTeam.py:358→747), [60-65] onSetMatchBigMap/FPS/NextGen/Occupation, [66] syncMatchState, [67] syncHallTeamModeSetting, [71] syncMatchingProgress, [76] onGetMatchedTeamInfo, [77] onMatchGameTypesUpdate, [93] onUpdateMatchTargetTime, [105] onMatchedPlayerInfoChange`. Base exposed: `createHallTeam, inviteHallTeamPlayer, leaveHallTeam, matchBattleGround(BOOL), cancelMatchBattleGround, backToHall [1351]` (`entity_0335.xml:43 hallTeamData PYTHON BASE Default {} + :289 matchBattleGround <Exposed/>`).

START→island (`GATE5_START_TO_ISLAND_PLAN.md`): `UIMain.matchBattleGround` → base `matchBattleGround` → server `syncMatchState|syncReadyState|syncMatchingProgress|onUpdateMatchTargetTime|onGetMatchedTeamInfo|onMatchedPlayerInfoChange|syncBattleState` → `transferToBattleServer(ip,port,name,password,backPort)` → new connection `BattleAccount(39)→Avatar(40)`.

---

## 3. Store (Mall) — `UIMallController`, `UIMall`, `UITreasureMall*`, `UIHallThemeMall`, `UIShareMall`

Tabs (`ui\UIMallController.py`, 84 btn consts): `btn_recommend` (Suggested), `btn_mall` (Packs), `btn_mall_cloth` (Looks), `btn_weapon` (Firearms), `btn_sundry` (Others), `btn_suit_mall`, `btn_share_mall` (Token), `btn_treasure_mall` (LuckyClub/Bargain), `btn_pay` (Top-up) + `inner_list/btn_accumulate_charge|btn_limit_package_month|week|new|btn_welfare`. Paths `anchor-upper-left/TabBtns/btn_*`. Handlers `_doSelectMallBtn|_doSelectMallClothBtn|_doSelectShareMallBtn|onTabBtnMallClicked|...|openTreasureMall`.

List/buy (`ui\UIMall.py` 7): `doQueryMallGoodsFromServer|queryAvailableMallGoods|queryAvailableMallGoodsByType|onQueryAvailableMallGoods|fillGoods/fillGoods2|buyMallGood|_showMallResult|getMallGoodSecondaryDisplayType`. Cloth filter: `ui\UIMallCloth.py queryAvailableMallGoods` (+`DtsAppearanceFilterUtils` gender). Weapon ownership abort: `ui\UIWeaponMall.py:onBuyBtnClicked`. Sundry type 10: `ui\UIMallSundry.py`. Token currency 202: `ui\UIShareMall.py`.

Treasure/Bargain (`ui\UITreasureMallController.py` 13): `TabBtns/btn_clothes|btn_vehicle|btn_weapon` + `UITreasureMallClothes|Vehicle|Weapon`, `UITreasureMallDialog.py` sticky panel (not under `currentUI` → leak, `STORE_AND_SUPPLY_ISSUES.md:150-168`).

Hall-theme mall (`ui\UIHallThemeMall.py` 10 + `ui\main\HallTheme.py` 4): `buyMallGood|buyMallsPanel|queryAvailableMallGoods|onQueryAvailableMallGoods|currentHallThemeID|dtsHallThemeID|hallThemeID|onShowTheme`, csb `ui/in_game/ui_hall_mall/ui_hall_mall.csb`. Real list = 14 goods `0x0687b507`, not 660-row merge (`LOGIN_FLOW_TRACE.md:187-190`).

Client RPCs: `[448] onQueryAvailableMallGoods, [449] onQueryAvailableMallGoodsByType(UINT32), [450] onQueryAvailableMallGoodsForAppearanceMall, [441] onBuyMallGood(ARRAY<INT32>), [447] onBuyMallGoodFailed (never sent), [451] onUpdateClothMallSortInfo, [453] onGetMallDefaultUIInfo, [454] onUpdateHallPropBuyTimes, [456] onBuyDtsMallHero, [459] onExchangeShareProp, [463] onResetShareMallPropCntLimit`. Upstream exposed (`local_baseapp_capture.py:873 _STORE_EXPOSED`): `306 buyMallGood, 307 buyMultipleMallGood, 308 buySuitMallGood, 309 buyMallGoodUseHallProp, 310/315 queryAvailableMallGoodsByType (5B UINT32, live-verified), 311/316 ForAppearanceMall, 312/314 queryAvailableMallGoods (no-arg, live-verified), 313 buyMallGoodInAppearanceMall, 317/318 giftMallGood/giftMallSuitGood`.
Server status: 306/310/311/312/313/314/315/316 YES (`_mall_tables:1081` 4 sigs `0x832995b1/0x878e57c9/0x55977219/0x9fb2d5d5`, `_mall_runtime_goods:1104`, `_send_mall_query_reply:1140`, `_handle_buy_mall_good:1185` + charge via 203/204). 307/308/309 MAPPED BUT UNHANDLED. 317/318 PARTIAL (reuses buy path, no real `442 onGetGift/443 showGiftInfo/444 showSuitGiftInfo/445-446 respond`). Token/ShareMall query MISSING. Treasure RPC (`931 onOpenTreasureMall, 932 onTreasureIndexUpdate`) NO HANDLER. Top-Up untouched (correct — locale/prices client-side, USD→PHP belongs to `translate_properties_en/PayGoods` path).

---

## 4. Supply / Draw / Gacha — `UISupplyController`, `UISupplyPackage*`, `iSupplement`

Tabs (`ui\UISupplyController.py`, 66 btn consts): `btn_supply` (STAR), `btn_month_supply` (SUPREME), `btn_advance_supply` (LOOKS), `btn_advance_supply_vehicle` (VEHICLE), `btn_advance_supply_weapon` (FIREARMS), `btn_advance_supply_hero|kof`, `btn_advance_gold_supply_3rd`, `btn_black_friday`, `btn_gala_supply`. Handlers `onTabBtnSupplyClicked|onTabBtnMonthSupplyClicked|onTabBtnAdvanceSupplyClicked|...`.

Box UI (`ui\UISupplyPackage.py`, 131 consts): `dlg/box_select_panel/box1|box2|box_adv|generalBox|timeLimitBox|emptyBox|previousBoxPanel|buyBtnPanel/generalBox|advanceBox|timeLimitBox`, `onBoxClicked|onBuyBtnClicked|onBuyMultiTimesBtnClicked|onPreviousBoxBtnClicked|onQueryAvailableSupplement|openSupplyBox|openMultipleSupplyBox|showSupplyProbTips`, coin panel `coinPanel/chipsText|colorDiamondText|diamondText|goldText`, `carnival_up`, `itemListPanel`. Variants: `UIMonthlySupplyPackage.py` (395: `getSupplementCurrencyType|openSupplyBox|openMultipleSupplyBox|hasAlreadyShowMonthSupply`), `UIAdvanceSupplyPackage(+Vehicle)`, `UIKofSupplyPackage`, `UICashSupply`, `UITimeLimitActivitySupply`, Anniversary/BlackFriday/ThirdAnniversary packages.

Logic (`entities\iSupplement.py`, 314): `SupplementKindEnum (NORMAL1|TIME_LIMIT2|GUARANTEE3|VEHICLE4|WEAPON5|MONTH7...)`, `CURRENCY_ID|BUY_TIMES_PRICE|BUY_MULTIPLE_TIMES_PRICE|NEXT_BUY_TIMES_PRICE`, `availSupplementDict, advanceSupplementDict, accumulateBuySupplementCntDict`, `_showSupplementResult|_showMultiBuySupplementResult`, `openSupplyBox|openMultipleSupplyBox|openSupplyBoxFree|tryGetExtraGiftProp|setHasAlreadyShowSupplyID|setIsUsePreciousTicketDiscount|tryRefreshFreeLotteryTimes|requireSupplementWeekendAccumulateAward`.

Client RPCs: `[392] onQueryAvailableSupplement(PYTHON)` ← upstream `queryAvailableSupplement` exposed `0xdd` — YES (`supplement_avail_payload:806`, `0x9e1c8652`, `ROS_SUPPLEMENT_ALL=1` → 248 boxes). `[387] onOpenSupplyBox` ← `openSupplyBox` `0xda` — YES (`handle_upstream:1342`, `supplement_pick_prizes:1428` + `supplement_cost:1481` + `grant_appearance_prizes:1243`). `[389] onMultiOpenSupplyBox` ← `0xdc` — YES (n=10). `[388] onOpenFreeSupplyBox` ← `openSupplyBoxFree` `0xdb` — MISSING (falls through silent). `[390/391] Failed` NEVER SENT. `[393/395/397/398/399/400] ExtraGift/AlreadyShow/BuyCntDict/WeekendAccumulate/WatchAd` MISSING/IGNORED. `[244] onSyncKofSupply, [271/272] BlackFriday discounts, [527-530] OpenSupplyGift, [780-786] CosmicSupply` NO PUSH/HANDLER (see §6).

Helpers implemented: `_supplement_runtime_record:773`, `supplement_pick_prizes:1428` (`rate_map={2:0.20,4:0.05,5:0.08,7:0.06,3:0.12}`, `ROS_DRAW_COSMETIC_ONLY=1`), `supplement_cost:1481` (only `91→48/5`, `2→1440/150`; NO `9`-colour-diamond `300/2880` fallback), `_expand_prop:1400`, `_is_cosmetic:1423`. Doc target curves (Star Legend 1.5/Epic 8.5/Rare 30/Common 60, Vehicle 2.5/8.5/89, Firearm 3.5/15/81.5) NOT in code. SUPREME black page = `getCurrentMonthSupplementID()` vs `data_month_supplement_param 5c64e12a/462e4a27 END 2021.12.30` — needs table patch/clock work (`inspect_month_supply.py`).

---

## 5. Depot / Looks / Theme — `UIDtsAppearanceMainController`

Tabs (126 consts): `anchor-left/MainControlLayer/costumBtn|vehicleBtn|weaponBtn|petBtn|suitBtn|repertoryBtn|newAddedBtn|workShopBtn|hallThemeMallBtn`, handlers `onCostumBtnEvent|onVehicleBtnEvent|onWeaponBtnEvent|onPetBtnEvent|onSuitBtnEvent|onHallThemeBtnEvent|onNewAddedBtnEvent|onWorkShopBtnEvent|on_enter|on_leave|displayAll`. Sub-tabs (costume others): `face/armor/backpack/car/feishi/frame/helmet/huahua/huojian/jiejing/paraglider/penqi/pose/..._nml/_sel.png`.

Client RPCs: `[344] onUpdateDtsWearableAppearanceList, [345] Body, [346] Emoji, [347] EmojiID, [348] FlyingAccessory, [349] Dyeing, [351] Weapon, [354] Tag, [355] onSetDtsAppearanceGender, [356] onNotifyEquipedAppearance, [357] onNotifyUnloadAppearance, [358] onNotifyEquipAppearanceFailed, [359/360] ShowWearable/ShowBody, [361-366] ShowFlying/Dyeing/BattlegroundProp/Weapon/Vehicle/Tag, [367] onUpdateDtsHallThemeID, [368] Paint, [369] JetWings, [371] Aircraft, [381] HallVehicleList, [383/384] Pendant, [335] onAddDtsAppearanceItem, [339] onUpdateDtsAppearanceItemNumber, [642] Nameplate`.
Upstream (`_DEPOT_EXPOSED:891`): `257 equipAppearance, 260 unloadAppearance, 261 setDtsAppearanceGender, 263 tryOffAppearance` → `handle_depot_call:1008`. Implemented: gender switch, single-slot equip/unload, persistence (`data/player_state.json`, `data/player_inventory.json`, `_rebuild_stream_bg()`), slot sanitize (`_get_appearance_slot:900`, `_sanitize_saved_appearance_lists:933`). Missing: `tryOnAppearance, queryOthersAppearanceDict, setDtsHallVehicleAppearance/cancel, takeOffAllAppearanceForSuit, putOn/TakeOffAppearanceClothSuit, buySuitWeaponDanceChargeCnt→[492/495], customized suits [947-953], vehicle/aircraft/pendant/nameplate updates [361-384]`.

Known crashes: Depot Review popup → X ignored, Back crashes `UIDtsAppearanceMainController.on_leave → UIMain.displayAll → UIMain.showRedPoint:2453 TypeError None not iterable`. 2nd Back crashes `UIDtsAppearanceCostume.on_leave → DtsAppearanceRightPanelPattern1.on_leave → onHideTransformBtn: None.refreshTransformPanel`.

---

## 6. Other hall systems (all static-found, most server-missing)

* Ranked page `ui\UIRankLadder.py` (65): `btn_close|btn_season|btn_rewards|btn_celebrities|btn_challenge|btn_wangzhe_1|2|btn_season_info, getRankDict|get_self_cur_rank_info|get_self_season_rank, ladder_celebrity.csb`. Rank RPCs `[165-196,297,301] onGetPlayerRank(+BattleGround/WeaponProficiency/HotVal), onRequire*RankList, updateDtsRankValue, updateFriendRank, updateRankBadge`. Visiting+exiting heals avatar/duplicates (re-runs display path).
* Lucky Carnival `ui\UILuckyCarnival*.py` (105+93+82+14+6+3+2): `content/panel/Button_lottery, Panel_lottery/lottery_1..8, lotteryBtn, onLotteryBtnClicked|onDoLuckyLottery|onGetLotteryResult|onOpenLuckyCarnival|onShowNew/OldCarnivalBg, onCurrencyChanged`. RPCs `[745] onUpdateLuckyCarnivalData (server sends all-zero placeholder → COMING SOON wheel), [750/751] onShow*Bg, base [897] onDoLuckyLottery|[898] onOpenLuckyCarnival|[899-902]`. Needs active season/round shape (`LUCKY_CARNIVAL_COMING_SOON.md:47-54`).
* OpenSupplyGift `ui\UITimeLimitActivityOpenSupplyGift*.py` (241+75+161) + `entities\iOpenSupplyGift.py` (113): `btn_open_appearance_gift|btn_open_supply_gift, onQueryAvailableOpenSupplyGift|onUpdateOpenSupplyGiftInfo|onGetOpenSupplyGift, availableOpenSupplyGift, giftId|giftState, gotoAdvanceSupplyPanel|gotoMonthSupplyPackage|...`. RPCs `[527-530]` NO HANDLER.
* Exchange/Convert `entities\iItemExchange.py` (17) + `ui\UIItemExchange.py` (13) + `ui\UITimeLimitActivityItemExchange.py` (11): `availExchangeItems|exchangeItem|onExchangeBtnEvent|dlg/exchangeBtn`. RPCs `[524] onQueryAvailableExchangeItem, [525] onExchangeItem, [526] onExchangeItemFailed, [212] onExchanged, [218] onConvertUniversalFragment, [542-544] notifyExchangeResult|onConfirmExchange|onDiscardExchange` — likely what `codex_fragment*.png` exercises. `Codex` as named system DOES NOT EXIST statically (zero `codex` methods in entity XMLs/method table/script index).
* CosmicSupply `ui\UICosmicSupply*.py` (126+434+116+93+323+250) + `entity_0011.xml`: `right_tab_panel_0/btn_1|2|3, bindInviteCode|inputRecallInviteCode|personalInviteCode, bonusPool|diamondCanGet|getBonusPoolDiamond`. RPCs `[780-786] updateCosmicSupplyBaseInfo/OpenNum/ShareUrl/ShareInfo/InviteAwardList|onGetCosmicSupplyAward|updateCosmicSupplyRankListInfo` NO HANDLER.
* WishPool `ui\UIWishPool.py` (18) + `entities\iWishPool.py` (13): `middle/left_part/wish_btn|wished_btn, onClickWish|setWishTargetPropID|getWishPoolAward`.
* Welfare/Sign/Daily: `[431] onShowSignedPanel, [432] onShowSignSuccess, [434] onSetSigned, [464-469] onQueryAvailableWelfare|onReceiveWelfare|onBoughtWelfare, [252] onGetCommonHolidaySignInReward, [755-762] SignAwardTime|DtsSignIn|KofSignIn|ComplementSign, [816] onResetDailyTasks, [821] onUpdateDailyTaskList, [405/406] RedPointInfo|AssistantRedPoint, [1099] gmsyncRedPoints([]) (server sends empty, required by displayAll), [1127] onGmClearNewFunctionGuide`. Daily-login popup (388 Gold claimable, TOTAL 0d) claim RPC unmapped — find via `script_query.py uidailylogin`.
* Chat/Friend/Mail: `[17] onGetFriendList, [19] onRequestSuggestFriends, [22-30] onUpdateFriend|onRemoveFriend|...|onRequestFriendOnlineStatus, [34] onRequestFriendAck, [116/117/119-122] gmDeleteChat|onChat|onChatPrivate|onAnnounceChat(InHall), [37/38/40] onMailUpdate|onLoadMailDetail|onGetAwardFromMail, [641] onUpdateChatBubbleTag, [452] onGetPropFromFriend, [903] onReceiveGiftFromFriend`. UI: `UIFriendPanel (btn_invite), UIFriendInfo (b_invite|inviteBtn|onInviteBtnClicked|dlg/tabs/invite), UIFriendship, UITeamInvitation|UITeamRequestion|UIRosMatchTeam*`.
* Currency (top bar): `[201] onSPUpdated, [202] onGPUpdated, [203] onYBUpdated(free,pay), [204] onCurrencyUpdated(id,val,src), [205] Tips, [208/209] NewVersionGP`. Diamond = free+payYuanbao; coin slot = `currencyList` id 213 (`UIMain.curExchangeCoin`); identical `283283` = same prefab default. Server `_dev_currencies={1,3,9,91,202,214,213:…}` + `ROS_DEV_CURRENCY/ROS_CURRENCY_PROBE/ROS_DEV_GP|SP|FREE_YB|PAY_YB` (`local_baseapp_capture.py:1773-1791`).
* Hall-theme/vehicle: `[367] onUpdateDtsHallThemeID, [381] onUpdateHallVehicleAppearanceList`.
* Events/modes: RosMatch `[562-597]`, PrizeMatch `[598-618]`, HorseRacing `[621-633]`, ChallengeCup `[703-712]`, `onGetAnniversaryAirShipRank [873]` (OPT-IN `ROS_AIRSHIP_STATE`, NOT idempotent — opens AIRSHIP BATTLE page), `syncClosedRankList [165]`, `updateLotteryMatchList [487]`, `onUpdateActivityRedPointInfo [405]`.
* Settings: `ui\UISettings.py` (53): `applySettings|saveBasicSettings|cSyncSettingDataToServer|syncUISettingModeToServer|settingModeIdx|qualitySettings|onCCVoiceSettingSave`. Client sends ~2.5KB settings blob on touch (seen in Store session log).

---

## 7. Guide overlay (blocks hall taps)

`ui\UIMainNewFunctionGuide.py` (187): `IS_FORCE_GUIDE|NewGuideEffType|doGuideInfo|newGuideArrow|playArrowStart|onMaskClick|isForceGuide, ui/out_game/ui_main_v2/csd/NewFunctionGuide.csb`. Driven by `dts_new_function_guide_utils.checkCanDoNewFunctionGuide/tryShowNewGuide` reading Athlete `newFunctionGuideRecord` (PYTHON, stream idx 825, None/default). Single step — tapping START clears it (`scratch/start1.png`). Fix: send record marking every `NewFunctionGuideCfgDict` id done (or `recordNewFunctionGuide` RPC).

---

## 8. What the server already sends (hall bootstrap)

`hall_state_rpcs` (right after verified char chain, while hall loads): `355 gender, 344/345/359/360 appearance lists, 1099 gmsyncRedPoints([]), 745 LuckyCarnival placeholder, 768 syncMonthPayRebateSpecialAwardInfo({'awards':{}}), 754 onPersonalRecommendStateUpdated(0,0,{},0), 392 onQueryAvailableSupplement, 448/450/449 mall catalog pre-push`. Opt-in `204 id=9` (`ROS_SEND_COLOR_CURRENCY=1`). `late_rpcs` at `ROS_HALL_LATE_DELAYS=45,90,150` (UIMain needs 60-90s to exist): `201/202/203` dev currency (`ROS_DEV_CURRENCY=1`), `204` probe per id (`ROS_CURRENCY_PROBE=1`), airship `[873]` once (`ROS_AIRSHIP_STATE/ROS_AIRSHIP_DELAY`).

---

## 9. Still missing / next probes (priority)

1. `388` free draw + `390/391/447` failures; `307/308/309` buys; real gift `442-446`; `456 buyDtsMallHero`; Token/ShareMall query; Treasure `931/932` + dialog-dismiss hook; Exchange `524-526`/Convert `719-722`; Cosmic `780-786`; OpenGift `527-530`; WatchAd/FreeLottery/WeekendAccumulate/KOF/BlackFriday; Depot extras (§5).
2. P0 avatar: what runs after `Athlete.py:275` / what `extconfigs.py:50` indexes (nstool/internalquery reply?).
3. `UIMain.py:2453 showRedPoint` None iterable owner; `refreshTransformPanel` None owner.
4. Full route sweep (only Depot ticked): open/render/exit(X+Back)+traceback per route.
5. `283283` origin; peso path; mall exposed arg shapes; supply drop weights; `NEXT_BUY_TIMES_PRICE`; guarantee counters; Supreme `END 2021.12.30`; Carnival active season shape; daily 388 Gold claim upstream; `ID:0`; RushHour banner; 2nd-Back crash; START ack semantics; Avatar/cell payloads.
