# ROS v1117219 — Mercury Interface/Method Name Tables (Binary-Extracted)

This is a directly-extracted artifact, not a reconstruction: the client binary embeds the
literal interface/method name strings used to build its Mercury RPC dispatch tables (kept
for debug logging / reflection). Found via raw byte search in
`03_lib/libclient_arm64.so`, all in one contiguous run of NUL-separated C strings starting
at rodata offset `0x2a49279` (verified: `.rodata` `addr==offset` in this build, so this is
also the load address).

**Confidence: CONFIRMED** for every string listed (directly read from the binary, not
inferred). The *order* of strings in this table almost certainly matches Mercury's
interface-method enumeration order (BigWorld's codegen emits interface descriptor tables in
declaration order), but that mapping to actual numeric opcodes was **not** independently
verified — see §4.

## 1. `LoginInterface` (client → LoginApp)

Only one string present near this table: `LoginInterface\0`. Unlike `BaseAppExtInterface`
and `ClientInterface`, no method name list follows it directly in this run — the login RPC
methods are not listed elsewhere in this dump. **Interpretation (INFERRED)**: this is
because `LoginApp` typically has only one client-facing entry point (called `login` /
`logOnBegin` in BigWorld convention). This is consistent with the rest of this project's
findings that the whole login handshake goes through a single Mercury message
(`LogOnParams::addToStream`, see `LOGONPARAMS_SERIALIZATION.md`) rather than multiple named
RPCs.

## 2. `BaseAppExtInterface` (client → BaseApp)

String table, offset `0x2a4a29d` onward, NUL-separated, in this exact order:

```
baseAppLogin
authenticate
avatarUpdateImplicit
avatarUpdateExplicit
avatarUpdateWardImplicit
avatarUpdateWardExplicit
switchInterface
requestEntityUpdate
enableEntities
setSpaceViewportAck
setVehicleAck
restoreClientAck
identifyVersionPoint
summariseVersionPoint
commenceResourceDownload
disconnectClient
resourceVersionTag
entityMessage
```

`baseAppLogin` (first entry) is the method the client calls immediately after receiving a
`LoginApp` reply — this matches `BaseAppLoginRequest::setNubAndSend()` in
`MERCURY_LOGIN_FLOW.md` §4.3, whose real function was located and confirmed at
`0x9384a8` (see §3 below) — `enableEntities` is very likely the trigger that starts entity
replication (`Account`/`Athlete`/`Avatar` creation) once BaseApp accepts the login.

## 3. `ClientInterface` (BaseApp/CellApp → client, i.e. server-to-client pushes)

Immediately follows the `BaseAppExtInterface` list in the same string blob:

```
ClientInterface
bandwidthNotification
updateFrequencyNotification
setGameTime
resetEntities
createBasePlayer
createCellPlayer
spaceData
spaceViewportInfo
updateEntity
enterAoI
enterAoIThruViewport
enterAoIOnVehicle
leaveAoI
tickSync
relativePositionReference
set...  (string truncated by read window; not yet fully extracted)
```

`createBasePlayer` and `createCellPlayer` confirm the two entity-creation push messages
already named in `MERCURY_LOGIN_FLOW.md` §5 (stages 7/6) — this is now backed by the literal
interface table rather than a log-string guess. `enterAoI` / `leaveAoI` (Area-of-Interest)
and `spaceData` / `spaceViewportInfo` confirm this client uses BigWorld's standard AoI/space
model for the battle-ground/cell layer, matching `BattleGroundSpace.def.xml` in
`05_entities/out/`.

## 2a. `BaseAppExtInterface` — CONFIRMED Wire Framing Per Method (2026-09-14 update)

The registration code for this table (`0x80c600`–`0x80cb00`, found by disassembling the
code containing the `baseAppLogin` string xref) calls a uniform registrar function at
`0x98b30c` once per method:

```
bl 0x98b30c(interfaceObj=x0, nameStringPtr=x1, lengthStyle=w2, lengthParam=w3, extra=x4)
```

Reading `w2`/`w3` directly at each call site gives a **CONFIRMED BY BINARY** framing table
for every method (lengthStyle: `0` = FIXED_LENGTH_MESSAGE, with `lengthParam` = the body
size in bytes; `1` = VARIABLE_LENGTH_MESSAGE, with `lengthParam` = the byte width of the
length-prefix field that precedes the variable body):

| Method | lengthStyle | lengthParam | Framing |
|---|---|---|---|
| `baseAppLogin` | 1 (VARIABLE) | 2 | `u16` length prefix + variable body |
| `authenticate` | 0 (FIXED) | 4 | 4-byte fixed body |
| `avatarUpdateImplicit` | 0 (FIXED) | 24 (0x18) | 24-byte fixed body |
| `avatarUpdateExplicit` | 0 (FIXED) | 32 (0x20) | 32-byte fixed body |
| `avatarUpdateWardImplicit` | 0 (FIXED) | 24 (0x18) | 24-byte fixed body |
| `avatarUpdateWardExplicit` | 0 (FIXED) | 32 (0x20) | 32-byte fixed body |
| `switchInterface` | 0 (FIXED) | 0 | no body |
| `requestEntityUpdate` | 1 (VARIABLE) | 2 | `u16` length prefix + variable body |
| `enableEntities` | 0 (FIXED) | 8 | 8-byte fixed body |
| `setSpaceViewportAck` | 0 (FIXED) | 8 | 8-byte fixed body |
| `setVehicleAck` | 0 (FIXED) | 8 | 8-byte fixed body |
| `restoreClientAck` | 0 (FIXED) | 4 | 4-byte fixed body |
| `identifyVersionPoint` | 1 (VARIABLE) | 2 | `u16` length prefix + variable body |
| `summariseVersionPoint` | 1 (VARIABLE) | 2 | `u16` length prefix + variable body |
| `commenceResourceDownload` | 1 (VARIABLE) | 2 | `u16` length prefix + variable body |
| `disconnectClient` | 0 (FIXED) | 1 | 1-byte fixed body |
| `resourceVersionTag` | 0 (FIXED) | 1 | 1-byte fixed body |
| `entityMessage` | 1 (VARIABLE) | 2 | `u16` length prefix + variable body |

`ClientInterface` registration follows immediately with the same mechanism (partial, table
truncated in the read window):

| Method | lengthStyle | lengthParam | Framing |
|---|---|---|---|
| `bandwidthNotification` | 0 (FIXED) | 4 | 4-byte fixed body |
| `updateFrequencyNotification` | 0 (FIXED) | 1 | 1-byte fixed body |
| `setGameTime` | 0 (FIXED) | 4 | 4-byte fixed body |

This table is a strict upgrade over §2/§3 above: it confirms not just that these methods
exist by name, but their exact **on-wire framing** (fixed vs. variable, and either the exact
byte count or the length-prefix width). Field-level content within each body — beyond
framing — is documented per-message where available; for `baseAppLogin` specifically, see
`BASEAPP_LOGIN_SERIALIZATION.md`.

## 4. Confirmed Function: `LoginHandler::onLoginReply` / `handleMessage`

Located via cross-reference of the evidence string `"sending base app request to %s "`
(rodata `0x2a49141`) — exactly **one** xref found:

- **Address: `0x9384a0`–`0x9384ec`** (the `adrp`/`add`/`bl` triplet loading and logging this
  string). This is inside a larger function spanning roughly `0x938100`–`0x9385f8+`.
- This **matches** (to within ~0x30 bytes) the address `0x9384e4`/`0x9384ec` claimed in the
  pre-existing `MERCURY_LOGIN_FLOW.md` §4.3 — that prior claim is **CONFIRMED accurate** by
  this independent xref method.
- Confirmed behaviors read directly from disassembly in this region:
  - Reads a 20-byte (`w1=0x14`) record via a stream-reader call (`bl #0x989600`), storing a
    16-byte quadword (`Address`-sized) at `this+0x50` and a trailing 4-byte field at
    `this+0x60` (`+0x50+0x10`). **CONFIRMED**: a fixed-size Address-like structure is read
    from the reply. **UNKNOWN**: whether this is `{ip:4, port:2, salt:2}` classic BigWorld
    `Mercury::Address` or an IPv6-capable variant — the previous report's claim of
    "IPv4/IPv6 address and port" is STRONG EVIDENCE but not byte-confirmed.
  - Compares a loaded 32-bit value against the literal constant `0x32ef9816`
    (`0x938298`–`0x9382a4`). **INFERRED**: this is an interface/entity-defs fingerprint
    hash check (BigWorld's standard version-mismatch guard), not a session key — do **not**
    treat `0x32ef9816` as a session key or account ID.
  - On mismatch/error paths, reads and logs additional length-prefixed strings using the
    *exact same* SSO-string-read pattern documented in `LOGONPARAMS_SERIALIZATION.md` §3 —
    confirms this string encoding is used engine-wide, not just for `LogOnParams`.
  - Error/reason strings confirmed present verbatim in rodata immediately after this
    function's string table: `"Mercury::REASON_CORRUPTED_PACKET"`, `"Unspecified error."`,
    `"Unelaborated error."`, `"Unable t[o connect to BaseApp...]"` (matches
    `MERCURY_LOGIN_FLOW.md` §4.2 verbatim).
- **NOT located in this pass**: the precise byte offsets of `SessionKey` and `AccountID`
  within the LoginApp reply payload. The previous report's §4.1 claim that
  `LoginReplyRecord` contains `{Address, SessionKey, AccountID}` is STRONG EVIDENCE (BigWorld
  architecture + partial byte confirmation of the Address field) but **not fully
  CONFIRMED** at the byte level — see `LOGIN_REPLY_RECORD.md` for the honest breakdown.

## 4a. Confirmed Function: `BaseAppLoginRequest` Send Chain (2026-09-14 update)

Full call-chain located and disassembled — see `BASEAPP_LOGIN_SERIALIZATION.md` for detail:

```
0x93a404  ServerConnection-level orchestrator (single-attempt retry gate, this+0x80 counter)
    └─ bl 0x9387cc   BaseAppLoginRequest build-and-send
         ├─ bl 0x937128   registers reply/timeout handler (5.0s timeout, InterfaceElement
         │                 handle for baseAppLogin loaded from global @ 0x457a210)
         └─ bl 0x9389dc   BaseAppLoginRequest::initNetwork (opens UDP socket, port range
                           0x861-0xe321 / 2145-58145, confirms MERCURY_LOGIN_FLOW.md's range)
```

No `BinaryOStream`-vtable-dispatched field write was located anywhere in this chain — see
`BASEAPP_LOGIN_SERIALIZATION.md` §4 for the honest UNKNOWN status of the message body
content.

## 5. Still Unresolved

1. Full `ClientInterface` method list (string window cut off after `relativePositionReference`).
2. Numeric Mercury interface/method IDs (opcodes) corresponding to each name above — the
   name strings exist for debug purposes but the actual on-wire integer IDs were not
   recovered in this pass (would require locating the interface descriptor table, likely a
   `.data.rel.ro` array of structs pointing at these strings with an adjacent index/size
   field).
3. `CellAppInterface` / `BaseAppInterface` string tables were searched for and **not found**
   verbatim in `libclient_arm64.so` — either named differently in this build, stored only as
   compiled-in numeric tables without string names, or located in a code path not yet
   searched.
