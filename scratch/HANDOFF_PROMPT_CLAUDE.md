# Handoff Prompt for Claude Code

Please review and execute the next steps for the Rules of Survival (ROS) Private Server Emulation:

### Read Master Specification & Handoff Docs First:
1. Master guide: [`GEMINI.md`](file:///c:/Users/Raysoo/Downloads/ROS_RE/GEMINI.md)
2. Comprehensive Checkpoint & RTTI Analysis: [`scratch/HANDOFF_TO_CLAUDE_2026-09-20.md`](file:///c:/Users/Raysoo/Downloads/ROS_RE/scratch/HANDOFF_TO_CLAUDE_2026-09-20.md)
3. Latest walkthrough artifact: [`walkthrough.md`](file:///C:/Users/Raysoo/.gemini/antigravity-ide/brain/7edfae7c-bf95-4fcc-8553-20b135423f8b/walkthrough.md)

### Current Status Summary:
- **Gates 0–3**: 100% PASS (Patch bypass, Sigma/UniSDK auth, LoginApp :25000 Blowfish encryption, BaseApp :25010 reliable channels).
- **Gate 4 Scene & Wire**: 100% PASS (`showSelectCharacter` 3D scene preload fixed, Mercury extended wire formula verified, character creation & lobby methods verified).
- **Gate 4 Property Stream**: **95% Complete**.
  - All 13 DataType vtables demangled 100% via ELF RTTI parsing directly from `libclient.so`.
  - Properties 0..300 verified byte-perfect in live tests (`weekendPushRewardsHaveGotten` at ord 258 delivered as `[]`, eliminating the `iWeekendPush` crash).
  - Target for this session: Finalize ordinals 301..306 collection defaults in `scratch/gen_stream_v2.py`, generate `data/athlete_mobile_stream.bin`, and verify full lobby entry with character model!

### Immediate Action to Run:
```bash
# 1. Update scratch/gen_stream_v2.py and generate stream
python scratch/gen_stream_v2.py

# 2. Tap PLAY on LDPlayer (emulator-5554)
adb -s emulator-5554 logcat -c
adb -s emulator-5554 shell input tap 960 740

# 3. Check live logcat and screenshot
adb -s emulator-5554 logcat -d > scratch/live_logcat_latest.txt
adb -s emulator-5554 shell screencap -p /sdcard/screen.png
adb -s emulator-5554 pull /sdcard/screen.png scratch/current_screen.png
```
