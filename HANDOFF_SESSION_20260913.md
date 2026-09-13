# HANDOFF — Session 2026-09-13 (OpenCode → AntiGravity)

## TL;DR (3 lines)
1. **G0 PATCH CLEARED** ✅ — plist serving works, no forcePatch, game boots to UniSDK login.
2. **LVU (age/consent panels) BLOCKED** — Birthday submitted, email page shows, but **NeoX engine intercepts ALL touch input** — ADB `input tap`, `sendevent`, keyboard TAB, `swipe` — NONE work on MpayActivity buttons. Game is force-stopped + ADB was restarted.
3. **Root access available** (`su 0`) — this is the key to bypassing LVU without clicking buttons.

---

## What Works
| Component | Status | Proof |
|-----------|--------|-------|
| Patch plist serving (`/pl/npk_version_na_android.plist`) | ✅ PASS | 482-byte T15 plist served, no forcePatch, boot continues |
| Server list (`server_list_ad.txt`) | ✅ PASS | 114 bytes served, `requestServerList` keypoint success |
| Guest login (`/api/users/login/guest`) | ✅ PASS | `code:0` with user object, `channelLogin` keypoint |
| Minors configs (`/api/minors/configs`) | ✅ PASS | Returns `country_codes:[["US","United States"]]` |
| Minors birthday (`/api/minors/update_birthday`) | ✅ PASS | Returns `(1,1)` → routes to email page |
| Minors email (`/api/minors/update_email`) | ✅ PASS | Returns `(2,1)` (adult terminal) — but Confirm button can't be clicked |
| whoami (`/v1`) | ✅ PASS | Signed payload with US geo |
| Fake loginapp | ❌ NOT YET | Need `loginapp.pubkey` + protocol RE |

## What's Blocked

### BLOCKER: NeoX Touch Interception
- The NeoX game engine renders on a SurfaceView that sits **ABOVE** the Android view hierarchy
- All touch events (tap, swipe, sendevent) are consumed by the NeoX engine before reaching MpayActivity buttons
- `input text` works because it uses the IME path (bypasses NeoX)
- uiautomator CAN see the buttons and their coordinates, but taps don't reach them
- **This means we CANNOT click any button in the age/consent dialogs via ADB**

### BLOCKER: LVU Terminal Enum Unknown
- `minor_status` values: 0=query/loop, 1=loop, 2=loop, 3=loop, ≥5=alert/fail
- After birthday 01-1990 (adult) → `update_birthday` returns `(1,1)` → email page
- `update_email` with `(2,1)` = terminal (adult), but button can't be clicked
- The EXACT terminal enum for `update_birthday`/`update_email` responses that COMPLETE the LVU flow is unknown

### BLOCKED-008: Original Reference
- No original screenshots/video of login → LVU → hall flow exists
- Cannot verify parity without reference

---

## ROOT ACCESS AVAILABLE
```bash
# Confirmed:
adb -s emulator-5554 shell "su 0 id"  → uid=0(root)
# Can read/write all app data:
adb -s emulator-5554 shell "su 0 ls /data/data/com.netease.chiji/shared_prefs/"
```

### SharedPreferences Files (all under `/data/data/com.netease.chiji/shared_prefs/`):
- `com.netease.mpay.202cb962ac59075b964b07152d234b70.xml` — main mpay config (ENCRYPTED blobs: sdk_config, dev, data, account)
- `com.netease.mpay.extra.202cb962ac59075b964b07152d234b70.xml` — has `host` with serialized Java HashMap
- `29d7ab0bddc6556885f1bce2c21ab5fe123.xml` — guest user data
- `com.netease.chiji_preferences.xml` — Facebook SDK data
- `neox_config.xml` — NeoX engine config

### LVU Driver Chain (from DEX disassembly):
- `j/d/d.c` method (0x3e0554): Gate is `isFirstLogin==true AND has_minor==true` → triggers LVU
- `has_minor` (`g/d.h`) defaults to `false` in constructor
- `j/d/d.c` SETS `has_minor=true` when `j/d/d.h` (String field, likely user token) is empty
- After `pm clear` → user token empty → `has_minor=true` → LVU triggers

---

## Proposed Next Steps (for AntiGravity)

### Strategy A: Bypass LVU via SharedPreferences (ROOT)
With root, we can potentially:
1. Write a SharedPreferences value that marks LVU as "completed"
2. OR populate the user token field so `has_minor` stays `false`
3. Problem: main SP data is encrypted Java serialization — may not be directly editable

### Strategy B: Skip LVU by Closing MpayActivity (ROOT)
1. Launch game, wait for MpayActivity to appear
2. Use `su 0 am force-stop com.netease.chiji` — but this kills entire game
3. BETTER: Use `su 0 am finish-activity <token>` to close ONLY the MpayActivity
4. Or: Use `su 0 input` with different source to bypass NeoX touch interception

### Strategy C: Modify Game Memory at Runtime (ROOT)
1. Use `su 0` + `gdb`/`ptrace` to modify `has_minor` boolean in running process
2. Or use `su 0` to inject a SharedPreferences write while game is running

### Strategy D: Figure Out LVU Terminal Values
1. Disassemble `e/b/c` state machine at 0x3cc968 (packed-switch keys 2-5)
2. Find which `minor_status` value makes the state machine "complete" and dismiss LVU
3. Then the problem becomes: how to click Confirm → same touch interception issue

### Strategy E: Modify MITM to Prevent LVU Trigger
1. The gate in `j/d/d.c` checks if user token String is empty
2. If we populate a token in the guest login response that gets stored in `j/d/d.h`, LVU won't trigger
3. Need to find what field in login response populates `j/d/d.h`

---

## Files Modified This Session
| File | Change |
|------|--------|
| `mitm/mitm_serve.py` | `update_email` returns `minor_status:2, age_status:1` (adult terminal) |
| `mitm/mitm_serve.py` | `minors/configs` returns `country_codes:[["US","United States"]]` |

## Screenshots This Session
| File | Description |
|------|-------------|
| `06_notes/shot_runH1.png` | Email page with "test@example.com" entered |
| `06_notes/shot_runH2.png` | Confirmation dialog: "Please confirm test@example.com" |
| `06_notes/shot_runH3.png` | Same confirmation dialog (tap missed) |
| `06_notes/shot_runH4.png` | Same (tap missed again) |
| `06_notes/shot_runH5.png` | Same (swipe tap failed) |
| `06_notes/shot_runH6.png` | TAB focused message text (yellow outline) |
| `06_notes/shot_runH7.png` | Same (TAB+ENTER failed) |
| `06_notes/shot_runH8.png` | Same (swipe failed) |
| `06_notes/shot_sendevent1.png` | Same (sendevent failed) |
| `06_notes/shot_kill1.png` | LDPlayer home after force-stop |
| `06_notes/shot_back1.png` | Same confirmation dialog (BACK failed) |

---

## Environment
- **ADB**: `C:\Users\Raysoo\AppData\Local\Android\Sdk\platform-tools\adb.exe`
- **Emulator**: `emulator-5554` (LDPlayer)
- **Python**: `C:\Python314\python.exe`
- **MITM server**: `C:\Users\Raysoo\Downloads\ROS_RE\mitm\mitm_serve.py`
- **DNAT**: port 80→8080 (iptables), adb reverse 8080→8080 + 8443→8443
- **Game PID**: was killed, ADB restarted
- **Root**: ✅ available via `su 0`

## Current State
- Game is **force-stopped** (killed to escape stuck confirmation dialog)
- ADB server was **restarted** (clean state)
- iptables DNAT for port 80 **still active**, adb reverse forwards **still active**
- MITM server needs restart (was killed with game)
- **Game needs relaunch** to continue testing
