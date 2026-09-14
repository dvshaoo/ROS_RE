# ROS v1117219 — Server Address Origin & Trace

## 1. Executive Summary & Critical Distinction

> [!IMPORTANT]
> **Definitive Finding**: The address `10.0.2.2:25000` (or `127.0.0.1:25000`) is **NOT** a production NetEase server address, nor is it hardcoded in the native client binary `libclient.so`.
> 
> It is an **arbitrary local test payload** injected into the runtime HTTP response for `server_list_ad.txt` by the local reverse-engineering proxy (`mitm/mitm_serve.py`) to steer the Android emulator (`10.0.2.2` = Android QEMU/LDPlayer virtual gateway to host) to local diagnostic socket listeners.

In the original NetEase production build, the server address originates dynamically from a CDN-hosted configuration file retrieved via HTTP GET during title screen initialization.

---

## 2. Server Address Lifecycle & Pipeline

```text
1. Platform Identification
   Module: extconfigs.py:80-87
   Evaluates OS -> selects '/server_list_ad.txt' for Android

2. HTTP Query Dispatch
   Module: ui/UILogin.py:130-136 (requestServerList)
   Issues HTTP GET: http(s)://<domain>/server_list_ad.txt

3. Web Response Handling
   Module: ui/UILogin.py:147-148 (initServerInfo)
   Receives plain text line-delimited ASCII payload

4. Line Parsing & Server Grouping
   Module: ui/UILogin.py:151-177 (updateServerList)
   Splits response by newline '\n' into individual server records

5. Positional Field Extraction
   Module: ui/UILogin.py:180-257 (parseOneServerInfo)
   Splits record by space ' ' into tokens: zone, name, telIP, cncIP, eduIP, etc.

6. Address Splitting
   Module: ui/UILogin.py:174-177
   Extracts telIP ("IP:PORT") -> server['ip'] = IP, server['port'] = int(PORT)

7. Native Handoff
   Module: ui/UILogin.py:doLoginGame()
   Passes server['ip'] and server['port'] into native engine

8. Socket Initialization & Connection
   Binary: libclient.so -> neox::bwclient::ServerConnection::logOnBegin(ip, port, ...)
   Initializes Mercury UDP Nub socket and targets server IP on specified port
```

---

## 3. Production Architecture vs. Test Environment Injection

### 3.1 Production Architecture (NetEase Official)
In live production, Rules of Survival operated hundreds of physical and cloud game instances organized by geographical zones (North America, South America, Europe, Asia).
- **Domain**: Fetched from NetEase patch/distribution servers (e.g. `g61.gph.easebar.com`, `h45na.gph.easebar.com`).
- **File**: `server_list_ad.txt` (Android), `server_list_ios.txt` (iOS), `server_list_pc.txt` (Windows).
- **Content**: A multi-line plain text table listing regional server endpoints with status flags (normal, busy, full, maintenance).

### 3.2 MITM Reverse-Engineering Proxy Origin (`mitm/mitm_serve.py`)
In the current reverse-engineering workspace, `mitm/mitm_serve.py` intercepts requests matching `server_list_ad.txt` and supplies a single-line synthetic server definition:

```python
# Defined at mitm/mitm_serve.py:112-115
SERVER_LIST_PAYLOAD = (
    b'North_America 1 1 1 North_America North_America '
    b'127.0.0.1:25000 127.0.0.1:25000 127.0.0.1:25000 10001 127.0.0.1:25000\n'
)
```

In earlier test configurations (`mitm/mitm_stdout2.txt` - `mitm_stdout7.txt`), the string was configured as:
```text
North_America 1 1 1 North_America North_America 10.0.2.2:25000 10.0.2.2:25000 10.0.2.2:25000 10001 10.0.2.2:25000
```
- `10.0.2.2` is the standard QEMU / Android emulator virtual alias for the host loopback interface (`127.0.0.1`).
- `25000` was chosen by the reverse engineering team as the port for local BigWorld LoginApp capture listeners (`=== LOGINAPP TCP/UDP :25000 LISTENING ===`).

---

## 4. Parser Specification (`ui/UILogin.py`)

Static analysis of the decompiled Python bytecode in `ui/UILogin.py` confirms the exact schema:

### 4.1 Positional Tokens
Tokens are space-separated (`.split(' ')`). Empty lines or lines with fewer than 9 tokens are ignored.

| Index | Field | Type | Description | Example |
| :---: | :--- | :--- | :--- | :--- |
| **0** | `zone` | `string` | Geographical Region / Zone identifier | `North_America` |
| **1** | `numberSt` | `int` | Server state index / population indicator | `1` |
| **2** | `netSt` | `int` | Network latency status flag | `1` |
| **3** | `serverSt` | `int` | Server status (0=Offline, 1=Normal, 2=Busy, 3=Full) | `1` |
| **4** | `name` | `string` | Localized server display name key | `North_America` |
| **5** | `oriName` | `string` | Internal server name | `North_America` |
| **6** | `telIP` | `string` | Primary Telecom IP & Port (`IP:PORT`) | `10.0.2.2:25000` |
| **7** | `cncIP` | `string` | Unicom / CNC route IP & Port | `10.0.2.2:25000` |
| **8** | `eduIP` | `string` | Education network route IP & Port | `10.0.2.2:25000` |
| **9** | `groupid` | `string` | Optional server group identifier | `10001` |
| **10** | `udpIP:udpPort` | `string` | Optional UDP ping/latency benchmark target | `10.0.2.2:25000` |

### 4.2 Primary IP/Port Assignment
In `ui/UILogin.py:174-177`:
```python
ipAndPort = server.get('tel')
(ip, port) = ipAndPort.split(':')
server['ip'] = ip
server['port'] = int(port)
```
The game engine reads `server.get('tel')` as the primary connection target.

---

## 5. Native Ingestion: `ServerConnection::logOnBegin`

When the user taps "PLAY", `ui.UILogin.doLoginGame()` passes the resolved `ip` and `port` to native code:

```arm64
// Binary: libclient_arm64.so @ 0x93c0e4 - 0x93c110
0x93c0e4: tst   w23, #0xffff      // Check if port (w23) is specified
0x93c0e8: mov   w8, #0x4e2d       // Default BigWorld port: 20013 (0x4e2d)
0x93c0ec: csel  w8, w23, w8, ne   // If port != 0 use port, else default 20013
0x93c0f0: rev   w8, w8            // Byte-swap to Big-Endian (network order)
0x93c0f4: lsr   w8, w8, #0x10     // Shift into sockaddr port position
0x93c0f8: sturh w8, [x29, #-0x5c] // Store in sockaddr_in structure
0x93c108: adrp  x0, #0x2a49000    // String base
0x93c10c: add   x0, x0, #0x363    // "ServerConnection::logOnBegin conneting to %s for loginAPP"
0x93c110: bl    #0x1cadbb4       // Format & log connection attempt
```

### 5.3 Fallback Mechanics
1. **If port is 0**: The native client automatically defaults to **20013** (`0x4e2d`), the official standard port defined by BigWorld Technology for `loginapp`.
2. **If port is specified (e.g. 25000)**: The native client accepts the port directly from the caller and initiates the UDP socket handshake to that port.

---

## 6. Summary Conclusion

1. **Origin of `10.0.2.2:25000`**: It originates strictly from `mitm/mitm_serve.py` serving a mock `server_list_ad.txt` response.
2. **Hardcoded Defaults in Binary**: The only hardcoded network constant in `libclient.so` is default port `20013` (`0x4E2D`).
3. **LAN Configurability**: Any arbitrary LAN IPv4 address (e.g., `192.168.1.100:20013` or `192.168.1.100:25000`) can be provided via `server_list_ad.txt` without modifying or patching `libclient.so`.
