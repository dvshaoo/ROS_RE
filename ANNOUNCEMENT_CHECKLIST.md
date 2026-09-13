# ROS New Gen — Mobile Update Checklist (v1117219)

> One gate at a time. A gate is DONE only when the client visibly passes it —
> "no crash" is not done. Values are per-version (vCode 1117219).

## GATE 1 — Patch check (IN PROGRESS)
- [x] Capture exact request (`GET /pl/npk_version_na_android.plist`)
- [x] MITM trust working (TLS intercepts, game talks to us)
- [x] Rule out 5 formats (XML/G4-text/manifest/bplist/empty — all 41006)
- [ ] Crack G4 patchlist schema (T11 script.npk decrypt running)
- [ ] Serve valid "no update" → dialog gone, client advances

## GATE 2 — Telemetry + update (MAPPED)
- [x] drpf POST shape captured (obb_state 0→5→6→100, full JSON)
- [x] update-check URLs captured (`latest_v*.json`)
- [ ] Serve success responses → no blocking dialogs

## GATE 3 — Guest auth (MAPPED)
- [x] Endpoints captured (`/api/users/login/guest` + migrate flows)
- [ ] Serve guest token → auth completes

## GATE 4 — Server list (QUEUED)
- [x] Proven: URL is runtime-set (0 static hits) → needs live capture
- [ ] Capture list response → serve our row → UI shows server

## GATE 5 — BigWorld login (MAPPED)
- [x] `logOnBegin(server,user,pass,?,port)` signature + runtime host
- [x] RSA pubkey flow (`loginapp.pubkey`, LogOnParams encrypt)
- [ ] Fake loginapp accepts → baseapp dial

## GATE 6 — Entities / create character (DECRYPT RUNNING)
- [x] entities.npk decrypted (400+ defs: Account, LoginProxy verified)
- [ ] Athlete.def (in script.npk — T11)
- [ ] Type-ID table (runtime or script.npk — T11)
- [ ] `showSelectCharacter` RPC → create screen

## GATE 7 — Lobby (QUEUED)
- [ ] `enterHall` RPC → hall loads → rank/character visible

## Principles
Backend first. One change, one test. Cite source:line or it didn't happen.
