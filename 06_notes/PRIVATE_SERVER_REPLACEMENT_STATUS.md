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
  **UPDATE (E2E-008)**: server now attempts a real reply (`ATTEMPT_BASEAPP_REPLY`),
  not capture-only. Four live iterations narrowed the wire model (BaseApp
  channel Blowfish-encrypts the WHOLE packet, unlike LoginApp's body-only
  encryption; the same `[flags][msgid][length][replyID][status]` inner
  shape is still expected, just inside the encrypted region) but the reply
  is still rejected — decrypts to wrong/garbage content, suggesting the
  BaseApp channel uses its OWN separate `EncryptionFilter`/key rather than
  reusing LoginApp's. See `07_ros_legacy_approach/END_TO_END_TEST_LOG.md`
  E2E-008 for the full 4-attempt record and next-step plan (live re-scan
  for a second key, timed within the ~5s single-shot retry window).
  **UPDATE (E2E-009)**: built the async live-rescan exactly as planned and
  found/fixed three real bugs in the on-device scan pipeline (shell
  quoting, a `dd` skip-arithmetic 32-bit overflow, and a `grep -b`
  line-relative-not-absolute offset quirk — all documented in E2E-009).
  Result is INCONCLUSIVE rather than a clean confirm/deny: the fixed
  pipeline reliably finds an exact 8-byte vtable-pointer match in the same
  large heap region, but a follow-up read at the reported address shows
  unrelated bytes each time, and three separate runs found three
  different addresses — consistent with that region being an
  actively-churning allocator arena rather than a stable object, making
  the two-step "locate on-device, then read" approach unreliable at this
  latency/scale (the host-side exact search step alone takes 3-13s to
  transfer one matching region). Per the coordinator's own standing
  instruction not to keep re-testing the same hypothesis indefinitely,
  this specific technique is parked (not disproven) and the recommended
  next avenue is re-examining `BASEAPP_LOGIN_SERIALIZATION.md`'s own
  remaining unknowns (status byte semantics, expected msgid, whether a
  generic Reply is even the right response shape for `baseAppLogin`)
  instead.
  **UPDATE (E2E-010)**: did exactly that. A live no-reply test
  (`ATTEMPT_BASEAPP_REPLY=0`) falsifies "BaseApp expects no reply at
  all" — the client hits the identical 5.0s timeout/error whether we
  reply wrongly or not at all, confirming a correctly-parsed reply is
  still needed to cancel Mercury's pending-request timer. Separately,
  re-reading `06_trace/BASEAPP_CELLAPP_FLOW.md` (pre-existing, high
  confidence) surfaced a previously under-weighted architectural point:
  the actual "login accepted" signal the client's game logic acts on is
  a **separate PUSH-style `createBasePlayer` `ClientInterface` message**
  (entity ID + `Account` property stream), not the generic Reply itself.
  **Revised model**: BOTH a working reply/ack (cancels the timeout) AND
  a `createBasePlayer` push (drives actual Account/Lobby progress) are
  needed — fixing the reply alone would only silence the error, not
  reach Account/Avatar/Lobby. A static attempt to locate
  `ServerConnection::createBasePlayer`'s exact wire-format handler via
  `scratch/xref_lib.py` did not converge within this pass's time budget
  (tooling limitation, not a negative finding about the function's
  existence — `BASEAPP_CELLAPP_FLOW.md` already cites its rodata
  strings from an earlier, undocumented-method pass).

## BLOCKED

1. **`script.npk` Python-layer patch (ROS-Legacy-Gate-1-style bypass)** —
   BLOCKED on two independent fronts: (a) general `7A 1C` stream cipher not yet broken;
   (b) Frida gadget injection on emulator hits native bridge translation module namespace limitation.
2. **BaseApp reply content (correct Blowfish key for the BaseApp channel)** — see PARTIALLY WORKING above; this is now the precise, narrow blocker, not the whole BaseApp reply concept.
3. **Account, Avatar, Lobby entity instantiation** — downstream of #2, NEXT IMPLEMENTATION TARGET once #2 is solved.

## RESOLVED (MOVED OUT OF BLOCKED)

1. **Mercury reply-ID correlation**: RESOLVED (Attempt K — 4-byte LE @ offset 5).
2. **First-LoginReply Blowfish key & cipher**: RESOLVED (Attempt L — key extracted from `EncryptionFilter` memory; cipher confirmed as `pc_variant` chaining per `0x989600` disassembly).

## NEXT IMPLEMENTATION TARGET

1. **Synthesize BaseApp `baseAppLogin` reply packet**: Formulate the response bundle for `BaseAppExtInterface::baseAppLogin` so the client completes the BaseApp handshake.
2. **Account entity initialization**: Respond to Mercury Channel messages to instantiate the `Account` entity and transition client into Lobby.
