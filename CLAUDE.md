# CLAUDE.md — Rules of Survival (ROS) Mobile RE & Private Server Guide

> **Project**: Rules of Survival Mobile Private Server Emulation (Game Preservation)  
> **Client**: Android APK `com.netease.chiji`, v1.610377.506841, vCode 1117219, arm64-v8a  
> **Target Environment**: LDPlayer 9 (`emulator-5554`, Android guest `172.16.1.15`, Gateway host `172.16.1.2`)  
> **ADB Path**: `C:\LDPlayer\LDPlayer9\adb.exe`  
> **Primary Script**: `mitm/local_baseapp_capture.py`  
> **Last Updated**: 2026-09-18 (Checkpoint 15: Gate 4 Wire Encoding Solved, Ground Truth Lobby Entry Implemented)

---

## 1. Standing Rules (Strict Constraints)
- **Local/LAN Only**: Never interact with real production NetEase servers.
- **Zero Guesswork**: Every packet format, entity type, and method index must be verified by live memory inspection or Ghidra decompilation.
- **Commit Frequently**: Always make atomic git commits with clear descriptive messages.
- **Mobile Only**: Do not confuse with PC client structures — use `com.netease.chiji` Android constants.

---

## 2. Gate Milestones Status

| Gate | Component | Protocol | Status | Resolution |
|:---|:---|:---|:---:|:---|
| **Gate 0** | Patch / CDN Server | HTTP :80/:443 | **PASS** | `mitm_serve.py` / `local_baseapp_capture.py` bypasses patch checks. |
| **Gate 1** | UniSDK / Auth / Sigma | HTTP :80/:443/:8443 | **PASS** | Guest auth token and Sigma keypoints handled cleanly. |
| **Gate 2** | LoginApp Handshake | Mercury UDP :25000 | **PASS** | 4-byte LE ReplyID correlation @ wire offset 5. Blowfish encrypted `LoginReplyRecord` redirecting to BaseApp :25010. |
| **Gate 3** | BaseApp Handshake | Mercury UDP :25010 | **PASS** | `createBasePlayer(Account, type=38, eid=1)` accepted; client packet #0 decrypted; 864-byte `Account.handshake` ACKed; `Account.onChannelLogin(19)` + `Account.onLogin(18)` sent. Client reported `accountOnBecomePlayer`, `onChannelLogin(code=0)`, and `Login Succ`. |
| **Gate 4** | Character Select / Lobby | Mercury RPC / DEF | **IMPLEMENTED** | **Reversed BigWorld Mercury wire formula from `libclient.so:0xad03b0`.** Official server ground truth sequence (`onCreateCharacter` $\to$ `updateBaseCharacter` $\to$ `updateBaseNickname` $\to$ `enterHall`) implemented in Stage 4. |

---

## 3. Verified Entity Type IDs (Live Memory Citation: `libclient.so:base + 0x45785f0`)

| Entity Type ID | Hex | Entity Class Name | Role / Notes |
|:---:|:---:|:---|:---|
| **37** | `0x25` | `LoginProxy` | Interim proxy |
| **38** | `0x26` | `Account` | **Base Account entity** (verified live in heap `pPlayerEntity_` @ `0x763892626820`, `eid=1`) |
| **39** | `0x27` | `BattleAccount` | In-battle proxy |
| **40** | `0x28` | `Avatar` | In-game avatar |
| **51** | `0x33` | **`Athlete`** | **Lobby player entity** (CRITICAL: Do NOT use 56; 56 is `RobotShadow`!) |
| **56** | `0x38` | `RobotShadow` | Not Athlete! |

---

## 4. Verified Client Method Vectors (Live Memory Citation: `EntityType[id] + 0x1e8`)

### A. `Account` (Type 38)
- **`[18] msgid=146`**: **`onLogin(INT32 ret, STRING reason)`** (`ret=0, reason=''`)
- **`[19] msgid=147`**: **`onChannelLogin(UINT8 ret, PYTHON sauth)`** (`ret=0, sauth={'uid':'900000001', ...}`)

### B. `Athlete` (Type 51) — 1131 Methods Total
- `[  54] msgid= 182`: `onEnterHallTeam`
- `[  59] msgid= 187`: `onLeaveHallTeam()` (resets solo team state, prevents `hallTeamData` crash)
- `[1081] msgid=1209`: `onRefreshMSToken(STRING, STRING)`
- `[1082] msgid=1210`: `onKickOff()`
- **`[1083] msgid=1211`**: **`showSelectCharacter(ARRAY<STRING> oldNames)`** (Preloads 3D scene; required before enterHall)
- **`[1084] msgid=1212`**: **`onCreateCharacter(BOOL success, STRING reason)`** (Character creation confirmation)
- **`[1085] msgid=1213`**: **`onRoleCreateSuc(INT32 roleId)`** (Role create success, roleId=10002)
- **`[1087] msgid=1215`**: **`updateBaseCharacter(INT32 charType)`** (10002=MALE, 10005=FEMALE per `getCharactersData`)
- **`[1088] msgid=1216`**: **`updateBaseNickname(STRING nick)`**
- **`[1091] msgid=1219`**: **`enterHall(BOOL isFirstLoginOfDay)`** (Lobby entry!)
- `[1103] msgid=1231`: `onLogin(INT32, STRING)`


---

## 5. BigWorld Mercury Extended Method Wire Encoding (Reversed from `libclient.so:0xad03b0` & `0xa478a8`)

For entities where method index exceeds the single-byte limit:
1. **Threshold**:
   $$\text{div} = \lfloor(\text{num\_methods} + 192) / 255\rfloor$$
   $$\text{threshold} = 62 - \text{div}$$
   - For `Athlete` (`num_methods = 1131`): $\text{div} = 5 \implies \text{threshold} = 57$.
2. **Encoding**:
   - If $\text{method\_index} < \text{threshold}$: $w_1 = \text{method\_index}$, extra byte = `b''`.
   - If $\text{method\_index} \ge \text{threshold}$:
     $$\text{diff} = \text{method\_index} - \text{threshold}$$
     $$w_1 = \text{threshold} + \lfloor\text{diff} / 256\rfloor$$
     $$\text{extra\_byte} = \text{diff} \pmod{256}$$
3. **Wire Message ID & Width**:
   $$\text{msgID} = 128 + w_1$$
   $$\text{width} = 2 \text{ bytes (uint16 LE) if } w_1 < 64 \text{ else } 1 \text{ byte (uint8)}$$
4. **Wire Payload**:
   $$\text{payload} = [\text{entity\_id: uint32 LE}] + [\text{extra\_byte}] + [\text{args}\dots]$$

### Proof of Client-Side Execution (`scratch/live_logcat_verified_wire.txt`)
Sending `showSelectCharacter` (idx 1083) produced:
`MethodDescription::getArgsAsTuple: Failed to get arg 0 (of type ARRAY of STRING) for method showSelectCharacter from the stream.`
`MethodDescription::callMethod: Couldn't stream off args for showSelectCharacter correctly, aborting method call!`
The client parsed the entity ID, decoded method 1083, and entered `MethodDescription::callMethod` for `showSelectCharacter`!

---

## 6. Official Server Ground Truth Sequence & `_realEnterHall` Resolution

### A. Proof of `updateBaseNickname` Success
- Telemetry in `mitm/captures/SERVE_B.txt:32050` verified: `"user_name": "Survivor"` was populated on the client immediately following `updateBaseNickname("Survivor")` (was empty prior to call).

### B. Root Cause of `_realEnterHall` Crash
- In `entities\Athlete.py:656`:
  `sc = GameObject.Find('Scene')`
  `ss = sc.GetComponent('SceneSystem')`
  `ss.loadHallScene(onHallSceneReady)`
- Calling `enterHall` without preloading the scene returned `sc = None`, raising `AttributeError: 'NoneType' object has no attribute 'GetComponent'`.
- `Athlete.showSelectCharacter([])` (idx 1083) is the required method that runs `_loadDefaultScene()` $\to$ `HALL_BASE_SCENE` $\to$ creates the `Scene` GameObject!

### C. `SequenceDataType` Wire Encoding Fix for `showSelectCharacter`
- Disassembly at `libclient.so:0x9a4b74-0x9a4b88`:
  `SequenceDataType` reads a **4-byte uint32 LE length prefix** (`mov w1, #4; blr stream.read; ldr w21, [x0]`).
- For empty `ARRAY<STRING>` (`oldNames = []`), the correct argument is:
  `struct.pack('<I', 0)` (`b'\x00\x00\x00\x00'`, 4 bytes).

---

## 7. Current Implementation & Live Test Plan for Claude

Implemented in `mitm/local_baseapp_capture.py` (`run_baseapp_stage_machine` Stage 4):
1. Sends `showSelectCharacter([])` (idx 1083, 4 bytes `00 00 00 00`) $\to$ triggers `_loadDefaultScene()` and instantiates `Scene`.
2. Sleeps `ROS_SCENE_LOAD_DELAY` (default 2.5s) to allow the async loader to instantiate `Scene`.
3. Sends `onCreateCharacter(True, "")` (idx 1084) $\to$ `updateBaseCharacter(1)` (idx 1087) $\to$ `updateBaseNickname("Survivor")` (idx 1088) $\to$ `enterHall(True)` (idx 1091).
4. `enterHall` finds `GameObject.Find('Scene')` successfully, invoking `SceneSystem.loadHallScene()`.

### Live Test Instructions for Claude:
1. Relaunch server: `python mitm/local_baseapp_capture.py`
2. Force-stop and restart app on LDPlayer: `adb shell am force-stop com.netease.chiji && adb shell monkey -p com.netease.chiji 1`
3. Capture logcat: `adb logcat -c && adb logcat > scratch/live_logcat_stage4_verified.txt &`
4. Tap PLAY: `adb shell input tap 960 740`
5. Verify in logcat that `_loadDefaultScene` and `showSelectCharacter` execute without arg errors, and `enterHall` executes without `AttributeError`!
6. Verify 3D scene / Lobby screencap!

