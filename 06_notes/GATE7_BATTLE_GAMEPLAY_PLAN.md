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

### 2026-09-25 Update: Frida attach working, touch pipeline & START button internals verified
- **Frida attach unblocked**:
  - The suspected NetEase anti-tampering was **refuted**. The attach failures and PID churn were caused by running an ARM64 `frida-server` binary on LDPlayer 9's `x86_64` guest under Houdini translation, causing user-space `Segmentation fault`s during ptrace initialization.
  - Using `/data/local/tmp/frida-server-x64` (16.2.1) + host `scratch/fridaenv16` (16.2.1) attaches cleanly to `com.netease.chiji` with a stable, persistent session and working Java bridge.
- **START button handler disassembled (`ui/UIMainBattleGroundTeam.py` `onGoEvent`)**:
  - The button path in `BattleGroundTeamLayer.csb` is `anchor-bottom-right/go` bound to `onGoEvent`.
  - Disassembly reveals:
    ```python
    def onGoEvent(self, args, members):
        if args.touch.phase != TouchPhase.Ended:
            return
        self._hide_operations()
        if not self.all_ready:
            members = '、'.join(self.members_not_ready)
            Globals.uiMgr.systemJumpTip(errtxt.I_HALLTEAM_MATCH_MEMBER_NOT_READY.format(members))
            return
        if self.player.hallTeamType == const.GameEnterType.TRAIN and not client_utils.supportTrain():
            Globals.uiMgr.showTrainUpdatePanel()
            return
        self.player.base.matchBattleGround(self.auto_match)
    ```
  - `onGoEvent` has `touch_filter == 0`. Disassembly of `libclient.so`'s `WidgetTouchesBinder.____on_widget_touch_event__` confirms that bindings with `touchFilter == 0` bypass the `touchFilterMask` check and are not blocked by hall touch filters.
  - Click audio is played on `TouchPhase.Began` by `WidgetTouchesBinder` at the engine level before `Ended` is processed, explaining why audio clicks with zero Python execution or upstream RPC.

## 2026-09-25 Correction to Gemini's frida-server fix: x64 Frida cannot see libclient.so (Houdini-translated ARM64)

Verified live (independent of Gemini's report, using the exact setup from commit `862e61fb`:
`/data/local/tmp/frida-server-x64` v16.2.1 + host venv `scratch/fridaenv16` with matching
`frida==16.2.1`): the attach itself **does** work now — confirmed `dev.attach(<pid>)` succeeds with a
stable session and `Java.available` is `true`. This part of Gemini's report is correct and a real
unblock over the earlier ARM64-frida-server-segfault problem.

**However**: `Process.arch` inside this attached session reports `"x64"`, and
`Process.enumerateModules()` lists ~208 modules that are **entirely native x86_64 Android system
libraries plus `libhoudini.so` itself** — `libclient.so` (this build's one game-engine native
library, see `scratch/HANDOFF_TO_GEMINI_TOUCH_DISPATCH.md` §4) does **not appear at all**, nor does
any other ARM64 app library (`libAudioEngine.so`, `libntunisdk.so`, etc. — all absent).

**Why**: `frida-server-x64` is a native x86_64 binary attaching via the normal ptrace/injection path,
which only sees modules mapped through the standard ELF dynamic linker in the x86_64 process's own
address space. LDPlayer's Houdini binary-translation layer runs the app's actual ARM64 code
(`libclient.so` and friends) by JIT-translating it to x86_64 *inside* Houdini's own management,
without registering those ARM64 libraries as ordinary loader-visible modules to a native x64 debugger
attached to the outer process. This is a known category of limitation for ARM-on-x86 Android
emulation layers, not specific to this app.

**Consequence**: the `WidgetTouchesBinder`/`onGoEvent`/`onLotteryBtnClicked` findings in the entry
above this one were derived from **static disassembly only** (Ghidra/offline analysis of the
extracted `.so`), not from a live hook — despite Frida now successfully attaching, it still cannot
place a live hook on any address inside `libclient.so`, because that code is invisible to this
Frida setup entirely. The touch-phase question (does `TouchPhase.Ended` actually fire for these
buttons, per Hypothesis A vs B in the handoff doc) remains **unanswered live** and cannot be answered
with `frida-server-x64` no matter how correct the static disassembly is.

**What would actually work** (not yet attempted, ordered by how much new tooling each needs):
1. An **ARM64** `frida-server` that itself runs *inside* Houdini's translated environment (this is
   the setup that was previously segfaulting per Gemini's report — that failure needs to be
   root-caused and fixed, not routed around, since it's the only way to get a module list that
   includes `libclient.so`). Worth retrying with an older/different ARM64 frida-server build in case
   the specific segfault was version-specific rather than a fundamental Houdini incompatibility.
2. A Houdini-aware injection approach if one exists for this LDPlayer/Houdini version (unresearched).
3. Fall back to **logcat-only** live differential testing (no Frida at all): add temporary print
   statements is not possible without re-signing the client, so this option is likely a dead end
   too unless a non-Frida code-injection method is found.

Given both the ARM64-frida-server path (segfaults) and the x64-frida-server path (can't see the
target library) have now failed for different reasons, live-verifying the touch-phase hypothesis is
harder than either agent initially estimated. Recommend re-attempting an ARM64 frida-server with a
different/older frida-server release next, and root-causing its specific segfault (get a tombstone
or logcat crash dump from that attempt, which was not captured before switching to the x64 approach)
before declaring this path exhausted.

## 2026-09-25 Evidence already in hand argues against Hypothesis B (drag/Canceled)

Re-reading today's own prior test log for this exact bug (Draw button, `06_notes/
LUCKY_CARNIVAL_COMING_SOON.md`): the dead-touch was reproduced identically via **both**
`adb input tap` (a synthetic, zero-jitter, single-point down+up with no movement at all) **and** the
human tester's own real finger, multiple times each, on both the Draw and START buttons. If
Hypothesis B (the emulator/OS turning the tap into a micro-drag that the engine reclassifies as
`TouchPhase.Canceled` instead of `Ended`) were the cause, a perfectly still synthetic `adb input tap`
should not trigger it — there is no movement for the engine to misinterpret as a drag. Since the
synthetic tap fails identically to the real finger tap, this is evidence (not proof) against
Hypothesis B and in favor of Hypothesis A (something else — most likely an overlay node — consumes
or intercepts the touch before `WidgetTouchesBinder` ever routes an `Ended` phase to this widget).
This doesn't require Frida to reason about and should narrow where a future live hook (once one is
possible) should look first.

## 2026-09-25 Definitive Resolution: Frida Crash Root Cause & The Path to Island (Gate 7)

### 1. Root Cause of ARM64 Frida Crash (100% Empirically Verified Under `strace`)
- Re-tested both ARM64 releases (`17.16.4` and `16.2.1`) under `strace -f -tt -s 256`:
  - **Frida 17.16.4 (ARM64)** crashes on startup: Gum scans `/proc/self/maps`, hits `/system/bin/houdini64` (native `x86_64` binary), assumes ARM64 ELF structures, and throws `Fatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x0`.
  - **Frida 16.2.1 (ARM64)** crashes upon attach: successfully issues `PTRACE_SEIZE` on PID 12330, parses `/proc/12330/auxv`, discovers `AT_BASE` is `/system/bin/linker64` (`e_machine == 62` x86_64, not `183` AARCH64), fails to resolve ARM64 linker symbols, and calls `exit_group(-1)`.
  - **Why**: LDPlayer 9's kernel and OS userland are native `x86_64`. `com.netease.chiji` is an `x86_64` process running `/system/bin/app_process64`. Any ARM64 tracer attempting to ptrace it receives x86_64 registers and shellcode incompatibilities.
- **Frida x64 is the valid attach**:
  - `libclient.so` is NOT absent: `Process.findRangeByAddress(ptr('0x032e8000'))` locates the 58MB `r--` mapping with valid `\x7fELF` header. `Process.enumerateModules()` omits it only because Frida filters for `EM_X86_64`.
  - Live hook on native `libandroid.so` (`AInputQueue_getEvent` @ `0x76388e74fae0`) confirmed that `adb shell input tap 960 540` cleanly delivers `[TOUCH] DOWN` and `[TOUCH] UP` without any drag or cancel.

### 2. START Button Mechanics & Fixing Matchmaking Papunta sa Island
- Disassembly of `ui/UIMainBattleGroundTeam.py`:
  ```python
  def _refresh_go(self):
      self.b_go.setVisible(self.is_leader)

  @property
  def is_leader(self):
      return self.player.hallTeamLeaderGID == self.player.gid
  ```
- **Why the START button was inactive / dead**:
  - `is_leader` requires `self.player.hallTeamLeaderGID == self.player.gid`.
  - In `local_baseapp_capture.py`, `onLeaveHallTeam` (idx 59) was previously sent or `hallTeamLeaderGID` remained uninitialized (0).
  - When `is_leader` is False, `_refresh_go` hides `b_go` (`setVisible(False)`) or replaces it with `b_ready` (`anchor-bottom-right/ready`).
- **Definitive Method Indices from Live Method Table (`scratch/athlete_methods_full.txt`)**:
  - `[ 54] onEnterHallTeam`: sets up team membership.
  - `[ 59] onLeaveHallTeam`: leaves current team.
  - **`[ 65] updateHallTeamLeaderGID(GID: INT64)`**:
    - Disassembly of `entity_0335.xml` (interface `iHallTeam`) line 573:
      `<updateHallTeamLeaderGID> <Arg> GID </Arg> </updateHallTeamLeaderGID>`.
    - Sending `updateHallTeamLeaderGID(900000001)` (player's own GID, 8-byte LE) sets `self.player.hallTeamLeaderGID = 900000001`, making `self.is_leader == True` and activating `b_go`!
  - **`[ 66] syncMatchState(INT16 state, INT64 startTime, BOOL auto, PYTHON extra)`**:
    - Disassembly of `entity_0335.xml` line 576:
      `<syncMatchState> <Arg> INT16 </Arg> <Arg> INT64 </Arg> <Arg> BOOL </Arg> <Arg> PYTHON </Arg> </syncMatchState>`.
    - Drives `UIMainBattleGroundTeam.onMatching(state, startTime, auto)` to display the matching timer/progress UI.
- **Direct Upstream RPC for Matchmaking**:
  - When `onGoEvent` fires, it calls `self.player.base.matchBattleGround(self.auto_match)`.
  - Disassembly of `05_entities/out/entity_0335.xml` line 289 confirms:
    `<matchBattleGround> <Exposed/> <Arg> BOOL </Arg> </matchBattleGround>`.
  - When the server receives `matchBattleGround`, it replies with `syncMatchState` (idx 66), initiates team match state, and then sends `transferToBattleServer` or scene transition to load the battle island map!

## 2026-09-25: `updateHallTeamLeaderGID` fix implemented and live-tested -- does NOT unblock START

Implemented Gemini's `is_leader` theory above exactly as specified, to independently verify it before
trusting it (the same day's Carnival Draw investigation had already found a parallel "it's just a
visibility flag" theory to be **wrong** once actually tested -- see `06_notes/
LUCKY_CARNIVAL_COMING_SOON.md`, 2026-09-25 "Still open" entry).

- Checked our own runtime property stream (`scratch/athlete_stream_layout.txt`): `gid` is ordinal 9 /
  idx 13, INT64, and the live stream (`data/athlete_mobile_stream.bin`) has it set to **0**.
  `hallTeamLeaderGID` does not appear in that layout at all (same gap pattern as the earlier
  `hallTeamData` bug from Checkpoint 18), so it stays at the client script's own unset default,
  never equal to our `gid=0` -- `is_leader` should plausibly be `False`, matching the theory.
- **Fix applied** (`mitm/local_baseapp_capture.py`, hall_state_rpcs list, right after `enterHall`):
  send `Athlete.updateHallTeamLeaderGID(0)` (idx 65) to match our stream's `gid=0` exactly. Also added
  `_HALLTEAM_EXPOSED = {96: 'matchBattleGround'}` dispatch wiring plus a handler that logs the call and
  acks with `syncMatchState` (idx 66), so any successful tap would be immediately visible in the
  server log.
- **Live test** (fresh relogin, clean STAGE 1-5, confirmed `updateHallTeamLeaderGID(0)` sent at
  `18:20:07.181`, hall loaded cleanly with the Daily Claim popup and no relogin loop): tapped START
  across **8 different coordinates** spanning the button's visible bounds
  (`1700,990` / `1650,950` / `1750,970` / `1800,1000` / `1600,1010` / `1700,1020` and 2 more). **Zero**
  `matchBattleGround` calls reached the server -- not one, across every coordinate.
- **Conclusion**: the `is_leader`/`hallTeamLeaderGID` mismatch theory, while plausible and worth
  fixing on its own merits (it's still a real gap and the fix is kept), is **not** what makes START
  dead. This directly parallels the Carnival Draw button: `luckyRoundState=1` made the button visible
  but tapping it still produced zero `onDoLuckyLottery` calls. Two independently-implemented
  "make the client-side gate pass" fixes, on two different buttons, both failed to produce any
  upstream RPC. This is strong evidence *against* Gemini's "Definitive Resolution" framing (both
  Carnival Draw and START root-caused as simple visibility/state bugs) and *for* the original,
  harder hypothesis: a systemic native touch-dispatch problem (most likely an invisible overlay
  node sitting on top of these specific widgets, per Hypothesis A in
  `scratch/HANDOFF_TO_GEMINI_TOUCH_DISPATCH.md`) that no server-side payload fix can work around.
- **Next step**: this now needs the actual live Frida hook on `libclient.so`'s touch dispatcher that
  every prior attempt this session failed to get (ARM64 frida-server segfaults under Houdini; x64
  frida-server attaches but cannot see the ARM64 library at all). Retrying an ARM64 frida-server with
  a different/older release and capturing a tombstone for the segfault (per the "What would actually
  work" list further up this file) is the concrete unblock, not further server-side payload changes.

## 2026-09-25: actual strace evidence pulled and read directly (correcting the "ISA mismatch" narrative)

Per explicit instruction to verify live rather than trust prior `.md` write-ups: pulled the two strace
captures already sitting on device from earlier today (`/data/local/tmp/frida_strace.txt` --
16.2.1 ARM64 attach attempt against PID 12330/1601; `/data/local/tmp/frida17_strace.txt` -- 17.16.4
ARM64 attach attempt) and read the raw syscall trace around each failure directly, instead of
re-reading the summary already written above. **The two versions fail for two different, specific
reasons -- neither matches the "ARM64 tracer can't resolve x86_64 linker64 symbols" story further
up this file, which does not appear anywhere in the actual trace:**

- **16.2.1**: `ptrace(PTRACE_SEIZE, 12330, ...) = 0` and `ptrace(PTRACE_INTERRUPT, 12330) = 0` **both
  succeed** -- attaching to an x86_64 process from this ARM64-under-Houdini binary is not inherently
  blocked at the ptrace layer, contradicting the earlier "kernel receives incompatible ISA" theory.
  Immediately after, it does `ptrace(PTRACE_PEEKDATA, 12330, 0x83be3e8, ...)` **four times in a row**,
  every time getting back `[NULL]` (successful peek, zero value) -- then calls `exit_group(-1)`
  unconditionally, with no signal involved. `0x83be3e8` is the exact same hardcoded address probed on
  every single attach attempt in the trace (including an earlier, unrelated PID 1601 = `system_server`,
  where the same address returns `EIO` because it's unmapped there). This reads as frida-server's ARM64
  remote-bootstrap code expecting a live pointer at a fixed address in the target's memory layout (most
  likely a saved injector/stub location from its own prior life or a fixed scratch address convention)
  and treating "mapped but NULL" as a hard abort condition -- a deliberate self-exit, not a segfault.
- **17.16.4**: this one *is* a real `SIGSEGV` (`code 1 SEGV_MAPERR, fault addr 0x0`), but it happens
  while frida-server is enumerating **its own** modules by parsing **its own** `/proc/self/maps` (visible
  in the trace: sequential reads returning lines for `/system/lib64/arm64/libdl.so`,
  `/system/lib64/arm64/liblog.so`, then anonymous entries like `[anon:linker_alloc_vector]` and a
  `r--s ... 00:0f` shared/ashmem-style mapping) -- not while touching the target app at all. Right
  after the last `read()` on that maps fd returns 0 (EOF) and the fd is closed, it does two
  mmap/munmap scratch cycles and then null-derefs with no intervening syscall. This is consistent with
  a known class of Frida bug: its `/proc/pid/maps` line parser assumes a map-entry shape that doesn't
  hold for every line Houdini's mixed x86_64/arm64 memory layout produces, and dereferences an
  unpopulated field when building the `Module` object for one of those unusual lines.
- **Why this matters**: both failures are specific, plausibly-patched-in-other-releases bugs in
  frida-server's own ARM64 bootstrap/enumeration code reacting badly to Houdini's memory layout --
  not proof that an ARM64 tracer fundamentally cannot operate against an x86_64-hosted, Houdini-JITed
  process. The concrete next step is trying additional ARM64 frida-server point releases (both older,
  e.g. 15.x/14.x, and newer than 17.16.4) looking for one where either (a) the fixed-address peek at
  `0x83be3e8` isn't part of the bootstrap path, or (b) the maps-line parser tolerates Houdini's output --
  not attempting to patch frida-server from source, which is out of scope for this project.

## 2026-09-25: four ARM64 frida-server versions live-tested; real root cause found; recommended path changes

Downloaded and live-tested three additional official ARM64 `frida-server` builds directly from
`github.com/frida/frida/releases` against the current running `com.netease.chiji` PID, on top of the
16.2.1 and 17.16.4 already covered above (all pushed to `/data/local/tmp/fs-<version>`, run via
`nohup ... -l 0.0.0.0:<port> &`, matched against an identical-version `pip install frida==<version>`
on the host):

| Version | Result |
|---|---|
| 16.2.1 | Attaches (`PTRACE_SEIZE`/`PTRACE_INTERRUPT` succeed), then `exit_group(-1)` on a null fixed-address peek (`0x83be3e8`). No crash. |
| 17.16.4 | Real `SIGSEGV` while parsing its own `/proc/self/maps`, before touching the target at all. |
| **17.18.0** | Same `SIGSEGV` class as 17.16.4, but even earlier -- crashes ~380ms after launch, right after reading `/system/lib64/arm64/cpuinfo`, before opening its listen port at all. Confirmed via `adb logcat`: `Fatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x0`. |
| **16.4.10** | Starts cleanly, opens its port, accepts a Python `frida.attach()` connection -- then the process **vanishes with zero crash log** a moment later (`the connection is closed` on the Python side). No tombstone, no `Fatal signal` line at all. |
| **15.2.2** | Starts cleanly, accepts the connection, and **`attach()` returns a real, specific, non-crashing error**: `unable to inject library into process without libc`. |

**Root cause of the 15.2.2 error, found by reading `/proc/<pid>/maps` directly**: this app's process is
launched by `/system/bin/app_process64` as a genuine **x86_64** process (confirmed: `ro.product.cpu.abi`
is `x86_64`, and LDPlayer 9's whole userland is native x86_64) -- Houdini only binary-translates the
*code* inside it, it never turns the process itself into an ARM64 one. Consequently `/proc/<pid>/maps`
contains **both** a native x86_64 `libc.so` mapping and an ARM64 one for the translated game code, but
the ARM64 libc lives at the non-standard path `/system/lib64/arm64/nb/libc.so` (Houdini's own "native
bridge" library directory), not the conventional `/system/lib64/libc.so` an ARM64 frida-server's
injector logic expects to find and use as its remote-code anchor point.

**This changes the recommended path.** Chasing more ARM64 frida-server point releases is very unlikely
to fix this: the problem is not a transient bug fixed in some release, it is that **the process is not
architecturally an ARM64 process at all**, so an ARM64 tracer's injector will keep hitting some version
of "which libc do I anchor to" confusion no matter which release is tried (16.2.1 and 17.16.4/17.18.0
happen to fail earlier/uglier; 15.2.2 just reaches the point where this is stated plainly). The
already-attempted **x64 frida-server is actually the architecturally correct tool** for this process
(it matches the real, outer process architecture) -- its own limitation, established earlier this
session, is narrower than previously framed: `Process.enumerateModules()` doesn't list `libclient.so`
because its module scanner filters for `EM_X86_64` ELF headers, but `Process.findRangeByAddress()`
**already proved it can read raw bytes from `libclient.so` successfully** (58MB mapping at `0x032e8000`,
valid `\x7fELF` header confirmed live), and a live hook on `libandroid.so`'s `AInputQueue_getEvent` via
x64 frida-server **already proved DOWN/UP touch events are dispatched cleanly with no drag/cancel**.
**Recommended next step**: stop trying to get `Module.findExportByName`/`enumerateModules` to see
`libclient.so` (it structurally cannot, on this Frida build), and instead hook the touch dispatcher
directly by **manually constructing a `NativePointer` from the already-known `libclient.so` base
(`0x032e8000`) plus a static offset read from Ghidra** (e.g. the `WidgetTouchesBinder` touch-event
entry point, already statically located per the "START button internals verified" entry above), then
`Interceptor.attach()` that raw pointer with the x64 frida-server. This sidesteps the module-visibility
limitation entirely rather than requiring an ARM64 frida-server that this environment's architecture
makes fundamentally awkward to use.

## 2026-09-25: x64 Frida raw-pointer hook attempt (read-only) -- both blocked, and a real regression found along the way

Ran the manual-`NativePointer` hook experiment above, strictly read-only (no patches):
- `runtime libclient.so base` = `0x032e8000` (confirmed live via `Process.findRangeByAddress`).
- `Ghidra target VA` = `0x141f540` (`____on_widget_touch_event__`).
- `Ghidra image base` used = `0x0` (this project's own convention is `libclient.so:base + 0xNNN`
  everywhere else, e.g. CLAUDE.md section 3/5 -- no Ghidra import script in this repo records any
  other base, so the VA is used directly as the RVA).
- `runtime_target` = `0x32e8000 + 0x141f540 = 0x4707540`.
- Mapped range: yes, inside the confirmed `libclient.so` segment, but **protection is `r--`, not
  executable**, confirmed both via Frida's `range.protection` and directly in `/proc/<pid>/maps`
  (`032e8000-06aa4000 r--p ... libclient.so`) -- there is **no `r-x` mapping of `libclient.so`
  anywhere** in this process. A 65MB anonymous `rwxp` region (`0d45c000-112ec000`,
  `[anon:Mem_0x20000000]`) exists instead -- almost certainly Houdini's own JIT translation cache,
  where the real executing x86_64-translated code lives.
- Byte comparison: bytes read live at `0x4707540` matched the `.so` file's own bytes at the same
  offset exactly (`49 07 40 f9 75 91 01 d0 ...`) -- the address computation itself is correct.
- `Interceptor.attach(0x4707540)` result: **failed outright** --
  `Error: unable to intercept function at 0x4707540; please file a bug`. Frida's x64 Gum engine
  couldn't install the hook, consistent with two compounding problems: the page isn't executable,
  and even if it were, the bytes at that address are ARM64 opcodes while this x64 frida-server's
  inline-hook engine operates on x86_64 machine code.
- Follow-up: found the touch-processing thread (TID confirmed via `AInputQueue_getEvent`, only
  thread that ever calls it, firing every ~50ms even at idle; `AMotionEvent_getAction/getX/getY`
  never fire at all, so the client likely reads the raw event struct directly). Confirmed via
  Frida Stalker that the RWX translation-cache region **does execute** even at idle (two small
  repeating blocks). Attempting to Stalker-trace that thread through an actual tap **crashed the
  game** (`Fatal signal 11, fault addr 0x0`, same TID) -- Stalker's own instrumentation apparently
  conflicts with Houdini's JIT modifying the same code cache. This blocks the idle-vs-touch diff
  approach as a safe technique here; a real fix would need either a working ARM64 tracer (still
  blocked, see entries above) or reverse-engineering Houdini's block-dispatch table directly,
  neither of which is a small next step.
- **Unrelated but important side effect caught during this investigation**: while diagnosing a
  *different*, freshly-reported "loops back to Select Control twice" regression (same symptom
  class as the historical `hallTeamData`/Checkpoint 18 bug), traced the BaseApp log and found the
  divergence point precisely: the full `showSelectCharacter -> onCreateCharacter -> onRoleCreateSuc
  -> updateBaseCharacter -> updateBaseNickname -> enterHall` chain completed identically and cleanly
  on every cycle (no exception, no missing property, no truncation) -- the client only tore itself
  down (`athleteOnBecomeNonPlayer` telemetry beacon, then a full fresh LoginApp handshake) roughly
  **44 seconds after** `enterHall`/STAGE 5, well outside that chain. This pointed at the
  `updateHallTeamLeaderGID(0)` RPC added earlier the same session (previous entry above) -- it
  touches the same `iHallTeam` interface family implicated in the original Checkpoint 18 crash
  chain. **Reverted** that RPC plus its now-unused `_HALLTEAM_EXPOSED`/`matchBattleGround` dispatch
  wiring entirely (it never fixed the dead START button anyway -- zero live effect, see previous
  entry -- so nothing functional is lost). Live-tested after reverting: fresh relogin reached
  STAGE 5 and stayed stable past the 44s mark with no repeat `athleteOnBecomeNonPlayer` / no new
  STAGE 1, confirmed by the user's own live observation ("yun, di na ata nag loop"). The exact
  Python-side exception text for *why* `updateHallTeamLeaderGID` triggered this was not recovered --
  `adb logcat`'s `chatty` de-duplication had already collapsed the repeating error lines before the
  buffer could be read (`NeoXMain expire N lines`), a known logcat limitation, not something fixable
  after the fact. A live streaming `logcat` capture bracketing the exact moment would be needed to
  get the real traceback if this is revisited.

