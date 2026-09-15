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

## TEST_ID: E2E-003
- **DATE**: 2026-09-15 (same day, third pass — user explicitly authorized
  "ibypass na natin lahat para makapaglaro na offline" / bypass everything
  necessary to make it playable offline, formally sanctioning
  CLIENT_MODIFIED work)
- **GOAL THIS PASS**: Implement the E2E-002-recommended pivot: patch
  `ui.UILogin.doLoginGame()` (or the real equivalent) in `script.npk` to
  short-circuit the native Mercury LoginApp/BaseApp handshake. **Result:
  this specific plan hit a hard, pre-existing, well-documented blocker
  before any patch could be written — see below — and the pass pivoted to
  investigating whether a device/environment reboot could unblock the
  earlier native memory-introspection path instead. Net result: no
  client-observable progress past the title screen this pass; several
  significant environmental findings recorded; one real incident (OBB
  files deleted by `adb uninstall`) caused and fully recovered from.**

### Sub-test A: script.npk crypto pipeline (static)
Attempted to decrypt `ui.UILogin`'s `script.npk` entry (hash `0xc6a16d1c`,
already located and dumped to `scratch/uilogin.raw` in an earlier session)
using the AES-128-ECB key documented in `MASTER_SPEC.md` (`w5q6^C04SW!@e}ad`
at `0x02B504E0` in `libclient_arm64.so`). **Result: FAIL.** AES-ECB decrypt
(whole-buffer and partial-block-plus-plain-tail variants) produced no valid
zlib stream or recognizable Python marshal header for either `UILogin.py`
or a second, independently cross-checked module (`patch/patch_mgr.py`,
whose encrypted/decrypted sizes are both stated in `MASTER_SPEC.md`).
**Root cause found**: re-reading `bridge/RESULT_T11.md` sec3 (already in
the repo, not re-derived) shows the AES-128-ECB key is **only** used for a
tiny 2-entry sub-container (hash `0xFB54F059`, 3,924B each) — it is
**explicitly NOT** the general-purpose cipher for the other 3,957
`script.npk` entries (magic `7A 1C`), which use "an additive stream cipher
... keystream generator... embedded in the proprietary compiled Python
runtime" and are recorded there as **"BLOCKED for offline standalone
extraction without Python VM execution... [requires] Dynamic interception
(via Frida hook on `package.get_file` / `PyMarshal_ReadObjectFromString`)."**
`MASTER_SPEC.md`'s own "Decrypted Module Hashes" table (listing
`patch/patch_mgr.py` etc. with plausible decrypted sizes) must therefore
have been produced by that same dynamic/Frida method in an earlier session,
not by the static AES path this pass mistakenly tried first. **CONFIRMED**:
static decryption of the general script.npk entry class is cryptographically
infeasible without dynamic instrumentation, exactly as already recorded in
this repo before this pass (this pass just re-discovered/re-confirmed it
the hard way instead of reading `RESULT_T11.md` first).

### Sub-test B: dynamic script.npk decryption via Frida (attempt)
Since static decryption is blocked, tried Frida (already present on device:
`/data/local/tmp/frida-server-16`, `frida-server-x64`) to dynamically hook
the target process and either dump decrypted bytecode or read the Mercury
`Nub` hashtable directly (the original E2E-002 blocker). **Result: FAIL**,
and reproducibly so:
- `strace -p <chiji-pid>` (real root, `su 0`) **succeeds** and prints live
  syscalls — ptrace attachment itself works against this exact process.
- `su 0 dd if=/proc/<pid>/mem ...` at a live, confirmed-mapped address
  (cross-checked against `/proc/<pid>/maps`, which does show the address
  inside a large `[anon:libc_malloc]` region) still returns `I/O error`
  every time. **INFERRED**: this kernel's `/proc/pid/mem` read path
  requires the READING process itself to hold the active ptrace
  relationship (not just "any root process"), consistent with
  `mm_access()`/`ptrace_access_vm()` returning `-EIO` for an unattached
  reader even when ptrace() itself is permitted for other callers.
- `frida-server` **crashes** (process disappears, no log output) the
  moment `device.attach(<chiji-pid>)` is called against this specific
  process, both via raw `enumerate_processes()` and via a direct
  `attach(pid)` call. Reproduced twice, both after a full emulator reboot
  (see Sub-test C) that had otherwise restored ptrace capability for
  unrelated processes (confirmed: `strace -p <system_server-pid>` worked
  cleanly). This crash is specific to attaching to the game process, not a
  general frida-server malfunction.
- **frida-gadget** (in-process instrumentation, no external ptrace needed)
  was tried as a workaround by installing the project's existing
  pre-built `01_apk/base_frida_signed.apk` (gadget already embedded from
  an earlier session). This DID successfully load (`Frida: Listening on
  127.0.0.1 TCP port 27042`, confirmed live JS execution via
  `Process.enumerateModules()` returning real results) — a genuinely new,
  working capability this pass (external ptrace/frida-server is not
  needed for basic in-process script execution). **However**: the app
  never progressed past the earliest native-linker stage (6 native
  modules loaded — `libc`, `libdl`, `libm`, `liblog`, `libc++`,
  `ld-android` — for over 90 seconds, `libclient.so` never appeared),
  because `tools/frida-gadget.config`'s baked-in
  `"interaction":{"type":"script","location":"http://192.168.100.8:8080/..."}`
  is a stale/non-standard config left over from an earlier session's
  different network topology; it appears to block early process
  init waiting on that fetch (attempts to make the URL reachable via a new
  iptables OUTPUT DNAT rule to `172.16.1.2:8080` did not help — zero
  connection attempts observed device-side at all, `netstat`/conntrack
  showed nothing, so the guest may not even be able to originate a
  connection to `192.168.100.8` from this specific process/init stage).
  **UNKNOWN, not resolved this pass**: the exact reason this specific
  gadget config hangs early process init; not investigated further given
  time budget — a rebuilt gadget config (`"type":"listen"`, the frida
  default, no network fetch dependency) is the obvious next fix and was
  not yet tried.

### Sub-test C: full emulator reboot (recovery attempt for Sub-test B's ptrace blocker)
Rebooted `emulator-5554` (`adb reboot`) specifically to test whether
E2E-002's ptrace/`/proc/pid/mem` blocker was a transient LDPlayer/kernel
state rather than a permanent restriction. **Result: PARTIALLY POSITIVE**
— `strace -p <pid>` against both `system_server` and the freshly-relaunched
game process succeeded post-reboot (this had failed pre-reboot in
E2E-002). However, raw `/proc/pid/mem` reads still failed (EIO, see Sub-test
B), so the reboot fixed ptrace-attach permission but did **not** fix the
unattached-reader `/proc/pid/mem` restriction — these are evidently two
separate gates. iptables OUTPUT DNAT rules were correctly detected as wiped
post-reboot and were successfully reapplied (`tcp:80/443/8443`,
`udp:25000/20013` → `172.16.1.2`) per this project's already-documented
reboot-recovery procedure — no new information there, procedure confirmed
still accurate.

### Incident: OBB files deleted by `adb uninstall`, fully recovered
While testing the frida-gadget APK (Sub-test B), `adb uninstall
com.netease.chiji` followed by reinstalling the project's backed-up
"currently installed" APK left the app unable to start
(`FileNotFoundException: /storage/emulated/0/Android/obb/com.netease.chiji/
main.1117219.com.netease.chiji.obb (No such file or directory)`) — **this
LDPlayer/Android configuration deletes the app's OBB expansion files on
`adb uninstall`, not just app data**, which is new, useful operational
knowledge for future sessions (prior sessions' notes did not record this).
**Recovery (CONFIRMED, fully successful)**: both OBB files were still
present in the repo's own `04_obb/` directory (used throughout this project
for static analysis) and were `adb push`-ed back to
`/storage/emulated/0/Android/obb/com.netease.chiji/` (main: 1,977,238,353B,
patch: 1,523,738,987B, ~2.5 min total transfer), permissions fixed
(`chmod 755`), and the app was confirmed to boot cleanly afterward all the
way back to the title screen with "Guest" logged in and PLAY available
(`scratch/title_final2.png`). **No data was permanently lost.** The
originally-installed working APK (`scratch/currently_installed_backup.apk`,
pulled before any changes this pass, 95,561,326 bytes, confirmed identical
in size to `01_apk/base_proxy_v5_signed.apk`) was reinstalled and is the
currently-running configuration — device is left in the SAME working state
it was in before this pass started, modulo the OBB round-trip.
**LESSON FOR FUTURE SESSIONS**: never `adb uninstall` this package without
first confirming the OBB files are backed up outside the device (they are,
in this repo's `04_obb/`, so this specific risk is now fully mitigated
going forward) — prefer `adb install -r` (reinstall, keeps data/obb) over
uninstall+install when swapping APK builds, unless a clean-slate install is
specifically required.

### RESULT / NEXT_ACTION
Both concrete technique paths for the user-authorized client-patch pivot
(static script.npk crypto, dynamic Frida-assisted script.npk decryption or
memory read) hit real, reproducible blockers this pass, distinct from
E2E-002's blocker:
- Static script.npk decrypt: cryptographically infeasible (confirmed
  pre-existing project finding, re-confirmed this pass).
- Dynamic (frida-server, external ptrace): frida-server crashes on attach
  to this specific process.
- Dynamic (frida-gadget, in-process): loads and runs, but the specific
  pre-built config hangs process init before `libclient.so` loads.

**NEXT_ACTION, in priority order**:
1. **Fix the frida-gadget config** — rebuild/repackage with
   `{"interaction":{"type":"listen","listen_address":"127.0.0.1:27042"}}`
   (frida's own default, no network fetch dependency) instead of the stale
   custom `"location"` HTTP-fetch config. This is a small, self-contained
   fix (edit one config asset inside the APK, or rebuild the gadget-injected
   APK fresh from the CURRENTLY working base rather than reusing the
   Sep-14 `base_frida_signed.apk`) and, if it works, unblocks BOTH the
   original native reply-ID memory-read investigation (E2E-002) AND
   dynamic script.npk decryption (Sub-test A here) via the exact
   `PyMarshal_ReadObjectFromString` hook `RESULT_T11.md` already
   recommends — potentially resolving the actual root blocker with a
   single working tool instead of requiring an invasive Python-logic
   rewrite.
2. If gadget-based introspection works: use it to (a) dump the real
   `LoginApp` reply-id key live (finally answering E2E-002's open
   question with a faithful fix, no client behavior change needed beyond
   the instrumentation itself), OR (b) dump `ui.UILogin`'s decrypted
   bytecode for a genuine, informed `doLoginGame()` patch as originally
   planned.
3. If gadget-based introspection still does not pan out in a further
   timeboxed attempt: fall back to the native `.so` patch path explicitly
   pre-authorized by the user as a last resort — two small, already
   disassembly-located patch targets (`Mercury::Nub::handleMessage`'s
   hashtable-match branch at `0x991f24`/`0x991f34`, and/or
   `EncryptionFilter::decrypt`'s call site at `0x989600`) are far more
   surgical than reconstructing an entire alternate Python-side
   Account/Avatar/Lobby flow, and reuse the ALREADY-CONFIRMED-correct
   BaseApp Mercury framing this project has built (Attempt H) rather than
   discarding it.

---

## TEST_ID: E2E-004
- **DATE**: 2026-09-15 (same day, fourth pass). **Scope correction from the
  user, logged verbatim**: native `.so` binary patching is explicitly
  WITHDRAWN from this project's authorized options (blocked by the
  orchestrating session's own security classifier as a "security weaken"
  action) — the `Mercury::Nub::handleMessage`/`EncryptionFilter::decrypt`
  native patch idea from E2E-003's NEXT_ACTION is **retracted, not to be
  attempted or proposed again**. All further work is script.npk
  (Python)-level only, ROS-Legacy-Gate-1-style, per: "ayusin natin lahat
  ibypass gaya ng ginawa ng ros legacy... tanggalin ang pag-modify ng
  script[.so]" (fix everything, bypass it like ROS Legacy did, remove any
  native `.so` modification from the plan).

### Sub-test A: fix the frida-gadget config bug (from E2E-003)
**CONFIRMED FIXED, real progress.** The stale
`{"interaction":{"type":"script","location":"http://192.168.100.8:8080/..."}}`
config was not actually bundled inside the APK zip (`01_apk/
base_frida_signed.apk` contains only `lib/arm64-v8a/libfrida-gadget.so`,
no config asset) — it must have been placed directly on the device's
extracted native-lib path by an earlier session and was lost. Root cause
confirmed: frida-gadget looks for a file literally named
`libfrida-gadget.config` next to the loaded `.so` in the app's own
extracted native-lib directory (`/data/app/<pkg>-<hash>/lib/arm64/`), not
inside the APK. Wrote a correct config
(`{"interaction":{"type":"listen","address":"127.0.0.1","port":27042,
"on_load":"resume"}}`) and placed it there directly via `su 0` (root shell
heredoc write, since the directory is `system:system`-owned and a plain
`adb push` there fails with `remote fchown failed`). **Result: the game
now boots all the way to the real 3D-rendered title screen** with the
gadget active and its listen port reachable (previously it hung
permanently at 6 native modules loaded, before `libclient.so` ever
appeared) — confirmed twice, on two independent fresh app launches.

### Sub-test B: dump `ui.UILogin` bytecode via Frida (`PyMarshal_ReadObjectFromString` hook) — NEW BLOCKER FOUND
With the gadget now loading correctly, attempted to attach a script and
either enumerate `libclient.so` or hook `PyMarshal_ReadObjectFromString`.
**Result: FAIL, root cause identified precisely (not a config issue this
time)**:
- `Process.enumerateModules()` / `Process.findModuleByName('libclient.so')`
  from inside the attached Gadget script consistently return only 6
  modules (`libdl.so`, `ld-android.so`, `libm.so`, `libc.so`, `liblog.so`,
  `libc++.so`) — **even while the title screen is visibly rendering 3D
  content**, proving `libclient.so` is definitely loaded and running in
  the same OS process, just not visible to this Frida session.
- `Process.arch` reports `arm64` and the visible modules' **full paths**
  are `/system/lib64/arm64/nb/libdl.so` etc. — the `/nb/` path segment is
  Android's **native bridge** (ARM-on-x86 translation layer, Intel
  Houdini-style) shim directory. **CONFIRMED root cause**: this LDPlayer
  instance's kernel is `x86_64` (per `uname -m`, previously checked in
  E2E-002/003); the `arm64-v8a` APK (including `libclient.so` AND our
  injected `libfrida-gadget.so`) runs under native-bridge CPU translation.
  The Frida Gadget, itself an arm64 binary loaded via the same
  `native_bridge3_loadLibraryExt` path as `libclient.so`, is evidently
  only seeing the native bridge's own minimal shim-library loader
  namespace (`/system/lib64/arm64/nb/*`), not the actual translated
  "guest" app code's separate module list where `libclient.so` lives. This
  is a known, hard class of problem for dynamic instrumentation on
  ARM-on-x86 emulators, **not fixable by further gadget config changes** —
  it needs either a genuinely different Frida build/injection technique
  specifically aware of native-bridge dual-namespace processes (not
  attempted — out of this pass's realistic scope), or a **test device that
  runs arm64 natively** (real ARM64 hardware, or an emulator/hypervisor
  configured for direct arm64 execution rather than x86_64+translation) —
  **this is an infrastructure/environment choice, not a routine step**,
  flagged per the task's stop condition B for a human decision if this
  path is to be pursued further.
- A secondary attempt to read `/proc/self/maps` directly from inside the
  gadget script (avoiding `Process.enumerateModules()` entirely, in case
  that API specifically was the blind spot) **hung the script engine
  entirely** (`File.readLine()` in a loop never returned/terminated,
  timing out `script.load()` and then poisoning the whole Gadget session
  for all further scripts until the app was restarted) — reported as an
  **UNKNOWN, not further investigated** side issue (Frida's `File` API
  behavior against `/proc` pseudo-files on this runtime), independent of
  the main native-bridge finding above, which was independently confirmed
  via the loop-free `findModuleByName`/`enumerateModules` calls on a fresh
  app restart.

### Sub-test C: static crib-drag on the script.npk stream cipher (fallback (a))
Since dynamic extraction is blocked, attempted to build on
`bridge/RESULT_T11.md`'s own partial static trace of the `7A 1C`-magic
stream cipher used by the ~3,957 real `script.npk` entries (as opposed to
the tiny, unrelated 2-entry AES-128-ECB sub-container). **New structural
finding this pass (CONFIRMED)**: bytes `[0:2]` of every one of the 3,957
checked entries are the literal, constant, PLAINTEXT bytes `7A 1C` (not
ciphertext) — this is a fixed container-type tag, confirmed by direct
inspection of 8 sample entries' raw bytes, matching `RESULT_T11.md`'s
naming of the magic but newly confirming it is unencrypted. **Actual
encryption starts at byte offset 2.** Attempted a known-plaintext
("crib-drag") attack on that basis: Python 2.7 marshal-serialized
top-level module code objects always begin with `TYPE_CODE` (`'c'`,
`0x63`) followed by 4-byte-LE `argcount` and `nlocals` fields that are
almost always `0` for module-level code — if the stream cipher's keystream
were purely position-dependent and file-independent (a literal
one-time-pad reused verbatim across files, which is how `RESULT_T11.md`'s
"30 consecutive zero bytes in the ciphertext delta between two files"
observation reads at face value), byte `[2]` of every entry's ciphertext
should be IDENTICAcal (`keystream[0] XOR 0x63`, a fixed value) across all
files. **Result: DISPROVEN** — a histogram of byte `[2]` across all 3,957
entries shows a long tail of at least 15 distinct values each occurring
many times (top value 886/3957 ≈ 22%, next 512, 402, 315...), not one
dominant constant. **CONCLUSION (INFERRED)**: the keystream is not a
single global file-independent sequence reused identically from byte 0 for
every entry — there is some per-file variation (most plausibly a per-file
seed/nonce derived from the entry's hash, offset, or size, mixed into the
keystream generator before the position-dependent part takes over) that
this pass did not have time to characterize further. `RESULT_T11.md`'s
own "static keystream" finding is **not contradicted** by this — it was
about comparing a specific PAIR of files at a specific offset window, not
a claim that ALL files share one universal keystream from byte 0, and this
pass's broader histogram is a real, additive data point for whoever
continues this thread, not a reason to distrust the earlier finding.

### RESULT / NEXT_ACTION (native `.so` patching permanently excluded per user)
Both fallback avenues (a) and (b) named by the user were attempted in good
faith this pass and each produced a genuine, well-diagnosed blocker rather
than a lazy stop:
- **(b) dynamic Frida extraction**: real progress (config bug fixed,
  gadget now loads and the app reaches the title screen with it active) —
  but blocked by a native-bridge dual-namespace module-visibility issue
  that is an environment/hardware-class limitation of this specific
  x86_64-with-ARM-translation LDPlayer setup, not a config or code
  mistake. **Recommend as NEXT ACTION for a future pass**: either (i) test
  on a genuinely arm64-native device/emulator (a real Android phone, or an
  ARM64-hosted virtual device) where Frida's gadget would share the same
  module namespace as the app's own code with no translation layer in the
  way — **this is the kind of environment/infrastructure choice this
  project's task brief itself flags as needing a human decision**, since
  it may mean setting up different hardware/emulation entirely; or (ii)
  research whether a specific Frida build/version has documented
  native-bridge-aware injection support (not checked this pass).
- **(a) static crypto crib-drag**: made real, new structural progress
  (confirmed the `7A1C` plaintext magic and that encryption starts at
  offset 2) but disproved the simplest global-keystream hypothesis; a
  correct break likely needs either recovering the per-file seed
  derivation (would need more of `libclient.so`'s marshal-loading code
  disassembled to find where that seed comes from — the "reading
  disassembly, not executing it" boundary this pass didn't cross) or
  substantially more many-file statistical cryptanalysis than this pass's
  time budget allowed.
- **No script.npk edit, no `doLoginGame()` patch, and no BaseApp/Account/
  Avatar/Lobby work was possible this pass** — both prerequisite
  extraction paths remain open problems. This is reported plainly rather
  than improvised around.

---
*Last updated: 2026-09-15. Do not overwrite prior entries — append new
TEST_ID blocks only.*
