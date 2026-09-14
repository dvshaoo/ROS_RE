# SERVER_RESOURCE_INVENTORY.md — Authoritative Server & Asset Resource Inventory

**Client Version**: `1.610377.506841`  
**Client Version Code**: `1117219`  
**Target Architecture**: `arm64-v8a`  
**Inspection Date**: 2026-09-14  

---

## 1. Client Asset & Binary Inventory

| Resource | File Path | Size (Bytes) | SHA-256 Hash | Format / Content | Status |
|---|---|---|---|---|---|
| Master Archive | `00_INBOX/RULES_OF_SURVIVAL_1.610377.506841.xapk` | 3,595,621,046 | Preserved master | XAPK (ZIP with APK + OBBs) | **PROVEN** |
| Base APK | `01_apk/base.apk` | 94,554,134 | `84A4799CF84EE52548934BEBCFB5E3B17ECF56E81C9100106A0F6247863043BC` | Android APK package | **PROVEN** |
| Primary DEX | `02_dex/classes.dex` | 5,210,852 | `264A10559E064E7CA12A19413BF0741D3ADF3BA3805421238374714102B7D345` | Dalvik Executable (UniSDK, MPAY) | **PROVEN** |
| Secondary DEX | `02_dex/classes2.dex` | 4,156,660 | Verified | Dalvik Executable | **PROVEN** |
| Tertiary DEX | `02_dex/classes3.dex` | 4,527,184 | Verified | Dalvik Executable | **PROVEN** |
| Native Engine Library | `03_lib/libclient_arm64.so` | 72,729,416 | `3192AA9609975ED14933FF84675877056A61B979AF918FBEC4B4C3CA82882D76` | ELF 64-bit LSB shared object (NeoX / BigWorld) | **PROVEN** |
| Main OBB | `04_obb/main.1117219.com.netease.chiji.obb` | 1,977,238,353 | Verified | ZIP archive (361 entries, includes `res/entities.npk`) | **PROVEN** |
| Patch OBB | `04_obb/patch.1117219.com.netease.chiji.obb` | 1,523,738,987 | Verified | ZIP archive (24 entries, includes `script.npk`, `assets.npk`) | **PROVEN** |
| Entity Package | `05_entities/entities.npk` | 337,112 | `E3CC118AA897B0390ABA9F4C94557DC001F8EDFF8F2FE57C786BE4E43D3E97F5` | NXPK Archive (Entity XML definitions) | **PROVEN** |

---

## 2. Server-Side Infrastructure Status

| Service Component | Port / Protocol | Required By | Status | Details |
|---|---|---|---|---|
| **Patch & Config HTTP Server** | `80`, `8080` / HTTP | Startup & Patch Check (`ResourcePatcher.py`) | **PROVEN** (Mocked) | Answers `/pl/npk_version_na_android.plist`, `/1117219/total_list`, `/server_list_ad.txt`. |
| **Patch & Config HTTPS Server** | `443`, `8443` / HTTPS | Native TLS & Game HTTPS | **PROVEN** (Mocked) | Handled by local self-signed TLS certificate (`mitm/srv.crt`). |
| **Auth Service (UniSDK/MPay)** | `80`, `443` / HTTP(S) | Title Screen Login Flow (`classes.dex`) | **PROVEN** (Mocked) | Endpoints: `/api/devices/init`, `/api/users/login/v2/sdk_token`, `/api/games/config`. |
| **BigWorld LoginApp** | `25000` / Mercury (UDP/TCP) | `neox::bwclient::ServerConnection::logOnBegin` | **MISSING** (Official) / **IN PROGRESS** (Local) | Official NetEase/BigWorld binary missing; minimal local Mercury adapter required. |
| **BigWorld BaseApp** | Dynamic / Mercury | `neox::bwclient::LoginHandler::onLoginReply` | **MISSING** (Official) / **UNKNOWN** | Handles character/role creation (`LoginProxy`, `Account`) and Base entities. |
| **BigWorld CellApp** | Dynamic / Mercury | World simulation & match synchronization | **MISSING** (Official) / **UNKNOWN** | Handles physics, movement, weapons, vehicles (`Avatar`, `Athlete`). |
| **BigWorld DBApp** | Internal | Account & character persistence | **MISSING** (Official) / **UNKNOWN** | SQLite / MySQL backed local schema planned. |

---

## 3. Cryptographic Keys & Tokens

| Key / Token | Location / Source | Value / Fingerprint | Classification |
|---|---|---|---|
| NeoX AES Decryption Key | `libclient_arm64.so` at offset `0x02B504E0` | `w5q6^C04SW!@e}ad` (16 bytes, AES-128-ECB) | **PROVEN** (Used to decrypt `script.npk`) |
| LoginApp RSA Public Key | Asset path `entities/loginapp.pubkey` (string in `libclient_arm64.so`) | File missing from top-level assets; binary pubkey or RSA modulus needed | **MISSING / UNKNOWN** |
| Whoami HMAC Key | Client bytecode | `prikey.57CRaLUV1tHB` | **PROVEN** (Used to sign `/v1` payloads) |

---

## 4. Entity Definition Census (from `05_entities/out`)

- **Total Definitions**: 723 extracted `.def.xml` files.
- **Key Client-Server Interfaces**:
  - `LoginProxy.def.xml`: Methods `handshake(DEVICE_INFO, CHANNEL_INFO)`, `onChannelLogin(UINT8, PYTHON)`.
  - `Account.def.xml`: Methods `handshake(...)`, `onLogin(INT32, STRING)`, `onChannelLogin(UINT8, PYTHON)`.
  - `Avatar.def.xml`: Core lobby and player state representation.
  - `Athlete.def.xml`: Match and combat simulation entity.
