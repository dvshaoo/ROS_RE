# G2 Game Session Trace

## Entry State

Client Title Screen (`ui/UILogin.py` in `script.npk` / `neox.Client`).
Triggered after authentication completion (`onLoginSuccess` delivering `ntOnLogin(unisdk_code=0)`), `requestServerList` (parsing `server_list_ad.txt` endpoint `10.0.2.2:25000`), and `channelLogin`.

## Connection

- **Host**: `10.0.2.2` (configured via `server_list_ad.txt` serving North_America endpoint)
- **Port**: `25000` (`loginapp` listening port)
- **Protocol**: BigWorld Mercury Network Protocol over UDP/TCP (`Mercury::Nub`, `Mercury::Channel`)

## Client Code

- **Connection Owner**: `neox::bwclient::ServerConnection`
- **First Connect Location**: `neox::bwclient::ServerConnection::logOnBegin`
- **Component**: `libclient.so` (native ARM64/x86 shared library in NeoX game engine)
- **Relevant Symbols**:
  - `neox::bwclient::ServerConnection::logOn(ServerMessageHandler*, char const*, char const*, char const*, unsigned short, ...)`
  - `neox::bwclient::ServerConnection::logOnBegin(char const*, char const*, char const*, char const*, unsigned short)`
  - `neox::bwclient::LogOnParams::addToStream(Mercury::Bundle&)`
  - `neox::bwclient::LoginHandler::onLoginReply`
  - `neox::bwclient::ServerConnection::sendBaseAppLoginHook`

## Protocol

- **Known**:
  - BigWorld Technology Mercury network engine.
  - Initial connection is directed to `loginapp` on port 25000.
  - Authentication payload (`LogOnParams`) is encrypted with an RSA public key located at asset path `entities/loginapp.pubkey`.
  - Upon successful `onLoginReply`, `loginapp` returns the winning `BaseApp` IP, port, and session encryption keys.
  - Client then establishes connection to `BaseApp` (`BaseAppLoginRequest`) for entity creation (`createBasePlayer`) and role management.
- **Unknown**:
  - Exact binary packet framing / opcode layout of the RSA-encrypted `LogOnParams` stream for this specific NetEase build (v1117219).
  - Exact contents of `entities/loginapp.pubkey` (embedded or asset-packaged).

## Handshake

1. Client initializes Mercury Nub socket: `ServerConnection::logOnBegin`.
2. Public key lookup: loads `entities/loginapp.pubkey`.
3. Encrypts login credentials: `LogOnParams::addToStream` (`publicEncrypt`).
4. Sends login bundle to `10.0.2.2:25000`.
5. Awaits `LoginHandler::handleMessage` / `LoginHandler::onLoginReply`.
6. Handles BaseApp address resolution: `LoginHandler::onLoginReply: change baseAddr from %s to %s`.

## Server Dependency

- Authoritative BigWorld `loginapp` server listening on `0.0.0.0:25000`.
- Requires matching RSA private key corresponding to the client's `loginapp.pubkey` to decrypt `LogOnParams`.
- Requires returning formatted `LoginReplyRecord` redirecting the client to a `BaseApp` service.

## Runtime Evidence

1. `server_list_ad.txt`: Space-delimited entry configured to route North_America to `10.0.2.2:25000` (live-served by `mitm/mitm_serve.py`).
2. Native strings in `libclient.so` (documented in `06_notes/NATIVE_LOGON.md`):
   - `ServerConnection::logOnBegin conneting to %s for loginAPP`
   - `entities\loginapp.pubkey`
   - `LoginHandler::onLoginReply: change baseAddr from %s to %s`
3. Port forwarding active: `adb reverse tcp:25000 tcp:25000` established on `emulator-5554`.

## Status

FOUND

Connection architecture, owner (`neox::bwclient::ServerConnection`), port (`25000`), entry method (`logOnBegin`), and handshake dependencies (`loginapp.pubkey` + Mercury Nub) are identified and mapped from native code evidence.

## Next Action

1. Resolve the remaining local persistent state blocker in G1 so `onLoginSuccess` is naturally dispatched to `UILogin.py`.
2. Capture first raw socket connection on port 25000 (`adb reverse` to host) when client executes `ServerConnection::logOnBegin`.
3. Extract/inspect `loginapp.pubkey` to prepare minimal BigWorld `loginapp` handshake responder.
