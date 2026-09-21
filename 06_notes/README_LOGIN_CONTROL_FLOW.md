# ROS LAN Server — Expected Login / Control-Selection Flow

Attach or quote this file whenever another AI continues work on this project.

## Current behavior: one control-selection screen only

This private LAN server intentionally skips the original interactive character-creation and nickname-entry flow. The server automatically creates/loads the role and uses the nickname:

`Dev | Raysoo`

The original client still has to initialize its character scene and first-time control UI, so a fresh device/profile follows this sequence:

1. Tap **PLAY** on the title screen.
2. A loading screen appears.
3. **Please select controls** appears. Keep **Classic Mode** selected and wait until the yellow **Confirm** button is enabled, then tap it.
4. A loading screen appears.
5. The client enters the hall/lobby automatically as **Dev | Raysoo**.

In short:

`PLAY -> Loading -> Select Controls -> Confirm -> Loading -> Lobby`

The control-selection choice is persisted by the client. Subsequent fresh launches should go straight to the lobby after loading.

### Fix verified 2026-09-21

The Athlete creation stream previously left `baseNickname` empty and only populated it later with
`updateBaseNickname`. `Athlete.onBecomePlayer` therefore observed a blank profile and the client could
enter a second bootstrap/reconnect path after the first controls confirmation. The runtime-typed stream
now contains the persisted nickname (`Dev | Raysoo`) at property ordinal 8, before `onBecomePlayer`.

A controlled fresh launch produced one BaseApp session, one Select Controls page, then the lobby/login
popup; it did not create a second BaseApp session or return to Select Controls. The Stage-4 RPC order was
not changed.

## When it is a real bug

Treat the flow as broken only when one of these occurs:

- Select Controls appears a second time after it has already been confirmed.
- The client remains on a loading screen and never reaches the lobby.
- The lobby appears with leftover **Support Droid / Human** character-selection controls.
- The top bar falls back to repeated placeholder values such as `283283` instead of the configured coin/diamond balances.
- The character is missing, has the wrong gender/outfit, or `SCRIPT ERROR` appears in logcat.

If any of those happen, capture the full `SCRIPT ERROR` traceback and inspect the saved stream/player state. Do not assume the two-pass control-selection flow is the root cause.

## Stage-4 protocol order — do not change

Keep this verified order intact:

1. `showSelectCharacter([])`
2. `onCreateCharacter(...)`
3. `onRoleCreateSuc(...)`
4. `updateBaseCharacter(...)`
5. `updateBaseNickname("Dev | Raysoo")`
6. `enterHall(...)`

`showSelectCharacter([])` is still required even though the user no longer types a name. It initializes the client-side 3D scene before the automatic role-creation response chain completes.

## Test guidance for future AIs

- Do not tap the Confirm button before its countdown/disabled state has finished.
- Treat a return to Select Controls after confirmation as a regression and capture the server timeline and logcat.
- A valid fresh-login test ends only after checking the final lobby screenshot and counting `SCRIPT ERROR` entries in logcat.
- Do not claim the hall is fixed from an already-running session. Force-stopping and relaunching the game (without rebooting LDPlayer) is required to validate the saved state.
- Do not remove the automatic nickname or re-enable manual name entry unless the user explicitly asks for that feature again.

## Repository checkpoint warning (verified 2026-09-21)

The actual Git commit `b0e06ca` contains only `.gitignore` and `mitm/captures/SERVE_B.txt` changes on top of `7b87a54`. It does **not** contain the claimed 6.9 KB player stream or the full gender/equip implementation. At the time this note was written, `data/athlete_mobile_stream.bin` was 2,659 bytes and `data/player_state.json` was absent after the reset recorded in the reflog.

Therefore, do not rely on the earlier “Done” summary alone. Verify the current files with `git show --stat b0e06ca`, `git status`, file sizes, and a fresh emulator login before making any claim about the checkpoint.
