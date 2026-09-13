# DEX Index

This document tracks all scanned targets across DEX files in `02_dex/`:
- `02_dex/classes.dex` (43,936 strings, 38,172 methods, 5,323 classes)
- `02_dex/classes2.dex` (30,118 strings — Google Play, Firebase, Ads, Facebook)
- `02_dex/classes3.dex` (38,147 strings — AppsFlyer, UniSDK core wrappers)

| DEX | Class | Method | Search Term | Location | Status | Notes |
|---|---|---|---|---|---|---|
| `classes.dex` | `Lcom/netease/mpay/oversea/MpayActivity;` | All lifecycle | `MpayActivity` | code `0x3be720` - `0x3beec8` | SEARCHED | 7 direct, 25 virtual methods. Delegates to `ui/a`. |
| `classes.dex` | `Lcom/netease/mpay/oversea/MpayLoginCallback;` | `onFailure`, `onLoginSuccess`, `onDialogFinish` | `MpayLoginCallback` | type #4267, methods #23773, #23774 | SEARCHED | Interface implemented by `SdkNeteaseGlobal$LoginCallback`. |
| `classes.dex` | `Lcom/netease/ntunisdk/SdkNeteaseGlobal$LoginCallback;` | `onFailure` | `onFailure` / `loginDone` | code `0x43886c` (`0x43887c` - `0x438a34`) | SEARCHED | Logs `func="MpayLoginCallback.onFailure", step="loginDone", unisdk_code=1, raw_code=1000, raw_msg="Cancel login"` |
| `classes.dex` | `Lcom/netease/mpay/oversea/ui/g$1$1;` | `run` | `onLoginSuccess` / `minorStatus` | code `0x3ff840` (`0x3ff858` - `0x3ff9ae`) | SEARCHED | Checks `isFirstLogin` & `has_minor`. Calls `onLoginSuccess` or `onFailure(minorStatus)`. |
| `classes.dex` | `Lcom/netease/mpay/oversea/ui/g$2;` | `onClick` | `1000` / `Cancel login` | code `0x3ffbb4` (`0x3ffbf0` - `0x3ffc68`) | SEARCHED | Hardcodes literal 1000: `MpayLoginCallback.onFailure(msg, 1000, minorStatus)`. |
| `classes.dex` | `Lcom/netease/mpay/oversea/ui/g;` | `a(int)` | `1000` / status mapper | code `0x400144` (`0x400154` - `0x4001d6`) | SEARCHED | `packed-switch` mapping internal dismiss codes 10003, 10010 to 1000. |
| `classes.dex` | `Lcom/netease/mpay/oversea/j/d/d;` | `c` | `j/d/d` / `0x3e0554` | code `0x3e0554` (`0x3e0564` - `0x3e05d4`) | SEARCHED | Checks `c.d().f` (isFirstLogin) and `c.d().h` (has_minor). Calls `h.a()`. |
| `classes.dex` | `Lcom/netease/mpay/oversea/j/a/h;` | `a`, `c` | `has_minor` storage | code `0x3dab5c`, `0x3dad04`, `0x3dad6c` | SEARCHED | Deserializes/serializes HashMap keys '1'-'5'. Key '4' is `has_minor`, key '1' is `isFirstLogin`. |
| `classes.dex` | `Lcom/netease/mpay/oversea/e/b/c;` | `a` | `e/b/c` / `0x3cc968` | code `0x3cc968` (`0x3cc968` - `0x3cc9a0`) | SEARCHED | LVU state machine: 1=init, 2=query, 3=birthday, 4=consent, 5=email. |
| `classes.dex` | `Lcom/netease/mpay/oversea/e/b/d;` | `a` | `minor_status` switch | code `0x3ccee0` (`0x3ccee0` - `0x3ccfe4`) | SEARCHED | Switch on keys 0,1,2,3 -> LVU loop; default -> calls `a()` (`0x3ccf9c`) to dismiss. |
| `classes.dex` | `Lcom/netease/mpay/oversea/h/a/a;` | `a` | `login/v2/sdk_token` | code `0x3d34bc` (`0x3d34cc` - `0x3d34fa`) | SEARCHED | Parses top-level `user_id`, `sdk_token`, `msg`, `code`. |
| `classes.dex` | `Lcom/netease/mpay/oversea/h/c/c$7;` | `a` | token refresh callback | code `0x3d4ce8` (`0x3d4cf8` - `0x3d4d70`) | SEARCHED | Calls `TransmissionData$LoginData;->c` -> `onLoginSuccess`. |
| `classes2.dex` | Third-party SDKs | - | All target strings | Entire string table | SEARCHED | Only contains Google Play, Facebook, Firebase SDKs. No NetEase MPay auth. |
| `classes3.dex` | UniSDK core | - | All target strings | Entire string table | SEARCHED | Contains AppsFlyer, UniSDK core dispatchers, WeChat pay SDK. |
