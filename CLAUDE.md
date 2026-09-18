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
`Athlete` inherits 152 interfaces resulting in 1080 flattened interface methods preceding Athlete's own methods:
- `[1081] msgid=1209`: `onRefreshMSToken(STRING, STRING)`
- `[1082] msgid=1210`: `onKickOff()`
- **`[1083] msgid=1211`**: **`showSelectCharacter(ARRAY<STRING> oldNames)`** (Drives Character Creation UI if character does not exist)
- **`[1084] msgid=1212`**: **`onCreateCharacter(BOOL success, STRING reason)`** (Character creation confirmation)
- **`[1085] msgid=1213`**: **`onRoleCreateSuc(INT32 roleId)`**
- **`[1087] msgid=1215`**: **`updateBaseCharacter(INT32 charType)`**
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

## 6. Official Server Ground Truth Sequence (`mitm/captures/SERVE_B.txt`)

Lines 5240–5254 in real traffic:
1. `accountOnBecomePlayer` (`createBasePlayer(Account, type=38, eid=1)`)
2. `athleteOnBecomePlayer` (`createBasePlayer(Athlete, type=51, eid=1, stream=b'')`)
3. `onCreateCharacter(True, "")` (idx 1084) $\to$ Client emits `{"keypoint": "onCreateCharacter", "extraData": "{\"ret\": 1, \"msg\": \"\"}"}`
4. `updateBaseCharacter(1)` (idx 1087)
5. `updateBaseNickname("Survivor")` (idx 1088)
6. `enterHall(True)` (idx 1091) $\to$ Client transitions into 3D Lobby and emits `{"keypoint": "athleteEnterHall"}`!

---

## 7. Current Implementation & Next Steps

Implemented in `mitm/local_baseapp_capture.py`:
- `send_entity_method()`: Generic BigWorld Mercury method encoder.
- `run_baseapp_stage_machine()`: Stage 4 now sends `onCreateCharacter` $\to$ `updateBaseCharacter` $\to$ `updateBaseNickname` $\to$ `enterHall`.

### Immediate Actions:
1. Tap PLAY on client (`adb shell input tap 948 752`).
2. Verify in server log that Stage 4 executes all 4 RPCs.
3. Check Sigma telemetry for `onCreateCharacter` and `athleteEnterHall`.
4. Capture screenshot of 3D Lobby.
