# Handoff to Claude: Athlete Property Stream Finalization & In-Game Lobby Handshake

> **From**: Antigravity / Gemini Agent  
> **To**: Claude Code / Claude Desktop  
> **Date**: 2026-09-20  
> **Workspace**: `C:\Users\Raysoo\Downloads\ROS_RE`  
> **Client Version**: Rules of Survival Mobile (Android `com.netease.chiji`, v1.610377.506841, arm64-v8a)  
> **Target Environment**: LDPlayer 9 (`emulator-5554`, Android guest `172.16.1.15`, Gateway host `172.16.1.2`)

---

## 1. Executive Summary & Verified Milestones

| Gate / Component | Status | Key Breakthrough / Verified Ground Truth |
|:---|:---:|:---|
| **Gate 0: Patch/CDN** | **PASS** | Local HTTP server (`mitm/local_baseapp_capture.py`) intercepts update manifests. |
| **Gate 1: UniSDK / Sigma** | **PASS** | Guest auth, keypoint telemetry, and token lifecycle callbacks fully working. |
| **Gate 2: LoginApp UDP :25000** | **PASS** | Blowfish `pc_variant` encrypted `LoginReplyRecord` redirecting client to BaseApp. |
| **Gate 3: BaseApp UDP :25010** | **PASS** | Handshake, SessionKey exchange, channel reliable ACK protocol, `Account.onChannelLogin(code=0)`. |
| **Gate 4: 3D Scene Preload** | **PASS** | `showSelectCharacter([])` with 4-byte uint32 count=0 cleanly preloads `HALL_BASE_SCENE` and spawns `Scene` GameObject with `SceneSystem`. |
| **Gate 4: Athlete Method Dispatch** | **PASS** | Extended Mercury method wire encoding formula mathematically verified live (`onCreateCharacter`, `onRoleCreateSuc(10002)`, `updateBaseCharacter(10002)`, `updateBaseNickname("Survivor")`, `onLeaveHallTeam()`, `enterHall(True)`). |
| **Gate 4: Athlete Property Stream** | **IN PROGRESS (95% COMPLETE)** | Deserializer reversed (`libclient.so` `FUN_00acf5ec` / `FUN_00acf8ac`). All **13 DataType vtables resolved 100% via ELF RTTI parsing**. Properties 0..300 verified byte-perfect in live tests. `weekendPushRewardsHaveGotten` (ord 258) delivered as pickled `[]`, completely eliminating the `iWeekendPush.py` TypeError crash! Remaining task: resolve ordinals 301..306 default collection types. |

---

## 2. ELF RTTI & DataType VTable Truth Table (Demangled from `libclient.so`)

Parsed directly from `.data.rel.ro` and `.rodata` RTTI `type_info` structures in `libclient.so` (arm64-v8a):

| VTable VA (Offset) | Demangled C++ Class | Type | Wire Encoding | Size (Empty / Default) |
|:---|:---|:---:|:---|:---:|
| `0x37ddf90` | `neox::bwclient::FixedDictDataType` | `FIXED_DICT` | Concatenated child fields | `rankRecord`=4B, `braveBookDataList`=4B, `dtsAppearancePackage`=15B |
| `0x37de050` | `neox::bwclient::StringDataType` | `STRING` | `packed_int(len) + raw_bytes` | `packed_int(0)` = `b'\x00'` (1B) |
| `0x37de448` | `neox::bwclient::ArrayDataType` | `ARRAY` | `struct.pack('<I', count) + elements` | `struct.pack('<I', 0)` (4B) |
| `0x37de778` | `neox::bwclient::IntegerDataType<unsigned char>` | `UINT8` | `struct.pack('<B', val)` | `b'\x00'` (1B) |
| `0x37de9d8` | `neox::bwclient::IntegerDataType<char>` | `INT8` | `struct.pack('<b', val)` | `b'\x00'` (1B) |
| `0x37deb08` | `neox::bwclient::IntegerDataType<short>` | `INT16` | `struct.pack('<h', val)` | `struct.pack('<h', 0)` (2B) |
| `0x37dec38` | `neox::bwclient::IntegerDataType<int>` | `INT32` | `struct.pack('<i', val)` | `struct.pack('<i', 0)` (4B) |
| `0x37df0f8` | `neox::bwclient::LongIntegerDataType<unsigned int>` | `UINT32` | `struct.pack('<I', val)` | `struct.pack('<I', 0)` (4B) |
| `0x37df228` | `neox::bwclient::LongIntegerDataType<long long>` | `INT64` | `struct.pack('<q', val)` | `struct.pack('<q', 0)` (8B) |
| `0x37df418` | `neox::bwclient::LongIntegerDataType<unsigned long long>`| `UINT64` | `struct.pack('<Q', val)` | `struct.pack('<Q', 0)` (8B) |
| `0x37df778` | `neox::bwclient::FloatDataType<float>` | `FLOAT` | `struct.pack('<f', val)` | `struct.pack('<f', 0.0)` (4B) |
| `0x37dfa28` | `neox::bwclient::PythonDataType` | `PYTHON` | `packed_int(len) + pickle_bytes` | `packed_int(2) + b'N.'` (3B) |
| `0x37e04f8` | `neox::bwclient::BlobDataType` | `BLOB` | `packed_int(len) + raw_bytes` | `packed_int(0)` = `b'\x00'` (1B) |

---

## 3. Property Stream Status & The Ordinals 301..306 Diagnosis

### A. Verified Working Bisection Results
Using `scratch/gen_stream_trunc.py <K>`:
- **K=262 (876 bytes)**: In sync.
- **K=284 (930 bytes)**: In sync.
- **K=295 (968 bytes)**: In sync.
- **K=301 (974 bytes)**: **100% in sync with 0 bytes remaining!**
- **Ordinal 258 (`weekendPushRewardsHaveGotten`, idx 515)**: Arrives as `[]` (`packed_int(3) + b'(l.'`). `iWeekendPush.py` TypeError is completely gone!

### B. Remaining Desync at Ordinals 301..306 (`iNewYearGoal`)
At ordinal 301, the entity stream transitions into `iNewYearGoal` interface properties (`05_entities/out/entity_0273.xml`):

```xml
[ord 301] [idx 590] newYearGoalSendInfo:           Type=PYTHON, Default=[]
[ord 302] [idx 591] newYearGoalReceiveInfo:        Type=PYTHON, Default={}
[ord 303] [idx 592] globalNewYearGoalTaskInfo:     Type=PYTHON, Default={}
[ord 304] [idx 593] newYearGoalTaskIDList:         Type=PYTHON, Default=[]
[ord 305] [idx 595] newYearGoalInviteRedPointList: Type=PYTHON, Default={}
[ord 306] [idx 596] forbidedNewYearGoalTaskIDList: Type=PYTHON, Default=[]
```

- When these properties are encoded with generic `None` (`b'N.'`, 3 bytes), `iNewYearGoal.onCreate` throws `TypeError: 'NoneType' object is not iterable` when iterating `self.newYearGoalSendInfo` or referencing dict keys.
- **Fix**: In `scratch/gen_stream_v2.py`, encode collections with their declared defaults:
  - Default `[]`: `packed_int(3) + b'(l.'` (or `b']\x00'`) (3 bytes)
  - Default `{}`: `packed_int(3) + b'(d.'` (or `b'}\x00'`) (3 bytes)

---

## 4. Current Environment State & Safety Rules

1. **Emulator Root & iptables**:
   - Device: `emulator-5554` (Redmi 22081212C, Android 9 Pie).
   - Root is active (`su 0 id` -> `uid=0(root)`).
   - All 5 iptables DNAT rules are active (`tcp:80, 443, 8443`, `udp:25000, 20013` -> `172.16.1.2`).
   - **Rule**: If the emulator ever hangs, restart LDPlayer from the desktop icon; DO NOT run `adb reboot` (reboot drops su binary permissions in this guest image).
2. **Server Process**:
   - `mitm/local_baseapp_capture.py` is configured with `ROS_ATHLETE_USE_STREAM_FILE=1`.
   - Modifying `data/athlete_mobile_stream.bin` is immediately read on the next login attempt without requiring a server restart.
3. **ADB Client Hygiene**:
   - Avoid leaving background `adb logcat > file &` processes running; kill adb clients before launching test runs.

---

## 5. Next Action Items for Claude

1. **Update `scratch/gen_stream_v2.py`**:
   - Set specific pickle encodings for Python collection defaults (`[]` -> `packed_int(3) + b'(l.'`, `{}` -> `packed_int(3) + b'(d.'`).
   - Regenerate `data/athlete_mobile_stream.bin`.
2. **Run End-to-End Login Test**:
   - Clear logcat: `adb -s emulator-5554 logcat -c`
   - Tap PLAY: `adb -s emulator-5554 shell input tap 960 740`
   - Capture logcat: `adb -s emulator-5554 logcat -d > scratch/live_logcat_latest.txt`
3. **Verify Lobby State**:
   - Confirm `ServerConnection::createBasePlayer: id 1` consumes all 1457 bytes.
   - Confirm `athleteEnterHall` keypoint fires and client enters full 3D Lobby with avatar model visible!
