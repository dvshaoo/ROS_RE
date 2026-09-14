# ROS v1117219 Call Flow Trace

This document details the confirmed call flow across Android Java (Dalvik/ART), JNI Native Bridge (`libclient.so`), NeoX Game Engine, UniSDK, NetEase MPay Authentication, and BigWorld Mercury Network Engine for Rules of Survival build `v1117219` (`com.netease.chiji`).

---

## 1. High-Level Lifecycle Chain

```
[OS Launch]
   │
   ▼
com.netease.neox.Launcher.onCreate()
   │
   ▼
com.netease.neox.Launcher.startPatch()
   │
   ▼
com.netease.neox.NativeInterface.NativeStartPatch()  [libclient.so]
   │
   ▼
com.netease.neox.Launcher.startGame()
   │
   ▼
com.netease.neox.Client.onCreate()  [android.app.NativeActivity -> libh45na.so / libclient.so]
   │
   ▼
[NeoX Engine & Embedded Python Runtime Initialized]
   │
   ▼
Python: ui.UIPatch / patch.patch_logic (Resource Verification & Patch Sync)
   │
   ▼
Python: ui.UILogin (Title Screen Rendered)
   │
   ▼
User Taps "PLAY" / "Log in as Guest" (ui.UILogin._on_click_login)
   │
   ▼
Channel.login() -> SdkMgr.getInst().ntLogin()
   │
   ▼
SdkNeteaseGlobal.login() [UniSDK netease_global]
   │
   ▼
MpayOverseaApi.login() -> MpayActivity.onCreate()
   │
   ▼
HTTP POST /api/users/login/guest (d.a.a.e.a)
   │
   ▼
HTTP POST /api/users/login/v2/sdk_token (h.a.a.a)
   │
   ▼
MpayLoginCallback.onLoginSuccess() -> SdkNeteaseGlobal$LoginCallback.onLoginSuccess()
   │
   ▼
SdkNeteaseGlobal.loginDone(0) -> Channel.loginDone(0)
   │
   ▼
NativeInterface.NativeOnLogin(0)  [JNI Boundary -> libclient.so]
   │
   ▼
Python: ui.UILogin.ntOnLogin(0) -> channelLogin = True
   │
   ▼
Python: ui.UILogin.requestServerList() -> HTTP GET /server_list_ad.txt
   │
   ▼
Python: ui.UILogin.doLoginGame()
   │
   ▼
neox::bwclient::ServerConnection::logOnBegin("10.0.2.2", 25000)  [libclient.so]
   │
   ▼
[Mercury Nub Socket Handshake -> Port 25000 (loginapp)]
   │
   ▼
neox::bwclient::LoginHandler::onLoginReply() (BaseApp Address Assigned)
   │
   ▼
neox::bwclient::BaseAppLoginRequest (BaseApp Handshake)
   │
   ▼
BaseApp Entity Instantiation: Account.def.xml (Account.handshake -> Account.onLogin)
   │
   ▼
Lobby / Hall Initialization (Avatar.def.xml Instantiated)
   │
   ▼
User Clicks Match / Play in Lobby (Avatar.cell.reqMatch / iRosMatchAvatar)
   │
   ▼
BigWorld Cell Space Created: BattleGroundSpace.def.xml
   │
   ▼
Battle Entity Assigned: BattleAccount.def.xml / Athlete.def.xml
   │
   ▼
Match In-Game Session (Skydiving, Island Combat, NeoX 3D World Rendering)
```

---

## 2. Detailed Component Call Sequences

### 2.1 Stage 1: Android Application Launch & Launcher Setup
1. **OS Intent**: `android.intent.action.MAIN`, category `android.intent.category.LAUNCHER`.
2. **Application Startup**: `com.netease.ntunisdk.application.NtSdkApplication.onCreate()`.
3. **Activity Entry**: `com.netease.neox.Launcher.onCreate(Bundle savedInstanceState)`.
4. **Storage & OBB Evaluation**:
   - `Launcher._determineStorage()` checks write permissions and external storage availability.
   - `Launcher.initStorageStatus()` resolves `main.1117219.com.netease.chiji.obb` and `patch.1117219.com.netease.chiji.obb`.
   - `Launcher._calcAssetToCopyFromApk()` / `Launcher.calcAssetToCopy()` scans `filelist_obb.txt`.
5. **Telemetry Dispatch**:
   - `Launcher.OBB_DRPF(int)` / `Launcher.DRPF(String)` posts startup diagnostics to `https://drpf-h45na.proxima.nie.easebar.com`.

### 2.2 Stage 2: Pre-Engine Patch Verification
1. **Patch Trigger**: `Launcher.preparePatch()` -> `Launcher.startPatch()`.
2. **Network Evaluation**: `Launcher.getNetworkType()` determines Wi-Fi vs. Cellular. If cellular and updates exist, triggers `neox_launcher_not_wifi` AlertDialog.
3. **Execution Thread**: `Launcher.patching()` opens `ProgressDialog` (`neox_launcher_updating`) and starts `Launcher$PatchFile` runnable thread.
4. **JNI Transition**:
   - `Launcher$PatchFile.run()` calls `com.netease.neox.NativeInterface.NativeStartPatch(String configPath)`.
   - Engine executes native patch routines (`libclient.so`).
   - Poll status: `NativeInterface.NativePatchGetPatchStatus()`.
5. **Completion Transition**:
   - `Launcher$PatchFile$1.run()` handles completion on UI thread.
   - If `status == 0` (SUCCESS), invokes `Launcher.startGame()`.
   - `Launcher.startGame()` instantiates `Intent(Launcher, com.netease.neox.Client.class)`, sets flag `0x10000000` (`FLAG_ACTIVITY_NEW_TASK`), calls `startActivity(Intent)`, and finishes `Launcher`.

### 2.3 Stage 3: Native Game Engine & Python Boot
1. **Activity Launch**: `com.netease.neox.Client` (`android.app.NativeActivity`).
2. **Native Loading**: OS loads native library specified in metadata:
   - `<meta-data android:name="android.app.lib_name" android:value="h45na"/>` -> `libclient.so`.
   - `com.netease.neox.NativeInterface.<clinit>` explicitly loads:
     - `System.loadLibrary("c++_shared")`
     - `FmodLoader.Load()` (`libfmodex.so`, `libfmodevent.so`)
     - `System.loadLibrary("client")` (`libclient.so`).
3. **NeoX VFS Mounting**:
   - Native engine mounts APK assets and OBB archives (`main.1117219.com.netease.chiji.obb` and `patch.1117219.com.netease.chiji.obb`).
   - Mounts persistent user storage at `/sdcard/Android/data/com.netease.chiji/files/netease/h45na/`.
4. **Python Engine Execution**:
   - `libclient.so` initializes embedded Python 2.7 runtime.
   - Mounts `res/script.npk` and executes `main.py` / `game.py`.
   - Engine loads `ui.UIPatch` to check remote patch versions (`/pl/h45na_hc` and `/pl/npk_version_na_android.plist`).
   - When verified, `ui.UIPatch` closes and instantiates `ui.UILogin` (Title Screen).

### 2.4 Stage 4: Title Screen & Authentication Invocation
1. **Title Screen Display**: `ui.UILogin` renders background video/art, version string, server button, and central "PLAY" button.
2. **User Tap Play**: `ui.UILogin._on_click_login()` is triggered.
3. **Session Check**:
   - Python checks if user is currently authenticated (`self.is_login` / `channelLogin`).
   - If not authenticated, invokes UniSDK `ntLogin()` via native channel bridge:
     `Channel.login("")` -> `SdkMgr.getInst().ntLogin()`.
4. **UniSDK Dispatch**:
   - `com.netease.ntunisdk.SdkNeteaseGlobal.login()` is invoked.
   - Evaluates `LOGIN_TYPE` property:
     - Case 0: Calls `mSdkInstance.login(mLoginCallback)`.
     - `mSdkInstance` (`Lcom/netease/mpay/oversea/MpayOverseaApi;`) starts `com.netease.mpay.oversea.MpayActivity`.

### 2.5 Stage 5: NetEase MPay Authentication & Session Creation
1. **Device Initialization**:
   - `MpayActivity` requests `POST /api/devices/init` to obtain device identifier.
   - Requests `POST /api/games/config` for authentication provider list and age policies.
2. **Guest Login Execution**:
   - Invokes `POST /api/users/login/guest`.
   - Response deserialized by `com.netease.mpay.oversea.d.a.a.e.a()` at bytecode `0x3c8f8c`:
     - Parses `user.id`, `user.account`, `user.token`, `minor_status`, `age_status`.
3. **LVU / Minor Age Verification**:
   - If `has_minor == true` (local storage unpopulated or `minor_status != 102`):
     - `com.netease.mpay.oversea.ui.g.a()` pops up `User Age Setting` dialog (`lvu_person_info`).
     - State machine `com.netease.mpay.oversea.e.b.c.a()` transitions through `/api/minors/query` and `/api/minors/update_birthday`.
4. **Token Refresh & Session Finalization**:
   - Client requests `POST /api/users/login/v2/sdk_token`.
   - Response parsed by `com.netease.mpay.oversea.h.a.a.a()` at bytecode `0x3d34bc`:
     - Expects top-level `"user_id"` and `"sdk_token"`.
   - Invokes `MpayLoginCallback.onLoginSuccess(User user)`.
5. **UniSDK Callback Dispatch**:
   - `SdkNeteaseGlobal$LoginCallback.onLoginSuccess(User user)` records session credentials:
     - `SdkNeteaseGlobal.setLoginUid(user.uid)`
     - `SdkNeteaseGlobal.setLoginSession(user.token)`.
   - Calls `SdkNeteaseGlobal.loginDone(0)`.
   - `SdkBase.loginDone(0)` notifies `OnLoginDoneListener.loginDone(0)`.
   - `Channel.loginDone(0)` invokes `NativeInterface.NativeOnLogin(0)`.

### 2.6 Stage 6: Title Screen Handshake to Gateway (loginapp)
1. **JNI Transition**:
   - `NativeInterface.NativeOnLogin(0)` enters `libclient.so`.
   - Native code forwards event to Python runtime: `ui.UILogin.ntOnLogin(unisdk_code=0)`.
2. **Server List Query**:
   - Python client sets `channelLogin = True`.
   - Client calls `fetch_by_vips` / `http_get` targeting `https://h45na.update.easebar.com/server_list_ad.txt`.
   - Deserializes space-delimited server record:
     `North_America 1 1 1 North_America North_America 10.0.2.2:25000 10.0.2.2:25000 10.0.2.2:25000 10001 10.0.2.2:25000`.
3. **Game Login Trigger**:
   - User taps PLAY on title screen or auto-connect fires: `ui.UILogin.doLoginGame()`.
   - Python calls native BigWorld client: `neox.bwclient.ServerConnection.logOnBegin()`.

### 2.7 Stage 7: BigWorld Mercury Handshake (Port 25000)
1. **Mercury Socket Initialization**:
   - `neox::bwclient::ServerConnection::logOnBegin("10.0.2.2", 25000)` creates Mercury Nub socket (`Mercury::Nub`).
2. **Credential Encryption**:
   - Loads public key from asset `entities/loginapp.pubkey`.
   - Calls `neox::bwclient::LogOnParams::addToStream()` using RSA public encryption.
3. **LoginApp Packet Transmission**:
   - Sends Mercury logon bundle to `10.0.2.2:25000`.
4. **LoginApp Reply Processing**:
   - `neox::bwclient::LoginHandler::onLoginReply()` parses server response.
   - Updates target BaseApp address: `change baseAddr from %s to %s`.
5. **BaseApp Login & Entity Attachment**:
   - Client creates `BaseAppLoginRequest` targeting assigned BaseApp address.
   - BaseApp creates server-side `Account` entity (`05_entities/out/Account.def.xml`).
   - Client executes `Account.handshake(STRING hotfix_md5, DEVICE_INFO, CHANNEL_INFO, CLIENT_ENGINE_INFO, STRING sauth_reply)`.
   - Server returns `Account.onLogin(int result, string msg)` and `Account.onChannelLogin(uint8 code, python data)`.

### 2.8 Stage 8: Lobby / Hall Progression & Matchmaking
1. **Lobby Scene Load**:
   - Client destroys Title UI (`ui.UILogin`) and transitions to Lobby controller (`ui.UIHall`).
   - Player character entity `Avatar` (`05_entities/out/Avatar.def.xml`) is instantiated in BigWorld client space.
   - Base properties synchronized: `baseNickname`, appearances, inventory (`iPackage3`), currencies, and event states.
2. **Matchmaking Request**:
   - User clicks Lobby "START" / "MATCH" button.
   - Lobby UI invokes matchmaking method on `Avatar`:
     - Method: `Avatar.cell.reqMatch(...)` / `iRosMatchAvatar`.
   - Passes parameters: game mode (Solo, Duo, Squad, Fireteam), perspective (TPP, FPP), map ID.
3. **Matchmaking Space Creation**:
   - Server matchmaking daemon groups 100+ players.
   - Allocates BigWorld cell space: `BattleGroundSpace.def.xml`.
   - Instantiates `BattleAccount.def.xml` and combat unit `Athlete.def.xml` (`iNormalCombatUnit`) for each connected player.
4. **Game Session Entry**:
   - BaseApp sends `loadSceneAfterReconnect(int mapID)` and `createCellPlayer` to client.
   - Client loads 3D terrain, vegetation, buildings from OBB packages (`scene.npk`, `model.npk`, `textures.npk`).
   - Game session starts: pre-match lobby island -> aircraft drop -> full battle royale loop.
