# END_TO_END_TEST_LOG.md — Private Server Live Test Log

Append-only. Never overwrite a prior entry. Labels: CONFIRMED / STRONGLY
SUPPORTED / INFERRED / UNKNOWN per this project's convention.

---

## TEST_ID: E2E-001
- **DATE**: 2026-09-15
- **CLIENT_BUILD**: `com.netease.chiji` v1117219 (h45na), installed on LDPlayer9
  `emulator-5554`, already at PLAY/title screen at session start (no fresh
  install performed this pass)
- **SERVER_BUILD**: `mitm/mitm_serve.py` (git-tracked, HEAD `bbccdd3` +
  uncommitted `session_store.py` wiring already present), `mitm/
  local_baseapp_capture.py` unchanged since its last commit (mtime
  2026-09-15 09:56, predates this test's process start at 09:56:40 local —
  code confirmed current, not stale)
- **CHANGE**: None — this is a REGRESSION/VERIFICATION pass only. No server
  or client files were modified before this test. Existing on-device
  iptables OUTPUT DNAT rules (tcp 80/443/8443 -> 172.16.1.2, udp 25000/20013
  -> 172.16.1.2) were already present from a prior session and were verified
  present (`su 0 iptables -t nat -L OUTPUT -n`), not re-applied.
- **EXPECTED**: Per `06_trace/MERCURY_REPLY_ID_TRACE.md` §4-5 ("Attempt H —
  current default"), tapping PLAY should: (1) client mints per-session HTTP
  auth tokens via `mitm_serve.py` (already CONFIRMED working, see below),
  (2) `ServerConnection::logOnBegin` sends a 273-byte RSA-OAEP `LogOnParams`
  bundle to `172.16.1.2:25000`, (3) `local_baseapp_capture.py`'s Attempt H
  responder echoes the 2-byte wire counter at request offset `[5:7]`
  zero-extended as the 4-byte replyID plus a 20-byte `LoginReplyRecord`
  body, (4) per the existing doc's own "CONFIRMED LIVE, reproduced twice"
  claim, the client's `Mercury::Nub::handleMessage` should find a handler
  for that replyID and proceed to `LoginHandler::onLoginReply` /
  `checkScriptBaseAppAddr` (address garbled due to the still-unresolved
  Blowfish key, but framing/dispatch should succeed).

- **ACTUAL**:
  - **HTTP/session tier (Phase 1 regression)**: **PASS, live-verified for
    the first time this project has had a reachable device for it.**
    `mitm/captures/SERVE_B.txt` 14:40:30 shows two `/api/users/login/v2/
    sdk_token` calls and one `/api/users/login/guest` call, each returning a
    **distinct** `sess_<uuid4hex>` session id (`sess_8bd...`, `sess_d07...`,
    `sess_684...`, prefixes only — redacted per project policy). Client
    screenshot (`06_notes/live_check_1789455100.png`) confirms the client is
    at the title screen showing "Guest" logged in with PLAY available —
    this closes the previously-UNRESOLVED "client accepts the HTTP
    response" / "client continues through login flow" rows from the
    `PRIVATE_SERVER_ADAPTATION_PLAN.md` §Phase-1 scorecard, which could not
    be tested in the prior pass (no device was reachable then).
  - **LoginApp UDP framing/reply-ID correlation (Phase 4/5 boundary)**:
    **REGRESSION from documented status — did NOT reproduce the "CONFIRMED
    LIVE" Attempt H success, in TWO independent fresh runs this pass.**
    Both runs (`06_notes/logcat_live_test_1.txt` 14:52:37-46,
    `06_notes/logcat_live_test_2.txt` 14:54:46-55) show:
    - `ServerConnection::logOnBegin conneting to 172.16.1.2:25000` fires.
    - `PublicKeyCipher::setKey: Loaded 1024-bit public key` fires (this
      exact string mismatch vs. the wire-confirmed 2048-bit RSA modulus is
      an already-documented, already-explained log-string quirk per
      `06_trace/MERCURY_PRE_LOGIN_KEY_ESTABLISHMENT.md` — not a new finding,
      not re-investigated further this pass).
    - For **every one of 10 retries** in both runs, almost immediately after
      each request/reply exchange (as fast as 21ms in run 2), the client
      logs `Mercury::Nub::handleMessage( 172.16.1.2:25000 ): Couldn't find
      handler for reply id 0x0000XXXX (maybe it timed out?)` — the exact
      failure mode `MERCURY_REPLY_ID_TRACE.md` §5 says Attempt G/H's fix
      made "disappear entirely". The logged `0x0000XXXX` value in every
      case matches exactly the counter this pass's server code echoed back
      (verified by cross-referencing `mitm/captures/BASEAPP_LOGIN_CAPTURE.txt`
      timestamps against the logcat, e.g. server sent `replyID=0x00002993`
      at 14:52:37, client logs "Couldn't find handler for reply id
      0x00002993" at 14:52:37.792).
    - Both runs end identically: `RetryingRequest::handleException( login ):
      Final attempt of 10 has failed (REASON_TIMER_EXPIRED), aborting` then
      `ServerConnection::logOnComplete: Logon failed
      (Mercury::REASON_TIMER_EXPIRED)`. The client falls back to the title
      screen (no crash, no hang) — confirmed by
      `06_notes/after_play_tap_2.png` showing the "Logging in" spinner mid-
      attempt in run 1.
    - The near-instant timing (21-430ms between send and rejection) rules
      out simple network/processing latency as the cause — the reply
      demonstrably arrives before the client would plausibly have already
      cycled past that specific attempt's registered handler on a pure
      timing basis, yet lookup still fails on the ID alone. This means the
      value at request wire offset `[5:7]` is **not reliably** the value
      the client's Mercury::Nub hashtable is keyed on, despite the
      documented single successful-looking correlation this project
      recorded earlier. **INFERRED**: the earlier "CONFIRMED LIVE,
      reproduced twice" result for Attempt H may have depended on
      incidental state (e.g. a stale registered handler bucket from an
      immediately-prior successful-looking exchange) rather than a durable,
      correct understanding of the real correlation key — this pass's two
      clean, fresh single-attempt runs both failed 10/10.

- **PACKETS**: `mitm/captures/BASEAPP_LOGIN_CAPTURE.txt` 14:52:37-14:52:40
  (run 1, 10 RECV/SENT pairs) and (run 2, not separately dumped to a new
  file — same live capture file, contiguous appended lines after the run-1
  block, replyIDs 0x2993-0x299c for run 1); raw request bytes are 273-byte
  RSA-OAEP `LogOnParams` bundles unchanged in shape from prior captures
  (`01 00 00 04 01` + 2-byte counter + `29 01 00 00` + `2b 00 00 00` +
  256-byte RSA ciphertext + 2-byte footer, matching
  `06_trace/LOGONPARAMS_SERIALIZATION.md`'s established layout).
- **CLIENT_STATE**: Title screen -> "Logging in" spinner (both runs) ->
  reverts to title screen with PLAY re-enabled after ~9s timeout. Does NOT
  reach `LoginHandler::onLoginReply` or `checkScriptBaseAppAddr` in either
  run (absent from both logcat captures — grep confirms zero hits).
- **SERVER_STATE**: `local_baseapp_capture.py` (PID 24528, running since
  09:56 this session) correctly received all 20 request packets (10 per
  run) and sent 20 Attempt-H-shaped replies; no server-side exceptions
  logged.
- **RESULT**: **FAIL at the LoginApp reply-ID correlation step** — this is
  a step *earlier* than the already-known Blowfish blocker (§13 of
  `PRIVATE_SERVER_ADAPTATION_PLAN.md`), since the client never reaches the
  Blowfish-decrypt call this run. Phase 1 (session/auth) reconfirmed PASS
  live. Phases 2-3 (server list -> LoginApp reachability) reconfirmed PASS
  live (the 273-byte requests do arrive). Phase 4/5 boundary (reply-ID
  correlation) is the new, more precise failure point identified this pass
  — more precise than before because this project now has (for the first
  time) a reachable live device to test the existing Attempt H code against
  fresh runs, rather than relying on the single historical "confirmed
  twice" result.
- **NEXT_ACTION**: Do not re-guess the replyID field. Use a live
  `/proc/<pid>/mem` read of the Nub's reply-tracking hashtable (bucket array
  at `Nub+0x88`, count at `Nub+0x90`, per `06_trace/MERCURY_REPLY_ID_TRACE.md`
  §3's already-disassembled lookup structure) **at the moment
  `logOnBegin` sends each request**, to capture the actual key value the
  client inserts into its own table, rather than continuing to assume it
  equals request wire offset `[5:7]`. This is the same class of technique
  (`/proc/<pid>/mem` read at a known static address, keyed off already-
  disassembled struct offsets) the task's Phase 5 instructions call for
  against the Blowfish key — it should be tried here FIRST, since this
  reply-ID correlation blocker sits chronologically before the Blowfish
  blocker and must be solved before Blowfish is ever reachable again on a
  clean run.

---

## TEST_ID: E2E-002
- **DATE**: 2026-09-15 (same day, follow-on pass to E2E-001)
- **CLIENT_BUILD**: same running process as E2E-001, `com.netease.chiji` PID
  `22345` on `emulator-5554`, not relaunched between sub-tests below (same
  ASLR base observed throughout: `Nub` object at `0x76384b971000` in every
  sub-test that reached it, consistent with one continuous process lifetime,
  not evidence of a real anomaly)
- **CHANGE**: (1) `mitm/local_baseapp_capture.py` `DEBUG_BADFLAGS=1` run to
  capture a fresh live `Nub` pointer for a `/proc/<pid>/mem` read attempt;
  (2) new `ATTEMPT_J` mode added to the same file (sticky first-counter
  cache, see in-file comment) to test the hypothesis that Mercury retries
  reuse one fixed reply id rather than a new one per retry.

- **SUB-TEST A — live `/proc/<pid>/mem` read of the Nub hashtable
  (`Nub+0x88`/`+0x90`), the task's own recommended next step**:
  **BLOCKED — could not be performed this pass, root cause identified and
  reproduced three independent ways, not a one-off flake**:
  1. `su 0 dd if=/proc/22345/mem bs=1 skip=$((NUB+0x88)) count=8` →
     `dd: /proc/22345/mem: I/O error` (confirmed on both `bs=1` and
     page-aligned `bs=4096` variants, both immediately (~120ms) after
     capturing a fresh live `Nub` pointer via the existing `DEBUG_BADFLAGS`
     technique and after a delay — same result both times, ruling out a
     pure timing race).
  2. `su 0 strace -p 22345` → `ptrace(PTRACE_SEIZE, 22345): Operation not
     permitted`, **even though** `su 0 id` reports `uid=0(root)
     gid=0(root) ... context=u:r:su:s0` (genuine root, not a restricted
     shell).
  3. `frida-server-16 -l 0.0.0.0:27042` (existing project binary,
     `/data/local/tmp/frida-server-16`, previously used successfully in
     this project per `06_trace/MERCURY_MESSAGE_ID_TRACE.md`'s own
     live-memory-dump claims) starts and accepts a remote connection, but
     `device.enumerate_processes()` throws `unable to perform ptrace
     getregs: Device or resource busy` and the frida-server process itself
     is gone (crashed, no /data/local/tmp/frida_start.log output) by the
     next check — a direct `device.attach(22345)` afterward fails with
     `the connection is closed`.
  - **Ruled out as the cause**: SELinux is `Permissive` (denials are
    logged, not enforced — confirmed via `getenforce` and cross-checked
    against `dmesg`/`logcat` `avc: denied ... permissive=1` lines, i.e. even
    the denials that exist are non-blocking); the target process has
    `Seccomp: 0` and `TracerPid: 0` (not sandboxed, not already traced);
    `/proc/sys/kernel/yama/ptrace_scope` does not even exist on this
    kernel (no Yama LSM loaded to restrict ptrace scope). None of the
    normal, checkable ptrace-restriction mechanisms are active, yet
    `PTRACE_SEIZE` from genuine root still returns `EPERM` and
    `/proc/<pid>/mem` reads still return `EIO` at the exact target
    address on every attempt.
  - **INFERRED**: something below the visibility of standard Android
    tooling — most plausibly LDPlayer's own hypervisor/virtualization
    layer, or a non-Yama in-kernel ptrace guard specific to this emulator
    build — is denying ptrace attach to this specific process even from
    real root, in this session, on this device state. This directly
    contradicts the capability this project's own prior documents
    (`06_trace/MERCURY_MESSAGE_ID_TRACE.md`) recorded as working on
    2026-09-15 earlier in the same nominal day. **Not reproduced as a
    working capability this pass despite three different tools/techniques
    all failing the same underlying way.** This is reported as a genuine,
    corroborated environmental blocker, not a skill or effort gap — it
    directly explains why this pass could not execute the task's own
    literal "immediate next step" instruction (the live `Nub+0x88` memory
    read) and had to fall back to wire-level empirical testing instead
    (Sub-test B below).

- **SUB-TEST B — `ATTEMPT_J` sticky first-counter hypothesis (wire-level,
  no memory read required)**: Modified `serve_loginapp_udp_responder` to
  cache the FIRST counter value seen from a given `(ip,port)` source and
  echo that SAME cached value for every subsequent retry from that source,
  instead of each retry's own incremented counter (rationale: if Mercury
  retries logically resend one pending request whose reply id is assigned
  once, echoing each retry's own incrementing counter would only ever
  accidentally match retry #1, if it matches at all). **Result: FAIL,
  10/10, live-verified** (`emulator-5554`, PID `22345`, fresh PLAY tap,
  15:08:24–28 local). Every one of the 10 retries — including the very
  first — was rejected: `Mercury::Nub::handleMessage( 172.16.1.2:25000 ):
  Couldn't find handler for reply id 0x000029cf` repeated 10 times,
  **identical value each time** (confirming the cache worked exactly as
  coded — this is not a bug in the test, the server really did echo
  0x29cf for all 10 replies). Since even the reply matching retry #1's own
  counter value fails, this **disproves** both (a) the "sticky/fixed
  reply id across retries" hypothesis and (b) more importantly, the
  underlying premise carried since `MERCURY_REPLY_ID_TRACE.md` that wire
  offset `[5:7]`'s counter equals the client's real internal reply-id key
  at all, for any retry including the first. **CONFIRMED (negative
  result)**: `data[5:7]`, zero-extended, alone, is not sufficient to
  satisfy the `Mercury::Nub::handleMessage` hashtable lookup, under any of
  the three encoding hypotheses tested across E2E-001 and E2E-002
  (per-retry counter, sticky first counter). Code kept in
  `mitm/local_baseapp_capture.py` behind `ATTEMPT_J=1`, off by default
  (Attempt H remains the default per its still-correct framing-level
  contribution), clearly commented as a disproven hypothesis rather than
  silently removed.

- **RESULT**: Both of this pass's two concrete attack angles on the
  reply-ID blocker — (A) the task's own recommended live memory read, and
  (B) the cheapest remaining wire-level hypothesis — are now closed out
  with honest negative/blocked results. (A) is environmentally blocked
  (ptrace denied to genuine root, three tools, three independent
  failures). (B) is empirically disproven (10/10 live). This leaves the
  reply-ID correlation blocker **without a known, testable-without-deeper-
  tooling next static/dynamic angle** — see NEXT_ACTION.

- **NEXT_ACTION**: Per the task's own explicit, standing authorization to
  pivot to a ROS-Legacy-style client-observable-behavior replacement when
  native reverse engineering is "slow or ambiguous" (both now true, and
  now additionally blocked by an environment-level ptrace restriction this
  pass could not lift): the highest-value next experiment is a
  **Python-layer (`script.npk`) shortcut** at `ui.UILogin.doLoginGame()` —
  the confirmed call site (`06_trace/ROS_LOGIN_PLAY_TRACE.md` §8.1) that
  invokes `ServerConnection.logOnBegin(host, port, username, password)`.
  Rather than continuing to guess at the native `Mercury::Nub`'s internal
  reply-id key with no working introspection tool, patch this Python call
  site (decompile/recompile `script.npk`, already-documented AES
  key/tooling per `MASTER_SPEC.md` "AES Key" section) to skip the native
  Mercury LoginApp/BaseApp handshake entirely for our private server case
  and drive the client directly into its own post-login UI state using
  whatever client-side call the Lobby/hall screen construction already
  uses once a real `onLoginReply`/`createBasePlayer` sequence would
  normally have fired — i.e. the same *pattern* ROS Legacy's Gate 1 used
  (a client-side shortcut calling the game's own success-path API
  directly) but applied one stage later in the flow (post-LoginApp/
  BaseApp, not post-SDK-auth, since the SDK-auth stage is already
  genuinely solved via the HTTP tier). This is a legitimate, explicitly
  authorized architectural pivot — not a fake success state — provided it
  is implemented as calling the client's *real* subsequent-stage
  entrypoints (not merely spoofing a "you're in the lobby" screen without
  backing state), and must be labeled `CLIENT_MODIFIED: YES` /
  `APPROACH_TAKEN: ros-legacy-style-replacement` honestly in any future
  report, never presented as the faithful protocol working. Locating the
  exact Lobby-entry call this Python shortcut should jump to is the
  concrete next task, not yet started this pass.

---
*Last updated: 2026-09-15. Do not overwrite prior entries — append new
TEST_ID blocks only.*
