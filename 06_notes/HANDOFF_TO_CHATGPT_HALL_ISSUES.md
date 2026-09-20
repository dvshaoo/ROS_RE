# Handoff to ChatGPT — Hall Lobby issues (2026-09-20)

Written for: an engineer/agent continuing the ROS (com.netease.chiji) LAN private-server work with no prior context.
Read `CLAUDE.md` first (standing rules: local/LAN only, zero guesswork — verify by live memory or Ghidra, commit often,
update the .md notes with every code change + live test). Detailed history: `06_notes/GHIDRA_PACKET_PARSER_TRACE.md`
(Checkpoints 20, 20b, 20d, 20e). Route checklist: `06_notes/HALL_NAVIGATION_CHECKLIST.md`.

## Current state (what works)
- Gates 0-3 pass. Gate 4: the real 3D Lobby renders (START, Ranked, Invite 0/0, currency bar, side menu).
- `createBasePlayer(Athlete)` property stream is real and sequential: 454 of 832 properties, bare ordered
  concatenation, generated from the LIVE runtime DataType tree by `scratch/gen_stream_v3.py` -> `data/athlete_mobile_stream.bin`
  (2178 B, consumed exactly by the client). Fixed-size arrays carry NO count. Packets > ~1459 B are fragmented.
- Stage-4 RPC order (keep intact): showSelectCharacter([]) -> wait Scene -> onCreateCharacter(True,"") ->
  onRoleCreateSuc(10002) -> updateBaseCharacter(10002) -> updateBaseNickname("Survivor") -> enterHall(True).

## Open issue 1 (PRIORITY): avatar missing after login until Rank/Depot is visited
- Right after login: duplicated overlapping promo boxes, stray "Leave Team", NO avatar. After the user navigates to
  Ranked (or Depot/Weapon page) the avatar appears and the hall is clean. Same stream sometimes gives a clean hall
  (replicate test failed) -> NOT caused by property default values (notes 20d, retracted claim).
- A no-interaction time series (notes 20e) was contaminated by the user touching the emulator; still unknown whether
  the hall self-heals with no input.
- Lead (UNVERIFIED): the only script traceback during a fresh login is
  `entities\Athlete.py:275 onBecomePlayer -> extconfigs.py:50 getServiceAccessPoint`
  `TypeError: 'NoneType' object has no attribute '__getitem__'` (logcat: scratch/probe_T_series_logcat.txt:12471,
  right after the voice AudioEngine starts). An uncaught exception aborts the rest of `onBecomePlayer`, so later
  init (maybe avatar/hall refresh) is skipped; navigating re-runs the UI display path. Script source is unavailable
  (script.npk encrypted), so what follows line 275 is unknown.
- Suggested next steps: (a) find what extconfigs line 50 indexes (a config filled from the nstool/internalquery HTTP
  reply? the server already answers internalquery with 200 — check the body shape); (b) supply a valid value and
  live-test whether the avatar shows with zero interaction; (c) repeat the time-series with hands off.

## Open issue 2: cannot leave the Depot page
- Depot opens a REVIEW popup with placeholder Chinese text ("这里是评价内容一共三行"), no data. Its X tap is ignored.
- Android Back (`input keyevent 4`) crashes: `UIDtsAppearanceMainController.on_leave -> UIMain.displayAll ->
  UIMain.showRedPoint (UIMain.py:2453)` `TypeError: 'NoneType' object is not iterable` -> leave aborted, user stuck.
- Some red-point list/property is still None. Candidates: Athlete PYTHON properties encoded as `N.` (None) in the
  stream. Identify which property line 2453 reads, then give it a real default (`[]` / `{}`).

## Open issue 3: full route scan not done
- Checklist of every button/route (Store, Supply, Manual, Platoon, Depot, Lucky Club, profile, Share, currency "+",
  Leave Team, Invite, offers, Racing, Ranked, friends, START, chat/voice) is in HALL_NAVIGATION_CHECKLIST.md, none ticked
  yet except Depot. Per route record: opens? renders data? exits with X and Back? traceback?

## Other known open items
- `fast_find_session_key()` in `mitm/local_baseapp_capture.py` still reads memory via `adb exec-out` (LF->CRLF
  corruption risk); use base64 via `adb shell` like `scratch/dump_runtime_types.py`.
- Semantic correctness of `xml` default values is unverified (only sizes/consumption are).
- Dynamic instrumentation is blocked: Frida and lldb-server fail at ptrace register access on this emulator. Use
  `/proc/<pid>/mem` reads + Ghidra.

## Practical how-to
- Server: `ROS_ATHLETE_USE_STREAM_FILE=1`, `ADB_PATH=<SDK adb>`, `python -u mitm\local_baseapp_capture.py`.
- One-command probe: `python scratch/lobby_probe.py <label> [names|MIN]` (env `PROBE_DELAYS="70,60,60"` for timed shots).
- Use ONE adb binary (LDPlayer's and the SDK's restart each other's server). Git-Bash needs `MSYS_NO_PATHCONV=1` for
  `adb push/pull`. Don't `adb reboot` (loses su); restart LDPlayer from the desktop, then reapply the 5 iptables DNAT
  rules (tcp 80/443/8443, udp 25000/20013 -> 172.16.1.2). Tap coordinates are landscape 1920x1080.
- Uncommitted on purpose: `mitm/mitm_serve.py`, `mitm/captures/SERVE_B.txt` (Gemini's unreviewed changes).
- Lesson: one A/B pair is not evidence — replicate before claiming a cause.
