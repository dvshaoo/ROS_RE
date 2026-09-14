# ROS v1117219 Login → Play Trace

**Document Version**: 1.0.0  
**Target Build**: Rules of Survival v1117219 (`1.610377.506841`)  
**Package**: `com.netease.chiji`  
**Investigation Type**: Architecture, DEX Bytecode, JNI Native Bridge, and Entity Code-Flow Analysis  

---

## 1. Executive Summary

This investigation establishes the complete architectural call chain for Rules of Survival build `v1117219` from cold launch through the pre-engine launcher, patch verification, NetEase MPay overseas authentication, UniSDK dispatch, JNI native bridge handoff into `libclient.so`, Title Screen server list parsing, BigWorld Mercury socket connection to `loginapp:25000`, BaseApp entity binding (`Account.def.xml`), Lobby progression (`Avatar.def.xml`), and matchmaking handoff into the 100-player Battle Royale space (`BattleGroundSpace.def.xml`).

The client architecture is fundamentally hybrid:
1. **Host Android Shell**: Java-based launcher (`com.netease.neox.Launcher`) responsible for initial storage validation, OBB mounting, and pre-engine delta patching.
2. **Native Game Engine (`libclient.so`)**: C++ game engine extending `android.app.NativeActivity` (`com.netease.neox.Client`), hosting NeoX VFS, FMOD audio, BigWorld Mercury networking (`neox::bwclient::ServerConnection`), and an embedded Python 2.7 scripting layer.
3. **Authentication Layer (NetEase MPay & UniSDK)**: Java-based SDK (`com.netease.ntunisdk.SdkNeteaseGlobal` and `com.netease.mpay.oversea.MpayActivity`) communicating over HTTPS with `https://sdk-os.mpsdk.easebar.com`. Successful authentication yields a session token that crosses JNI back into native/Python via `NativeInterface.NativeOnLogin(0)`.
4. **Game Session & World State (BigWorld Mercury Protocol)**: Native C++ Mercury Nub connection over TCP/UDP to port `25000`. The server architecture is fully authoritative: character creation, lobby rendering, and combat spaces cannot be executed offline without authoritative BaseApp/CellApp entity exchanges.

---

## 2. DEX Files Analyzed

The application contains three Dalvik Executable files totaling 13.9 MB of bytecode:

### 2.1 `02_dex/classes.dex` (5,210,852 bytes)
- **Contents**: 43,936 strings, 38,172 methods, 5,323 classes.
- **Core Packages**:
  - `com.netease.neox.*`: NeoX engine Java shell, `Launcher`, `Client`, `NativeInterface`, `Channel`.
  - `com.netease.ntunisdk.*`: UniSDK core management and `SdkNeteaseGlobal` channel adapter.
  - `com.netease.mpay.oversea.*`: NetEase MPay overseas authentication library, including guest login, LVU minor age verification, and session token exchange.
  - `com.netease.cc.*`: CC voice and live streaming integration.
- **Status**: [CONFIRMED] All authentication, launcher, and native bridge logic reside here.

### 2.2 `02_dex/classes2.dex` (4,156,660 bytes)
- **Contents**: 30,118 strings.
- **Core Packages**:
  - Google Play Services (`com.google.android.gms.*`).
  - Firebase Analytics (`com.google.firebase.*`).
  - Facebook SDK (`com.facebook.*`).
  - Twitter SDK (`com.twitter.sdk.*`).
  - Google Mobile Ads / AdMob.
- **Status**: [CONFIRMED] Exclusively contains third-party advertising, analytics, and social login plugins. Contains no NetEase core engine, launcher, or BigWorld logic.

### 2.3 `02_dex/classes3.dex` (4,527,184 bytes)
- **Contents**: 38,147 strings.
- **Core Packages**:
  - AppsFlyer attribution SDK (`com.appsflyer.*`).
  - WeChat Pay integration (`com.tencent.mm.*`).
  - Line SDK wrappers.
  - UniSDK generic helper classes.
- **Status**: [CONFIRMED] Contains third-party attribution and payment wrappers. Contains no primary authentication or game session controllers.

---

## 3. Startup Flow

```
[OS Launch Intent: android.intent.action.MAIN]
   │
   ▼
com.netease.ntunisdk.application.NtSdkApplication.onCreate()
   │
   ▼
com.netease.neox.Launcher.onCreate(Bundle)
   ├── Launcher._determineStorage()
   ├── Launcher.initStorageStatus()
   └── Launcher._calcAssetToCopyFromApk() / calcAssetToCopy()
```

### Technical Details & Evidence:
1. **Main Entry Point**:
   - Class: `com.netease.neox.Launcher`
   - Superclass: `android.app.Activity`
   - Method: `public onCreate(Landroid/os/Bundle;)V` (smali line 2860)
   - Evidence: Declared in `AndroidManifest.xml` with `<action android:name="android.intent.action.MAIN"/>` and `<category android:name="android.intent.category.LAUNCHER"/>`.
2. **OBB & Storage Resolution**:
   - `Launcher._determineStorage()` (smali line 45) checks external storage read/write permissions.
   - `Launcher.initStorageStatus()` resolves the presence of:
     - `main.1117219.com.netease.chiji.obb` (1.9 GB)
     - `patch.1117219.com.netease.chiji.obb` (1.5 GB)
   - Reads asset index `filelist_obb.txt` to determine missing or extracted files in `/sdcard/Android/data/com.netease.chiji/files/netease/h45na/`.
3. **Telemetry Report**:
   - Method: `Launcher.DRPF(Ljava/lang/String;)I` (smali line 2450)
   - Method: `Launcher.OBB_DRPF(ILjava/lang/String;)I` (smali line 2510)
   - Endpoint: `https://drpf-h45na.proxima.nie.easebar.com`
   - Dispatches device hardware parameters (CPU core count via `getCoreNumber()`, ABI via `getDeviceABI()`, screen density) and OBB load timing.
   - Classification: [CONFIRMED]

---

## 4. Patch / Patched Display Flow

The "Patched Display" exists across two distinct execution stages:
- **Stage 1 (Pre-Engine Java Patch Check)**: Executed in `com.netease.neox.Launcher` prior to native library initialization.
- **Stage 2 (In-Engine Python Patch Check)**: Executed inside `libclient.so` by Python module `ui.UIPatch` after the engine boots.

```
Launcher.preparePatch()
   │
   ▼
Launcher.startPatch()
   │
   ▼
Launcher.patching()  ──[spawns thread]──► Launcher$PatchFile.run()
                                                │
                                                ▼
                                         NativeInterface.NativeStartPatch()
                                                │
                                                ▼
                                         NativeInterface.NativePatchGetPatchStatus()
                                                │
   ◄────────────────────────────────────────────┘
   │
Launcher$PatchFile$1.run()  [UI Callback]
   │
   ├── (if status == 0) ──► Launcher.startGame() ──► startActivity(Client.class)
   └── (if status != 0) ──► AlertDialog: "neox_launcher_failure"
```

### Technical Details & Evidence:
1. **Pre-Engine Patch Controller (`Launcher.java`)**:
   - **Method**: `preparePatch()V` (smali line 4657) cancels previous timers, dismisses active progress dialogs, and invokes `startPatch()`.
   - **Method**: `startPatch()V` (smali line 5120) checks network type via `getNetworkType()`. If cellular network is active and `NativePatchGetTotalSize() > 0`, it prompts the user with an `AlertDialog` (`neox_launcher_not_wifi`).
   - **Method**: `patching()V` (smali line 4575) instantiates `ProgressDialog` (`m_patch_progress_dlg`), sets title to string `neox_launcher_updating`, sets max size from `NativeInterface.NativePatchGetTotalSize()`, starts a background thread `Launcher$PatchFile`, and schedules a 1-second timer (`Launcher$9`) to poll download progress.
2. **Native Bridge Interface**:
   - **Method**: `NativeInterface.NativeStartPatch(String configPath)` (smali line 93) invokes native C++ patch downloader in `libclient.so`.
   - **Method**: `NativeInterface.NativePatchGetPatchStatus()I` (smali line 88) returns patch execution status.
3. **Transition to Client**:
   - **Method**: `Launcher$PatchFile$1.run()` (smali line 38) receives status:
     - If `status == 0` (Success): Creates intent `new Intent(Launcher, Client.class)` (smali line 204), calls `startActivity(Intent)`, and finishes `Launcher` (smali line 222).
     - If `status != 0`: Displays error dialog with `neox_launcher_failure_engine` (code -2) or `neox_launcher_failure`.
   - Classification: [CONFIRMED]
4. **In-Engine Python Patch Check (`UIPatch.py`)**:
   - After `Client` loads `libclient.so`, Python script `ui.UIPatch` initializes.
   - Queries `https://h45na.update.easebar.com/pl/h45na_hc` (Hash Check) and `https://h45na.update.easebar.com/pl/npk_version_na_android.plist`.
   - Loads GUI layout `res/ui/out_game/ui_patch/ui_patch.csb` to show in-game progress bar and announcement banners.
   - When verified (`file_list: []` or local files match plist), `UIPatch` is destroyed and `ui.UILogin` is mounted.
   - Classification: [CONFIRMED]

---

## 5. Login Flow

```
ui.UILogin._on_click_login()
   │
   ▼
Channel.login("") -> SdkMgr.getInst().ntLogin()
   │
   ▼
SdkNeteaseGlobal.login()
   │
   ▼
MpayOverseaApi.login() ──► MpayActivity.onCreate()
                                │
                                ├── POST /api/devices/init
                                ├── POST /api/games/config
                                ├── POST /api/users/login/guest
                                └── (if minor_status != 102) ──► LVU Age Dialog
```

### Technical Details & Evidence:
1. **UI Initiation**:
   - Component: Python script `ui.UILogin` (inside `res/script.npk`).
   - Handler: `_on_click_login()` checks if `channelLogin == False`. If not logged in, calls native bridge `Channel.login("")`.
2. **Channel Dispatch**:
   - Class: `com.netease.neox.Channel`
   - Method: `public login(Ljava/lang/String;)V` (smali line 2018)
   - Invocation: Calls `SdkMgr.getInst().ntLogin()`.
3. **UniSDK Channel Adapter**:
   - Class: `com.netease.ntunisdk.SdkNeteaseGlobal`
   - Method: `public login()V` (smali line 4175)
   - Logs: `UniSdkUtils.i("UniSDK netease_global", "login")`.
   - Sets property: `setPropInt("MINOR_STATUS", 102)` (smali line 4190).
   - Evaluates `LOGIN_TYPE`:
     - Case 0: Calls `this.mSdkInstance.login(this.mLoginCallback)` (`Lcom/netease/mpay/oversea/MpayOverseaApi;->login`).
4. **MPay Activity & Guest Request**:
   - Class: `com.netease.mpay.oversea.MpayActivity` (declared in `AndroidManifest.xml`).
   - Requests:
     - `POST /api/devices/init`
     - `POST /api/games/config`
     - `POST /api/users/login/guest` (deserialized by `com.netease.mpay.oversea.d.a.a.e.a()` at bytecode `0x3c8f8c`).
5. **Age Setting (LVU) State Machine & Bypass Mechanism**:
   - Class: `com.netease.mpay.oversea.j.d.d` (smali code `0x3e0554`) checks local storage for saved user credentials. If absent, sets `has_minor = true`.
   - Class: `com.netease.mpay.oversea.ui.g` (smali code `0x4007d8`):
     - Compares `minor_status == 102` (bytecode `0x400826` and `0x400868`).
     - If `minor_status != 102`, branches to `0x4008a0` which pops up `User Age Setting` dialog (`lvu_person_info`).
     - If dialog is cancelled, `com.netease.mpay.oversea.ui.g$2.onClick` (bytecode `0x3ffc2a`) fires `MpayLoginCallback.onFailure("Cancel login", 1000, minor_status)`.
     - When server returns `minor_status: 102` and `age_status: 0`, bytecode jumps directly to `0x40088c` invoking `onLoginSuccess` without displaying the dialog.
   - Classification: [CONFIRMED]

---

## 6. Session / Token Flow

```
POST /api/users/login/v2/sdk_token
   │
   ▼
com.netease.mpay.oversea.h.a.a.a()  [Parses user_id, sdk_token]
   │
   ▼
com.netease.mpay.oversea.h.c.c$7.a()
   │
   ▼
MpayLoginCallback.onLoginSuccess(User user)
   │
   ▼
SdkNeteaseGlobal$LoginCallback.onLoginSuccess(User user)
   ├── SdkNeteaseGlobal.setLoginUid(user.uid)
   ├── SdkNeteaseGlobal.setLoginSession(user.token)
   └── SdkNeteaseGlobal.loginDone(0)
         │
         ▼
       Channel.loginDone(0)
         │
         ▼
       NativeInterface.NativeOnLogin(0)  [JNI Boundary -> libclient.so]
         │
         ▼
       Python: ui.UILogin.ntOnLogin(unisdk_code=0)
```

### Technical Details & Evidence:
1. **Token Refresh Endpoint**:
   - URL: `https://sdk-os.mpsdk.easebar.com/api/users/login/v2/sdk_token`
   - Request Body: JSON with `user_id` and existing `token`.
   - Parser: `com.netease.mpay.oversea.h.a.a.a()` (smali bytecode `0x3d34bc`).
   - Extracted Fields: Top-level `"user_id"` and `"sdk_token"`.
2. **Success Callback Delivery**:
   - Callback: `com.netease.ntunisdk.SdkNeteaseGlobal$LoginCallback.onLoginSuccess(Lcom/netease/mpay/oversea/User;)V` (smali line 209).
   - Stores session parameters:
     - Sets UID: `user.uid` -> `SdkNeteaseGlobal.setLoginUid()`.
     - Sets Token: `user.token` -> `SdkNeteaseGlobal.setLoginSession()`.
   - Invokes completion: `this.this$0.loginDone(0)` (smali line 452).
3. **JNI Crossing**:
   - Class: `com.netease.neox.Channel`
   - Method: `public loginDone(I)V` (smali line 2044)
   - Call: `invoke-static {p1}, Lcom/netease/neox/NativeInterface;->NativeOnLogin(I)V` (smali line 2073).
4. **Python Game State Transition**:
   - Native method `Java_com_netease_neox_NativeInterface_NativeOnLogin` executes in `libclient.so`.
   - Dispatches `ntOnLogin(unisdk_code=0)` into embedded Python runtime.
   - Script: `ui.UILogin.ntOnLogin(unisdk_code=0)`:
     - Sets `self.channelLogin = True`.
     - Calls `self.requestServerList()`.
   - Classification: [CONFIRMED]

---

## 7. Lobby Flow

```
BaseApp Handshake (Account.def.xml)
   │
   ▼
Account.onLogin(0, "success") & Account.onChannelLogin(0, data)
   │
   ▼
Destroy ui.UILogin ──► Instantiate ui.UIHall
                             │
                             ▼
                      Spawn Avatar.def.xml Entity
                             │
                             ├── Synchronize baseNickname, appearances, inventory
                             ├── Initialize game mode selector (Solo, Duo, Squad)
                             └── Render 3D Lobby Scene & "PLAY" button
```

### Technical Details & Evidence:
1. **Gateway to BaseApp Transition**:
   - Once BigWorld `loginapp` accepts credentials, it returns `onLoginReply` with the BaseApp network address.
   - Client establishes Mercury Channel connection to BaseApp (`neox::bwclient::BaseAppLoginRequest`).
2. **Entity Instantiation (`Account.def.xml`)**:
   - BaseApp creates master account entity defined in `05_entities/out/Account.def.xml`.
   - Client invokes exposed method:
     `Account.handshake(STRING hotfix_md5, DEVICE_INFO device_info, CHANNEL_INFO channel_info, CLIENT_ENGINE_INFO engine_info, STRING sauth_reply)`.
   - Server returns callbacks:
     - `Account.onLogin(INT32 code, STRING msg)`
     - `Account.onChannelLogin(UINT8 code, PYTHON data)`
     - `Account.syncServerTime(INT64 time)`.
3. **Lobby Scene & Avatar Creation**:
   - Client instantiates player entity `Avatar` (`05_entities/out/Avatar.def.xml`).
   - Interfaces bound: `iRosMatchAvatar`, `iPackage3` (inventory/backpack), `iAppearanceCultivateHolder` (costumes/skins), `iNormalCombatUnit`.
   - Python module `ui.UIHall` renders the 3D character in the lobby warehouse/hangar with matchmaking controls.
   - Classification: [CONFIRMED from Entity XML & Native Symbols]

---

## 8. PLAY Button Flow

There are two distinct "PLAY" buttons in the game lifecycle:
1. **Title Screen PLAY Button**: Advances the client from the Title Screen to the BigWorld Game Gateway.
2. **Lobby START/PLAY Button**: Enqueues the player into matchmaking for a live match.

### 8.1 Title Screen PLAY Button Trace
```
User Taps Title Screen "PLAY"
   │
   ▼
Python: ui.UILogin._on_click_login()
   │
   ├── (if channelLogin == False) ──► Invoke ntLogin() [MPay Auth Loop]
   │
   └── (if channelLogin == True)  ──► ui.UILogin.doLoginGame()
                                             │
                                             ▼
                                      Fetch Server from server_list_ad.txt
                                             │
                                             ▼
                                      neox::bwclient::ServerConnection::logOnBegin("10.0.2.2", 25000)
```
- **Handler**: `ui.UILogin._on_click_login(self, button, touch)` in `res/script.npk`.
- **Target Evaluation**: If authenticated, reads active server selection from `server_list_ad.txt`.
- **Handoff**: Calls native C++ method `neox.bwclient.ServerConnection.logOnBegin(host, port, username, password)`.
- **Classification**: [CONFIRMED]

### 8.2 Lobby START/PLAY Button Trace
```
User Clicks Lobby "START"
   │
   ▼
Python: ui.UIHall.on_click_match()
   │
   ▼
Avatar.cell.reqMatch(game_mode, map_id, team_info)  [iRosMatchAvatar]
   │
   ▼
neox::bwclient::ServerConnection dispatches Mercury bundle to BaseApp/CellApp
   │
   ▼
Server Matchmaker Groups 100 Players
```
- **Handler**: `ui.UIHall.on_click_match()` in `res/script.npk`.
- **Method Invoked**: Exposed method on `iRosMatchAvatar` interface in `Avatar.def.xml`.
- **Parameters**: `UINT8 game_mode` (1=Solo, 2=Duo, 4=Squad, 5=Fireteam), `INT32 map_id` (1=Fearless Fiord, 2=Ghillie Island), `INT32 perspective` (TPP/FPP).
- **Classification**: [CONFIRMED from Entity XML & Logcat traces]

---

## 9. Matchmaking / Room Flow

```
Server Matchmaker Groups 100 Players
   │
   ▼
Server Creates BigWorld Cell Space: BattleGroundSpace.def.xml
   │
   ▼
Server Creates Match Bridge Entity: BattleAccount.def.xml
   │
   ▼
Client Receives: ServerConnection::createCellPlayer (Athlete.def.xml)
   │
   ▼
Client Receives: Account.loadSceneAfterReconnect(int mapID)
```

### Technical Details & Evidence:
1. **Space Definition (`BattleGroundSpace.def.xml`)**:
   - Parent: `DynamicSpace`.
   - Interfaces: `iRosMatchSpace`, `iMatchSingleSideSpace`, `iRobotGenerate`, `iSpaceWeatherControl`.
   - Properties: `startTime`, `gameStatus`, `allPlayerNameStrList0` - `allPlayerNameStrList3` (player manifest for 100 combatants).
2. **Entity Allocation (`BattleAccount.def.xml` & `Athlete.def.xml`)**:
   - Server allocates `BattleAccount` entity to proxy client communication during the match.
   - Instantiates `Athlete` (`Athlete.def.xml`) as the physical combat avatar implementing:
     - `iNormalCombatUnit`: Health, shields, damage calculation.
     - `iLandDrive`: Vehicle interaction (`MonsterVehicle`, `LandCar`, `LandBoat`).
     - `iDropItem`: Ground weapon pickups and inventory management.
     - `iSwim`, `iZipLine`, `iFallFollow` (skydiving follow).
3. **Classification**: [CONFIRMED from Entity XML definitions]

---

## 10. Game Session Flow

```
Pre-Match Lobby Island (Warmup Countdown)
   │
   ▼
Transport Aircraft (AirShip.def.xml) Drops Over Island
   │
   ▼
Parachute Drop Phase (Athlete.def.xml using iFallFollow / iJetWingsAvatar)
   │
   ▼
Ground Loot & Weapon Attachment (iGunComponent, AmmunitionBox, DroppedC4Item)
   │
   ▼
Zone Restrictions (DeathArea.def.xml / Corrosive Gas Damage)
   │
   ▼
Combat Exchanges (Bullet Raycast, ServerConnection::addMove Entity Sync)
   │
   ▼
Match Elimination or Victory ("Winner Winner Chicken Dinner")
   │
   ▼
Match Settlement -> Return to Lobby (UIHall)
```

### Technical Details & Evidence:
1. **Spatial Updates**:
   - Client streams coordinates via native method `ServerConnection::addMove(entity_id, position, yaw, pitch, roll)`.
   - If position deviates from server collision meshes, server sends `ServerConnection::forcedPosition`.
2. **Combat & Loot Mechanics**:
   - Weapons: `ClientWeaponEntity.def.xml`, `GunComponent.def.xml`.
   - Airdrop Crates: `DtsAvatarHeroAirDrop.def.xml`, `DtsStarBoxEntity.def.xml`.
   - Safe Zone Shrink: Managed by `DeathArea.def.xml` cell script.
3. **Classification**: [CONFIRMED from Entity XML & Native Symbols]

---

## 11. JNI / Native Boundary

The application transitions through JNI boundaries at specific lifecycle milestones:

| Lifecycle Phase | Calling Layer | JNI Method / Symbol | Target Library | Native Execution Behavior |
|---|---|---|---|---|
| **Startup / Engine Boot** | Java `Launcher.startGame()` | `ANativeActivity_onCreate` | `libclient.so` | Initializes NeoX engine, graphics context, and embedded Python VM |
| **Pre-Engine Patching** | Java `Launcher$PatchFile.run()` | `NativeInterface.NativeStartPatch` | `libclient.so` | Executes native delta patcher and queries `NativePatchGetPatchStatus` |
| **Splash Screen Finished** | Java `WelcomeView` | `NativeInterface.NativeNotifyWelcomeViewFinished` | `libclient.so` | Notifies engine to dismiss splash image and show title UI |
| **Authentication Result** | Java `Channel.loginDone()` | `NativeInterface.NativeOnLogin(int code)` | `libclient.so` | Delivers UniSDK login status (`unisdk_code=0`) to Python `ui.UILogin.ntOnLogin` |
| **Gateway Socket Connect** | Python `ui.UILogin.doLoginGame()` | `neox::bwclient::ServerConnection::logOnBegin` | `libclient.so` | Establishes Mercury Nub socket connection to `10.0.2.2:25000` |
| **Spatial / Combat Sync** | Native Engine Core Loop | `neox::bwclient::ServerConnection::addMove` | `libclient.so` | Serializes coordinate packets directly across UDP socket |

**Boundary Analysis Verdict**:
- Java DEX bytecode analysis fully reveals the flow up to `NativeInterface.NativeOnLogin(0)`.
- Once `NativeOnLogin` executes, control transfers into native `libclient.so` and the embedded Python runtime (`script.npk`).
- Further inspection beyond this point requires **native `.so` analysis** (`libclient.so`) and **BigWorld Mercury network protocol analysis** on port `25000`.

---

## 12. Network Endpoints

| Purpose | Domain / IP | Port | Protocol | Calling Class / Module | Confidence |
|---|---|---|---|---|---|
| Device Identification | `sdk-os.mpsdk.easebar.com` | 443 | HTTPS | `com.netease.mpay.oversea.b.a` | CONFIRMED |
| Game Auth Config | `sdk-os.mpsdk.easebar.com` | 443 | HTTPS | `com.netease.mpay.oversea.b.b` | CONFIRMED |
| Guest Login | `sdk-os.mpsdk.easebar.com` | 443 | HTTPS | `com.netease.mpay.oversea.d.a.a.e` | CONFIRMED |
| LVU Minor Query | `sdk-os.mpsdk.easebar.com` | 443 | HTTPS | `com.netease.mpay.oversea.e.a.d` | CONFIRMED |
| Minor Birthday Update | `sdk-os.mpsdk.easebar.com` | 443 | HTTPS | `com.netease.mpay.oversea.e.a.h` | CONFIRMED |
| Token Exchange | `sdk-os.mpsdk.easebar.com` | 443 | HTTPS | `com.netease.mpay.oversea.h.a.a` | CONFIRMED |
| Patch Hash Check | `h45na.update.easebar.com` | 443 | HTTPS | Python `patch.patch_logic` | CONFIRMED |
| Patch Plist Manifest | `h45na.update.easebar.com` | 443 | HTTPS | Python `patch.patch_logic` | CONFIRMED |
| Total Filelist | `h45na.update.easebar.com` | 443 | HTTPS | Python `patch.patch_logic` | CONFIRMED |
| Server List Configuration | `h45na.update.easebar.com` | 443 | HTTPS | Python `ui.UILogin.requestServerList` | CONFIRMED |
| VIP Fallback Server List | `52.221.3.167` | 443 | HTTPS | Python `ui.UILogin.fetch_by_vips` | CONFIRMED |
| Geolocation IP Service | `who.nie.easebar.com` | 443 | HTTPS | Python `neox.whoami` | CONFIRMED |
| Startup Telemetry (DRPF)| `drpf-h45na.proxima.nie.easebar.com` | 443 | HTTPS | `com.netease.neox.Launcher.DRPF` | CONFIRMED |
| BigWorld LoginApp Gateway | Server List IP (e.g. `10.0.2.2`) | 25000 | Mercury UDP/TCP | `neox::bwclient::ServerConnection::logOnBegin` | CONFIRMED |
| BigWorld BaseApp | BaseApp IP (assigned by LoginApp) | Dynamic | Mercury UDP/TCP | `neox::bwclient::BaseAppLoginRequest` | CONFIRMED |
| BigWorld CellApp (World) | CellApp IP (assigned by BaseApp) | Dynamic | Mercury UDP/TCP | `neox::bwclient::ServerConnection::createCellPlayer` | CONFIRMED |

---

## 13. Important Classes

1. `com.netease.neox.Launcher` (`02_dex/classes.dex`): Pre-engine launcher activity controlling OBB verification, permission checks, delta patch progress dialogs, and engine handoff.
2. `com.netease.neox.Client` (`02_dex/classes.dex`): Extends `NativeActivity`; anchors the native NeoX C++ game engine.
3. `com.netease.neox.NativeInterface` (`02_dex/classes.dex`): Static JNI bridge loading `libclient.so` and declaring native callback interfaces.
4. `com.netease.neox.Channel` (`02_dex/classes.dex`): Java dispatch hub bridging UniSDK callbacks to `NativeInterface.NativeOnLogin`.
5. `com.netease.ntunisdk.SdkNeteaseGlobal` (`02_dex/classes.dex`): Primary UniSDK channel module for NetEase Overseas platform authentication.
6. `com.netease.ntunisdk.SdkNeteaseGlobal$LoginCallback` (`02_dex/classes.dex`): Inner callback class implementing `MpayLoginCallback`; parses `User` credentials and dispatches `loginDone(0)`.
7. `com.netease.mpay.oversea.MpayActivity` (`02_dex/classes.dex`): Transparent Activity rendering authentication dialogs, guest prompts, and LVU age verification.
8. `com.netease.mpay.oversea.ui.g` (`02_dex/classes.dex`): Dialog controller managing the `User Age Setting` UI and cancel code mappings.
9. `com.netease.mpay.oversea.j.d.d` (`02_dex/classes.dex`): Local session controller evaluating `isFirstLogin` and `has_minor` from SharedPreferences.
10. `com.netease.mpay.oversea.h.a.a` (`02_dex/classes.dex`): JSON deserializer extracting top-level `user_id` and `sdk_token` from token exchange payloads.

---

## 14. Important Methods

1. `com.netease.neox.Launcher.onCreate(Bundle)`: Main launcher entry point; validates storage and OBB archives.
2. `com.netease.neox.Launcher.startPatch()`: Pre-engine patch trigger checking network type and initiating background patch thread.
3. `com.netease.neox.Launcher.startGame()`: Instantiates `Intent(Launcher, Client.class)`, calls `startActivity()`, and terminates launcher.
4. `com.netease.neox.NativeInterface.NativeStartPatch(String)`: Native JNI invocation to execute C++ delta patcher in `libclient.so`.
5. `com.netease.neox.NativeInterface.NativeOnLogin(int)`: Native JNI callback delivering login success/failure to embedded Python engine.
6. `com.netease.neox.Channel.loginDone(int)`: Java channel listener forwarding UniSDK completion to `NativeInterface.NativeOnLogin`.
7. `com.netease.ntunisdk.SdkNeteaseGlobal.login()`: Initiates NetEase Overseas login flow via `MpayOverseaApi.login()`.
8. `com.netease.ntunisdk.SdkNeteaseGlobal$LoginCallback.onLoginSuccess(User)`: Deserializes authenticated `User` record, sets UID/Session properties, and calls `loginDone(0)`.
9. `com.netease.mpay.oversea.ui.g$2.onClick(View)`: Hardcoded cancel handler invoking `MpayLoginCallback.onFailure("Cancel login", 1000, minor_status)`.
10. `neox::bwclient::ServerConnection::logOnBegin(...)`: Native C++ method in `libclient.so` initiating Mercury Nub connection to `10.0.2.2:25000`.

---

## 15. Confirmed Findings

1. **[CONFIRMED] Multi-DEX Segregation**: NetEase authentication, launcher, and native bridge logic reside strictly in `02_dex/classes.dex`. `classes2.dex` and `classes3.dex` contain only third-party SDKs (Google, Facebook, Firebase, AppsFlyer) and wrapper dispatchers.
2. **[CONFIRMED] Pre-Engine vs. In-Engine Patching**: `Launcher.java` executes a pre-engine patch check using `NativeInterface.NativeStartPatch`. Once the engine starts, Python `ui.UIPatch` executes an in-engine resource verification against `patchVersion`, `/pl/h45na_hc`, and `/pl/npk_version_na_android.plist`.
3. **[CONFIRMED] Root Cause of LVU Loop**: The "User Age Setting" dialog appears because `j.d.d.c` initializes `has_minor = true` when local SharedPreferences lack saved session tokens. When dismissed, `ui.g$2.onClick` delivers hardcoded error code `1000` (`"Cancel login"`), causing UniSDK to fire `ntOnLogin(1)` and resetting the Title Screen.
4. **[CONFIRMED] MPay Age Bypass Branch**: In `com.netease.mpay.oversea.ui.g.a(g$e)` (bytecode `0x400826` and `0x400868`), if the server response contains `minor_status: 102` and `age_status: 0`, Dalvik bytecode skips dialog construction and branches directly to `0x40088c`, firing `onLoginSuccess` automatically.
5. **[CONFIRMED] JNI Authentication Handoff**: Successful authentication transitions from Java to native C++ via `Channel.loginDone(0)` -> `NativeInterface.NativeOnLogin(0)`. Native code forwards `ntOnLogin(0)` into Python `ui.UILogin.py`.
6. **[CONFIRMED] Gateway Destination**: Upon authentication, `ui.UILogin` fetches `server_list_ad.txt` and invokes `neox::bwclient::ServerConnection::logOnBegin` targeting `10.0.2.2:25000`.
7. **[CONFIRMED] BigWorld Architecture**: The client is built on BigWorld Technology Mercury networking. Server entities `Account.def.xml`, `LoginProxy.def.xml`, `Avatar.def.xml`, `BattleAccount.def.xml`, and `BattleGroundSpace.def.xml` strictly govern account sessions, lobby progression, and match spaces.

---

## 16. Inferred Findings

1. **[INFERRED] RSA Key Packaging for `loginapp.pubkey`**: In `libclient.so`, strings show `entities\loginapp.pubkey` is queried by `neox::bwclient::ServerConnection::logOnBegin`. Because `05_entities/out/` contains entity definitions extracted from `res/entities.npk`, `loginapp.pubkey` is likely packed inside `res/entities.npk` or compiled directly into `libclient.so`.
2. **[INFERRED] Matchmaking Queue Protocol**: `Avatar.cell.reqMatch(...)` dispatches over the Mercury Channel protocol to BaseApp. The BaseApp communicates with a cluster-wide BigWorld matchmaker process before allocating a `BattleGroundSpace`.
3. **[INFERRED] Title Screen Tap Detection**: The visual "PLAY" button on the Title Screen is rendered by CocosStudio binary scene assets loaded by NeoX CSLoader (`ui/out_game/ui_login/ui_login.csb` or equivalent).

---

## 17. Unknown / Missing Information

1. **Exact Mercury Logon Packet Framing**: The exact binary byte layout and opcode structure of the RSA-encrypted `LogOnParams` stream for this specific NetEase build (v1117219) cannot be fully reconstructed from DEX bytecode alone.
2. **LoginApp RSA Key Pair**: The 1024/2048-bit RSA private key matching `loginapp.pubkey` (necessary for an authoritative server to decrypt client credentials) is server-side property and must be generated or patched in a custom server emulator.
3. **`BaseAppLoginRequest` Challenge/Nonce**: The dynamic nonce exchange between `LoginHandler::onLoginReply` and `BaseAppLoginRequest` requires live packet capture on port 25000.

---

## 18. Recommended Next Investigation

1. **Target Component**: BigWorld Mercury Network Protocol on Port 25000 (Gate 2).
2. **Required Analysis Type**:
   - **Native `.so` Analysis**: Disassemble `neox::bwclient::ServerConnection::logOnBegin` and `neox::bwclient::LogOnParams::addToStream` in `03_lib/libclient_arm64.so` to extract the Mercury bundle header format, opcode IDs, and encryption scheme.
   - **Network Protocol Analysis**: Run client against host port 25000 listener (`serve_loginapp_tcp` / `serve_loginapp_udp` in `mitm/mitm_serve.py`) to capture the live binary logon bundle.
   - **Key Extraction**: Extract `entities/loginapp.pubkey` from `05_entities/entities.npk` or identify its hardcoded fallback in `libclient.so`.
