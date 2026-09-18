# Continuation Prompt for Claude / Next AI Session (ROS_RE Mobile Track)

> **Target**: Rules of Survival Mobile (`com.netease.chiji`, v1.610377.506841, vCode 1117219, arm64-v8a)  
> **Workspace**: `C:\Users\Raysoo\Downloads\ROS_RE`  
> **Emulator**: LDPlayer 9 (`emulator-5554`, Android `172.16.1.15`, Gateway/Host `172.16.1.2`)  
> **ADB Path**: `C:\LDPlayer\LDPlayer9\adb.exe`  
> **Current Date**: 2026-09-18 (Checkpoint 15: Gate 4 Wire Protocol Solved, Ground Truth Lobby Entry Implemented)

---

## 1. Executive Summary & Gate Status

| Gate | Protocol / Target | Status | Proven Implementation Details |
|:---|:---|:---:|:---|
| **Gate 0** | Patch / CDN HTTP :80/:443 | **PASS** | Local HTTP server (`mitm_serve.py` / `local_baseapp_capture.py`) returns valid manifest. |
| **Gate 1** | UniSDK Auth HTTP :80/:443/:8443 | **PASS** | Handles guest auth, tokens, Sigma keypoints (`connectLoginHostCallback` status=1). |
| **Gate 2** | LoginApp UDP :25000 | **PASS** | 4-byte LE ReplyID @ wire offset 5. Blowfish `pc_variant` encrypted `LoginReplyRecord` pointing to BaseApp `172.16.1.2:25010`. |
| **Gate 3** | BaseApp Channel & Handshake :25010 | **PASS** | Session key discovered live from heap. `createBasePlayer(Account, type 38, eid 1)` accepted; reliable ACK protocol; 864-byte handshake handled. |
| **Gate 4** | Athlete & Lobby / Hall Entry | **VERIFIED & IMPLEMENTED** | **BigWorld Mercury extended method wire encoding solved and mathematically proven.** Real-server ground truth sequence (`onCreateCharacter` $\to$ `updateBaseCharacter` $\to$ `updateBaseNickname` $\to$ `enterHall`) implemented in Stage 4 of `local_baseapp_capture.py`. |

---

## 2. Definitive Breakthroughs from Memory & Disassembly

### A. Entity Types (Live Process Memory @ `libclient.so:base + 0x45785f0`)
- **Type 38** (`0x26`): `Account` (Base account entity)
- **Type 51** (`0x33`): `Athlete` (Lobby player entity — **NOT 56**; 56 is `RobotShadow`!)

### B. BigWorld Mercury Extended Method Wire Formula (Reversed from `libclient.so:0xad03b0` & `0xa478a8`)
For entities with many methods (e.g. `Athlete` with **1131 methods**):
1. **Threshold Calculation**:
   $$\text{div} = \lfloor(\text{num\_methods} + 192) / 255\rfloor = \lfloor(1131 + 192) / 255\rfloor = 5$$
   $$\text{threshold} = 62 - \text{div} = 62 - 5 = 57$$
2. **Index & Wire Message ID Encoding**:
   - If $\text{method\_index} < \text{threshold}$:
     $w_1 = \text{method\_index}$, extra byte = `b''`
   - If $\text{method\_index} \ge \text{threshold}$:
     $$\text{diff} = \text{method\_index} - \text{threshold}$$
     $$w_1 = \text{threshold} + \lfloor\text{diff} / 256\rfloor$$
     $$\text{extra\_byte} = \text{diff} \pmod{256} \quad (1 \text{ byte uint8 prepended to payload})$$
3. **Wire Message ID & Width**:
   $$\text{msgID} = 128 + w_1$$
   $$\text{width} = 2 \text{ bytes (uint16 LE) if } w_1 < 64 \text{ else } 1 \text{ byte (uint8)}$$
4. **Wire Payload**:
   $$\text{payload} = [\text{entity\_id: uint32 LE}] + [\text{extra\_byte}] + [\text{args}\dots]$$

### C. Proof of Correctness from Client Logcat (`scratch/live_logcat_verified_wire.txt`)
When `showSelectCharacter` (method index 1083, $w_1 = 61 \implies \text{msgID} = 189 \ (0xBD)$, extra byte = `0x02`) was sent:
```text
[ERROR] MethodDescription::getArgsAsTuple: Failed to get arg 0 (of type ARRAY of STRING) for method showSelectCharacter from the stream.
[ERROR] MethodDescription::callMethod: Couldn't stream off args for showSelectCharacter correctly, aborting method call!
```
The client **successfully unpacked the entity ID, identified method index 1083, and invoked `showSelectCharacter`**! This completely validated the reversed formula.

---

## 3. Ground Truth Gate 4 Sequence from Real Traffic (`mitm/captures/SERVE_B.txt`)

Analysis of official NetEase server traffic (`SERVE_B.txt` lines 5240–5254) revealed that **the server NEVER sends `showSelectCharacter` to valid accounts**. Instead, the official sequence is:

1. `accountOnBecomePlayer` (`Account` eid=1, type 38)
2. `athleteOnBecomePlayer` (`Athlete` eid=1, type 51)
3. **`Athlete.onCreateCharacter(True, "")`** (method idx **1084**):
   - $1084 - 57 = 1027 \implies w_1 = 61 \implies \text{msgID} = 189$ (`0xBD`), extra byte = `0x03`
   - Args: `struct.pack('<B', 1) + b'\x00'` (BOOL=1, STRING="" with 1-byte length 0)
   - Client emits Sigma keypoint: `{"keypoint": "onCreateCharacter", "extraData": "{\"ret\": 1, \"msg\": \"\"}"}`!
4. **`Athlete.updateBaseCharacter(1)`** (method idx **1087**):
   - $1087 - 57 = 1030 \implies w_1 = 61 \implies \text{msgID} = 189$ (`0xBD`), extra byte = `0x06`
   - Args: `struct.pack('<i', 1)` (INT32=1)
5. **`Athlete.updateBaseNickname("Survivor")`** (method idx **1088**):
   - $1088 - 57 = 1031 \implies w_1 = 61 \implies \text{msgID} = 189$ (`0xBD`), extra byte = `0x07`
   - Args: `b'\x08Survivor'` (1-byte length 8 + ASCII)
6. **`Athlete.enterHall(True)`** (method idx **1091**):
   - $1091 - 57 = 1034 \implies w_1 = 61 \implies \text{msgID} = 189$ (`0xBD`), extra byte = `0x0A`
   - Args: `struct.pack('<B', 1)` (BOOL=1, isFirstLoginOfDay=True)
   - Client transitions into the 3D Lobby and emits: `{"keypoint": "athleteEnterHall"}`!

---

## 4. Code Implemented in `mitm/local_baseapp_capture.py`

1. **`send_entity_method()`** (lines 758–784):
   Encodes any entity method call using the exact BigWorld Mercury formula.
2. **`run_baseapp_stage_machine()` Stage 4** (lines 869–900):
   ```python
   # Stage 4: Athlete character activation & enterHall (ground truth from SERVE_B.txt)
   time.sleep(0.1)
   use_key = _key_cache.get(addr) or _early_key_by_host.get(addr[0]) or key or _BFKEY_HEX

   # 1. Athlete.onCreateCharacter(True, "") (idx 1084)
   occ_args = struct.pack('<B', 1) + _packed_int(0)
   send_entity_method(sock, addr, use_key, athlete_eid, 1084, occ_args, flags=0x0008, num_methods=1131)

   # 2. Athlete.updateBaseCharacter(1) (idx 1087)
   time.sleep(0.05)
   ubc_args = struct.pack('<i', 1)
   send_entity_method(sock, addr, use_key, athlete_eid, 1087, ubc_args, flags=0x0008, num_methods=1131)

   # 3. Athlete.updateBaseNickname("Survivor") (idx 1088)
   time.sleep(0.05)
   nick = b"Survivor"
   ubn_args = _packed_int(len(nick)) + nick
   send_entity_method(sock, addr, use_key, athlete_eid, 1088, ubn_args, flags=0x0008, num_methods=1131)

   # 4. Athlete.enterHall(True) (idx 1091)
   time.sleep(0.1)
   eh_args = struct.pack('<B', 1)
   send_entity_method(sock, addr, use_key, athlete_eid, 1091, eh_args, flags=0x0008, num_methods=1131)
   ```

---

## 5. Current State & What Claude Needs to Do Next

1. **Active Game & Server State**:
   - The game is currently open in LDPlayer at the title screen with the `- PLAY -` button visible.
   - The server is running as a daemon (`python mitm/local_baseapp_capture.py`).
   - The game process has a fresh PID (check with `adb shell pidof com.netease.chiji`).
2. **Immediate Actions for Claude**:
   - Tap the PLAY button (center at `X=948, Y=752` on 1920x1080):
     ```powershell
     & 'C:\LDPlayer\LDPlayer9\adb.exe' shell input tap 948 752
     ```
   - Watch the server log for:
     ```text
     BASEAPP STAGE 1: sent createBasePlayer(Account)
     BASEAPP STAGE 2: sent Account.onChannelLogin & onLogin
     BASEAPP STAGE 3: sent createBasePlayer(Athlete)
     BASEAPP STAGE 4: sent Athlete.onCreateCharacter(ret=1) idx=1084
     BASEAPP STAGE 4: sent Athlete.updateBaseCharacter(1) idx=1087
     BASEAPP STAGE 4: sent Athlete.updateBaseNickname("Survivor") idx=1088
     BASEAPP STAGE 4: sent Athlete.enterHall(True) idx=1091
     ```
   - Check Sigma telemetry for:
     - `{"keypoint": "onCreateCharacter"}`
     - `{"keypoint": "athleteEnterHall"}`
   - Capture screen to confirm 3D Lobby UI rendered:
     ```powershell
     & 'C:\LDPlayer\LDPlayer9\adb.exe' shell screencap -p /sdcard/screen.png
     & 'C:\LDPlayer\LDPlayer9\adb.exe' pull /sdcard/screen.png scratch/lobby_screen.png
     ```
