# ROS_RE — Offline/LAN Rebuild Master Roadmap

> **Purpose:** Master engineering checklist for rebuilding a Rules of Survival research/test environment into a self-contained offline/LAN gameplay stack.  
> **Target:** Laptop authoritative local server + up to 3 Android devices on the same LAN.  
> **Important scope note:** This roadmap focuses on legitimate local/test-session architecture, reverse-engineering documentation, gameplay systems, networking, build/install, persistence, and performance. It does **not** provide instructions for defeating age/consent verification, forging authentication/session tokens, or disabling security gates.

---

## 0. PROJECT RULES

- [ ] Keep an untouched backup of every original APK, DEX, native library, asset package, config, and database.
- [ ] Keep original files read-only.
- [ ] Separate `original/`, `working/`, `build/`, `server/`, and `docs/`.
- [ ] Record every discovered class, method, address, asset, config key, endpoint, packet type, and state transition.
- [ ] Never implement a guessed dependency when the original dependency can be documented first.
- [ ] Mark every finding:
  - `FOUND`
  - `PARTIAL`
  - `BROKEN`
  - `MISSING`
  - `SERVER-DEPENDENT`
  - `UNKNOWN`
- [ ] Use deterministic test data for local development.
- [ ] Keep client/server protocol versions explicit.
- [ ] Make the local server authoritative for gameplay state.
- [ ] Make the LAN build independent of production backend services.
- [ ] Maintain a reproducible APK build/install procedure.
- [ ] Test every milestone before moving to the next one.

---

# 1. REPOSITORY PREPARATION

## 1.1 Repository structure

Recommended structure:

```text
ROS_RE/
├── 01_apk/
├── 02_dex/
├── 03_native/
├── 04_assets/
├── 05_configs/
├── 06_notes/
├── 07_tools/
├── 08_build/
├── 09_server/
├── 10_protocol/
├── 11_tests/
├── 12_logs/
├── docs/
├── scripts/
├── server/
├── client/
├── PROGRESS.md
└── OFFLINE_LAN_REBUILD_MASTER_CHECKLIST.md
```

- [ ] Preserve original DEX files.
- [ ] Preserve APK hashes.
- [ ] Record Android package name.
- [ ] Record version/build number.
- [ ] Record ABI(s).
- [ ] Record minimum/target SDK.
- [ ] Record required permissions.
- [ ] Record native libraries.
- [ ] Record asset package names.
- [ ] Record configuration files.
- [ ] Record known server addresses.
- [ ] Record known ports.
- [ ] Record current milestone.

---

# 2. DEX INVENTORY

Inspect all available DEX files.

Current repository:
- `02_dex/classes.dex`
- `02_dex/classes2.dex`
- `02_dex/classes3.dex`

### 2.1 Search targets
- [ ] `MpayActivity`
- [ ] `MpayLoginCallback`
- [ ] `onFailure`
- [ ] `onLoginSuccess`
- [ ] `loginDone`
- [ ] `has_minor`
- [ ] `isFirstLogin`
- [ ] `minor_status`
- [ ] `Cancel login`
- [ ] `RESULT_CANCELED`
- [ ] `RESULT_OK`
- [ ] `finish`
- [ ] `setResult`
- [ ] `startActivityForResult`
- [ ] `j/d/d`
- [ ] `e/b/c`

Known investigation addresses:
- `0x3e0554`
- `0x3cc968`
- `0x3ff902`
- `0x3ff958`
- `0x3ff978`

### 2.2 DEX documentation

Create:
- `06_notes/DEX_MAP.md`
- `06_notes/LOGIN_FLOW_TRACE.md`
- `06_notes/CLASS_METHOD_INDEX.md`

For every important method record:

| Field | Value |
|---|---|
| **DEX** | `classes.dex` / `classes2.dex` / `classes3.dex` |
| **Class** | package/class |
| **Method** | method name/signature |
| **Address** | native/decompiled address if known |
| **Caller** | caller |
| **Callee** | callee |
| **State** | `FOUND` / `PARTIAL` / etc. |
| **Purpose** | explanation |
| **Evidence** | source/log/disassembly |
| **Dependency** | client/server/config/native |

---

# 3. G0 — PATCH / BOOT

**Goal:**
```text
APK
 ↓
Application startup
 ↓
Patch/config validation
 ↓
Server/config initialization
 ↓
Title/login flow
```

### 3.1 Boot
- [ ] APK installs.
- [ ] Application launches.
- [ ] No immediate crash.
- [ ] Native libraries load.
- [ ] Required assets exist.
- [ ] Configuration loads.
- [ ] Version information is readable.
- [ ] Patch/version check is understood.
- [ ] Startup logs are captured.

### 3.2 Patch system

Document:
- [ ] Patch version file.
- [ ] Patch manifest.
- [ ] Asset version.
- [ ] Client version.
- [ ] Configuration version.
- [ ] Download/update state.
- [ ] Local cache path.
- [ ] Validation state.
- [ ] Failure state.
- [ ] Retry state.

Known patch location:
- `/sdcard/Android/data/com.netease.chiji/files/netease/h45na/`

### 3.3 G0 acceptance
```text
BOOT → PATCH CHECK → CONFIG LOAD → SERVER/LOCAL CONFIG → TITLE
```
- [ ] Repeatable.
- [ ] No production backend required for LAN test build.
- [ ] Logs identify every transition.

---

# 4. G1 — LOCAL / TEST SESSION

**Goal:**
```text
TITLE
 ↓
LOCAL TEST SESSION
 ↓
SESSION CREATED
 ↓
GAME ENTRY
```

### 4.1 Session architecture

Define local equivalents for:
- `/session/create`
- `/session/<id>`
- `/session/refresh`
- `/session/logout`

*These are conceptual local APIs and must not impersonate production credentials.*

- [ ] Session creation.
- [ ] Session ID.
- [ ] Player ID.
- [ ] Protocol version.
- [ ] Client build.
- [ ] Server ID.
- [ ] Session expiration.
- [ ] Disconnect.
- [ ] Reconnect.
- [ ] Session cleanup.

### 4.2 Session state machine
```text
NO_SESSION → CREATING → ACTIVE → CONNECTED → DISCONNECTED → RECONNECTING → CLOSED
```
- [ ] Document every transition.
- [ ] Log transition reason.
- [ ] Test invalid session.
- [ ] Test disconnect.
- [ ] Test reconnect.

### 4.3 G1 acceptance
- [ ] Client reaches local/test session.
- [ ] Session ID appears in logs.
- [ ] Server recognizes client.
- [ ] Client can leave.
- [ ] Client can reconnect.

---

# 5. G2 — BASEAPP / GAME SESSION

**Goal:**
```text
LOCAL SESSION
 ↓
GAME SESSION
 ↓
GAME SERVER CONNECTION
```

Investigate/document:
- [ ] Loginapp equivalent.
- [ ] Baseapp equivalent.
- [ ] Game server endpoint.
- [ ] Port.
- [ ] Protocol.
- [ ] Handshake.
- [ ] Client version.
- [ ] Server version.
- [ ] Heartbeat.
- [ ] Timeout.
- [ ] Disconnect.
- [ ] Reconnect.
- [ ] Session ownership.

### 5.1 Handshake

Document:
```text
CLIENT HELLO → SERVER HELLO → VERSION CHECK → SESSION ACCEPT → PLAYER CONNECT
```
- [ ] Message structure.
- [ ] Serialization.
- [ ] Compression.
- [ ] Encryption if legitimately used by the local protocol.
- [ ] Error codes.
- [ ] Timeout behavior.

---

# 6. G3 — ROLE / CHARACTER SYSTEM

**Goal:**
```text
GAME SESSION
 ↓
PLAYER PROFILE
 ↓
CHARACTER LIST
 ↓
CHARACTER CREATE/SELECT
```

### 6.1 Character data

Define:
- `player_id`
- `character_id`
- `name`
- `gender/body`
- `face`
- `hair`
- `clothing`
- `accessories`
- `animation`
- `appearance`

Checklist:
- [ ] Character creation.
- [ ] Character selection.
- [ ] Character preview.
- [ ] Character save.
- [ ] Character load.
- [ ] Character delete if supported.
- [ ] Default character.
- [ ] Appearance persistence.

### 6.2 Persistence

Database tables:
- `players`
- `characters`
- `appearance`
- `inventory`
- `loadouts`
- `settings`
- `stats`

---

# 7. G4 — HALL

**Goal:**
```text
CHARACTER
 ↓
HALL
 ↓
PLAYER AVATAR
 ↓
HALL UI
```

### 7.1 Hall scene
- [ ] Hall environment.
- [ ] Player avatar.
- [ ] Camera.
- [ ] Movement.
- [ ] Collision.
- [ ] Lighting.
- [ ] Interactive objects.
- [ ] NPCs if applicable.
- [ ] Background effects.
- [ ] Audio.
- [ ] UI overlay.

### 7.2 Hall functions
- [ ] Profile.
- [ ] Character.
- [ ] Inventory.
- [ ] Weapons.
- [ ] Equipment.
- [ ] Cosmetics.
- [ ] Stats.
- [ ] Settings.
- [ ] Match/play.
- [ ] Squad/team.
- [ ] Map/mode.
- [ ] Ready state.

### 7.3 G4 acceptance
```text
LOGIN → CHARACTER → HALL → PLAYER AVATAR VISIBLE → UI WORKS → PLAY BUTTON WORKS
```

---

# 8. G5 — CHARACTER PRESENTATION
- [ ] Character model.
- [ ] Skeleton.
- [ ] Animations.
  - [ ] Idle.
  - [ ] Walk.
  - [ ] Run.
  - [ ] Sprint.
  - [ ] Jump.
  - [ ] Crouch.
  - [ ] Prone.
  - [ ] Weapon holding.
  - [ ] Weapon switching.
  - [ ] Hit reaction.
  - [ ] Death.
  - [ ] Vehicle animations.
- [ ] Animation state machine.

---

# 9. COMPLETE UI INVENTORY

Document every screen:

### Boot
- [ ] Splash.
- [ ] Loading.
- [ ] Title.
- [ ] Version.

### Account/session
- [ ] Local session.
- [ ] Profile.
- [ ] Character.

### Hall
- [ ] Play.
- [ ] Inventory.
- [ ] Weapons.
- [ ] Equipment.
- [ ] Cosmetics.
- [ ] Stats.
- [ ] Achievements.
- [ ] Settings.
- [ ] Map.
- [ ] Mode.
- [ ] Team.

### Matchmaking
- [ ] Match selection.
- [ ] Create room.
- [ ] Join room.
- [ ] Player list.
- [ ] Ready.
- [ ] Waiting.
- [ ] Countdown.
- [ ] Loading.

### Gameplay
- [ ] HUD.
- [ ] Health.
- [ ] Armor.
- [ ] Ammo.
- [ ] Weapon.
- [ ] Minimap/map.
- [ ] Compass.
- [ ] Teammates.
- [ ] Kill feed.
- [ ] Interaction.
- [ ] Vehicle HUD.
- [ ] Zone warning.

### End game
- [ ] Death.
- [ ] Spectator.
- [ ] Results.
- [ ] Stats.
- [ ] Return to hall.

---

# 10. LAN LOBBY / MATCHMAKING

**Target flow:**
```text
PLAY
 ↓
DISCOVER LOCAL SERVER
 ↓
CREATE/JOIN ROOM
 ↓
PLAYER LIST
 ↓
READY
 ↓
ALL READY
 ↓
COUNTDOWN
 ↓
LOAD MAP
```

### 10.1 Lobby
- [ ] Server discovery.
- [ ] Room creation.
- [ ] Room join.
- [ ] Room leave.
- [ ] Player list.
- [ ] Player names.
- [ ] Avatar.
- [ ] Team.
- [ ] Ready.
- [ ] Ping.
- [ ] Connection state.
- [ ] Host/server state.
- [ ] Map.
- [ ] Mode.
- [ ] Max players.

---

# 11. WAITING AREA
- [ ] Spawn points.
- [ ] Player visibility.
- [ ] Player names.
- [ ] Avatars.
- [ ] Movement.
- [ ] Collision.
- [ ] Ready state.
- [ ] Team state.
- [ ] Countdown.
- [ ] Map preview.
- [ ] Connection indicator.
- [ ] Server/player count.

**Target:**
```text
3 PLAYERS CONNECTED → ALL VISIBLE → ALL READY → COUNTDOWN → MATCH LOAD
```

---

# 12. GAME WORLD

### 12.1 World assets
- [ ] Terrain.
- [ ] Buildings.
- [ ] Roads.
- [ ] Bridges.
- [ ] Water.
- [ ] Trees.
- [ ] Rocks.
- [ ] Props.
- [ ] Collision.
- [ ] Navigation.
- [ ] Spawn points.
- [ ] Loot points.
- [ ] Zone boundaries.
- [ ] Map limits.

### 12.2 World streaming
- [ ] Distance-based loading.
- [ ] LOD.
- [ ] Frustum culling.
- [ ] Occlusion culling where practical.
- [ ] Asset streaming.
- [ ] Scene streaming.
- [ ] Memory budget.
- [ ] Object pooling.

---

# 13. PLAYER CONTROLLER

### Required:
- [ ] Walk.
- [ ] Run.
- [ ] Sprint.
- [ ] Jump.
- [ ] Crouch.
- [ ] Prone.
- [ ] Fall.
- [ ] Land.
- [ ] Interaction.
- [ ] Weapon switch.
- [ ] Aim.
- [ ] Fire.
- [ ] Reload.
- [ ] Vehicle enter.
- [ ] Vehicle exit.

### Optional depending on original implementation:
- [ ] Vault.
- [ ] Climb.
- [ ] Swim.
- [ ] Lean.

---

# 14. MOBILE CONTROLS
- [ ] Movement joystick.
- [ ] Camera drag.
- [ ] Fire.
- [ ] Aim.
- [ ] Reload.
- [ ] Jump.
- [ ] Crouch.
- [ ] Prone.
- [ ] Interact.
- [ ] Weapon switch.
- [ ] Inventory.
- [ ] Map.
- [ ] Vehicle enter/exit.
- [ ] Vehicle steering.
- [ ] Vehicle acceleration.
- [ ] Vehicle brake.
- [ ] Sensitivity.
- [ ] Button layout.
- [ ] Touch feedback.
- [ ] Controller support if desired.

---

# 15. WEAPON SYSTEM

Every weapon definition should include:
- `weapon_id`
- `name`
- `damage`
- `fire_rate`
- `magazine_size`
- `ammo_type`
- `reload_time`
- `recoil`
- `spread`
- `range`
- `projectile/hitscan`
- `attachments`
- `animations`
- `sounds`

### 15.1 Weapon states
```text
HOLSTERED → EQUIPPED → AIMING → FIRING → RELOADING → READY
```
- [ ] Equip.
- [ ] Unequip.
- [ ] Fire.
- [ ] Reload.
- [ ] Ammo.
- [ ] Recoil.
- [ ] Spread.
- [ ] Range.
- [ ] Damage falloff.
- [ ] Attachments.
- [ ] Animation.
- [ ] Audio.

---

# 16. COMBAT / DAMAGE

**Core pipeline:**
```text
INPUT → FIRE → HIT DETECTION → TARGET → BODY PART → BASE DAMAGE → ARMOR → HP → KNOCK/DEATH → KILL EVENT
```

### 16.1 Damage state
Track:
- `attacker`
- `victim`
- `weapon`
- `damage`
- `hit_location`
- `distance`
- `timestamp`
- `armor`
- `health`

### 16.2 Authority
Server should be authoritative for:
- [ ] Damage.
- [ ] Health.
- [ ] Death.
- [ ] Kill attribution.
- [ ] Loot ownership.
- [ ] Match state.

---

# 17. PROJECTILE / HIT DETECTION

Determine whether each weapon uses:
- Hitscan.
- Projectile.
- Hybrid.

Implement/document:
- [ ] Raycast.
- [ ] Projectile movement.
- [ ] Collision layer.
- [ ] Hitbox.
- [ ] Body-part collider.
- [ ] Penetration if supported.
- [ ] Range.
- [ ] Falloff.
- [ ] Impact effect.
- [ ] Hit marker.
- [ ] Damage event.

---

# 18. HEALTH / DEATH

**State machine:**
```text
ALIVE → DAMAGED → KNOCKED → DEAD → SPECTATOR → RESULT
```
- [ ] HP.
- [ ] Armor.
- [ ] Healing.
- [ ] Knock state.
- [ ] Revive if supported.
- [ ] Death animation.
- [ ] Kill attribution.
- [ ] Spectator.
- [ ] Result screen.

---

# 19. LOOT SYSTEM

### 19.1 Item definitions
- Item ID.
- Category.
- Rarity.
- Stack size.
- Capacity.
- Spawn rules.
- Pickup rules.
- Drop rules.
- Despawn rules.

Categories:
- Weapons.
- Ammo.
- Armor.
- Healing.
- Attachments.
- Equipment.
- Consumables.

### 19.2 Loot lifecycle
```text
SPAWN → AVAILABLE → PICKED UP → INVENTORY → DROPPED → DESPAWN/RESET
```

---

# 20. INVENTORY / LOADOUT
- [ ] Inventory slots.
- [ ] Equipment slots.
- [ ] Weapon slots.
- [ ] Ammo.
- [ ] Healing.
- [ ] Attachments.
- [ ] Pickup.
- [ ] Drop.
- [ ] Swap.
- [ ] Equip.
- [ ] Unequip.
- [ ] Stack.
- [ ] Capacity.
- [ ] Persistence.

---

# 21. VEHICLE SYSTEM

### 21.1 Vehicle definition
- `vehicle_id`
- `model`
- `seats`
- `driver_seat`
- `passenger_seats`
- `max_speed`
- `acceleration`
- `braking`
- `steering`
- `suspension`
- `collision`
- `hp`
- `fuel`

### 21.2 Vehicle lifecycle
- [ ] Spawn.
- [ ] Enter.
- [ ] Exit.
- [ ] Seat switch.
- [ ] Driver.
- [ ] Passenger.
- [ ] Camera.
- [ ] HUD.
- [ ] Movement.
- [ ] Collision.
- [ ] Damage.
- [ ] Destruction.
- [ ] Despawn.

### 21.3 Vehicle networking
Synchronize:
- [ ] Position.
- [ ] Rotation.
- [ ] Velocity.
- [ ] Driver.
- [ ] Seat state.
- [ ] HP.
- [ ] Vehicle action.

---

# 22. ZONE / BATTLE ROYALE SYSTEM
- [ ] Initial zone.
- [ ] Random center.
- [ ] Shrink phases.
- [ ] Timers.
- [ ] Warning.
- [ ] Boundary.
- [ ] Outside-zone damage.
- [ ] Final zone.
- [ ] End-game condition.

*Server authoritative.*

---

# 23. MATCH STATE MACHINE

Recommended:
```text
LOBBY → PREPARING → LOADING → WAITING → COUNTDOWN → IN_MATCH → FINAL_ZONE → MATCH_END → RESULT → HALL
```

For every state document:
- Entry condition.
- Exit condition.
- Timeout.
- Network message.
- UI.
- Persistence.
- Failure handling.

---

# 24. NETWORKING ARCHITECTURE

**Target:**
```text
PHONE 1 ─┐
PHONE 2 ─┼── LAN ── LAPTOP SERVER
PHONE 3 ─┘
```

**Recommended authority:**
```text
CLIENT
  ↓ input
SERVER
  ↓ validates/simulates
SERVER WORLD STATE
  ↓ snapshots/events
CLIENTS
```

### 24.1 Client responsibilities
- [ ] Input.
- [ ] Camera.
- [ ] UI.
- [ ] Local prediction where needed.
- [ ] Interpolation.
- [ ] Rendering.
- [ ] Effects.
- [ ] Audio.

### 24.2 Server responsibilities
- [ ] Player state.
- [ ] Movement validation.
- [ ] Damage.
- [ ] Health.
- [ ] Death.
- [ ] Loot.
- [ ] Vehicles.
- [ ] Zone.
- [ ] Match state.
- [ ] Results.
- [ ] Persistence.

---

# 25. NETWORK SYNCHRONIZATION

Player state:
- `position`
- `rotation`
- `velocity`
- `movement`
- `animation`
- `health`
- `armor`
- `weapon`
- `ammo`
- `action`

Implement:
- [ ] Snapshots.
- [ ] Interpolation.
- [ ] Client prediction.
- [ ] Server reconciliation.
- [ ] Delta updates.
- [ ] Event messages.
- [ ] Relevance filtering.
- [ ] Interest management.

*Avoid sending every visual effect every frame.*

---

# 26. LOCAL SERVER

Recommended server layout:
```text
server/
├── gateway/
├── session/
├── lobby/
├── match/
├── world/
├── combat/
├── inventory/
├── vehicles/
├── zone/
├── persistence/
└── protocol/
```

### 26.1 Database
SQLite is suitable for the first local implementation.

Tables:
- `players`
- `characters`
- `appearance`
- `inventory`
- `weapons`
- `matches`
- `stats`
- `rooms`
- `settings`

### 26.2 Server requirements
- [ ] Startup command.
- [ ] Config file.
- [ ] LAN bind address.
- [ ] Port configuration.
- [ ] Health endpoint.
- [ ] Logging.
- [ ] Room management.
- [ ] Match management.
- [ ] Database.
- [ ] Graceful shutdown.
- [ ] Backup.
- [ ] Recovery.

---

# 27. LAN DISCOVERY

Support at least one reliable method:
- Manual server IP.
- Local discovery.
- Server browser.
- QR/config import if useful.

Display:
- `SERVER NAME`
- `IP`
- `PORT`
- `PING`
- `PLAYERS`
- `VERSION`
- `STATUS`

Test:
- [ ] Join.
- [ ] Leave.
- [ ] Reconnect.
- [ ] Server restart.
- [ ] Invalid IP.
- [ ] Wrong port.
- [ ] Version mismatch.

---

# 28. MATCH MANAGEMENT

Room lifecycle:
```text
ROOM_CREATED → JOINING → READY → COUNTDOWN → STARTING → RUNNING → FINISHED → CLOSED
```
- [ ] Minimum player count.
- [ ] Maximum player count.
- [ ] Ready requirement.
- [ ] Countdown.
- [ ] Map selection.
- [ ] Mode selection.
- [ ] Spawn allocation.
- [ ] Match seed.
- [ ] Match ID.

---

# 29. STATS / RESULTS

Track:
- `kills`
- `deaths`
- `damage`
- `headshots`
- `shots`
- `hits`
- `accuracy`
- `survival_time`
- `placement`
- `distance`
- `weapon_usage`

Flow:
```text
MATCH END → RESULT → SAVE STATS → UPDATE PROFILE → RETURN HALL
```

---

# 30. AUDIO

Effects:
- [ ] Weapon fire.
- [ ] Reload.
- [ ] Footsteps.
- [ ] Jump.
- [ ] Landing.
- [ ] Hit.
- [ ] Damage.
- [ ] Death.
- [ ] Vehicle engine.
- [ ] Vehicle collision.
- [ ] Explosion.
- [ ] Ambient.
- [ ] UI.
- [ ] Zone warning.
- [ ] Music.

Mobile optimization:
- [ ] Compress audio.
- [ ] Stream long tracks.
- [ ] Limit simultaneous sources.
- [ ] Pool frequently used sounds.
- [ ] Avoid unnecessary 3D audio sources.

---

# 31. GRAPHICS / RENDERING

Inventory:
- [ ] Materials.
- [ ] Shaders.
- [ ] Textures.
- [ ] Meshes.
- [ ] Particles.
- [ ] Lighting.
- [ ] Shadows.
- [ ] Post-processing.
- [ ] UI.
- [ ] Animation.

Optimization:
- [ ] LOD.
- [ ] Culling.
- [ ] Batching.
- [ ] Instancing.
- [ ] Texture compression.
- [ ] Shader simplification.
- [ ] Reduced transparency.
- [ ] Reduced overdraw.
- [ ] Reduced particle count.
- [ ] Dynamic resolution if supported.

---

# 32. HIGH-FPS MOBILE OPTIMIZATION

### 32.1 CPU
- [ ] Reduce unnecessary per-frame updates.
- [ ] Avoid per-frame allocations.
- [ ] Pool objects.
- [ ] Reduce physics objects.
- [ ] Reduce script overhead.
- [ ] Reduce AI update frequency.
- [ ] Batch network operations.
- [ ] Move heavy work away from render loop.

### 32.2 GPU
- [ ] LOD.
- [ ] Texture compression.
- [ ] Simpler shaders.
- [ ] Reduce dynamic shadows.
- [ ] Reduce particles.
- [ ] Reduce post-processing.
- [ ] Reduce transparency.
- [ ] Reduce overdraw.

### 32.3 Memory
- [ ] Stream assets.
- [ ] Compress textures.
- [ ] Unload unused scenes.
- [ ] Avoid duplicate assets.
- [ ] Set memory budgets.
- [ ] Monitor allocations.
- [ ] Monitor native heap.
- [ ] Monitor graphics memory.

---

# 33. MOBILE PERFORMANCE PRESETS

### Competitive
- Highest sustainable FPS.
- Low shadows.
- Low effects.
- Low post-processing.
- Medium textures.
- Aggressive LOD.
- Reduced particles.

### Balanced
- Stable FPS.
- Medium textures.
- Medium effects.
- Moderate shadows.

### Quality
- Higher textures.
- Higher effects.
- Higher shadows where hardware allows.
- Lower FPS priority.

---

# 34. FPS TARGETS

Test:
- 30 FPS
- 45 FPS
- 60 FPS
- 90 FPS
- 120 FPS

*Do not force an FPS target that the device cannot sustain.*

Measure:
- Average FPS.
- 1% low FPS.
- Frame time.
- CPU time.
- GPU time.
- Memory.
- Temperature/thermal behavior.
- Network latency.
- Frame-time spikes.

---

# 35. LAPTOP SERVER OPTIMIZATION

Target machine:
- Intel Core i5 12th Gen
- RTX 3050 Ti
- 16 GB RAM target

Recommended:
- [ ] Prefer dedicated/headless server.
- [ ] Keep GPU available for client testing.
- [ ] Prioritize CPU.
- [ ] Prioritize LAN/network stability.
- [ ] Use SQLite initially.
- [ ] Batch persistence writes.
- [ ] Rotate logs.
- [ ] Monitor CPU/RAM.
- [ ] Avoid unnecessary graphical server workloads.
- [ ] Keep server tick rate configurable.

---

# 36. THREE-DEVICE TEST PLAN

### Test 1 — One device: `SERVER + PHONE 1`
Verify:
- [ ] Boot.
- [ ] Session.
- [ ] Lobby.
- [ ] Map.
- [ ] Spawn.
- [ ] Movement.
- [ ] Combat.
- [ ] Result.

### Test 2 — Two devices: `SERVER + PHONE 1 + PHONE 2`
Verify:
- [ ] Discovery.
- [ ] Lobby.
- [ ] Player visibility.
- [ ] Movement synchronization.
- [ ] Shooting.
- [ ] Damage.
- [ ] Death.
- [ ] Results.

### Test 3 — Three devices: `SERVER + PHONE 1 + PHONE 2 + PHONE 3`
Verify:
- [ ] All join.
- [ ] All visible.
- [ ] Movement.
- [ ] Combat.
- [ ] Damage.
- [ ] Loot.
- [ ] Vehicles.
- [ ] Zone.
- [ ] Death.
- [ ] Result.
- [ ] Return to hall.
- [ ] Persistence.

---

# 37. NETWORK TEST MATRIX

| Test | Expected |
|---|---|
| **Join** | Client joins room |
| **Leave** | Client removed cleanly |
| **Disconnect** | Server detects timeout |
| **Reconnect** | Client can recover |
| **Movement** | Other players see movement |
| **Shooting** | Server receives fire |
| **Damage** | Server applies damage |
| **Death** | Correct player dies |
| **Vehicle** | Vehicle state syncs |
| **Loot** | Pickup is authoritative |
| **Zone** | All clients see same zone |
| **Result** | Same result state |
| **Persistence** | Stats saved |

---

# 38. DEBUGGING INFRASTRUCTURE

Use categories:
`BOOT`, `SESSION`, `LOBBY`, `MATCH`, `PLAYER`, `WORLD`, `WEAPON`, `DAMAGE`, `VEHICLE`, `LOOT`, `ZONE`, `NETWORK`, `RESULT`

Every important log should contain:
- `timestamp`
- `player_id`
- `match_id`
- `event`
- `state`
- `server/client`
- `data`

Examples:
```text
[SESSION] created player=...
[LOBBY] joined room=...
[MATCH] started match=...
[PLAYER] spawned player=...
[WEAPON] fired weapon=...
[DAMAGE] attacker=... victim=... amount=...
[VEHICLE] entered vehicle=...
[ZONE] phase=...
[RESULT] placement=...
```

---

# 39. AUTOMATED VALIDATION

Automate:
- [ ] Server startup.
- [ ] Port availability.
- [ ] LAN discovery.
- [ ] Room creation.
- [ ] Room join.
- [ ] Player count.
- [ ] Ready state.
- [ ] Match start.
- [ ] Spawn.
- [ ] Movement.
- [ ] Damage.
- [ ] Death.
- [ ] Result.
- [ ] Persistence.

---

# 40. APK BUILD PIPELINE

Target pipeline:
```text
SOURCE → DECODE/BUILD → RESOURCE VALIDATION → DEX VALIDATION → NATIVE LIB VALIDATION → PACKAGE → SIGN → INSTALL → SMOKE TEST
```

Checklist:
- [ ] Build tools documented.
- [ ] SDK version documented.
- [ ] JDK version documented.
- [ ] APK signing key documented.
- [ ] Build reproducible.
- [ ] Package name unchanged where required.
- [ ] ABI correct.
- [ ] Native libraries included.
- [ ] Assets included.
- [ ] DEX count validated.
- [ ] Manifest validated.
- [ ] Permissions validated.

---

# 41. DEVICE INSTALLATION

For test devices:
- [ ] Enable developer options.
- [ ] Enable USB debugging.
- [ ] Confirm ADB connection.
- [ ] Install test APK.
- [ ] Clear old app state when necessary.
- [ ] Push test assets/config.
- [ ] Configure local server address.
- [ ] Confirm all devices use same protocol version.
- [ ] Confirm all devices use same map/config version.

Basic ADB workflow:
```bash
adb devices
adb install -r app.apk
adb shell pm list packages
adb shell dumpsys package <package>
adb logcat
```

For an already-installed APK, identify its APK path before pulling it:
```bash
adb shell pm path <package>
adb pull <apk-path>
```

*If the app uses split APKs, preserve and install all required splits rather than assuming a single APK is sufficient.*

---

# 42. COMPLETE GAMEPLAY ACCEPTANCE TEST

The complete target flow is:
```text
BOOT → TITLE → PLAY → LOCAL SESSION → CHARACTER → HALL → MATCH → LAN ROOM → 3 PLAYERS → READY → WAITING → COUNTDOWN → MAP → SPAWN → MOVE → LOOT → WEAPON → COMBAT → DAMAGE → VEHICLE → ZONE → DEATH → RESULT → STATS → HALL
```

Every transition must have:
- Client behavior.
- Server behavior.
- Network message/state.
- UI state.
- Persistence behavior.
- Failure handling.
- Logs.

---

# 43. REQUIRED DOCUMENTATION FILES

### Docs (`docs/`):
- [ ] `docs/ARCHITECTURE.md`
- [ ] `docs/CLIENT_FLOW.md`
- [ ] `docs/SERVER_FLOW.md`
- [ ] `docs/NETWORK_PROTOCOL.md`
- [ ] `docs/GAME_STATE_MACHINE.md`
- [ ] `docs/WORLD_SYSTEM.md`
- [ ] `docs/COMBAT_SYSTEM.md`
- [ ] `docs/DAMAGE_SYSTEM.md`
- [ ] `docs/WEAPON_SYSTEM.md`
- [ ] `docs/VEHICLE_SYSTEM.md`
- [ ] `docs/LOOT_SYSTEM.md`
- [ ] `docs/INVENTORY_SYSTEM.md`
- [ ] `docs/CHARACTER_SYSTEM.md`
- [ ] `docs/HALL_SYSTEM.md`
- [ ] `docs/LOBBY_SYSTEM.md`
- [ ] `docs/MATCH_SYSTEM.md`
- [ ] `docs/UI_INVENTORY.md`
- [ ] `docs/MOBILE_OPTIMIZATION.md`
- [ ] `docs/PERFORMANCE_TESTS.md`
- [ ] `docs/TROUBLESHOOTING.md`

### Research notes (`06_notes/`):
- [ ] `06_notes/DEX_MAP.md`
- [ ] `06_notes/LOGIN_FLOW_TRACE.md`
- [ ] `06_notes/CLASS_METHOD_INDEX.md`
- [ ] `06_notes/ASSET_MAP.md`
- [ ] `06_notes/CONFIG_MAP.md`
- [ ] `06_notes/NATIVE_LIBRARY_MAP.md`
- [ ] `06_notes/NETWORK_FINDINGS.md`
- [ ] `06_notes/STATE_MACHINE.md`

### Root:
- [x] `OFFLINE_LAN_REBUILD_MASTER_CHECKLIST.md`

---

# 44. ANTIGRAVITY INVESTIGATION PROMPT

Use this prompt as the investigation brief:

> You are auditing the ROS_RE repository for an offline/LAN rebuild.  
> **DO NOT** modify implementation code yet.  
> First inspect the entire repository and produce a complete dependency map.  
>  
> Inspect:
> 1. classes.dex
> 2. classes2.dex
> 3. classes3.dex
> 4. native libraries
> 5. assets
> 6. configuration files
> 7. manifests/resources
> 8. existing MITM/server research
> 9. existing progress notes
> 10. build/install scripts
>  
> Map:
> - **A. BOOT:** Application startup, Patch/config initialization, Server configuration, Title flow
> - **B. SESSION:** Local/test session flow, Session states, Login callbacks, Disconnect/reconnect, Server dependencies
> - **C. GAME SESSION:** loginapp/baseapp equivalents, handshake, protocol, heartbeat, server address/port
> - **D. CHARACTER:** Player profile, Character list, Character creation, Appearance, Persistence
> - **E. HALL:** Scene, Player avatar, Camera, UI, Inventory, Equipment, Match entry
> - **F. LOBBY:** Room creation, Room join, Player list, Ready, Countdown
> - **G. BATTLE:** Map, Spawn, Player controller, Weapons, Projectile/hitscan, Damage, Health, Death, Loot, Inventory, Vehicles, Zone, Results
> - **H. NETWORK:** Client messages, Server messages, State synchronization, Snapshots, Events, Timeouts, Reconnect
> - **I. PERFORMANCE:** Rendering, CPU, GPU, Memory, Asset streaming, LOD, Culling, Network bandwidth
>  
> For every item classify: `FOUND`, `PARTIAL`, `BROKEN`, `MISSING`, `SERVER-DEPENDENT`, `UNKNOWN`  
>  
> For every important class/method provide: DEX, class, method, signature, address if known, callers, callees, state transition, evidence, dependency.  
>  
> Pay special attention to: `MpayActivity`, `MpayLoginCallback`, `onFailure`, `onLoginSuccess`, `loginDone`, `has_minor`, `isFirstLogin`, `minor_status`.  
>  
> *Do not implement or describe methods for defeating age/consent verification, forging credentials/session tokens, or bypassing security controls.*  
> *Instead identify legitimate local/test-session paths and the server-side functionality required to reproduce the game flow in an authorized LAN environment.*  
>  
> Write:  
> - `06_notes/DEX_MAP.md`  
> - `06_notes/LOGIN_FLOW_TRACE.md`  
> - `06_notes/CLASS_METHOD_INDEX.md`  
> - `06_notes/ASSET_MAP.md`  
> - `06_notes/CONFIG_MAP.md`  
> - `06_notes/NETWORK_FINDINGS.md`  
> - `06_notes/STATE_MACHINE.md`  
>  
> At the end produce:
> 1. Dependency graph
> 2. Client state machine
> 3. Server state machine
> 4. Network message inventory
> 5. Gameplay subsystem inventory
> 6. Missing dependency list
> 7. Recommended implementation order
>  
> *Do not start vehicles, cosmetics, or FPS optimization until the dependency map is complete.*

---

# 45. RECOMMENDED IMPLEMENTATION ORDER

### Phase A — Foundation
- [ ] Backup.
- [ ] DEX inventory.
- [ ] Asset inventory.
- [ ] Config inventory.
- [ ] Native library inventory.
- [ ] Build pipeline.
- [ ] Logging.
- [ ] Debug tools.

### Phase B — Client Flow
- [ ] Boot.
- [ ] Patch/config.
- [ ] Legitimate local/test session.
- [ ] Game session.
- [ ] Role/character.
- [ ] Hall.
- [ ] UI.

### Phase C — LAN
- [ ] Local server.
- [ ] LAN discovery.
- [ ] Session.
- [ ] Lobby.
- [ ] Waiting area.
- [ ] Ready.
- [ ] Countdown.
- [ ] Match start.

### Phase D — Gameplay
- [ ] World.
- [ ] Player controller.
- [ ] Mobile controls.
- [ ] Weapons.
- [ ] Hit detection.
- [ ] Damage.
- [ ] Health/death.
- [ ] Loot.
- [ ] Inventory.
- [ ] Vehicles.
- [ ] Zone.
- [ ] Match results.

### Phase E — Persistence
- [ ] Character persistence.
- [ ] Inventory persistence.
- [ ] Stats.
- [ ] Match history.
- [ ] Settings.
- [ ] Database backup/recovery.

### Phase F — Optimization
- [ ] CPU profiling.
- [ ] GPU profiling.
- [ ] Memory profiling.
- [ ] Network profiling.
- [ ] LOD.
- [ ] Culling.
- [ ] Texture optimization.
- [ ] Shader optimization.
- [ ] Effects optimization.
- [ ] FPS presets.

### Phase G — Testing
- [ ] One device.
- [ ] Two devices.
- [ ] Three devices.
- [ ] Disconnect/reconnect.
- [ ] Long session.
- [ ] Match completion.
- [ ] Persistence.
- [ ] Server restart.
- [ ] Client restart.
- [ ] Performance soak test.

---

# 46. CURRENT PRIORITY

Do not attempt to build the entire game at once.

Current sequence:
```text
G0 PATCH
 ↓
G1 LOCAL/TEST SESSION
 ↓
G2 GAME SESSION
 ↓
G3 ROLE/CHARACTER
 ↓
G4 HALL
 ↓
G5 CHARACTER PRESENTATION
 ↓
G6 BATTLE
 ↓
LAN 3-PLAYER
 ↓
FULL GAMEPLAY
 ↓
PERSISTENCE
 ↓
OPTIMIZATION
```

The first objective is to make the client/server state machine reliable.  
After that, expand gameplay systems one subsystem at a time.

---

# 47. DEFINITION OF DONE

The project is considered ready for the first complete LAN milestone when:

- [ ] APK builds reproducibly.
- [ ] APK installs on all 3 test devices.
- [ ] Client boots reliably.
- [ ] Local/test session works.
- [ ] Character can be created/selected.
- [ ] Hall loads.
- [ ] Local server starts reliably.
- [ ] All 3 devices discover/connect to the server.
- [ ] All 3 players appear in the room.
- [ ] Ready state works.
- [ ] Countdown works.
- [ ] Map loads.
- [ ] All players spawn.
- [ ] Movement synchronizes.
- [ ] Weapons work.
- [ ] Hit detection works.
- [ ] Damage works.
- [ ] Death works.
- [ ] Loot works.
- [ ] Inventory works.
- [ ] Vehicles work if included in the current milestone.
- [ ] Zone works.
- [ ] Match ends correctly.
- [ ] Results are displayed.
- [ ] Stats are saved.
- [ ] Players can return to hall.
- [ ] Reconnect behavior works.
- [ ] Server restart is recoverable.
- [ ] No production backend is required for the LAN test environment.
- [ ] Mobile FPS has been measured.
- [ ] Memory usage has been measured.
- [ ] Network latency has been measured.
- [ ] Long-session stability has been tested.

---

# 48. FINAL OBJECTIVE

### Final target architecture:

```text
                    ┌──────────────────────┐
                    │      LAPTOP          │
                    │  Local Game Server   │
                    │                      │
                    │ Gateway              │
                    │ Session              │
                    │ Lobby                │
                    │ Match                │
                    │ World                │
                    │ Combat               │
                    │ Inventory            │
                    │ Vehicles             │
                    │ Zone                 │
                    │ Persistence          │
                    │ SQLite               │
                    └──────────┬───────────┘
                               │
                         LOCAL LAN
                               │
              ┌────────────────┼────────────────┐
              │                │                │
        ┌─────▼─────┐    ┌─────▼─────┐    ┌─────▼─────┐
        │  PHONE 1  │    │  PHONE 2  │    │  PHONE 3  │
        │   CLIENT  │    │   CLIENT  │    │   CLIENT  │
        └───────────┘    └───────────┘    └───────────┘
```

### Complete gameplay target:
```text
BOOT → TITLE → LOCAL SESSION → CHARACTER → HALL → LAN ROOM → 3 PLAYERS → READY → WAITING → COUNTDOWN → MAP → SPAWN → MOVE → LOOT → WEAPON → COMBAT → DAMAGE → VEHICLE → ZONE → DEATH → RESULT → STATS → HALL
```

---

### Final engineering principle

Build the smallest working vertical slice first:

```text
1 PLAYER → LOCAL SERVER → HALL → MAP → MOVE → SHOOT → DAMAGE → DEATH → RESULT
```

Then:
```text
2 PLAYERS → SYNC → COMBAT
```

Then:
```text
3 PLAYERS → FULL LAN MATCH
```

Only after that:
```text
VEHICLES → LOOT EXPANSION → ADVANCED UI → PERSISTENCE EXPANSION → GRAPHICS OPTIMIZATION → HIGH-FPS PRESETS
```
