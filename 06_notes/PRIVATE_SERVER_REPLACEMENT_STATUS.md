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
  **UPDATE (E2E-011)**: found it via an alternate path — decoded the
  FULL 122-entry `BaseAppExtInterface`+`ClientInterface` method
  registration table by walking every `BL` caller of the shared
  registrar function `0x98b30c` (`scratch/decode_clientinterface_table.py`),
  after confirming (via three independent methods: ADRP+ADD scan,
  raw-pointer scan, `.rela.dyn`/`.rela.plt` relocation scan) that
  `createBasePlayer`'s name string genuinely has zero direct code/data
  references — the string-xref method was a dead end, not a tooling gap.
  **CONFIRMED BY BINARY**: `createBasePlayer` = `[u16 bodyLength][body]`
  (VARIABLE_LENGTH_MESSAGE, same framing as `baseAppLogin`).
  **STRONGLY SUPPORTED**: message ID 4 within `ClientInterface`
  (bandwidthNotification=0, updateFrequencyNotification=1,
  setGameTime=2, resetEntities=3, createBasePlayer=4), by the same
  registration-order inference already validated for `baseAppLogin=0`.
  Implemented and live-tested a `createBasePlayer` push
  (`ATTEMPT_CREATEBASEPLAYER`) — still blocked by the same BaseApp-
  channel-key issue (both the reply/ack and the push fail to decrypt
  correctly with the same key), confirming the two blockers are
  sequential: the key issue must be solved before `createBasePlayer`'s
  content can be meaningfully tested at all.
  **UPDATE (E2E-012 — MAJOR)**: the "separate BaseApp key" hypothesis is
  now **OVERTURNED**. Found and fixed a fourth scan-pipeline bug (a
  racy two-step "find via download, then re-read key via a SEPARATE dd
  call" design — real memory churn between the two reads was returning
  wrong bytes even for a genuinely-confirmed match; fixed by extracting
  the key directly from the same already-downloaded snapshot). With this
  fix, the BaseApp channel's key was found **CONFIRMED identical** to
  LoginApp's, reproduced 10+ times across multiple scans on a fresh
  process. New hypothesis (implemented, not yet live-verified — see
  Environment Incident below): the two channels may share the literal
  same `EncryptionFilter` object, meaning `pc_variant` chaining state
  carries over from LoginApp's last message rather than resetting to
  IV=0 for BaseApp — `bf_encrypt()` now supports an `iv` override and
  the server chains from each host's last-sent plaintext block.
  **Environment incident**: this pass's own repeated malformed-packet
  test traffic most plausibly drove the client into a CPU-pegging
  (96-100% sustained) spin, cascading into a device-wide graphics-
  subsystem ANR on the shared emulator (also in use by another
  concurrent tool). Remediated by force-killing the game process
  (`su 0 kill -9`, CPU returned to idle) but `screencap`/`dumpsys window`
  remained hung afterward — the graphics subsystem itself may need more
  time or an emulator-level fix to recover; a full reboot was
  deliberately NOT attempted unilaterally given shared usage. Testing
  was paused before the chain-IV fix could be verified live.

## BLOCKED

1. **`script.npk` Python-layer patch (ROS-Legacy-Gate-1-style bypass)** —
   BLOCKED on two independent fronts: (a) general `7A 1C` stream cipher not yet broken;
   (b) Frida gadget injection on emulator hits native bridge translation module namespace limitation.
2. **BaseApp reply content (correct Blowfish chaining, key now confirmed shared)** — see PARTIALLY WORKING above; narrowed from "which key" to "which chaining IV", with a concrete untested fix ready to verify once the device is healthy again.
3. **Emulator graphics-subsystem hang** — `screencap`/`dumpsys window` unresponsive as of end of this pass; `adb shell`/`logcat`/`pidof` remain functional. Requires a health check before any further live testing.
3. **Account, Avatar, Lobby entity instantiation** — downstream of #2, NEXT IMPLEMENTATION TARGET once #2 is solved.

## RESOLVED (MOVED OUT OF BLOCKED)

1. **Mercury reply-ID correlation**: RESOLVED (Attempt K — 4-byte LE @ offset 5).
2. **First-LoginReply Blowfish key & cipher**: RESOLVED (Attempt L — key extracted from `EncryptionFilter` memory; cipher confirmed as `pc_variant` chaining per `0x989600` disassembly).

## NEXT IMPLEMENTATION TARGET

1. **Synthesize BaseApp `baseAppLogin` reply packet**: Formulate the response bundle for `BaseAppExtInterface::baseAppLogin` so the client completes the BaseApp handshake.
2. **Account entity initialization**: Respond to Mercury Channel messages to instantiate the `Account` entity and transition client into Lobby.
