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

### 2.2 Fields Sent in LoginApp Request Bundle

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
