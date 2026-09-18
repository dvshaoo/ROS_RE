# Handoff to Claude: Lobby UI Polish, Character Model Fix, and Exhaustive Lobby Navigation Audit

> **From**: Gemini / Antigravity Agent  
> **To**: Claude Code / Claude Desktop  
> **Date**: 2026-09-18  
> **Project**: Rules of Survival (ROS) Private Server Emulation (`com.netease.chiji`, v1.610377.506841, arm64-v8a)  
> **Target Device**: LDPlayer 9 (`emulator-5554`, Android guest `172.16.1.15`, Gateway host `172.16.1.2`)  
> **Scope**: Root-cause resolution for (1) Duplicated/overlapping promo UI, (2) Missing avatar character model, and (3) Full Lobby UI audit and unblocking.

---

## 1. Executive Summary & Root Cause Breakdown (Zero-Guesswork Evidence)

You confirmed in Gate 4 that the 3D Lobby scene loaded successfully via `showSelectCharacter` + `enterHall`. During that run, three issues remained:
1. Duplicated/overlapping "team promo" boxes ("Haven't Paid", 20% extra gold, "小小白因拉", "Leave Team", "0/0").
2. No visible character/avatar model on the terrace.
3. Lobby UI buttons (Settings, Start/Matchmaking, mode selection) missing or unresponsive.

**We investigated all three issues with hard evidence and pinpointed their single shared root cause.**

### Issue 1: Duplicated/Overlapping Promo Boxes ("Haven't Paid", 20% Gold Bonus)
- **Hard Evidence from Logcat (`live_logcat_scenefix_1789735992.txt:70170-70185`)**:
  ```python
  09-18 21:17:50.679 11778 11886 I [21:17:50.679] M <SCRIPT> : File "ui\UIMgr.py", line 967, in enterHallUI
  09-18 21:17:50.679 11778 11886 I [21:17:50.679] M <SCRIPT> : File "ui\UIMain.py", line 1265, in on_enter
  09-18 21:17:50.679 11778 11886 I [21:17:50.679] M <SCRIPT> : File "ui\main\UIModes.py", line 405, in on_enter
  09-18 21:17:50.679 11778 11886 I [21:17:50.679] M <SCRIPT> : File "ui\main\UIModes.py", line 627, in _refresh_members
  09-18 21:17:50.679 11778 11886 I [21:17:50.679] M <SCRIPT> : File "ui\main\UIModes.py", line 636, in _init_ui_visibilities
  09-18 21:17:50.679 11778 11886 I [21:17:50.679] M <SCRIPT> : File "ui\main\UIModes.py", line 256, in members_num
  09-18 21:17:50.679 11778 11886 I [21:17:50.679] M <SCRIPT> : File "entities\iHallTeam.py", line 744, in isInTeam
  09-18 21:17:50.679 11778 11886 I [21:17:50.679] M <SCRIPT> : AttributeError: 'PlayerAthlete' object has no attribute 'hallTeamData'
  ```
- **Why this produces the duplicate UI**:
  - `entity_0335.xml:43` defines `hallTeamData` with `<Flags> BASE </Flags>`. In BigWorld Mercury, BASE properties only exist on the server; they are NEVER initialized in the client's dictionary at entity creation.
  - When `UIMain.on_enter` invoked `UIModes.on_enter` at line 1265, `UIModes._refresh_members` threw `AttributeError: 'PlayerAthlete' object has no attribute 'hallTeamData'`.
  - This exception **aborted `UIMain.on_enter` immediately**!
  - `MainScene.csb` (the Cocos Studio layout) has 5 default template member slots: `member-0` through `member-4` under `anchor-center/`. Each has `visible=True` by default with template strings ("小小白因拉", "Haven't Paid ", "Grants 20% extra gold in any mode...").
  - Because `UIMain.on_enter` crashed before `_init_ui_widgets` and `_refresh_members` could execute `member-{}.setVisible(False)`, **all 5 member slots remained visible simultaneously**, drawing on top of each other!
- **The Fix**:
  - `Athlete` implements `iHallTeam` client methods (`05_entities/out/entity_0335.xml:525-554`):
    - `[ 59] onLeaveHallTeam()` (0 args).
  - Invoking `onLeaveHallTeam()` before/after `enterHall` sets client team state to solo (`hallTeamData = {}`, `isInFormedTeam = False`).
  - Wire encoding for `onLeaveHallTeam` (idx 59, `num_methods = 1131`):
    - `threshold = 57`, `diff = 59 - 57 = 2`, `w1 = 57`, `extra_byte = b'\x02'`, `msgid = 128 + 57 = 185 (0xB9)`.
    - Payload = `[eid: uint32 LE] + b'\x02'` (5 bytes).

### Issue 2: Missing Character/Avatar Model on the Terrace
- **Hard Evidence from Disassembly & Properties Table**:
  - In `UIMain.py:234` `_display_self`:
    The client calls `legacyProperties.getCharactersData(player.getCharacterType())`.
  - Our server was sending `Athlete.updateBaseCharacter(1)` (idx 1087).
  - Ground truth from `probe_character_data.py:32-34` and `cc_stub_player.py:1020, 1147`:
    - `CHAR_TYPES = [10002, 10005, 10001]`
    - `10002` = MALE (`character/dataosha_male/male.gim`, dress parts `[1101, 2101, 4101, 5101]`).
    - `10005` = FEMALE (`character/dataosha_female/female.gim`).
    - `1` is NOT a valid character type! `getCharactersData(1)` returns `None`.
    - When `getCharactersData(1)` returns `None`, `dts_show_model_path` is empty/None, so `scene.createDressModelAsync` aborts.
  - Also: `Athlete.onRoleCreateSuc(10002)` (idx 1085, `struct.pack('<i', 10002)`) confirms role creation.
- **The Fix**:
  - Update `updateBaseCharacter` to send `10002` (`struct.pack('<i', 10002)`).
  - Send `onRoleCreateSuc(10002)` (idx 1085).

### Issue 3: Exhaustive Lobby UI Navigation & Rendering Audit
- **Start / Matchmaking Button (`anchor-bottom-right/go`)**:
  - Managed by `UIModes`.
  - Was completely blocked because `UIModes.on_enter` aborted on the `hallTeamData` exception!
  - Unblocking `UIModes.on_enter` via `onLeaveHallTeam()` initializes the Start button and mode selector (`solo`, `dual`, `squad`, `fireteam`).
- **Currency Counters ("283283")**:
  - `MainScene.csb` hardcodes "283283" as default text in the CSB node. Real currency values are set via `player.onCurrencyChanged` or `setCurrencyWithOwned`.
- **Top Bar & Side Menu Navigation Catalog**:
  - Profile: `anchor-upper-left/profile` $\to$ `UIMeetMainPage`
  - Settings: `anchor-upper-right/top-navigator/setting` $\to$ `UISettingForPC` / `UISettings`
  - Store: `anchor-middle-left/entry/mall` $\to$ `UIMallController`
  - Appearance / Depot: `anchor-middle-left/entry/change_clothes` $\to$ `UIDtsAppearanceMainController`
  - Activities / Events: `anchor-middle-left/entry/activities` $\to$ `UIDtsActivity`
  - Welfare: `anchor-upper-right/common-entry/welfare` $\to$ `UIWelfareController`
  - Friends: `anchor-middle-left/entry/friend` $\to$ `UIFriendship`
  - Rank: `anchor-middle-left/entry/rank` $\to$ `UIRankList` / `UINationalRank`
  - All of these buttons had their event bindings suppressed because `UIMain.on_enter` halted before reaching line 1500+.

---

## 2. Server Implementation Applied (`mitm/local_baseapp_capture.py`)

Stage 4 in `mitm/local_baseapp_capture.py` has been updated with the fix candidates:

```python
# 1. Athlete.onCreateCharacter(True, "") (idx 1084)
occ_args = struct.pack('<B', 1) + _packed_int(0)
send_entity_method(sock, addr, use_key, athlete_eid, 1084, occ_args, flags=0x0008, num_methods=1131)

# 2. Athlete.onRoleCreateSuc(10002) (idx 1085)
char_type = int(os.environ.get('ROS_BASE_CHAR_TYPE', '10002'))
orcs_args = struct.pack('<i', char_type)
send_entity_method(sock, addr, use_key, athlete_eid, 1085, orcs_args, flags=0x0008, num_methods=1131)

# 3. Athlete.updateBaseCharacter(10002) (idx 1087)
ubc_args = struct.pack('<i', char_type)
send_entity_method(sock, addr, use_key, athlete_eid, 1087, ubc_args, flags=0x0008, num_methods=1131)

# 4. Athlete.updateBaseNickname("Survivor") (idx 1088)
nick = b"Survivor"
ubn_args = _packed_int(len(nick)) + nick
send_entity_method(sock, addr, use_key, athlete_eid, 1088, ubn_args, flags=0x0008, num_methods=1131)

# 5. Athlete.onLeaveHallTeam() (idx 59) -> Pre-hall solo team state
send_entity_method(sock, addr, use_key, athlete_eid, 59, b'', flags=0x0008, num_methods=1131)

# 6. Athlete.enterHall(True) (idx 1091)
eh_args = struct.pack('<B', 1)
send_entity_method(sock, addr, use_key, athlete_eid, 1091, eh_args, flags=0x0008, num_methods=1131)

# 7. Athlete.onLeaveHallTeam() (idx 59) -> Post-hall solo team reassert
send_entity_method(sock, addr, use_key, athlete_eid, 59, b'', flags=0x0008, num_methods=1131)
```

---

## 3. Step-by-Step Live Test Instructions for Claude

### Step A: Start Server
```powershell
python mitm/local_baseapp_capture.py
```

### Step B: Launch Logcat & Client in LDPlayer
```powershell
C:\LDPlayer\LDPlayer9\adb.exe logcat -c
C:\LDPlayer\LDPlayer9\adb.exe logcat > scratch/live_logcat_lobby_audit.txt 2>&1 &
C:\LDPlayer\LDPlayer9\adb.exe shell am force-stop com.netease.chiji
C:\LDPlayer\LDPlayer9\adb.exe shell monkey -p com.netease.chiji 1
```

### Step C: Tap PLAY and Observe
1. Tap PLAY on title screen (`adb shell input tap 640 600`).
2. Server will execute:
   - `showSelectCharacter([])` (idx 1083) -> wait 2.5s for 3D scene preload.
   - `onCreateCharacter(True, "")` (idx 1084).
   - `onRoleCreateSuc(10002)` (idx 1085).
   - `updateBaseCharacter(10002)` (idx 1087).
   - `updateBaseNickname("Survivor")` (idx 1088).
   - `onLeaveHallTeam()` (idx 59).
   - `enterHall(True)` (idx 1091).
   - `onLeaveHallTeam()` (idx 59, post-hall).

### Step D: Verification Criteria
1. **Logcat Check**:
   Search `scratch/live_logcat_lobby_audit.txt` for `hallTeamData`:
   Verify that `AttributeError: 'PlayerAthlete' object has no attribute 'hallTeamData'` is GONE!
2. **Avatar Check**:
   Take a screenshot (`adb shell screencap -p /sdcard/screen.png && adb pull /sdcard/screen.png scratch/LOBBY_POLISH_SCREEN.png`).
   Check if the male avatar model (`male.gim`) is rendered on the terrace standing next to the bike.
3. **Team Promo Check**:
   Verify whether the duplicate overlapping "Haven't Paid" / 20% bonus boxes disappeared or collapsed into a single solo card.
4. **UI Navigation Sweep**:
   Test taps on:
   - Start / Matchmaking button (`anchor-bottom-right/go`).
   - Mode select button.
   - Settings icon (`anchor-upper-right/top-navigator/setting`).
   - Store / Mall (`anchor-middle-left/entry/mall`).
   - Depot / Clothes (`anchor-middle-left/entry/change_clothes`).
   - Profile (`anchor-upper-left/profile`).
