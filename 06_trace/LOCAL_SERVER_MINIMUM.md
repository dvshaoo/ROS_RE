# ROS v1117219 — Minimum Viable Local Server (PLAY → Lobby)

Synthesis of `LOGONPARAMS_SERIALIZATION.md`, `LOGIN_REPLY_RECORD.md`,
`BASEAPP_LOGIN_SERIALIZATION.md`, and `MERCURY_PACKET_MAP.md`. Answers: *what is the
smallest local server that could make the original client progress from PLAY toward
Lobby?*

## Stage Breakdown

### Stage 1 — Client → local LoginApp

**Packet**: one Mercury bundle carrying the `LogOnParams` payload (see
`LOGONPARAMS_SERIALIZATION.md` §4):
```
u8   flags
[RSA-OAEP-encrypted block: flags, stringA, stringB, stringC]   (only if a public key is configured)
u8[16] digest        (only if flags & 1)
u32  numericField
```
**Confidence**: CONFIRMED structure, UNKNOWN semantic field names.
**Requirement for a local server**: none — a local LoginApp does not need to *decrypt*
anything to make progress, since it fully controls what it replies with regardless of
whether it can parse the client's credentials. A prototype LoginApp can simply **not care**
about the plaintext content and unconditionally reply with a synthetic BaseApp address (see
Stage 2). RSA decryption is only required if the local server wants to actually validate
credentials, which is out of scope for LAN/preservation use.

### Stage 2 — Local LoginApp → Client (`LoginReplyRecord`)

**Packet**: a 20-byte address-shaped record (`this+0x50`/`+0x60` in
`LoginHandler::onLoginReply`, see `LOGIN_REPLY_RECORD.md` §2), of which the sub-field
layout (IPv4 vs IPv6, port position, and whether a session key rides along) is
**UNKNOWN, not CONFIRMED**.

**Practical mitigation**: since exact layout wasn't recovered, the fastest path to an
empirical answer is *not* more static analysis — it's capturing one real login attempt
against the existing `mitm/mitm_serve.py` harness (already in this repo) with a raw UDP
packet dump. A 20-byte reply is small enough to brute-force-interpret once a real sample
exists: try `{4-byte IP, 2-byte port, 14 bytes unknown}` and `{16-byte IPv6, 2-byte port,
2 bytes unknown}` against a known test server address and see which one round-trips.

**Requirement for a local server**: build the 20-byte record with the local BaseApp's real
IP:port in whichever position testing confirms, matching the compare against
`0x32ef9816` behavior — this constant looks like a fingerprint the client checks on a
different branch (not necessarily gating the address record itself), so it may not need to
be reproduced exactly. Flagged UNKNOWN — treat as a risk, not a blocker, until tested.

### Stage 3 — Client → BaseApp (`baseAppLogin`)

**Not byte-level traced** (see `BASEAPP_LOGIN_SERIALIZATION.md`). Confirmed only that the
Mercury interface method name is `baseAppLogin` (first entry of `BaseAppExtInterface`).

**Requirement for a local server**: this is the actual first unresolved blocker for a
working prototype — a local BaseApp cannot be written with confidence until this bundle's
fields are known, because if the client re-sends a LoginApp-issued key that BaseApp is
expected to validate, mismatched local LoginApp/BaseApp implementations will silently
reject the client with no useful client-side error (per `LoginHandler`'s generic
"Unspecified error." / "Unelaborated error." strings confirmed in `LOGIN_REPLY_RECORD.md`).

### Stage 4 — BaseApp → Client (entity creation)

**Confirmed** (from `MERCURY_PACKET_MAP.md` §3, direct interface-table extraction):
`ClientInterface::createBasePlayer` and `ClientInterface::createCellPlayer` are real,
named Mercury pushes. Their argument encoding was not traced, but their *existence and
names* are no longer speculative — this is a strict improvement over the previous report's
purely architectural claim.

**Requirement for a local server**: send a `createBasePlayer` push whose entity property
blob matches the client-side entity definition for `Account` (`05_entities/out/Account.def.xml`).
This is INFERRED FROM ENTITY DEFINITIONS, not binary-confirmed — the property
serialization order for `createBasePlayer` was not disassembled.

### Stages 5–7 — Account → Athlete → matchmaking → CellApp

Not investigated in this pass beyond what the pre-existing `BASEAPP_CELLAPP_FLOW.md`
already documents (architectural, entity-def-derived — no new native evidence gathered
here). No change to prior confidence levels for these stages.

## First Implementable Prototype

**Stage 1 + Stage 2 only** ("local LoginApp") remains the correct first target, as the
prior `LAN_FEASIBILITY.md` already concluded — but with an important correction: the client
does **not** require the local server to be able to decrypt `LogOnParams` to reach Stage 2,
since the client only needs *a plausible-looking reply*, not proof the server understood its
credentials. This lowers the bar for a Stage-1/2 prototype from "must implement RSA-OAEP
decryption with the real private key (impossible without NetEase's key)" down to "must
reply with a correctly-shaped 20-byte address record" — a much smaller, achievable target
that doesn't require solving the encryption problem at all.

The remaining hard blocker to reach Lobby is Stage 3 (`baseAppLogin` field layout),
correctly identified above as the next highest-value native-analysis target.

## Confidence Summary

| Stage | Structure known? | Confidence |
|---|---|---|
| 1. Client→LoginApp | Yes | CONFIRMED |
| 2. LoginApp→Client | Partial (size known, sub-fields not) | STRONG EVIDENCE / UNKNOWN sub-fields |
| 3. Client→BaseApp | No | UNKNOWN — top priority follow-up |
| 4. BaseApp→Client (entity push) | Names only, no field encoding | STRONG EVIDENCE (names), UNKNOWN (encoding) |
| 5–7. Entity handshake / matchmaking / CellApp | Architectural only | INFERRED FROM ENTITY DEFINITIONS |
