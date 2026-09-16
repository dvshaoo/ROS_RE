# LOBBY_ENTRY_TRACE.md — Reconnect-Watchdog Investigation + Account/Avatar/Lobby Wire Checklist

> Written by a parallel, static-analysis-only session (no emulator/adb/live-server
> access), working alongside a concurrent session doing live testing of the
> `identifyVersionPoint` blocker (see `07_ros_legacy_approach/END_TO_END_TEST_LOG.md`
> E2E-021 through E2E-023, `GEMINI.md` §3). This file did not exist before this pass;
> everything below is new. All disassembly was done statically against
> `03_lib/libclient_arm64.so` using `scratch/xref_lib.py` (capstone-based ARM64
> disassembler + ADRP/ADD cross-reference finder already present in this repo).
> No device, adb, or `mitm/local_baseapp_capture.py` was touched.

---

## Task A — Is the ~10s reconnect trigger `identifyVersionPoint`-specific, or a generic watchdog?

### Verdict: **STRONGLY SUPPORTED** — it is a generic, BigWorld-stock, per-Channel "no server activity" watchdog, NOT specific to `identifyVersionPoint` or any other single RPC.

### Evidence

1. **The exact literal `10.000000` in the observed logcat line is the engine's own
   `InactivityTimeout`, logged one line above at the moment the external channel to
   BaseApp is created** — already captured verbatim in `GEMINI.md` §2D:
   ```
   [INFO] external channel minUnackPacketResendPeriod: 0.100000, InactivityTimeout 10.000000
   ```
   This line is emitted by the exact function this pass located and disassembled at
   `0x93888c`-`0x938918` in `libclient_arm64.so` (offset `0x938000` region, matches
   `GEMINI.md`'s own `0x93880c` "LoginApp timeout literal" area). It calls two getter
   functions back to back — `0x984a04` (min-unack-resend-period getter) and `0x9849c8`
   (inactivity-timeout getter) — converts both to float, and passes them to the format
   string at `0x2a48f97`: `"external channel minUnackPacketResendPeriod: %f,
   InactivityTimeout %f"`. **CONFIRMED BY BINARY**: this is the Channel object's own
   two configured timing parameters being logged right after channel creation, not a
   coincidental log near unrelated code.

2. **`getInactivityTimeout`/`setInactivityTimeout` are real, named, script-exposed
   BigWorld engine API symbols** — found directly in the binary's string table
   immediately adjacent to `InactivityTimeout` itself (`0x2a48400` region):
   ```
   ...findClosestVisibleInAngle\0setInactivityTimeout\0getInactivityTimeout\0setMinUnackPacketRese...
   ```
   `ServerConnection.setInactivityTimeout()` / `getInactivityTimeout()` are documented,
   stock BigWorld Technology public Python API members (this is standard, well-known
   BigWorld engine terminology, not a ROS-specific invention) — their whole purpose in
   the upstream engine is: *disconnect (and, on this client's variant, trigger a fresh
   LoginApp handshake) if no packet of any kind has been received from the peer for N
   seconds.* This is a **transport/channel-level liveness watchdog**, entirely
   independent of which particular BaseApp RPC the client happens to be waiting on.

3. **The getter's implementation confirms it is a single global timer value, not a
   per-RPC state flag**: `0x9849c8` disassembles to:
   ```
   adrp x8, #0x457d000 ; ldr d0,[x8,#0x328]   ; global raw tick count
   adrp x8, #0x2a46000 ; ldr d1,[x8,#0x558]   ; global "stamps-per-second" constant
   ucvtf d0,d0 ; fdiv d0,d0,d1 ; fcvt s0,d0 ; ret
   ```
   i.e. it reads one process-global tick value and divides by the engine's own
   ticks-per-second constant to produce a float number of *seconds*. This is a classic
   BigWorld "configured timeout, expressed as engine ticks, converted to seconds on
   read" pattern — a single global setting for the whole channel, not something keyed
   to `identifyVersionPoint`, `createBasePlayer`, or any other specific message.

4. **Configurability**: **INFERRED** (not fully confirmed which specific resource file
   sets it) — the value is read from a global/static memory slot (`0x457d000+0x328`)
   rather than being an immediate literal baked into the channel-creation call site (no
   `10.0f` / `0x41200000` bit-pattern literal was found anywhere near the channel-init
   code in a targeted scan). This is consistent with this project's own prior
   established finding (re: `logOnBegin`'s retry count) that BigWorld timeout/retry
   parameters are typically populated once at startup from an external config resource
   rather than hardcoded per call site. We did **not** locate the specific resource
   file/key this pass (out of scope for the time budget) — flagged as a loose end, not
   a blocker.

### Practical implication for the live-testing session (the actual question asked)

**Fixing `identifyVersionPoint`'s reply alone will very likely NOT be sufficient to
permanently prevent this reconnect loop.** The mechanism above watches for *any*
packet arriving from the server, not specifically a `versionPointIdentity` reply. Two
concrete predictions, both actionable once a live device is available again:

- Since the Mercury reliable-channel ACK (already implemented per `GEMINI.md` §3,
  commit `b5d6f2b`) is itself a valid received packet, it plausibly resets the
  `InactivityTimeout` clock once, at the moment it's sent for packet #0. If that's the
  *only* packet the server ever sends, the client would still hit the 10s inactivity
  ceiling **10 seconds after that ACK**, independent of whether `identifyVersionPoint`
  ever gets a semantically-correct application-level reply. This matches the observed
  timing (~10s from stall to full reconnect) at least as well as an
  `identifyVersionPoint`-specific theory does, and is a simpler explanation requiring
  no new hypothesis about `versionPointIdentity`'s msgID.
- Even after Finding 2 from E2E-021 (a real `versionPointIdentity` reply) is confirmed
  and implemented, the server will need a **recurring** keep-alive push at an interval
  safely under 10s for as long as the BaseApp connection is meant to stay open — not
  just a one-time reply to this one RPC — or the exact same reconnect loop will
  resurface later (e.g. once the client is idle in the Lobby with no further pending
  RPCs). The `ClientInterface` table already documents good, purpose-built candidates
  for this (`06_trace/MERCURY_PACKET_MAP.md` §3): **`setGameTime`** (4-byte fixed body,
  ClientInterface ID confirmed FIXED/4 in the framing table) or **`tickSync`** are the
  most natural fits — both are exactly the class of periodic, content-light
  "still here" pushes BigWorld servers normally send. `bandwidthNotification` (also
  FIXED/4 bytes, registration-order ID 0) is another plausible minimal-content
  keep-alive candidate.

**Recommended next live-test step for the other session** (not executed here, per this
task's static-only scope): once `versionPointIdentity`'s numeric msgID is resolved and
tested, ALSO start sending a trivial periodic push (e.g. `setGameTime` with the
server's wall-clock time, every ~5s) on the BaseApp channel and confirm the client
never re-triggers the LoginApp restart even after `identifyVersionPoint` is
answered — this isolates whether Finding 2's echo fix alone is sufficient or whether
the generic watchdog (this task's finding) is the thing that actually needs
addressing.

---

## Task B — Account / Avatar / Lobby wire-format checklist (prepared ahead of unblock)

### B.1 — `Account` entity (type 127, CONFIRMED both by prior live capture — `GEMINI.md`
§2D `createBasePlayer` logcat — and independently by this pass's own count of
`05_entities/out/entities.xml`'s declaration order, see below)

Source: `05_entities/out/Account.def.xml` (full file read this pass).

- **Implements**: `iProxyNoCell`, `iQueue`, `iActivation`, `iChildCare`.
- **Properties** (7 total): `isBan` (BOOL, BASE), `startBanTime` (INT64, BASE),
  `banTime` (INT32, BASE), `banReason` (STRING, BASE), `nickname` (STRING, BASE),
  `isMobileAccount` (BOOL, **BASE_AND_CLIENT**), `isGuest` (BOOL, BASE, default
  `False`), `finalPlatform` (STRING, BASE).
- **CONFIRMED**: exactly **one** `BASE_AND_CLIENT`-flagged property exists on
  `Account`, matching the prior GEMINI.md/task-brief claim — it is **`isMobileAccount`**
  (a `BOOL`, persistent, no explicit default given in the def file — BigWorld defaults
  an unset BOOL to `False`). This is the only `Account` property value the client's own
  entity-property stream needs to carry (the rest are `BASE`-only, i.e. server-side/
  cell-side state never pushed to the client in the initial property stream).
- **Minimum property stream to construct a valid `Account` entity server-side**: per
  BigWorld's standard entity-creation wire format, only `BASE_AND_CLIENT` (and
  `CELL_PUBLIC`/`ALL_CLIENTS`, not applicable here since `Account` has no cell) flagged
  properties are serialized into the property stream sent to the client at creation
  time. **Practical minimum: a single BOOL byte for `isMobileAccount`** (e.g. `0x00` for
  a non-mobile/guest login) — this is CONSISTENT with `GEMINI.md`'s already-confirmed
  wire layout for `createBasePlayer` showing only `entityID`(4B)+`entityType`(2B) in the
  message header, with any per-entity property payload appended separately/optionally
  depending on BigWorld's exact `createBasePlayer` framing (the message is
  VARIABLE_LENGTH per `MERCURY_PACKET_MAP.md` §2b, so a property stream CAN be appended,
  but a 0-length/absent property stream is also legal BigWorld behavior when every
  property is either default or `BASE`-only — **INFERRED**, not live-verified, that an
  all-default/empty property stream will produce a working `Account` given only one
  BASE_AND_CLIENT property and it already has effectively no meaningful default state
  needed for the handshake to proceed).
- **BaseMethods this entity must be ready to receive from the client**: `handshake`
  (`<Exposed/>` — client→server; args: `hotfixMd5` STRING, `deviceInfo` DEVICE_INFO,
  `channelInfo` CHANNEL_INFO, `clientEngineInfo` CLIENT_ENGINE_INFO, `sauthReply`
  STRING), `onAcquireLock`, `onDuplicateLogin`, `uploadABSwitchesConfig` (`<Exposed/>`).
  Per `06_trace/BASEAPP_CELLAPP_FLOW.md` §2.2, `handshake` is the first real
  application-level RPC the client will call once `Account` exists — **this is
  likely the actual next blocker after `identifyVersionPoint`/the watchdog are
  resolved**, and is a good target for the next disassembly pass once live testing
  reaches it.
- **ClientMethods the server must be able to send**: `onLogin` (INT32 code, STRING
  message), `onChannelLogin` (UINT8 status, PYTHON accountData — **this is the one
  that per `BASEAPP_CELLAPP_FLOW.md` §2.2 #2 triggers the client to either show
  character-creation UI or transition toward Lobby**, depending on the decoded
  `accountData` dict's character-list content), `refreshSwitches`, `refreshForbiddenID`,
  `syncServerTime`, `syncServerTimeZone`, `onLoginPCServer`, `loadSceneAfterReconnect`.

### B.2 — `Avatar`/`Athlete` entity type IDs — **CORRECTION to `GEMINI.md`**

`GEMINI.md` §4 states `Athlete = 128` (uncited, presumably assumed from being "the
entity right after Account" or copied from a PC-client numbering). **This pass
independently counted `05_entities/out/entities.xml`'s actual 0-indexed declaration
order** (BigWorld assigns entity type IDs by declaration order in this file — the same
mechanism already used to CONFIRM `Account = 127`) and found:

```
index 127: Account        (matches live-CONFIRMED createBasePlayer entityType=127)
index 128: BattleAccount   <-- NOT Athlete
index 129: Avatar
...
index 140: Athlete
```

**CORRECTED, STRONGLY SUPPORTED** (same counting method that already independently
matches the live-confirmed `Account=127`, but not itself live-verified for
`Athlete`/`Avatar` specifically): `Avatar` is type **129**, and `Athlete` (the actual
Lobby entity per `BASEAPP_CELLAPP_FLOW.md` §3, NOT `Avatar`) is type **140**. Whoever
implements the next `createBasePlayer`-style push for the Lobby transition should send
`entityType = 140` for `Athlete`, not 128. This is flagged prominently because it's an
easy, previously-undetected off-by-inference bug that would have silently produced a
wrong/rejected entity type on the first live attempt.

(`Avatar.def.xml` is the CellApp battle-unit entity per `BASEAPP_CELLAPP_FLOW.md` §5,
type 129 — not needed until the matchmaking/CellApp phase, well after Lobby entry.)

### B.3 — Message flow after `createBasePlayer`: is `createCellPlayer` required for Lobby?

**STRONGLY SUPPORTED: no.** `Athlete` (`Athlete.def.xml`) implements only
`iProxyNoCell` (confirmed by direct read of the def file this pass — `<Interface>
iProxyNoCell </Interface>` is its only base/cell-nature interface, alongside ~60
purely-BaseApp feature interfaces like `iHallTeam`, `iChatHall`, `iFriend`, `iMall`,
`iRank`, etc. — no cell-side interface at all). `iProxyNoCell` means this entity has
**no CellApp/physical-space counterpart** — per `BASEAPP_CELLAPP_FLOW.md` §3.1/§5.1,
`createCellPlayer`, `spaceData`, `spaceViewportInfo`, and `enterAoI` are all part of the
**CellApp/`BattleGroundSpace` combat-entry path** (`Avatar`, which DOES implement
`iProxyWithCell`), triggered only later by matchmaking (`BASEAPP_CELLAPP_FLOW.md` §4-§5)
— they are **not required** to get the client from "BaseApp login accepted" into the
Lobby UI. This confirms `BASEAPP_CELLAPP_FLOW.md`'s own architecture diagram (§1) is
correct and directly answers this task's open question: the minimal Lobby-entry path
needs only BaseApp-side `Account`→`Athlete` entity replacement/creation, no CellApp
space handshake at all.

### B.4 — Is the Lobby transition purely server-driven, or does client Python (`.nxs`) logic gate it?

**Cited from existing doc, not re-derived**: `BASEAPP_CELLAPP_FLOW.md` §3.2 already
states: *"Upon `Athlete` creation, `ClientApp` binds the entity to Python script
`ui/UIHall.py`. The title screen (`ui/UILogin.py`) is dismissed, and the player enters
the interactive 3D main menu (Lobby)."* This is **INFERRED** in that source doc (not
independently re-confirmed at the disassembly level this pass — no new evidence was
found or sought this pass beyond what that doc already states, per the task's
instruction to cite rather than re-derive). The practical implication either way is the
same for server implementation purposes: **entity replacement of the client's bound
entity from `Account` to `Athlete` (a real server-side entity-type transition, not just
a property change) is the server-observable trigger** — whether the client's own
Python UI layer then makes cosmetic decisions based on `Athlete`'s property values
(e.g. whether to show a "create character" flow first, per `Account.onChannelLogin`'s
`accountData` PYTHON blob mentioned in B.1) is a client-side detail that does not change
what the server needs to send.

### B.5 — Concrete minimal checklist: BaseApp-login-accepted → visibly-in-Lobby

This assumes `identifyVersionPoint`/watchdog (Task A) are already resolved and the
BaseApp channel stays alive. Order matters; items marked `[BLOCKED ON LIVE TEST]` are
not yet independently confirmed by a real client response, only by static disassembly/
def-file reading:

1. **`Account` entity already exists** (msgID `createBasePlayer`, `entityType=127`) —
   already CONFIRMED live per `GEMINI.md` §2D. No property stream strictly required
   beyond default/zero values for its single `BASE_AND_CLIENT` property
   (`isMobileAccount`) — send `0x00` (non-mobile) as the simplest first attempt.
2. **Respond to the client's `Account.handshake` BaseApp RPC** `[BLOCKED ON LIVE TEST]`
   — this is the first real application call after entity creation
   (`BASEAPP_CELLAPP_FLOW.md` §2.2 #1); its exact numeric `BaseAppExtInterface`/entity
   method ID and wire body layout for the 5 arguments (`hotfixMd5`, `deviceInfo`,
   `channelInfo`, `clientEngineInfo`, `sauthReply`) have **not yet been disassembled** —
   flagged as the next concrete static-analysis task once `identifyVersionPoint` is
   closed out.
3. **Push `Account.onChannelLogin`** (ClientMethod, UINT8 `status=0`, PYTHON
   `accountData`) — this is the confirmed trigger (`BASEAPP_CELLAPP_FLOW.md` §2.2 #2)
   for the client to decide character-creation vs. Lobby. The `accountData` PYTHON
   blob's exact expected dict schema (UID, role metadata, character list) is
   **UNKNOWN** — not yet reverse-engineered; needs either a real reference capture
   (impossible, no real server available) or disassembly of the client's
   `onChannelLogin` handler to find which dict keys it reads. Recommend, as the
   cheapest first live guess, an **empty-but-well-formed** dict (e.g. `{'characters':
   []}` or similarly named per whatever key the handler actually reads) to force the
   character-creation path rather than guessing a fully-populated character record.
4. **Push `Account.onLogin`** (INT32 `code=0`, STRING `message=""`) if the handler
   requires an explicit success code separate from `onChannelLogin` — order relative to
   step 3 not yet determined; `[BLOCKED ON LIVE TEST]`.
5. **Replace/transition the client's bound entity from `Account` (127) to `Athlete`
   (140, CORRECTED per B.2)** via the same `createBasePlayer`/entity-replacement
   mechanism (exact BigWorld idiom — whether this is a second `createBasePlayer` push
   with a new entity ID, or a `resetEntities` + fresh `createBasePlayer`, is
   **UNKNOWN**, not yet disassembled this pass — `resetEntities` (ClientInterface
   msgID 3 per registration-order counting in `MERCURY_PACKET_MAP.md` §2b) is a
   plausible mechanism worth checking first, since it exists specifically to clear
   prior entity state before a fresh entity population).
6. **No `createCellPlayer`/`spaceData`/`spaceViewportInfo`/`enterAoI` needed** for
   Lobby (CONFIRMED per B.3 — `Athlete` is `iProxyNoCell`). These become relevant only
   at the matchmaking/`BattleGroundSpace` stage (`BASEAPP_CELLAPP_FLOW.md` §4-§5), well
   after Lobby.
7. **Client-visible result**: once the client's bound entity is genuinely `Athlete`
   (type 140) and `ui/UIHall.py` binds to it (client-internal, not server-observable —
   B.4), the title screen (`ui/UILogin.py`) should dismiss and the 3D Lobby should
   render. The concrete, externally-observable success signal for the next live-testing
   session to watch for in logcat is any `UIHall`-related Python log line, or simply a
   screenshot showing the 3D main-menu scene instead of the login spinner.

### Open items for the next pass (explicitly NOT done this pass, listed so no one
re-discovers the same gap from scratch)

- `Account.handshake`'s numeric method ID and 5-argument wire layout — not
  disassembled.
- The `accountData` PYTHON dict schema expected by the client's `onChannelLogin`
  handler — not disassembled.
- Whether entity-type transition Account→Athlete uses `resetEntities` or a second
  `createBasePlayer` — not disassembled.
- The specific config resource (if any) that sets the 10.0s `InactivityTimeout` —
  not located.
