# BLOCKERS.md — Active Technical Unknowns & Missing Components

**Rule**: No invented values. All items listed here represent missing resources or unmapped protocol contracts.

---

## 1. Active Blockers

### BLK-01: BigWorld LoginApp Protocol Framing & Mercury Handshake (Priority: CRITICAL)
- **Component**: `neox::bwclient::ServerConnection::logOnBegin` -> port `25000`
- **What is known**:
  - Initial connection goes to port 25000 (from `server_list_ad.txt`).
  - Native client uses BigWorld Mercury protocol (`Mercury::Nub`, `Mercury::Bundle`).
  - Native method `neox::bwclient::LogOnParams::addToStream` packages login arguments.
- **What is missing/unknown**:
  - Exact binary packet framing of the initial bundle (magic bytes, packet header length, sequence indexing).
  - Exact contents / format of `entities/loginapp.pubkey` (RSA public key).
- **Safe Experiment**:
  - Run port 25000 capture daemon to record the exact byte stream emitted by the client during `logOnBegin`.

### BLK-02: BigWorld Official Server Binaries (Priority: ARCHITECTURAL)
- **Component**: `loginapp`, `baseapp`, `cellapp`, `dbapp`
- **Status**: **MISSING** from client distributions (expected for client-only packages).
- **Resolution Strategy**:
  - Construct a lightweight, compatible local Mercury adapter in Python using the extracted entity definitions (`LoginProxy.def.xml`, `Account.def.xml`).

### BLK-03: Emulator SurfaceView Touch Interception on Consent UI (Priority: HIGH)
- **Component**: Android UI on `MpayActivity` dialogs
- **What is known**:
  - NeoX game engine renders on a `SurfaceView` above standard Android view hierarchy in some emulator configurations, capturing raw touch events before they reach Dalvik dialog buttons.
  - Dalvik state machine maps `minor_status == 102` and `age_status == 1` as adult verified (`0x400826`, `0x3cc624`).
- **Resolution Strategy**:
  - Ensure the local auth service returns `minor_status: 102` and `age_status: 1` directly on the initial `/api/users/login/guest` and `/api/users/login/v2/sdk_token` responses so the consent activity does not open.

---

## 2. Resolved Blockers

- **[RESOLVED] Alarm 41006 / W_PARSE_NPK_VERSION_ERR**: Fixed by `##########` separator and JSON tail.
- **[RESOLVED] KeyError: 'type' in `patch_size_calc`**: Fixed by `"type": "package"` in JSON tail.
- **[RESOLVED] `forcePatch` & `CANCEL_STAGE` at startup ("Failed to retrieve patches")**: Fixed by planting `<absDocRoot>/patchVersion` = `1.0.0.en` at `/sdcard/Android/data/com.netease.chiji/files/netease/h45na/patchVersion`.
- **[RESOLVED] Server List 404 Loop**: Fixed by serving single-space positional `server_list_ad.txt`.
- **[RESOLVED] UniSDK Token Exchange**: Fixed by top-level `user_id` and `sdk_token` payload.
