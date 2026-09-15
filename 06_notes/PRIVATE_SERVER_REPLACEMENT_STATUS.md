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
  **UPDATE (E2E-013)**: user/coordinator rebooted the shared emulator
  (`ldconsole.exe reboot --index 0`) and reapplied iptables DNAT rules;
  device confirmed healthy (`screencap` exit 0) at both start and end of
  this pass. Fresh key extraction re-validated on a THIRD independent
  process (`PID 4048`, key `b76ae6ae`, found in 3.9s). Live-tested the
  chain-IV fix with ONE paced iteration (not a rapid-fire loop, per new
  standing practice): still rejected, but with a **new, more specific
  error** — `Nub::processFilteredPacket(...): Packet (flags 183, size
  16) failed checksum (wanted 04040101, got 00000000)` — a genuinely
  different failure mode (checksum validation, not header/parse
  corruption) than every prior attempt, suggesting the chain-IV fix
  changed the decrypted content as expected but a checksum/CRC field
  this project has not yet accounted for may be the remaining gap.
  **Inconclusive, not confirmed.** Client CPU rose to 92-104% and stayed
  elevated for 13+ seconds even after this project's server was
  stopped — proactively force-stopped the game process before it could
  cascade into another ANR; `am force-stop` worked cleanly this time
  (unlike the E2E-012 incident), device left healthy and idle.
  **UPDATE (E2E-014)**: pursued the checksum lead statically — found a
  genuine, standard, zlib-compatible CRC-32 implementation in the binary
  (exact 256/256 table match, textbook update function), but its 4 known
  callers sit in a distant, likely-unrelated part of the code (probably
  asset/resource-name hashing), not confirmed as the packet checksum.
  The checksum error string's actual call site was confirmed unlocatable
  via 5 independent static methods (extending, not just repeating,
  `LOGIN_REPLY_MERCURY_ENVELOPE.md`'s own earlier "vestigial strings"
  finding). Separately, found and fixed a real bug while re-testing live
  (the `createBasePlayer` push's degenerate all-zero tail block was
  corrupting later retries' chaining state) and, with that understood,
  obtained a **clean negative result** for the chain-IV hypothesis
  itself: even correctly chaining from LoginApp's real last plaintext
  block, the FIRST BaseApp ack still decrypts to garbage (`bad flags
  5679`). The key-sharing finding from E2E-012 stands, but simple linear
  chaining-state-sharing is now disproven — the true relationship
  between the two channels' crypto state remains unresolved.
  **UPDATE (E2E-015)**: settled, via pure static disassembly (no live
  testing), whether BaseApp uses a distinct decrypt code path — it does
  NOT. Traced `BaseAppLoginRequest::initNetwork` and CONFIRMED BY BINARY
  that the new BaseApp `Channel` object is constructed holding the
  LITERAL SAME `EncryptionFilter` pointer read out of
  `ServerConnection+0x148` (not a copy, no new key material) — proving
  by construction, not coincidence, that both channels execute identical
  decrypt code. This closes out "different chaining mode for BaseApp" as
  an explanation. The remaining puzzle (same object/key/code, still wrong
  output) must be about the object's internal state at decrypt time,
  which this project cannot currently observe dynamically. See the new
  consolidated writeup, `06_notes/BASEAPP_CRYPTO_BLOCKER_SUMMARY.md`, for
  the full history in one place.

## BLOCKED

1. **`script.npk` Python-layer patch (ROS-Legacy-Gate-1-style bypass)** —
   BLOCKED on two independent fronts: (a) general `7A 1C` stream cipher not yet broken;
   (b) Frida gadget injection on emulator hits native bridge translation module namespace limitation.
2. **BaseApp reply content** — key is confirmed shared with LoginApp's (E2E-012), but neither IV=0 nor IV=chained-from-LoginApp produces correct decryption (E2E-008, E2E-014). A checksum/CRC field remains a candidate for a related/separate issue but its validation code could not be statically located despite 5 independent methods across two passes. This is now the project's most persistent open blocker on the path to Account/Avatar/Lobby — static analysis with current tooling appears exhausted; unblocking further likely requires either a fundamentally different static technique or working dynamic instrumentation (both native-bridge and classifier blockers currently prevent the latter).
3. **Account, Avatar, Lobby entity instantiation** — downstream of #2, NEXT IMPLEMENTATION TARGET once #2 is solved.

## RESOLVED (MOVED OUT OF BLOCKED)

1. **Mercury reply-ID correlation**: RESOLVED (Attempt K — 4-byte LE @ offset 5).
2. **First-LoginReply Blowfish key & cipher**: RESOLVED (Attempt L — key extracted from `EncryptionFilter` memory; cipher confirmed as `pc_variant` chaining per `0x989600` disassembly).

## NEXT IMPLEMENTATION TARGET

1. **Synthesize BaseApp `baseAppLogin` reply packet**: Formulate the response bundle for `BaseAppExtInterface::baseAppLogin` so the client completes the BaseApp handshake.
2. **Account entity initialization**: Respond to Mercury Channel messages to instantiate the `Account` entity and transition client into Lobby.
