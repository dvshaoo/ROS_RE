# GEMINI.md — Rules of Survival (ROS) Private Server Emulation & RE Master Guide

> **Author**: Gemini / Antigravity Agent  
> **Last Updated**: 2026-09-16  
> **Client Version**: Rules of Survival Mobile (Android `com.netease.chiji`, v1.610377.506841, vCode 1117219, arm64-v8a)  
> **Target Environment**: LDPlayer 9 (`emulator-5554`, Android guest `172.16.1.15`, Gateway host `172.16.1.2`)

---

## 1. Executive Summary & Current Milestones (Status)

| Gate | Component | Protocol | Status | Key Finding / Implementation |
|:---|:---|:---|:---:|:---|
| **Gate 0** | Patch / CDN Server | HTTP :80/:443 | **PASS** | Bypassed patch check using local HTTP server (`mitm_serve.py` / `local_baseapp_capture.py`). Returns valid update manifest. |
| **Gate 1** | UniSDK / Auth / Sigma | HTTP :80/:443/:8443 | **PASS** | Handled guest auth token, keypoints, and telemetry callbacks (`connectLoginHostCallback` status=1). |
| **Gate 2** | LoginApp UDP Handshake | Mercury UDP :25000 | **PASS** | Solved 4-byte LE ReplyID correlation @ wire offset 5. Blowfish `pc_variant` encrypted `LoginReplyRecord` pointing client to BaseApp `172.16.1.2:25010`. |
| **Gate 3** | BaseApp Channel & Entity Init | Mercury UDP :25010 | **IN PROGRESS (SOLVED)** | Disassembled `in_place_decrypt` (IV=0 per packet) and BigWorld wastage padding. Client reaches `status==LOGGED_ON`, creates Base Player (`Account`, type 127, msg ID 5). Client packet #0 decrypted; ACK protocol reversed. |
| **Gate 4** | Character Select / Lobby | Mercury RPC / DEF | **PENDING** | Awaiting ACK response delivery to unblock client reliable channel, followed by `onEnumerateCharacters` / role creation. |

---

## 2. Solved Protocol & Binary Reverse-Engineering Discoveries

### A. LoginApp UDP Reply (`0x938070` LoginHandler::handleMessage)
- **Reply ID**: Extracted from client request packet at wire offset `5:9` (4-byte LE `uint32`).
- **Wire Framing**:
  ```text
  [flags: u16 = 0x0001]
  [msgID: u8 = 0xFF (Mercury::REPLY_MESSAGE_ID)]
  [length: u32 = len(inner)]
  [inner payload]:
      [replyID: u32 LE]
      [status: u8 = 0x01 (SUCCESS)]
      [LoginReplyRecord: 24 bytes (padded from 20 bytes)]
  [footer: b'\x00\x00']
  ```
- **LoginReplyRecord Layout (20 bytes + 4 bytes pad = 24 bytes)**:
  - BaseApp IP (4 bytes, network order) + BaseApp Port (2 bytes, big-endian) + Pad (2 bytes)
  - BaseApp IP (4 bytes) + BaseApp Port (2 bytes) + Pad (2 bytes)
  - Session Key / trailing u32 (4 bytes LE)
  - Padded with 4 zero bytes to satisfy Blowfish 8-byte block size (`24 % 8 == 0`).

### B. Blowfish Encryption Mode (`pc_variant`) & IV Rules
- **Binary citations**:
  - `EncryptionFilter::encrypt` (`0x98938c` in `libclient.so`)
  - `in_place_decrypt` (`0x98924c` in `libclient.so`)
- **Cipher Mechanics**:
  - OpenSSL `BF_ecb_encrypt` with non-standard plaintext XOR chaining:
    - Encrypt: `dst[i] = BF_ecb_encrypt(src[i] ^ prev_plaintext)`
    - Decrypt: `dst[i] = BF_ecb_decrypt(src[i]) ^ prev_plaintext`
- **Critical Discovery (E2E-020)**:
  - At `0x9892c8`, `in_place_decrypt` executes: `mov x26, xzr`.
  - **The IV is reset to all-zeros (`b'\x00'*8`) on EVERY datagram**. There is **NO** inter-packet chaining state across UDP datagrams.
- **Wastage / Padding Rule**:
  - `in_place_decrypt` (`0x989324`-`0x989350`) reads the last byte of decrypted plaintext: `wastage = packet[total_len - 1]`.
  - If `wastage <= 8`, it strips `wastage` bytes from packet length.
  - Padding must always end with the byte value `pad_len` (e.g., `b'\x00' * (pad_len - 1) + bytes([pad_len])`).

### C. Live Session Key Discovery
- Client generates a 4-byte Blowfish key per connection using OpenSSL `RAND_bytes(4)`.
- Key is stored in an `EncryptionFilter` C++ object.
- Vtable pointer in `libclient.so`: `base + 0x37dd3a0`.
- Object field: `+0x10` contains SSO length control byte (`0x08` for 4 bytes), `+0x11` contains the 4 raw key bytes.
- The BaseApp reliable channel reuses the same live key (`fa490e60`).

### D. `createBasePlayer` Wire Format
- **Message ID**: **5** (`0x05` in `ClientInterface`, disassembled at `0x947dc4` & `ClientApp::onBasePlayerCreate` `0x918504`).
  *(Note: Message ID 4 is `resetEntities`, NOT `createBasePlayer`)*.
- **Wire Layout**:
  ```text
  [flags: u16 = 0x0001]
  [msgID: u8 = 0x05]
  [length: u16 = 6]
  [entityID: u32 = 1]
  [entityType: u16 = 127 (<Account/> from entities.xml)]
  [footer: b'\x00\x00']
  [BigWorld wastage padding to multiple of 8]
  ```
- **Live logcat confirmation**:
  ```text
  [INFO] LoginHandler::onLoginReply: after Endpoint::convertAddress from 172.16.1.2 to 172.16.1.2:0
  [INFO] ServerConnection::checkScriptBaseAppAddr not call script, script addr=172.16.1.2:25010
  [INFO] Nub::recreateListeningSocket 0x76384e06c000 0.0.0.0:58112
  [INFO] external channel minUnackPacketResendPeriod: 0.100000, InactivityTimeout 10.000000
  [INFO] ServerConnection::createBasePlayer: id 1
  [INFO] ServerConnection::logOn: status==LOGGED_ON
  [INFO] ServerConnection::logOn: to: 172.16.1.2:25010
  ```

---

## 3. The Current Blocker & Reliable Channel ACK Protocol

### The Issue
Client reaches `status==LOGGED_ON` and initiates the external reliable channel by sending packet #0:
```text
[WARNING] Channel::checkResendTimers( 172.16.1.2:25010 ): Resending unacked packet #0 due to inactivity
```
Client decrypts cleanly on server as:
- Flags: `0x0058` (`FLAG_ON_CHANNEL = 0x0008` | `FLAG_IS_RELIABLE = 0x0010` | `FLAG_HAS_SEQUENCE_NUMBER = 0x0040`)
- Sequence number: `0` (last 4 bytes of unpadded payload)
- Payload: Client's initial BaseApp handshake / `identifyVersionPoint` (Method ID 12).

### Mercury Reliable ACK Wire Specification
Disassembly of `Nub::processFilteredPacket` (`0x990364`-`0x9904fc`) and `Channel::handleAck` (`0x986898`):
1. **Flags**:
   - `FLAG_ON_CHANNEL` (`0x0008`): Resolves destination channel object.
   - `FLAG_HAS_ACKS` (`0x0004`): Activates ACK processing path.
   - Combined Flags: `0x000c`.
2. **Body**:
   - Empty bundle zero footer: `b'\x00\x00'` (2 bytes).
3. **ACK Footer**:
   - `[ack_seq_0: uint32 LE] ... [ack_count: uint8]`
   - For packet #0: `struct.pack('<I', 0) + bytes([1])` (5 bytes).
4. **Full Standalone ACK Packet Construction**:
   ```python
   # 1. Plaintext construction (9 bytes)
   plain = struct.pack('<H', 0x000c) + b'\x00\x00' + struct.pack('<I', seq) + bytes([1])
   
   # 2. BigWorld wastage padding (16 bytes)
   pad_len = 8 - (len(plain) % 8) # 7 bytes
   plain_padded = plain + b'\x00' * (pad_len - 1) + bytes([pad_len])
   
   # 3. Blowfish pc_variant encryption with IV = 0
   ack_enc = bf_encrypt(plain_padded, key_hex=session_key, iv=b'\x00' * 8)
   
   # 4. Transmit
   udp_sock.sendto(ack_enc, client_addr)
   ```

---

## 4. Key Files & Architecture

- `mitm/local_baseapp_capture.py`: Integrated MITM server running HTTP (:80/:443/:8443), LoginApp UDP (:25000), and BaseApp UDP (:25010).
- `mitm/mitm_serve.py`: Base HTTP response generator for UniSDK, G0/G1 patches, and Sigma keypoints.
- `01_apk/base_decompiled/lib/arm64-v8a/libclient.so`: Main game native library containing the NeoX / BigWorld engine.
- `05_entities/out/entities.xml`: Extracted entity types (`Account = 127`, `Athlete = 128`).
- `06_notes/BASEAPP_CRYPTO_BLOCKER_SUMMARY.md`: Detailed step-by-step crypto trace and disassembly proof.

---

## 5. Immediate Next Steps for Next Session

1. **Deploy ACK Responder in `local_baseapp_capture.py`**:
   - When receiving any packet on UDP 25010 with `FLAG_HAS_SEQUENCE_NUMBER` (`0x0040`):
     Extract `seq = struct.unpack('<I', data_decrypted[-4:])[0]`.
     Immediately send back the 16-byte encrypted ACK packet.
2. **Verify Client Logcat**:
   - Confirm `Resending unacked packet #0 due to inactivity` stops completely.
   - Confirm `delResendTimer()` logs success for packet #0.
3. **Handle Incoming Client RPC & Gate 4 (Lobby Transition)**:
   - Parse client's `identifyVersionPoint` or entity method call.
   - Send role / character enumeration response (`onEnumerateCharacters` / role list) to transition the UI from "Logging in" spinner to Character Creation / Lobby.
