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

## Milestone Chain (project gates G1–G6) — next frontier: LOGIN + SERVER LIST
- G1 Login (`loginapp` accepted) / G2 BaseApp / G3 Role list / G4 Hall / G5 Character / G6 Battle — all NOT YET attempted
- Current blocker: `server_list_ad.txt` + `notice_pc_hw.txt` all 404 (client loops); server-list schema + UniSDK/drpf auth are the next campaign (AGENT.md T02–T05 targets still open)

## Gate 2-6 — Not Yet Attempted
- G2: BaseApp session receive
- G3: Role list display
- G4: Hall loading (currently at fallback create screen)
- G5: Character model appearance
- G6: Battle loading

## Recent Task Completion
| Task | Status | Finding |
|------|--------|---------|
| **T13** | COMPLETE | G4 parser schema: `##########` separator + JSON tail. Minimal payload `##########\n{}` (13 bytes) eliminates error 41006 |
| **T14** | COMPLETE | `KeyError: 'type'` root cause: missing `"type": "package"` key in JSON tail. Also: `"version"` must be STRING, not int. |
| **T15** | NARROW-VERIFIED | `patch/ResourcePatcher.py:1285,1299,1308-1324` — string `file_list` + `_updated/_size/_md5` tail keys resolve ZeroDivision/TypeError/missing-key crashes. Live-verified: no traceback, boot reaches `properties.init()`. |
| **T16** | STATIC-PASS (live of clearing input pending) | `bridge/RESULT_T16.md` — force-Patch driver mapped: `patchVersion` file absent → `patch_utils.py:18` None → `patch_mgr.py:611` True → `patch_mgr.py:446` `forcePatch=True` → `patch_mgr.py:665` print + `CANCEL_STAGE`. Chain matches live log (`patch_language: None`, `need patch for language!`, `force Patch!`). One citation slip: §1 step 4 says `patch/patch_size_calc.py`, should be `patch/ResourcePatcher.py`. |
| **T17a** | STATIC-PASS (one location correction) | `bridge/RESULT_T17a.md` — sole writer `BaseStage.beforePatchFinish` (`patch_mgr.py:160-162`), format L447 `1.<engine>.<client>.<lang>`, cancel path writes too (L667), deleter `BirthStage.cleanPatch`. CORRECTION: `absDocRoot` = `/sdcard/Android/data/com.netease.chiji/files/netease/h45na/` (live-proven), not `/data/data/.../files/`. No `patchVersion`/`firstPackVersion` found device-wide → cancel-path write never lands there. |
| **T17b** | LIVE-PASS ✅ | Planted `patchVersion`=`1.0.0.en` at true doc root; fresh boot: plist served 482B, zero `force Patch!`/traceback, client reaches `requestServerList`+`channelLogin` keypoints with `"patch_version":"1.0.0.en"`. PATCH GATE CLEARED. |
| **Gate 1** | IN PROGRESS | Plist parses; `patch_size_calc` crash-free; clearing input for `forcePatch` is T17 (write local `patchVersion` vs serve path) |

## Next Steps
1. LVU age/consent (T19, this session): panels NOT bypassed — age auto-opens every login (RUN-A FAIL, screenshot). Proven: (1,1)=minor-consent path, (0,0)=restart, (2,2)=hard fail. Verified enum → BLOCKED-008 (map e/b/c states 2-5 or capture original).
2. After LVU: G1 fake loginapp at 10.0.2.2:25000 (BigWorld Mercury; needs loginapp.pubkey + protocol RE) → G2 baseapp → G3 role/creation → G4 hall.
3. Continue gate-by-gate verification against original (reference/ still empty — need Leo captures).

---
*Last updated: 2026-09-13*  
*Project: ROS_RE — reverse-engineering workspace (sariling RE, walang ibang project)*