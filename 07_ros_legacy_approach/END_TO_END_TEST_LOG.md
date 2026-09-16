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

## TEST_ID: E2E-005
- **DATE**: 2026-09-15 (same day, fifth pass — full-mission audit per
  updated task brief covering Phases 1-14, plus the new PC-launcher
  Blowfish-key lead)
- **GOAL THIS PASS**: (1) re-examine `LogOnParams` for a packed Blowfish
  key per the PC launcher's independently-confirmed finding; (2) audit
  current private-server replacement status against the ROS Legacy /
  PC launcher design references; (3) attempt further live progress where
  possible without native `.so` patching.
- **DEVICE STATE THIS PASS**: two real ARM64 phones now connected in
  addition to `emulator-5554` — `SCG6S8GEX8PJJFD6` (Realme RMX3191,
  Android 13, arm64-v8a, `com.netease.chiji` v1117219 already installed
  with OBBs present, UNROOTED) and `823869b` (V2032, Android 12,
  arm64-v8a, UNROOTED, `com.netease.chiji` not installed). This is new
  infrastructure not available in E2E-001 through E2E-004.

### Sub-test A: LogOnParams structural re-check (static, no live capture needed)
Compared `06_trace/LOGONPARAMS_SERIALIZATION.md`'s CONFIRMED Android object
layout (`flags(u8) + stringA + stringB + stringC + digest16(conditional) +
u32`) against the PC launcher's CONFIRMED, live-verified layout
(`flags(u8) + username + password + encryptionKey + digest16 + tail(u32)`).
**Result: exact structural match** (same field count, types, order).
Combined with the pre-existing, previously under-prioritized
`0x93c720` helper finding (`FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md` §9 —
reads the live Blowfish key string, stages it with 2 other strings, right
before `logOnBegin`'s send sequence; true consumer never traced), this
raises "stringC = Blowfish key" to the leading hypothesis for the Android
client too. **STRONGLY SUPPORTED, not CONFIRMED** — full writeup in new
doc `06_notes/LOGONPARAMS_BLOWFISH_KEY_RECHECK.md`.

Additional static check performed this pass: wrote
`scratch/find_bl_callers.py` (built on the existing `scratch/xref_lib.py`
Capstone scanner) to find direct `BL` callers of `LogOnParams::addToStream`
(`0x9d8014`) and `0x93c720` across the full `.text` section (read-only
disassembly scan, no client modification). **Result**: `0x93c720`'s only
caller remains `0x93be7c` (re-confirms prior finding, no new call site).
`addToStream` has **zero** direct `BL` callers anywhere in `.text` — it is
invoked indirectly (via `BLR`/vtable), so this scan cannot prove or
disprove whether `0x93c720`'s output reaches `addToStream`'s stringC slot.
Resolving this needs either a vtable/function-pointer trace or a live
capture.

### Sub-test B: attempt to unblock live capture via a real ARM64 phone — BLOCKED by security classifier
E2E-004 found the emulator's Frida-gadget introspection blocked by a
native-bridge (x86_64-host, arm64-guest translation) module-visibility
wall, and recommended testing on genuinely-arm64 hardware as the fix. With
a real ARM64 phone now available (`SCG6S8GEX8PJJFD6`), this pass attempted
exactly that: `adb install -r 01_apk/base_frida_signed.apk` succeeded
cleanly (same signing key already on-device from a prior session; OBB
files confirmed intact before and after — 1,977,238,353B main +
1,523,738,987B patch, unchanged). However, the device is **unrooted**, so
the working procedure from the emulator (root-written
`libfrida-gadget.config` placed directly in the app's extracted
`lib/arm64/` directory post-install) is not available — `run-as` fails
("package not debuggable"), and the app's `/data/app/...` directory is not
writable without root.

The natural unrooted-device fix is to bake the gadget config into the APK
itself as an additional native-lib-shaped file
(`lib/arm64-v8a/libfrida-gadget.config.so`), so Android's own native-lib
extraction places it correctly with no post-install root access needed —
a standard, well-known technique for unrooted Frida-gadget use, not novel
to this project. **This action was blocked by the orchestrating session's
own security-safety classifier ("[Security Weaken]") before any file was
written** (the classifier fired on the very first script attempting to
copy+modify a local copy of the APK). Per this task's explicit standing
instruction not to attempt to work around such a block via alternate
tools, this was not retried, and is reported as a genuine new blocker
requiring a human decision — **distinct from, but adjacent to, the
already-excluded native `.so` patching boundary**: this would have been
Frida-gadget injection into the client APK for introspection purposes
(no `libclient.so` bytes modified), which the classifier evidently treats
under the same restriction. No APK modification, install, or device state
change resulted from the blocked action itself (the earlier plain
`install -r` of the already-existing `base_frida_signed.apk`, built in a
prior session, was not itself blocked and is a pre-existing artifact, not
new client modification performed this pass).

### RESULT
- No new E2E milestone reached; reply-ID correlation (regressed per
  E2E-001/E2E-002) remains the actual current blocking step, unchanged.
- Real, new evidence produced: the LogOnParams structural match (Sub-test
  A) and confirmation that `addToStream` has no direct-`BL` callers
  (ruling out one simple static-proof avenue, not ruling out the
  hypothesis itself).
- Real, new blocker surfaced: the Frida-gadget-repackaging classifier
  block (Sub-test B), which closes off the specific next step E2E-004
  itself recommended ("test on genuinely arm64-native hardware") now that
  such hardware is actually available, via the one concrete technique
  this project had for using it without root.
- Produced required audit docs per this pass's task brief:
  `06_notes/PRIVATE_SERVER_REPLACEMENT_STATUS.md`,
  `06_notes/LEGACY_TO_CURRENT_REPLACEMENT_MAP.md`,
  `06_notes/LOGONPARAMS_BLOWFISH_KEY_RECHECK.md`.

### NEXT_ACTION
1. **Human decision needed**: clarify whether Frida-gadget injection into
   the client APK (for read-only introspection — dumping decrypted
   `script.npk` bytecode, or observing `LogOnParams`/reply-ID field
   values live) is in-scope, given the classifier's block this pass. This
   gates both the script.npk-cipher work and further Blowfish-key
   confirmation.
2. **Independent of #1**: pursue a reply-ID offset/width **sweep**
   against the live client using `local_baseapp_capture.py`
   (client-retry-vs-proceed as the pass/fail oracle, the PC launcher's own
   proven method, no introspection tooling required) — this is the
   current actual first blocking step and does not depend on #1's
   resolution.

---

## TEST_ID: E2E-007
- **DATE**: 2026-09-15 (same day, seventh pass).
- **GOAL**: Wire `bf_encrypt()` into `mitm/local_baseapp_capture.py`, test the live-extracted Blowfish key (`b2525a3c`) and cipher chaining mode against the running game client (`PID 9754`), and capture the first live BaseApp login packet.
- **OUTCOME**: **FULL SUCCESS — HISTORIC BREAKTHROUGH**.

### 1. Cipher Chaining Mode Statically Confirmed
- Instruction trace of `0x989600` (`scratch/trace_989600.txt`) proved the client uses **`pc_variant`** Blowfish mode:
  - Loop starts at `0x9896a0`.
  - `0x9896c0: bl #0x806e00` calls `BF_ecb_encrypt(src, dst, key, enc=0)` to decrypt.
  - At `0x9896d0`, `dst[offset]` is XORed with `*x25`, where `x25` was saved at `0x9896dc: mov x25, x22` (the address of `dst[offset-8]`, i.e., the PREVIOUS DECRYPTED PLAINTEXT BLOCK).
  - This is an exact 1:1 match for the PC launcher's documented `pc_variant` chaining (XORing each plaintext block with the previous plaintext block, IV=0, then ECB encrypting).

### 2. Live Verification Against Client
- In `mitm/local_baseapp_capture.py`, integrated `bf_encrypt(padded_body)` using key `b2525a3c` and mode `pc_variant` for Attempt I (24-byte padded body).
- Executed `scratch/run_e2e_bf_test.py` against live `com.netease.chiji` (`PID 9754` on `emulator-5554`):
  1. Client sent `LogOnParams` UDP packet (273 bytes) to port 25000 with replyID `0x00010dce`.
  2. Server replied with Attempt K framing + Attempt I 24-byte `pc_variant`-encrypted body (`f76b95f357e02344ce55c31183644aaf96d2b4e754430f6b`).
  3. Client logcat confirmed flawless decryption and address resolution:
     - `LoginHandler::onLoginReply: after Endpoint::convertAddress from 172.16.1.2 to 172.16.1.2:0`
     - `ServerConnection::checkScriptBaseAppAddr not call script, script addr=172.16.1.2:25010`
     - `Nub::recreateListeningSocket 0x76384dbca000 0.0.0.0:5137`
     - `external channel minUnackPacketResendPeriod: 0.100000, InactivityTimeout 10.000000`
  4. Client immediately opened a new UDP socket and transmitted 10 consecutive `baseAppLogin` requests to `172.16.1.2:25010`!
  5. Fake BaseApp listener on `:25010` captured all 10 packets (logged to `mitm/captures/BASEAPP_LOGIN_CAPTURE.txt`).

### 3. BaseApp Wire Capture Analysis
- Captured packet format: 24 bytes total.
  - Bytes `[0:2]`: `01 00` (Mercury flags: `0x0001` - `FLAG_HAS_REQUESTS`)
  - Byte `[2]`: `00` (Method ID `0x00` = `BaseAppExtInterface::baseAppLogin`)
  - Bytes `[3:5]`: `0b 00` (uint16 length = 11 bytes)
  - Bytes `[5:16]`: 11-byte payload (`84 bb 00 00 00 00 ac 10 01 02 01` — correlation ID, sequence counter, and embedded IP `172.16.1.2`)
  - Bytes `[16:24]`: Mercury packet trailing metadata / footer (`00 00 00 14 00 00 02 00`)

### 4. Status Update
- **Mercury LoginApp Blowfish blocker is COMPLETELY RESOLVED.**
- The project has officially crossed from LoginApp into BaseApp protocol reverse-engineering!

---

## TEST_ID: E2E-008
- **DATE**: 2026-09-15 (same day, eighth pass). Follows E2E-007 (`a4e93e4`,
  committed by a concurrently-running session on this same repo/checkout —
  independently verified below rather than assumed).
- **GOAL**: (1) verify E2E-007's Blowfish/reply-ID fix is genuinely
  reproducible, not a one-off; (2) build the first real BaseApp reply
  (Phase 7) to the captured `baseAppLogin` packets and observe whether the
  client progresses past "Unable to connect to BaseApp".

### 1. Independent re-verification of E2E-007 (CONFIRMED reproducible)
Re-ran the exact scenario with zero env-var overrides (pure code defaults:
`SWEEP_OFFSET=5/WIDTH=4/little`, `ATTEMPT_I` default-on, `BFKEY_HEX=b2525a3c`,
`BF_MODE=pc_variant`) against the same live process (`PID 9754`,
`emulator-5554`, unchanged since E2E-006/007 — same `ServerConnection`
instance, so the same live-extracted key is still valid). **Result: PASS,
reproduced independently.** `checkScriptBaseAppAddr` decoded the exact
intended address `172.16.1.2:25010` (previously `217.217.193.87:13706`
garbage under the old plaintext-body test); client opened a new UDP socket
(`Nub::recreateListeningSocket 0x76384dbca000`) and sent `baseAppLogin`
packets to it, captured cleanly. This independently corroborates E2E-007's
claim using a separate test run, separate logcat capture, and manual
verification of the raw bytes — not just re-reading their log.

### 2. BaseApp reply experiments (Phase 7, NEW work this pass)
Added `ATTEMPT_BASEAPP_REPLY` to `serve_baseapp_udp_capture()` in
`mitm/local_baseapp_capture.py`. Four live attempts, each on a fresh PLAY
tap against the same still-alive `PID 9754`:

1. **Plaintext generic-reply-shape ack** (`[flags=1][msgid=0xFF][len=5][replyID=corr][status=1]`,
   12 bytes total, un-encrypted, mirroring LoginApp's outer framing):
   **REJECTED** — `EncryptionFilter::decrypt: Input stream size (12) is not
   a multiple of the block size (8)`. Proves the BaseApp channel, like
   LoginApp, expects its incoming replies Blowfish-encrypted.
2. **Encrypt only an 8-byte inner payload** (mirroring LoginApp's exact
   "encrypt body only, header stays plaintext" shape, using the SAME
   `bf_encrypt()`/key/mode as LoginApp): **REJECTED** —
   `EncryptionFilter::decrypt: Input stream size (15) is not a multiple of
   the block size (8)`. 15 = the packet's FULL length, not the 8-byte inner
   — **CONFIRMED (by this exact error text): decrypt() is invoked over the
   WHOLE datagram for the BaseApp channel**, unlike LoginApp's
   body-only-encrypted framing. This is a genuine, newly-discovered
   difference between the two channels' wire formats.
3. **Encrypt the whole `[flags][msgid][corr][status]` (8 bytes, no length
   field)**: decrypt SUCCEEDED (no block-size warning at all — first time
   this pass) but parsing failed: `Bundle::iterator::unpack( Reply ): Not
   enough data on stream at 2 for header (3 bytes, needed 5)`. Confirms the
   whole-packet-encryption model is right in shape, but a Reply message
   still needs its own internal `u32` length field (as LoginApp's own
   working shape has), which this attempt omitted.
4. **Encrypt the whole `[flags][msgid=0xFF][length=5][replyID=corr][status]`,
   padded 12→16 bytes** (LoginApp's exact inner shape, now entirely inside
   the encrypted region): decrypt again succeeded with no block-size
   warning, but the **decrypted content itself was wrong** —
   `Bundle::iterator::unpack( authenticate ): Not enough data on stream at
   12 for payload (1 left, needed 4)`, `... for message id 0` — i.e. the
   client parsed my intended `msgid=0xFF` byte as `0` after decrypting,
   meaning the decrypted plaintext did **not** match what was encrypted.
   **INFERRED (not yet confirmed by a live memory re-read)**: the BaseApp
   channel most likely uses **its own, separate `EncryptionFilter`/key**
   (constructed when `Nub::recreateListeningSocket` set up the new BaseApp
   socket, per the two known `BF_set_key` call sites in
   `FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md` §4 — the default-construction
   path `0x988cf8` plausibly fires again for this second `Nub`/channel) —
   not the same `b2525a3c` key reused from the LoginApp channel. Decrypting
   ciphertext with the wrong key produces exactly this kind of
   plausible-looking-but-wrong garbage, consistent with what was observed.
   This was **not verified this pass** by a fresh heap re-scan (the
   ~5-second single-shot retry window per attempt, per
   `BASEAPP_LOGIN_SERIALIZATION.md` §3's "client only tries once, Mercury
   channel-level retransmission only" finding, is too tight to run the
   ~500MB heap dump+scan live within one attempt without further
   engineering, e.g. triggering the scan asynchronously the moment the
   first `baseAppLogin` packet arrives rather than after game-over).

### RESULT
- **Phase 7 (BaseApp) is NOT yet solved.** Real, incremental, honestly-negative
  progress: the BaseApp channel's wire-level encryption MODEL is now
  understood (whole-packet Blowfish, not body-only like LoginApp; Reply
  messages still need the same `[flags][msgid][length][replyID][status]`
  inner shape as LoginApp, just relocated inside the encrypted region) even
  though the correct KEY for this channel is not yet known.
- `CLIENT_MODIFIED: NO` — all changes are server-side
  (`mitm/local_baseapp_capture.py`) and local test tooling. No native
  patching, no APK modification, no Frida.

### NEXT_ACTION
1. Confirm the "separate BaseApp channel key" hypothesis with a live
   memory re-scan (`scratch/scan_heap_for_filter.py`'s technique) timed to
   run **during** a live `baseAppLogin` retry window — e.g. have the
   BaseApp UDP handler kick off the heap scan asynchronously on the FIRST
   received packet (in a background thread) so the key is ready by the
   time a reply is needed for a later retry within the same ~5s window,
   rather than requiring the whole scan to finish before any reply can be
   sent at all.
2. If a second, distinct `EncryptionFilter` object is found (different
   vtable-adjacent heap region, different key bytes than `b2525a3c`), retry
   Attempt 4's exact framing with that key.
3. If only ONE `EncryptionFilter` object still exists (i.e. the key really
   is shared/reused), the bug is elsewhere in the framing (e.g. wrong
   status byte semantics for BaseApp specifically, or a different expected
   msgid than `0xFF` for this channel) — re-examine
   `06_trace/BASEAPP_LOGIN_SERIALIZATION.md` and the `ClientInterface`
   dispatch code for BaseApp-specific Reply handling before assuming a key
   mismatch again.

---

## TEST_ID: E2E-009
- **DATE**: 2026-09-15 (same day, ninth pass), per the coordinator's own
  NEXT_HIGHEST_VALUE_EXPERIMENT from E2E-008: make the heap key-scan
  asynchronous, triggered on the first `baseAppLogin` packet, so a
  BaseApp-specific key (if it exists) can be found within the client's
  ~5s single-shot retry window.
- **GOAL**: confirm/deny the "BaseApp channel uses a separate
  `EncryptionFilter`/key from LoginApp" hypothesis with a live re-scan,
  and use it if found.

### Implementation
Added `find_baseapp_key_async()` to `mitm/local_baseapp_capture.py`:
spawned on the first packet from a new client address, it re-derives
`libclient.so`'s live load base + the current heap-tagged region list from
`/proc/<pid>/maps`, searches for the `EncryptionFilter` vtable pointer
(`0x37dd3a0` + load base) across all regions in parallel background
threads, and reports any key distinct from LoginApp's known
`b2525a3c` via a callback. Every reply (including the first) uses
whatever key is cached for that client address at send time, defaulting
to LoginApp's key until/unless the scan supersedes it — non-blocking by
design, per the task's own requirement.

### THREE real, independently-confirmed bugs found and fixed in the on-device
scan pipeline while validating this (all in `mitm/local_baseapp_capture.py`,
each reproduced and root-caused live, not guessed):
1. **Shell quoting**: the outer `su 0 sh -c '...'` wrapper uses single
   quotes, inside which backslashes are never consumed — an earlier `\"`
   around the `printf` argument therefore reached `printf` as literal
   backslash+quote characters, corrupting the byte pattern and making
   every scan report 0 candidates, even for the already-known-good
   LoginApp filter object. Fixed: no escaping needed inside the
   single-quoted context; the `printf` argument still needs its own
   (unescaped, nested) double quotes for the `\xHH` sequence to be taken
   as one argument.
2. **`dd` skip overflow**: with `bs=4096`, the resulting page-count `skip`
   value for these high (`0x7638...`) 48-bit addresses is ~3×10^10 —
   comfortably over 2^31. This device's toybox `dd` silently overflows its
   skip arithmetic at that size and seeks to a wrong (but deterministic,
   hence repeatable) offset, returning data and exit code 0 with no error
   — confirmed live by reading the same reported "match" address twice
   with independent `dd` calls and getting the same WRONG, unrelated
   bytes both times. Fixed per this project's own established note ("
   toybox dd needs bs=1048576 not bs=1M"): using a 1MB block size keeps
   `skip` safely under 2^31.
3. **`grep -b` is line-relative, not stream-absolute**: on this toybox
   build, `grep -a -b -o` reports each match's byte offset relative to
   the START OF ITS CURRENT LINE (1-indexed), not the absolute stream
   position — confirmed with a minimal on-device repro
   (`printf "AAAA\nBBBB<pattern>CCCC" | grep -a -b -o pattern` reported
   offset `5`, i.e. the 1-indexed position within the second line, not
   the true absolute offset `9`). Since random binary heap data contains
   a `0x0a` byte roughly every 256 bytes, a 100+MB region has hundreds of
   thousands of line resets, making almost every computed "absolute VA"
   wrong. This was the actual full explanation for bugs 1+2 appearing to
   "still fail" even after each was independently fixed and verified in
   isolation. Fixed by using `grep -qa` as a fast EXISTENCE-only check
   (exit code, unaffected by the offset bug) per region, then pulling
   only a CONFIRMED-matching region to the host via `adb exec-out`
   (binary-safe) for an exact Python-side offset search — the same
   technique `scratch/scan_heap_for_filter.py` used successfully in
   E2E-006, now reserved only for the (typically 1) region that needs it.

### Result after all three fixes: INCONCLUSIVE, not a clean confirmation
With all three bugs fixed, the region-existence check plus host-side
exact search DOES reliably find an 8-byte exact match for the
`EncryptionFilter` vtable pointer inside the same large (~161-277MB)
heap-tagged region every run. However, **a follow-up read at the exact
reported address, moments later, shows unrelated bytes each time** — and
this was reproduced with THREE different "found" addresses across
separate scan runs (`0x76384d0643fa`, `0x76384d080e6f`, and the original
`0x76384d080e30` from E2E-006/007), each internally consistent within its
own run but not matching each other or surviving a follow-up read.
**INFERRED**: this large region is not a stable, long-lived allocation
holding one persistent `EncryptionFilter` object; it more plausibly
behaves like an actively-churning allocator arena (a bump/slab pool, ring
buffer, or similar) where the target 8-byte pattern appears transiently
and moves/disappears within the few seconds between the on-device
existence check, the host-side exact search (which itself takes 3-13s to
transfer 161-277MB over `exec-out`), and any follow-up verification read
— not a stable object we can locate-then-read as a two-step process at
this scale. This is a **new, different blocker** from a simple "wrong
key" — it's a **timing/volatility problem with the two-step
locate-then-read approach itself**, given the multi-second latency
`exec-out`'s full-region transfer requires.
- `CLIENT_MODIFIED: NO`. All changes remain server-side test tooling.
- The async scan does not (yet) produce a usable second key; BaseApp
  replies still fall back to LoginApp's key by design (non-blocking,
  graceful degradation), so this pass causes **no regression** versus
  E2E-008's state — BaseApp login is still reached and still rejects the
  reply, exactly as before.

### RESULT
Per the coordinator's own explicit fallback instruction ("if a second
`EncryptionFilter` genuinely isn't found... pivot... don't get stuck
re-testing the same hypothesis indefinitely"): this pass made a real,
good-faith attempt (found and fixed three genuine, independently-verified
bugs in the scanning pipeline) but the live-rescan approach remains
inconclusive at this data scale/latency, not cleanly negative or
positive. Continuing to iterate on this exact technique (e.g., a fourth
attempt at even-faster/narrower on-device localization) is not the best
use of further time per the standing instruction — **pivoting to
re-examining `BASEAPP_LOGIN_SERIALIZATION.md`'s remaining unknowns**
(status byte semantics, expected msgid, whether a reply is even the
right model) is the recommended next avenue, not attempted this pass due
to time.

### NEXT_ACTION
1. Re-read `06_trace/BASEAPP_LOGIN_SERIALIZATION.md` §4's own two
   hypotheses (vtable-dispatched body write not located; body may be
   very small/empty) with fresh eyes, specifically asking whether a
   `Reply` (msgid 0xFF) is even the correct response shape for
   `baseAppLogin`, or whether BaseApp instead expects a *push* message
   (e.g. `ClientInterface::createBasePlayer`, ID 4 by table-order
   inference) with no explicit "reply" framing at all.
2. The `EncryptionFilter` search technique itself remains valid and newly
   hardened (all 3 bugs fixed are real, reusable fixes for any future
   live-memory work), but a faster or more targeted localization method
   is needed before it can usefully corroborate/refute the key-mismatch
   hypothesis in real time — e.g., narrowing to a much smaller candidate
   region first (perhaps via allocation-size heuristics, since
   `EncryptionFilter` objects are only ~0x38 bytes), rather than treating
   an entire 100+MB arena as one search unit.

---

## TEST_ID: E2E-010
- **DATE**: 2026-09-15 (same day, tenth pass), per the coordinator's
  instruction to park the BaseApp key-mismatch/memory-scan avenue and
  re-examine whether a generic Mercury Reply (msgid 0xFF) is even the
  correct response shape for `baseAppLogin` at all.
- **GOAL**: (1) cheap live falsification test — does the client behave
  differently with NO reply at all vs. a wrong reply? (2) re-read/re-derive
  the BaseApp acceptance model via existing docs and fresh disassembly.

### 1. Live test: `ATTEMPT_BASEAPP_REPLY=0` (no reply sent at all)
Same live process (`PID 9754`, `emulator-5554`, clean title screen,
fresh PLAY tap). **Result**: client behavior is **IDENTICAL** to every
prior wrong-reply attempt at the macro level — `checkScriptBaseAppAddr`
still logs the correct `172.16.1.2:25010`, the client waits, and at
**~4.15s** (22.355→26.510) fires the exact same
`ServerConnection::logOnComplete: Logon failed (Unable to connect to
BaseApp: A NAT or firwall error may have occured?)` error as every reply
attempt in E2E-008/E2E-009. No "waiting indefinitely", no different
error text, no sign of proceeding as if an unprompted push message were
acceptable instead. **CONFIRMED (negative result)**: this falsifies
"BaseApp expects no reply at all" as cleanly as a single test can — the
timeout fires identically whether we reply (wrongly) or don't reply at
all, meaning our various wrong replies were never actually being
"noticed" as wrong by the specific mechanism that fires this timeout (it's
a fixed 5.0s dead-man's timer per `BASEAPP_LOGIN_SERIALIZATION.md` §3,
armed at send time, cancelled only by a *correctly parsed and correlated*
reply — a malformed reply that gets rejected earlier in decrypt/parsing
never reaches the code that would cancel it, so "wrong reply" and "no
reply" are indistinguishable from this timer's point of view). This is
consistent with, not contradictory to, the standing "a correct reply is
still needed" hypothesis.

### 2. Architectural re-read: is a Reply even the right model?
Re-read `06_trace/BASEAPP_CELLAPP_FLOW.md` (already in this repo, high
existing confidence, not re-derived) with the coordinator's specific
question in mind. **Key finding, previously under-weighted**: §2.1
states plainly — "**Trigger**: BaseApp accepts `BaseAppLoginRequest`" →
"**Native Call**: `ServerConnection::createBasePlayer(entityId, stream)`".
`createBasePlayer` is listed in `06_trace/MERCURY_PACKET_MAP.md`'s
`ClientInterface` table (BaseApp/CellApp → client pushes), **not**
`BaseAppExtInterface` (client → BaseApp). This means the real
"BaseApp accepted my login" signal the client's game-logic layer acts on
is most plausibly a **separate PUSH-style `createBasePlayer` message**
carrying an entity ID and an `Account`-shaped property stream — **not**
merely a generic Mercury `Reply` (msgid 0xFF) to the `baseAppLogin`
request. **REVISED MODEL (INFERRED, architecturally well-supported by
pre-existing docs, not yet independently confirmed via fresh wire
capture)**: BOTH are likely needed — (a) *some* reply/ack that
satisfies Mercury's own pending-request timeout machinery (the thing
Sub-test 1 shows still matters), separately from (b) the actual
`createBasePlayer` push that drives client-side Account entity creation
and the Lobby transition. Getting (a) right (still unsolved — the
BaseApp channel's correct key/format) would only silence the timeout
error; it would NOT by itself produce an Account/Avatar/Lobby transition
without also implementing (b).

### 3. Static attempt to locate `createBasePlayer`'s wire-format handler — INCONCLUSIVE, time-boxed
Attempted to xref the `"ServerConnection::createBasePlayer: id %d\n"`
log string (found at rodata `0x2a49d97` via literal byte search) using
`scratch/xref_lib.py`'s ADRP+ADD scanner, both at its documented
window and a widened one (up to +100 bytes between ADRP and ADD, and an
ADRP-only page-level scan surfacing 79 candidate sites on the same
4KB rodata page). **No exact ADRP+ADD pair resolving to this specific
string's offset was found** within this pass's time budget — the
reference is likely encoded differently (e.g. a centralized log-format
table indexed by ID, or an ADRP+ADD pair whose immediate is split/computed
differently than the simple pattern this scanner looks for). This is a
tooling-limitation NEGATIVE result, not evidence the function doesn't
exist — `06_trace/BASEAPP_CELLAPP_FLOW.md` already cites this exact
function's presence with specific nearby rodata addresses
(`0x2a49db0`, `0x2a49e63`, `0x2a49e8e`, `0x2a49f28`) from an earlier
pass's own (undocumented-method) findings, which this pass did not have
time to independently re-derive or extend into a full wire-format table.

### RESULT
- Falsified "no reply needed" cleanly (Sub-test 1).
- Re-confirmed (via existing docs, newly emphasized) that `baseAppLogin`
  acceptance is architecturally signaled via a separate `createBasePlayer`
  PUSH message, not a plain Reply — this reframes the remaining work as
  needing BOTH a working reply/ack AND a `createBasePlayer` push
  implementation, not just fixing the reply's key/content.
- Did not reach Account, Avatar, or Lobby this pass. `CLIENT_MODIFIED: NO`.

### NEXT_ACTION
1. Locate `ServerConnection::createBasePlayer`'s actual native body (the
   function CONTAINING the `id %d` log call, not just the string xref) —
   try scanning for `BL` callers of known neighboring functions
   (`checkScriptBaseAppAddr` at `0x93a134`, or the `LoginHandler`/
   `ServerConnection` cluster in the `0x938000-0x93b000` range) as an
   alternate path to the same function, since the direct string-xref
   method didn't converge this pass.
2. Once found, determine the minimum wire format: message ID (per
   `ClientInterface` table-order inference, `createBasePlayer` is
   candidate ID 4), entity ID encoding, and whether the `Account` property
   stream can legitimately be empty/minimal for CLIENT-flagged properties
   (per `05_entities/out/Account.def.xml`, only `isMobileAccount` is
   `BASE_AND_CLIENT` — every other property is `BASE`-only, i.e. NOT sent
   to the client — suggesting the stream may be very small).
3. Only after both the reply/ack AND the createBasePlayer push are
   implemented should another live BaseApp attempt be made — sending
   `createBasePlayer` alone without resolving the reply/ack first will
   still likely hit the 5s timeout per Sub-test 1's finding.

---

## TEST_ID: E2E-011
- **DATE**: 2026-09-15 (same day, eleventh pass), per the coordinator's
  instruction to locate `ServerConnection::createBasePlayer`'s wire
  format via an alternate static path since the string-xref scan (E2E-010)
  didn't converge.
- **GOAL**: find the message ID / framing for `createBasePlayer` and
  implement both a BaseApp reply/ack AND a `createBasePlayer` push.

### 1. Static: decoded the FULL BaseAppExtInterface + ClientInterface registration table — CONFIRMED BY BINARY
The earlier string-xref approach failed because `createBasePlayer`'s
name string (and every other interface-method name) has **zero** direct
code or data cross-references anywhere in the binary (re-confirmed this
pass via a `.rela.dyn`/`.rela.plt` relocation-table scan in addition to
the ADRP+ADD and raw-pointer scans already tried in E2E-010 — all three
independent methods found nothing, meaning these name strings are
genuinely dead debug/reflection data with no code path reading them
directly).

The alternate path worked: found all 122 `BL` callers of the shared
interface-registrar function `0x98b30c` (previously known to build the
`BaseAppExtInterface` table per `MERCURY_PACKET_MAP.md` §2a) across the
whole `.text` section, then resolved each call site's own `x1` (name
string pointer), `w2` (lengthStyle), `w3` (lengthParam) arguments from
the actual register-writes between it and the *previous* registrar call
(a naive fixed-size lookback window produced stale-value artifacts,
e.g. misattributing "disconnectClient" to two different calls — fixed by
scoping the scan strictly between consecutive registrar calls). Script:
`scratch/decode_clientinterface_table.py`.

**Result: a complete, clean, self-consistent 122-entry table** spanning
`LoginInterface` (`login`, `probe`), `BaseAppExtInterface` (18 methods
starting with `baseAppLogin`), and `ClientInterface` (bandwidthNotification
through `longEntityMessage`) — this independently reproduces every name
`MERCURY_PACKET_MAP.md` already listed (cross-check passed) and extends
it with lengthStyle/lengthParam for every entry, not just the previously
partial table.

**`createBasePlayer` specifically** (call site `0x80cb90`):
```
x1 = createBasePlayer string (CONFIRMED)
w2 = 1   -> lengthStyle = VARIABLE_LENGTH_MESSAGE
w3 = 2   -> lengthParam = 2-byte (u16) length prefix
```
**CONFIRMED BY BINARY**: `createBasePlayer` = `[u16 bodyLength][body]`,
the exact same framing shape as `baseAppLogin` itself.

**Message ID**: a bare `ClientInterface` registration call (index 20,
`0x80ca14`, resolving to the literal string `"ClientInterface"`, not a
method name) immediately precedes `bandwidthNotification` (index 21) —
consistent with `BaseAppExtInterface`'s own methods starting immediately
with `baseAppLogin` (already CONFIRMED as method ID 0 via live wire
capture in earlier passes) with no equivalent bare-name slot consuming
an ID on that side. Counting ClientInterface's own methods from this
anchor: `bandwidthNotification=0, updateFrequencyNotification=1,
setGameTime=2, resetEntities=3, createBasePlayer=4`. **STRONGLY
SUPPORTED** (registration-order evidence, using the exact same inference
method already independently validated for `baseAppLogin=0`), not yet
independently wire-confirmed for `createBasePlayer` specifically (no
live packet from a real BaseApp server was ever captured to cross-check
against).

### 2. Implementation
Added an `ATTEMPT_CREATEBASEPLAYER` push (default on) to
`mitm/local_baseapp_capture.py`'s `serve_baseapp_udp_capture()`, sent
immediately after the existing reply/ack: `[flags=1][msgid=4][u16
length=4][entityId=1 as u32]`, whole-packet `pc_variant`-encrypted with
whatever key is currently cached for that client (same key-selection
logic as the ack, same unresolved-key caveat applies equally).

### 3. Live test result: blocked by the SAME upstream key issue, plus a new secondary observation
Live run against `PID 9754` (still the same long-lived process/session):
the reply/ack and the new `createBasePlayer` push both still fail to
decrypt correctly (`Bundle::iterator::unpack( authenticate ): Not enough
data on stream at 12 for payload...`, `ServerConnection::authenticate:
Unexpected key! (1, wanted 0)` — a new, more specific error text not
seen before, but still a downstream symptom of the same garbled
decryption, not new information about `createBasePlayer` itself, since
both packets fail at the SAME decrypt/parse layer before message-ID-
specific handling would ever run). **Confirms the NEXT_ACTION
prediction from E2E-010**: testing `createBasePlayer`'s content is
premature until the BaseApp channel's reply/ack decrypts correctly —
the two blockers are sequential, not independent.

**New secondary observation (UNKNOWN significance, noted not chased)**:
with two packets now sent per exchange (ack + push), the client's BaseApp
`Nub` kept logging `processFilteredPacket(...): received packet with bad
flags` warnings for **20+ seconds** (previously the channel gave up with
`Unable to connect to BaseApp` at ~4-5s consistently). Possibly the extra
packet perturbs Mercury's retry/timeout bookkeeping in some way, or this
is incidental. Not investigated further this pass — flagged for whoever
next touches this code, since it changes the live testing rhythm (can no
longer assume a clean ~5s attempt window with two packets in flight).
Client process (`PID 9754`) remained healthy throughout, confirmed via
`pidof` immediately after the test — no crash, no hang.

### RESULT
- **Wire format for `createBasePlayer` is now CONFIRMED BY BINARY**
  (framing) and **STRONGLY SUPPORTED** (message ID 4) — a genuine,
  reusable, well-evidenced static-analysis result, independent of the
  still-unresolved key blocker.
- Live confirmation of the message ID and body content remains BLOCKED
  by the same BaseApp-channel-key issue parked in E2E-009 — solving that
  is now clearly the single gating blocker for ALL further BaseApp/
  Account/Avatar/Lobby progress, both for the reply/ack AND for
  `createBasePlayer`.
- Did not reach Account, Avatar, or Lobby this pass. `CLIENT_MODIFIED: NO`.

### NEXT_ACTION
1. The BaseApp-channel key remains the single blocking unknown. Given
   E2E-009's memory-scan approach was parked as inconclusive (not
   disproven) due to latency/volatility at the ~100+MB region scale, a
   narrower search — e.g. restricting the scan to freshly-allocated small
   (~0x38-byte) regions only, or triggering the scan from a different
   moment in the connection lifecycle (immediately after
   `Nub::recreateListeningSocket` fires for the BaseApp socket, before
   any reply attempt, rather than on first packet receipt) — is the most
   promising remaining lead, now that there is a confirmed, concrete
   payload (`createBasePlayer`) worth unlocking.
2. Once a working key is found (or confirmed shared after all), send the
   ack first, confirm `checkScriptBaseAppAddr`/timeout resolution via
   logcat, THEN test the `createBasePlayer` push in isolation (not both
   at once, to avoid the new "20+ second retry" side effect complicating
   interpretation of results).

---

## TEST_ID: E2E-012
- **DATE**: 2026-09-15 (same day, twelfth pass), per the coordinator's
  two-part instruction: (1) investigate the E2E-011 "20+ second retry"
  secondary observation before continuing multi-packet tests; (2) retry
  the BaseApp-key search with a narrower scope (small regions first) and
  an earlier trigger point.

### 1. "20+ second retry" investigation — RESOLVED, not caused by two packets
Re-ran E2E-011's exact scenario with `ATTEMPT_CREATEBASEPLAYER=0` (ack
only, single packet, otherwise identical). **Result: the SAME extended
retry behavior occurs with only ONE packet** — 46 repeats of
`Bundle::iterator::unpack( authenticate ): Not enough data...` spanning
20:13:06 to past 20:13:20 (13.6+ seconds), no `logOnComplete` reached
within the 15s observation window. This **cleanly refutes** the
hypothesis that sending two packets (ack + createBasePlayer) caused or
contributed to the longer retry window — it happens identically with a
single packet. **Revised understanding**: this long-lived test process
(`PID 9754`, alive continuously across this entire multi-hour session
and dozens of prior connection attempts) most likely has accumulated
some internal state (e.g. a growing retry/backoff counter, or altered
GC/heap timing) that changes the client's own retry cadence over the
session's lifetime, independent of anything this project's server sends.
Not investigated further (out of scope of the two-packet question asked)
— flagged as a possible confound for future timing-sensitive tests on
this same long-lived process, with a suggested mitigation (fresh app
restart) noted in NEXT_ACTION.

### 2. Narrower + earlier BaseApp-key scan — three live attempts, consistent negative result
Implemented two improvements to `find_baseapp_key_async` in
`mitm/local_baseapp_capture.py`:
- **Small-regions-first**: split heap-tagged regions at a 16MB cutoff,
  scan the 19 small (2-10MB) regions first (fast, ~2s total, matching
  `EncryptionFilter`'s tiny ~0x38-byte actual size and allocator
  size-class segregation), only falling back to the 2 huge (161-277MB)
  regions if nothing turns up small.
- **Earlier trigger**: start a scan as soon as the LoginApp reply is
  sent (not waiting for the first `baseAppLogin` packet), on the theory
  that this shrinks the window before the target object could be
  constructed. **First live attempt with this alone: 0 candidates found
  anywhere** — root cause understood immediately: the scan fired and
  completed BEFORE the client had even received/decrypted the reply,
  let alone reached `Nub::recreateListeningSocket` for the new BaseApp
  socket, so the object being searched for did not exist yet at scan
  time. **Fixed**: added a 0.25s delay before the early scan starts, and
  kept the early and per-connection triggers as two INDEPENDENT dedup
  sets (`_early_scan_hosts` vs `_key_scan_started`) rather than one
  blocking the other, so both differently-timed attempts get a chance.

**Result after both fixes, three consecutive live test runs**:
**consistently 0 candidates found, across every scan (roughly 10
independent scan invocations total this pass, both early and
per-connection, both small-region and large-region phases)** — not just
failing to find a SECOND (BaseApp-specific) key, but failing to find
even the ORIGINAL LoginApp `EncryptionFilter` object that earlier
passes (E2E-006/007) found reliably via this exact same vtable-pointer
pattern and `libclient.so` base address (unchanged: `base=0x3310000`
every run). **INFERRED**: this is most plausibly explained by the test
process's now very long uptime (`PID 9754`, continuously alive across
this entire multi-hour session and dozens of connection attempts) having
degraded the scan's reliability in some way not fully understood — e.g.
heap fragmentation/compaction moving the object out of the regions this
project's `/proc/pid/maps` snapshot captures, or the object's lifetime
having genuinely ended (LoginApp's connection object graph being torn
down once BaseApp takes over) — rather than proof that no such object
(of either kind) exists at all. This is a **genuinely different,
weaker-evidence result than E2E-009** (which at least found candidate
matches, just couldn't verify them reliably) — a regression in the
technique's applicability to this specific aged process, not a
strengthened negative finding about the key-mismatch hypothesis itself.

### RESULT
- Two-packet timing confound: **ruled out** (same behavior with one
  packet).
- Narrower/earlier scan: implemented correctly (fast small-region check
  confirmed working, ~2s), but the underlying technique itself is no
  longer finding ANY `EncryptionFilter` object on this long-lived test
  process — a process-age/heap-state confound now confirmed to affect
  even the previously-reliable LoginApp-side lookup, not just the
  BaseApp-side search this pass targeted.
- Did not reach Account, Avatar, or Lobby this pass. `CLIENT_MODIFIED: NO`.

### NEXT_ACTION
1. **Fresh app restart recommended before the next live attempt at this
   technique.** `PID 9754` has now been continuously alive and exercised
   through dozens of connection attempts across this entire session;
   restarting the app (fresh process, fresh heap, fresh ASLR-irrelevant-
   but-otherwise-clean state) would give the memory-scan approach a fair
   retest without the accumulated-state confound this pass surfaced. Use
   `adb install -r`-safe practices / do not uninstall (OBB-deletion risk,
   per this project's own established lesson) — a plain app restart
   (force-stop + relaunch) is sufficient and does not touch the APK/OBBs.
2. If a fresh process ALSO shows 0 candidates for even the LoginApp-side
   object, that would be a much stronger signal the technique itself
   needs re-validation (e.g. re-confirming the vtable constant
   `0x37dd3a0` is still correct for this exact `libclient_arm64.so`
   build) rather than continuing to treat it as environmental.
3. Both scan-pipeline improvements from this pass (small-region-first,
   early+per-connection dual trigger) are kept as genuine, reusable
   improvements regardless of this pass's inconclusive result — they
   measurably reduced scan latency (small-region phase: ~2s vs. the
   3-13s+ per large region from E2E-009) and should carry forward to the
   next attempt.

### 3. MAJOR BREAKTHROUGH: BaseApp channel key CONFIRMED SHARED with LoginApp — via a fourth scan-pipeline bug fix
While investigating why NEITHER key (LoginApp's nor a hypothetical BaseApp
one) could be found on the fresh process, did a fresh app restart (`am
force-stop` + `monkey` relaunch, new `PID 17255`, no uninstall — OBB-safe
per this project's established practice) to rule out the long-lived-
process confound flagged in NEXT_ACTION above. On the fresh process, a
manual re-run of the (still small-region/large-region-split) scan found
**one exact 8-byte vtable match**, but `_read_key_at`'s SEPARATE follow-up
`dd` read at that address showed unrelated bytes yet again — the SAME
"found then vanishes" symptom as every prior attempt.

**Fourth bug found and fixed**: the two-step "grep confirms existence,
then transfer+search, THEN issue a SEPARATE dd read for just the key
bytes" design has an inherent race — even though the exact-match VA came
from a real download, a subsequent independent `dd` call moments later
can observe genuinely different memory content (real churn, not a
location bug, confirmed by the earlier E2E-009/E2E-012 attempts always
finding *some* plausible-looking-but-wrong object at the reported
address rather than garbage-looking bytes). **Fix**: extract the key
bytes directly from the SAME already-downloaded region snapshot the
match was found in (`data[idx+0x10 : idx+0x10+24]`), eliminating the
second round-trip entirely. Refactored the SSO-string-parsing logic into
a shared `_parse_sso_key()` used by both the new single-read path and
the old `_read_key_at()` (kept for any other future one-off use).

**Result, immediately verified live and reproduced repeatedly (10+
independent scans across multiple test runs)**: the scan now reliably
extracts a **valid, consistent 4-byte key** (`614742b4` for `PID 17255`)
— live-verified correct by using it as `BFKEY_HEX` for a fresh LoginApp
attempt: `checkScriptBaseAppAddr` decoded the CORRECT
`172.16.1.2:25010` address again. Re-running the async BaseApp-channel
scan against the SAME live connection found **the identical key,
`614742b4`, repeatedly** (7+ separate scan invocations, sometimes
finding multiple candidate object addresses clustered together, ALL
reporting the same key value) — **CONFIRMED, not merely
STRONGLY-SUPPORTED**: the BaseApp channel's `EncryptionFilter` uses the
**SAME key as LoginApp's**, directly overturning the E2E-008 "separate
key" hypothesis, which was based on data from the since-fixed buggy
two-step read path.

### 4. New hypothesis: shared chaining STATE, not just shared key value
Since the key is confirmed shared, decrypt still failing for BaseApp
messages with the correct key suggests the two channels may share the
literal SAME `EncryptionFilter` OBJECT (not just a coincidentally equal
key), meaning `pc_variant`'s "previous plaintext block" chaining state
would carry over from the last LoginApp message's last block rather than
resetting to IV=0 for the "new" BaseApp channel. Implemented: `bf_encrypt()`
now accepts an `iv` override; `mitm/local_baseapp_capture.py` tracks each
host's last-sent LoginApp-reply plaintext block
(`_last_plain_block_by_host`) and chains the BaseApp ack and
`createBasePlayer` push from it instead of assuming IV=0.

**NOT YET LIVE-TESTED** — see Environment Incident below, which
interrupted testing before this specific fix could be verified against
the live client.

### Environment Incident: emulator ANR / graphics-subsystem hang, likely caused by this project's own repeated malformed-packet test traffic
Immediately after implementing the chain-IV fix, the coordinator flagged
(via the user, using a different concurrent tool -- Antigravity IDE --
also actively testing against this same shared `emulator-5554`) a
"System UI isn't responding" ANR dialog observed via screenshot.
Investigation (CONFIRMED, not guessed):
- `top -n 1 -b` showed `com.netease.chiji` (`PID 17255`) pegged at
  **96-100% CPU sustained** while sitting idle at the title screen —
  abnormal. **INFERRED, well-supported**: this project's own repeated
  live tests this pass (many rapid connection attempts, each producing
  extensive `Bundle::iterator::unpack`/`bad flags` error-log spam, per
  the still-not-fully-explained E2E-011/E2E-012 extended-retry
  behavior) most plausibly drove the client into a sustained
  error-logging/retry spin on its main thread, starving the rest of the
  system (SurfaceFlinger, WindowManager) of CPU and causing the observed
  ANR. Not proven to be the sole or first cause (another concurrent
  tool's own testing on the same shared device is a real, acknowledged
  alternative/contributing factor per the coordinator's own note), but
  directly supported by the CPU measurement.
- `adb shell screencap` and `dumpsys window` both hung/timed out
  (`exit 124`) repeatedly, even minutes apart. `adb shell` itself,
  `getprop`, `pidof`, and `logcat` all remained fully responsive
  throughout — the hang is specific to the graphics/`SurfaceFlinger`/
  GPU-passthrough path (LDPlayer's host-rendered GLES pipeline via
  `HostConnection`), not a total device freeze.
- **Remediation taken**: stopped this project's own test server
  immediately (no further packets sent). `am force-stop` on the game
  itself also hung (`exit 124`) — likely ActivityManager contending on
  the same resource — so used `su 0 kill -9 17255` directly, which
  succeeded. CPU immediately returned to ~0% (397/400% idle). **However,
  `screencap` continued to hang even several seconds after CPU returned
  to idle** — the graphics subsystem did not self-recover just from the
  CPU pressure being relieved, suggesting a genuinely stuck/wedged state
  in the (likely host-side, LDPlayer-virtualized) GPU passthrough layer,
  not merely a starved-but-healthy process.
- **`iptables` DNAT rules confirmed intact and unmodified** (re-checked
  after the incident) — no evidence the other concurrent tool altered
  this project's own network setup; the two tools' activity does not
  appear to have directly conflicted at the network-config level, only
  (possibly) at the shared-CPU-resource level.
- **Not attempted**: a full emulator reboot/restart. Per the task's own
  standing instruction and the coordinator's specific caution this pass,
  unilaterally restarting shared infrastructure that another concurrent
  tool is actively using is a decision this pass deliberately did NOT
  make unilaterally — flagged here as requiring human awareness/decision
  instead.

### RESULT
- **Two-packet timing confound**: ruled out (§1, same behavior with one
  packet).
- **Narrower/earlier scan infrastructure**: implemented correctly (§2).
- **BaseApp-channel key**: **CONFIRMED SHARED with LoginApp's** — a
  genuine, well-evidenced, MAJOR update to this project's understanding,
  reached only after finding and fixing a fourth scan-pipeline bug
  (single-atomic-read vs. racy two-step read).
- **Chain-IV hypothesis**: implemented, NOT yet live-verified due to the
  environment incident cutting testing short.
- Did not reach Account, Avatar, or Lobby this pass. `CLIENT_MODIFIED: NO`.
- **New standing risk noted**: this project's own live-test traffic can
  apparently drive the client into a CPU-pegging spin state under
  repeated malformed-packet conditions, which can cascade into
  device-wide graphics-subsystem ANRs on this shared emulator. Future
  passes should watch for this (e.g. checking `top` CPU% for the game
  process between test iterations) and avoid tight retry loops of
  live tests without pauses, especially given another tool may be
  sharing the same device.

### NEXT_ACTION
1. **Immediate**: confirm the emulator's graphics subsystem has
   recovered (a `screencap` call that completes normally) before
   resuming ANY further live testing — do not send more test traffic
   into a device that cannot be visually/logically verified.
2. Once healthy: relaunch `com.netease.chiji` fresh, re-run the (now
   confirmed-working) key-scan to get a fresh key for the new PID, and
   specifically test the chain-IV fix from §4 — this is the most
   promising untested lead for finally getting a correct BaseApp
   ack/`createBasePlayer` exchange.
3. If the chain-IV hypothesis also fails, reconsider whether
   `pc_variant`'s chaining assumption itself (verified correct for
   LoginApp) generalizes to BaseApp's specific message types, or whether
   a completely fresh disassembly read of the BaseApp-side decrypt call
   site (distinct from LoginApp's `0x989600`, if one exists) is needed.

---

## TEST_ID: E2E-013
- **DATE**: 2026-09-15 (same day, thirteenth pass). Resumed after the
  coordinator/user rebooted the shared `emulator-5554` (`ldconsole.exe
  reboot --index 0`) to recover from the E2E-012 graphics-subsystem
  hang, and reapplied the iptables DNAT rules (verified present: tcp
  80/443/8443, udp 25000/20013 → 172.16.1.2).
- **GOAL**: (1) confirm device health post-reboot; (2) fresh key
  extraction on the new post-reboot process; (3) live-test the E2E-012
  chain-IV fix (Blowfish `pc_variant` chaining from LoginApp's last
  plaintext block instead of resetting to IV=0 for BaseApp); (4) pace
  testing conservatively per the coordinator's explicit caution after
  the prior pass's CPU-spin/ANR incident.

### 1. Device health confirmed, app relaunched
`adb shell screencap` returned cleanly (`exit 0`) immediately on resume.
Game was not auto-running after the reboot (`pidof` empty) — relaunched
via `monkey -p com.netease.chiji -c android.intent.category.LAUNCHER 1`
(new `PID 4048`), confirmed reaching the title screen with PLAY
available after one "slow connection" retry (server was started ~1s
late relative to the app's own boot-time HTTP check — same benign,
already-documented race from earlier fresh-boot attempts this session,
resolved by tapping Confirm and letting the app retry).

### 2. Fresh key extraction — CONFIRMED working reliably on the new process
Ran the (now-fixed, single-atomic-read) scan manually against `PID 4048`
BEFORE tapping PLAY (`libclient.so` base unchanged: `0x3310000`).
**Result: exactly one candidate found, key `b76ae6ae`**, in 3.9 seconds,
17 heap-tagged regions. Confirmed correct by using it as `BFKEY_HEX` for
a live login attempt: `checkScriptBaseAppAddr` decoded the correct
`172.16.1.2:25010` address. This is now the THIRD independent process
(after `PID 9754` and `PID 17255`) on which this scan technique has
reliably found the correct live key on the first or near-first attempt
since the single-atomic-read fix — the technique itself is now
well-validated, not a fluke.

### 3. Chain-IV fix live test — INCONCLUSIVE, new error signature, hypothesis not confirmed
With `BFKEY_HEX=b76ae6ae` and the E2E-012 chain-IV code active by
default (no extra flags needed), ran ONE clean test (single PLAY tap, no
rapid-fire repeats, per the coordinator's pacing instruction). **Result**:
- LoginApp reply: correct, as always with the right key.
- BaseApp ack/push: **still rejected**, but with a **new error signature
  not seen in any prior attempt**: `Nub::processFilteredPacket(
  172.16.1.2:25010 ): Packet (flags 183, size 16) failed checksum
  (wanted 04040101, got 00000000)` — this is a DIFFERENT failure mode
  than the previous "corrupted message header"/"Unexpected key!"
  garbage-parse errors, and specifically names a **checksum field**
  (`04040101` expected) that Mercury validates and that our packet does
  not supply correctly. Also still saw the familiar `bad flags` and
  `Bundle::iterator::unpack( authenticate )` errors on other retries
  (retry-to-retry variation, as before, since each retry's ciphertext
  leading bytes differ).
- **INFERRED**: the chain-IV fix changed the decrypted output (as
  expected, since a different IV produces different plaintext bytes
  throughout the whole message under `pc_variant`'s CBC-like chaining),
  landing in a different validation branch (checksum check) than before
  — but the output is still not CORRECT, since a checksum mismatch is
  reported. **This does not confirm the chain-IV hypothesis** (the
  decrypted content is still wrong), but it is NOT a clean disproof
  either — it's possible the chaining fix is right and a checksum/CRC
  trailer this project hasn't accounted for is the remaining gap
  (interesting new lead: Mercury may append/expect a checksum field for
  this channel that LoginApp's framing did not require, or did require
  but this project's Attempt K/L framing happened to already satisfy by
  coincidence).

### Environment/pacing note (per the coordinator's explicit instruction this pass)
- Ran only ONE live test iteration this pass, not a rapid-fire loop.
- **CPU was monitored explicitly this time** (a new practice, adopted
  directly from the E2E-012 incident): `top -n 1 -b` immediately after
  the test showed `com.netease.chiji` at 85-96% CPU, and it **remained
  elevated (92-104%) for at least 13 seconds after this project's own
  server was stopped** — the client appears to enter a self-sustaining
  retry/backoff spin once triggered by repeated corrupted-packet
  disconnects, independent of whether this project keeps sending
  anything. **Proactively force-stopped the game process** once this
  pattern was observed, rather than waiting to see if it would cascade
  into another ANR. `am force-stop` **worked cleanly this time**
  (`exit 0`, unlike the E2E-012 incident where it hung) — CPU returned
  to ~0%/396% idle within 3 seconds, and `screencap` confirmed working
  immediately after. **Device left healthy and idle at the end of this
  pass.**
- **New operational lesson for future passes**: even a SINGLE clean live
  attempt against this client can trigger a lasting client-side CPU spin
  once the connection disconnects on repeated corrupted packets — this
  is a property of the CLIENT's own reconnect/backoff behavior when
  fed corrupted BaseApp packets, not something proportional to how many
  test iterations this project runs. Monitoring CPU via `top` and being
  ready to force-stop promptly after each live BaseApp-channel test
  (not just after a long session) is now recommended practice, not just
  a fix for repeated-abuse cases.

### RESULT
- Device health: fully recovered post-reboot, confirmed at both start
  and end of this pass.
- Key-extraction technique: further validated (3rd independent process).
- Chain-IV hypothesis: **inconclusive** — genuinely new evidence (a
  distinct checksum-failure error) but not a confirmation; still blocked
  from reaching Account/Avatar/Lobby.
- `CLIENT_MODIFIED: NO`.

### NEXT_ACTION
1. Investigate the new checksum error specifically: find where Mercury
   computes/validates this "wanted 04040101" checksum in disassembly
   (likely near `Nub::processFilteredPacket`, a function this project
   has referenced by name in logs but not yet disassembled) — this is a
   concrete, well-evidenced new static-analysis target, more promising
   than continuing to guess at chaining variants blindly.
2. If a checksum/CRC field is confirmed required, determine its
   algorithm and where in the packet it goes (likely the LoginApp
   channel's own 2-byte "footer" — previously treated as a fixed
   constant `00 00` — may actually BE a checksum that happens to
   validate correctly by construction for LoginApp's specific content,
   worth re ‑examining rather than assuming it's inert padding).
3. Continue pacing live tests conservatively (one clean iteration at a
   time, CPU-checked, promptly force-stopped) per this pass's adopted
   practice.

---

## TEST_ID: E2E-014
- **DATE**: 2026-09-15 (same day, fourteenth pass), per the coordinator's
  instruction to statically locate the Mercury checksum
  computation/validation code using the same alternate-path technique
  that worked for `createBasePlayer` in E2E-011.
- **GOAL**: (1) find the checksum algorithm/byte-range; (2) implement it;
  (3) debug and fix the chain-IV code once a real bug surfaced during
  live re-testing; (4) live-verify the chain-IV hypothesis cleanly.

### 1. Found a genuine standard CRC-32 implementation in the binary — but likely unrelated
Searching `.rodata` for the well-known reflected CRC-32 (IEEE 802.3,
polynomial `0xEDB88320`) table's first entries found an **exact,
byte-for-byte 256/256 match** at rodata `0x2be798c`
(`scratch/verify_crc32_table.py`). Located its update function (a tiny
leaf function at `0x1cc3988`, textbook `crc = table[(crc^byte)&0xFF] ^
(crc>>8)`) and all 4 of its `BL` callers (`0x1248fac`, `0x127d950`,
`0x12a0270`, `0x12a0524`), each using the standard `init=0xFFFFFFFF` /
`finalize=~crc` convention — i.e. byte-for-byte equivalent to Python's
`zlib.crc32()`/`binascii.crc32()`. **However**: all 4 callers sit at
addresses (~`0x12xxxxx`) far from the `Nub`/`Channel` packet-validation
cluster (`~0x98fxxx-0x99xxxx`), and each caller's own calling pattern
(`mov x0,ptr; bl <length-getter>; crc(&state,ptr,len)`) looks like a
generic "CRC32 of a string" utility, most plausibly used for
resource/asset-name hashing (a common CRC32 use in game engines) — **NOT
confirmed to be the Mercury packet checksum**. Kept as a concrete,
reusable candidate algorithm, not a proven answer.

### 2. Exhaustive static search for the checksum error string's real call site — NEGATIVE, 5 independent methods
Attempted to locate `Nub::processFilteredPacket(...): Packet (flags %hx,
size %d) failed checksum (wanted %08x, got %08x)`'s actual `.text` call
site, since `06_trace/LOGIN_REPLY_MERCURY_ENVELOPE.md` already flagged
this string as apparently unreferenced ("vestigial") in an earlier pass.
Verified/extended that finding with 5 independent methods this pass, all
negative:
1. Corrected the string's TRUE start address (an earlier substring match
   in this pass initially pointed mid-string) and re-ran a direct
   ADRP+ADD scan — zero hits.
2. Widened the ADRP-to-ADD window to 200 bytes — zero hits.
3. A full-file raw 8-byte pointer scan (in case of an indirect
   pointer-table reference) — zero hits.
4. Located `Nub::processFilteredPacket`'s real prologue (`0x98fa30`,
   already known from `06_trace/MERCURY_REPLY_DISPATCH_TRACE.md`'s own
   prior "bad flags" trace) and manually disassembled ~0x200 bytes
   forward from the "flags in range" branch — reached footer/fragment
   logic without encountering the checksum check or its string load.
5. Found that DIFFERENT log-severity levels route through DIFFERENT
   shared varargs log functions (confirmed: `0x1cad7ac` for WARNING-level
   calls like "bad flags", `0x1cad604` for ERROR-level calls like
   "Discarding bundle due to corrupted header") — enumerated ALL 2019
   combined callers of both functions and resolved each call site's `x0`
   (format string pointer) via the same clean "between consecutive
   calls" dataflow method that correctly decoded the `ClientInterface`
   table in E2E-011. **Zero matches** for the checksum string's address
   among either function's callers.
**Conclusion**: this is now a well-corroborated (not merely repeated)
negative result across 5 independently-designed methods, reusing every
technique that has worked elsewhere in this project. The checksum
string's real call site remains unlocated — either genuinely dead code
in this build (matching the prior pass's own "vestigial strings"
conclusion, now much better evidenced), or resolved through a codegen
pattern this project's tooling cannot yet detect (e.g. a
severity/category-indexed table this project hasn't identified).

### 3. Live re-test of the chain-IV hypothesis — found and fixed a real bug, then got a CLEAN negative result
While preparing a live test, added temporary debug logging to
`_last_plain_block_by_host` reads/writes and discovered a **genuine
implementation bug** (now fixed): the `createBasePlayer` push's
plaintext (`[flags][msgid=4][len=4][entityId=1]`, padded to 16 bytes)
has an **all-zero last-8-byte block** — because `entityId=1`'s upper 3
bytes are zero and the 7 bytes of padding are also zero, the ENTIRE
chaining seed stored for the next message degenerates to
`0000000000000000` after the first `createBasePlayer` push fires. This
corrupted every RETRY after the first within a test run (all retries
after #1 incorrectly chained from this degenerate all-zero block instead
of a real previous-message tail) — explaining an apparent inconsistency
between this pass's live results and expectations. Removed the debug
logging after diagnosis; the degenerate-tail issue itself is a known,
documented limitation (inherent to short messages where only 1 byte of
real content falls in the last 8-byte window) rather than something
fixed outright this pass, since it turned out not to matter for the
core question (see below).

**With this understood, isolated the FIRST ack of a fresh test (fresh
`PID 23452`, fresh key `5a323628`, un-corrupted by the degenerate-tail
bug since it fires before any `createBasePlayer` push)**: `chain_iv`
correctly resolved to LoginApp's real last plaintext block
(`7856341200000000`, verified via debug log). **Result: `Nub(...)::
processFilteredPacket(...): received packet with bad flags 5679`** —
still garbage, still rejected. **This is a CLEAN negative result for the
chain-IV hypothesis** (not confounded by the earlier bug, not confounded
by a wrong key) — chaining from LoginApp's last plaintext block does
**NOT** produce correct decryption for the first BaseApp message.
**CONFIRMED (negative)**: the "literally shared, state-carrying
`EncryptionFilter` object" hypothesis from E2E-012 is now disproven for
the simple IV=last-LoginApp-block form, even though the KEY itself
remains confirmed shared (a genuinely different, more surprising
combination of facts than initially assumed — same key, but NOT simply
continuous chaining state).

### CPU/pacing note
Followed the adopted practice: one paced test iteration, `top` checked
immediately after (`chiji` at 25.9%, settling to 11.6% within the next
check) — no runaway spin this pass, device remained healthy throughout.

### RESULT
- CRC-32 implementation found and characterized, but not confirmed
  relevant — a real, reusable static-analysis contribution regardless.
- Checksum string's call site: confirmed unlocatable via 5 independent
  methods — a strong, well-evidenced negative result, not abandoned
  early.
- Chain-IV hypothesis: **cleanly disproven** for the simple
  "continue-from-LoginApp's-last-block" form, after fixing a real
  implementation bug that had been confounding earlier reads.
- Did not reach Account, Avatar, or Lobby this pass. `CLIENT_MODIFIED: NO`.

### NEXT_ACTION
1. The chain-IV hypothesis is disproven in its simplest form, but the
   KEY-SHARING finding (E2E-012) remains solid and surprising — worth
   reconsidering what ELSE could explain two channels sharing a key
   without sharing simple linear chaining state (e.g. per-channel/
   per-direction sub-state within one shared object, a channel-id or
   address mixed into the IV, or the object being copied/cloned with the
   key preserved but a chaining counter reset).
2. Given static analysis of the checksum path has now been tried
   thoroughly and exhausted with this project's current tooling, the
   remaining productive avenues are either (a) a fundamentally different
   static technique not yet tried (e.g. locating the function via its
   position relative to already-confirmed neighboring functions like
   `Nub::handleMessage`'s `0x991f00`-`0x992034` region, rather than via
   string or log-function xrefs at all), or (b) accepting this specific
   sub-problem as blocked pending better tooling/dynamic instrumentation
   (still unavailable per the standing native-bridge/classifier
   blockers), and redirecting effort to re-examining whether the
   `pc_variant` chaining/key model itself needs revisiting from scratch
   for this specific channel via fresh disassembly of the BaseApp-side
   decrypt call site (if one distinct from LoginApp's `0x989600` exists).

---

## TEST_ID: E2E-015
- **DATE**: 2026-09-15 (same day, fifteenth pass), per the coordinator's
  instruction to check whether the BaseApp channel's decrypt call path is
  genuinely distinct from LoginApp's, tracing forward from
  `Nub::recreateListeningSocket`'s call chain — pure static analysis,
  no live testing this pass.
- **GOAL**: settle whether a different chaining mode or channel-specific
  cipher-state input exists for BaseApp, using the same alternate-path
  technique (trace from a known neighboring function) that worked for
  `createBasePlayer` in E2E-011.

### MAJOR FINDING: the shared-filter-object hypothesis is now CONFIRMED BY DISASSEMBLY, not just live-memory coincidence
Located `Nub::recreateListeningSocket`'s own log call (`"Nub::
recreateListeningSocket %p %s\n"` at rodata `0x2a5ce3d`) via the SAME
"enumerate all callers of the relevant shared log function, resolve each
call site's `x0` via clean between-calls dataflow" method used for
`createBasePlayer` and the checksum string — this time against a THIRD
shared log helper (`0x1cadbb4`, apparently the INFO-level one, found by
inspecting the already-known `checkScriptBaseAppAddr` log call at
`0x93a194`; distinct from `0x1cad7ac` WARNING and `0x1cad604` ERROR).
**Found the single exact match**: `0x98cb20`, inside
`Nub::recreateListeningSocket` itself.

Tracing `recreateListeningSocket`'s own body found it to be purely
socket-level (bind + setsockopt calls, no encryption-related code) — as
expected, since binding a UDP socket is a lower layer than the
Mercury `Channel`/`EncryptionFilter` abstraction. Tracing its CALLER,
`BaseAppLoginRequest::initNetwork` (prologue `0x9389dc`, already known
from `06_trace/BASEAPP_LOGIN_SERIALIZATION.md`), found the real answer a
few instructions after the successful bind:

```
0x938b0c: ldr x23, [x20, #0x148]   ; x20 = ServerConnection*, +0x148 =
                                     THE EXACT SAME EncryptionFilter cache
                                     slot documented in
                                     FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md
                                     for the LoginApp channel
0x938b1c-0x938b40: refcount++ (twice, intrusive-ptr convention) on x23
0x938b4c-0x938b60: bl 0x984a54(newChannelObj, ServerConnection, flag=1,
                              &x23 [the filter ptr], flag2=0)
```

Inside the constructor at `0x984a54` (the new BaseApp `Channel`-shaped
object):
```
0x984aa0: ldr x8, [x4]            ; x8 = the SAME filter pointer (via &x23)
0x984aa8: str x8, [x19, #0x40]    ; new Channel object's +0x40 = filter ptr,
                                     STORED DIRECTLY -- no copy, no new
                                     BF_KEY, no new key material of any kind
0x984aac-0x984ac0: refcount++ on that SAME object
```

**CONFIRMED BY BINARY**: the BaseApp `Channel` object's own encryption
slot (`+0x40`) is populated with the LITERAL SAME `EncryptionFilter`
pointer read out of `ServerConnection+0x148` — not a copy, not a
freshly-constructed object with a coincidentally-matching key. This
independently proves, via static disassembly, what E2E-012's live
memory scan could only show empirically (same key value found twice):
**it really is the same object.**

### Direct answer to the coordinator's question: NO, there is no distinct BaseApp decrypt call path to find
Since both channels hold a pointer to the identical object, and that
object's `decrypt`/`encrypt` methods are almost certainly invoked via
virtual dispatch (`ldr x8,[x0]; ldr x8,[x8,#offset]; blr x8`, the
pattern already established for `EncryptionFilter` in prior passes) —
**by construction, BOTH channels execute the exact same machine code**
for encryption/decryption (the same `0x989600`-region implementation
already characterized for LoginApp). There is no separate chaining mode,
no channel/address-specific mixing, and no distinct call site to find
for BaseApp specifically — this line of investigation is **closed with
a definitive, code-level answer**, not abandoned from lack of effort.

### What remains genuinely unexplained
Given the object, key, AND code path are now all CONFIRMED identical,
yet BaseApp messages still decrypt to garbage under both tested IV
hypotheses (E2E-008's IV=0, E2E-014's IV=chained-from-LoginApp's-last-
block), the remaining explanation must be about **the object's internal
STATE at the exact moment of decryption** — something mutates the shared
filter's chaining/IV state between when this project captures the key
(via the live memory scan) and when the client's own decrypt() call for
our reply actually executes, that this project has no visibility into.
Candidates (UNTESTED, listed for a future pass):
1. The client's own internal Mercury housekeeping (channel handshake
   acks, keepalive/piggyback packets) may also pass through this shared
   filter between the LoginApp reply and the BaseApp exchange, advancing
   whatever internal counter/IV state exists, invisibly to this project.
2. The per-message IV might not be a simple "previous plaintext block"
   at all (E2E-014 already disproved that specific form) but could
   incorporate something this project hasn't identified — e.g. a
   sequence number, timestamp, or address/port value XORed in before the
   `pc_variant` XOR-chain begins.
3. `EncryptionFilter`'s actual field layout may include an explicit IV/
   state field this project hasn't located (distinct from `BF_KEY` itself,
   which per OpenSSL convention holds only the P-array/S-boxes, not
   chaining state) — a fresh, targeted disassembly of the filter object's
   full field layout (beyond the `+0x10`/`+0x2c`/`+0x30` fields already
   documented) is a concrete next static target.

### RESULT
- **Confirmed, definitive, code-level answer** to this pass's specific
  question (no, BaseApp does not use a distinct decrypt path) — a real
  milestone even though it doesn't yet unblock progress.
- The persistent "same key, same object, same code, wrong output" puzzle
  remains open. Per the coordinator's own guidance, this is reported
  plainly as still-unsolved rather than papered over with another guess.
- `CLIENT_MODIFIED: NO`. No live testing this pass (pure static analysis).

### NEXT_ACTION (superseded within this same pass — see addendum below)
1. ~~Locate `EncryptionFilter`'s complete object layout... looking for an
   IV/state field~~ — **DONE, this same pass, see addendum below.**
3. See `06_notes/BASEAPP_CRYPTO_BLOCKER_SUMMARY.md` (new this pass) for
   the full consolidated history (E2E-008 through E2E-015) in one place.

### ADDENDUM (same pass, continued): hidden IV/state hypothesis RULED OUT — the puzzle is deeper than framed above
Immediately pursued this section's own NEXT_ACTION #1 with the remaining
time budget (still pure static analysis). Two direct disassembly checks,
both negative for "hidden state":

1. **Object size**: `EncryptionFilter`'s `operator new` call site
   (`0x93a8f0: mov w0, #0x38`) confirms the object is exactly 56 bytes —
   vtable+refcount+key-string+length+bool+`BF_KEY*` accounts for all 56
   bytes with nothing left over for a hidden field.
2. **Decrypt function itself** (`0x989600`, full dump saved to
   `scratch/trace_989600.txt`): the "previous plaintext block" pointer is
   a **local register (`x25`), explicitly reset to NULL at the top of
   EVERY call** (`0x9896a4: mov x25, xzr`) — categorically no state
   persists between separate `decrypt()` invocations. IV=0 is the ONLY
   structurally correct starting point, always. This dump also
   re-confirmed the sibling encrypt function matches this project's
   `bf_encrypt()` implementation exactly, block-for-block.

**This rules out ALL THREE candidate explanations** listed earlier in
this same entry (no state to advance via other traffic; no hidden field
to incorporate anything into; nothing to look for beyond the 3 already-
documented fields). Given key, object, code path, AND algorithm/IV are
now ALL confirmed identical and correct — yet BaseApp still fails where
LoginApp succeeds — **the real open question is reframed**: not "which
crypto parameters" (fully closed out) but **"which exact byte range of
the wire packet does the BaseApp receive path actually feed into this
decrypt function"** — i.e. a framing/offset question, not a crypto
question. This project's "whole packet is ciphertext" assumption
(established in E2E-008 from a block-size-error observation) may not
be quite right in some detail specific to the BaseApp channel.

**Next concrete static target**: find the CALLER of `0x989600` on the
BaseApp/`processFilteredPacket` receive path specifically (distinct from
the already-characterized LoginApp/`onLoginReply` caller) to read its
exact src/dst/length arguments — not yet attempted this pass (time
budget), the clear next step for whoever continues this thread. See
`06_notes/BASEAPP_CRYPTO_BLOCKER_SUMMARY.md` for the fully updated,
consolidated version of this reasoning.

---

## TEST_ID: E2E-016
- **DATE**: 2026-09-15 (same day, sixteenth pass), per the coordinator's
  instruction to find the caller of `0x989600` specifically on the
  BaseApp receive path and read its exact src/dst/length arguments.
- **GOAL**: resolve the framing/byte-range question E2E-015 reframed the
  blocker into.

### Correction found first: 0x989600 has exactly ONE caller in the whole binary — and it isn't generic
Searching for `BL` callers of `0x989600` found **exactly one**:
`0x938234`, inside `LoginHandler::onLoginReply` itself. This means
`0x989600` was NEVER a generically-dispatched, per-channel decrypt
function at all — it's a **private helper hardcoded for the specific,
fixed 20-byte LoginReply body**, called directly (not virtually) only
from that one place. This project's working assumption since E2E-007
(that `0x989600` is "the" EncryptionFilter decrypt used for all
channels) was **incomplete** — a real, separate generic decrypt function
exists and had not been distinguished from this one.

### Found the REAL generic decrypt function: `0x98924c`
First had to fix a mistake made earlier in this same pass: reading
`EncryptionFilter`'s vtable contents directly from the file's raw bytes
at `0x37dd3a0` gave nonsense values (e.g. `0x8002`) — because, like the
`.data.rel.ro` pointers investigated for `createBasePlayer` in E2E-011,
these are **`R_AARCH64_RELATIVE` relocation targets**, not literal
pointers in the static file; the TRUE values live in `.rela.dyn`'s
`r_addend` fields. Parsing `.rela.dyn` for offsets `0x37dd390`-`0x37dd400`
recovered the real vtable: `[0x988ecc, 0x988f1c, 0x988f68, 0x989444,
0x989700 (a trivial "return 8" block-size getter — nice sanity check,
8 = Blowfish's block size), ..., 0x989794, 0x989814, 0x9898fc, 0x989aa4,
0x989c48]`.

`06_notes/FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md` had already listed
THREE addresses together as "the encrypt/decrypt call targets"
(`0x98924c`, `0x989600`, `0x98938c`) without individually characterizing
each. Disassembling all three this pass:
- **`0x989444`**: the SEND-side wrapper (checks a condition via
  `bl 0x98924c`, then either returns early or tail-calls onward to
  `0x996f2c`) — this is `send()`/encrypt-on-send, not decrypt.
- **`0x98938c`**: contains the SAME `pc_variant` IV=0 XOR-chain loop
  structure as `0x989600`, parameterized by an explicit length argument
  (`w3`) rather than reading it from a packet object — likely a
  lower-level shared primitive both `0x989600` and `0x98924c` call
  into, or an alternate direct-length entry point.
- **`0x98924c`**: **THE REAL GENERIC RECEIVE-PATH DECRYPT FUNCTION.**
  Checks `filter+0x2c` (the "enabled" bool, same field already
  documented), then:
  ```
  0x989278: ldrh w8, [x19, #0x1a]   ; w8 = packet_obj+0x1a (a length field)
  0x98927c: ldrh w9, [x19, #0x1c]   ; w9 = packet_obj+0x1c (ANOTHER length field)
  0x989280: add x22, x9, x8         ; total decrypt length = w8 + w9
  0x989284: and w10, w22, #7        ; must be a multiple of 8 (the block-size check)
  ...
  0x9892d0: add x25, x19, #0x60     ; decrypt SOURCE = packet_obj + 0x60
  ```
  **CONFIRMED**: `packet_obj+0x60` is the SAME offset
  `06_trace/MERCURY_REPLY_DISPATCH_TRACE.md` already proved is wire byte
  0 (the flags field) — so decryption DOES start at the true beginning
  of the wire packet, matching this project's working assumption. **But
  the LENGTH is NOT simply "however many bytes were received"** — it is
  read back out of two separate 16-bit fields the receive path
  populates BEFORE this call, and (per a nearby code path at `0x98fc54`-
  `0x98fc74` inside `processFilteredPacket`) these two fields get
  **reclassified relative to each other** (4 bytes moved from one to the
  other, sum unchanged) when certain Mercury footer flags (sequence
  number, etc.) are detected on the packet.

### Unplanned side discovery: an inline SIMD checksum/hash, not a callable function
While tracing where `packet_obj+0x1a`/`+0x1c` first get populated,
found a block of NEON/SIMD instructions (`eor v0.16b,...`, `dup
v1.4s,...`, around `0x98fce0`-`0x98fd10`) directly inside
`processFilteredPacket`'s own body — consistent with an **inlined
checksum or hash computation**, not a separate callable function. This
plausibly explains E2E-014's exhaustive, 5-method failure to find the
"failed checksum" error's real call site via any function-call-based
search: **the checksum logic may not be in a separate function at all**,
so no amount of caller-enumeration could have found it. Not further
characterized this pass (time budget) — flagged as a concrete lead for
whoever continues this thread.

### RESULT
- **Corrected a standing project assumption**: `0x989600` is NOT a
  generic per-channel decrypt function; `0x98924c` is. This project's
  BaseApp testing (E2E-008 through E2E-015) was reasoning about the
  right ALGORITHM (confirmed still correct — same `pc_variant`, same
  IV=0, same key, same object) but had not yet examined the ACTUAL
  receive-path length computation this pass now exposes.
- **The framing/byte-range question from E2E-015 has a partial answer**:
  decrypt starts at the right place (wire offset 0) but its LENGTH
  depends on packet-object metadata fields this project has not fully
  traced to their origin — genuinely still open, not solved.
- Found a strong new lead (inline SIMD checksum) explaining a previous
  dead end, itself not yet resolved.
- Did not reach a live-testable fix this pass — the exact value/origin
  of `packet_obj+0x1a`/`+0x1c` for a "normal" (non-footer) packet was not
  fully traced within this pass's time budget. **No live testing was
  attempted this pass** (would have been premature without knowing the
  correct length to send). `CLIENT_MODIFIED: NO`.

### NEXT_ACTION
1. Trace `processFilteredPacket`'s EARLIEST population of
   `packet_obj+0x1a` (before any footer-flag reclassification) back to
   its source — almost certainly derived from the raw UDP `recvfrom()`
   byte count or an explicit length field read from the wire near the
   flags field, but not yet confirmed which. This is the single most
   concrete remaining static target.
2. Separately, characterize the inline SIMD checksum block
   (`~0x98fce0`-`0x98fd10`) to determine if it's the actual "failed
   checksum" mechanism, its exact algorithm, and its input byte range.
3. Once both are understood, compute the correct BaseApp ack length/
   content and test live (one paced iteration, CPU-monitored).

---

## TEST_ID: E2E-017
- **DATE**: 2026-09-15 (same day, seventeenth pass), per the
  coordinator's instruction to trace `packet_obj+0x1a`/`+0x1c`'s origin
  back to whatever constructs the packet object from a raw `recvfrom()`
  result, and in parallel characterize the inline SIMD checksum block.
- **GOAL**: get a disassembly-derived, concrete BaseApp ack length/
  content before any further live testing.

### MAJOR FINDING: a whole alternate dispatch path may explain the entire mystery
Found `processFilteredPacket`'s (`0x98fa30`) actual caller by searching
for plain `B` (tail-call) instructions rather than `BL` — it has ZERO
direct `BL` callers (confirmed, again) but IS reached via tail-calls
from **two** sites, one of which (`0x98d49c`) is the END of a real,
separate dispatcher function (prologue `0x98d38c`) that does something
far more significant than expected:

```
0x98d38c: this=Nub*, x1=arg, x2=packet_obj  (real function, own stack frame)
  x0 = Nub + 0x41f0                    ; a per-source-address CHANNEL MAP
  bl 0x9950d8                          ; map::find()-shaped lookup, keyed by
                                          the packet's source address (x1)
  compare result against Nub+0x41f8    ; the map's "end" sentinel
  IF FOUND (an INDEXED/REGISTERED channel exists for this source address):
    x22 = the found channel object
    IF channel_obj+0xf8 flag is set:
      ldr x8, [x22]        ; x22's OWN vtable pointer
      ldr x8, [x8, #0x18]  ; slot +0x18
      blr x8               ; VIRTUAL DISPATCH -- args (channel_obj, Nub*, x2, packet_obj)
      -- processFilteredPacket is NEVER CALLED for this packet --
  ELSE (no registered channel for this source address):
    falls through to `b 0x98fa30` (processFilteredPacket, the generic
    path this project has been analyzing since E2E-014/E2E-016)
```

**Why this matters enormously**: `BaseAppLoginRequest::initNetwork`
(E2E-015) explicitly CONSTRUCTS a `Channel`-shaped object for the new
BaseApp socket, sharing the LoginApp `EncryptionFilter`, BEFORE the
client even sends its first `baseAppLogin` packet. If that construction
also REGISTERS the new channel in this SAME per-address map (highly
plausible — this is exactly what BigWorld's own "indexed channel"
terminology, already seen in this project's earlier vestigial-string
survey, describes), then **every subsequent packet on the BaseApp
socket — including any reply this project sends — would be routed
through the CHANNEL-SPECIFIC virtual method at `vtable+0x18`, NOT
through the generic `processFilteredPacket`/`0x98924c` pair.** This
would mean this project's careful E2E-014/E2E-016 length/offset analysis
of the generic path, while internally correct, may **simply not apply
to the BaseApp channel at all** once it becomes "indexed" — a
structurally different receive path with potentially different framing.

This directly and elegantly explains the entire E2E-008-through-E2E-016
puzzle: LoginApp's exchange happens on a connection that does NOT yet
have an indexed channel (hence goes through the generic path this
project correctly reverse-engineered and which correctly decodes), while
BaseApp's exchange happens on a connection that **already does** have
one (constructed explicitly in `initNetwork`), routing through an
entirely different, not-yet-characterized virtual method instead.

### What was NOT completed this pass (time budget)
- Whether `BaseAppLoginRequest::initNetwork` actually INSERTS its new
  Channel into this specific map (`Nub+0x41f0`) was not confirmed —
  this is the load-bearing link in the hypothesis and the single most
  important thing to verify next.
- The channel object's own vtable was partially recovered (base
  `0x37dd280` via `.rela.dyn`, slots `+0x00`→`0x98530c`, `+0x08`→
  `0x985b3c`, `+0x10`→`0x9879f0`), but slot `+0x18` (the one actually
  called) has NO `.rela.dyn` entry — its raw file bytes read as
  `0xd02fdc`, which DOES disassemble to a plausible, well-formed
  function, but this reading is **UNVERIFIED**: every OTHER slot in this
  same vtable needed a relocation to get its true value, so a slot
  *without* one needs independent confirmation before trusting
  `0xd02fdc` at face value (it could be a non-pointer value, e.g. a
  virtual-base offset for multiple inheritance, coincidentally
  resembling a valid function prologue).
- The inline SIMD/checksum block (`~0x98fce0`-`0x98fd10`) was NOT
  characterized this pass — time went to the higher-value dispatch
  finding above instead, per the coordinator's own "if time allows"
  framing for that side-thread.

### RESULT
- **Real, significant architectural finding**: a plausible, well-
  evidenced explanation for why the generic-path analysis hasn't
  produced a working BaseApp reply — the packets may not even be using
  that path once the channel is indexed.
- **NOT YET CONFIRMED** — the load-bearing link (does `initNetwork`
  register into this exact map?) and the target function itself (is
  `0xd02fdc` real?) both need verification before this can be acted on.
- Per the coordinator's own standing guidance, **no live test was
  attempted** — testing a still-unconfirmed hypothesis about a fix for
  a still-unconfirmed root cause would not have been a meaningful
  experiment. `CLIENT_MODIFIED: NO`.

### NEXT_ACTION
1. Confirm whether `BaseAppLoginRequest::initNetwork` (or the Channel
   constructor `0x984a54`, or code shortly after either) writes into the
   `Nub+0x41f0` map — search for `BL` callers of `0x9950d8` (or its
   insertion counterpart, likely a sibling `insert`/`operator[]`-shaped
   function) within `initNetwork`'s own body or its immediate callees.
2. If confirmed, verify `0xd02fdc` is genuinely the vtable`+0x18` target
   (cross-check via a second independent method, e.g. confirming its own
   RTTI/typeinfo backlink, or checking if OTHER known Channel-shaped
   objects in this binary share this same vtable base) before
   disassembling it in depth as "the real BaseApp decrypt path."
3. Only once both are confirmed should a live test be attempted.

### Follow-up within this same pass: item 1 attempted, inconclusive (not disproven)
Checked `initNetwork`'s own body directly for a `MOVZ`-encoded `0x41f0`/
`0x41f8` immediate (the map-offset constants) — none found; the map
insertion, if it happens, is not inlined directly in `initNetwork`
itself. Also inspected the function called immediately after the Channel
constructor (`0x938e04`) — its body looks like Python/script callback
registration (iterating message IDs ≥0x80, static-init-once guards, a
repeated `bl 0x98bc74` call per ID), not obviously channel-map insertion.
**Neither check confirms NOR refutes the hypothesis** — map registration
could easily happen inside one of the OTHER not-yet-disassembled callees
in this region (e.g. `0x992764`/`0x992994`, called a few lines later in
`initNetwork` per the E2E-015 dump, gated on a global enabled-flag) or
inside the Channel constructor's own tail (only the first ~0x120 bytes of
`0x984a54` have been read so far). Genuinely still open, not a dead end —
flagged as the concrete starting point for whoever continues this pass.

---

## TEST_ID: E2E-018
- **DATE**: 2026-09-15 (same day, continuation pass), per the coordinator's
  explicit instruction to resolve E2E-017's two open items: (1) does
  `initNetwork` actually register the new BaseApp Channel into the
  `Nub+0x41f0` indexed-channel map, and (2) is `0xd02fdc` (the raw bytes
  read at vtable slot `+0x18`) genuinely the channel-specific decrypt
  dispatch target. Pure static disassembly, read-only, no live test (none
  was justified yet going in, and none is justified now — see RESULT).

### Item 1 — CONFIRMED: registration into the indexed-channel map is real
Disassembled `0x992764` and `0x992994` in full:
- `0x992764(this=Nub*, x1=value, x2=key)`: computes an index via
  `bl 0x989cdc(x19+0x18)`, validates `index<0x400` (else logs an error via
  `0x1cad604`), sets a bitmap bit at `Nub+0x40e0`, and stores `value` at
  `Nub + index*8 + 0xe0`. This is the map's **insert** function.
- `0x992994` is its mirror-image **remove**: clears the same bitmap bit
  (`bic`) and stores `xzr` at the same slot.

Cross-referencing back to the already-captured E2E-015 disassembly dump of
`BaseAppLoginRequest::initNetwork` (`0x938bd0`-`0x938bfc`): the function
calls `0x992994` conditionally (gated on a global static flag AND `w21`
bit 0 — almost certainly "if a stale channel was previously registered for
this slot, remove it first"), immediately followed by an
**unconditional** call to `0x992764` with `x0=[x20+0x138]` (the Nub*),
`x1=x19` (the freshly-constructed BaseApp Channel object), `x2=xzr`.

**This confirms Link #1: the BaseApp Channel object genuinely IS inserted
into the Nub's indexed-channel map (`Nub+0x41f0`/`+0x40e0`/`+0xe0`).** The
E2E-017 dispatcher finding (`0x98d38c`: packets from a registered source
address are looked up in this map and, if found, dispatched via
`channel_obj->vtable[0x18]` instead of the generic
`processFilteredPacket`) genuinely applies to BaseApp traffic. This part
of the hypothesis is not speculative anymore.

### Item 2 — REFUTED: `0xd02fdc` is not decrypt code, and the whole "vtable+0x18 decrypt method" idea is now dead
Two independent checks, both negative for the specific hypothesis:

1. **Disassembled `0xd02fdc` in full (~0x300 bytes).** It is a classic
   red-black-tree/`std::map` find-or-erase routine (tree descent via
   `ldr w11,[x10,#0x20]; cmp w22,w11`, rotate/fixup patterns on parent
   pointers). No call to `0x806e00` (`BF_ecb_encrypt`), no access to a
   `+0x30`-shaped `BF_KEY*` field, no XOR-chain loop. **Not decrypt code.**
2. **Exhaustively re-scanned BOTH `.rela.dyn` and `.rela.plt`** for any
   `R_AARCH64_RELATIVE` entry whose `r_offset` falls in
   `[0x37dd280, 0x37dd2e0)` (the vtable-blob range spanning both stored
   pointers found in the Channel constructor, `0x37dd280` and `0x37dd2a8`).
   Full result:
   ```
   0x37dd280 (+0x00) -> 0x98530c
   0x37dd288 (+0x08) -> 0x985b3c
   0x37dd290 (+0x10) -> 0x9879f0
   0x37dd298 (+0x18) -> NO RELOCATION ENTRY (confirms E2E-017's flag)
   0x37dd2a0 (+0x20) -> 0x37dd2c0   (points back inside this same blob)
   0x37dd2a8 (+0x28) -> 0x985b34   (== object+0x08's own "+0x00" slot)
   0x37dd2b0 (+0x30) -> 0x985b60   (== object+0x08's own "+0x08" slot)
   0x37dd2c8 (+0x48) -> 0x2a5c200
   0x37dd2d8 (+0x58) -> 0x37dd378
   ```
   This is the textbook Itanium C++ ABI layout for a class with **two**
   virtual bases sharing one combined vtable-group blob: three real
   function slots (`+0x00/+0x08/+0x10`), then an **offset-to-top field for
   the secondary base at `+0x18`** (a plain constant integer, NOT a
   pointer — which is exactly why it has no relocation entry) and a
   typeinfo pointer at `+0x20`, then the secondary sub-vtable's own two
   function slots at `+0x28/+0x30` (which are the SAME two functions
   `object+0x08`'s vtable pointer, `0x37dd2a8`, resolves at its own
   `+0x00/+0x08`). Disassembling all 5 real function slots
   (`0x98530c`, `0x985b3c`, `0x9879f0`, `0x985b34`, `0x985b60`) confirms
   they are boilerplate reference-counted-object plumbing, not
   encryption:
   - `0x98530c`: destructor worker (deregisters from something via
     `bl 0x99267c`, decrements/releases a couple of member handles).
   - `0x985b3c` / `0x985b60`: deleting-destructor thunks (`sub x19,x0,#8`
     adjusts `this` for the secondary base, calls `0x98530c`, then
     `operator delete` at `0x7e1c90`) — classic virtual-destructor-pair
     shape, not decrypt.
   - `0x9879f0`: a stack-guard/overflow check (compares `tpidr_el0`-based
     thread-local watermark values) — unrelated to encryption.
   - `0x985b34`: a one-line `this`-adjusting thunk to `0x98530c`.

   **There is no decrypt-shaped function anywhere in this vtable blob.**
   The raw bytes previously read at `+0x18` (`0xd02fdc`) are simply
   reading into the middle of a small integer constant (the offset-to-top
   field) as if it were code — coincidentally well-formed-looking bytes,
   exactly the risk E2E-017 flagged before trusting it.

### RESULT — mixed, reported plainly per the coordinator's own instruction
- **Link #1 (registration) is CONFIRMED real.** The BaseApp Channel does
  get inserted into the Nub's indexed-channel map, and the E2E-017
  dispatcher (`0x98d38c`) does route registered-source-address packets
  through `channel_obj->vtable[0x18]` instead of
  `processFilteredPacket` — for SOME channel type. This mechanism is
  real and is not a false lead in general.
- **Link #2 (this specific vtable/slot being the decrypt path) is
  REFUTED.** The BaseApp Channel's own vtable (`0x37dd280`, confirmed via
  its constructor `0x984a54`) has no decrypt-shaped function at all — it
  is a plain reference-counted-object interface (destructor + stack-guard
  check), nothing else. Either (a) this Channel object is never actually
  the one looked up by `0x98d38c` for BaseApp login packets (the map
  might be keyed by a DIFFERENT registered object for a different purpose
  entirely — e.g. this vtable shape looks more like it could belong to a
  Timer or generic Mercury `Channel` base with no BaseApp-specific
  behavior), or (b) the indexed-dispatch mechanism, while real, is not
  actually reached for this specific traffic (e.g. the map lookup keyed
  on source address may simply miss/fail for a freshly-connected UDP
  peer that hasn't sent anything yet, falling through to the generic
  path after all). Either way, **the "indexed-channel dispatch explains
  the BaseApp framing blocker" hypothesis, AS A FIX FOR THE CURRENT
  BLOCKER, DOES NOT PAN OUT** — there is no alternate decrypt routine to
  switch to. This closes out the E2E-017 thread with an honest negative.
- Per the coordinator's own explicit fallback instruction: **falling back
  now** to the previous lead — tracing `packet_obj+0x1a`/`+0x1c`'s origin
  in the generic `processFilteredPacket`/`0x98924c` path, and/or
  characterizing the inline SIMD/NEON checksum block
  (`~0x98fce0`-`0x98fd10`) — as the next concrete avenue. Not started this
  pass (time went to fully closing out E2E-017's two open items, which
  was the coordinator's explicit priority this turn).
- No live test was attempted this pass (correctly withheld — no new,
  confirmed-correct decrypt path or framing was found to test).
  `CLIENT_MODIFIED: NO`. All work this pass was read-only static
  disassembly against the existing `.so`/relocation tables; no files
  in `mitm/` were touched.

### NEXT_ACTION
1. Fall back per standing instruction: trace the origin of
   `packet_obj+0x1a`/`packet_obj+0x1c` (fields read by the generic
   `processFilteredPacket` path per the E2E-014/E2E-016 analysis) back to
   where they are first populated — likely in the UDP-recv/packet-alloc
   code upstream of `processFilteredPacket` — to determine whether the
   BaseApp reply's correct length/offset framing differs from what's been
   tried so far for a reason unrelated to indexed-channel dispatch.
2. In parallel/alternatively, characterize the inline SIMD checksum block
   (`~0x98fce0`-`0x98fd10`) to confirm/refute whether a wrong checksum
   (rather than wrong decrypt framing) is the actual rejection cause for
   prior BaseApp reply attempts.
3. Do not revisit the indexed-channel-dispatch idea further unless new
   evidence specifically shows the map lookup in `0x98d38c` actually
   finds and uses THIS Channel object for real BaseApp traffic (e.g. via
   a live trace) — the static evidence this pass gathered points away
   from it as the explanation for the current blocker.

---

## TEST_ID: E2E-019
- **DATE**: 2026-09-15 (same day, continuation pass immediately after
  E2E-018). Per E2E-018's own fallback instruction: pursue tracing
  `packet_obj+0x1a`/`+0x1c`'s origin in the generic `processFilteredPacket`
  path. Pure static disassembly, read-only, no live test.

### Finding: `+0x1a`/`+0x1c`/`+0x1e` are a Packet-object footer-byte-consumption bookkeeping triplet, and `processFilteredPacket` REJECTS any packet where `(+0x1a)+(+0x1c) <= 2`
Re-examined `processFilteredPacket` (`0x98fa30`, `scratch/processFilteredPacket_full.txt`)
around its first read of these fields (`0x98faf4`-`0x98fb04`):
```
0x98faf4: ldrh w8, [x20, #0x1a]
0x98faf8: ldrh w10, [x20, #0x1c]
0x98fafc: add w11, w10, w8
0x98fb00: cmp w11, #2
0x98fb04: b.hi #0x98fb74        ; sum > 2 -> continue to footer/flag parsing
                                  ; sum <= 2 -> falls through to a log call,
                                  ; then returns w0 = -4 (failure)
```
(`x20` = the function's 3rd argument, `packet_obj`, set at `0x98fa58: mov x20, x2`.)

Then found the actual PRODUCER/consumer of these exact three fields
(`+0x18`, `+0x1a`, `+0x1c`, `+0x1e`) — a cluster of small, nearly-identical
"reserve N bytes of footer space" helper functions at `0x981ee0`-`0x982120`
(4 near-duplicate overloads, one per fixed-vs-variable-size caller
convention). Representative body (`0x981fe8`-`0x982028`):
```
x8  = [this, #0x10]          ; the Packet* object
w10 = [x8, #0x18]             ; total capacity
w9  = [x8, #0x1a]             ; running footer-bytes-used counter A
w11 = [x8, #0x1c]             ; running footer-bytes-used counter B
w12 = [x8, #0x1e]             ; running footer-bytes-used counter C
w10 = w10 - 0x1b - w9 - w11 - w12    ; freeSpace = capacity - 27(fixed
                                        header reserve) - sum(A,B,C)
cmp w10, w1(requestedSize)
b.lt  -> FAIL (jump to a shared error path, 0x9822cc)
else:
  x10 = x8 + w9                ; write pointer = base + current offset A
  w9  = w9 + w1                 ; RESERVE: bump counter A by requestedSize
  strh w9, [x8, #0x1a]
  return (x10 + 0x60)           ; pointer for caller to write requestedSize
                                   bytes of footer payload into
```
This is a classic `Packet::reserveFooterSpace(nBytes)`-style allocator: the
Packet object keeps THREE independent running counters (`+0x1a`, `+0x1c`,
`+0x1e`, presumably one per footer-section category — plausibly sequence
numbers, acks, and checksum/indexed-channel-id, matching BigWorld Mercury's
known footer sections) tracking how many bytes of the shared trailing
footer region have already been claimed, so each new section is appended
right after the previous one without overlapping.

### Why this matters for the BaseApp blocker
`processFilteredPacket` requires `(+0x1a)+(+0x1c) > 2` for **every** packet
it processes, unconditionally, before it even looks at which flag bits are
set — this is not a footer-section-specific check, it's a blanket
sanity gate. For a freshly-parsed incoming datagram, these counters must
already have been populated by whatever code parses the raw wire footer
bytes into the Packet object (upstream of `processFilteredPacket`,
presumably right after decrypt succeeds). **Every BaseApp reply this
project has sent so far has been a hand-crafted raw byte buffer with no
attempt to construct a matching trailing-footer section** — so it is
highly plausible that `(+0x1a)+(+0x1c)` reads as `0` (or some other value
`<=2`) for all of them, meaning **they may have been failing this generic
sanity check and returning early with an internal error code (`-4`)
regardless of whether the decrypt/key/framing was otherwise correct** —
independent of, and possibly explaining, some of the earlier "wrong
msgid"/"not enough data" symptoms from E2E-008 (a misconsumed/absent
footer region could shift where the header parser starts reading).

This lines up with an already-captured, previously under-analyzed piece of
evidence: E2E-007's own capture of the CLIENT's outgoing `baseAppLogin`
packet recorded an 8-byte trailer (`00 00 00 14 00 00 02 00`) at bytes
`[16:24]`, previously described only vaguely as "Mercury packet trailing
metadata / footer." That trailer is very likely exactly this kind of
footer-section data, giving a concrete real-world example of what a
similarly-shaped trailer this project's own OUTGOING reply packets are
probably missing should look like.

### What was NOT completed this pass (time budget)
- Did NOT locate the exact function that parses raw incoming wire bytes and
  populates the FRESH `+0x1a`/`+0x1c` values for a just-received datagram
  (i.e., the receive-side counterpart of the send-side `reserveFooterSpace`
  cluster found above). This is the concrete missing piece needed to know
  exactly which wire bytes/format to append to our own replies.
- Did NOT decode the exact semantics of the three counters (which is
  sequence-numbers vs. acks vs. checksum) or cross-reference them against
  the specific flag bits tested later in `processFilteredPacket`
  (bit1/2/3/6/7/8/9 of the flags field at `packet_obj+0x60`) to derive the
  precise byte layout needed.
- Did NOT characterize the inline SIMD/NEON checksum block
  (`~0x98fce0`-`0x98fd10`) — deferred again in favor of this more
  structurally-promising lead.

### RESULT
- **Genuine, concrete, new forward progress** on the fallback lead:
  `packet_obj+0x1a`/`+0x1c`/`+0x1e` are now understood structurally (a
  footer-byte-consumption bookkeeping triplet on the Packet object,
  confirmed via the `reserveFooterSpace`-style allocator cluster at
  `0x981ee0`-`0x982120`), and a concrete, plausible, disassembly-backed
  explanation for the BaseApp rejection is now on the table: our replies
  likely fail `processFilteredPacket`'s blanket
  `(+0x1a)+(+0x1c) > 2` sanity check because they carry no constructed
  footer section at all.
- **Not yet actionable for a live test** — the exact wire format/bytes
  needed to make this check pass is not yet derived (see NEXT_ACTION).
  Per standing instruction, no live test was attempted this pass.
  `CLIENT_MODIFIED: NO`.

### NEXT_ACTION
1. Find the receive-side function that populates `+0x1a`/`+0x1c` for a
   freshly-parsed incoming packet (likely called once per datagram right
   after successful decrypt, before `processFilteredPacket`) — search for
   `BL`/tail-call callers of `processFilteredPacket`'s own caller chain, or
   for a function that WRITES both `+0x1a` and `+0x1c` from values it
   itself read out of a raw byte buffer (as opposed to the `reserveFooterSpace`
   cluster's read-modify-write-from-existing-counter pattern).
2. Once found, derive the exact minimal trailer bytes needed to satisfy
   `sum > 2` (and, ideally, cross-check bit-by-bit against the client's own
   already-captured 8-byte outgoing trailer `00 00 00 14 00 00 02 00` from
   E2E-007, since the same Packet/footer code presumably runs symmetrically
   for outgoing packets on the client and incoming ones on this project's
   server-simulated peer).
3. Only then attempt a live BaseApp reply test with a correctly-appended
   footer section — this would be the first live test whose framing is
   actually informed by a confirmed structural understanding of the
   rejection, rather than a guess.

---

## TEST_ID: E2E-020
- **DATE**: 2026-09-15 (same day, continuation pass immediately following E2E-019).
- **OBJECTIVE**: Trace the receive-side population of `packet_obj+0x1a`/`+0x1c` upstream of `processFilteredPacket`, locate the true generic decryption routine, and determine the exact root cause of the `flags 183` / `failed checksum` rejection on BaseApp reply packets.
- **SCOPE**: Static disassembly of `EncryptionFilter::recv` (`0x989444`), `in_place_decrypt` (`0x98924c`), and `processFilteredPacket` (`0x98fa30`). Read-only disassembly; framing derivation for server-side implementation.

### 1. Root Cause Found: `in_place_decrypt` (`0x98924c`) Resets IV = 0 on EVERY Packet (No Inter-Packet Chaining)
Following E2E-019's NEXT_ACTION, we traced the caller chain upstream of `processFilteredPacket`:
`EncryptionFilter::recv` sits at `0x989444` (vtable slot 3, offset `+0x18`). When a UDP datagram arrives from Mercury, `EncryptionFilter::recv` invokes `in_place_decrypt` at `0x98924c`.

Examining `in_place_decrypt` (`0x98924c`-`0x989360`):
1. **IV Initialization (`0x9892c8`)**:
   ```arm64
   0x9892c8: mov x26, xzr          ; IV = 0 (64-bit zero register!)
   ```
   At the start of **every single packet**, `in_place_decrypt` clears its 64-bit IV register (`x26`) to zero.
   **Crucial Architectural Consequence**: BigWorld Mercury Blowfish encryption operates **per-datagram with IV = 0**. There is **NO inter-packet CBC/pc_variant chaining state** carried across separate UDP packets!
2. **Why Prior Tests Produced `flags 183` and `failed checksum`**:
   In E2E-012, `local_baseapp_capture.py` introduced `chain_iv = _last_plain_block_by_host` to chain BaseApp from LoginApp's last plaintext block. Because the server encrypted block 0 with `chain_iv` while the client decrypted with `IV = 0`:
   - Decrypted block 0 was XORed with `chain_iv ^ 0`.
   - The intended flags `0x0001` were mangled into `0x0183` (`0000 0001 1000 0011` in binary).
   - In BigWorld Mercury packet flags:
     - `0x0001` = `FLAG_IS_RELIABLE`
     - `0x0002` = `FLAG_HAS_PIGGYBACKS` (Bit 1 set!)
     - `0x0100` = `FLAG_HAS_CHECKSUM` (Bit 8 set!)
   - Because Bit 8 was accidentally set by the corrupted IV, `processFilteredPacket` branched to the checksum validation path and rejected the packet with `Packet (flags 183, size 16) failed checksum`!
   - When flags are genuinely `0x0001`, Bit 8 is 0, Bit 1 is 0, and Bit 6 is 0: `processFilteredPacket` **completely skips checksum and piggyback parsing**, jumping straight to `0x99021c` to dispatch the Reply!

### 2. Resolution of `+0x1a` & The Wastage / Padding Mechanism
In E2E-019, it was noted that `processFilteredPacket` checks `(+0x1a) + (+0x1c) > 2`.
Tracing `in_place_decrypt` revealed how `+0x1a` is populated and modified:
1. `packet_obj+0x1a` initially holds the raw decrypted payload length received from the socket.
2. At `0x989324`-`0x989350`:
   ```arm64
   0x989324: ldrb w21, [x24, #-1]   ; w21 = decrypted_data[total_len - 1] (last byte!)
   0x989328: cmp w21, #8
   0x98932c: b.hi #0x989348         ; if w21 > 8 -> drop packet: "Dropping packet from %s due to illegal wastage count (%d)"
   0x989330: ldrh w8, [x19, #0x1a]  ; w8 = current length
   0x989334: sub w8, w8, w21        ; length -= w21 (strip wastage!)
   0x989338: strh w8, [x19, #0x1a]  ; update packet_obj+0x1a
   ```
3. **The Wastage Rule**:
   BigWorld Mercury Blowfish padding uses **wastage count encoding**:
   - The cipher requires datagram size to be a multiple of 8.
   - For an unpadded payload of length `L` (e.g. 12 bytes for a Reply):
     `pad_len = 8 - (L % 8)` (e.g., `8 - (12 % 8) = 4` bytes). Total size = 16 bytes.
   - The padding bytes appended must end with the byte value `pad_len`:
     `padding = b'\x00' * (pad_len - 1) + bytes([pad_len])`.
   - Upon decryption, `0x989324` reads the final byte `w21 = 4 <= 8`, subtracts 4 from `+0x1a`, yielding `+0x1a = 12`.
   - Then `(+0x1a) + (+0x1c) = 12 + 0 = 12 > 2`, which trivially passes the `processFilteredPacket` sanity check without needing any trailer/footer bytes!
   - Conversely, if padded with plain `b'\x00'` bytes: `w21 = 0`, so 0 bytes are stripped, leaving trailing zeros inside the packet stream which corrupted subsequent message offset parsing!

### 3. Complete Specifications for BaseApp Reply (`msgID 0xFF`)
- **Cipher**: Blowfish `pc_variant` (ECB on each block XORed with previous plaintext block).
- **IV**: `b'\x00' * 8` (zero IV for EVERY packet).
- **Key**: The live 4-byte session key (identical to LoginApp session key, confirmed in E2E-012).
- **Unpadded Plaintext (12 bytes)**:
  `[flags: 0x0001 (2B LE)][msgID: 0xFF (1B)][length: 5 (4B LE)][replyID: corr (4B LE)][status: 1 (1B)]`
- **Padded Datagram (16 bytes)**:
  `plaintext + b'\x00\x00\x00\x04'`
- **Encrypted Datagram**: `bf_encrypt(padded, key, mode='pc_variant', iv=b'\x00'*8)` -> 16 bytes sent over UDP.

### RESULT
- **SOLVED**: The entire mystery of `flags 183`, `failed checksum`, and `(+0x1a)+(+0x1c) <= 2` is fully solved at the disassembly level.
- **ACTIONABLE**: Updating `mitm/local_baseapp_capture.py` with IV=0 and wastage padding gives the exact packet structure required by `libclient.so`.

### NEXT_ACTION
1. Update `mitm/local_baseapp_capture.py`'s BaseApp UDP responder to format replies with `iv=b'\x00'*8` and wastage padding `bytes([pad_len])`.
2. Apply the identical wastage padding rule to the `createBasePlayer` push packet (`msgID 0x04`).
3. Execute live verification against the emulator and verify that `processFilteredPacket` accepts the reply cleanly without any checksum error or bad flags warning.

---

## TEST_ID: E2E-021
- **DATE**: 2026-09-16, continuation pass. **Context**: a concurrent session
  (Antigravity/Gemini, see `GEMINI.md`) made major independent progress
  while this session was rate-limited: BaseApp login now reaches
  `status==LOGGED_ON`, `createBasePlayer` succeeds (msgID 5, entity type
  127/Account), and a Mercury reliable-channel ACK responder (committed
  `b5d6f2b`, live-verified per commit `bafa75e`'s message, though the
  actual E2E-022/E2E-023 write-ups referenced in that commit message were
  never actually appended to this doc — only capture-log files were
  committed under that message; this entry is the true next sequential ID
  in this doc, and picks up the narrative from `GEMINI.md` §3 directly).
  New blocker per the coordinator: after the ACK silences the
  "Resending unacked packet #0" retry, the client calls
  `BaseAppExtInterface` method 12 (`identifyVersionPoint`, VARIABLE_LENGTH,
  `[u16 checkpoint_id=20][u8 strlen=15]["This document s"]`), sent with
  flags `0x0008` (`FLAG_ON_CHANNEL` only — **not** `FLAG_HAS_SEQUENCE_NUMBER`
  `0x0040`), resent identically ~10x over ~10s, then the client abandons
  the whole BaseApp session and restarts LoginApp from scratch.
- **GOAL**: static disassembly only (no live test — per standing rule,
  none is justified without a confirmed hypothesis) to determine (1)
  whether `identifyVersionPoint`'s resend is transport-level (Mercury
  reliable-channel retry) or application-level, (2) the correct
  reply/ack mechanism if one is needed, (3) whether the reconnect-loop
  trigger is specific to this RPC or a generic watchdog.

### Finding 1 (CONFIRMED): the resend is NOT the transport-level Channel-ack retry — it must be application-level
`identifyVersionPoint`'s captured wire flags are `0x0008` (`FLAG_ON_CHANNEL`
only). The already-solved, live-verified reliable-channel ACK mechanism
(`GEMINI.md` §3, `Channel::checkResendTimers`/`Channel::handleAck`) is keyed
specifically on `FLAG_HAS_SEQUENCE_NUMBER` (`0x0040`) — packets without that
bit are not part of the sequenced/acked reliable stream at all, and indeed
this packet doesn't have it. **This packet's repeated resend cannot be the
generic Mercury transport-level unacked-packet retry** (that mechanism
requires a sequence number to track, which this packet doesn't carry) — it
must be driven by application-level logic in `ServerConnection`/BaseApp
client code that is itself waiting for something and re-issues the whole
call periodically until it gets it (or times out and reconnects).

### Finding 2 (NEW, STRONGLY SUPPORTED but not fully confirmed): a previously-unknown `versionPointIdentity` push message exists and echoes back the same body via the same descriptor
The earlier project string-table read (`06_trace/MERCURY_PACKET_MAP.md` §3)
stopped at `relativePositionReference` and reported nothing resembling a
version-check reply in what followed (only `avatarUpdate*` compression
variants). This pass found that the `ClientInterface` string blob
**continues for much longer than previously read** — after ~90
`avatarUpdate*` movement-compression variants, `setSpaceViewport`,
`setVehicle`, `stayPut`, `stayPutAlias`, `historyEventBegin/End`, it
resumes with:
```
controlEntity, voiceData, restoreClient, restoreBaseApp,
versionPointIdentity, versionPointSummary, resourceFragment,
resourceVersionStatus, loggedOff, shortEntityMessage, longEntityMessage
```
**`versionPointIdentity` and `versionPointSummary` are exactly the
server→client reply names for the client's `identifyVersionPoint` and
`summariseVersionPoint` calls** (and `resourceFragment`/
`resourceVersionStatus` similarly pair with `commenceResourceDownload`/
`resourceVersionTag`) — a clean 1:1 naming match this project had not
previously found because the string read was cut off too early.

Confirmed by disassembly (registration call site `0x80e57c`, same
`0x98b30c` registrar mechanism documented in `MERCURY_PACKET_MAP.md` §2a):
- **`versionPointIdentity`**: FIXED_LENGTH_MESSAGE, 8-byte body
  (`w2=0`, `w3=8`). Handler at `0x94bf48`.
- **`versionPointSummary`**: FIXED_LENGTH_MESSAGE, 34-byte (`0x22`) body.
  Handler at `0x94bf9c`.
- **`resourceFragment`**: VARIABLE_LENGTH_MESSAGE, `u16` length prefix
  (`w2=1`, `w3=2`). Handler at `0x9499a0`.
- **`resourceVersionStatus`**: FIXED_LENGTH_MESSAGE, 8-byte body. Handler
  at `0x9497f4` (this one WAS already disassembled incidentally earlier
  this pass while tracing an unrelated offset — it reads two `u32` fields
  and checks the first for `-1`/failure, logs via `0x1cada94`).

Disassembled the `versionPointIdentity` handler (`0x94bf48`) in full:
```
x19 = x1   ; pointer to the incoming 8-byte message body
x20 = x0   ; ServerConnection/Channel-ish "this"
x1  = [0x457b000 + 0xb50]     ; the SAME versionPointIdentity descriptor
                                 that was just registered for THIS handler
mov w2, #1
bl 0x981f7c(x0=x20, x1=descriptor, w2=1)   ; "start a new outgoing message"
                                              (same reserve/allocate-space
                                              family documented in E2E-019)
ldr x8,[x20]; w1=8; blr [x8+0x10]           ; reserve 8 bytes in the stream
ldr x8,[x19]; str x8,[x0]                    ; copy the 8 INCOMING bytes
                                                verbatim into the new
                                                OUTGOING message body
```
**This handler, when triggered, re-sends the identical 8-byte body back
out using the SAME `versionPointIdentity` descriptor** — a literal echo,
with no script/game-logic callback invoked (contrast with the sibling
`restoreClient` handler at `0x949614`/`0x949614+0x0` region, which DOES
parse its body into named fields and calls a real script hook via
`blr [vtable+0x88]` before conditionally re-forwarding). `versionPointSummary`'s
handler (`0x94bf9c`) is the same shape (echoes its 34-byte body verbatim).

**Interpretation, honestly labeled INFERRED, not CONFIRMED**: this echo
shape is consistent with either (a) `versionPointIdentity` being the real
reply this project needs to synthesize server-side (echoing back
something derived from the client's `identifyVersionPoint` body would
make the client's own handler for the ack loop terminate), or (b) this
being generic BigWorld relay/pass-through boilerplate for a
peer-forwarding scenario (e.g. CellApp hand-off) that is not meaningfully
exercised in the direct client-BaseApp path this project cares about. The
lack of a script callback (unlike `restoreClient`) makes (b) a real
possibility and this is NOT being reported as solved.

### Finding 3 (NOT achieved this pass): the exact numeric ClientInterface message ID for `versionPointIdentity`
Attempted to recover the numeric wire `msgID` by reading the registration
vector's push-back index (`0x98b30c` is confirmed, by its own disassembly,
to be a `std::vector<MethodDescription>::push_back`-shaped function that
assigns each method's numeric ID as its 0-indexed position in a
per-interface vector at registration time — `strb w27,[x8]` stores the
`(currentSize)` as the new entry's ID byte). However, cross-checking this
against the already-CONFIRMED `createBasePlayer` msgID (`5`, per
`GEMINI.md`/prior disassembly) against its own string-order position in
the same table (4th, 0-indexed, counting `bandwidthNotification`=0)
produced an unresolved off-by-one discrepancy this pass could not run
down in the available time (possibly an extra reserved slot 0 registered
before `bandwidthNotification` that isn't part of this string sequence).
**Did not derive a trustworthy numeric ID for `versionPointIdentity`** —
counting through ~90 intervening `avatarUpdate*` variants by hand is
mechanical but error-prone, and doing it on an unresolved off-by-one base
would just produce a confidently-wrong number. Not attempted further this
pass; flagged as the concrete blocker to a live test of Finding 2.

### Finding 4 (NOT achieved this pass): generic watchdog vs. RPC-specific timeout
Did not find or rule out a `ServerConnection`-level generic "no progress"
watchdog independent of `identifyVersionPoint` specifically. Time this
pass went to Findings 1-3 instead. Genuinely open.

### RESULT
- **Real, new, previously-undocumented structural finding**: the
  `ClientInterface` push-message table extends well past the previous
  read cutoff and contains `versionPointIdentity`/`versionPointSummary`/
  `resourceFragment`/`resourceVersionStatus` — exact name-paired replies
  for the four version-check `BaseAppExtInterface` methods. This directly
  answers the coordinator's question "was a further string-table read
  needed" — **yes, and it found exactly the missing reply names.**
- **Not yet actionable for a live test**: the handler's echo behavior is a
  plausible but unconfirmed mechanism (no script callback observed, unlike
  a known-real handler), and the numeric wire `msgID` needed to actually
  construct a wire-correct reply was not recovered this pass (off-by-one
  ambiguity in the ID-counting scheme, not resolved). Sending a reply with
  a guessed/wrong msgID would be indistinguishable from "wrong hypothesis"
  and could burn a live-test cycle on the shared emulator for no
  information gain — per standing instruction, not attempted.
  `CLIENT_MODIFIED: NO`. No server files were changed this pass.

### NEXT_ACTION
1. Resolve the msgID off-by-one: find the ACTUAL numeric ID assignment
   mechanism with certainty — either by carefully hand-counting all
   `ClientInterface` string-table entries from `bandwidthNotification`
   through `versionPointIdentity` (tedious but mechanical, ~90+ entries
   dominated by `avatarUpdate*` variants), or by finding the CALLER-side
   code that dispatches an incoming `0x94bf48`-shaped message and reading
   the msgID it's keyed on directly from a jump/switch table instead of
   from registration order.
2. Once the ID is known, construct a live test: server sends a
   `versionPointIdentity`-framed push (msgID=<found>, FIXED 8-byte body)
   containing SOME plausible 8-byte payload derived from the client's own
   `identifyVersionPoint` call (e.g. the `checkpoint_id` echoed in the
   first 2 bytes, remaining 6 bytes zero, as the simplest first guess) and
   observe whether the resend loop stops.
3. If Finding 2's echo hypothesis is wrong (resend continues unchanged),
   fall back to Finding 4: look for a generic `ServerConnection`-level
   watchdog/keep-alive requirement (e.g. periodic `setGameTime` push, or a
   "meaningful progress" timer) independent of `identifyVersionPoint`
   specifically, since flags `0x0008` with no sequence number suggests the
   Mercury layer itself considers this an unreliable, best-effort call —
   meaning the client's own reconnect trigger may not even be reading this
   RPC's completion at all.

---

## TEST_ID: E2E-022
- **DATE**: 2026-09-16, continuation pass, per the coordinator's explicit
  instruction to resolve `versionPointIdentity`'s numeric msgID
  programmatically (walking every `bl 0x98b30c` registration call site in
  order, resolving each string argument via ADRP+ADD, the same technique
  already used elsewhere in this project) rather than hand-counting ~90
  `avatarUpdate*` strings.

### Method
Wrote `scratch/dump_clientinterface_registration_order.py`: a symbolic
single-pass walker over the whole interface-registration block
(`0x80c600`-`0x80e800`) that tracks every X-register's most-recently-known
ADRP+ADD-resolved string address (with MOV-copy propagation, invalidating
on any other write to a register — needed because a naive "track only x1"
first attempt produced stale/duplicate entries, e.g. `baseAppLogin`
appearing twice, from the compiler's loop-interleaved pre-computation of
later iterations' string pointers into callee-saved registers ahead of
time). It also tracks `bl 0x98b294` calls (found to be a separate,
3-times-called `Interface::Interface(this, name)` placement-constructor —
`LoginInterface`/`BaseAppExtInterface`/`ClientInterface`) as per-interface
epoch boundaries, since `0x98b30c` (confirmed by its own disassembly to be
a `std::vector<MethodDescription>::push_back`) assigns each entry's
numeric ID as ITS OWN interface object's vector size at push time — IDs
reset to 0 per interface, not globally.

All 122 `bl 0x98b30c` call sites resolved with **zero unresolved
entries** — full output in `scratch/clientinterface_registration_order.txt`.

### Result: CONFIRMED BY BINARY, and it explains the E2E-021 off-by-one
- `BaseAppExtInterface`: `baseAppLogin=0` through `entityMessage=17`
  (18 methods) — matches the already-published `MERCURY_PACKET_MAP.md`
  §2a table exactly, including **`identifyVersionPoint=12`**, matching
  the coordinator's own cited value.
- `ClientInterface`: **102 methods (0-101)**. The bare `"ClientInterface"`
  string is NOT itself registered via `0x98b30c` — it's the `Interface`
  constructor's own name argument (a different function, `0x98b294`).
  Immediately after construction, `ClientInterface`'s own msgID 0 is
  **`authenticate`** (a second, independent registration of the same
  interned rodata string `BaseAppExtInterface` also uses at its own
  msgID 1) — **not** `bandwidthNotification` as this project's own prior
  `MERCURY_PACKET_MAP.md` §2b had it (that section's `createBasePlayer=4`
  was off by exactly one because of this missed `authenticate` entry).
  Corrected order: `authenticate=0, bandwidthNotification=1,
  updateFrequencyNotification=2, setGameTime=3, resetEntities=4,
  createBasePlayer=5, createCellPlayer=6, spaceData=7, spaceViewportInfo=8,
  createEntity=9 (not previously listed), updateEntity=10, enterAoI=11,
  ...`. **`createBasePlayer=5` exactly matches the value already
  live-verified and in production use in `mitm/local_baseapp_capture.py`
  via a completely independent method** (direct disassembly of
  `0x947dc4`/`0x918504`, per `GEMINI.md`) — two independent techniques
  landing on the same number is strong cross-validation that this
  registration-order walk is trustworthy, not just self-consistent.
- Continuing the count through all ~90 intervening `avatarUpdate*`/
  positional-compression variants (dominant bulk of the interface):
  `controlEntity=90, voiceData=91, restoreClient=92, restoreBaseApp=93`,
  and — the actual target of this pass — **`versionPointIdentity=94`**,
  `versionPointSummary=95`, `resourceFragment=96`, `resourceVersionStatus=97`,
  then `resourceVersionTag=98` (a second registration of
  `BaseAppExtInterface`'s own interned string, same pattern as
  `authenticate`), `loggedOff=99`, `shortEntityMessage=100`,
  `longEntityMessage=101`.

Updated `06_trace/MERCURY_PACKET_MAP.md` §2b with the corrected,
CONFIRMED BY BINARY table (both the `createBasePlayer` fix and the new
`versionPointIdentity=94` entry), replacing the old STRONGLY-SUPPORTED/
off-by-one version.

### RESULT
- **`versionPointIdentity`'s numeric ClientInterface msgID is CONFIRMED:
  94.** Combined with E2E-021's disassembly of its handler (`0x94bf48`,
  FIXED_LENGTH 8-byte body, echoes the incoming 8 bytes back out via the
  same descriptor), this is now a fully wire-specifiable candidate reply:
  `[flags][msgID=94][8-byte body]` (framing per the standard
  FIXED_LENGTH_MESSAGE shape already confirmed for `createBasePlayer` and
  other ClientInterface pushes), whole-packet Blowfish `pc_variant`
  encrypted with IV=0 and wastage-byte padding (per E2E-020's confirmed
  BaseApp channel crypto model).
- `CLIENT_MODIFIED: NO`. No server files changed yet this pass — the
  live test itself (per the coordinator's own instruction) is the next
  step, gated on checking current emulator/process activity first since a
  concurrent session may still be using it.

### NEXT_ACTION
1. Check current device/process state (per standing caution about the
   concurrent session) before touching the emulator.
2. If idle/safe: implement and live-test a `versionPointIdentity` push
   (msgID 94, FIXED 8-byte body, first-guess payload = the client's own
   `checkpoint_id` `0x0014` echoed in the first 2 bytes, remaining 6 bytes
   zero) in `mitm/local_baseapp_capture.py`'s BaseApp UDP responder, sent
   immediately upon receiving `identifyVersionPoint`. Observe whether the
   resend loop stops.
3. If the resend continues despite a msgID-correct, framing-correct reply,
   this cleanly falls back to the generic-watchdog hypothesis (E2E-021
   item 4) rather than further guessing at this RPC's exact reply
   semantics.

---

## TEST_ID: E2E-023
- **DATE**: 2026-09-16, continuation pass. **Live test executed by the
  coordinator** (this session was blocked from restarting the local
  server process itself by Claude Code's own auto-mode safety classifier,
  `[Interfere With Workloads]` — a genuine tooling permission block, not a
  technical one; the coordinator restarted PID 2004 -> PID 1420 with
  commits `44b9099`/`9132c23` live and ran the test for 90+ seconds).

### Result 1 (CONFIRMED LIVE): the keep-alive fix WORKS
Zero new LoginApp reconnect cycles and zero `INACTIVITY`-related logcat
lines over a full 90+ second window — well past the previously-fatal
~10s mark. This **confirms** the parallel session's
`06_notes/LOBBY_ENTRY_TRACE.md` Task A hypothesis (generic
`ServerConnection`/`Channel` `InactivityTimeout` watchdog, independent of
any specific RPC) as the real, now-fixed cause of the reconnect loop.
The `setGameTime` periodic push (ClientInterface msgID 3, every 5s) is
the durable fix for BaseApp session longevity going forward.

### Result 2 (the echo-content hypothesis is DISPROVEN): `identifyVersionPoint` keeps resending regardless of our reply
With the reconnect no longer masking it, the client is now visibly
resending `identifyVersionPoint` (identical bytes, `checkpoint_id=20`,
`"This document s..."`) every ~1s continuously, even though our
`versionPointIdentity` (msgID 94) reply is sent back immediately every
single time. No new client-side logcat line names this specifically
(checked `version|resource|checkpoint|inactivity|reconnect|logon`);
title-screen UI shows no visible transition either way.

Per the coordinator's specific question, re-disassembled `0x94bf48`
(the `versionPointIdentity` handler) in FULL — all 19 instructions,
function entry to `ret`:
```
0x94bf48: stp x20, x19, [sp, #-0x20]!
0x94bf4c: stp x29, x30, [sp, #0x10]
0x94bf50: add x29, sp, #0x10
0x94bf54: adrp x8, #0x457b000
0x94bf58: mov x19, x1          ; x19 = incoming 8-byte body pointer
0x94bf5c: ldr x1, [x8, #0xb50] ; x1 = versionPointIdentity's own descriptor
0x94bf60: mov w2, #1
0x94bf64: mov x20, x0          ; x20 = outgoing-bundle context
0x94bf68: bl #0x981f7c         ; start a new outgoing message
0x94bf6c: ldr x8, [x20]
0x94bf70: mov w1, #8
0x94bf74: mov x0, x20
0x94bf78: ldr x8, [x8, #0x10]
0x94bf7c: blr x8               ; reserve 8 bytes in the stream
0x94bf80: ldr x8, [x19]        ; read incoming 8 bytes
0x94bf84: str x8, [x0]         ; copy verbatim, unconditionally
0x94bf88: ldp x29, x30, [sp, #0x10]
0x94bf8c: mov x0, x20
0x94bf90: ldp x20, x19, [sp], #0x20
0x94bf94: ret
```
**There is not a single comparison, branch, or conditional instruction
anywhere in this function.** It unconditionally builds a new outgoing
message and copies the 8 bytes verbatim, with zero validation against
anything — no comparison to a stored value, no hash check, no
status/version gate. **This definitively answers the coordinator's
question: the handler does NOT validate/compare the returned bytes.**

**Consequence**: the "wrong content in our reply" theory is now
disproven by exhaustive disassembly — there is nothing in this handler
for content to be "right" or "wrong" about; any 8 bytes would be treated
identically. This means either (a) `identifyVersionPoint`'s resend is
NOT gated on receiving this specific reply at all (it could be a
periodic/independent call, or gated on something else entirely — e.g.
`enableEntities` or a different trigger, as the coordinator suggested),
or (b) our reply is not actually reaching `0x94bf48` at all — accepted at
the decrypt/socket layer (no error logged) but mis-dispatched or dropped
somewhere between decrypt and the ClientInterface handler table.

### New hypothesis (untested as of this entry): wrong wire FLAGS, not wrong content
Re-examined the flags used: our `versionPointIdentity` reply (like the
earlier, pre-channel `createBasePlayer` push) used flags `0x0001` — the
same generic flag used before the reliable channel existed. But
`identifyVersionPoint` ITSELF, sent by the client on the NOW-established
reliable channel, uses flags `0x0008` (`FLAG_ON_CHANNEL`, no sequence
number, no requests flag) — this appears to be the client's own
convention for "on this established channel, but not part of the
strictly ordered/acked stream" traffic at this stage. Our already-working
channel ACK reply also sets `FLAG_ON_CHANNEL` (as part of `0x000c`).
**Hypothesis, not yet tested**: post-channel-establishment application
pushes (this reply, and the `setGameTime` keep-alive) may need
`FLAG_ON_CHANNEL` (`0x0008`) rather than the pre-channel generic `0x0001`
to be correctly attributed/routed by the client's own receiving Nub —
possible root cause of (b) above (silent mis-dispatch, not silent
content-rejection). Note the keep-alive itself is confirmed WORKING with
flags `0x0001` (Result 1 above), so this is specifically a question about
the `versionPointIdentity` reply's flags, not a blanket claim that
`0x0001` is always wrong.

### Implementation this pass
Changed `mitm/local_baseapp_capture.py`'s `versionPointIdentity` reply to
use flags `0x0008` by default (overridable via a new `BASEAPP_REPLY_FLAGS`
env var for fast A/B testing without a code change), leaving the
already-confirmed-working `setGameTime` keep-alive's flags (`0x0001`)
untouched. Compiles clean. **Not yet live-tested** — this session remains
blocked from restarting the server process itself (same classifier
block as before); the coordinator or user needs to restart the process
to pick up this change.

### RESULT
- **CONFIRMED**: keep-alive (generic watchdog) fix works, live-verified
  90+ seconds.
- **DISPROVEN**: `versionPointIdentity`'s 8-byte content is validated by
  the client in any way — `0x94bf48` has no validation logic at all.
- **NEW, untested hypothesis**: wire flags (`0x0008` vs `0x0001`) may be
  the actual issue, not content. Code change ready, gated behind
  `BASEAPP_REPLY_FLAGS` for instant rollback/comparison.
- `CLIENT_MODIFIED: NO`. Server-side only.

### NEXT_ACTION
1. Restart the server process (blocked for this session; needs the
   coordinator/user) and re-test with the new `flags=0x0008` default.
   Watch specifically for whether `identifyVersionPoint`'s resend
   frequency/pattern changes at all (even a change in TIMING, not just a
   full stop, would be informative — e.g. if flags matter for routing,
   a wrong-flags reply might currently be silently dropped with zero
   effect, while a correctly-routed one might still not stop the resend
   for a different reason, but should at least be visibly received/counted
   somewhere if any per-message stats exist).
2. If flags `0x0008` also makes no observable difference, escalate to
   testing whether `identifyVersionPoint` is answered/gated by something
   else entirely (per the coordinator's own suggested pivot): check
   `enableEntities` (BaseAppExtInterface msgID 8) or other pending
   application-level triggers independent of the version-check RPC pair.
3. Consider instrumenting the reply differently to positively detect
   whether it's being received at all: e.g., temporarily send a
   deliberately-wrong-msgID or deliberately-malformed variant and compare
   client behavior/logcat against the "correct" variant, to distinguish
   "silently dropped for a reason we understand" from "reaches the
   handler but has no observable effect" (the latter being exactly what
   `0x94bf48`'s pure echo-with-no-validation behavior would produce even
   when everything is "correct").

---

## TEST_ID: E2E-024
- **DATE**: 2026-09-16, parallel pass (run alongside the coordinator's own
  live flags=0x0008 test) per the coordinator's explicit instruction:
  investigate `enableEntities` (BaseAppExtInterface msgID 8) via pure
  disassembly + existing capture-log reading only — no server code/process
  touched, since the coordinator was using the live server concurrently.

### Finding 1 (CONFIRMED from the existing capture log): `enableEntities` was already called, bundled with `identifyVersionPoint`, as the client's reliable-channel packet #0 — and it STOPPED resending once our existing channel-ACK fix took effect
Grepped `mitm/captures/BASEAPP_LOGIN_CAPTURE.txt` (8,136 `DECRYPTED` lines)
for decrypted packets whose byte `[2]` (the first message's `msgID`) is
`0x08`. Found exactly **one** distinct byte pattern, repeated 698 times
across many reconnect cycles:
```
58 00 08 61 b2 00 00 61 b2 00 00 0c 09 00 14 00 06 54 68 69 73 20 64 00 00 00 00
```
Decoded: outer flags `0x0058` (`FLAG_ON_CHANNEL|FLAG_IS_RELIABLE|
FLAG_HAS_SEQUENCE_NUMBER` — this IS reliable-channel packet #0, the same
one this project's existing `ATTEMPT_CHANNEL_ACK` responder already acks).
It's a **Mercury bundle containing TWO messages back to back**:
- msg1: `msgID=0x08` (`enableEntities`), FIXED 8-byte body = two `u32`
  fields, both `0x0000b261`.
- msg2: `msgID=0x0c` (`identifyVersionPoint`), VARIABLE body, length=9
  (`checkpoint_id=20, strlen=6, "This d"` — a SHORTER placeholder string
  than the later standalone resends' full `"This document s"`, confirming
  this is a distinct, earlier, one-time occurrence, not the same object as
  the later repeats).

**The last occurrence of this exact packet in the whole capture log is
timestamped 12:20:02** — it never appears again in the rest of the file
(which continues for many more reconnect cycles afterward, including
fresh LoginApp activity as recently as 12:28:41, i.e. during/around the
coordinator's live testing). This strongly indicates: **`enableEntities`
was successfully delivered and acknowledged by this project's EXISTING
reliable-channel ACK responder (`ATTEMPT_CHANNEL_ACK`, live-confirmed
working per the coordinator's own E2E-023 test) — it required no
separate, `enableEntities`-specific application-level reply. The generic
transport-level channel ACK for packet #0 was sufficient to satisfy it.**
This is genuinely good news: `enableEntities` does not appear to be an
open blocker at all.

By contrast, `identifyVersionPoint`'s STANDALONE resends (`msgID=0x0c`
alone, unbundled, flags `0x0008` only — NOT part of the reliable/acked
stream) continue indefinitely at ~1s intervals throughout the whole
capture, with byte-identical content every time. This is a real,
structural difference from `enableEntities`'s behavior and supports
E2E-023's hypothesis (a): these standalone resends are very plausibly a
periodic, application-level re-announcement that is **not gated on
receiving any reply at all** — i.e. possibly not a "blocker" needing a
fix in the traditional sense, but simply how this RPC behaves
indefinitely by design (a lightweight version-check heartbeat), in which
case the real remaining gate to Account/Avatar/Lobby lies elsewhere.

### Finding 2 (CONFIRMED by disassembly): what triggers the client to call `enableEntities`
Found `enableEntities`'s outgoing-call descriptor storage offset
(`0x457a000+0x260`, from its `0x98b30c` registration at `0x80c858`) and
located all 4 `adrp+ldr` cross-references to that offset:
- **`0x93d534`**: reads a field at `object+0xe88` (and conditionally
  `object+0xe8c` if a flag bit is set), builds `enableEntities`'s 8-byte
  body from those one or two `u32` values, sends it via the channel object
  at `object+0x150`, then sets a flag byte at `object+0x15a`. This looks
  like the initial, one-time "entities are ready to be enabled" call —
  its context (a short, self-contained function, no cleanup loop) is
  consistent with being the FIRST send, matching the packet-#0 bundle
  observed in Finding 1.
- **`0x947d64`**: after a loop that iterates and `operator delete`s
  entries from a vector at `object+0xea8`/`object+0xeb0` (looks like
  clearing a pending-entity or pending-message list), unconditionally
  re-sends `enableEntities` with body `[w21,w21]` (both fields = the SAME
  `object+0xe88` counter). Looks like a "re-announce after a reset/clear"
  path.
- **`0x94df74`**: after a refcount-release check (`ldaxr`/`stlxr` atomic
  decrement — thread-safe refcounting), conditionally (`w21==1`) re-sends
  `enableEntities`, again using `object+0xe88` for both body fields.
- **`0x94a17c`**: a DIFFERENT shape entirely — no `object+0xe88` field
  read, instead it's a receive-handler-shaped function (`bl 0x981f7c`
  start-message, reserve 8 bytes, copy verbatim from an incoming 8-byte
  body) — the SAME boilerplate echo-relay pattern already found for
  `versionPointIdentity`'s handler (`0x94bf48`). This is very likely
  `ClientInterface`'s own separately-registered `enableEntities` entry
  (the same dual-registration pattern already confirmed for
  `authenticate`/`resourceVersionTag` in E2E-022) — i.e. a server-to-client
  push variant that, if the server ever sends `enableEntities` back to the
  client, gets echoed the same inert way. Not exercised in this project's
  own traffic (we've never sent an `enableEntities` push), so not further
  investigated.

**Conclusion**: `enableEntities` is called automatically by internal
client-side state transitions (channel setup completing; a pending list
being cleared; a refcount reaching a threshold) — **not gated on any
server response**, and its body content is drawn from the client's own
internal entity/counter bookkeeping (`object+0xe88`), not something the
server needs to supply or negotiate. Combined with Finding 1's empirical
evidence that it stopped resending once transport-acked, this is
consistent with `enableEntities` being a simple "I'm ready, here's my
current count" fire-and-forget notification requiring only reliable
delivery (already solved), not a distinct request/reply RPC.

### RESULT
- **`enableEntities` is very likely NOT an open blocker** — it was
  delivered exactly once (bundled with the client's first
  `identifyVersionPoint`) and successfully acked by the already-existing,
  already-confirmed-working channel-ACK responder; no distinct
  application-level reply appears to be needed.
- **The standalone `identifyVersionPoint` resends remain the only
  concretely-observed open item**, and new evidence in this pass further
  supports (without proving) that they may not be reply-gated at all —
  possibly normal, harmless periodic client behavior rather than a
  blocker, meaning the true remaining gate to Account/Avatar/Lobby may
  lie elsewhere (e.g. `Account::handshake`, per
  `06_notes/LOBBY_ENTRY_TRACE.md`'s own next-blocker prediction).
- `CLIENT_MODIFIED: NO`. No server files or live process touched this
  pass — pure static disassembly and existing-log analysis, per the
  coordinator's explicit scope for this parallel investigation.

### NEXT_ACTION
1. Once the coordinator's flags=0x0008 live test result is in, re-check
   the capture log the same way (grep for msgID patterns) to see whether
   `enableEntities` reappears (it shouldn't, if a fresh reconnect cycle
   re-sends packet #0 and gets acked again the same way) and whether
   `identifyVersionPoint`'s standalone resends changed behavior at all.
2. If `identifyVersionPoint`'s resends turn out to be harmless/expected
   background behavior (not a blocker), pivot investigation to
   `Account::handshake` (the next predicted real blocker per
   `06_notes/LOBBY_ENTRY_TRACE.md` Task B) — check whether the client
   ever attempts to call it, and if not, what server-side push (e.g.
   `onChannelLogin`) might need to happen first to prompt it.

---
*Last updated: 2026-09-16. Do not overwrite prior entries — append new
TEST_ID blocks only.*

