# Private-Server Replacement Status (2026-09-15 audit pass)

Labels used in this document (this pass's own four-label set, per task
instruction): **CONFIRMED** / **INFERRED** / **HYPOTHESIS** / **BLOCKED**.
Existing cited docs may use this project's other established set
(CONFIRMED/STRONGLY SUPPORTED/INFERRED/UNKNOWN) — not rewritten here, only
cited.

Scope: what does `com.netease.chiji` v1117219 actually need from
now-dead production infrastructure, and what does this repo's own
local/LAN replacement already provide for each, as of this pass? See
`07_ros_legacy_approach/END_TO_END_TEST_LOG.md` (E2E-001 through E2E-004)
and `06_notes/FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md` for full evidence;
this document only aggregates and classifies, it does not re-derive.

## WORKING

- **HTTP/SDK auth tier** (`mitm/mitm_serve.py`, `mitm/session_store.py`):
  local HTTPS MITM (hosts-file/DNS + CA + iptables DNAT on the rooted
  emulator) intercepts NetEase SDK login calls
  (`/api/users/login/v2/sdk_token`, `/api/users/login/guest`) and mints
  distinct local `sess_<uuid4hex>` session IDs. CONFIRMED live-working,
  E2E-001, `mitm/captures/SERVE_B.txt` — client reaches the title screen
  logged in as "Guest" with PLAY available.
- **Server-list redirection**: client's server-list HTTP response is
  locally substituted to point LoginApp at the local server IP/port
  (172.16.1.2:25000). CONFIRMED (client's `LogOnParams` requests do arrive
  at the local UDP responder — E2E-001 PACKETS section).
- **Mercury/LogOnParams request framing (structure, not content)**: the
  273-byte RSA-OAEP `LogOnParams` bundle's outer envelope (15-byte header +
  256-byte ciphertext + 2-byte footer) and the plaintext object layout
  (`flags + 3 strings + digest16 + u32`, `06_trace/LOGONPARAMS_SERIALIZATION.md`)
  are CONFIRMED understood via disassembly + one dynamic capture. The
  server does not need to decrypt this yet for framing-level test purposes
  (only for content-level correctness, see BLOCKED below).

- **LoginApp UDP responder** (`mitm/local_baseapp_capture.py`): FULLY WORKING
  - Reply-ID correlation (Attempt K, 4-byte LE at wire offset 5): CONFIRMED.
  - Blowfish session key & cipher (Attempt L, `pc_variant` chaining, 24-byte padded body): CONFIRMED LIVE in E2E-007.
  - Client decodes target address (`172.16.1.2:25010`) cleanly with zero errors.
  - Client transitions immediately to BaseApp connection stage.

## PARTIALLY WORKING

- **BaseApp UDP handshake capture** (`mitm/local_baseapp_capture.py` on :25010):
  Captured 10 consecutive live `baseAppLogin` requests (24 bytes each, MsgID 0x00, bodyLength 11 bytes).
  Server is currently capture-only; needs reply packet formulation to advance to entity instantiation / Lobby.

## BLOCKED

1. **`script.npk` Python-layer patch (ROS-Legacy-Gate-1-style bypass)** —
   BLOCKED on two independent fronts: (a) general `7A 1C` stream cipher not yet broken;
   (b) Frida gadget injection on emulator hits native bridge translation module namespace limitation.
2. **Account, Avatar, Lobby entity instantiation** — NEXT IMPLEMENTATION TARGET.

## RESOLVED (MOVED OUT OF BLOCKED)

1. **Mercury reply-ID correlation**: RESOLVED (Attempt K — 4-byte LE @ offset 5).
2. **First-LoginReply Blowfish key & cipher**: RESOLVED (Attempt L — key extracted from `EncryptionFilter` memory; cipher confirmed as `pc_variant` chaining per `0x989600` disassembly).

## NEXT IMPLEMENTATION TARGET

1. **Synthesize BaseApp `baseAppLogin` reply packet**: Formulate the response bundle for `BaseAppExtInterface::baseAppLogin` so the client completes the BaseApp handshake.
2. **Account entity initialization**: Respond to Mercury Channel messages to instantiate the `Account` entity and transition client into Lobby.
