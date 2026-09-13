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
