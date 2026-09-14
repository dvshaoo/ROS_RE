# ROS v1117219 — Private LAN Feasibility & Server Architecture Analysis

## 1. Executive Summary & Core Feasibility Verdict

### Can Rules of Survival Operate on a Private LAN Without the Original Backend?

> [!IMPORTANT]
> **Theoretical Verdict**: **YES, FEASIBLE IN PRINCIPLE**.
> 
> The client architecture does **not** rely on hardcoded public IP addresses, certificate pinning against fixed NetEase domain certs, or hardware dongles. It receives its network targets dynamically via plain text (`server_list_ad.txt`) and connects via standard BigWorld Mercury UDP protocols.
>
> **Practical Engineering Verdict**: **MASSIVE SERVER RE-IMPLEMENTATION REQUIRED**.
> 
> "Offline play" (playing entirely disconnected without any server) is **IMPOSSIBLE**. Rules of Survival is an authoritative client-server multiplayer game: terrain physics, entity instantiation, combat resolution, line of sight, and space management live entirely on the server.
>
> To play a match on a private LAN, a complete, compatible BigWorld Mercury server suite (`LoginApp`, `BaseApp`, `CellApp`) must be executed on a local machine.

---

## 2. Component Requirements Matrix

Every subsystem required to establish a functional local/LAN environment is classified below:

| Component | Classification | Layer / Host | Responsibility | Feasibility Assessment |
| :--- | :--- | :--- | :--- | :--- |
| **A. Android/Java Layer** | `CLIENT-ONLY` | Android Client | Launches `Launcher.class`, unpacks OBB, initializes `libclient.so`, manages graphics surface | **SOLVED**: Existing APK/OBB runs in LDPlayer. |
| **B. Authentication Layer (MPay/UniSDK)** | `REQUIRED` | Server-Side (HTTP) | Serves `/api/users/login/guest`, `/api/minors/` returning `minor_status: 102` (adult verified) | **SOLVED**: Lightweight Python HTTP server (`mitm_serve.py`) fulfills this. |
| **C. Server List Service** | `REQUIRED` | Server-Side (HTTP) | Serves `server_list_ad.txt` pointing to local LAN IP and UDP port (e.g. `192.168.1.50:20013`) | **SOLVED**: Single-line text payload serves target LAN IP. |
| **D. LoginApp Service** | `REQUIRED` | Server-Side (Mercury UDP) | Listens on port `20013` / `25000`. Returns BaseApp redirect | **REVISED (see `LOGONPARAMS_SERIALIZATION.md`/`LOCAL_SERVER_MINIMUM.md`)**: binary analysis confirms the client does not require the server to successfully decrypt `LogOnParams` to proceed — it only needs a plausible `LoginReplyRecord`. A local LoginApp does **not** need the real RSA private key; it can ignore the (undecryptable) credential block entirely and unconditionally reply with a synthetic BaseApp address. Still unresolved: exact byte layout of that reply record. |
| **E. BaseApp Service** | `REQUIRED` | Server-Side (Mercury UDP) | Handles `BaseAppLoginRequest`, instantiates `Account` entity, runs `handshake`, transitions to `Athlete` (Lobby) | **UNRESOLVED**: Requires BaseApp Mercury bundle parser and Python entity runtime. |
| **F. CellApp Service** | `REQUIRED` (for Battle)<br>`OPTIONAL` (for Lobby) | Server-Side (Simulation) | Manages `BattleGroundSpace`, runs physics/bullet trajectories, ticks game simulation, syncs player movements | **UNRESOLVED**: Requires 3D space manager and collision mesh evaluator. |
| **G. Entity Definitions** | `REQUIRED` | Shared (Client & Server) | 723 XML entity specifications (`Account.def.xml`, `Athlete.def.xml`, `Avatar.def.xml`, etc.) | **SOLVED**: Full decrypted XML catalog extracted in `05_entities/out/`. |
| **H. Mercury Protocol Stack** | `REQUIRED` | Server-Side (Network) | UDP bundle framing, unack resends, sliding window sequence numbers, Blowfish/Salsa session encryption | **FEASIBLE**: Standard BigWorld Technology protocol specification. |
| **I. Game Assets** | `CLIENT-ONLY` | Android Client | Models, textures, animations, sounds, map terrain, UI `.csb` files | **SOLVED**: Retained intact inside client APK and OBB packages. |
| **J. Matchmaking Engine** | `REQUIRED` (for Battle)<br>`OPTIONAL` (for Lobby) | Server-Side | Groups players, creates dynamic match spaces, spawns AI bots (`Robot.def.xml`) | **FEASIBLE**: In 1-player LAN test, can immediately allocate match space. |

---

## 3. Server Responsibilities That Must Be Recreated

To achieve a legitimate local game session on a private LAN without NetEase's proprietary infrastructure, the local server environment must provide:

### 3.1 HTTP Infrastructure Tier
1. **Patch / Version Bypass**: Returns `file_list` with 0 updates or matching client hash so the client skips content download.
2. **UniSDK MPay Authentication**: Returns valid JSON response with `minor_status: 102` and non-empty `sdk_token` / `login_token` to bypass the age verification dialog and trigger `onLoginSuccess`.
3. **Server List Dispatch**: Serves `server_list_ad.txt` pointing to the host's LAN IP address.

### 3.2 BigWorld LoginApp Tier
1. **UDP Socket Listener**: Listening on port `20013` (default) or `25000` (custom).
2. **Mercury Bundle Framing**: Unpacks raw incoming UDP packets into Mercury messages (`LoginInterface::login`).
3. **RSA Decryption**: Decrypts the `LogOnParams` buffer using the private key corresponding to `entities\loginapp.pubkey`.
4. **Login Reply**: Returns a `LoginReplyRecord` bundle containing:
   - Status code `0` (`LOGGED_ON`).
   - BaseApp address (`Mercury::Address`).
   - Symmetric session encryption key (used for channel encryption).

### 3.3 BigWorld BaseApp Tier
1. **BaseApp Login Processing**: Accepts `BaseAppExtInterface::baseAppLogin` bundle from the client.
2. **Base Player Creation**: Dispatches `createBasePlayer` message to instantiate the client's `Account` entity (ID e.g. `1001`).
3. **Handshake RPC**: Receives and acknowledges `Account.handshake` with `Account.onChannelLogin(0, characterDict)`.
4. **Lobby Entity Transition**: Instantiates `Athlete` entity (ID e.g. `1002`) and sends base property updates (nickname, level, cosmetics, currency).

### 3.4 BigWorld CellApp & Match Tier (To Reach Gameplay)
1. **Match Request**: Receives `reqMatch` from `Athlete` / `iRosMatchAvatar`.
2. **Space Allocation**: Creates `BattleGroundSpace` dynamic space instance.
3. **Cell Player Creation**: Sends `createCellPlayer` to instantiate `Avatar` entity.
4. **Spatial Streaming**: Streams terrain metadata, plane path, toxic circle radius/center, loot drops, and other players/bots to the client's Area of Interest.
5. **Movement Loop**: Consumes 20 Hz movement packets (`ServerConnection::addMove`) and validates kinematics.

---

## 4. Security & Anti-Tamper Boundaries

During native reverse engineering of `libclient.so`, the following protection mechanisms were observed:

### 4.1 Anti-Cheat Watchers (`iAntiCheating`, `iCheatSupervisor`)
- **Native Implementation**: Monitored in `05_entities/out/Avatar.def.xml` and `BattleGroundSpace.def.xml`.
- **Function**: Server-authoritative position validation. If a client attempts to teleport or move faster than defined speed caps, the server dispatches `ServerConnection::forcedPosition(entityId, pos)`.
- **LAN Implications**: A custom LAN server can simply execute clean standard physics without weaponized anti-cheat checks.

### 4.2 RSA Public Key Encryption (`loginapp.pubkey`)
- **Function**: Protects login credentials in transit between client and LoginApp.
- **LAN Implications**:
  - The client binary contains the public key `entities\loginapp.pubkey`.
  - To communicate without modifying the client, the local server must know the corresponding private key.
  - If the private key is permanently lost (held only on decommissioned NetEase servers), a clean LAN setup requires replacing `entities\loginapp.pubkey` in the client asset package with a newly generated RSA key pair.
  - Documented as an architectural boundary, not an exploit.

---

## 5. First Unresolved Technical Barrier

The immediate technical barrier preventing the game client from progressing past the Title Screen into a local session is:

> **Gate 2: BigWorld Mercury LoginApp Handshake on Port 20013 / 25000**
> 
> While the HTTP and Java/DEX tiers are fully mapped, the client's native `ServerConnection::logOnBegin` requires:
> 1. An active Mercury UDP server listening on port 20013 / 25000.
> 2. The exact binary packet serialization layout of `LogOnParams::addToStream`.
> 3. The RSA private key corresponding to `entities\loginapp.pubkey` to decrypt the client's login bundle and formulate a valid `LoginReplyRecord`.

---

## 6. 2026-09-14 Update — Deeper Native Verification

A follow-up pass went one level deeper into `03_lib/libclient_arm64.so` than the analysis
above, confirming §5 point 2 at the byte level and **revising** §5 point 3. Full detail in:

- **`LOGONPARAMS_SERIALIZATION.md`** — `LogOnParams::addToStream` fully mapped at the
  instruction level: confirmed field order/offsets, confirmed the string-length encoding
  scheme, and confirmed the encryption uses **RSA-OAEP** (not PKCS#1 v1.5 as previously
  assumed) with multi-block chunking. Critically: **only 4 of 6 fields are inside the RSA
  block** — the entity-defs digest and a trailing uint32 are always sent in plaintext.
- **Revision to §5 point 3**: the client does not require the server to actually decrypt
  the credential block to proceed past LoginApp — it only needs a plausible-shaped
  `LoginReplyRecord` in response. This means a local LoginApp prototype does **not** need
  the real private key at all. See `LOCAL_SERVER_MINIMUM.md` for the corrected staged plan.
- **`LOGIN_REPLY_RECORD.md`** — confirmed `LoginHandler::onLoginReply` function location and
  a 20-byte address-shaped record read from the reply; `SessionKey`/`AccountID` byte
  locations from the prior report were **not** independently confirmed and are marked
  UNKNOWN pending further work, rather than restated as fact.
- **`MERCURY_PACKET_MAP.md`** — directly extracted the client's `BaseAppExtInterface` and
  `ClientInterface` Mercury method name tables from rodata (`baseAppLogin`,
  `createBasePlayer`, `createCellPlayer`, `enterAoI`, etc.) — the first byte-verified
  artifact of the actual RPC surface, rather than names inferred from architecture alone.
- **New top-priority blocker**: `BaseAppLoginRequest`'s bundle serialization
  (`baseAppLogin`) was not yet traced — see `BASEAPP_LOGIN_SERIALIZATION.md`.

### 2026-09-14 (second pass) — `baseAppLogin` framing confirmed

Full send-chain located (`ServerConnection` orchestrator → `BaseAppLoginRequest` build →
reply-handler registration → `initNetwork` socket bind). CONFIRMED: `baseAppLogin` is a
Mercury VARIABLE_LENGTH_MESSAGE with a 2-byte length prefix, sent **exactly once** (no
client retry) with a 5-second reply timeout. The message body's field content remains
UNKNOWN — no `BinaryOStream`-style field-write call was located in the traced chain. Traced
whether a LoginApp-issued session key flows into this message: **no evidence found that it
does**, which tentatively (not conclusively) lowers the bar for row E in the matrix above —
see `BASEAPP_LOGIN_SERIALIZATION.md` §5 and `LOCAL_SERVER_MINIMUM.md` for full detail and
caveats.

### 2026-09-14 (third pass) -- object layout mapped, wire body still unresolved

A further pass fully decoded the client-side BaseAppLoginRequest tracker object
(120 bytes, every field's source traced) and **ruled out** the previous pass's "184-byte
object" lead as an unrelated logging function, correcting that speculation rather than
carrying it forward. The wire-level content of baseAppLogin's variable body remains
UNKNOWN after three passes of static analysis -- this is reported as a genuine limit of
symbol-free static analysis on this stripped 72MB binary, not a gap left unexamined. See
BASEAPP_LOGIN_SERIALIZATION.md section 5a/5b for the full trace and the concrete recommended
next step (dynamic instrumentation).

### 2026-09-14 (dynamic capture attempt) -- environment built, capture not yet obtained

A session attempted live Frida + local-server dynamic capture of baseAppLogin per
FRIDA_BASEAPP_LOGIN_CAPTURE.md. Key durable findings for future sessions:
- This LDPlayer instance's guest-to-host NAT gateway is **172.16.1.2**, not 10.0.2.2 or
  the host's real LAN IP -- several existing files/comments assuming those addresses are
  stale for this environment.
- /etc/hosts on the guest is not writable (read-only rootfs even as root); on-device
  iptables OUTPUT-chain DNAT rules are a more robust redirection method and were used
  instead (see FRIDA_BASEAPP_LOGIN_CAPTURE.md section 3).
- frida-server needs a specific version/arch combination to work on this image (16.2.1,
  x86_64 build -- not the arm64 build, and not 17.x) -- see section 2 of that document.
- Two real bugs in mitm/mitm_serve.py were found and fixed (total_list absolute-URI path
  matching, empty file_list ZeroDivisionError), advancing the client further through boot
  than previously recorded, but a further local-patch-server schema gap still blocks
  reaching PLAY. No baseAppLogin bytes were captured this session.

### 2026-09-14 (patch-gate fix) -- Retrieving patch lists 0.00% cleared, client reaches title screen

The blocker documented in the previous update (client stuck at "Retrieving patch lists
0.00%") is now RESOLVED -- see TOTAL_LIST_SCHEMA.md for the full evidence trail. Root cause
was two stacked bugs in the local plist response (empty file_list crashes the client's own
ResourcePatcher.py with ZeroDivisionError; per-file metadata must be flat name+"_suffix"
keys directly on the plist dict, not nested in total_list as previously assumed). Fixed in
mitm/mitm_serve.py and verified live: the client now boots fully through engine init and
reaches the title/login screen (Guest already signed in, User Agreement dialog showing).
No baseAppLogin traffic has been captured yet -- PLAY was not reached in this pass, per
that task's explicit scope (fix the patch gate only, do not chase further gates).
