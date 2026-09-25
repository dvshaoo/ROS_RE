# ROS_RE Login/LVU Flow Trace

## DEX Mapping

| Class / Component | DEX File | Methods / Locations | Status | Evidence |
|---|---|---|---|---|
| `Lcom/netease/mpay/oversea/j/d/d;` | `classes.dex` | `c` @ code `0x3e0554` (`0x3e0564`-`0x3e05d2`) | FOUND | Local session controller; checks `isFirstLogin` & `has_minor`. |
| `Lcom/netease/mpay/oversea/j/a/h;` | `classes.dex` | `a` @ code `0x3dab5c`, `0x3dad04`, `0x3dad6c` | FOUND | Serializes/deserializes HashMap keys 1-5 (1=isFirstLogin, 4=has_minor, 3=token). |
| `Lcom/netease/mpay/oversea/e/b/c;` | `classes.dex` | `a` @ code `0x3cc968` (`0x3cc968`-`0x3cc9a0`) | FOUND | State machine packed-switch: 1=init, 2=query, 3=birthday, 4=consent, 5=email. |
| `Lcom/netease/mpay/oversea/e/b/d;` | `classes.dex` | `a` @ code `0x3ccee0` (`0x3ccee0`-`0x3ccfe4`) | FOUND | Evaluates server `minor_status`. Keys 0-3 loop; default invokes `0x3ccf9c` success. |
| `Lcom/netease/mpay/oversea/MpayActivity;` | `classes.dex` | `onCreate` @ `0x3beae0`, `close` @ `0x3be8c8` | FOUND | Hosts dialogs; delegates input and lifecycle to `ui/a`. |
| `Lcom/netease/mpay/oversea/MpayLoginCallback;` | `classes.dex` | `onFailure` #23773, `onLoginSuccess` #23774 | FOUND | Interface implemented by `SdkNeteaseGlobal$LoginCallback`. |
| `Lcom/netease/ntunisdk/SdkNeteaseGlobal$LoginCallback;` | `classes.dex` | `onFailure` @ code `0x43886c` (`0x43887c`-`0x438a34`) | FOUND | Logs `loginDone`, `raw_code: 1000`, `raw_msg: "Cancel login"`. Calls `ntOnLogin(1)`. |
| `Lcom/netease/mpay/oversea/ui/g$2;` | `classes.dex` | `onClick` @ code `0x3ffbb4` (`0x3ffbf0`-`0x3ffc68`) | FOUND | Hardcodes `const/16 v4, 1000` passed directly to `onFailure`. |
| `Lcom/netease/mpay/oversea/ui/g;` | `classes.dex` | `a(int)` @ code `0x400144` (`0x400154`-`0x4001d6`) | FOUND | Status code mapper: translates 10003, 10010 to 1000. |

`classes2.dex` and `classes3.dex` contain no NetEase MPay authentication logic (third-party and wrapper libraries only).

---

## Guest Login

1. Invoked by game Python script `ui/UILogin.py` calling `ntLogin()` via UniSDK.
2. Requests `POST /api/users/login/guest`.
3. Response parsed by `Lcom/netease/mpay/oversea/d/a/a/e;->a` at code `0x3c8f8c`:
   - `minor_status`: optInt (default 0)
   - `age_status`: optInt (default 4)
   - `user`: object with `id`, `account`, `token`, `login_token`

---

## has_minor Source

* **Writer**: `Lcom/netease/mpay/oversea/j/d/d;->c` at code `0x3e0554` (`0x3e05ce`: `iput-boolean v0, v3, Lcom/netease/mpay/oversea/g/d;::h : Z`).
* **Source value**: Computed by `Lcom/netease/mpay/oversea/j/a/h;->a(...)` at `0x3dad04`:
  - `h.d` stores the saved user token from local SharedPreferences (`com.netease.mpay...xml`).
  - If `h.d` is empty (new session or cleared storage), `has_minor` defaults to `true`.
* **Field storage**: SharedPreferences file `com.netease.mpay.202cb962ac59075b964b07152d234b70.xml`, serialized HashMap key `'4'` (`has_minor`) and `'3'` (`user_id/token`).

---

## LVU Trigger

* At `Lcom/netease/mpay/oversea/ui/g;->a(g$e)` (code `0x4007d8`):
  - Bytecode `0x4008a4`: reads `g$e.k` (`minor_status`).
  - Bytecode `0x4008a8`: calls `Lcom/netease/mpay/oversea/e/b;->a(int)` to get the LVU view tag (`lvu_person_info` for birthday).
  - Bytecode `0x4008dc`: displays the `User Age Setting` dialog.

---

## LVU State Machine

`Lcom/netease/mpay/oversea/e/b/c;->a` at code `0x3cc968`:

| State | Action / Request Builder | Endpoint | Next Transition |
|---|---|---|---|
| **1** | Init state | - | Moves to State 2 |
| **2** | `Lcom/netease/mpay/oversea/e/a/d;` | `/api/minors/query` | Handled by `e/b/d` (`0x3ccee0`) |
| **3** | `Lcom/netease/mpay/oversea/e/a/h;` | `/api/minors/update_birthday` | Submits `birthday` & `country_code` |
| **4** | `Lcom/netease/mpay/oversea/e/a/i;` | `/api/minors/consent` | Minor parent consent |
| **5** | `Lcom/netease/mpay/oversea/e/a/j;` | `/api/minors/update_email` | Submits parent email |

Response handler `0x3cca14`:
- Reads `minor_status` from `e/a/f`.
- Updates `loginInfo.m` (`minor_status`).
- Evaluates `e/a/f.a()`: if complete, updates local `has_minor` in SharedPreferences.

---

## MpayActivity

* Activity class: `Lcom/netease/mpay/oversea/MpayActivity;`.
* `onCreate` (`0x3beae0`): Configures window flags, transparent background, dim amount, and initializes UI manager `ui/a`.
* `close` (`0x3be8c8`): Calls `this.finish()`.
* `onBackPressed` (`0x3bea88`): Forwards to `ui/a.a()`; if not handled, calls `super.onBackPressed()`.

---

## Activity Result

* When Age Setting 'X' is tapped:
  - `MpayActivity` finishes with `RESULT_CANCELED`.
  - The dialog dismiss listener `g$2` is triggered.

---

## loginDone

* Logged in `Lcom/netease/ntunisdk/SdkNeteaseGlobal$LoginCallback;->onFailure` at `0x43897c`.
* Represents UniSDK terminal reporting step (`step="loginDone"`).
* Delivers `ntOnLogin(unisdk_code=1)` to the game engine.

---

## onFailure(1000)

* **Exact call site**: `Lcom/netease/mpay/oversea/ui/g$2;->onClick` at bytecode `0x3ffc2a`.
* **Disassembly**:
  ```smali
  0x3ffc16 iget-object v3, v2, Lcom/netease/mpay/oversea/ui/g$2;->c : Lcom/netease/mpay/oversea/MpayLoginCallback;
  0x3ffc1a const/16 v4, 1000
  0x3ffc1e iget-object v0, v2, Lcom/netease/mpay/oversea/ui/g$2;->d : Ljava/lang/String;
  0x3ffc22 iget-object v1, v2, Lcom/netease/mpay/oversea/ui/g$2;->b : Lcom/netease/mpay/oversea/ui/g$e;
  0x3ffc26 iget v1, v1, Lcom/netease/mpay/oversea/ui/g$e;->k : I
  0x3ffc2a invoke-interface {v3, v0, v4, v1}, Lcom/netease/mpay/oversea/MpayLoginCallback;->onFailure(Ljava/lang/String;II)V
  ```
* **Arguments**:
  - `v0`: `this.d` = `"Cancel login"` (from string resource `netease_mpay_oversea__login_error_cancel`)
  - `v4`: `1000` (constant literal)
  - `v1`: `this.b.k` = `minor_status` (0)

---

## Retry Loop

1. `MpayLoginCallback.onFailure` notifies `SdkNeteaseGlobal$LoginCallback`.
2. UniSDK fires `ntOnLogin(code=1)` to `ui/UILogin.py`.
3. Game shows Toast: `"Account login has been cancelled"`.
4. Game remains on Title Screen with `channelLogin = False`.
5. User presses **PLAY** button (`UILogin._on_click_login`).
6. Python checks `is_login == False` and re-invokes `ntLogin()`.
7. Because local storage still lacks saved adult token in `j/d/d`, `has_minor` triggers LVU again -> **LOOP**.

---

## Existing Creation/Offline Path

* **Finding**: `CREATE_ROLE` and `USERINFO_STAGE_CREATE_ROLE` exist in `classes.dex` strings (#3549, #19183).
* **Game Engine Logic**: Lives inside `script.npk` (BigWorld Mercury engine Python scripts).
* **Architecture**: The client connects to `loginapp` (`10.0.2.2:25000` specified in `server_list_ad.txt`). `loginapp` receives credentials, returns character list or triggers role creation on `baseapp`.
* **Offline Path**: There is no standalone local-only offline mode in the client binary; the client requires an authoritative server socket handshake on port 25000 to transition from Title Screen to Character Creation / Hall.

---

## Root Cause

`MpayActivity` displays the LVU Age Setting window because `j/d/d.c` defaults `has_minor = true` when local session storage is unpopulated. When the dialog is dismissed (or birthday token exchange `/api/users/login/v2/sdk_token` lacks top-level `user_id` and `sdk_token` keys), `ui/g$2` invokes `MpayLoginCallback.onFailure` with hardcoded `raw_code: 1000` (`"Cancel login"`). The game receives login failure, resets state, and pressing PLAY restarts the loop.

---

## Evidence

1. `02_dex/classes.dex`: `0x3ffc1a` (`const/16 v4, 1000`), `0x3ffc2a` (`invoke-interface onFailure`).
2. `02_dex/classes.dex`: `0x43886c` (`SdkNeteaseGlobal$LoginCallback;->onFailure` formats `loginDone`).
3. `02_dex/classes.dex`: `0x3e0554` (`j/d/d;->c` condition `isFirstLogin || has_minor`).
4. `02_dex/classes.dex`: `0x3d34bc` (`login/v2/sdk_token` response parser expects top-level `user_id`, `sdk_token`).
5. Live Logcat: `{"func":"MpayLoginCallback.onFailure","step":"loginDone","unisdk_code":"1","raw_code":"1000","raw_msg":"Cancel login"}`.

---

## Recommended Legitimate Fix

1. In local test server (`mitm/mitm_serve.py`), provide schema-compliant payloads for:
   - `/api/users/login/guest`: return valid `user` object, `minor_status: 4`, `age_status: 0`.
   - `/api/users/login/v2/sdk_token`: return top-level `"user_id": "guest_11178811c6a412d9"`, `"sdk_token": "guest_token_fake_ros_2026"`, `"code": 0`, `"msg": ""`.
2. This allows `com.netease.mpay.oversea.h.a.a` to parse successfully and invoke `onLoginSuccess` via `h.c.c$7` without triggering the cancel dialog.

---

## Remaining Unknowns

* BigWorld `loginapp` public key (`loginapp.pubkey`) and packet framing for the post-login handshake on port 25000 (Gate 1 -> Gate 2 transition).

## 2026-09-22 Regression Check — Age Dialog Before Title

- Live fresh launches still open `MpayActivity` and the **User Age Setting** page before the title screen, even when the local guest response sends `minor_status=102` and `age_status=1` and the normal `/api/games/config` response is served.
- Re-testing `birth_stage` enabled and disabled produced the same page. Restoring each available encrypted MPay SharedPreferences backup produced the same page. Therefore neither configuration flag nor the tested saved-state copies is sufficient evidence of a fix.
- Two temporary signed APK experiments that forced MPay `isFirstLogin` / `has_minor` false were installed and live-tested; both still displayed the page. They were removed by reinstalling the saved pre-test APK `scratch/currently_installed_backup.apk` immediately afterward.
- The decompiled pre-test APK already contains a non-original `"PATCHED: Age check bypassed, proceeding to login"` replacement in `e/b/d.smali`. Do not treat it as a verified fix. Trace the `MpayActivity` launch caller and its success callback before any next static patch.

## 2026-09-22 Emulator / Vivo Character-Creation Parity

- The Vivo path remained on `showSelectCharacter([])` and waited for the client `createCharacter` call; the emulator default immediately ran `onCreateCharacter -> onRoleCreateSuc -> updateBaseCharacter -> updateBaseNickname -> enterHall` after 2.5 seconds.
- That automatic entry races the first-time controller tutorial and accounts for the observed two Select Controls pages before the hall.
- The first manual-mode experiment used `ROS_AUTO_ENTER_HALL=0` and waited for exposed method 921 (`createCharacter`). The server received `showSelectCharacter([])` successfully, but the emulator stayed on the title layer and never sent a `createCharacter` RPC. This was reproduced with the current 8,169-byte stream, the 8,080-byte Vivo-captured stream, and a generated 8,157-byte stream with a blank `baseNickname`.
- Therefore the manual name editor is **not fixed** and must not be the default login mode. Its real client activation prerequisite remains unknown. `ROS_AUTO_ENTER_HALL` defaults back to `1`, preserving the previously live-proven automatic `Dev | Raysoo` hall path. `ROS_AUTO_ENTER_HALL=0` remains only an explicit research mode.
- Recovery verification: after restoring the original 8,169-byte player stream and automatic mode, a fresh emulator launch completed `PLAY -> one Select Controls confirmation -> hall`. The final hall rendered the persisted female outfit, 999999 diamond/coin balances, and `Dev | Raysoo`; the captured post-hall logcat contained no `SCRIPT ERROR`, `Traceback`, or `TypeError`.

## 2026-09-22 Current LAN Login Handoff

- The intended local profile remains automatic: `Dev | Raysoo`; manual nickname creation is still research-only and must not be re-enabled by default.
- Current successful control path is `PLAY -> Loading -> Select Controls -> Confirm -> Loading -> Daily Claim -> click START -> Lobby`. The control page is required only when the client has no stored controller choice. A second page after a completed confirmation remains a regression, not expected behavior.
- After Daily Claim, a full-screen **"click START"** overlay appears over the hall. It must be tapped once to dismiss it; until then hall navigation (Depot, Supply, etc.) is blocked behind the overlay. This is expected client behavior, not a soft-lock.
- **Known unresolved pre-title issue:** a fresh launch can open the MPay **User Age Setting** dialog before the title screen, despite the LAN guest/config responses. Closing the dialog with its X reaches the title screen; do not enter an age merely to work around it. This is separate from the BaseApp hall/control flow and must be traced through the MPay launch/success callback before it is called fixed.
- The latest clean-state work also guards persistent equipped appearance lists: IDs without a client prop definition must not be written into `wear`/`body`, because `character_scene.getPartsStyles` aborts hall construction with `AttributeError: 'NoneType' object has no attribute 'APPEAR'`. This is a hall-state integrity guard, not a Lobby Theme selector implementation.

## 2026-09-22 Supply / Hall-Theme List Delay & Flicker (observed live, root-caused)

- **Supreme Supply:** content takes visibly long to appear; the left tab list briefly disappears, then reappears and navigation works. Server log shows each `queryAvailableSupplement` gets a **39,368 B** `onQueryAvailableSupplement` reply (248 records, ~27 fragmented datagrams), re-sent on every client query (~15 replies in 23 s while the Supply UI was open). The client rebuilds the tab list on each reply, which accounts for the vanish/reappear flicker and the slow first paint.
- **Depot > Lobby Theme:** theme cards also populate with a delay. Root cause found server-side: `_hall_theme_runtime_goods()` filters the merged mall dict by truthy `HALL_PROP_ID`, but that field is truthy on **every** row of the normal mall tables (`0x832995b1`: 270, `0x878e57c9`: 345, `0x55977219`: 31 — e.g. good 1024 has `HALL_PROP_ID=400076`). Result: **660 goods** sent via idx 448 instead of the real **14** hall-theme goods in table `0x0687b507` (good ids 10000, 10002-10004, 19001-19010, whose `HALL_PROP_ID` values are real theme IDs like 279009). Live log: `HALL THEME: UI entry received; sent 660 Hall-theme goods via idx=448`.
- **Proposed fix:** source `_hall_theme_runtime_goods()` only from table `0x0687b507` instead of filtering the merged dict. Supplement payload size/frequency to be addressed separately.

## 2026-09-22 Select Controls Regression Retest

- Fresh emulator retest: close the pre-title Age dialog, tap **PLAY**, leave **Classic Mode** selected, and tap **Confirm** once after it becomes available. The client went directly to Daily Claim / hall without a second Select Controls page.
- Server evidence for that run: exactly one `Athlete.showSelectCharacter([])` and one automatic creation chain were emitted for BaseApp port `53735`; no second BaseApp channel or second scene-init call was observed.
- Logcat captured after arrival contained no `SCRIPT ERROR`. A temporary channel-handoff suppression experiment was removed because this successful trace did not exercise it; it must not be treated as the cause of the fix.

## 2026-09-25 Select Controls Double-Loop — User-Identified Trigger (Confirm-Before-Timer Race)

- Reproduced live: pressing **Confirm** on the Select Controls page immediately, before its on-screen countdown has visibly started ticking down, sends the client back through a full second `Loading -> Select Controls` cycle. Waiting until the countdown has counted down a few seconds (observed safe around the 8-9s mark from a ~10s start) before pressing Confirm avoids the loop every time.
- Server-side log correlation for the looping run (PID unchanged, same emulator session, ports differ only because each cycle opens a fresh BaseApp UDP channel):
  ```
  08:10:30 STAGE 1 createBasePlayer(Account) -> ('127.0.0.1', 65503)
  08:10:36 STAGE 5 HOLDING for 65503                      (first cycle completes)
  08:11:23 STAGE 1 createBasePlayer(Account) -> ('127.0.0.1', 59095)   (second cycle starts ~47s later)
  08:11:27 STAGE 5 HOLDING for 59095
  ```
  vs. the clean single-pass run after waiting for the timer:
  ```
  08:16:41 STAGE 1 createBasePlayer(Account) -> ('127.0.0.1', 56604)
  08:16:45 STAGE 5 HOLDING for 56604                      (only cycle; no repeat)
  ```
- No `SCRIPT ERROR`/Python traceback was found in logcat around either looping cycle, keepalive `setGameTime` cadence stayed a steady 5.0s throughout (no channel timeout), and the Android process PID was identical across both cycles (engine-level session reset, not an app crash/restart). One `Level Destroy (-1)` line appeared 6s after the second STAGE 5 with no accompanying traceback — not yet explained, likely unrelated teardown noise.
- This is a client-side timing/UI-state race (confirming before the countdown widget has initialized), not a server protocol bug — no server-side fix identified or attempted. Workaround: wait for the visible countdown to start ticking before tapping Confirm.
