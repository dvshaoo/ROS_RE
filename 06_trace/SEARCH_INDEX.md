# ROS v1117219 Search Index

This index lists the core classes, methods, and symbols discovered across `02_dex/classes.dex`, `classes2.dex`, `classes3.dex`, native libraries, and BigWorld entity definitions for Rules of Survival build `v1117219`.

---

## 1. Android Java & Smali Classes

| Component / Layer | Fully Qualified Class Name | DEX / Location | Key Methods | Functional Responsibility |
|---|---|---|---|---|
| **App Startup** | `com.netease.ntunisdk.application.NtSdkApplication` | `classes.dex` | `onCreate()` | Main application class initialized by OS |
| **App Launcher** | `com.netease.neox.Launcher` | `classes.dex` (`0x3be000`) | `onCreate`, `startPatch`, `patching`, `preparePatch`, `startGame`, `runGame`, `DRPF`, `OBB_DRPF` | Checks storage/OBBs, displays update dialogs, triggers patch engine, launches `Client` |
| **Native Activity** | `com.netease.neox.Client` | `classes.dex` | `onCreate`, `onResume`, `isNotchScreen`, `isRunningOnEmulator` | Extends `NativeActivity`; entry point for native NeoX engine |
| **JNI Bridge** | `com.netease.neox.NativeInterface` | `classes.dex` (`NativeInterface.smali`) | `NativeStartPatch`, `NativePatchGetPatchStatus`, `NativePatchGetTotalSize`, `NativeOnLogin`, `NativeOnLogout` | Static JNI methods exported by `libclient.so` |
| **Channel Dispatcher** | `com.netease.neox.Channel` | `classes.dex` (`Channel.smali`) | `login`, `loginDone`, `logout`, `hasLogin` | Bridges UniSDK login callbacks into `NativeInterface.NativeOnLogin` |
| **UniSDK Manager** | `com.netease.ntunisdk.base.SdkMgr` | `classes.dex` / `classes3.dex` | `getInst()`, `loadLibrary()` | Singleton registry for channel SDK implementations |
| **UniSDK Base** | `com.netease.ntunisdk.base.SdkBase` | `classes.dex` (`SdkBase.smali`) | `ntLogin`, `loginDone`, `setLoginUid`, `setLoginSession` | Core UniSDK abstraction interface (`GamerInterface`) |
| **Overseas Channel** | `com.netease.ntunisdk.SdkNeteaseGlobal` | `classes.dex` (`SdkNeteaseGlobal.smali`) | `login`, `logout`, `getLoginSession`, `getLoginUid` | Concrete channel plugin for global NetEase overseas auth |
| **Login Callback** | `com.netease.ntunisdk.SdkNeteaseGlobal$LoginCallback` | `classes.dex` (`LoginCallback.smali:209`) | `onLoginSuccess`, `onFailure`, `onDialogFinish` | Implements `MpayLoginCallback`; parses `User` object and dispatches `loginDone(0)` |
| **MPay Public API** | `com.netease.mpay.oversea.MpayOverseaApi` | `classes.dex` | `login`, `channelLogin`, `shouldAutoLogin`, `migrateCodeLogin` | Public API facade exposed by NetEase MPay SDK |
| **MPay Activity** | `com.netease.mpay.oversea.MpayActivity` | `classes.dex` (`0x3beae0`) | `onCreate`, `close`, `onBackPressed` | Transparent Activity hosting login UI, guest prompt, and LVU age dialogs |
| **Guest Auth Deserializer**| `com.netease.mpay.oversea.d.a.a.e` | `classes.dex` (`0x3c8f8c`) | `a(JSONObject)` | Parses `POST /api/users/login/guest` response |
| **LVU Dialog Controller** | `com.netease.mpay.oversea.ui.g` | `classes.dex` (`0x4007d8`) | `a(g$e)`, `a(int)` | Controls `User Age Setting` dialog display; maps cancel to code `1000` |
| **Age Dialog Cancel Handler**| `com.netease.mpay.oversea.ui.g$2` | `classes.dex` (`0x3ffbb4`) | `onClick(View)` | Hardcodes `const/16 v4, 1000` passed to `onFailure(1000)` |
| **LVU State Machine** | `com.netease.mpay.oversea.e.b.c` | `classes.dex` (`0x3cc968`) | `a(State)` | State machine handling states 1-5 (query, birthday, consent, email) |
| **Minor Status Evaluator** | `com.netease.mpay.oversea.e.b.d` | `classes.dex` (`0x3ccee0`) | `a(minor_status)` | Packed switch evaluating minor status codes 0-3 vs success (`0x3ccf9c`) |
| **Local Session Manager** | `com.netease.mpay.oversea.j.d.d` | `classes.dex` (`0x3e0554`) | `c()` | Checks `isFirstLogin` and `has_minor` from SharedPreferences |
| **Session Serializer** | `com.netease.mpay.oversea.j.a.h` | `classes.dex` (`0x3dab5c`) | `a()`, `c()` | Serializes/deserializes HashMap keys: '1'=firstLogin, '3'=token, '4'=has_minor |
| **Token Deserializer** | `com.netease.mpay.oversea.h.a.a` | `classes.dex` (`0x3d34bc`) | `a(JSONObject)` | Parses top-level `user_id`, `sdk_token` from `login/v2/sdk_token` |
| **Token Callback** | `com.netease.mpay.oversea.h.c.c$7` | `classes.dex` (`0x3d4ce8`) | `a()` | Forwards parsed token to `TransmissionData$LoginData` -> `onLoginSuccess` |

---

## 2. Native Engine Symbols (`libclient.so`)

| Symbol / Namespace | Component | Purpose |
|---|---|---|
| `neox::bwclient::ServerConnection::logOnBegin` | BigWorld Client Network | Initiates Mercury Nub connection to `10.0.2.2:25000` for loginapp |
| `neox::bwclient::ServerConnection::logOn` | BigWorld Client Network | Manages server logon state machine |
| `neox::bwclient::LogOnParams::addToStream` | BigWorld Authentication | Encrypts logon credentials with RSA public key (`entities/loginapp.pubkey`) |
| `neox::bwclient::LoginHandler::onLoginReply` | BigWorld Authentication | Receives BaseApp redirection address and session key from loginapp |
| `neox::bwclient::BaseAppLoginRequest` | BigWorld BaseApp | Connects to assigned BaseApp for entity instantiation |
| `neox::bwclient::ServerConnection::createBasePlayer` | BigWorld Entity Engine | Creates base player entity upon BaseApp connection |
| `neox::bwclient::ServerConnection::createCellPlayer` | BigWorld Entity Engine | Creates cell player entity upon entering world space |
| `neox::bwclient::ServerConnection::addMove` | BigWorld Spatial Engine | Dispatches local player coordinate updates to server |
| `Java_com_netease_neox_NativeInterface_NativeOnLogin` | JNI Native Bridge | Receives UniSDK login status and forwards to embedded Python runtime |
| `Java_com_netease_neox_NativeInterface_NativeStartPatch` | JNI Native Bridge | Executes native resource patch sync |
| `Java_com_netease_neox_NativeInterface_NativePatchGetPatchStatus` | JNI Native Bridge | Returns native patcher status code (0 = success) |

---

## 3. BigWorld Entity Definitions (`05_entities/out/`)

| Entity Definition | Client / Base / Cell Interface | Key Properties & Methods | Gameplay Role |
|---|---|---|---|
| `Account.def.xml` | ClientName: `Account` (Base) | Base: `handshake`, `uploadABSwitchesConfig`<br>Client: `onLogin`, `onChannelLogin`, `loadSceneAfterReconnect` | Master user account entity; handles channel authentication & initial login |
| `LoginProxy.def.xml` | ClientName: `LoginProxy` (Base) | Base: `handshake`, `bindUrs`<br>Client: `onChannelLogin` | Authentication proxy between LoginApp and BaseApp |
| `Avatar.def.xml` | ClientName: `Avatar` (Base + Cell) | Interfaces: `iRosMatchAvatar`, `iPackage3`, `iNormalCombatUnit`, `iCell`<br>Properties: `baseNickname`, `gid` | Player character entity in Lobby and Game Session |
| `BattleAccount.def.xml` | ClientName: `BattleAccount` (Base) | Base: `handshake`, `onNextProxyDestroy`<br>Properties: `avatarProperties`, `athleteMailBox` | Bridge entity connecting account to a specific match |
| `Athlete.def.xml` | ClientName: `Athlete` (Cell) | Interfaces: `iNormalCombatUnit`, `iLandDrive`, `iSwim`, `iDropItem` | In-match physical avatar representation on the battlefield |
| `BattleGroundSpace.def.xml` | Parent: `DynamicSpace` (Cell) | Interfaces: `iRosMatchSpace`, `iMatchSingleSideSpace`, `iRobotGenerate`<br>Properties: `startTime`, `gameStatus` | 100-player Battle Royale world space (Desert / Fearless Fiord) |

---

## 4. Game Engine Python Scripts (`script.npk`)

| Script / Module | Path in VFS | Key Functions | Functional Role |
|---|---|---|---|
| `ui.UILogin` | `ui/UILogin.py` | `_on_click_login`, `ntOnLogin`, `requestServerList`, `doLoginGame` | Title Screen UI, "PLAY" button handler, server list parser |
| `ui.UIPatch` | `ui/UIPatch.py` | `checkVersion`, `onPatchFinish`, `updateProgress` | Patch Screen UI, download progress bar, CSB loader (`ui_patch.csb`) |
| `patch.patch_logic` | `patch/patch_logic.py` | `check_update`, `fetch_by_vips`, `http_get` | HTTP client querying `server_list_ad.txt` and `npk_version_na_android.plist` |
| `ui.UIHall` | `ui/UIHall.py` | `init_hall`, `on_click_match`, `update_avatar` | Main Lobby controller; game mode selector and matchmaking trigger |
