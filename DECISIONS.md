# DECISIONS.md — Every Attempt and Outcome

## Rule: Before trying anything, check here — never repeat a logged failure.

All entries below are permanent. Do not delete or overwrite. Add new entries at the bottom.

## GATE 1 — PATCH VERSION CHECK

### T13 — G4 Parser Hypotheses (May 2026)
- **T07-Hypothesis-A**: Serve plain text `b'G4\nversion=1117219\ncount=0\n'` → **FAILED**: `W_PARSE_NPK_VERSION_ERR` (41006). Parser enforces `##########` separator.
- **T07-Hypothesis-B**: Serve XML plist → **FAILED**: `W_PARSE_NPK_VERSION_ERR`. Parser not XML.
- **T07-Hypothesis-C**: Serve manifest-mirror bplist → **FAILED**: `W_PARSE_NPK_VERSION_ERR`.
- **T07-Hypothesis-D**: Serve 200-empty body → **FAILED**: `W_PARSE_NPK_VERSION_ERR`.
- **T07-Hypothesis-E**: Serve empty plist → **FAILED**: `W_PARSE_NPK_VERSION_ERR`.
- **T13**: Cracked parser from bytecode → format is `##########` + JSON tail. Minimal payload `##########\n{}` (13 bytes). **PASS**.

### T14 — KeyError: 'type' Investigation (September 2026)
- **Initial**: Served plist without `"type"` key → `KeyError: 'type'` at `ResourcePatcher.py:1279`. **FAILED**.
- **Root cause identified**: JSON tail missing `"type": "package"` key. All scalar config keys must come from JSON tail; head only parses CSV lines.
- **Fix applied**: Serve plist with `"type": "package"`, `"version": "1117219"` (string), `"file_list": []`, `"use_dlc_clothes": false`.
- **Result**: `process_result host=g61.update.easebar.com, success=True, fault=None` — **PASS** (gate 1 passes). Remaining: `ZeroDivisionError` in `patch_size_calc`.

### T15 — ZeroDivision/TypeError/missing-_updated Fix + Live Verification (September 2026)
- **Static fix (AntiGravity)**: `file_list` as string list `["patch.1117219.com.netease.chiji.obb"]` + tail keys `<name>_updated: 0`, `<name>_size: 1`, `<name>_md5: "00...0"` + protocol-2 `{}` total_list. Rationale matches T14 bytecode: L1296 loop needs string fileName; L1308 needs `version_info[fileName + '_updated']`; L1320 `type == 'package'` + `_updated == 0` → `needPatch=False`, `useFirstPack=True`.
- **Stale-server trap caught live**: port 8080 had THREE stale listeners (PIDs 14948, 25084, 2252) serving the old 339-byte payload (dict-entry file_list). Disk file already held the 482-byte T15 payload. Killed all three, restarted ONE server from disk, re-fetched: `200`, 482 bytes, `_updated` keys present. **Lesson: always re-fetch served bytes after any edit; PID count >1 = stale.**
- **Live verdict (PID 3161, fresh logcat)**: `fubingnan version info` contains all T15 keys; `filesToPatch [u'patch.1117219.com.netease.chiji.obb']` then `[]`; ZERO `Traceback`/`KeyError`/`ZeroDivisionError`/`TypeError`; boot continues to `[trouger] properties.init()... assets/data/properties`. **Narrow claim VERIFIED: the three crashes are gone.**
- **New state (NOT a pass)**: `fubingnan totalSizeToDownload == 0 but force Patch!, patch resource got problem?` — non-fatal (boot continues). Needs triage: find driver (which flag forces Patch when size is 0), then decide next change. Gate 1 NOT passed; parity UNDECIDABLE (no original reference); screenshot PENDING.

### T16 — force-Patch Driver Trace, Static Assessment (September 2026)
- **Delivered**: `bridge/RESULT_T16.md` (106 lines). Chain: `patchVersion` file absent → `patch_utils.py:18` returns None → `patch_mgr.py:611` `need_language_patch=True` → `patch_mgr.py:444-446` `forcePatch=True` → `patch_mgr.py:664-668` print + `CANCEL_STAGE`. Excerpts for print site (655-670), setter (431-447), check (608-615), reader (18-30).
- **Cross-check vs live log (PID 3161)**: `patch_language: None`, `need patch for language!`, `force Patch!` all observed — chain CONSISTENT with runtime. No contradiction.
- **One citation slip**: §1 step 4 cites `patch/patch_size_calc.py`; per T14 the function lives in `patch/ResourcePatcher.py`. Corrected here; not a driver error.
- **Key new facts**: L659 clean-exit branch `if not (forcePatchForValidation or needPatch)` → `patch_finish()` exists but is unreachable while `forcePatch=True` (L664 takes precedence). L447 builds `context.patchVersion = '1.%d.%d.%s'` from plist mins + language — context field, not the file. Cancel path never writes the file → manual file write is the candidate clearing input.
- **Verdict**: STATIC-PASS. Live test of clearing input is T17 (this session).

### T17a — patchVersion Path + Write-Site, Static Assessment (September 2026)
- **Delivered**: `bridge/RESULT_T17a.md` (92 lines). Sole writer `BaseStage.beforePatchFinish` (`patch_mgr.py:160-162`), format L447 `1.<engine>.<client>.<lang>`, cancel path writes (L667), deleter `BirthStage.cleanPatch` (292+), callers listed (660/667/735/737/990/1087).
- **CORRECTION (live-proven)**: `absDocRoot` is NOT `/data/data/com.netease.chiji/files/` — device-wide find shows no `patchVersion`/`firstPackVersion` there or anywhere; the true client-writable doc root is `/sdcard/Android/data/com.netease.chiji/files/netease/h45na/` (resident `VersionRecord`=`1.610377.506841`, `user_data.xml`, `assets.npk`, `script/`, `res/`). T17a's filename/format/writer/deleter citations stand; only the engine-derived path guess was wrong.
- **Verdict**: STATIC-PASS with location correction.

### T17b — Clearing-Input Live Test: PASS, PATCH GATE CLEARED (September 2026)
- **One change**: wrote `/sdcard/Android/data/com.netease.chiji/files/netease/h45na/patchVersion` = `1.0.0.en` (matches live `settingLanguage: en`; reader strips, so no-newline fine). File survives reboot — cleanPatch does not delete on normal boot.
- **Fresh boot (PID 4053)**: `GET /pl/npk_version_na_android.plist` → served 482-byte T15 plist (`SERVE_B.txt:6926-6927`); ZERO `force Patch!`/`Traceback`/`KeyError`/`ZeroDivisionError`/`TypeError` in fresh logcat; client advanced to `requestServerList` + `channelLogin` keypoints reporting `"patch_version": "1.0.0.en"` (`SERVE_B.txt:6957,6959`); plist download telemetry confirms fetch (`SERVE_B.txt:6962-6972`).
- **Note**: no `/1117219/total_list` request arrived this boot — with `type: package` the total-list step is evidently skipped (likely package-mode early path in the undisassembled L1282-1286 gap). No 2055 alarm either. Behavior-verified; no action needed.
- **Verdict**: LIVE-PASS. Patch gate CLEARED. Next frontier: server list (`server_list_ad.txt` 404 loop) + UniSDK/drpf auth (AGENT.md T02–T05). Screenshot PENDING; parity UNDECIDABLE.

## T19 — LVU (Age/Consent) Bypass Campaign (2026-09-13, single-editor: Muse session; Gemini stopped)

Driver map (all cited to `02_dex/classes.dex` via `scratch/dexdis.py`):
- Login parser `d/a/a/e.a` (code 0x3c8f8c): `optInt(minor_status)` default 0, `optInt(age_status,4)` default 4 → `d/a/b/c` result → `User.minorStatus` (default 0, `User.<init>` 0x3c20cc).
- Minors req builders: query `e/a/d` (`/api/minors/query`), configs `e/a/b` (reads ONLY `country_codes` — our configs schema valid), birthday `e/a/h` (birthday+country_code), email `e/a/j`, consent `e/a/i`.
- Shared resp parser `e/a/e` (0x3cc540): minor_status/age_status/alert_msg → `e/a/f`; `e/a/f.B()` (0x3cc624) returns (age_status==1).
- Orchestrator `e/b/c` (LVU pages via `e/b` router: lvu_query/input_mail/upload_image/person_info/waiting_result); `has_minor` Bundle flag (`g/d.h`, key 'has_minor') written from `e/b/c` + `j/d/d`.
- Post-login branch `ui/g$1$1` (0x3ff858): onFailure(User.minorStatus) vs onLoginSuccess. `LoginCallback` reports MINOR_STATUS prop + `minaStatus` clientlog (matches SERVE_B 13:20:05).
- Query-result switch `e/b/d` (0x3ccee0): packed-switch on minor keys {0,1,2,3} → uniform LVU-loop target; default → alert dialog. (Payload parsed from bytecode.)

Live runs (adb emulator-5554, MITM restarted by this session; iptables DNAT 80→8080/443→8443 + adb reverse intact):
- RUN-A: guest-login WITHOUT minor_status/age_status (parser defaults 0/4). Stamp `RUN-A no-minor-fields` served 14:14:30. VERDICT: FAIL for panels — age panel still auto-opens (screenshot `06_notes/login_runa.png`). No crash; login flow otherwise identical. KEPT (harmless, more truthful than fake minor=1).
- X-dismiss (1225,171 via uiautomator bounds): closes age panel → title screen (PLAY + `Fast North_America` server row renders). But PLAY re-runs login → panel reopens. NOT a bypass. First X tap missed (1290,185 outside [1191,137][1259,205]) — use uiautomator bounds always.
- Birthday submit 05-2004 (adult 22) + update_birthday=(1,1) → parent-email panel. PROVEN: (1,1) = minor-pending-consent even for adult birthday (server authoritative).
- Email submit test@example.com + update_email=(1,1) → confirm loop, no progress (SERVE_B 14:31:16). PROVEN: (1,1) on email = wait, not verified.
- RUN-B: update_email=(0,0) → client RESET to empty birthday panel. PROVEN: (0,0) on email = restart-verification, not verified. REVERTED (RUN-C minor=4 never landed — server restarted mid-tap, no request; reverted to (1,1) per no-untested-edits).
- Earlier (2,2) → channelLoginFail code 1 / "Cancel login" / minaStatus 2 (SERVE_B 13:20:05). PROVEN: 2 = hard-blocked.
- Verified-terminal enum for update responses REMAINS UNKNOWN → BLOCKED-008. Next: map e/b/c state machine (packed-switch keys 2-5 @0x3cc968) or obtain original-server capture.

## GATES 2-6 — NOT YET ATTEMPTED
- G2: BaseApp session receive
- G3: Role list display
- G4: Hall loading (currently fallback create screen)
- G5: Character model appearance
- G6: Battle loading

---
*Per rule §8: All verified goes unrecorded. Unknowns go to BLOCKED.md. Before trying anything, check here — never repeat a logged failure.*
*Last updated: 2026-09-13*