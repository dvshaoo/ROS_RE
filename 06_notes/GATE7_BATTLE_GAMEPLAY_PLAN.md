# GATE 7 PLAN — In-battle gameplay after island entry (static research, 2026-09-24)

> Status: RESEARCH ONLY — nothing below is implemented or live-verified unless marked VERIFIED.
> Method: static-only (no game run). Sources: `05_entities/out/*.xml` DEFs,
> `scratch/athlete_methods_full.txt` (1131 Athlete client methods, type 51),
> `06_notes/athlete_base_methods_table.txt` (1393 Athlete base methods),
> `scratch/script_index.txt` via `tools/script_query.py` (bare lowercase substrings),
> `mitm/local_baseapp_capture.py`, `06_notes/GATE5_START_TO_ISLAND_PLAN.md`,
> `06_notes/GATE6_BUY_AND_DRAW_PLAN.md`, `06_notes/HALL_DEEP_DIVE_2026-09-24.md`.
> Follow CLAUDE.md rules (zero guesswork; live test + notes + commit).
> Note: no Gate 7 was previously defined in the repo — Gates 0–4 PASS, Gate 5 = START→island,
> Gate 6 = Store buy + draws. This document DEFINES Gate 7 as the natural next milestone.

## 0. Definition

```
Gate 5:  START (matchBattleGround) -> hall match-state RPCs -> transferToBattleServer(ip,port,name,pass,backPort)
Gate 7:  BattleAccount(39) login on battle host -> Avatar cell entity(40) in BattleGroundSpace
         -> stand on island, NO countdown timer, NO plane, NO airdrop
```

User goal (same as Gate 5 island requirement): pressing START must enter real gameplay; for testing
the player just stands on the island. Exit path `backToHall` must work or the tester gets stuck.

## 1. Handoff chain (VERIFIED static)

### 1.1 START upstream — Athlete base methods

DEF — Athlete-side hall interface (client-callable). `05_entities/out/entity_0335.xml:289-293`,
identical in `05_entities/out/entity_0574.xml:289-293` (both 767 lines, same content):

```xml
<matchBattleGround> <Exposed/>
  <Arg> BOOL </Arg>
</matchBattleGround>
<cancelMatchBattleGround> <Exposed/>
</cancelMatchBattleGround>
```

Context: `entity_0335.xml:43-47` `hallTeamData PYTHON BASE Default {}`.

DEF — BaseApp-internal variant (NOT client-callable, do NOT use for START).
`05_entities/out/entity_0354.xml:2-5` (`iBaseNoCell+iOfflineOperation`), `:146-155`:

```xml
<matchBattleGround>   <!-- no Exposed -->
  <Arg> GID </Arg> <Arg> GLOBAL_MAIL_BOX_INFO </Arg> <Arg> BOOL </Arg> <Arg> PYTHON </Arg>
</matchBattleGround>
<cancelMatchBattleGround>   <!-- no Exposed -->
  <Arg> GID </Arg> <Arg> GLOBAL_MAIL_BOX_INFO </Arg>
</cancelMatchBattleGround>
```

Base-table indices (live-dumped in `06_notes/athlete_base_methods_table.txt`, NOT wire ids —
header states `NOT yet mapped to wire method ids`):

| Base idx | Method | Table line |
|:---:|:---|:---|
| 96 | `matchBattleGround` | `athlete_base_methods_table.txt:99` |
| 97 | `cancelMatchBattleGround` | `:100` |
| 1351 | `backToHall` | `:1354` |

Exposed wire id: UNKNOWN statically (`GATE5_START_TO_ISLAND_PLAN.md:35`, GATE6 plan `UNKNOWN §1`).
`matchBattleGround` is in neither `mitm/local_baseapp_capture.py:899-920`
`_STORE_EXPOSED` nor `_DEPOT_EXPOSED`. Needs one live START tap to log the
`DECRYPTED(bundle)` + `UPSTREAM CALL: msg=0x.. method=0x.. exposed_idx=..` line
(`local_baseapp_capture.py:1388-1391`), the same way `306/310/312` were mapped.

### 1.2 Hall match-state RPCs (VERIFIED static — server drives these)

Runtime client indices (`scratch/athlete_methods_full.txt`):

| Idx | Method | Table line |
|:---:|:---|:---|
| 66 | `syncMatchState` | `:67` |
| 68 | `syncReadyState` | `:69` |
| 69 | `syncBattleState` | `:70` |
| 71 | `syncMatchingProgress` | `:72` |
| 76 | `onGetMatchedTeamInfo` | `:77` |
| 93 | `onUpdateMatchTargetTime` | `:94` |
| 105 | `onMatchedPlayerInfoChange` | `:106` |

`backToHall` has NO client index — base `[1351]` only. `syncBattleState` has NO base variant (client-only).

Arg shapes from DEFs (`entity_0335.xml` == `entity_0574.xml`; first arg
`GLOBAL_MAIL_BOX_INFO` is stripped on the client wire):

Client (server SENDS — use these):

| DEF lines | Signature |
|:---|:---|
| `:576-581` | `syncMatchState(INT16,INT64,BOOL,PYTHON)` |
| `:587-591` | `syncReadyState(GID,BOOL,UINT8)` |
| `:592-595` | `syncBattleState(GID,BOOL)` |
| `:600-604` | `syncMatchingProgress(INT32,INT32,FLOAT)` |
| `:617-619` | `syncYuanbaoMatchingProgress(INT32)` |
| `:620-622` | `onGetMatchedTeamInfo(ARRAY<PLAYER_LOADING_INFO>)` |
| `:685-687` | `onUpdateMatchTargetTime(INT32)` |
| `:734-737` | `onMatchedPlayerInfoChange(GID,PYTHON)` |

Script anchors (`script_query.py`): `syncMatchState|syncMatchingProgress|syncReadyState|syncBattleState|
onGetMatchedTeamInfo|onMatchedPlayerInfoChange` = 1 hit each in `entities\iHallTeam.py`;
`onUpdateMatchTargetTime` = 2 hits (`entities\iHallTeam.py` + `ui\UIBattleGroundsMatchTimer.py`).
`backToHall|enterMatchBattleSpace|createCellPlayer|spaceViewport` = 0 exact script-name hits
(`backToHall` exit trigger statically unknown — see §4.5).

### 1.3 Battle handoff — `transferToBattleServer` (VERIFIED static)

DEF signature — server→client ClientMethod, NOT base.
`05_entities/out/Athlete.def.xml:552 <BaseMethods>` / `:817 <ClientMethods>` / `:860-866`:

```xml
<transferToBattleServer>
  <Arg> STRING </Arg>     <!-- ip -->
  <Arg> INT32 </Arg>      <!-- port -->
  <Arg> KEY_NAME </Arg>   <!-- playerName -->
  <Arg> BLOB </Arg>       <!-- password -->
  <Arg> UINT32 </Arg>     <!-- backPort -->
</transferToBattleServer>
```

Runtime client index: `scratch/athlete_methods_full.txt:1094` `[1093] transferToBattleServer`
(1131 total; context `:1085-1104`: `[1091]enterHall ... [1093]transferToBattleServer [1094]systemMsg`).
Server→client wire per CLAUDE.md §5 (1131 methods → div=5, threshold=57, msgID=128+w1).

Script refs (`script_query.py`, bare lowercase, read-only):
- `transfertobattle`: 2 hits — `entities\Athlete.py :: transferToBattleServer`,
  `helpers\ConnectMonitor.py :: transferToBattleServer`
- `battlehos`: 16 hits — `entities\Athlete.py :: setBattleHostInfo` (1),
  `helpers\ConnectMonitor.py` (10: `setBattleHostInfo|connectBattleHost|ConnectBattleHostCallback|
  battleHostFailure|battleHostRecord|doConnectBattleHost|...`), `elkLogging.py` (5)
- `matchbattle`: 7 hits — `ui\UIMain.py :: matchBattleGround` (START caller),
  `ui\UIMainBattleGroundTeam.py :: matchBattleGround|cancelMatchBattleGround` (2),
  `ui\UIBattleGroundsMatchTimer.py` + `ui\UIYuanbaoBattleMatchTimer.py` (cancel),
  `common\task\task_utils.py` (TaskEventMatchBattle)
- `syncmatchstate`: 1 hit — `entities\iHallTeam.py :: syncMatchState`
- `battleaccount`: 12 hits, all `entities\BattleAccount.py`
  (`BattleAccount|PlayerBattleAccount|ClientEntity|base|handshake|onBecomePlayer|needBGM|iProxy|...`)

Semantics (`GATE5_START_TO_ISLAND_PLAN.md:14-18`): `entities/Athlete.py
transferToBattleServer(ip,port,playerName,password,backPort)` calls
`ConnectMonitor.getInstance().setLoginHostBackPort` + `setBattleHostInfo`, then
`uiMgr.enter_ui(...)`. The client does NOT stay on our BaseApp — it opens a NEW
connection to battle `ip:port` and logs in there with `playerName/password` as
`BattleAccount(39)` → `Avatar(40)` in `BattleGroundSpace`.

## 2. Battle-side entities (VERIFIED static)

Type IDs (CLAUDE.md §3, live memory `libclient.so:base + 0x45785f0`):
`37 LoginProxy, 38 Account, 39 BattleAccount, 40 Avatar, 51 Athlete, 56 RobotShadow`.
Declaration order still visible in `05_entities/out/entities.xml:151-165`
(`LoginProxy/Account/BattleAccount/Avatar/.../Athlete`; `:47 BattleGroundSpace`,
`:153 BattleAccount`, `:241 BattleGroundAvatar`). Supersedes stale
`06_notes/LOBBY_ENTRY_TRACE.md:172-177` PC-counting (`127/128/129/140`).

### 2.1 BattleAccount — `05_entities/out/BattleAccount.def.xml:1-35`

- `:2` `ClientName BattleAccount`, `:4` `iProxyNoCell` only (no cell).
- `:6-27` Properties — 5× `BASE`-only, none sent to the client in a `createBasePlayer`
  domain=0 stream (which only sends `BASE_AND_CLIENT`):
  `avatarProperties PYTHON BASE`, `avatarType STRING BASE`, `avatarIndex INT32 BASE`,
  `athleteMailBox GLOBAL_MAIL_BOX_INFO BASE`, `password BLOB BASE`.
- `:28-34` BaseMethods only, no ClientMethods/CellMethods:
  `:29-30` `<handshake> <Exposed/>`, `:31-33` `<onNextProxyDestroy><Arg>INT32`.

### 2.2 Avatar — `05_entities/out/Avatar.def.xml`

- `:4` `iProxyWithCell` (vs `Athlete.def.xml:5`, `BattleAccount.def.xml:4`,
  `Account.def.xml:3` = `iProxyNoCell`).
- `:90` `ClientName Avatar`, `:91-99` Indexes `gid,baseNickname`,
  `:101-106` Volatile `position/yaw/pitch/timestamp`.
- `:108` Properties (177), `:997` BaseMethods (102), `:1417` CellMethods (147),
  `:1937` ClientMethods (93).
- Battle-relevant base samples: `:1048-1050` `loadingFinish <Exposed/><Arg>INT32`,
  `:1060-1065` `enterSpace(PYTHON,MAILBOX,VECTOR3,VECTOR3)`,
  `:1283-1285` `finishBattle(INT32 teamSize)`, `:1293` `<backToHall> </backToHall>` (no `Exposed`;
  same as `Athlete.def.xml:671` `<backToHall> </backToHall>`, no `Exposed`).
- Client samples: `:1940-1957` `loadMap(INT32,...)`, `onTransferSpace(BOOL)`.
- Movement (CellMethods): `:1670-1690,1770-1775,1879-1883,1785-1790`
  `jumpStart(BOOL)/jumpEnd(FLOAT)/fall/vault(INT8,FLOAT)/changePose/changeFallPhase/
  changeGlidePhase/skydiveMoveDir(VECTOR3)/updateOnTrainPosition(VECTOR3,VECTOR3,ENTITY_ID)/reportStuck`.
- Combat/pickup: `:1433-1451` `shootHit/chargeShootHit(SHOOT_WEAPON_INFO,VECTOR3,ENTITY_ID,HIT_PART,...)`;
  `:1471-1495` `getOnVehicle/enterVehicle/buyBuff/getOffVehicle`;
  `:1756-1758` `onPickUpProp(BOOL)`; `:1841-1843,1858-1860,1874-1878`
  `onPickHeritage, supplyWhenLand, generatePlayerLandProp`.
- Space entities present in `05_entities/out/*.def.xml` + `entities.xml:197-198,272`:
  `DtsProp/DroppedC4Item/CrackItem/DtsSecretTreasureBox/AirShip/Detector`.

### 2.3 BattleGroundAvatar — `05_entities/out/BattleGroundAvatar.def.xml:1-19`

`:2` `Parent Avatar`, `:3` `ClientName BattleGroundAvatar`,
`:5-10` Implements `iDtsEquip|iDtsProp|iDtsPackage|iDtsEquipAppearanceAvatar|iVoxelBuild`,
`:11-18` empty Properties/CellMethods/BaseMethods/ClientMethods (inherits all from `Avatar`).
Variants with `Parent BattleGroundAvatar`: `AvatarCampWar/FreeParadise/Imba/SecretTreasure/
UnitedBattle/AutoRoyaleAvatar.def.xml:2`.

### 2.4 BattleGroundSpace — `05_entities/out/BattleGroundSpace.def.xml`

- `:2` `Parent DynamicSpace`; `:4-15` Implements
  `iMatchSingleSideSpace|iRobotGenerate|iSpaceObserve|iSpaceWeatherControl|...`;
  `:17` `ClientName BattleGroundSpace`.
- `:19-571` Properties, e.g. `gameStatus INT32 ALL_CLIENTS`, `circleStage INT32 ALL_CLIENTS`,
  `planeEntityIDs ARRAY<INT32> ALL_CLIENTS`, `movePath ARRAY<VECTOR3 size 3> CELL_PUBLIC`,
  many `CELL_PRIVATE` timers (never on wire).
- Circle (ALL_CLIENTS, `:163-201`): `blueCircleCenter:VECTOR2, blueCircleRadius:INT32,
  whiteCircleCenter/Radius, circleStage:INT32`.
- Plane/move (`:271-273,387-389`): `planeDir:VECTOR3`, `planeEntityIDs:ARRAY<INT32> ALL_CLIENTS`,
  `movePath:ARRAY<VECTOR3><size>3</size> CELL_PUBLIC`.
- Status (`:19-38,95-98,358-441`): `teamSize/specialType/aliveNum:ALL_CLIENTS`,
  `gameStatus, startTime/gameStageStartTime`.
- CellMethods (`:674-1107`), incl. `:723-739,821-822,692-716`
  `onPlaneCreate/onPlaneEnter/onPlaneLeave/onForceLeavePlane/playerGetOffPlane/
  notifyEnterWorld<Exposed/>/discardProp/createPaintEntity/leaveHeritage/airDrop`.
- ClientMethods (`:572-673`): `gameEnd(INT8,SINGLE_BATTLE_GAME_RESULT)`,
  `showKillInfo`, `onNotifyEnterWorld`, `onSyncAllHumansOnMap`, ... plane-auction/airship.
- `:1108-1114` BaseMethods `updateCourseData`.
- Children with `Parent BattleGroundSpace`: `AutoRoyaleSpace, BattleCampWarSpace,
  BattleGroundCustomSpace/ImbaMode/QuickMode/FreeParadise, BattleSecretTreasure,
  BattleWildModeSpace, BattleUnitedBattleSpace...` + `entity_0120/0336/0355/0374.xml`.

## 3. Cell/space wire mechanics (VERIFIED static, not yet implemented)

- `06_notes/CLIENTINTERFACE_MESSAGE_TABLE.md:36-48`: `5 createBasePlayer VARIABLE,
  6 createCellPlayer VARIABLE, 7 spaceData VARIABLE, 8 spaceViewportInfo FIXED13,
  9 createEntity VARIABLE, 10 updateEntity VARIABLE, 11 enterAoI FIXED5...`
- `06_notes/GHIDRA_PACKET_PARSER_TRACE.md:2791-2838`: `ClientApp` vtable `0x038d64d0`
  slot0 `onBasePlayerCreate` (msg5) / slot1 `onCellPlayerCreate` (msg6) / slot3
  `onBecomeCellPlayer`; `createCellPlayer` wire `[spaceID u32][vehicleID u32]
  [pos 3xf32][dir 3xf32]` 32B + `domain=1` stream filter
  `(flags>>3&1)==0 && (flags&6)!=0` (`OWN_CLIENT/CELL_PUBLIC/ALL_CLIENTS`),
  then `onBecomeCellPlayer`.
- `06_notes/LOBBY_ENTRY_TRACE.md:192-207`: `Athlete=iProxyNoCell` ⇒ NO
  `createCellPlayer/spaceData/spaceViewportInfo/enterAoI` for the lobby;
  `Avatar=iProxyWithCell` ⇒ they ARE required (BASEAPP_CELLAPP_FLOW §4-5
  matchmaking/`BattleGroundSpace` stage).
- Island-only rule: use a `BattleGroundSpace` variant and NEVER send the
  countdown/plane/airdrop starters (`onPlaneCreate/Enter/Leave`, `playerGetOffPlane`,
  `movePath/planeDir/prepareTime`, `onNotifyEnterWorld`, `updateCircleRestTime`,
  `onSyncAllHumansOnMap`).

## 4. Open unknowns (must be answered live, NOT guessed)

1. **START upstream**: exposed wire id + arg bytes of `matchBattleGround(BOOL)` +
   server ack semantics — which of `syncMatchState/syncReadyState/syncMatchingProgress/
   onUpdateMatchTargetTime/onGetMatchedTeamInfo/onMatchedPlayerInfoChange/syncBattleState`
   actually moves the UI off the spinner; exact `PYTHON` blob schemas and `INT16/INT64` enum values.
2. **`transferToBattleServer` args**: `KEY_NAME/BLOB/UINT32 backPort` wire encoding;
   whether password is validated or echoed; `setBattleHostInfo/setLoginHostBackPort`
   IP/port format (host `172.16.1.2` vs guest `172.16.1.15`?); `uiMgr.enter_ui` target.
3. **Battle-host handshake**: session-key derivation (current memory-scan method needs
   root — breaks non-root LAN testers); `BattleAccount.createBasePlayer` exact stream bytes
   (needs `scratch/dump_runtime_types.py` + `gen_stream_v3.py` rerun for type 39, same as
   Checkpoint 20 — note all 5 props are BASE-only so the domain=0 stream may be
   empty/defaults, but confirm via runtime dump, not XML); `BattleAccount.handshake` reply.
4. **Avatar/space sequence**: Avatar base + cell streams, `createCellPlayer(spaceID,pos/dir)`,
   `spaceData/spaceViewportInfo/createEntity/enterAoI` order to leave the loading screen;
   `gameStatus/circleStage/aliveNum/teamSize` minimal values; which space ClientMethods
   start countdown/plane/airdrop (omit them); map geometry/assets location (`04_obb/`
   holds `main/patch.1117219…obb`, `obb_extract/`, `npk_extract/` — no verified island-mesh
   lookup yet); robot/pickup spawn tables.
5. **`backToHall` trigger**: no script name found (`backToHall|enterMatchBattleSpace|
   createCellPlayer|spaceViewport` = 0 hits); `Athlete.backToHall[1351]` and
   `Avatar.backToHall` are both non-`Exposed` in DEF — unknown whether server- or
   client-initiated, and which bytes return to hall without a stuck state.

## 5. Suggested first slice (small, verifiable)

1. Log the START message and dump what the client does on a bare `syncMatchState` reply
   (add `matchBattleGround` to the upstream name map once its exposed idx is captured).
2. Implement `transferToBattleServer` to a second listener (LoginApp+BaseApp pair, same
   Mercury/Blowfish handling as Gates 2–3, entity `BattleAccount`).
3. Verify the client reaches `BattleAccount` login without a crash — BEFORE touching
   Avatar/space. (`GATE5_START_TO_ISLAND_PLAN.md:42-44`.)

## 6. Trace index (where everything above came from)

| Item | Source |
|:---|:---|
| Gate 5 research | `06_notes/GATE5_START_TO_ISLAND_PLAN.md` |
| Gate 6 research | `06_notes/GATE6_BUY_AND_DRAW_PLAN.md` |
| Hall map | `06_notes/HALL_DEEP_DIVE_2026-09-24.md` |
| Store/Supply issues | `scratch/STORE_AND_SUPPLY_ISSUES.md` |
| Packet parser trace | `06_notes/GHIDRA_PACKET_PARSER_TRACE.md` |
| Hall nav checklist | `06_notes/HALL_NAVIGATION_CHECKLIST.md` |
| Server impl | `mitm/local_baseapp_capture.py` (`_STORE_EXPOSED`, `_DEPOT_EXPOSED`, `handle_upstream_calls`, `hall_state_rpcs`, `send_entity_method`, `send_mercury_message`) |
| Stream tooling | `scratch/dump_runtime_types.py`, `scratch/gen_stream_v3.py`, `scratch/dump_athlete_methods.py`, `scratch/dump_athlete_base_methods.py` |
| Script search | `tools/script_query.py`, `tools/script_disas.py`, `tools/load_table.py` |
| Method tables | `scratch/athlete_methods_full.txt`, `06_notes/athlete_base_methods_table.txt` |
| Entity DEFs | `05_entities/out/Athlete.def.xml`, `BattleAccount.def.xml`, `Avatar.def.xml`, `BattleGroundAvatar.def.xml`, `BattleGroundSpace.def.xml`, `entity_0335/0574/0354.xml` |
| Ground-truth rules | `CLAUDE.md` §§1–8 (Gates 0–4, entity IDs, method vectors, Mercury extended encoding, Checkpoint 18/20/20d/20j) |

## 2026-09-25 START button exhibits the same dead-touch signature as Carnival Draw

Live-tested (real finger tap, not adb): tapping START plays its click sound (confirms the touch is
recognized at the engine/audio level) but produces **zero** effect otherwise — no popup, no mode
selector, no visible state change, and critically:
- Zero upstream Mercury call reaches the server (checked `local_baseapp_capture.py`'s `_seen_exposed`
  log, which records every distinct upstream `(method,len)` pair including unmapped ones — nothing
  new appeared after the tap).
- Zero `<SCRIPT>`-tagged output of any kind in a clean `adb logcat -c` capture bracketing the tap (no
  error, no print, nothing).

This is the identical signature already documented for the Lucky Carnival Draw button in
`06_notes/LUCKY_CARNIVAL_COMING_SOON.md` (2026-09-25 entry): audio/engine-level touch acknowledgment
with no Python-level execution at all. Since two independently-implemented buttons in different UI
modules show the exact same failure mode, this now looks less like a per-button script bug and more
like a systemic native touch-dispatch issue in this client build (or this specific hall layout/skin
state) -- consistent with the still-unconfirmed theory that some overlay node with an oversized
invisible touch-catcher sits on top of the interactive layer.

This blocks even the "first slice" of Gate 5/7 (`log the START message`, `06_notes/
GATE7_BATTLE_GAMEPLAY_PLAN.md:266-269`) — the exposed wire id for `matchBattleGround` cannot be
captured live if the client never sends it. Before continuing any Gate 5/7 work, the native Frida
touch-dispatch investigation flagged for the Carnival Draw button (see
`06_notes/LUCKY_CARNIVAL_COMING_SOON.md`, "needs a native Frida hook on the touch dispatcher") should
be done first, since it now blocks two unrelated features rather than one.
