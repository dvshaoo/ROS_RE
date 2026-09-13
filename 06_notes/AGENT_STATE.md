# Agent State

## Gates
- **G1**: PASS (Local Session Contract independently validated & live-exchanged without onFailure)
- **G2**: INVESTIGATION (BigWorld loginapp connection dependency mapped to 10.0.2.2:25000)

## Current Gate
G2 (Game Session / BaseApp Connection)

## Current Task
G2.1 — Establish minimal BigWorld Mercury loginapp handshake responder on port 25000.

## Completed
- G0 Patch gate live-cleared (T15 plist 482B + resident `patchVersion` = `1.0.0.en`).
- Server list served (`server_list_ad.txt` directing to `10.0.2.2:25000`).
- Complete static trace of `onFailure(1000)`, `has_minor`, `j/d/d.c`, `e/b/c`, and `loginDone`.
- Scanned all three DEX files (`classes.dex`, `classes2.dex`, `classes3.dex`) and indexed in `DEX_INDEX.md`.
- Documented full findings in `06_notes/LOGIN_FLOW_TRACE.md`.
- Backed up repository and pushed to GitHub (`https://github.com/dvshaoo/ROS_RE`).
- Validated Local Session Contract for `/api/users/login/v2/sdk_token` (documented in `06_notes/LOCAL_SESSION_CONTRACT.md`).
- Live-tested contract: client successfully consumed `/api/users/login/v2/sdk_token` without hitting `onFailure(1000)`.
- Mapped G2 connection dependency (`neox::bwclient::ServerConnection::logOnBegin` -> `10.0.2.2:25000`) in `06_notes/G2_GAME_SESSION_TRACE.md`.

## Known Evidence
- `02_dex/classes.dex`: code `0x3d34bc` parses top-level `"user_id"` and `"sdk_token"` from `login/v2/sdk_token`.
- `02_dex/classes.dex`: code `0x400826` and `0x400868` compare `minor_status == 102` to bypass age prompt and invoke `onLoginSuccess` via `0x40039c`.
- `02_dex/classes.dex`: code `0x3cc624` (`e/a/f.a`) checks `age_status == 1` to execute `0x3ccb42` (`iput-boolean false, g/d::h` clearing `has_minor`).
- `libclient.so`: `neox::bwclient::ServerConnection::logOnBegin` connects to `10.0.2.2:25000` for `loginapp` using `entities/loginapp.pubkey`.

## Files Changed
- `mitm/mitm_serve.py` (updated routes for `sdk_token` top-level keys, `minor_status=102`, `age_status=1`)
- `06_notes/LOCAL_SESSION_CONTRACT.md`
- `06_notes/G2_GAME_SESSION_TRACE.md`
- `06_notes/AGENT_STATE.md`
- `PROGRESS.md`

## Last Test
Live execution on `emulator-5554` with MITM server.

## Last Result
G1 Contract PASS — Token exchange completed cleanly. LVU dismissal transition mapped to Dalvik bytecode `0x400868` (`minor_status=102`) and `0x3ccb42` (`has_minor=false`).

## Next Exact Action
Extract `entities/loginapp.pubkey` or native RSA parameters from `libclient.so` and prepare port 25000 listener for Mercury handshake.

## Do Not Repeat
- Do not rescan `classes2.dex` or `classes3.dex` for NetEase MPay auth (confirmed absent).
- Do not search for `onFailure(1000)` origin again (proven at `0x3ffc2a`).
- Do not use `>` in PowerShell for binary stdout redirection (produces corrupted UTF-16LE).
- Always use `-s emulator-5554` with `adb` commands.

