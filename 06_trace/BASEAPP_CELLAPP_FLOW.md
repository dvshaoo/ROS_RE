# ROS v1117219 — BaseApp to CellApp Entity & Session Flow

## 1. Overview & Architectural Hierarchy

The BigWorld Technology architecture divides server-side simulation into two distinct server tiers:
1. **BaseApp**: Authoritative over persistent data, client network proxying, database storage, account verification, and lobby features.
2. **CellApp**: Authoritative over real-time spatial simulation, 3D physics, line-of-sight, projectiles, combat damage, vehicle movement, and Area of Interest (AOI) entity streaming.

In Rules of Survival (`com.netease.chiji`, build `v1117219`), the client interacts with three primary player entities during its lifecycle:
1. **`Account` (`Account.def.xml`)**: Ephemeral gateway entity on BaseApp for client handshake and authentication.
2. **`Athlete` (`Athlete.def.xml`)**: Persistent Lobby entity on BaseApp managing friends, teams, chat, mall, ranks, and user appearance.
3. **`Avatar` (`Avatar.def.xml`)**: Combat unit entity in `BattleGroundSpace` on CellApp managing health, weapons, driving, and battle royale survival.

```text
       ┌─────────────────────────────────────────────────────────────┐
       │                   BigWorld Server Cluster                   │
       │                                                             │
       │   ┌──────────────────┐               ┌──────────────────┐   │
       │   │     BaseApp      │               │     CellApp      │   │
       │   │                  │               │                  │   │
       │   │  Account Entity  │               │                  │   │
       │   │        │         │               │                  │   │
       │   │        ▼         │               │                  │   │
       │   │  Athlete Entity  │               │                  │   │
       │   │     (Lobby)      │               │                  │   │
       │   │        │         │               │                  │   │
       │   │        ▼         │   allocate    │BattleGroundSpace │   │
       │   │  Matchmaking ────┼──────────────►│        │         │   │
       │   │  (iRosMatch)     │     Space     │        ▼         │   │
       │   │                  │               │  Avatar Entity   │   │
       │   │                  │               │  (Combat Unit)   │   │
       │   └────────┬─────────┘               └────────┬─────────┘   │
       │            │                                  │             │
       └────────────┼──────────────────────────────────┼─────────────┘
                    │                                  │
                    │   Mercury UDP External Channel   │
                    │   (Proxy Message / Entity RPC)   │
                    ▼                                  ▼
       ┌─────────────────────────────────────────────────────────────┐
       │                 Rules of Survival Client                    │
       │                                                             │
       │   ServerConnection::createBasePlayer -> Account (Handshake) │
       │   ServerConnection::createBasePlayer -> Athlete (Lobby/Hall)│
       │   ServerConnection::createCellPlayer -> Avatar (Battlefield)│
       └─────────────────────────────────────────────────────────────┘
```

---

## 2. Stage 1: Account Entity Handshake (`Account.def.xml`)

### 2.1 Creation
- **Trigger**: BaseApp accepts `BaseAppLoginRequest`
- **Native Call**: `ServerConnection::createBasePlayer(entityId, stream)`
- **Entity Type**: `Account` (Type index resolved via `entities_TABLE.xml` / `entities.xml`)
- **Interfaces**: Implements `iProxyNoCell`, `iQueue`, `iActivation`, `iChildCare`.

### 2.2 Methods Invoked During Login

#### 1. `Account.handshake` (`BaseMethod`, `<Exposed/>`)
- **Direction**: Client $\to$ BaseApp
- **Arguments**:
  - `hotfixMd5` (`STRING`): MD5 digest of hotfix scripts
  - `deviceInfo` (`DEVICE_INFO`): Hardware fingerprint, OS version, GPU model
  - `channelInfo` (`CHANNEL_INFO`): Store/distribution channel (`unisdk`)
  - `clientEngineInfo` (`CLIENT_ENGINE_INFO`): NeoX engine version and build timestamp
  - `sauthReply` (`STRING`): Authentication session verification token
- **Native Framing**: `MethodDescription::addToStream` encodes arguments into Mercury bundle dispatched via `ServerConnection::startProxyMessage`.

#### 2. `Account.onChannelLogin` (`ClientMethod`)
- **Direction**: BaseApp $\to$ Client
- **Arguments**:
  - `status` (`UINT8`): 0 = Channel authentication successful
  - `accountData` (`PYTHON`): Serialized Python dictionary containing account UID, player role metadata, and character list.
- **Client Action**: Unpacks player character profile. If character does not exist, triggers character creation UI. If character exists, initiates transition to Lobby.

#### 3. `Account.onLogin` (`ClientMethod`)
- **Direction**: BaseApp $\to$ Client
- **Arguments**:
  - `code` (`INT32`): Login return code
  - `message` (`STRING`): Status explanation string

---

## 3. Stage 2: Lobby Entity Instantiation (`Athlete.def.xml`)

### 3.1 Entity Role & Verification
- **CONFIDENCE**: CONFIRMED
- **Client Name**: `Athlete`
- **Interface Definition**: `05_entities/out/Athlete.def.xml`
- **Parent**: Implements `iProxyNoCell` (Base-only entity, does not possess physical cell in game space).
- **Core Interfaces**:
  - `iHallTeam`: Team/Party formation, matchmaking queues, invitations.
  - `iChatHall`: Lobby global, channel, and team text/voice chat.
  - `iFriend`: Friends list, status tracking, presence notifications.
  - `iMall` / `iCurrency`: Storefront, cosmetic outfits, tokens, weapon skins.
  - `iRank`: Leaderboards, tier progression, MMR display.
  - `iRecord`: Match history statistics, kill/death ratios, victory counts.

### 3.2 UI Transition
Upon `Athlete` creation, `ClientApp` binds the entity to Python script `ui/UIHall.py`. The title screen (`ui/UILogin.py`) is dismissed, and the player enters the interactive 3D main menu (Lobby).

---

## 4. Stage 3: Matchmaking & Space Allocation

### 4.1 Matchmaking Invocation
- **UI Trigger**: User taps "START / PLAY" in Lobby (`ui/UIHall.py`).
- **Entity Method**: `Avatar.cell.reqMatch(...)` or `Athlete.base.reqMatch(...)` via `iRosMatchAvatar`.
- **Arguments**:
  - `gameMode` (`INT32`): Solo, Duo, Squad, Fireteam
  - `mapId` (`INT32`): Ghillie Island (`1001`), Fearless Fiord (`1002`)
  - `crossPlatform` (`BOOL`): Mobile-only vs PC emulator matching pool
  - `teamGid` (`STRING`): Party identifier if queued with friends

### 4.2 Server Matchmaker Coordination
1. The server-side matchmaker aggregates up to 120 or 300 players into a match group.
2. The matchmaker contacts a `CellApp` manager to instantiate a new dynamic space:
   - **Entity**: `BattleGroundSpace` (`BattleGroundSpace.def.xml`)
   - **Parent**: `DynamicSpace`
   - **Space Interfaces**: `iMatchSingleSideSpace`, `iRobotGenerate`, `iSpaceWeatherControl`, `iRosMatchSpace`.

---

## 5. Stage 4: CellApp Transition & Battle Entity (`Avatar.def.xml`)

### 5.1 Native Handshake: `ServerConnection::createCellPlayer`
- **CONFIDENCE**: CONFIRMED
- **BINARY**: `libclient_arm64.so` at `0x2a49e63`
- **Mechanism**:
  1. BaseApp creates the physical cell entity on CellApp.
  2. BaseApp routes a Mercury notification to Client:
     `ServerConnection::createCellPlayer(entityId, spaceId)`
  3. If received out-of-order, logged at `0x2a49db0`:
     `ServerConnection::createBasePlayer: Playing buffered createCellPlayer message`
     `ServerConnection::createCellPlayer: Got createCellPlayer before createBasePlayer. Buffering message`

### 5.2 Viewport & Space Setup
- **Native Logging**:
  - `ServerConnection::spaceViewportInfo: space %d svid %d` (`0x2a49f28`)
  - `ServerConnection::spaceData: space %d for addr %s with key %u, value %d` (`0x2a49e8e`)
- **Client Execution**:
  1. Client attaches camera to the newly created cell entity.
  2. Initializes space terrain, static scene meshes, and environmental lighting from `04_obb/`.
  3. Space geometry loads: water plane, collision meshes, navigation mesh.

### 5.3 Battle Entity: `Avatar`
- **Entity Definition**: `05_entities/out/Avatar.def.xml`
- **Parent**: Implements `iProxyWithCell` (possesses both BaseApp proxy and CellApp physical representation).
- **Core Interfaces**:
  - `iNormalCombatUnit`: Health points (`hp`), armor, damage calculations, death state.
  - `iLandDrive`: Vehicle physics, seat occupancy, driving input sync.
  - `iSwim` / `iZipLine`: Swimming kinematics, zip-line traversal.
  - `iFallFollow`: Skydiving formation, parachute opening, glide trajectories.
  - `iAntiCheating`: Client speed-hack and position validation watcher.
- **Link Back to Lobby**:
  - Contains property `<athleteMailBox>` of type `GLOBAL_MAIL_BOX_INFO` (`Avatar.def.xml:154-157`).
  - Contains property `<athMailBox>` of type `GLOBAL_MAIL_BOX_INFO` (`Avatar.def.xml:167-170`).
  - This allows the in-game `Avatar` on the CellApp to dispatch score and currency rewards back to the `Athlete` entity on the BaseApp.

---

## 6. Stage 5: Real-Time In-Game Synchronization

Once inside `BattleGroundSpace`, communication between client and server proceeds at 10–30 Hz:

1. **Client Movement**: `ServerConnection::addMove(entityId, pos, dir, onGround)` sends player position, yaw, pitch, and velocity.
2. **Server Correction**: If invalid, server fires `ServerConnection::forcedPosition(entityId, pos)`.
3. **AOI Entity Streaming**: As opposing players, vehicles, or airdrops enter the player's Area of Interest, the server sends `enterWorld` and `onPartialUpdate` for those entities.
4. **Combat Actions**: Firing weapons, reloading, throwing grenades, and consuming medical kits dispatch RPCs via `MethodDescription::addToStream` on `self.cell`.
5. **Zone Shrinkage**: `BattleGroundSpace` synchronizes toxic gas circle radius and center via properties `gasCenter` and `gasRadius`.

---

## 7. Match Termination & Return to Lobby

```text
[ Match Conclusion: Player Killed or Chicken Dinner ]
                         │
                         ▼
Avatar.cell.onDeath / onGameOver
                         │
                         ▼
Avatar dispatches match results to athleteMailBox (Athlete on BaseApp)
                         │
                         ▼
ServerConnection::loggedOff(cellEntity) -> Avatar leaves world (preLeaveWorld -> leaveWorld)
                         │
                         ▼
Client returns to Lobby UI (ui/UIHall.py) bound to existing Athlete entity
```
The client does **not** disconnect from the BaseApp when a match ends; it simply tears down the `Avatar` cell entity and returns control to the `Athlete` lobby entity.
