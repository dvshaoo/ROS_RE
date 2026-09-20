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
| Depot -> Back (2nd press) | Depot main page | Back crashes | `UIDtsAppearanceCostume.on_leave -> DtsAppearanceRightPanelPattern1.on_leave -> onHideTransformBtn`: `NoneType.refreshTransformPanel`; blank scene, stuck |

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

## Open items added 2026-09-20 (user reports)
- **Daily login popup ("LOG IN DAILY TO CLAIM GIFTS", 388 Gold marked "Claimable", TOTAL LOGINS: 0d) — the free reward cannot be claimed.**
  Appears right after the hall UI finishes building (it was never reachable before UIMain.on_enter stopped aborting). The claim is a base
  method the client calls (find it with `python tools/script_query.py ui/UIDailyLogin ""` / the sign-in UI script) and the server must reply with
  the matching client method (result + updated state), or nothing happens. Not investigated yet.
- Top-bar currency now real (diamond slot shows freeYuanbao; coin slot needs `currencyList`) — see notes 20j.
- New-player guide overlay (dimmed hall, yellow arrows on START) appears on some fresh logins.
- "RushHour" banner + tank icon (btn_airship) still visible; profile "My Page" shows `ID: 0`.

## Store (sidebar STORE) — user report 2026-09-20
- Tabs **Suggested / Packs / Looks**: nothing displayed. **Fire(arms)**: items display but a skin cannot be bought. **Top-up**: prices show "USD" — should be peso (PHP).
- Probable cause class: mall goods lists / prices are server-supplied (mall goods table sync + purchase base method + reply RPC); none implemented yet.

## New-function guide overlay blocks the hall (found 2026-09-20 while testing Store)
- On some fresh logins the hall is dimmed with yellow arrows on START; taps on STORE/other buttons are swallowed (Store did not open; it opened on
  logins where the guide was absent). Overlay = `ui\UIMainNewFunctionGuide` (`IS_FORCE_GUIDE`), driven by `dts_new_function_guide_utils.checkCanDoNewFunctionGuide`
  / `tryShowNewGuide` reading Athlete `newFunctionGuideRecord` (PYTHON, stream idx 825, currently None/default; `has_key`-style dict keyed by guide id).
  Guide ids come from `NewFunctionGuideCfgDict` (data file, not yet located). Plan: find the id list and send a record marking every guide as done
  (or the RPC that records completion: `recordNewFunctionGuide`), then re-test Store.
- Store report status: Store opens and shows 999999 gold + 999999 diamond in its own header, but the tab panel is blank (no script error, no upstream request
  seen in the server log in that login). Suggested/Packs/Looks tabs empty, Fire tab lists items but purchase does not work, top-up shows "USD".
  Next: with the guide out of the way, capture the exact upstream message on tab open / on buy and find the reply RPC via `tools/script_query.py ui/TreasureMall...`.
- Environment note: after the emulator VM was restarted the iptables NAT rules were empty; reapply the 5 DNAT rules (tcp 80/443/8443, udp 25000/20013 -> 172.16.1.2 same port).

## Store investigation, session 2026-09-20 (later)
- The forced new-function guide is a single step: tapping START clears the overlay (verified `scratch/start1.png`); after that STORE opens (`scratch/store3.png`).
- Store sidebar: SUGGESTED, PACKS, LOOKS, FIREARMS, TOP-UP (submenu), OTHERS, TOKEN MALL. Store header already shows 999999 gold + 999999 diamond.
  SUGGESTED shows only the banner ("THE SUN KNOWS EVERYTHING!" BUY 3000 diamond); the item list under it is empty. No script error.
- Client mall code (`ui\UIMall.py`): `doQueryMallGoodsFromServer`, `queryAvailableMallGoods(ByType)`, `onQueryAvailableMallGoods`, `buyMallGood`, `_showMallResult`,
  `getMallData`, `fillGoods/fillGoods2`. So the list is filled from a server reply (`onQueryAvailableMallGoods`) and purchases need a reply too.
- Server log finding: the BaseApp DOES receive and decrypt client bundles (`DECRYPTED (...)` lines; earlier greps for "UPSTREAM RECV" were the wrong pattern).
  In one Store session the distinct non-keepalive payloads were telemetry-like (strings `AppearanceRecommend`, `UIDtsAppearanceMall`, `UIMallController`,
  `MallAdvancedSupplement`, `UIAdvanceSupplyPackage`) plus a ~2.5 KB settings blob (`{0:74,1:74,...}` sent when Settings/Store settings were touched).
  No recognisable `queryAvailableMallGoods` call was seen, so the exposed-method message id of that call is still unmapped (the bundle header bytes 0x58/0x78
  hide the msg id). Next: map Athlete exposed base-method ids from the live EntityType (like the client-method table, `EntityType+0x?`), decode the bundle,
  then answer `onQueryAvailableMallGoods` (args: see entity def) with a goods list built from the client's own mall tables (`tables.MallGoods`, locate in script.npk/data).
- Reminder: prices show "USD" from the client's locale tables (`translate_properties_en`, `PayGoods`); the peso change belongs to that table/currency-symbol path, not to the property stream.
