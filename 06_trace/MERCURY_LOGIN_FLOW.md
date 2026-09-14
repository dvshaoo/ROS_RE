# ROS v1117219 — BigWorld Mercury LoginApp Protocol Flow

## 1. Protocol Architecture & Mercury Framing

Rules of Survival utilizes the **BigWorld Mercury** network architecture. Mercury is an asynchronous, reliable UDP protocol layered over standard Berkeley/POSIX UDP sockets (`Mercury::Nub`, `Mercury::Channel`, `Mercury::Bundle`).

```text
[ Client: UILogin.doLoginGame ]
              │
              ▼
neox::bwclient::ServerConnection::logOnBegin(server, port, user, pwd, keyPath)
              │
              ▼
1. Mercury::Nub::recreateListeningSocket() -> binds local UDP socket (0x861-0xe321)
2. ServerConnection::setKeyFromResource("entities\\loginapp.pubkey") -> loads RSA key
3. LogOnParams::addToStream(bundle) -> encrypts authentication block via RSA
4. Mercury::Bundle::send() -> dispatches UDP packet to LoginApp (Port 20013 / 25000)
              │
              ▼
      [ BigWorld LoginApp ]
              │ (Validates account, selects winning BaseApp instance)
              ▼
LoginApp returns LoginReplyRecord over UDP
              │
              ▼
5. LoginHandler::handleMessage() -> packet integrity check (REASON_CORRUPTED_PACKET)
6. LoginHandler::onLoginReply() -> unpacks BaseApp IP, port, session encryption key
7. BaseAppLoginRequest::setNubAndSend() -> dispatches baseAppLogin bundle to BaseApp
```

---

## 2. Client-Side Login Request: `LogOnParams`

### 2.1 Struct & Protocol Role
- **Class**: `neox::bwclient::LogOnParams` (RTTI `0x37c7c80` in `libclient_arm64.so`)
- **Method**: `neox::bwclient::LogOnParams::addToStream(Mercury::BinaryOStream&)`
- **Purpose**: Packages all client identification, authentication tokens, engine versions, and security digests into an encrypted binary bundle dispatched to the `loginapp`.

> **2026-09-14 UPDATE**: The table below (§2.2) was written before instruction-level
> disassembly of `addToStream` was performed and does not match what the binary actually
> does. It is kept for history but is **superseded** by `LOGONPARAMS_SERIALIZATION.md`,
> which documents the real field offsets, the real (non-BigWorld-standard) 4-argument
> function signature, and confirms the RSA padding is **OAEP**, not PKCS#1 v1.5. In
> particular: only 4 fields (flags + 3 strings) are inside the encrypted block — the
> "Entity Defs MD5" and a numeric field are always sent in plaintext, contradicting the
> "CONFIRMED" marks below for those two rows.

### 2.2 Fields Sent in LoginApp Request Bundle (SUPERSEDED — see note above)

| Field | Source | Purpose | Encoding / Framing | Confirmed? |
| :--- | :--- | :--- | :--- | :--- |
| **Message ID** | BigWorld Engine | Identifies Mercury RPC opcode for login | `uint8` (`LoginInterface::login`) | CONFIRMED |
| **Account / Username** | UniSDK `user.id` / MPay | Unique player account identifier | Length-prefixed string (`std::string`) | CONFIRMED |
| **Password / Token** | UniSDK `login_token` / `sdk_token` | Ephemeral authentication credential | Length-prefixed string (`std::string`) | CONFIRMED |
| **Client Version** | `patchVersion` / `VERSION` | Validates client compatibility with server | `uint32` / Version string (`1117219`) | CONFIRMED |
| **Engine Version** | NeoX engine compile timestamp | Verifies native protocol binary compatibility | `uint32` hash / integer | STRONG EVIDENCE |
| **Entity Defs MD5** | `BigWorld.getEntityDefsMd5()` | Verifies that client and server XML schemas match | 16-byte MD5 digest (`BinaryOStream`) | CONFIRMED |
| **Nonce / Challenge** | Server handshake / Client seed | Anti-replay synchronization counter | `uint32` integer | STRONG EVIDENCE |
| **Channel / Platform** | Android OS / UniSDK channel ID | Identifies store/distribution channel (e.g. Google, NetEase) | `uint32` integer | CONFIRMED |
| **Public Key Encryption** | OpenSSL RSA (`loginapp.pubkey`) | Encrypts credentials/tokens to protect against eavesdropping | RSA-1024 / RSA-2048 PKCS#1 v1.5 block | CONFIRMED |

---

## 3. Public Key Cryptography: `entities\loginapp.pubkey`

### 3.1 Verification & Binary Evidence
- **Binary**: `libclient_arm64.so` at offset `0x93b448` (`ServerConnection::setKeyFromResource`)
- **Key Path**: Hardcoded string `entities\loginapp.pubkey` (located at `.rodata:0x2a4939e`)
- **Loading Mechanism**:
  1. `ServerConnection::logOnBegin` inspects the key path parameter. If empty, it defaults to `entities\loginapp.pubkey`.
  2. `ServerConnection::setKeyFromResource` calls `BWResource::open("entities\\loginapp.pubkey")` to read raw bytes from the virtual filesystem (NPK archives or asset storage).
  3. If not found, logs: `ServerConnection::setKeyFromResource: Couldn't load private key from non-existent file %s.`
  4. Returns `false`, triggering error handler at `0x93c250`:
     - Dispatches error log: `ServerConnection::logOnBegin PUBLIC_KEY_LOOKUP_FAILED`
     - Invokes login failure callback with `LogOnStatus` code `0x701`.

> **2026-09-14 UPDATE**: The exact xref addresses `0x93b448` and `0x996f50` cited in this
> section could not be reproduced with an independent ADRP/ADD cross-reference scan of the
> `entities\loginapp.pubkey` and `setKeyFromResource` strings (zero hits — likely referenced
> via a pointer table rather than an inline literal load, which the scan method used does
> not follow). The general claim (client loads a PEM RSA public key via OpenSSL
> `BIO`/`PEM_read_bio_RSA_PUBKEY`/`RSA_size`) remains STRONG EVIDENCE — those OpenSSL symbol
> names are genuinely present in `.dynstr` — but the specific addresses in this section are
> UNVERIFIED, not CONFIRMED. What **was** independently confirmed at the instruction level is
> the padding mode used at encryption time: **RSA-OAEP**, not PKCS#1 v1.5 — see
> `LOGONPARAMS_SERIALIZATION.md` §5.

### 3.2 Key Format & OpenSSL Parsing
Decompilation of `0x996f50` (`Mercury::EncryptionFilter::setKey`) reveals:
1. `0x996f78`: Calls OpenSSL `BIO_s_mem()`
2. `0x996f7c`: Calls OpenSSL `BIO_new()`
3. `0x996f94`: Calls OpenSSL `BIO_puts()` / `BIO_write()` to write key data into memory BIO
4. `0x996fc8`: Calls OpenSSL `PEM_read_bio_RSA_PUBKEY()` to parse standard X.509 / PKCS#1 SubjectPublicKeyInfo PEM header:
   ```text
   -----BEGIN PUBLIC KEY-----
   MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQE...
   -----END PUBLIC KEY-----
   ```
5. `0x996ff0`: Calls `RSA_size(rsa)` to extract key modulus length.

### 3.3 Security Role
The public key is **asymmetric**. The client holds only the **public key** to encrypt `LogOnParams`. The server holds the corresponding **private key** to decrypt the credentials.
The client cannot operate against a server unless the server possesses the private key matching the public key baked into the client, **OR** unless the public key asset in the client is replaced with a key whose private counterpart is known to the server.

---

## 4. LoginApp to BaseApp Handshake: `LoginHandler`

### 4.1 LoginApp Reply: `LoginReplyRecord`
When the LoginApp accepts the client credentials, it sends an incoming Mercury bundle over UDP.

- **Handler**: `neox::bwclient::LoginHandler::handleMessage` (`libclient_arm64.so`)
- **Dispatcher**: `neox::bwclient::LoginHandler::onLoginReply` (`libclient_arm64.so` @ `0x938474`)
- **Contents of `LoginReplyRecord`**:
  1. `Mercury::Address`: IPv4/IPv6 address and port of the allocated `BaseApp`.
  2. `SessionKey`: Encryption key used for subsequent symmetric channel encryption between Client and BaseApp.
  3. `AccountID`: Assigned account identifier.

### 4.2 Address Mapping & Logging
`LoginHandler::onLoginReply` decodes the BaseApp address and logs:
- `LoginHandler::onLoginReply: change baseAddr from %s to %s`
- `LoginHandler::onLoginReply: after Endpoint::convertAddress from %s to %s`
- `LoginHandler::onLoginReply: Address::convertToIPV6 to %s`

If the packet format or payload length is invalid, the engine aborts:
- `LoginHandler::handleMessage: Got reply of unexpected size (%d)`
- `Mercury::REASON_CORRUPTED_PACKET`
- `Unable to connect to BaseApp: A NAT or firwall error may have occured?`

### 4.3 BaseApp Connection Request: `BaseAppLoginRequest`
Once the address is resolved:
1. Client instantiates `neox::bwclient::BaseAppLoginRequest`.
2. Engine transitions state to `CONNECTING_TO_BASEAPP` (`0x9384dc`).
3. Sends `BaseAppExtInterface::baseAppLogin` bundle to the BaseApp address over UDP:
   ```arm64
   // Binary: libclient_arm64.so @ 0x9384e4
   0x9384e4: add  x1, x1, #0x1a1   // String: "sending base app request to %s"
   0x9384ec: bl   #0x83f8a8        // Dispatch BaseAppLoginRequest bundle
   ```

---

## 5. Summary State Transition Table

| Stage | Trigger / Caller | Native Method | Network Action | Next State |
| :---: | :--- | :--- | :--- | :---: |
| **1** | User taps "PLAY" | `ServerConnection::logOnBegin` | UDP socket bind (`recreateListeningSocket`) | `LOOKING_UP_PUBKEY` |
| **2** | Key path validated | `ServerConnection::setKeyFromResource` | Reads `entities\loginapp.pubkey` | `ENCRYPTING_PAYLOAD` |
| **3** | Key instantiated | `LogOnParams::addToStream` | Dispatches encrypted login bundle to LoginApp | `WAITING_LOGINAPP_REPLY` |
| **4** | LoginApp reply received | `LoginHandler::onLoginReply` | Unpacks BaseApp IP & Port | `CONNECTING_TO_BASEAPP` |
| **5** | BaseApp addressed | `BaseAppLoginRequest::setNubAndSend` | Dispatches `baseAppLogin` bundle to BaseApp | `WAITING_BASEAPP_REPLY` |
| **6** | BaseApp reply received | `LoginHandler::onBaseAppReply` | Establishes indexed Mercury channel | `CONNECTED_TO_BASEAPP` |
| **7** | Entity stream received | `ServerConnection::createBasePlayer` | Instantiates `Account` base entity | `ACCOUNT_ACTIVE` |

---

## 6. 2026-09-14 — Live-Verified Request Packet, and Confirmed Mercury `Nub` Architecture Strings

**CONFIRMED BY DYNAMIC CAPTURE**: a real `LogOnParams` request from the live client (PID
`16332` on the project's LDPlayer test instance) was captured — 273 bytes total, a 256-byte
RSA-2048-OAEP ciphertext block (confirming the key size for the first time), with constant
framing bytes and an incrementing 2-byte value at request offset `[5:7]` across retries.
Full byte-level detail: `LOGONPARAMS_SERIALIZATION.md` §6a, `PLAY_TO_BASEAPP_CAPTURE.md`
§2.

**STRONG EVIDENCE (real strings, not fabricated)**: `libclient_arm64.so` contains a large,
coherent set of `Mercury::Nub`/`Channel` diagnostic strings describing a packet/footer
validation architecture (flags check → checksum check → optional footers for
piggyback/acks/indexed-channel/fragment/sequence-number/first-request-offset → message-id
dispatch), and a reply-correlation model keyed by a 32-bit "reply id" with source-address
verification. Exhaustive static cross-reference analysis could **not** locate the live code
implementing this (see `LOGIN_REPLY_MERCURY_ENVELOPE.md` §3 for the full, bounded attempt
and why these strings are believed to be vestigial/dead in this specific release build).
This section is added here only because it materially updates the "LoginApp reply" row (row
4 above) — the previous assumption that a bare `LoginReplyRecord` body is sufficient is now
known to be **incomplete**: some Mercury-level envelope is required first, and three
candidate envelopes have been tried and rejected (`LOGIN_REPLY_MERCURY_ENVELOPE.md` §5).
`LoginHandler::onLoginReply` has **not** been confirmed reached by any local reply sent so
far.

## 7. 2026-09-14 (follow-up) — `handleMessage` Boundary Confirmed; Dispatch Path Still Opaque

**CONFIRMED BY BINARY**: `LoginHandler::onLoginReply`/`handleMessage`'s exact function
boundary is `0x938070`–`0x938724` (re-verified via a systematic 75-function prologue
inventory of the whole `ServerConnection` code cluster, `0x936000`–`0x93d000`) — narrower
and more precise than the loosely-quoted "0x938100–0x938940" range in earlier documents.

**STRONG EVIDENCE**: this function, `LogOnParams::addToStream`, and a nearby
log-formatting routine are each called via a mechanism that produced **zero results** across
five independent static call-graph methods (direct `BL`, direct `B`, absolute-pointer scan,
relocation-addend scan, relative-vtable-offset scan) — see
`MERCURY_REPLY_DISPATCH_TRACE.md` §2 for the full account. This is consistent with genuine
C++ virtual dispatch (expected for a message-handler interface in BigWorld's Mercury
design) whose vtable could not be located by slot-value scanning. The dispatch path from
raw UDP receipt to this handler — and the lifecycle of the 32-bit "reply id" implied by
`Mercury::Nub::handleMessage`'s own diagnostic string — remains **UNKNOWN**, not
established despite a real, thorough attempt.

## 8. 2026-09-14 (Stalker pass) — JIT Cache Identified, Dispatch Still Not Attributed

**CONFIRMED BY DYNAMIC CAPTURE**: Frida Stalker (call-summary mode, thread `16424`,
identified via `logcat` tagging) directly observed execution resolving into
`/system/lib64/arm64/nb/libtcb.so` (`r-x`, real file-backed mapping) — this is
NativeBridge's actual JIT translation cache, confirmed for the first time by direct dynamic
evidence rather than inference. Execution bursts in this region and in `libhoudini.so`
correlate in time (~1s resolution) with `ServerConnection::logOnBegin` and the
`Mercury::REASON_TIMER_EXPIRED` timeout. Full detail: `MERCURY_STALKER_RUNTIME_TRACE.md`.

This does **not** resolve the dispatch-path question in §6/§7 above: the observed hot
addresses are Houdini's generic dispatch machinery (shared by all ARM64 code on that
thread), not attributable to `LoginHandler::onLoginReply` specifically.
`LoginHandler::onLoginReply` is still **not confirmed reached**.

## 9. 2026-09-14 (wire capture) — Kernel-Level Capture Confirms Bytes, Not Dispatch

**CONFIRMED BY DYNAMIC CAPTURE**: a genuine `tcpdump` capture on the Android guest's
`wlan0` (`06_trace/MERCURY_WIRE_CAPTURE.md`) proves the client sends exactly 10
`LogOnParams` retries at a fixed ~0.43s cadence, then waits ~5.1s of silence before
`Mercury::REASON_TIMER_EXPIRED` at ~9.0s total — reproduced identically across two capture
sessions. Client wire bytes match server-received bytes exactly, in both directions,
ruling out the local network path as a source of any corruption. A reply/no-reply control
experiment shows retry timing is **completely unaffected** by whether a reply is sent at
all. This is new, precise, wire-level evidence, but it does **not** establish whether
`LoginHandler::onLoginReply` executes — that remains unknown, and is not claimed here.

## 10. 2026-09-14 (socket-read trace) — CONFIRMED: Reply Is Read By The Application

**CONFIRMED BY DIRECT SYSCALL EVIDENCE** (`06_trace/MERCURY_SOCKET_READ_TRACE.md`): using
`strace` attached to TID `16424`, the client's `recvfrom()` call on the Mercury LoginApp
socket (FD 181) returns our exact 22-byte reply on all 10 retries, byte-for-byte, with a
no-reply control confirming the same call returns nothing when nothing is sent. **This
answers the question left open by §9**: the reply demonstrably reaches the application
process. The retry/timeout behavior is still unaffected by this (row 4 in the state table
above remains only partially resolved) — the rejection now provably happens in
application-level Mercury processing after the socket read, not in network delivery.
`LoginHandler::onLoginReply` is still not confirmed to execute.
