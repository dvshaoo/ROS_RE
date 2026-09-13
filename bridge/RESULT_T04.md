TASK: T04
FINDING: logOnBegin confirmed (ServerConnection::logOnBegin, LogOnParams); loginAPP host = runtime %s arg; pubkey handshake confirmed; serverlist/25000/channel_login = 0 hits → BLOCKED

## (a) logOnBegin evidence

| Symbol / String | Source |
|---|---|
| `ServerConnection::logOnBegin ALREADY_ONLINE_LOCALLY` | libclient_arm64.so |
| `ServerConnection::logOnBegin PUBLIC_KEY_LOOKUP_FAILED` | libclient_arm64.so |
| `ServerConnection::logOnBegin conneting to %s for loginAPP` | libclient_arm64.so |
| `ServerConnection::logOnBegin recreateListeningSocket for %d failed` | libclient_arm64.so |
| `ServerConnection::logOnBegin: server:%s username:%s` | libclient_arm64.so |
| `LogOnParams::addToStream publicEncrypt failed` | libclient_arm64.so |
| `LogOnParams::readFromStream privateDecrypt failed` | libclient_arm64.so |
| Mangled: `N4neox8bwclient11LogOnParamsE` | libclient_arm64.so |
| Mangled: `N4neox8bwclient16ServerConnectionE` | libclient_arm64.so |
| Lambda: `ZN4neox8bwclient16ServerConnection10logOnBeginEPKcS3_S3_S3_tE4$_13` | libclient_arm64.so |

Signature confirmed: `logOnBegin(const char* server, const char* username, const char* password, const char* ?, uint16_t port)`

## (b) loginAPP host

**Runtime `%s` argument — NOT hardcoded.**
Exact log string: `ServerConnection::logOnBegin conneting to %s for loginAPP`
→ Host is passed at runtime (likely from server-list response or OBB config — not in .so strings).

Also seen:
- `ServerConnection::logOn: to:   %s` (runtime)
- `ServerConnection::resumelogOn from script ip:%s,  port:%d` (runtime)
- `LoginHandler::onLoginReply: change baseAddr from %s to %s` (runtime)

## (c) entities\loginapp.pubkey — handshake meaning

String found: `entities\loginapp.pubkey`  [03_lib\libclient_arm64.so]
→ BigWorld engine loads this public key file to RSA-encrypt the LogOnParams stream before sending to loginAPP.
   Evidence: `LogOnParams::addToStream publicEncrypt failed` = RSA public-key encrypt step.
   `ServerConnection::logOnBegin PUBLIC_KEY_LOOKUP_FAILED` = key file missing/unreadable abort.
   Key file expected at resource path relative to OBB (BigWorld res path).

## (d) serverlist / 25000 / channel_login — BLOCKED

| Section | Hits |
|---|---|
| `## serverlist` | 0 |
| `## 25000` | 0 |
| `## channel_login` | 0 |

→ BLOCKED-not-in-so-strings. Runtime-set or inside OBB config — huwag hulaan.

SOURCE: 06_notes/NATIVE_LOGON.md §serverconnection (lines 3-43), §logon (lines 45-74), §loginapp (lines 78-80)
        file: 03_lib\libclient_arm64.so
VERSION: 1.610377.506841 / vCode 1117219
STATUS: PASS (a+b+c confirmed; d = BLOCKED-0-hits-in-.so as expected)
