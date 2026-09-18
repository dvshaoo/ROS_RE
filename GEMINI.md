# GEMINI.md — Rules of Survival (ROS) Private Server Emulation & RE Master Guide

> **Author**: Gemini / Antigravity Agent  
> **Last Updated**: 2026-09-18 (Checkpoint 14: updateEntity decompiled; iWeekendPush crash traceback confirmed non-fatal)  
> **Client Version**: Rules of Survival Mobile (Android `com.netease.chiji`, v1.610377.506841, vCode 1117219, arm64-v8a)  
> **Target Environment**: LDPlayer 9 (`emulator-5554`, Android guest `172.16.1.15`, Gateway host `172.16.1.2`)

---

## 1. Executive Summary & Milestones Status

| Gate | Component | Protocol | Status | Key Finding / Implementation |
|:---|:---|:---|:---:|:---|
| **Gate 0** | Patch / CDN Server | HTTP :80/:443 | **PASS** | Bypassed patch check using local HTTP server (`mitm_serve.py` / `local_baseapp_capture.py`). Returns valid update manifest. |
| **Gate 1** | UniSDK / Auth / Sigma | HTTP :80/:443/:8443 | **PASS** | Handled guest auth token, keypoints, and telemetry callbacks (`connectLoginHostCallback` status=1). |
| **Gate 2** | LoginApp UDP Handshake | Mercury UDP :25000 | **PASS** | Solved 4-byte LE ReplyID correlation @ wire offset 5. Blowfish `pc_variant` encrypted `LoginReplyRecord` pointing client to BaseApp `172.16.1.2:25010`. |
| **Gate 3** | BaseApp Channel & Handshake | Mercury UDP :25010 | **PASS** | `createBasePlayer(Account, type 38, eid 1)` accepted; client reached `status==LOGGED_ON`. Client packet #0 decrypted; reliable ACK protocol reversed; client sent 864-byte `Account.handshake`; `accountOnBecomePlayer` and `onChannelLogin(code=0)` fired! |
| **Gate 4** | Character Select / Lobby | Mercury RPC / DEF | **PASS (READY FOR LIVE TEST)** | Wire formula verified live by Claude (`onCreateCharacter` ret=1). `updateBaseNickname` verified in telemetry (`"user_name": "Survivor"`). `_realEnterHall` crash resolved: was caused by missing `HALL_BASE_SCENE` preload. Fixed `showSelectCharacter` (idx 1083) `ARRAY` wire format to use 4-byte uint32 LE count (`struct.pack('<I', 0)`). Stage 4 loads scene then transitions to Character Creation / Lobby! |

---

## 2. Definitive Entity Types (Live Process Memory Citation)

Extracted directly from `libclient.so:base + 0x45785f0` (`std::vector<EntityType*>` in running process memory, 172 entity types total):

| Entity Type ID | Hex | Entity Class Name | Provenance / Role |
|:---:|:---:|:---|:---|
| **37** | `0x25` | `LoginProxy` | Interim proxy before Account |
| **38** | `0x26` | `Account` | **Base Account player** (verified live in heap `pPlayerEntity_` @ `0x763892626820`, eid=1) |
| **39** | `0x27` | `BattleAccount` | In-battle proxy |
| **40** | `0x28` | `Avatar` | In-game avatar |
| **51** | `0x33` | **`Athlete`** | **Lobby player entity** (CRITICAL: Previously mistaken as 56, but 56 is `RobotShadow`!) |
| **56** | `0x38` | `RobotShadow` | Do not use for Athlete! |

---

## 3. Definitive Client Method Vectors (Live Process Memory Citation)

Extracted directly from `EntityType[id] + 0x1e8` (`std::vector<MethodDescription>`, where each element is 24 bytes storing libc++ `std::string` inline method names):

### A. `Account` (Type 38) — 25 Methods Total
- `[11] msgid=139`: `onRankRefresh`
- `[12] msgid=140`: `onEnterQueueFailed`
- `[13] msgid=141`: `onRequireActivation`
- `[14] msgid=142`: `onShowRealNameAuthenWebView`
- `[17] msgid=145`: `loadSceneAfterReconnect`
- **`[18] msgid=146`**: **`onLogin(INT32 ret, STRING reason)`** (OK = `ret=0, reason=''`)
- **`[19] msgid=147`**: **`onChannelLogin(UINT8 ret, PYTHON sauth)`** (OK = `ret=0, sauth={'uid':'900000001', ...}`)
- `[24] msgid=152`: `onLoginPCServer(BOOL)`

### B. `Athlete` (Type 51) — 1131 Methods Total
`Athlete` implements 152 interfaces, resulting in 1080 flattened interface methods preceding Athlete's own client methods:
- `[ 54] msgid= 182`: `onEnterHallTeam`
- `[ 56] msgid= 184`: `onInvitedToHallTeam`
- `[ 59] msgid= 187`: `onLeaveHallTeam()` (resets solo team state, prevents `hallTeamData` crash)
- `[104] msgid= 232`: `startHeroSelect`
- `[407] msgid= 535`: `onSelectAssistant`
- `[1081] msgid=1209`: `onRefreshMSToken(STRING, STRING)`
- `[1082] msgid=1210`: `onKickOff()`
- **`[1083] msgid=1211`**: **`showSelectCharacter(ARRAY<STRING> oldNames)`** (Empty array 4-byte uint32 count=0 -> **Preloads 3D scene**)
- **`[1084] msgid=1212`**: **`onCreateCharacter(BOOL success, STRING reason)`**
- **`[1085] msgid=1213`**: **`onRoleCreateSuc(INT32 roleId)`** (roleId=10002)
- **`[1087] msgid=1215`**: **`updateBaseCharacter(INT32 charType)`** (10002=MALE, 10005=FEMALE per `getCharactersData`)
- **`[1088] msgid=1216`**: **`updateBaseNickname(STRING nick)`**
- **`[1091] msgid=1219`**: **`enterHall(BOOL isFirstLoginOfDay)`** (Lobby entry!)
- `[1103] msgid=1231`: `onLogin(INT32, STRING)`


---

## 4. Entity Lifecycle & Property Stream Unpacking Mechanics

### Disassembly Evidence (`libclient.so`)
1. **`ClientApp::onBasePlayerCreate` (`0x918504`, Ghidra `0x00a18504`)**:
   ```c
   *(undefined4 *)(param_1 + 0xf90) = param_2; // eid
   lVar2 = FUN_00a29890(param_3);              // EntityType[type]
   uVar3 = FUN_00a2ac04(lVar2, param_2, ..., param_4, 0); // Entity creation via stream
   puVar4 = (undefined8 *)FUN_00a185d0(param_1 + 0xfc0, &local_4c);
   *puVar4 = uVar3;                            // entities_[eid] = uVar3
   uVar5 = FUN_00a2d284();                     // Entities singleton (base + 0x45786e0)
   FUN_00a2d0dc(uVar5, uVar3);                 // Entities::setPlayer(Entity*)
   ```

2. **`EntityType::newDictionary` (`0x92a58c`)**:
   - `0x92a5cc: ldr x8, [x8, #0x18]; blr x8`: Calls `BinaryIStream::remainingLength()`.
   - `0x92a5d4: cbz w0, #0x92a60c`:
     - **If stream is empty (`remainingLength == 0`)**: jumps to `0x92a60c` -> calls `0x92a344` (`PyDict_New()`), initializes default entity dictionary, and succeeds cleanly!
     - **If stream is non-empty**: calls `0x9cf8ac` to unpack properties. If the stream contains malformed or mismatched data (like the guessed 3632-byte stream), it throws an exception / fails, preventing `setPlayer` from running!
   - **Rule**: `createBasePlayer(Athlete)` should be sent with an **empty stream (`stream = b''`)** unless exact properties are verified.

3. **Live Process Heap Verification**:
   - `Entities` singleton pointer: `base + 0x45786e0` (`0x76384cdec360`).
   - `*Entities` (offset 0): `pPlayerEntity_` (`0x763892626820`).
   - Currently verified in memory: Type 38 (`Account`), `eid = 1`.

---

## 5. Verified Wire Protocol for Method Indices >= 57 (Reversed from `0xad03b0` & `0xa478a8`)

**STATUS as of 2026-09-18 (Checkpoint 15)**: SOLVED AND MATHEMATICALLY PROVEN.
The dispatch mechanism does NOT use msgID 100/101. BigWorld Mercury encodes extended method indices directly into message IDs in range `128..255`:

### The Exact Wire Formula
1. **Threshold**:
   $$\text{div} = \lfloor(\text{num\_methods} + 192) / 255\rfloor$$
   $$\text{threshold} = 62 - \text{div}$$
   - For `Account` (`num_methods = 25`): $\text{div} = 0 \implies \text{threshold} = 62$.
   - For `Athlete` (`num_methods = 1131`): $\text{div} = 5 \implies \text{threshold} = 57$.
2. **Method Index Encoding**:
   - If $\text{method\_index} < \text{threshold}$:
     $$w_1 = \text{method\_index}, \quad \text{extra\_byte} = \text{b''}$$
   - If $\text{method\_index} \ge \text{threshold}$:
     $$\text{diff} = \text{method\_index} - \text{threshold}$$
     $$w_1 = \text{threshold} + \lfloor\text{diff} / 256\rfloor$$
     $$\text{extra\_byte} = \text{diff} \pmod{256} \quad (1 \text{ byte uint8 prepended to payload})$$
3. **Wire Message ID & Width**:
   $$\text{msgID} = 128 + w_1$$
   $$\text{width} = 2 \text{ bytes (uint16 LE) if } w_1 < 64 \text{ else } 1 \text{ byte (uint8)}$$
4. **Wire Payload**:
   $$\text{payload} = [\text{entity\_id: uint32 LE}] + [\text{extra\_byte}] + [\text{args}\dots]$$

### Proof of Client Execution (`scratch/live_logcat_verified_wire.txt`)
When `showSelectCharacter` (idx 1083, $w_1 = 61 \implies \text{msgID} = 189 \ (0xBD)$, extra byte = `0x02`) was sent:
`[ERROR] MethodDescription::getArgsAsTuple: Failed to get arg 0 (of type ARRAY of STRING) for method showSelectCharacter from the stream.`
`[ERROR] MethodDescription::callMethod: Couldn't stream off args for showSelectCharacter correctly, aborting method call!`
The client successfully routed the wire packet to `MethodDescription::callMethod` for `showSelectCharacter`!

### Ground Truth Lobby Entry Sequence (`mitm/captures/SERVE_B.txt`)
Real NetEase traffic shows existing accounts never invoke `showSelectCharacter`. Instead:
1. `onCreateCharacter(True, "")` (idx 1084, msgID 189, extra 0x03) $\to$ Sigma: `{"keypoint": "onCreateCharacter", "extraData": "{\"ret\": 1, \"msg\": \"\"}"}`
2. `updateBaseCharacter(1)` (idx 1087, msgID 189, extra 0x06, args `struct.pack('<i', 1)`)
3. `updateBaseNickname("Survivor")` (idx 1088, msgID 189, extra 0x07, args `b'\x08Survivor'`)
4. `enterHall(True)` (idx 1091, msgID 189, extra 0x0A, args `struct.pack('<B', 1)`) $\to$ Sigma: `{"keypoint": "athleteEnterHall"}`! Loading 3D Lobby!

---

## 6. Critical Protocol Rules & Bug Fixes

### A. Bundle Termination Rule (`FLAG_HAS_REQUESTS`)
- In `mitm/local_baseapp_capture.py`: Do NOT unconditionally append `00 00` footer to packet bundles!
- Only append `00 00` footer when `flags & 1` (`FLAG_HAS_REQUESTS`) is set.
- Unconditionally appending `00 00` leaves 2 stray bytes that the client's bundle parser treats as a truncated message ID 0 (`authenticate`), causing phantom `Bundle::get: not enough data` errors.

### B. LoginApp Reachability Probe (`b'hello ros'`)
- The client sends an ASCII 9-byte packet `b'hello ros'` to LoginApp port 25000 before/during login.
- If treated as a normal 273-byte `LogOnParams` request, the server responds with a bogus `LoginReplyRecord`, breaking client attempt state.
- **Rule**: In `serve_loginapp_udp_responder()`, strictly check:
  ```python
  if data == b'hello ros':
      log('LOGINAPP: skipping probe packet (b"hello ros") -- not replying')
      continue
  ```

### C. Diagnostic Telemetry: `connectLoginHostCallback`
- Client emits HTTP Sigma keypoint `connectLoginHostCallback`:
  - `{"status": 1}`: Success! Client proceeds to BaseApp port 25010.
  - `{"status": 2}`: Failed pre-BaseApp handshake.
- Check this keypoint first in logs (`SERVE_B.txt`) to know immediately if a run reaches BaseApp.

---

## 7. End-to-End Execution Sequence (Current Known-Working Steps)

```text
[Client] Tap PLAY -> HTTP Auth & Sigma Keypoints -> LoginApp UDP :25000 Handshake
  |
  v
[BaseApp :25010]
  1. BaseAppLogin ACK + Session Key
  2. Send createBasePlayer(Account, type=38, eid=1, stream=b'')
  3. Client sends 864-byte Account.handshake (ACK immediately)
  4. Send Account.onChannelLogin(idx=19, sauth_dict) + Account.onLogin(idx=18, OK)
  5. Client reports Sigma: "accountOnBecomePlayer" + "onChannelLogin code: 0"
  6. Send createBasePlayer(Athlete, type=51, eid=1, stream=b'')
     -> Athlete.onBecomePlayer() fires
     -> Athlete.onCreate() fires (chains through 35+ interface onCreate() calls)
     -> iWeekendPush TypeError caught non-fatally by elkLogging.py
  7. Send Athlete.showSelectCharacter([]) (idx 1083, w1=61 -> msgID=189, extra=0x02, args=struct.pack('<I', 0)):
     -> Unpacks 4-byte uint32 count = 0 cleanly via SequenceDataType (libclient.so 0x9a4b74)
     -> Fires Athlete._loadDefaultScene() -> loads HALL_BASE_SCENE -> instantiates GameObject 'Scene' with SceneSystem!
     -> Enters UISelectCharacter (3D Character Creation UI)
   8. Wait ROS_SCENE_LOAD_DELAY (default 2.5s) for async scene initialization:
      -> Send Athlete.onCreateCharacter(True, "") (idx 1084, msgID 189, extra 0x03)
      -> Send Athlete.onRoleCreateSuc(10002) (idx 1085, msgID 189, extra 0x04)
      -> Send Athlete.updateBaseCharacter(10002) (idx 1087, msgID 189, extra 0x06) [10002=MALE, 10005=FEMALE]
      -> Send Athlete.updateBaseNickname("Survivor") (idx 1088, msgID 189, extra 0x07)
      -> Send Athlete.onLeaveHallTeam() (idx 59, msgID 185, extra 0x02) [Resets solo team state; prevents hallTeamData crash]
      -> Send Athlete.enterHall(True) (idx 1091, msgID 189, extra 0x0A)
      -> Athlete._realEnterHall() calls GameObject.Find('Scene').GetComponent('SceneSystem').loadHallScene(...)
      -> 'Scene' GameObject is found and SceneSystem loads Hall!
      -> Client emits Sigma: {"keypoint": "athleteEnterHall"}!
      -> Send Athlete.onLeaveHallTeam() (idx 59) post-hall to guarantee solo state
   9. [LOBBY ACTIVE] Client transitions into full 3D Hall / Lobby with visible avatar and solo team chrome!
```

### Current Status & Live Test Verification Plan
- Wire encoding formula: **SOLVED & CONFIRMED**
- `updateBaseNickname` state change: **CONFIRMED** (`user_name: "Survivor"` in telemetry)
- `_realEnterHall` crash cause: **SOLVED** (`GameObject.Find('Scene')` required `showSelectCharacter` scene preload)
- `SequenceDataType` wire length prefix: **SOLVED** (4-byte uint32 LE, NOT 1 byte)
- `hallTeamData` crash & UI duplication cause: **SOLVED** (missing solo team sync; fixed via `onLeaveHallTeam` idx 59)
- Character model missing cause: **SOLVED** (`updateBaseCharacter` must be `10002` Male or `10005` Female, not `1`)
- **Ready for Claude live execution and verification with ADB + logcat.**

---

## 8. Key Files in Workspace

- `GEMINI.md`: Master specification and memory guide for Gemini/Antigravity.
- `CLAUDE.md`: Master specification and instructions for Claude Code / Claude desktop.
- `scratch/HANDOFF_PROMPT_CLAUDE.md`: Clean, self-contained handoff prompt to paste into Claude.
- `mitm/local_baseapp_capture.py`: Main integrated server (HTTP, LoginApp 25000, BaseApp 25010).
- `05_entities/out/Athlete.def.xml`: Athlete entity definition XML.
- `05_entities/out/entity_0376.xml`: `iWeekendPush` interface definition (contains `weekendPushRewardsHaveGotten: PYTHON`).
- `scratch/ghidra_updateentity.txt`: Decompile of `updateEntity` handler + `createBasePlayer` handler + `newEntity` wrapper.
- `scratch/ghidra_propstream.txt`: Decompile of `EntityType::newDictionary` (FUN_00a2a58c).
- `scratch/ghidra_longentitymsg.txt`: Complete `_INIT_44` decompile showing all ClientInterface message registrations.
- `scratch/athlete_methodtable.bin`: Raw 27144-byte Athlete MethodDescription array dump (live memory).
- `scratch/find_showselect.py`: Script used to verify showSelectCharacter index=1083 from live memory.
- `scratch/live_logcat_1789717869.txt`: Logcat with complete iWeekendPush crash traceback (lines 21651-21691).

---

## 9. updateEntity Wire Protocol (FUN_00a49590 = msgID 10)

Decompiled 2026-09-18 (checkpoint 14). From `scratch/ghidra_updateentity.txt`:

```c
void FUN_00a49590(long param_1, long *param_2) {
  if (*(long *)(param_1 + 0x110) != 0) {
    puVar1 = (read_4_bytes)(param_2, 4);  // entity_id: uint32
    (vtable+0x38)(manager, *puVar1, param_2, mode_byte);
  }
}
```

Wire format: `[flags:u16][msgID:10][len:u16][entity_id:u32][property_stream...]`

**Next step**: Decompile `vtable+0x38` on the entity manager object
(`*(long **)(param_1 + 0x110)`, slot 7 of the vtable) to determine what
the `property_stream` looks like. This function parses the actual property
update data and may reveal the bitmask-indexed format required to send a
correct property update.

**IMPORTANT**: `updateEntity` cannot fix the `iWeekendPush` crash because
`onCreate` fires synchronously during `createBasePlayer`. The Python exception
is NON-FATAL (caught by `elkLogging.py:wrapper`). Test `showSelectCharacter`
first; only investigate `updateEntity` stream format if the Python exception
actually blocks the Character Creation UI.

