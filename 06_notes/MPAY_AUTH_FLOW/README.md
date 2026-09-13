# NetEase MPay Authentication & Minor / Age Consent Analysis (Rules of Survival)

This document and directory contain the exact reverse-engineered driver chain and Dalvik bytecode references for:
- `MpayLoginCallback` (`onLoginSuccess`, `onFailure`)
- `raw_code: 1000` / `Cancel login`
- `MpayActivity` lifecycle and UI dismissal
- Age / Consent LVU workflow (`User Age Setting`, `Parent Email`)
- `minor_status`, `age_status`, `has_minor`
- `login/v2/sdk_token` and `Guest Login` (`/api/users/login/guest`)

---

## 1. Key Classes & Methods Map

| Class | Method | Dex Offset | Purpose |
|---|---|---|---|
| `Lcom/netease/mpay/oversea/d/a/a/e;` | `a(JSONObject)` | `0x3c8f8c` | Parses `/api/users/login/guest` response: `user`, `minor_status`, `age_status` |
| `Lcom/netease/mpay/oversea/ui/g$1$1;` | `run()` | `0x3ff840` | Post-login verification: checks `has_minor`, routes to `onLoginSuccess` or `onFailure(minorStatus)` |
| `Lcom/netease/mpay/oversea/ui/g$2;` | `onClick(...)` | `0x3ffbb4` | Dialog cancel handler: converts cancel action to `MpayLoginCallback.onFailure(1000)` ("Cancel login") |
| `Lcom/netease/mpay/oversea/ui/g;` | `a(int)` | `0x400144` | Status mapper: maps internal state `10003` / `10010` to public error code `1000` (`Cancel login`) |
| `Lcom/netease/mpay/oversea/e/b/d;` | `a(...)` | `0x3ccee0` | LVU minor status router: checks `minor_status` ({0,1,2,3} = LVU loop; default/4 = success dismissal) |
| `Lcom/netease/mpay/oversea/h/a/a;` | `a(JSONObject)` | `0x3d34bc` | Parses `/api/users/login/v2/sdk_token` response: requires top-level `user_id`, `sdk_token` |
| `Lcom/netease/mpay/oversea/h/c/c$7;` | `a(...)` | `0x3d4ce8` | Callback for token refresh: invokes `onLoginSuccess` via `TransmissionData$LoginData` |
| `Lcom/netease/mpay/oversea/j/d/d;` | `c(...)` | `0x3e0554` | First login / user token check: sets `has_minor = true` if user token is empty |

---

## 2. Disassembled Flow Files in This Directory

1. `01_login_response_parser_0x3c8f8c.txt`:
   - Decodes `minor_status` (default 0), `age_status` (default 4).
   - Extracts user credentials (`id`, `account`, `token`, `login_token`).

2. `02_post_login_branch_and_onLoginSuccess_0x3ff840.txt`:
   - `0x3ff902`: Checks `isFirstLogin` and `has_minor`.
   - `0x3ff958`: If minor verification pending -> calls `onFailure(User.minorStatus)`.
   - `0x3ff978`: If minor verification satisfied -> calls `MpayLoginCallback.onLoginSuccess(User)`.

3. `03_cancel_login_callback_1000_0x3ffbb4.txt`:
   - `0x3ffc1a`: Loads constant `1000`.
   - `0x3ffc2a`: Calls `MpayLoginCallback.onFailure(msg, 1000, minorStatus)`.

4. `04_status_code_mapping_to_1000_0x400144.txt`:
   - Internal switch table converting cancel/dismiss events (10003, 10010) to `1000`.

5. `05_minor_status_query_handler_0x3ccee0.txt`:
   - Query response processor: handles minor statuses {0, 1, 2, 3}.
   - Fallthrough (`0x3ccf9c`): constructs success result `g$e` and calls `onLoginSuccess`.

6. `06_sdk_token_login_v2_parser_0x3d34bc.txt`:
   - Parses response from `POST /api/users/login/v2/sdk_token`.
   - Requires top-level `"user_id"` and `"sdk_token"`.

7. `07_sdk_token_login_callback_0x3d4ce8.txt`:
   - Checks if token refresh succeeded and invokes final success callback.

---

## 3. Logcat Failure Trace

```json
{"func":"MpayLoginCallback.onFailure","step":"loginDone","unisdk_code":"1","raw_code":"1000","raw_msg":"Cancel login","minaStatus":"0","gameid":"h45naxx1gb","transid":"11178811c6a412d9_1789298666046_006606954","channel":"netease_global","version":"2.13.0","UDID":"11178811c6a412d9","logtime":"2026-09-13 19:29:50","timestamp":"2026-09-13 19:29:50","res_code":200}
```
