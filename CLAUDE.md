# CLAUDE.md — Rules of Survival (ROS) Mobile RE & Private Server Guide

> **Project**: Rules of Survival Mobile Private Server Emulation (Game Preservation)  
> **Client**: Android APK `com.netease.chiji`, v1.610377.506841, vCode 1117219, arm64-v8a  
> **Target Environment**: LDPlayer 9 (`emulator-5554`, Android guest `172.16.1.15`, Gateway host `172.16.1.2`)  
> **ADB Path**: `C:\LDPlayer\LDPlayer9\adb.exe`  
> **Primary Script**: `mitm/local_baseapp_capture.py`  
> **Last Updated**: 2026-09-25 (Checkpoint 21: "Invalid login" MPay Popup Auto-Dismissed, Root Cause of Prior Bad Fix Reverted)

---

## 0. Environment Setup After Every LDPlayer Restart (READ THIS FIRST if traffic isn't reaching the server)

LDPlayer wipes both of the following on every VM reboot/restart. If you see "Failed to retrieve
patches", "Slow connection", or the game stuck on a blank screen right after a restart, run
**`scratch/reapply_env_setup.sh`** before debugging anything else:
1. iptables DNAT (tcp 80/443/8443, udp 25000/20013 -> `172.16.1.2`) — without this, no traffic
   reaches `mitm_serve.py`/`local_baseapp_capture.py` at all.
2. `srv.crt` installed as a system-trusted CA (tmpfs overlay on `/system/etc/security/cacerts/`)
   — without this, any subsystem using standard Android TLS validation (the `mpay_oversea` login
   SDK, bundled 3rd-party SDKs) rejects our self-signed cert with a `certificate_unknown` TLS
   alert. The game's own NeoX HTTP client trusts everything unconditionally, so most traffic
   works even without this — but mpay's login/config-fetch calls don't, which is what causes the
   "Slow connection" dialog and a broken age-gate response (2026-09-25, see
   `06_notes/GATE7_BATTLE_GAMEPLAY_PLAN.md`).

After running the script, restart `local_baseapp_capture.py`, `adb shell pm clear com.netease.chiji`
(fresh app state after a cert change), then force-stop + relaunch the game.

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
| **Gate 4** | Character Select / Lobby | Mercury RPC / DEF | **PASS (Lobby renders)** | **2026-09-20: the real 3D Lobby renders** (START, Ranked, Invite 0/0, currency bar, side menu) using the runtime-DataType-driven Athlete stream (`python scratch/gen_stream_v3.py`). The hall UI is **non-deterministic**: some runs show the avatar model and a clean solo state, others show duplicated overlapping promo boxes, a stray "Leave Team" and no avatar until the Ranked page is visited. Open: `extconfigs.getServiceAccessPoint` TypeError in `onBecomePlayer`. |

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
- `[  59] msgid= 187`: `onLeaveHallTeam()` **(does NOT prevent the `hallTeamData` crash — retracted; see below)**
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

## 7. Checkpoint 18: Definitive Root Cause of the Two Missing Attributes & Teardown

See detailed breakdown in [HANDOFF_TO_CLAUDE_WEEKENDPUSH_LOBBY.md](file:///c:/Users/Raysoo/Downloads/ROS_RE/scratch/HANDOFF_TO_CLAUDE_WEEKENDPUSH_LOBBY.md).

### The Root Cause:
1. `iHallTeam.onCreate()` line 45 sets `self.hallTeamData = {}`.
2. `Athlete.onCreate()` line 365 sets `self.timerRefreshMSToken = None`.
3. Both methods are chained via `safesuper(Class, self).onCreate()` over 143 interfaces.
4. In `entities\iWeekendPush.py:14`, `onCreate` calls `tryActiveWeekendPushRedBadge()`.
5. At line 66, it does `set(rewardsCanGet) - set(self.weekendPushRewardsHaveGotten)`.
6. Because `weekendPushRewardsHaveGotten` has `<Flags> BASE_AND_CLIENT </Flags>` and NO default in `entity_0376.xml`, sending an empty stream in `createBasePlayer(Athlete)` initializes it as `None`.
7. `set(None)` raises `TypeError: 'NoneType' object is not iterable` (verified in `live_logcat_charcreate_test.txt:153421`).
8. This unhandled `TypeError` **aborts the unwinding of the entire `onCreate()` chain**!
9. Consequently:
   - `self.hallTeamData = {}` never runs $\to$ `AttributeError: hallTeamData` in `UIModes.on_enter`.
   - `self.timerRefreshMSToken = None` never runs $\to$ `AttributeError: timerRefreshMSToken` in `onBecomeNonPlayer`.
   - `onBecomeNonPlayer` crash causes `setPlayer::new player is null` $\to$ `App CMD 31` (Quit) $\to$ `Level Destroy (-1)`.

### Resolution Strategy:
Neutralize `TypeError` in `tryActiveWeekendPushRedBadge` or supply default in `createBasePlayer` property stream.
Once `onCreate()` finishes cleanly, `hallTeamData` and `timerRefreshMSToken` exist automatically, allowing the client to transition past the "Please select controls" screen (`hall_entry_t12s.png`) into the interactive 3D Lobby!


---

## 8. Checkpoint 20 (2026-09-20): property-stream ground truth (supersedes anything older that conflicts)

- **`createBasePlayer(Athlete)` property stream is real and parsed sequentially** (`EntityType::newDictionary` ->
  `FUN_00acf8ac`, flag mask `0x0b`): a bare ordered concatenation of the 454 properties passing
  `(f&0x10)==0 && (f&0x08) && (f&0x06)`. No bitmask, no index tags. (The old "domain=0 + non-empty stream =
  exception" claim was wrong.)
- **Fixed-size arrays have NO count on the wire.** `SequenceDataType::createFromStream` (`FUN_00aa4b14`) reads the
  4-byte count only when the DataType's fixed size (`+0x30`) is 0. `childBaseClientPropertyList` and
  `childClientPropertyList2` are `ARRAY <of> FIXED_DICT ... <size> 1 </size>`: the element (a large FIXED_DICT)
  is written inline with no count. Encoding them as "count 0" desyncs the whole stream from ordinal 207.
  The generator must be built from the **runtime** DataType tree, not XML regexes (`scratch/dump_runtime_types.py`).
- **One Mercury packet carries at most ~1459 B of `createBasePlayer` stream.** Larger messages must be fragmented
  (`send_mercury_message` in `mitm/local_baseapp_capture.py`); an oversize single datagram is dropped by the
  client with `EncryptionFilter::recv: Dropping packet ... illegal wastage count`, which looks like "the entity
  layer went silent" and logs only ONE `createBasePlayer` instead of two.
- **Session-key scan:** `fast_find_session_key()` must scan every heap region >= 2 MB (was > 16 MB, which skipped the
  10 MB region holding the EncryptionFilter on some launches). Load base and heap layout change every launch.
- **Use ONE adb binary** (LDPlayer 34.0.4 vs SDK 37.0.1 fight over the adb server); start the server with `ADB_PATH`.
- **Do not trust "no error" as "in sync".** Verify alignment with a specific client error whose numbers match a
  known stream offset (see `06_notes/GHIDRA_PACKET_PARSER_TRACE.md`, Checkpoint 20).

- **Milestone (2026-09-20):** with the v3 stream the client consumes all 2178 B exactly (no DataType errors, no "still N bytes left"), `Athlete.onBecomePlayer` runs, and the real Lobby renders (`scratch/lobby_avatar_2026-09-20.png`). The old `hallTeamData` / `timerRefreshMSToken` / `hostID` / `baseLevel` AttributeErrors are gone. `gen_stream_v2.py` output is desynced at ordinal 207 -- do not use it.
- **RETRACTED (2026-09-20): "declared XML defaults make the Lobby clean".** Six no-interaction runs of the same 2178 B layout: `min` messy, `xml` clean, A messy, B clean, B1 messy, B2 messy -- and an exact replicate of B came out **messy**. The identical stream gave both outcomes, so the clean/messy hall state is NOT determined by the property values (likely timing or a UI refresh; the user reports it becomes clean after visiting the Ranked page). See `06_notes/GHIDRA_PACKET_PARSER_TRACE.md`, Checkpoint 20d.

- **Checkpoint 20j (2026-09-20): hall UI root cause found.** `UIMain.on_enter` aborted on two BASE-only attributes (`personalRecommendState`, `monthPayRebateSpecialAwardInfo`); the server now sends `onPersonalRecommendStateUpdated` (idx 754) and `syncMonthPayRebateSpecialAwardInfo` (idx 768) after Stage 4. Result: 0 script errors on fresh login, real top bar (diamond = freeYuanbao+payYuanbao; coin slot = `currencyList` id 213), correct timers, no stacked labels. Dev balance 999999/999999 via `scratch/gen_stream_v3.py`. Full method-name table: `scratch/dump_athlete_methods.py`. Client scripts can be decrypted/searched with `tools/script_index.py|script_query.py|script_disas.py` (disassembly opcodes unreliable; names lists are fine). Details and open items: `06_notes/GHIDRA_PACKET_PARSER_TRACE.md` 20j.
