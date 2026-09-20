# Gate 5 plan — START button -> in-game island (no match timer, no plane)

User goal (2026-09-20): pressing START must enter real gameplay; for testing the player should just stand on the island,
with no countdown timer and no plane/airdrop. Status: RESEARCH ONLY — nothing below is implemented or live-verified yet
unless marked VERIFIED. Follow CLAUDE.md rules (zero guesswork; live test + notes + commit).

## What the client does on START (from decrypted scripts; use tools/script_query.py / script_disas.py)
- VERIFIED (script constants/def XML): UIMain calls the base method `matchBattleGround` on the hall player.
  Def (entity_0335 / entity_0574, Athlete side): `matchBattleGround(BOOL)` `<Exposed/>`; `cancelMatchBattleGround()` `<Exposed/>`.
  (entity_0354 is the BaseApp-internal variant with GID + GLOBAL_MAIL_BOX_INFO args.) The client therefore sends an
  exposed base-method message to our BaseApp on START; the server must answer.
- Client hall callbacks the server can drive (iHallTeam client methods, entity_0335 ClientMethods): `syncMatchState`, `syncReadyState`,
  `syncMatchingProgress`, `onUpdateMatchTargetTime`, `onGetMatchedTeamInfo`, `onMatchedPlayerInfoChange`, `syncBattleState(gid, inWorld)`.
- VERIFIED (Athlete.def.xml:860): the hand-off to the battle is `Athlete.transferToBattleServer(STRING ip, INT32 port,
  KEY_NAME playerName, BLOB password, UINT32 backPort)`. Script `entities/Athlete.py transferToBattleServer(self, ip, port,
  playerName, password, backPort)` uses `ConnectMonitor.getInstance().setLoginHostBackPort` and `setBattleHostInfo`, then
  `uiMgr.enter_ui(...)`. So the client does NOT stay on our BaseApp: it opens a NEW connection to a battle host (ip:port) and logs
  in there with `playerName`/`password`, where the entity types are `BattleAccount` (39) then `Avatar` (40) in a `BattleGroundSpace`.

## Consequences / work breakdown
1. Capture and decode the START upstream message (log it in `local_baseapp_capture.py`; msg id from the Athlete exposed-method table).
2. Reply with the hall-side state RPCs (e.g. syncMatchState / syncMatchingProgress) — must be verified against the client scripts
   so the UI does not stay in a matching spinner; the runtime method indices must be derived like idx 873 (anchors in the runtime
   table) — do NOT guess.
3. Send `transferToBattleServer(ip, port, name, password, backPort)` pointing at a second listener on our host
   (a second LoginApp+BaseApp pair, same Mercury/Blowfish handling as Gates 2-3, but entity BattleAccount).
4. Battle-side handshake: `createBasePlayer(BattleAccount)` (needs its own runtime DataType-driven property stream, same tooling as
   `scratch/dump_runtime_types.py` / `gen_stream_v3.py` but for type 39), then the in-space Avatar (cell entity, type 40) creation,
   space/geometry/weather data, and whatever the client needs to leave the loading screen on the island.
5. Island only: no matchmaking timer, no plane, no airdrop — the space must be the waiting island (`BattleGroundSpace` variant);
   find which client methods start the countdown / plane and simply never send them.
6. Exit path: back-to-hall must work (see HALL_NAVIGATION_CHECKLIST.md) — otherwise the tester gets stuck after each test.

## Open unknowns (must be answered from the client, not guessed)
- The exposed-method wire id of `matchBattleGround` and how the server should ack it.
- What the client needs from the Avatar entity property stream and cell-entity/space messages (largest unknown; cell entities were not
  implemented in Gates 3-4).
- Whether KEY_NAME/BLOB password are validated client-side or only echoed to the battle host.
- Whether battle host connections require the same encryption key derivation (currently obtained by scanning client memory as root,
  which will not work for non-rooted testers — see the note on non-root LAN tests).

## Suggested first slice (small, verifiable)
Log the START message and dump what the client does on a bare `syncMatchState` reply; then implement (3)+(4) for BattleAccount only
and check the client reaches the BattleAccount login without a crash, before touching Avatar/space.
