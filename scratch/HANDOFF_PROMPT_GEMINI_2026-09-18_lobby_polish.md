# Handoff prompt for Gemini/Antigravity — Lobby UI duplication + missing character model

> **Project**: Rules of Survival Mobile Private Server Emulation (Game Preservation)
> **Workspace**: `C:\Users\Raysoo\Downloads\ROS_RE`
> **Client**: `com.netease.chiji`, v1.610377.506841, vCode 1117219, arm64-v8a
> **This file**: written by Claude after independently live-testing your scene-preload fix (`c0e8a09`). It worked — the 3D Lobby is reached and confirmed via the `athleteEnterHall` telemetry keypoint and a screenshot. Two new, narrower issues found during that same test. Read this before doing anything else.

---

## Standing rules (do not violate)

- Local/LAN only. Never touch real NetEase servers.
- Zero guesswork: every packet format, entity type, property, and method index must be verified by live memory inspection, Ghidra decompilation, or a captured log line — not assumed.
- Commit frequently with descriptive messages.
- Read `06_notes/GHIDRA_PACKET_PARSER_TRACE.md` in full before doing anything — especially the "GATE 4 CLEARED" section at the very end, and the section right before it about the retest of Candidate A (unrelated, but shows the project's evidence bar).

## Confirmed working — do not touch

- The threshold-based extended wire-index encoding formula (`div`/`threshold`/`w1`/`extra_byte`) — proven live via `onCreateCharacter`'s `{"ret": 1}` telemetry.
- The `showSelectCharacter([])` 4-byte `ARRAY<STRING>` count-prefix fix, and the 2.5s `ROS_SCENE_LOAD_DELAY` before continuing.
- The `onCreateCharacter` → `updateBaseCharacter` → `updateBaseNickname` → `enterHall` sequence — confirmed via `athleteEnterHall` telemetry AND a screenshot showing the actual 3D Lobby (STORE/SUPPLY/MANUAL/PLATOON/DEPOT menu, currency counters, rendered environment).

## Also confirmed this session — a design fact, not a bug: there is no interactive Character Creation UI in this client

The user asked why the player never got to type a nickname or pick a character. Claude tested this directly: disabled the auto-follow-up RPCs (`ROS_AUTO_ENTER_HALL=0`) so the server sends only `showSelectCharacter([])` and then stops, holding the connection open. Waited ~25 seconds with logcat capturing and repeated screenshots. **Result: the client never showed any UI beyond the title screen.** The only script activity was:
```
Type <class 'libclaudia.Classes.SceneSystem.Scene'> should be initialized immediately after creation.
...
GetAllSubObj set([<Scene (GameObject) at 0x...>])
```
i.e. `showSelectCharacter` → `_loadDefaultScene()` only instantiates the 3D `Scene` GameObject in the background — it does not, by itself, present any name-entry or appearance-selection screen. **Do not go looking for a missing "character creation form" RPC or UI trigger — there is real live evidence there isn't one in this flow.** The real production flow evidently auto-creates the character server-side (hence `onCreateCharacter`/`updateBaseCharacter`/`updateBaseNickname` all being server→client pushes, not responses to a client request) and lets the player rename/customize later from within the Lobby. If you find concrete evidence this assumption is wrong (e.g. a client→server request message this project isn't sending, captured in `mitm/captures/SERVE_B.txt` or found via Ghidra), that would override this, but don't assume it without such evidence.

## New issue 1: duplicated/overlapping promotional UI in the Lobby

The Lobby screenshot from this session's test shows multiple copies of the same UI elements overlapping each other:
- The "All team members receive additional 20%" promo box appears **4-5 times**, stacked/overlapping at different screen positions.
- "Haven't Paid" labels appear multiple times.
- "GAMING" tags and player name tags appear duplicated (e.g. "小小白因拉" tag appears several times).

**Hypothesis to investigate (not confirmed)**: this is likely a **team/platoon promotional feature**, not core entity-creation logic — possibly related to the `Athlete` method table entries this session already found via live memory (e.g. things like `onEnterHallTeam`, `onInvitedToHallTeam`, `addHallTeamMember`, `syncHallTeamMatchingRandom` — all real method names confirmed present in the live `MethodDescription` array, documented in `06_notes/GHIDRA_PACKET_PARSER_TRACE.md`'s "MAJOR CORRECTION" section). This project's server has never sent any team-related pushes at all, so any team UI showing up must be the client's own default/cached state, possibly stale from repeated test sessions reusing app data.

**What to check**:
1. Whether `adb shell pm clear com.netease.chiji` (full app data wipe, not just force-stop) before a test run changes this — Claude's last test wiped app data and the duplication still appeared, so this alone likely isn't the fix, but confirm/refute this properly rather than assuming.
2. Whether there's a specific property or RPC (client-side default state vs. something this server should be actively pushing/suppressing) that controls whether this promo UI shows once vs. repeatedly. Check `entities.xml`/`entity_*.xml` for anything team/platoon/promo-related with an XML `<Default>` that might not be getting applied correctly (same class of issue as the earlier `weekendPushRewardsHaveGotten` bug — check whether this is another missing-default symptom).
3. Whether this is purely a **client rendering issue** unrelated to protocol correctness at all (e.g. a UI widget that's supposed to cycle/rotate through promo messages but is instead rendering all of them simultaneously because some "how many to show" or "carousel" state is uninitialized) — in which case it may not be fixable from the server side at all, and should be documented as a known cosmetic limitation rather than chased indefinitely.

## New issue 2: no visible character/avatar model in the Lobby

The Lobby screenshot shows the environment (bike, crates, mountains) and UI chrome, but no rendered player character model. `updateBaseCharacter(1)` (idx 1087) is currently sent with just an `INT32` value of `1` and nothing else — no appearance/skin/gender data.

**What to check**:
1. `Athlete.def.xml` / the interface .xml files already extracted in `05_entities/out/` for what `updateBaseCharacter`'s single `INT32 charType` argument actually selects (a preset character type/gender enum?) and whether `charType=1` is even a valid value, or whether appearance requires additional properties/RPCs this project isn't sending yet (e.g. something in the `dtsWearableAppearanceList`/`dtsBodyAppearanceList`-style fields Claude's earlier live memory dump saw referenced in a nearby FIXED_DICT structure for hall team members — see the `addHallTeamMember` entry in the "MAJOR CORRECTION" section's method table dump for the exact field list of a related structure, which may hint at what Athlete's own equivalent fields look like).
2. Whether there's a specific property-push (not a method call) needed to give the character a visible model — reuse the live-memory-scanning technique (walk `EntityType[51]`'s structure, this time looking at its *properties* list rather than its *methods* list, if such a properties array can be located the same way the `MethodDescription` array was found) to check what `Athlete`'s appearance-related properties actually are and what a sensible non-empty value looks like.
3. Cross-check `mitm/captures/SERVE_B.txt` for what a real server sends around character creation that might set appearance data — this project has used that capture as ground truth for the Gate 4 sequence already, so it may contain the answer directly.

## Division of labor (same as last time)

You (Gemini) investigate and implement fix candidates for these two issues. Claude will live-test them (emulator control, logcat capture, screenshot verification) rather than each of us duplicating both halves. Commit your evidence and fix candidates with clear messages describing what you found and why you believe the fix is correct; note in the commit or in the notes file exactly what env var / sequence Claude should run to test it, if anything non-default is needed.

## Environment quick reference

- Emulator: LDPlayer, device `emulator-5554`. adb: `C:\LDPlayer\LDPlayer9\adb.exe`.
- Server: `python mitm/local_baseapp_capture.py`. Restart after any code change; force-stop + relaunch the app too.
- Capture logcat during every live test: `adb logcat -c && adb logcat > scratch/live_logcat_<label>_<timestamp>.txt &`.
- `adb shell pm clear com.netease.chiji` gives a fully fresh account/app-data state if you need to rule out stale-cache explanations (this triggers the NetEase user-agreement dialog on first launch after clearing — tap Accept — and a longer initial load).
