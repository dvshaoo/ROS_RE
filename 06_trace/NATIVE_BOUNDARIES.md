# ROS v1117219 Native Boundaries & JNI Bridge

This document details all Java ↔ Native boundaries discovered across the DEX bytecode (`classes.dex`, `classes2.dex`, `classes3.dex`), their corresponding native libraries, and the exact handoff points between Android Java, native C++ (`libclient.so`), and the embedded NeoX Python runtime.

---

## 1. Native Shared Libraries Discovered

The APK contains 17 native ELF libraries located in `lib/armeabi-v7a/` and `lib/arm64-v8a/`:

| Library Name | File Size (v7a / arm64) | Primary Purpose | Loading Mechanism | Evidence |
|---|---|---|---|---|
| `libclient.so` | 57.2 MB / 72.7 MB | Core NeoX Game Engine, BigWorld Mercury Client, Embedded Python Runtime | `NativeInterface.<clinit>`, `NativeLibararyLoader`, `NativeActivity` | `classes.dex`: `NativeInterface.java`, `Client.java` |
| `libc++_shared.so` | 657 KB / 920 KB | LLVM libc++ runtime dependency | `NativeInterface.<clinit>` | `classes.dex`: `NativeInterface.smali:13` |
| `libfmodex.so` | 1.1 MB / 1.5 MB | FMOD Sound System Engine | `FmodLoader.Load()` | `classes.dex`: `FmodLoader.smali:16` |
| `libfmodevent.so` | 392 KB / 520 KB | FMOD Event System | `FmodLoader.Load()` | `classes.dex`: `FmodLoader.smali:16` |
| `libntunisdk.so` | 13.9 KB / 18.2 KB | UniSDK JNI bridge wrapper | System.loadLibrary | `classes.dex`: `SdkMgr.smali` |
| `libunisdkdctool.so` | 1.7 MB / 2.3 MB | Diagnostics and telemetry collection | System.loadLibrary | `classes.dex`: `unisdkdctool.smali:20` |
| `libstreammgr.so` | 3.7 MB / 5.1 MB | Screen recording and live streaming | System.loadLibrary | `classes.dex`: `StreamMgr.smali:33` |
| `libAudioEngine.so` | 1.5 MB / 2.1 MB | NetEase CC Voice engine core | System.loadLibrary | `classes.dex`: `CCVoiceEngine.smali:34` |
| `libAudioEngineJni.so` | 9.3 KB / 14.1 KB | JNI bridge for NetEase CC Voice | System.loadLibrary | `classes.dex`: `CCVoiceEngine.smali:35` |
| `libAudioCore.so` | 1.6 MB / 2.2 MB | WebRTC audio processing & codecs | System.loadLibrary | `classes.dex`: `CCVoiceEngine.smali:36` |
| `libAudioCCReName.so` | 1.0 MB / 1.4 MB | Audio symbol namespace wrapper | System.loadLibrary | `classes.dex`: `CCVoiceEngine.smali:37` |
| `libijkplayer.so` | 293 KB / 410 KB | Bilibili IJK media player core | System.loadLibrary | `classes.dex`: `IjkMediaPlayer.smali:28` |
| `libijkffmpeg.so` | 5.8 MB / 8.2 MB | FFmpeg media demuxer & decoders | System.loadLibrary | `classes.dex`: `IjkMediaPlayer.smali` |
| `libijksdl.so` | 202 KB / 285 KB | SDL video/audio output for IJK | System.loadLibrary | `classes.dex`: `IjkMediaPlayer.smali` |
| `libijkutil.so` | 9.3 KB / 14.2 KB | Utility functions for IJK | System.loadLibrary | `classes.dex`: `IjkMediaPlayer.smali` |
| `libcom_netease_androidcrashhandler_AndroidCrashHandler.so` | 362 KB / 510 KB | Native signal catcher & crash reporter | System.loadLibrary | `classes.dex`: `AndroidCrashHandler.smali:5` |
| `libcom_netease_ps_codescanner.so` | 9.5 KB / 14.5 KB | Camera frame NV21 to RGB scanner | System.loadLibrary | `classes.dex`: `Graphics.smali:6` |

---

## 2. Core NeoX JNI Bridge: `Lcom/netease/neox/NativeInterface;`

All native methods in `NativeInterface` are exported directly by `libclient.so`.

| Native Method | Return Type | Parameters | Target Library | Functional Purpose | Handoff Boundary |
|---|---|---|---|---|---|
| `NativeStartPatch` | `void` | `(String configPath)` | `libclient.so` | Triggers native filelist check and patch download engine | **NATIVE BOUNDARY — requires .so analysis** |
| `NativePreparePatch` | `void` | `(String path)` | `libclient.so` | Prepares VFS directories for patching | **NATIVE BOUNDARY — requires .so analysis** |
| `NativePatchGetPatchStatus` | `int` | `()` | `libclient.so` | Returns 0 for success, negative for failure | **NATIVE BOUNDARY — requires .so analysis** |
| `NativePatchGetTotalSize` | `int` | `()` | `libclient.so` | Returns total patch download size in bytes | **NATIVE BOUNDARY — requires .so analysis** |
| `NativePatchGetDownloadedSize` | `int` | `()` | `libclient.so` | Returns currently downloaded bytes | **NATIVE BOUNDARY — requires .so analysis** |
| `NativeOnLogin` | `void` | `(int code)` | `libclient.so` | Delivers UniSDK login status to game engine Python | **NATIVE BOUNDARY — forwards to Python `UILogin.ntOnLogin`** |
| `NativeOnLogout` | `void` | `(int code)` | `libclient.so` | Delivers logout notification to game engine | **NATIVE BOUNDARY — forwards to Python runtime** |
| `NativeResumeMainInit` | `void` | `()` | `libclient.so` | Resumes main engine startup loop | **NATIVE BOUNDARY — requires .so analysis** |
| `NativeNotifyWelcomeViewFinished` | `void` | `()` | `libclient.so` | Notifies splash video/image playback complete | **NATIVE BOUNDARY — requires .so analysis** |
| `NativeOnExtendFuncCall` | `void` | `(String json)` | `libclient.so` | Generic UniSDK JSON RPC callback | **NATIVE BOUNDARY — forwards to Python runtime** |
| `NativeOnNetworkChanged` | `void` | `(int status, int type)` | `libclient.so` | Network connectivity change listener | **NATIVE BOUNDARY — requires .so analysis** |
| `NativeOnVirtualKeyboardShown` | `void` | `(int height)` | `libclient.so` | Notifies IME virtual keyboard appearance | **NATIVE BOUNDARY — requires .so analysis** |
| `NativeOnVirtualKeyboardHidden` | `void` | `()` | `libclient.so` | Notifies IME virtual keyboard dismissal | **NATIVE BOUNDARY — requires .so analysis** |
| `NativeOnChar` | `void` | `(int unicodeChar)` | `libclient.so` | Forwards keyboard input characters to NeoX UI | **NATIVE BOUNDARY — requires .so analysis** |
| `NativeOnInputFinish` | `void` | `(String text)` | `libclient.so` | Commits completed input field string | **NATIVE BOUNDARY — requires .so analysis** |
| `NativeOnLocationUpdated` | `void` | `(double lat, double lng, double alt)` | `libclient.so` | GPS location telemetry | **NATIVE BOUNDARY — requires .so analysis** |
| `NativeOnCrash` | `String[]` | `()` | `libclient.so` | Retrieves native backtrace upon crash | **NATIVE BOUNDARY — requires .so analysis** |

---

## 3. Java ↔ Native Handoff Points by Flow Stage

### 3.1 Startup & Native Activity Transition
- **Java Caller**: `com.netease.neox.Launcher.startGame()` (smali line 5064).
- **Handoff**: Starts `com.netease.neox.Client` (`android.app.NativeActivity`).
- **Native Implementation**:
  - Android OS invokes native entry point `ANativeActivity_onCreate` inside `libclient.so`.
  - Native engine sets up OpenGL ES surface, event loop, and asset manager.
  - Initialized state transfers control to the embedded Python engine (`script.npk`).
- **Boundary Classification**: **NATIVE BOUNDARY — requires .so analysis**.

### 3.2 Pre-Engine Patch Sync Handoff
- **Java Caller**: `com.netease.neox.Launcher$PatchFile.run()` (smali line 59).
- **Handoff**: Invokes `NativeInterface.NativeStartPatch(String)`.
- **Native Implementation**:
  - `libclient.so` executes native downloader / delta patcher.
  - Queries `NativePatchGetPatchStatus()`.
  - Returns code `0` (Success) back to Java thread.
- **Boundary Classification**: **NATIVE BOUNDARY — requires .so analysis**.

### 3.3 Authentication Result Handoff
- **Java Caller**: `com.netease.neox.Channel.loginDone(int)` (smali line 2073).
- **Handoff**: Invokes `NativeInterface.NativeOnLogin(code)`.
- **Native Implementation**:
  - In `libclient.so`, `NativeOnLogin` maps to C++ function `Java_com_netease_neox_NativeInterface_NativeOnLogin(JNIEnv*, jclass, jint)`.
  - C++ wrapper forwards the code to the Python game script by invoking `neox.Client.ntOnLogin(code)`.
  - Python `ui.UILogin.ntOnLogin(unisdk_code=0)` catches the event, sets `channelLogin = True`, and proceeds to server list fetching.
- **Boundary Classification**: **NATIVE BOUNDARY — forwards to Python `UILogin.ntOnLogin`**.

### 3.4 Title Screen "PLAY" Button → Game Session Handoff
- **Python Caller**: `ui.UILogin.doLoginGame()` (invoked when PLAY is clicked).
- **Handoff**: Python calls native method on `neox.bwclient.ServerConnection`:
  `neox.bwclient.ServerConnection.logOnBegin(host, port, username, password)`.
- **Native Implementation**:
  - Symbol: `neox::bwclient::ServerConnection::logOnBegin(char const*, char const*, char const*, char const*, unsigned short)` in `libclient.so`.
  - Opens BigWorld Mercury Nub socket directed to `10.0.2.2:25000`.
  - Loads RSA key `entities/loginapp.pubkey`.
  - Encrypts logon bundle (`LogOnParams::addToStream`).
  - Processes `LoginHandler::onLoginReply`.
  - Connects to BaseApp for entity instantiation (`Account.def.xml`).
- **Boundary Classification**: **NATIVE BOUNDARY — requires .so analysis & port 25000 Mercury protocol handling**.

### 3.5 Lobby / Hall → Matchmaking Handoff
- **Python Caller**: `ui.UIHall` (Lobby UI).
- **Handoff**: Calls exposed entity method on `Avatar`:
  `Avatar.cell.reqMatch(mode, map_id, ...)` via `iRosMatchAvatar`.
- **Native Implementation**:
  - `libclient.so` serializes method call into BigWorld Mercury entity packet stream.
  - Dispatches over network to BaseApp/CellApp.
  - Server assigns player to `BattleGroundSpace.def.xml` and allocates `BattleAccount.def.xml` / `Athlete.def.xml`.
  - Client receives `createCellPlayer` and `loadSceneAfterReconnect`.
- **Boundary Classification**: **NATIVE BOUNDARY — requires .so analysis & BigWorld CellApp entity protocol handling**.
