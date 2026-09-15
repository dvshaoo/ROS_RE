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
*Last updated: 2026-09-15. Do not overwrite prior entries — append new
TEST_ID blocks only.*
