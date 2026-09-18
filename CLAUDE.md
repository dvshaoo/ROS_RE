# CLAUDE.md — Rules of Survival (ROS) Mobile RE & Private Server Guide

> **Project**: Rules of Survival Mobile Private Server Emulation (Game Preservation)  
> **Client**: Android APK `com.netease.chiji`, v1.610377.506841, vCode 1117219, arm64-v8a  
> **Target Environment**: LDPlayer 9 (`emulator-5554`, Android guest `172.16.1.15`, Gateway host `172.16.1.2`)  
> **ADB Path**: `C:\LDPlayer\LDPlayer9\adb.exe`  
> **Primary Script**: `mitm/local_baseapp_capture.py`

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
| **Gate 4** | Character Select / Lobby | Mercury RPC / DEF | **IN PROGRESS (SOLVED INDICES)** | Pinned exact `Athlete` method indices directly from process memory: `showSelectCharacter` is index **1083** (msgID 1211). |

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
- **`[1083] msgid=1211`**: **`showSelectCharacter(ARRAY<STRING> oldNames)`** (Empty array `0x00` -> **Drives Character Creation UI!**)
- **`[1084] msgid=1212`**: **`onCreateCharacter(BOOL success, STRING reason)`**
- **`[1085] msgid=1213`**: **`onRoleCreateSuc(INT32 roleId)`**
- **`[1087] msgid=1215`**: **`updateBaseCharacter(INT32 charType)`**
- **`[1091] msgid=1219`**: **`enterHall(BOOL isFirstLoginOfDay)`** (Lobby entry!)
- `[1103] msgid=1231`: `onLogin(INT32, STRING)`

---

## 5. Critical Mechanics & Implementation Details

### A. Empty Stream for BasePlayer Creation
- In `libclient.so` `0x92a58c` (`EntityType::newDictionary`):
  `0x92a5d4: cbz w0, #0x92a60c`: If stream is empty (`remainingLength == 0`), client skips stream unpack, initializes clean default dictionary via `PyDict_New()`, and succeeds.
  If stream has mismatched/guessed data, unpack throws `TypeError: 'FailedUnpickle'` in `iBindPhone.py:132`.
- **Rule**: Send `createBasePlayer(Athlete, type=51, eid=1, stream=b'')`.

### B. Wire Dispatch for Method Index 1083
Because 1083 > 63, BigWorld Mercury uses:
1. **Candidate A (Standard `longEntityMessage`)**:
   `ClientInterface` message **101** (2-byte length prefix):
   ```python
   # [flags: u16 = 0x0008][msgID: u8 = 101][len: u16][eid: u32][method_index: u16 = 1083][args: u8 = 0]
   payload = struct.pack('<I', athlete_eid) + struct.pack('<H', 1083) + bytes([0])
   plain = struct.pack('<H', 0x0008) + bytes([101]) + struct.pack('<H', len(payload)) + payload
   pad_len = 8 - (len(plain) % 8)
   padded = plain + b'\x00' * (pad_len - 1) + bytes([pad_len])
   enc = bf_encrypt(padded, key_hex=key, iv=b'\x00' * 8)
   sock.sendto(enc, client_addr)
   ```
2. **Candidate B (Direct msgID modulo 256)**:
   `msgID = (128 + 1083) & 0xff = 1211 & 0xff = 187 (0xBB)` with 2-byte length prefix:
   ```python
   payload = struct.pack('<I', athlete_eid) + bytes([0])
   plain = struct.pack('<H', 0x0008) + bytes([187]) + struct.pack('<H', len(payload)) + payload
   ```

### C. Bundle Termination Rule (`FLAG_HAS_REQUESTS`)
- Only append `00 00` footer to bundles when `flags & 1` (`FLAG_HAS_REQUESTS`) is set.
- Appending `00 00` without bit 0 causes client bundle parser to misread trailing bytes as a truncated msgID 0 (`authenticate`).

### D. LoginApp Reachability Probe (`b'hello ros'`)
- Skip literal 9-byte ASCII packet `b'hello ros'` on LoginApp UDP 25000 (`if data == b'hello ros': continue`). Do not reply with LoginReplyRecord.

### E. Diagnostic Telemetry: `connectLoginHostCallback`
- Check `mitm/captures/SERVE_B.txt` for `connectLoginHostCallback`:
  `status: 1` = BaseApp connection will occur.
  `status: 2` = Pre-BaseApp handshake failed.

---

## 6. Immediate Next Steps for Claude
1. **In `mitm/local_baseapp_capture.py`**:
   - In Stage 3, send `createBasePlayer(Athlete, type=51, eid=1, stream=b'')`.
   - In Stage 4, send `showSelectCharacter` (Method Index 1083) using Candidate A (msgID 101) and Candidate B (msgID 187).
2. **Launch & Verify**:
   - Start server: `python mitm/local_baseapp_capture.py`
   - Tap PLAY in LDPlayer
   - Check screencap for Character Creation UI (`UISelectCharacter`)!
