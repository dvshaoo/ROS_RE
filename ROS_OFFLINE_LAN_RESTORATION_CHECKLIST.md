# Rules of Survival Offline/LAN Restoration Checklist

## Scope

This document is a requirements and evidence checklist for an authorized private offline/LAN restoration or compatible local implementation of the exact client version:

- Client version: `1.610377.506841`
- Version code: `1117219`
- Host: Acer Nitro 5, Intel i5 12th gen, RTX 3050 Ti
- Clients: Android phones/laptops on the same LAN

Bypass production authentication, DRM, age/consent protection, or security controls. Use only owned/authorized client assets, traces, backups, and server resources.

## Current Known Blockers

1. Startup fails at `Failed to retrieve patches`.
2. Local patch manifest and resource contract must be reproduced from evidence.
3. A local authorized account/consent flow is needed.
4. BigWorld/Mercury `loginapp` and BaseApp session are not yet proven.
5. Role list, hall, room creation, battle, and multi-client synchronization are not yet proven.
6. Original official BigWorld server binaries/configuration have not been found.

## Evidence Rules: No Guessing

Every feature must be classified:

- **PROVEN**: observed in a reproducible trace or test.
- **INFERRED**: supported by strong client evidence but not yet reproduced.
- **UNKNOWN**: insufficient evidence.
- **MISSING**: required server/resource component is unavailable.

For every endpoint, packet, UI action, or file, record:

```text
Feature:
Source file/trace/screenshot:
Client version:
Endpoint or protocol:
Request/input:
Expected response/output:
State transition:
Required assets:
Status: PROVEN | INFERRED | UNKNOWN | MISSING
Confidence:
Reproduction test:
Next safe experiment:
```

## System Inventory

### 1. Startup and Client Bootstrap

- APK/OBB/resource validation
- Exact version/build checks
- Patch manifest retrieval
- Patch download and integrity verification
- Remote configuration
- Maintenance/server status
- CDN/resource URLs
- TLS/certificate behavior
- Crash and error handling
- Offline fallback behavior

### 2. Account and Access

- Local authorized account creation/login
- Guest account
- Session/token lifecycle
- Logout and reconnect
- Private-LAN consent/age flow
- Region and language settings
- Maintenance and error responses

### 3. BigWorld/Mercury Networking

- `loginapp`
- Mercury packet framing
- Authentication/key exchange
- Encryption and serialization
- `baseapp`
- `cellapp`
- Entity creation and method calls
- Heartbeat/ping
- Reconnect/disconnect
- Compression
- Server tick and time synchronization

### 4. Hall and Lobby

- Server list
- Lobby entrance
- Player profile
- Role/character list
- Nickname/avatar
- Friends
- Team/squad
- Chat/mail if required
- Room creation and joining
- Matchmaking
- Invitations
- Ready/start/cancel
- Loading screen
- Return-to-hall flow

### 5. Player and Account Data

- Inventory
- Currency
- Weapons and items
- Skins/cosmetics
- Crates/rewards
- Achievements
- Missions/tasks
- Level/experience
- Statistics
- Presets/loadouts
- Daily rewards
- Persistence and save/load

### 6. Battle and Gameplay

- Map/space loading
- Spawn/respawn
- Movement
- Camera
- Aiming/shooting
- Reload
- Damage/armor/health
- Knockdown/death
- Revive
- Loot and pickups
- Safe-zone behavior
- Match timer
- Win/loss state
- Spectating
- Results/rewards

### 7. Vehicle System

- Vehicle definitions and assets
- Vehicle spawning
- Enter/exit
- Seats and passengers
- Driving physics
- Acceleration/braking/steering
- Fuel/durability
- Vehicle damage
- Vehicle weapons
- Collision
- Network state synchronization
- Vehicle loot/repair

### 8. UI and Presentation

- Startup and patch UI
- Login UI
- Server selection
- Lobby/hall
- Character screen
- Inventory
- Shop
- Missions
- Settings
- Controls
- Matchmaking
- Team UI
- Map/minimap
- HUD
- Health/ammo/vehicle indicators
- Kill feed
- Notifications
- Loading screens
- Results screens
- Localization and fonts
- Audio/music
- Animations/VFX

### 9. Services and Operations

- Profile database
- Account/session persistence
- Game configuration
- Logging
- Analytics/telemetry where needed by the client
- Admin/test tools
- Backups
- LAN discovery or fixed host address
- Multiple-client testing
- Version compatibility

## Recommended Build Order

### Phase 0: Preserve and Inventory

- Do not edit original APK, OBB, dumps, or archives.
- Record SHA-256 hashes.
- Record exact client version and resource hashes.
- Inventory repository, backups, emulator dumps, and archives.
- Search specifically for `loginapp.pubkey`, matching private/config files, `loginapp`, `baseapp`, `cellapp`, `dbapp`, and server packages.

### Phase 1: Evidence Map

- Capture DNS and HTTP(S) requests in an authorized test environment.
- Record patch endpoint, request headers/body, response status, manifest format, filenames, sizes, and hashes.
- Extract client strings, entity definitions, schemas, and screen names.
- Map each UI screen to the server state it requires.
- Never infer a protocol field only from a name; confirm with a trace or client code reference.

### Phase 2: Startup Vertical Slice

Target:

```text
start app
→ local patch/config response
→ validate existing local resources
→ local authorized login
→ reach hall
```

Do not proceed until this is reproducible with one clean client.

### Phase 3: Minimal Multiplayer Vertical Slice

Target:

```text
hall
→ create room
→ second client joins
→ load one map
→ spawn two players
→ synchronize movement
→ end match
→ return to hall
```

This proves the core architecture before implementing every menu or item.

### Phase 4: Layered Local Services

```text
patch/config service
local auth/session service
BigWorld loginapp adapter
BaseApp/session service
Hall/lobby service
Cell/battle service
Profile/database service
LAN gateway/discovery
```

Keep service contracts explicit and testable. Do not combine all behavior into one untraceable process.

### Phase 5: Feature Expansion

Implement in this order:

1. Player movement and state synchronization
2. Shooting, damage, health, knockdown, death
3. Loot and inventory
4. Match lifecycle and rewards
5. Vehicle enter/exit
6. Vehicle movement and passengers
7. Vehicle damage and synchronization
8. Profiles, progression, missions, cosmetics
9. Remaining lobby and UI systems

## Acceptance Gates

### G1: Startup

- Patch/config request is answered by the local service.
- Client accepts the response without modifying security checks.
- Existing resources validate correctly.

### G2: Login and BaseApp

- One client completes the authorized local login flow.
- Mercury framing and session messages are documented.
- Client reaches a verified game session.

### G3: Hall

- Role/profile data loads.
- Client can enter and leave the hall.

### G4: Two-Client Room

- Two clients connect through LAN.
- Both see the same room and ready state.

### G5: Playable Map

- Both clients load the same map.
- Spawn, movement, and disconnect behavior are reproducible.

### G6: Gameplay

- Combat, loot, match end, results, and return-to-hall work.

### G7: Vehicles

- Spawn, enter/exit, driving, passengers, damage, and synchronization work.

## Test Matrix

| Test | One client | Two clients | Reproducible | Evidence |
|---|---:|---:|---:|---|
| Startup/patch |  |  |  |  |
| Local login |  |  |  |  |
| Hall entry |  |  |  |  |
| Room create/join |  |  |  |  |
| Map load |  |  |  |  |
| Movement sync |  |  |  |  |
| Combat |  |  |  |  |
| Loot |  |  |  |  |
| Vehicle enter/exit |  |  |  |  |
| Vehicle sync |  |  |  |  |
| Match end |  |  |  |  |
| Return to hall |  |  |  |  |

## Immediate Next Actions

1. Resolve and document the exact patch request causing `Failed to retrieve patches`.
2. Verify whether all referenced patch/resource files exist locally.
3. Produce a read-only server-resource inventory with hashes and paths.
4. Determine whether an original authorized BigWorld server package exists.
5. If not found, document the minimum compatible local service contract instead of guessing.
6. Implement and test only the G1 startup vertical slice.
7. Move to G2 only after G1 is repeatable.

## Definition of Done

The project is complete only when the exact client can start from local resources, authenticate through an authorized private-LAN flow, enter the hall, allow multiple clients to join a room, load a map, play a synchronized match including vehicles, save results, and return to the hall—with every behavior backed by reproducible evidence and tests.
