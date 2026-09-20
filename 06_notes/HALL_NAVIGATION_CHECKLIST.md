# Hall Lobby Navigation Checklist (live-tested on LDPlayer, private server)

Method per route: tap the entry, screenshot, `adb logcat -d` for `SCRIPT ERROR` tracebacks, then leave the page with the
in-page X and with Android Back (`input keyevent 4`), screenshot again. Record: opens? / renders data? / can exit? / error.
Screen is landscape 1920x1080 in tap coordinates (`wm size` reports the native 1080x1920). Evidence goes in `scratch/nav_*.png`.

## PRIORITY 0 — character not shown after login until the Ranked page is visited
- Symptom: right after login the hall shows duplicate overlapping promo boxes, stray "Leave Team", NO avatar.
  Visiting Rank (or the Weapon/Depot page) makes the avatar appear and the hall clean (user report + t0/t2 shots of run T_series).
- Status: OPEN. Not caused by property default values (see notes 20d). Hypothesis: the hall UI is built before some
  state exists; navigating forces a re-display. Investigation log below.

## Findings so far
| Route | Opens | Exit | Error |
|---|---|---|---|
| Depot -> Review popup | yes (placeholder Chinese text, no data) | X tap ignored; Android Back crashes | `UIDtsAppearanceMainController.on_leave -> UIMain.displayAll -> UIMain.showRedPoint` (UIMain.py:2453) `TypeError: 'NoneType' object is not iterable` -> leave aborted, user stuck |

## To test (tick when done)
Left menu: [ ] Store  [ ] Supply  [ ] Manual  [ ] Platoon  [ ] Depot  [ ] Lucky Club  [ ] NEW! tag
Top bar: [ ] avatar/profile  [ ] Share  [ ] each currency "+"  [ ] Leave Team  [ ] Invite  [ ] Settings/mail (if any)
Right: [ ] Daily Special Offer  [ ] Activity  [ ] Super Carnival  [ ] Monthly Offer  [ ] Racing  [ ] Ranked selector  [ ] friends "1 Ghillie"
Bottom: [ ] START  [ ] chat/voice icons  [ ] team icons
For each: does Back/X return to the hall? which traceback?

## Investigation log (PRIORITY 0)
- 2026-09-20: the ONLY script traceback during a fresh login (probe_T_series_logcat.txt:12471) is
  `Athlete.onBecomePlayer` (Athlete.py:275) -> `extconfigs.getServiceAccessPoint` (extconfigs.py:50)
  `TypeError: 'NoneType' object has no attribute '__getitem__'`, raised right after the voice AudioEngine starts.
  An uncaught exception aborts the REST of `onBecomePlayer`, so whatever it does after line 275 (possibly avatar/hall
  model refresh) never runs. Navigating to Rank/Depot re-runs the UI display path, which would explain "avatar
  appears after visiting Rank". UNVERIFIED: no script source available (script.npk is encrypted), so the code after
  line 275 is unknown. Next: find what `extconfigs` line 50 indexes (a config dict from the server's nstool/
  internalquery reply?) and give it a valid value, then live-test whether the avatar shows without navigating.
- Depot exit bug (see table) is a second, separate `NoneType is not iterable` in `UIMain.showRedPoint` (UIMain.py:2453):
  some red-point property/list is still None; candidates are the Athlete properties the stream fills with `N.`
  for PYTHON types. To identify: log which Athlete PYTHON property is read at UIMain.py:2453.
