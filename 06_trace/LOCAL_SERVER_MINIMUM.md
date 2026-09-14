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

**Framing CONFIRMED, body UNKNOWN** (see `BASEAPP_LOGIN_SERIALIZATION.md`, 2026-09-14
update):

```
Mercury message header (baseAppLogin = method #0 of BaseAppExtInterface)
u16  bodyLength
u8[bodyLength]  <-- exact field content not recovered
```

Also confirmed: the client sends this **exactly once** per connection attempt (no
client-side retry — a second attempt fails locally without transmitting anything), with a
5-second reply timeout. A local BaseApp prototype therefore has one shot and 5 seconds to
reply before the client gives up.

**Cross-checked against `LoginReplyRecord`**: no evidence was found that a distinct
LoginApp-issued session key gets threaded into this message's body — the one candidate
24-byte context block traced turned out to be logging/bookkeeping data (a backup of the
previous BaseApp address for a log message), not a credential. This *suggests* — but does
not prove — that BaseApp may not need to validate a LoginApp-issued secret at all, which
would substantially simplify a local prototype. See `BASEAPP_LOGIN_SERIALIZATION.md` §5 for
the full caveat.

**Requirement for a local server**: this remains the top blocker for a working prototype —
the local BaseApp still cannot be written with confidence until the body content (if any)
is known. But the risk has narrowed: we now know the framing exactly (so a prototype BaseApp
at minimum can correctly *parse* the length-prefixed body even without understanding its
contents), and we have tentative (not proven) reason to believe no session-key validation
loop needs to be replicated.

**2026-09-14 (third pass) update**: the client-side `BaseAppLoginRequest` object (the
in-memory structure built right before sending) has now been fully mapped byte-for-byte
(`BASEAPP_LOGIN_SERIALIZATION.md` §5a) — but this resolved a *different* question than the
wire body. It confirms the object is shaped like a reply-timeout/callback tracker (a
`std::function<void()>` callback, a back-pointer, the interface handle, timeout floats), and
it remains genuinely unproven whether the one candidate data block inside it
(`ServerConnection+0x24..0x3B`, copied verbatim into the tracker) is ever written to the
network at all, versus being pure local callback context. A blind, unscoped search for the
actual field-by-field wire-write code across the rest of `.text` was attempted and did not
converge — isolating it now requires either locating the `ServerConnection`/`LoginHandler`
constructor by a more reliable method than the RTTI-chain reconstruction attempted here (an
attempt was made and abandoned when it produced an inconsistent, unverifiable result), or
dynamic instrumentation (Frida hook on the confirmed send chain, logging the constructed
Mercury bundle bytes at send time). This is the clearest remaining path to closing Stage 3.

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

## Minimum Information Breakdown: LoginApp → BaseApp → Account/Lobby (2026-09-14)

1. **Required for the client to send `baseAppLogin` at all**: a valid `LoginReplyRecord`
   from Stage 2 containing a BaseApp address the client accepts (STRONG EVIDENCE: a
   20-byte address-shaped record, see `LOGIN_REPLY_RECORD.md`) — the client's socket-bind
   and reply-handler setup (`BASEAPP_LOGIN_SERIALIZATION.md` §3) do not depend on
   understanding any credential, only on having *an* address to connect to.
2. **Required for BaseApp to parse the incoming packet**: knowledge of the CONFIRMED framing
   — Mercury message header identifying method `baseAppLogin` (interface index 0 of
   `BaseAppExtInterface`), followed by a `u16` body-length field, followed by that many
   bytes. A minimal BaseApp can read and discard the body without understanding it and
   still have correctly parsed the packet.
3. **Required for BaseApp to validate it**: UNKNOWN. No evidence was found that a
   LoginApp-issued session key is resubmitted in this body (see
   `BASEAPP_LOGIN_SERIALIZATION.md` §5) — a permissive local BaseApp could plausibly accept
   any well-formed packet on this port without validating body content, but this is
   INFERRED from absence of evidence, not a confirmed safe assumption.
4. **Required for BaseApp to create the `Account` entity**: architectural only (INFERRED
   FROM ENTITY DEFINITIONS) — `05_entities/out/Account.def.xml`'s property list would need
   to be populated with *something* for the subsequent `createBasePlayer` push (Stage 4) to
   be well-formed; whether any of that data must come from the `baseAppLogin` body itself
   was not determined.
5. **Required for the client to accept `createBasePlayer`**: not traced in this pass — the
   Mercury framing for `ClientInterface::createBasePlayer` was not looked up (it appears in
   the interface string table per `MERCURY_PACKET_MAP.md` §3 but was not part of the
   `BaseAppExtInterface` w2/w3 table in §2a since it belongs to the separate
   `ClientInterface`, which was only partially registered within this pass's read window).

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
