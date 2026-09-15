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

---
*Last updated: 2026-09-15*  
*Project: ROS_RE — reverse-engineering workspace (sariling RE, walang ibang project)*