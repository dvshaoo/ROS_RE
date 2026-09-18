# GEMINI.md — Rules of Survival (ROS) Private Server Emulation & RE Master Guide

> **Author**: Gemini / Antigravity Agent  
> **Last Updated**: 2026-09-18 (Major Milestone: Athlete Method Vector & Entity Table Solved)  
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
| **Gate 4** | Character Select / Lobby | Mercury RPC / DEF | **IN PROGRESS (SOLVED INDICES)** | Pinned exact `Athlete` method indices directly from process memory: `showSelectCharacter` is index **1083** (msgID 1211); `onCreateCharacter` is index **1084**; `enterHall` is index **1091**. Ready for extended msgID / `longEntityMessage` wire dispatch. |

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
- `[104] msgid= 232`: `startHeroSelect`
- `[407] msgid= 535`: `onSelectAssistant`
- `[1081] msgid=1209`: `onRefreshMSToken(STRING, STRING)`
- `[1082] msgid=1210`: `onKickOff()`
- **`[1083] msgid=1211`**: **`showSelectCharacter(ARRAY<STRING> oldNames)`** (Empty array `0x00` -> **Drives Character Creation UI**)
- **`[1084] msgid=1212`**: **`onCreateCharacter(BOOL success, STRING reason)`**
- **`[1085] msgid=1213`**: **`onRoleCreateSuc(INT32 roleId)`**
- **`[1087] msgid=1215`**: **`updateBaseCharacter(INT32 charType)`**
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

## 5. Wire Protocol for Method Indices > 63

In BigWorld Mercury:
- Method index `0..63`: Wire `msgID = 128 + index` (128..191, `longEntityMessage`, length prefix = `uint16`).
- Method index `64..127`: Wire `msgID = 128 + index` (192..255, `shortEntityMessage`, length prefix = `uint8`).
- Method index `>= 128` (like `showSelectCharacter` = index 1083):
  - In `ClientInterface`:
    - `msgID 100`: `shortEntityMessage` (1-byte length prefix)
    - `msgID 101`: `longEntityMessage` (2-byte length prefix)
  - Envelope for `longEntityMessage` (`msgID 101`):
    ```python
    # Format: [msgID: 101][len: u16][entity_id: u32][method_index: u16][args...]
    payload = struct.pack('<I', entity_id) + struct.pack('<H', method_index) + args
    packet = struct.pack('<H', flags) + bytes([101]) + struct.pack('<H', len(payload)) + payload
    ```
  - Also sweep extended `msgID` framing if `msgID = (128 + index) & 0xff` is used by the client parser.

---

## 6. End-to-End Execution Sequence for Claude

To transition client from title screen into Character Creation:

```text
[Client] Tap PLAY -> HTTP Auth & Sigma Keypoints -> LoginApp UDP :25000 Handshake
  |
  v
[BaseApp :25010]
  1. BaseAppLogin ACK + Session Key (`be5194d3` for PID 23776)
  2. Send createBasePlayer(Account, type=38, eid=1, stream=b'')
  3. Client sends 864-byte Account.handshake (ACK immediately)
  4. Send Account.onChannelLogin(idx=19, sauth_dict) + Account.onLogin(idx=18, OK)
  5. Client reports Sigma: "accountOnBecomePlayer" + "onChannelLogin code: 0"
  6. Send createBasePlayer(Athlete, type=51, eid=1 or 2, stream=b'')
  7. Send Athlete.showSelectCharacter([]) using method index 1083:
     - Candidate A: msgID 101 (longEntityMessage) with method_index=1083
     - Candidate B: msgID (128 + 1083) & 0xff = 0xBB (187) with width 2
  8. Client UI transitions from title screen into Character Creation UI!
```

---

## 7. Key Files in Workspace

- `mitm/local_baseapp_capture.py`: Main integrated server (HTTP, LoginApp 25000, BaseApp 25010).
- `scratch/HANDOFF_PROMPT_CLAUDE.md`: Quick-start prompt for Claude sessions.
- `05_entities/out/entities.xml`: Entity definition XMLs.
- `05_entities/out/Athlete.def.xml`: Athlete entity definition XML.
- `05_entities/out/Account.def.xml`: Account entity definition XML.
