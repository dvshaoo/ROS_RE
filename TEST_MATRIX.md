# TEST_MATRIX.md — Systematic Test Execution Matrix

**Client Version**: `1.610377.506841`  
**Client Version Code**: `1117219`  

---

## 1. Test Matrix

| Test Scenario | One Client | Two Clients | Reproducible | Primary Evidence / Log Citation | Status |
|---|:---:|:---:|:---:|---|:---:|
| **Startup / Patch Retrieval** | PASS | PENDING | YES | `SERVE_B.txt:6926-6927`, `patchVersion` planted | **VERIFIED** |
| **Local Auth / Token Exchange** | PASS | PENDING | YES | `LOCAL_SESSION_CONTRACT.md`, Dalvik `0x3d34bc` | **VERIFIED** |
| **Server List Selection** | PASS | PENDING | YES | `UILogin.py:197`, `requestServerList` keypoint | **VERIFIED** |
| **Mercury LoginApp Handshake** | IN PROGRESS | PENDING | UNTESTED | Port 25000 TCP/UDP connection | **IN PROGRESS** |
| **BaseApp Session & Role List** | PENDING | PENDING | NO | Awaiting Mercury handshake completion | **PENDING** |
| **Hall Entry** | PENDING | PENDING | NO | Awaiting BaseApp entity creation | **PENDING** |
| **Room Create / Join** | PENDING | PENDING | NO | Awaiting Hall service | **PENDING** |
| **Map Loading** | PENDING | PENDING | NO | Awaiting Room launch | **PENDING** |
| **Movement Synchronization** | PENDING | PENDING | NO | Awaiting CellApp simulation | **PENDING** |
| **Combat & Damage** | PENDING | PENDING | NO | Post-vertical slice | **PENDING** |
| **Loot & Inventory** | PENDING | PENDING | NO | Post-vertical slice | **PENDING** |
| **Vehicle Enter / Drive / Sync** | PENDING | PENDING | NO | Post-vertical slice | **PENDING** |
| **Match End & Return to Hall** | PENDING | PENDING | NO | Post-vertical slice | **PENDING** |

---

## 2. Test Execution Log

### Test T-01: G0 Startup & Patch Manifest Verification
- **Command**: Launch `com.netease.chiji` on `emulator-5554` with local DNS redirect to MITM service on port 8080.
- **Expected**: `GET /pl/npk_version_na_android.plist` returns 200 (482 bytes); client executes `properties.init()`; zero tracebacks; zero `force Patch!`.
- **Actual**: 200 OK served; client advanced to `requestServerList` reporting `"patch_version": "1.0.0.en"`.
- **Result**: **PASS**.

### Test T-02: G1 Local Auth Exchange
- **Command**: Trigger guest login on title screen.
- **Expected**: POST to `/api/users/login/v2/sdk_token` returns 200 with top-level `user_id` & `sdk_token`; no `onFailure(1000)` triggered.
- **Actual**: 200 OK returned; top-level keys parsed cleanly at `0x3d34bc`; no `onFailure(1000)` recorded.
- **Result**: **PASS**.
