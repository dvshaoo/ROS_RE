# IMPLEMENTATION_PROGRESS.md — Milestone Progress Tracker

**Client Version**: `1.610377.506841`  
**Client Version Code**: `1117219`  
**Current Phase**: Phase 2 (Startup & Minimal Multiplayer Vertical Slice)  
**Last Updated**: 2026-09-14  

---

## 1. Acceptance Gates Summary

| Gate | Name | Target Objective | Status | Evidence / Verification |
|---|---|---|---|---|
| **G0** | **Startup & Patch** | Local patch manifest answered, zero crashes, boot reaches engine init | **CLEARED** ✅ | `/pl/npk_version_na_android.plist` (482B) + `patchVersion` (`1.0.0.en`). Zero crashes. |
| **G1** | **Auth / Test Session** | Local test token exchange, UniSDK reports clean success | **CLEARED** ✅ | `/api/users/login/v2/sdk_token` returns top-level `user_id` & `sdk_token`. Zero `onFailure(1000)`. |
| **G2** | **BigWorld BaseApp** | LoginApp answers Mercury handshake, routes to BaseApp | **IN PROGRESS** 🔄 | `ServerConnection::logOnBegin` mapped to port 25000. Listener active; responder under construction. |
| **G3** | **Role / Character List** | Client loads role/profile without fallback crash | **PENDING** ⏳ | Depends on G2 entity instantiation (`LoginProxy` -> `Account`). |
| **G4** | **Enter Hall** | Real 3D hall scene loads | **PENDING** ⏳ | Depends on G3. |
| **G5** | **Two-Client Room** | Two clients connect via LAN into same room | **PENDING** ⏳ | Core multiplayer prerequisite. |
| **G6** | **Playable Map** | Map loads, player spawn, movement synchronization | **PENDING** ⏳ | Vertical slice target. |
| **G7** | **Vehicles & Combat** | Vehicle enter/drive/damage + combat lifecycle | **PENDING** ⏳ | Post-vertical slice expansion. |

---

## 2. Phase Execution Detail

### Phase 0: Preserve and Inventory
- SHA-256 hashes generated and recorded for core binaries.
- All 723 entity defs cataloged in `05_entities/out/`.
- 3,959 Python modules cataloged.
- Official BigWorld server binaries verified absent (**MISSING**).
- **Status**: **COMPLETE**.

### Phase 1: Evidence Map
- Verified startup patch endpoints, `KeyError: 'type'` root cause, and `forcePatch` language check.
- Verified Dalvik bytecode contracts for UniSDK auth.
- Documented in `EVIDENCE_MAP.md` and `SERVER_RESOURCE_INVENTORY.md`.
- **Status**: **COMPLETE**.

### Phase 2: Startup Vertical Slice (G1 -> G2 -> G3 -> G4)
- Current focus: Construct minimal BigWorld Mercury `loginapp` protocol responder for port 25000.
- Handle `Mercury::Nub` packet framing.
- **Status**: **ACTIVE**.
