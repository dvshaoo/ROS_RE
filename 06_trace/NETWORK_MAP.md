# ROS v1117219 Network Architecture Map

This document catalogs every network endpoint, protocol, payload schema, and handler identified across the DEX files, native binaries, and network traces for Rules of Survival build `v1117219`.

---

## 1. Authentication & Account Servers (NetEase MPay & UniSDK)

| Purpose | Host / Endpoint | Method | Request Payload / Params | Response Structure | Calling Class & Method | Confidence |
|---|---|---|---|---|---|---|
| Device Init | `https://sdk-os.mpsdk.easebar.com/api/devices/init` | POST | Device hardware IDs, OS version, app bundle | `{"code":0,"device":{"id":"..."}}` | `com.netease.mpay.oversea.b.a` (Dex) | CONFIRMED |
| Game Auth Config | `https://sdk-os.mpsdk.easebar.com/api/games/config` | POST | App ID, channel, platform, sdk version | `{"code":0,"game_config":{"account_type":{...}}}` | `com.netease.mpay.oversea.b.b` (Dex) | CONFIRMED |
| Guest Authentication | `https://sdk-os.mpsdk.easebar.com/api/users/login/guest` | POST | `device_id`, game ID, client token | `{"code":0,"user":{"id":"...","token":"..."},"minor_status":102,"age_status":0}` | `com.netease.mpay.oversea.d.a.a.e` (Dex `0x3c8f8c`) | CONFIRMED |
| Standard User Login | `https://sdk-os.mpsdk.easebar.com/api/users/login` | POST | Account type, auth credentials, device token | `{"code":0,"user":{"id":"...","token":"..."},"minor_status":102}` | `com.netease.mpay.oversea.d.a.a` (Dex) | CONFIRMED |
| LVU Minor Query | `https://sdk-os.mpsdk.easebar.com/api/minors/query` | POST | `user_id`, `token` | `{"code":0,"minor_status":102,"age_status":0}` | `com.netease.mpay.oversea.e.a.d` (Dex `0x3ccee0`) | CONFIRMED |
| Minor Birthday Update | `https://sdk-os.mpsdk.easebar.com/api/minors/update_birthday` | POST | `user_id`, `token`, `birthday`, `country_code` | `{"code":0,"minor_status":102}` | `com.netease.mpay.oversea.e.a.h` (Dex `0x3cc968`) | CONFIRMED |
| Minor Parental Consent | `https://sdk-os.mpsdk.easebar.com/api/minors/consent` | POST | `user_id`, `token`, consent flag | `{"code":0}` | `com.netease.mpay.oversea.e.a.i` (Dex `0x3cc968`) | CONFIRMED |
| Minor Email Update | `https://sdk-os.mpsdk.easebar.com/api/minors/update_email` | POST | `user_id`, `token`, `email` | `{"code":0}` | `com.netease.mpay.oversea.e.a.j` (Dex `0x3cc968`) | CONFIRMED |
| Session Token Exchange | `https://sdk-os.mpsdk.easebar.com/api/users/login/v2/sdk_token` | POST | `user_id`, `token` | `{"code":0,"user_id":"...","sdk_token":"..."}` | `com.netease.mpay.oversea.h.a.a` (Dex `0x3d34bc`) | CONFIRMED |
| QR Code Login Session | `https://qr.mpsdk.easebar.com/` | GET/POST | Session token, device metadata | QR session state | `com.netease.mpay.oversea.scan` (Dex) | CONFIRMED |

---

## 2. Patch, Manifest & Version Servers

| Purpose | Host / Endpoint | Method | Request Payload / Params | Response Structure | Calling Class & Method | Confidence |
|---|---|---|---|---|---|---|
| Patch Hash Check | `https://h45na.update.easebar.com/pl/h45na_hc` | GET | `headcode` / version parameters | `{"code":0,"md5":"...","size":...}` | Python `patch.patch_logic` via NeoX `http_get` | CONFIRMED |
| Patch Plist Manifest | `https://h45na.update.easebar.com/pl/npk_version_na_android.plist` | GET | None | Plist dictionary containing patch metadata, file sizes, MD5 hashes | Python `patch.patch_logic` / `NativeStartPatch` | CONFIRMED |
| Total Package Filelist | `https://h45na.update.easebar.com/1117219/total_list` | GET | Version string | Zlib-compressed pickled dictionary of file MD5s | Python `patch.patch_logic` via NeoX `http_get` | CONFIRMED |
| Server Notice Banner | `https://h45na.update.easebar.com/notice_na.txt` | GET | None | Raw UTF-8 maintenance / announcement text | Python `ui.UILogin` via NeoX `http_get` | CONFIRMED |
| UniSDK Update Manifest | `https://update.unisdk.easebar.com/html/latest_v6.json` | GET | SDK build number | JSON update descriptor | `com.netease.ntunisdk.base` (Dex) | CONFIRMED |

---

## 3. Gateway, Server List & Routing

| Purpose | Host / Endpoint | Method | Request Payload / Params | Response Structure | Calling Class & Method | Confidence |
|---|---|---|---|---|---|---|
| Server List Configuration | `https://h45na.update.easebar.com/server_list_ad.txt` | GET | None | Space-delimited server definition records: `[Name] [ID] [State] [Type] [Title] [Region] [GatewayIP:Port] ...` | Python `ui.UILogin.requestServerList` | CONFIRMED |
| VIP Fallback Server List | `https://52.221.3.167:443/server_list_ad.txt` (Host header: `h45na.update.easebar.com`) | GET | None | Space-delimited server definition records | Python `ui.UILogin.fetch_by_vips` | CONFIRMED |
| Geolocation IP Resolution | `https://who.nie.easebar.com/v1` | GET | None | Base64-encoded signed JSON: `{"sig":"...","payload":"..."}` | Python `neox.whoami` / `neox::bwclient` | CONFIRMED |
| HTTPDNS Domain Lookup | `https://httpdns.proxima.nie.easebar.com/resolve?domain=...` | GET | `domain`, `gameid` | `{"domain":"...","addrs":["..."],"ttl":600}` | `com.netease.ntunisdk.base` & NeoX Pharos | CONFIRMED |
| ISP Network Diagnostics | `https://h45na.update.easebar.com/pharos_isp.txt` | GET | None | Tab-delimited IP range to ISP region map | NeoX Pharos Network Diagnostics | CONFIRMED |

---

## 4. Lobby, Game Session & World Servers (BigWorld Mercury Protocol)

| Purpose | Host / Endpoint | Protocol | Transport | Packet Framing / Payload Structure | Calling Class & Method | Confidence |
|---|---|---|---|---|---|---|
| BigWorld LoginApp Gateway | Server IP: `25000` (e.g. `10.0.2.2:25000`) | BigWorld Mercury Nub Protocol | UDP / TCP | RSA-encrypted `LogOnParams` stream containing username, password/token, client version, public key hash (`loginapp.pubkey`). Reply: `onLoginReply` with winning BaseApp IP:Port | `neox::bwclient::ServerConnection::logOnBegin` (`libclient.so`) | CONFIRMED |
| BigWorld BaseApp (Account) | BaseApp IP: Assigned Port | BigWorld Mercury Channel Protocol | UDP / TCP | Mercury message packets invoking `Account.handshake`, `uploadABSwitchesConfig`. Reply invokes `Account.onLogin`, `Account.onChannelLogin` | `neox::bwclient::BaseAppLoginRequest` (`libclient.so`) | CONFIRMED |
| BigWorld BaseApp (Lobby Avatar) | BaseApp IP: Assigned Port | BigWorld Mercury Channel Protocol | UDP / TCP | Method calls on `Avatar.def.xml` interface: item equipment, friend lists, rankings, custom control sync | `neox::bwclient::ServerConnection` (`libclient.so`) | CONFIRMED |
| Matchmaking Queue | BaseApp IP: Assigned Port | BigWorld Mercury Protocol | UDP / TCP | Exposed method on `iRosMatchAvatar` / `Avatar.cell.reqMatch(...)` sending game mode, map ID, team configuration | Python `ui.UIHall` -> `Avatar` entity method | CONFIRMED |
| BigWorld CellApp (Battle Session) | CellApp IP: Assigned Port | BigWorld Mercury Channel Protocol | UDP / TCP | High-frequency spatial packets: entity position updates (`ServerConnection::addMove`), forced positions, weapon firing, bullet traces, vehicle controls, loot drops (`BattleGroundSpace.def.xml`, `Athlete.def.xml`) | `neox::bwclient::ServerConnection::createCellPlayer` (`libclient.so`) | CONFIRMED |

---

## 5. Telemetry, Anti-Cheat & Analytics

| Purpose | Host / Endpoint | Method | Request Payload / Params | Response Structure | Calling Class & Method | Confidence |
|---|---|---|---|---|---|---|
| Startup Diagnostics | `https://drpf-h45na.proxima.nie.easebar.com` | POST | JSON payload with OBB load timing, device hardware, CPU cores, screen density | `{"code":200,"status":"ok"}` | `com.netease.neox.Launcher.DRPF` (Dex line 2450) | CONFIRMED |
| Anti-Cheat Telemetry | `https://data-detect.nie.easebar.com/client/mobile_upload` | POST | Encrypted binary blob of security scans, root checks, memory hooks | `{"status":0}` | `libclient.so` / `com.netease.ntunisdk.base` | CONFIRMED |
| UniSDK App Open Log | `https://applog.matrix.easebar.com/client/sdk/open_log` | POST | JSON tracking app launch events | `{"code":0}` | `com.netease.ntunisdk.SdkNeteaseGlobal` (Dex) | CONFIRMED |
| UniSDK Payment / Order Log | `https://applog.matrix.easebar.com/client/sdk/pay_log` | POST | Order verification records | `{"code":0}` | `com.netease.ntunisdk.base` (Dex) | CONFIRMED |
| CC Live / Voice Streaming | `http://vquery.cc.vapi.cc.easebar.com/query` | GET | Channel ID, stream token | Voice room endpoint descriptors | `com.netease.cc.ccscreenlivesdk` (Dex/JNI) | CONFIRMED |
