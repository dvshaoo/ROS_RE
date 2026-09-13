# Local Session Contract

## Endpoint

`/api/users/login/v2/sdk_token`

## Status

FOUND

## Request

- **Method**: POST
- **URL**: `http://127.0.0.1:8080/api/users/login/v2/sdk_token` (or HTTPS port 8443)
- **Headers**:
  - `Content-Type`: `application/x-www-form-urlencoded` or `application/json`
  - `Host`: `sdk-os.mpsdk.easebar.com`
- **Body**: Form parameters or JSON including `user_id`, `token`, `game_id`, `cv`, `gv`, `device_id`.

## Response

- **Status Code**: 200 OK
- **Content-Type**: `application/json`
- **Body**:
```json
{
  "code": 0,
  "msg": "",
  "user_id": "guest_11178811c6a412d9",
  "sdk_token": "guest_token_fake_ros_2026",
  "alert_type": 0,
  "minor_status": 4,
  "age_status": 0,
  "security_email": "",
  "user": {
    "id": "guest_11178811c6a412d9",
    "account": "Guest_11178811c6a412d9",
    "login_token": "guest_token_fake_ros_2026",
    "token": "guest_token_fake_ros_2026",
    "quick_login_enable": true
  }
}
```

## Required Client Fields

- `user_id`: String (Top-level). Parsed by `com.netease.mpay.oversea.h.a.a:a` via `optString("user_id")` at Dalvik bytecode `0x3d34cc`.
- `sdk_token`: String (Top-level). Parsed by `com.netease.mpay.oversea.h.a.a:a` via `optString("sdk_token")` at Dalvik bytecode `0x3d34d8`.
- `code`: int. Evaluated by base response parser (0 indicates success).
- `msg`: String. Parsed via `optString("msg")` at Dalvik bytecode `0x3d34e4`.

## Evidence

1. **Client Disassembly (`02_dex/classes.dex`)**:
   - `0x3d34cc`: `const-string v3, "user_id"` -> `invoke-virtual {p1, v3}, Lorg/json/JSONObject;->optString(Ljava/lang/String;)Ljava/lang/String;`
   - `0x3d34d8`: `const-string v0, "sdk_token"` -> `invoke-virtual {p1, v0}, Lorg/json/JSONObject;->optString(Ljava/lang/String;)Ljava/lang/String;`
   - `0x3d34e4`: `const-string v1, "msg"` -> `invoke-virtual {p1, v1}, Lorg/json/JSONObject;->optString(Ljava/lang/String;)Ljava/lang/String;`
   - `0x3d34f4`: `invoke-direct {v1, v3, v0, v2}, Lcom/netease/mpay/oversea/h/a/b;-><init>(Ljava/lang/String;Ljava/lang/String;I)V` (instantiates local auth token container).
2. **Server Implementation (`mitm/mitm_serve.py:296-313`)**:
   - Explicit route handler for `/api/users/login/v2/sdk_token`.
   - Returns top-level `user_id`, `sdk_token`, `code: 0`, and `msg: ""` along with backward-compatible user object.

## Test Result

PASS

Independent validation via HTTP/HTTPS query confirmed:
- HTTP status: 200 OK
- Content-Type: `application/json`
- Valid JSON schema
- `user_id`: `"guest_11178811c6a412d9"` (type: `str`)
- `sdk_token`: `"guest_token_fake_ros_2026"` (type: `str`)

## Next Step

Live execution on Android emulator client to verify whether client consumes this contract and transitions toward G2 (Game Session / BigWorld loginapp connection on port 25000).
