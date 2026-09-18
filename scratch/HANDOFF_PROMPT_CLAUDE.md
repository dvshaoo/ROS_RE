# Continuation Prompt for Claude / Next AI Session (ROS_RE Mobile Track)

> **Target**: Rules of Survival Mobile (`com.netease.chiji`, v1.610377.506841, arm64-v8a)  
> **Workspace**: `C:\Users\Raysoo\Downloads\ROS_RE`  
> **Emulator**: LDPlayer 9 (`emulator-5554`, Android `172.16.1.15`, Host `172.16.1.2`)  
> **ADB Path**: `C:\LDPlayer\LDPlayer9\adb.exe`  
> **Active PID**: `23776` (or check with `adb shell pidof com.netease.chiji`)

---

## 1. Standing Rules (Do NOT Violate)
- **Local/LAN only**. Never touch real NetEase servers.
- **Never guess packet formats or indices without evidence.** Every value below is cited from live memory or Ghidra disassembly.
- **Commit frequently with descriptive git messages.**

---

## 2. Definitive Breakthroughs from Memory & Disassembly

### A. Entity Type IDs (from `libclient.so:base + 0x45785f0`)
- `LoginProxy`: Type **37** (`0x25`)
- `Account`: Type **38** (`0x26`) — Base account entity
- `BattleAccount`: Type **39** (`0x27`)
- `Avatar`: Type **40** (`0x28`)
- **`Athlete`**: Type **51** (`0x33`) — **Lobby character entity** (CRITICAL: Do NOT use 56; 56 is `RobotShadow`!)

### B. Confirmed Live Memory State (`Entities` singleton @ `base + 0x45786e0`)
- `*Entities` (offset 0) points to `pPlayerEntity_` (`0x763892626820`).
- The player entity in live memory is currently `Account` (`Type 38`, `eid = 1`).
- The client successfully sent its **864-byte `Account.handshake`** and Sigma reported:
  - `{"keypoint": "accountOnBecomePlayer"}`
  - `{"keypoint": "onChannelLogin", "extraData": "{\"code\": 0}"}`
  - Telemetry: `"Login Succ"`!

### C. The Holy Grail Discovery: Athlete Method Vector (`EntityType[51] + 0x1e8`)
Extracted directly from the running process memory. `Athlete` implements 152 interfaces resulting in 1080 flattened interface methods preceding its own methods. Total client methods = **1131**:

| Method Index | Wire msgID | Method Name | Parameters | Purpose |
|:---:|:---:|:---|:---|:---|
| **18** (in Account) | 146 | `onLogin` | `INT32 ret, STRING reason` | Complete Account login (`ret=0, reason=''`) |
| **19** (in Account) | 147 | `onChannelLogin` | `UINT8 ret, PYTHON sauth` | Authenticate Account (`ret=0, sauth={...}`) |
| **1081** (in Athlete) | 1209 | `onRefreshMSToken` | `STRING, STRING` | Refresh token |
| **1082** (in Athlete) | 1210 | `onKickOff` | - | Kick off |
| **1083** (in Athlete) | **1211** | **`showSelectCharacter`** | `ARRAY<STRING> oldNames` | **Empty list (`0x00`) drives Create-Character UI!** |
| **1084** (in Athlete) | 1212 | `onCreateCharacter` | `BOOL success, STRING reason` | Result of character creation |
| **1085** (in Athlete) | 1213 | `onRoleCreateSuc` | `INT32 roleId` | Role creation success |
| **1087** (in Athlete) | 1215 | `updateBaseCharacter` | `INT32 charType` | Update base character |
| **1091** (in Athlete) | 1219 | `enterHall` | `BOOL isFirstLoginOfDay` | **Enter main lobby!** |

---

## 3. The Two Tasks for Claude to Complete Gate 4

### Task 1: Fix `createBasePlayer(Athlete)` Stream
In `mitm/local_baseapp_capture.py`, Stage 3 previously sent `athlete_mobile_stream.bin` (3632 bytes), which caused `EntityType::newDictionary` (`0x92a58c`) to fail because the guessed stream didn't match the 152 interfaces.
- **Disassembly proof of `0x92a58c`**:
  `0x92a5d4: cbz w0, #0x92a60c`: If stream is empty (`remainingLength == 0`), it calls `0x92a344` (`PyDict_New()`), sets defaults, and succeeds without unpacking!
- **Fix**: Send `createBasePlayer(Athlete, type=51, eid=1, stream=b'')`.

### Task 2: Deliver `showSelectCharacter` (Method Index 1083)
Because 1083 > 63, it cannot fit directly in a standard 1-byte `128 + idx` msgID without extension.
Test the two standard BigWorld delivery mechanisms:
1. **Candidate A (Standard BigWorld Extended Message `longEntityMessage`)**:
   `ClientInterface` message **101** is `longEntityMessage` with a 2-byte length prefix:
   ```python
   # [flags: u16 = 0x0008][msgID: u8 = 101][len: u16][eid: u32][method_idx: u16 = 1083][args: u8 = 0]
   payload = struct.pack('<I', athlete_eid) + struct.pack('<H', 1083) + bytes([0])
   plain = struct.pack('<H', 0x0008) + bytes([101]) + struct.pack('<H', len(payload)) + payload
   pad_len = 8 - (len(plain) % 8)
   padded = plain + b'\x00' * (pad_len - 1) + bytes([pad_len])
   enc = bf_encrypt(padded, key_hex=key, iv=b'\x00' * 8)
   sock.sendto(enc, client_addr)
   ```
2. **Candidate B (Direct msgID modulo 256)**:
   `msgID = (128 + 1083) & 0xff = 1211 & 0xff = 187 (0xBB)`:
   ```python
   payload = struct.pack('<I', athlete_eid) + bytes([0])
   plain = struct.pack('<H', 0x0008) + bytes([187]) + struct.pack('<H', len(payload)) + payload
   pad_len = 8 - (len(plain) % 8)
   padded = plain + b'\x00' * (pad_len - 1) + bytes([pad_len])
   enc = bf_encrypt(padded, key_hex=key, iv=b'\x00' * 8)
   sock.sendto(enc, client_addr)
   ```

---

## 4. Verification Commands
- Check live player entity in memory:
  ```powershell
  python -c "import subprocess, struct, base64; ADB='C:\\LDPlayer\\LDPlayer9\\adb.exe'; pid=subprocess.run([ADB, '-s', 'emulator-5554', 'shell', 'pidof', 'com.netease.chiji'], capture_output=True).stdout.decode().strip().split()[0]; maps=subprocess.run([ADB, '-s', 'emulator-5554', 'shell', 'su', '0', 'cat', f'/proc/{pid}/maps'], capture_output=True).stdout.decode(errors='replace'); base=int([l for l in maps.splitlines() if 'libclient.so' in l and '00000000' in l][0].split()[0].split('-')[0], 16); cmd=f'su 0 dd if=/proc/{pid}/mem bs=1 count=8 skip={base+0x45786e0} 2>/dev/null | base64'; b=struct.unpack('<Q', base64.b64decode(subprocess.run([ADB, '-s', 'emulator-5554', 'shell', cmd], capture_output=True).stdout.decode().strip()))[0]; cmd2=f'su 0 dd if=/proc/{pid}/mem bs=1 count=32 skip={b} 2>/dev/null | base64'; p=struct.unpack('<Q', base64.b64decode(subprocess.run([ADB, '-s', 'emulator-5554', 'shell', cmd2], capture_output=True).stdout.decode().strip())[:8])[0]; cmd3=f'su 0 dd if=/proc/{pid}/mem bs=1 count=32 skip={p} 2>/dev/null | base64'; raw=base64.b64decode(subprocess.run([ADB, '-s', 'emulator-5554', 'shell', cmd3], capture_output=True).stdout.decode().strip()); print(f'PlayerEntity @ 0x{p:x}, type_ptr=0x{struct.unpack(\"<Q\", raw[16:24])[0]:x}, eid={struct.unpack(\"<I\", raw[24:28])[0]}')"
  ```
- Capture screen:
  ```powershell
  & 'C:\LDPlayer\LDPlayer9\adb.exe' -s emulator-5554 shell screencap -p /sdcard/screen.png
  & 'C:\LDPlayer\LDPlayer9\adb.exe' -s emulator-5554 pull /sdcard/screen.png scratch/screen_claude.png
  ```
