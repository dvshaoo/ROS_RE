# EVIDENCE_MAP.md — Verified Traces, Disassembly, and Protocol Contracts

**Client Version**: `1.610377.506841`  
**Client Version Code**: `1117219`  
**Rule**: No guessing. Every entry cites file path, line number, opcode, or reproducible trace.

---

## 1. Startup & Patch System (Gate 0)

### 1.1 Patch Version Manifest Endpoint
- **Feature**: Patch list retrieval
- **Source File**: `patch/ResourcePatcher.py:403-420`, `patch/antihijack.py:264-269`
- **Client Version**: `1.610377.506841` (v1117219)
- **Endpoint**: `GET /pl/npk_version_na_android.plist`
- **Host**: `g61.update.easebar.com`
- **Request Format**: Standard HTTP GET
- **Response Format**: Exact delimiter `##########` (10 hash characters `0x23`) followed by JSON tail.
- **Minimum Required JSON Keys**:
  ```json
  {
    "type": "package",
    "version": "1117219",
    "version_name": "1.610377.506841",
    "min_client_version": 0,
    "min_engine_version": 0,
    "min_patch_client_version": 0,
    "min_patch_engine_version": 0,
    "use_dlc_clothes": false,
    "file_list": [],
    "patch.1117219.com.netease.chiji.obb_updated": 0,
    "patch.1117219.com.netease.chiji.obb_size": 1,
    "patch.1117219.com.netease.chiji.obb_md5": "00000000000000000000000000000000"
  }
  ```
- **State Transition**: `_parse_npk_version_string` succeeds -> `PatchCache.VERSION_INFO` populated -> advances to `patch_size_calc`.
- **Status**: **PROVEN** (Live-verified 2026-09-13, PID 4053, zero tracebacks).

### 1.2 "Failed to retrieve patches" Driver Chain
- **Feature**: Language check & forcePatch
- **Source Files**: `patch/patch_utils.py:18-30`, `patch/patch_mgr.py:446, 611, 665`
- **Trigger**: `<absDocRoot>/patchVersion` absent or does not match `settingLanguage: en`.
- **Location on Android**: `/sdcard/Android/data/com.netease.chiji/files/netease/h45na/patchVersion`
- **Clearing Input**: Content string `1.0.0.en`
- **Status**: **PROVEN** (Survives reboot, eliminates `CANCEL_STAGE` trigger).

### 1.3 Total List Endpoint
- **Feature**: File download manifest
- **Source File**: `patch/ResourcePatcher.py:1285`
- **Endpoint**: `GET /1117219/total_list`
- **Response Format**: zlib-compressed cPickle object (`pickle.dumps({}, 2)`).
- **Status**: **PROVEN**

---

## 2. Server List System

### 2.1 Server List Schema
- **Feature**: Game cluster resolution
- **Source File**: `ui/UILogin.py:197-237` (OBB `script.npk`)
- **Endpoint**: `GET /server_list_ad.txt`
- **Format**: Single-space-delimited positional line:
  `North_America 1 1 1 North_America North_America 127.0.0.1:25000 127.0.0.1:25000 127.0.0.1:25000 10001 127.0.0.1:25000\n`
- **State Transition**: Dispatches `requestServerList` success keypoint, renders server row on title screen.
- **Status**: **PROVEN**

---

## 3. Account & Local Auth System (Gate 1)

### 3.1 Token Verification Endpoint
- **Feature**: Local test session token exchange
- **Source File**: `02_dex/classes.dex` (`com.netease.mpay.oversea.h.a.a:a` at Dalvik `0x3d34bc-0x3d34f4`)
- **Endpoint**: `POST /api/users/login/v2/sdk_token`
- **Required Response**:
  ```json
  {
    "code": 0,
    "msg": "",
    "user_id": "guest_11178811c6a412d9",
    "sdk_token": "guest_token_fake_ros_2026",
    "alert_type": 0,
    "minor_status": 102,
    "age_status": 1,
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
- **Evidence**: Dalvik `optString("user_id")` (`0x3d34cc`) and `optString("sdk_token")` (`0x3d34d8`).
- **Status**: **PROVEN** (Live-exchanged without `onFailure(1000)`).

---

## 4. BigWorld Mercury Network Layer (Gate 2)

### 4.1 LoginApp Connection Handshake
- **Feature**: Mercury session initiation
- **Source File**: `03_lib/libclient_arm64.so`
- **Native Symbols**:
  - `neox::bwclient::ServerConnection::logOnBegin(char const*, char const*, char const*, char const*, unsigned short)`
  - `neox::bwclient::LogOnParams::addToStream(Mercury::Bundle&)`
  - `neox::bwclient::LoginHandler::onLoginReply`
- **Network Target**: Port `25000` (UDP/TCP)
- **Status**: **INFERRED / FRONTIER** (Connection initiation proven by native symbols; Mercury packet framing responder under implementation).
