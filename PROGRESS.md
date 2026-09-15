# PROGRESS.md — ROS_RE Reverse Engineering Project Status

## Current Milestone Chain
The following gates must pass in order. Don't chase a later gate while an earlier one is unverified.

| Gate | Passes when |
|------|-------------|
| **G1 Login** | `loginapp` log shows an accepted login. |
| **G2 BaseApp** | `baseapp` receives a real accepted session (not just keepalive). |
| **G3 Role list** | Client shows the correct character/role list (matches reference). |
| **G4 Enter hall** | The real hall loads (not the fallback create screen). |
| **G5 Character** | Character preview matches the ORIGINAL model/appearance. |
| **G6 Battle** | Battle loads and plays like the original. |

## Gate 0 — PATCH CHECK ✅ CLEARED (live-verified 2026-09-13)
- **Proof**: fresh boot PID 4053 — `GET /pl/npk_version_na_android.plist` → served 482-byte T15 plist (`SERVE_B.txt:6926-6927`); zero `Traceback`/`force Patch!` in fresh logcat; client advanced to `requestServerList` + `channelLogin` keypoints reporting `"patch_version": "1.0.0.en"` (`SERVE_B.txt:6957,6959`); plist download telemetry confirms fetch (`SERVE_B.txt:6962-6972`)
- **Clearing input**: planted `<absDocRoot>/patchVersion` = `1.0.0.en` (matches live `settingLanguage: en`); file survives reboot (cleanPatch does not delete on normal boot); `getPatchLanguage()` → `'en'` → `need_language_patch=False` → `forcePatch` stays False → L659 clean finish
- **Doc-root correction**: `absDocRoot` = `/sdcard/Android/data/com.netease.chiji/files/netease/h45na/` (proven by resident client-written files + VersionRecord), NOT `/data/data/.../files/` (T17a's engine-derived guess was wrong on location, right on filename/format/writer)
- **Screenshot**: PENDING; **Parity**: UNDECIDABLE (reference/original/ empty)

## Gate 1 — AUTH / TEST SESSION ✅ CLEARED (live-verified 2026-09-13)
- **Proof**: `/api/users/login/v2/sdk_token` contract verified with top-level `user_id` and `sdk_token` per Dalvik parser `com.netease.mpay.oversea.h.a.a:a` (`0x3d34bc`). Live exchange confirmed on `emulator-5554` with zero `onFailure(1000)` / "Cancel login" events.
- **Contract**: Documented in `06_notes/LOCAL_SESSION_CONTRACT.md`.

## Milestone Chain (project gates G1–G6) — current frontier: G2 GAME SESSION (loginapp / BaseApp)
- G1 Login: PASS
- G2 BaseApp: INVESTIGATION (`10.0.2.2:25000` mapped to `neox::bwclient::ServerConnection` in `libclient.so`)
- G3 Role list / G4 Hall / G5 Character / G6 Battle — not yet attempted

## Recent Task Completion
| Task | Status | Finding |
|------|--------|---------|
| **T13** | COMPLETE | G4 parser schema: `##########` separator + JSON tail. Minimal payload `##########\n{}` (13 bytes) eliminates error 41006 |
| **T14** | COMPLETE | `KeyError: 'type'` root cause: missing `"type": "package"` key in JSON tail. Also: `"version"` must be STRING, not int. |
| **T15** | NARROW-VERIFIED | `patch/ResourcePatcher.py:1285,1299,1308-1324` — string `file_list` + `_updated/_size/_md5` tail keys resolve ZeroDivision/TypeError/missing-key crashes. Live-verified: no traceback, boot reaches `properties.init()`. |
| **T16** | STATIC-PASS (live of clearing input pending) | `bridge/RESULT_T16.md` — force-Patch driver mapped: `patchVersion` file absent → `patch_utils.py:18` None → `patch_mgr.py:611` True → `patch_mgr.py:446` `forcePatch=True` → `patch_mgr.py:665` print + `CANCEL_STAGE`. Chain matches live log (`patch_language: None`, `need patch for language!`, `force Patch!`). One citation slip: §1 step 4 says `patch/patch_size_calc.py`, should be `patch/ResourcePatcher.py`. |
| **T17a** | STATIC-PASS (one location correction) | `bridge/RESULT_T17a.md` — sole writer `BaseStage.beforePatchFinish` (`patch_mgr.py:160-162`), format L447 `1.<engine>.<client>.<lang>`, cancel path writes too (L667), deleter `BirthStage.cleanPatch`. CORRECTION: `absDocRoot` = `/sdcard/Android/data/com.netease.chiji/files/netease/h45na/` (live-proven), not `/data/data/.../files/`. No `patchVersion`/`firstPackVersion` found device-wide → cancel-path write never lands there. |
| **T18** | COMPLETE | Server list schema: space-delimited single-line format serving North_America endpoint `10.0.2.2:25000`. Keypoint `requestServerList` success. |
| **G1 Auth Trace** | COMPLETE | Complete trace of `onFailure(1000)`: `ui/g$2` at `0x3ffc2a` emits code 1000 ("Cancel login"). Bridge `SdkNeteaseGlobal$LoginCallback` at `0x43886c` logs `step="loginDone"`. `login/v2/sdk_token` parser at `0x3d34bc` expects top-level `user_id` and `sdk_token`. Full trace documented in `06_notes/LOGIN_FLOW_TRACE.md`. |
| **Gate 1** | PASS | Local test session contract verified and live-exchanged without `onFailure(1000)`. Documented in `06_notes/LOCAL_SESSION_CONTRACT.md`. |
| **Gate 2** | INVESTIGATION | Connection dependency `10.0.2.2:25000` mapped to `neox::bwclient::ServerConnection` in `libclient.so`. Mercury protocol handshake trace documented in `06_notes/G2_GAME_SESSION_TRACE.md`. |

## Next Steps
1. Extract `entities/loginapp.pubkey` or RSA keys from assets / `libclient.so`.
2. Construct minimal BigWorld Mercury handshake receiver on port 25000 (`loginapp`).
3. Handle `ServerConnection::logOnBegin` Mercury bundle and reply with `LoginReplyRecord`.
4. **[NEW 2026-09-15]** Live `/proc/<pid>/mem` read of the Mercury `Nub`'s
   reply-tracking hashtable (`Nub+0x88` bucket array / `Nub+0x90` count) at
   the moment `logOnBegin` sends each request, to find the client's REAL
   reply-ID correlation key — two fresh live runs this pass (first time a
   device was reachable for regression testing) both showed the existing
   Attempt H responder (`mitm/local_baseapp_capture.py`, echoing request
   wire offset `[5:7]`) failing 10/10 retries with `"Couldn't find handler
   for reply id"`, contradicting the previously-recorded "CONFIRMED LIVE,
   reproduced twice" status. See `07_ros_legacy_approach/END_TO_END_TEST_LOG.md`
   TEST_ID E2E-001 for full evidence. This is now a MORE PRECISE blocker
   than the already-known Blowfish-key issue, since the client no longer
   reaches `onLoginReply` at all on a clean run.

## 2026-09-15 Live Regression Pass (device reachable for the first time)
- **Phase 1 (session/auth) — RECONFIRMED PASS, live, for the first time**:
  `emulator-5554` reachable, existing iptables OUTPUT DNAT rules intact,
  `mitm_serve.py`/`session_store.py` (commit `bbccdd3`) minted 3 distinct
  `sess_<uuid4hex>` sessions during a real client PLAY-button tap; client
  screenshot confirms Guest-logged-in title screen. Closes the
  `PRIVATE_SERVER_ADAPTATION_PLAN.md` Phase-1 scorecard rows previously
  marked "NOT VERIFIED THIS PASS — no device available".
- **Phases 2-3 (server list -> LoginApp reachability) — RECONFIRMED PASS,
  live**: client's 273-byte RSA-OAEP `LogOnParams` bundles do arrive at
  `local_baseapp_capture.py`'s UDP :25000 responder, matching
  `LOGONPARAMS_SERIALIZATION.md`'s established wire layout exactly.
- **Phase 4/5 boundary (reply-ID correlation) — REGRESSION found, see
  Next Steps item 4 above and `END_TO_END_TEST_LOG.md` E2E-001.**
- **Phase 5 (Blowfish key) — NOT reached this pass**: the client did not
  get past reply-ID correlation in either fresh run, so the already-known
  Blowfish blocker (`06_notes/FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md`) could
  not be re-examined live this pass; it remains exactly as previously
  documented (CONFIRMED UNRESOLVED), just temporarily unreachable behind
  the new, more precise reply-ID blocker.

## 2026-09-15 Follow-on Pass — Reply-ID Blocker: Memory Read BLOCKED, Sticky-Counter Hypothesis DISPROVEN
- **Live `/proc/<pid>/mem` read attempt (the task's own recommended
  immediate next step) is environmentally BLOCKED this pass**, reproduced
  three independent ways against the live client (PID 22345,
  `emulator-5554`): (1) `su 0 dd if=/proc/<pid>/mem ...` at the live `Nub`
  address returns `I/O error` even ~120ms after capture; (2) `su 0 strace
  -p <pid>` → `ptrace(PTRACE_SEIZE,...): Operation not permitted` despite
  genuine `uid=0` root; (3) `frida-server-16` (the project's own,
  previously-working binary) crashes on `enumerate_processes()`/`attach()`
  with a ptrace error. SELinux is Permissive, no Yama LSM is loaded, target
  has `Seccomp: 0`/`TracerPid: 0` — none of the normal, checkable
  ptrace-restriction mechanisms explain this. Full detail:
  `07_ros_legacy_approach/END_TO_END_TEST_LOG.md` TEST_ID E2E-002 Sub-test A.
  This contradicts this project's own prior claimed live-memory-read
  successes (`06_trace/MERCURY_MESSAGE_ID_TRACE.md`) from earlier the same
  nominal day — treated as a genuine, reported environmental regression,
  not silently worked around.
- **`ATTEMPT_J` sticky-first-counter hypothesis DISPROVEN, live, 10/10**:
  echoing retry #1's counter value for all 10 retries (rather than each
  retry's own incrementing counter) still fails every single time,
  including for the reply matching retry #1 itself. This closes out the
  cheapest remaining wire-level guess and further undermines the standing
  belief (since `MERCURY_REPLY_ID_TRACE.md`) that request wire offset
  `[5:7]` is the client's real internal reply-id key at all. See E2E-002
  Sub-test B.
- **NEXT_ACTION (updated, supersedes the "live /proc/pid/mem read" item
  above since it is now blocked, not merely pending)**: per the task's own
  standing authorization to pivot to a ROS-Legacy-style client-observable
  replacement when native RE is slow/ambiguous/blocked, the recommended
  next experiment is a `script.npk` (Python) shortcut at
  `ui.UILogin.doLoginGame()` to drive the client directly into its
  post-login UI state via the client's own real subsequent-stage
  entrypoints, bypassing the now-twice-blocked native Mercury reply-id
  problem rather than continuing to guess at it with no working
  introspection tool. This must be labeled `CLIENT_MODIFIED: YES` /
  `APPROACH_TAKEN: ros-legacy-style-replacement`, never presented as the
  faithful protocol working. Not yet started.

## 2026-09-15 Third Pass — User authorized full client-patch bypass; frida-gadget partially works, script.npk crypto confirmed blocked, OBB incident recovered
- **User decision (explicit, logged)**: "ibypass na natin lahat para
  makapaglaro na offline" — bypass everything necessary to make the game
  playable offline. This formally authorizes `CLIENT_MODIFIED: YES` work
  (Java/smali/Python/native), per the standing risk-ordered preference
  (Java/smali/Python before native `.so` patches).
- **script.npk Python patch plan (the originally recommended next step)
  is BLOCKED on a crypto/tooling prerequisite**, not abandoned: the general
  `script.npk` entry cipher (magic `7A 1C`, ~3,957 of 3,959 entries,
  including `ui/UILogin.py`) is a stream cipher whose keystream generator
  lives only inside the compiled Python runtime — already recorded as
  BLOCKED for static extraction in `bridge/RESULT_T11.md` sec3 (pre-existing
  finding, re-confirmed this pass after an AES-128-ECB attempt failed — that
  key only covers a small, unrelated 2-entry sub-container, not the general
  case). Dynamic (Frida) extraction is the documented way around this, but:
  `frida-server` (external, ptrace-based) crashes on attach to this specific
  process; `frida-gadget` (in-process) loads and runs but the project's
  existing pre-built config hangs early process init on a stale HTTP-fetch
  URL. Full detail: `07_ros_legacy_approach/END_TO_END_TEST_LOG.md` E2E-003.
- **New environmental finding**: a full `adb reboot` of the emulator
  restores ptrace-ATTACH capability (confirmed via `strace -p`) that was
  broken in the prior pass (E2E-002), but does NOT restore unattached
  `/proc/pid/mem` reads (still EIO) — these are separate kernel gates.
- **Incident, fully recovered**: `adb uninstall com.netease.chiji` deletes
  this app's OBB expansion files too (not just app data) on this
  LDPlayer/Android config — new operational knowledge. Both OBB files were
  restored from this repo's own `04_obb/` via `adb push` (~3.5GB total,
  ~2.5 min), and the device was confirmed back to a clean working title
  screen. No permanent data loss; the pre-pass-working APK
  (`scratch/currently_installed_backup.apk`) is reinstalled and running.
- **NEXT_ACTION (highest priority)**: fix `tools/frida-gadget.config` to
  use the standard `{"type":"listen"}` interaction (no network dependency)
  instead of the stale custom HTTP-fetch config, rebuild/reinstall the
  gadget-injected APK from the CURRENT working base (not the stale Sep-14
  `base_frida_signed.apk`), and use it to either (a) dump the real
  LoginApp reply-id key live — potentially resolving the ORIGINAL native
  protocol blocker with no further client patch needed, which would be
  the smallest, most faithful fix — or (b) dump `ui.UILogin`'s decrypted
  bytecode for an informed `doLoginGame()` Python patch. Native `.so`
  patch (two small, already-disassembly-located targets:
  `Mercury::Nub::handleMessage`'s match branch,
  `EncryptionFilter::decrypt`'s call site) remains the documented fallback
  if gadget-based introspection does not pan out in a further timeboxed
  attempt.

## 2026-09-15 Fourth Pass — Scope correction (no native .so patching), frida-gadget config fixed but hits native-bridge wall, script.npk cipher structurally advanced but not broken
- **User scope correction (logged verbatim)**: native `.so` binary
  patching is permanently WITHDRAWN from this project's authorized
  options — blocked by the orchestrating session's own security
  classifier. The `Mercury::Nub::handleMessage`/`EncryptionFilter::decrypt`
  patch idea from the prior pass is retracted and must not be proposed
  again. All further work toward "bypass everything, reach Lobby" must be
  script.npk (Python) level only, ROS-Legacy-Gate-1-style.
- **Real fix landed**: `tools/frida-gadget.config` was stale (a custom
  HTTP-fetch config pointing at an unreachable host, left over from an
  earlier session) and caused the previously-built gadget-injected APK to
  hang forever before `libclient.so` ever loaded. Replaced with the
  standard `{"type":"listen"}` interaction and placed correctly at
  `/data/app/<pkg>-<hash>/lib/arm64/libfrida-gadget.config` (root-owned
  directory, needs `su 0` heredoc write, not a plain `adb push`). **The
  app now boots all the way to the real title screen with the gadget
  active** — confirmed live, twice.
- **New blocker found (environment-class, not a mistake)**: Frida's view
  from inside the gadget only sees the native-bridge translation layer's
  own shim libraries (`/system/lib64/arm64/nb/*.so`) — `libclient.so`
  (the actual app engine, confirmed loaded and rendering) is invisible to
  `Process.enumerateModules()`/`findModuleByName()` from this session, a
  known class of problem on x86_64-with-ARM-translation Android emulators
  (this LDPlayer instance's kernel is x86_64; the APK is arm64-v8a-only,
  running under native bridge). This blocks the planned
  `PyMarshal_ReadObjectFromString` hook. Full evidence:
  `07_ros_legacy_approach/END_TO_END_TEST_LOG.md` E2E-004 Sub-test B.
- **Static crypto (fallback (a)) advanced but not broken**: confirmed the
  `7A 1C` container magic is a plaintext tag (encryption starts at byte
  offset 2), but disproved the simplest hypothesis that the stream cipher
  reuses one universal, file-independent keystream from byte 0 (a
  histogram of byte[2] across all 3,957 real entries shows a long tail of
  15+ distinct common values, not one dominant constant) — a real break
  needs either the per-file seed derivation (more `libclient.so`
  disassembly) or more extensive statistical cryptanalysis than this
  pass's budget allowed. See E2E-004 Sub-test C.
- **No script.npk edit was made this pass** — both extraction paths
  (dynamic via Frida, static via crypto) remain open. Device was left in
  its original clean working state (plain APK reinstalled via `adb
  install -r`, OBB files confirmed intact throughout — `install -r` was
  used instead of uninstall+install specifically to avoid repeating the
  prior pass's OBB-deletion incident, successfully this time).
- **NEXT_ACTION, in priority order, NO native `.so` involved**:
  1. **Human/infrastructure decision needed** (per stop condition B): the
     native-bridge module-visibility wall is best solved by testing on a
     genuinely arm64-native test device or emulator (real hardware, or an
     ARM64-hosted virtual device) rather than this x86_64+translation
     LDPlayer setup — this is an environment choice outside a routine next
     step, surfaced rather than attempted unilaterally.
  2. Alternatively, research a native-bridge-aware Frida injection
     technique (unexplored this pass).
  3. Continue the static crypto crib-drag: disassemble more of
     `libclient.so`'s marshal/package-loading code path (already
     partially traced per `bridge/RESULT_T11.md`) specifically looking for
     where a per-file seed would be derived (entry hash? offset? size?),
     to convert the disproven "one global keystream" guess into a correct,
     per-file-aware one.

---
*Last updated: 2026-09-15*  
*Project: ROS_RE — reverse-engineering workspace (sariling RE, walang ibang project)*