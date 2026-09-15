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

## PARTIALLY WORKING

- **LoginApp UDP responder** (`mitm/local_baseapp_capture.py`, "Attempt H"
  framing): receives the 273-byte request and sends back a shaped
  `LoginReply`-like packet. Framing-level send/receive is CONFIRMED
  working (server sees requests, sends replies, no exceptions). **But the
  client rejects every reply** — see BLOCKED, reply-ID correlation.

## BLOCKED

1. **Mercury reply-ID correlation — REGRESSED, currently the actual first
   blocking step** (earlier than the previously-primary Blowfish blocker).
   `06_trace/MERCURY_REPLY_ID_TRACE.md`'s "Attempt H, CONFIRMED LIVE,
   reproduced twice" claim did **not** reproduce in two fresh clean runs
   this project's own E2E-001 pass (10/10 failures each run,
   `Mercury::Nub::handleMessage(...): Couldn't find handler for reply id`).
   E2E-002 disproved the follow-up "sticky first counter" hypothesis
   (10/10 live failures, including the very first attempt). **CONFIRMED
   negative result**: wire offset `[5:7]`, zero-extended, alone, is not the
   client's real reply-id hashtable key, under every encoding hypothesis
   tested so far. The task-recommended fix (live `/proc/<pid>/mem` read of
   the `Nub` hashtable at the moment of send) is itself BLOCKED on
   `emulator-5554`: `su 0 dd`, `strace -p` (PTRACE_SEIZE), and
   `frida-server` attach all fail with root-independent ptrace/EIO errors,
   reproduced 3 ways across 2 sessions including after a full reboot
   (E2E-002 Sub-test A, E2E-003 Sub-test B). This is the single highest-
   priority NEXT IMPLEMENTATION TARGET (see below).
2. **First-LoginReply Blowfish key** — NOT SOLVED. See
   `06_notes/FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md` (CONFIRMED: the active
   decrypt key for the first reply is the client's own `RAND_bytes(4)`
   value, no path found that lets a server learn/predict it) and this
   pass's `06_notes/LOGONPARAMS_BLOWFISH_KEY_RECHECK.md` (a new,
   STRONGLY-SUPPORTED-but-not-CONFIRMED hypothesis, driven by the PC
   launcher's independently-confirmed finding, that the key is *also*
   packed as `LogOnParams`' 3rd string field for the server to read back
   out — pending live confirmation, which requires either resolving the
   reply-ID blocker above enough to get further live captures, or a
   working introspection tool, both currently blocked). Genuinely BLOCKED
   pending either tooling or a static call-graph proof.
3. **`script.npk` Python-layer patch (ROS-Legacy-Gate-1-style bypass)** —
   BLOCKED on two independent fronts, both re-confirmed this project's own
   prior pass (E2E-003/E2E-004): (a) the general `7A 1C`-magic stream
   cipher used by ~3,957 of `script.npk`'s entries (including
   `ui/UILogin.py`) cannot be statically broken (crib-drag disproved the
   simplest global-keystream hypothesis; the real per-file seed derivation
   is unrecovered); (b) dynamic (Frida) extraction is blocked on the
   emulator by a native-bridge dual-namespace module-visibility wall
   (arm64-v8a APK running under x86_64 translation — `libclient.so`
   invisible to `Process.enumerateModules()`), and this pass's attempt to
   route around that by testing on a genuinely-arm64 real phone
   (`SCG6S8GEX8PJJFD6`) was itself blocked by the orchestrating session's
   own security classifier before any repackaged APK could be written
   (flagged "[Security Weaken]" — Frida-gadget injection into the client
   APK, a closely related but distinct action from native `.so` patching,
   is evidently treated the same way). **This is a new blocker this pass,
   requiring a human decision** on whether/how Frida-based client
   introspection may proceed at all under the current safety posture,
   since both of this project's two live-instrumentation avenues
   (emulator ptrace, real-device Frida-gadget repackaging) are now closed.
4. **BaseApp, Account, Avatar, Lobby** — NOT YET REACHED (unchanged from
   task brief). All are downstream of #1/#2 above; no new evidence this
   pass changes this.

## OBSOLETE-NO-LONGER-NEEDED

- Nothing identified this pass as newly obsolete. The project's
  strategic reframing (local compatibility layer, not original-server
  reproduction) was already the operative approach going into this pass;
  no dead code paths calling unreachable production infra were found or
  removed this pass (Phase 4 audit was not separately re-run this pass —
  see NEXT below).

## NEXT IMPLEMENTATION TARGET

In priority order, given this pass's findings:

1. **Resolve the reply-ID correlation regression** — this is now
   confirmed to sit chronologically *before* the Blowfish blocker and
   must be fixed first on any future clean run. Both of this project's
   "obvious" next steps (live memory read, wire-level guessing) are
   exhausted/blocked as of E2E-002. A genuinely new angle is needed: e.g.
   a broader byte-offset **sweep** against the live client's own
   pass/fail signal (does it retry, or move on — the PC launcher's own
   proven method, see `PC_LAUNCHER_STUDY.md` §5.3), rather than
   continuing to guess a single documented offset. This does not require
   any blocked tooling — it is pure black-box wire-level experimentation
   against `local_baseapp_capture.py`, safe to attempt without
   introspection.
2. **Get a human decision on the Frida-gadget classifier block** — this
   pass hit a new wall (§ BLOCKED item 3) that is not resolvable by this
   agent alone: whether Frida-based client instrumentation (distinct from
   native `.so` patching) is in-scope at all going forward. Until
   resolved, both the script.npk-cipher and the deeper Blowfish-key
   confirmation paths that depend on live introspection remain closed.
3. Only after #1: re-attempt live confirmation of the
   `LOGONPARAMS_BLOWFISH_KEY_RECHECK.md` hypothesis (stringC = Blowfish
   key), since a working reply-ID fix would make repeated live LoginApp
   exchanges observable again, which is a prerequisite for any renewed
   memory-read or behavioral-inference attempt at the key.
