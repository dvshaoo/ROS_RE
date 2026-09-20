# Question for ChatGPT: BigWorld/NeoX client accepts our entity property stream cleanly, but never enters the Lobby

## What this is

A local-only, LAN-only private-server reimplementation of **Rules of Survival Mobile**
(`com.netease.chiji`, v1.610377.506841, arm64-v8a) for game preservation. The client is
a **BigWorld/Mercury**-derived engine (NetEase "NeoX") with an embedded **Python 2**
script layer. We run it in LDPlayer 9 and speak the Mercury protocol to it from a Python
server.

We are **not** asking for help bypassing DRM or attacking live servers — everything runs
against our own loopback server. What we want is help reasoning about a BigWorld entity
lifecycle that stalls.

## Where we are

Working end to end, all verified live:

- LoginApp (UDP :25000) Blowfish handshake, BaseApp (UDP :25010) reliable channel.
- `createBasePlayer(Account, type=38, eid=1)`, `Account.onChannelLogin`, `Account.onLogin`.
- `createBasePlayer(Athlete, type=51, eid=1)` **with a full 1585-byte property stream**.
- `Athlete.showSelectCharacter([])`, which preloads `HALL_BASE_SCENE` and spawns the
  `Scene` GameObject.
- Extended Mercury method-index wire encoding (for method indices >= 128).

We reversed the property-stream deserializer out of `libclient.so`:

- `EntityType::newDictionary` → for domain 0 it calls a deserializer with flag mask `0x0b`.
- That walks the entity's 832-entry property descriptor table (`EntityType+0x58`, `0x68`
  stride) and, for every property passing three flag-bit predicates
  (`(f & 0x10)==0 && (f & 0x08) && (f & 0x06)`), reads one value **sequentially** off the
  stream. **No presence bitmask, no per-property index tags** — a bare ordered
  concatenation, so one wrong width desynchronizes everything after it.
- That yields exactly **454** properties for our entity.
- Each descriptor's DataType pointer is at `+0x18`; its vtable identifies the wire type.
  13 vtables cover all of them (INT8/16/32/64, UINT8/32/64, FLOAT, STRING, BLOB, PYTHON,
  ARRAY, FIXED_DICT).

## The state we have reached

The stream is now **consumed perfectly**. In the latest run the client logged:

- 0 `SequenceDataType::createFromStream` errors
- 0 `PythonDataType::createFromStream` errors
- 0 `EntityDescription::readStream: Could not create <prop>` failures
- 0 `cPickle.UnpicklingError`
- 0 Python `Traceback`, 0 `TypeError`, 0 `AttributeError`
- no `Bundle::iterator::unpack` rejection

Server side, all five stages completed in ~3 seconds:

```
STAGE 1 createBasePlayer(Account type=38, eid=1)
STAGE 2 Account.onChannelLogin(idx=19) + Account.onLogin(idx=18)
STAGE 3 createBasePlayer(Athlete type=51, eid=1, stream=1585 B)
STAGE 4 Athlete.showSelectCharacter([]) idx=1083
STAGE 5 HOLDING
```

## The problem

**The client stays on the title screen.** It never enters the 3D Lobby.

Two observations that we think are the real clue, and which we cannot yet explain:

1. The logcat for that run contains **no entity-layer Python output whatsoever** — no
   `onCreate`, no `onBecomePlayer`, nothing from `entities\*.py`. The only `<SCRIPT>`
   lines are startup noise (patch check, language, loading panel).
2. It logs **`ServerConnection::createBasePlayer: id 1` only once**, where earlier runs
   logged it **twice** (once for the Account entity, once for the Athlete entity).

So it looks like the Athlete `createBasePlayer` is either not reaching the client, or is
being dropped before the script layer sees it — even though no error is printed.

### What changed between "entity layer ran" and "entity layer silent"

This is the confusing part, and the main thing we want a second opinion on.

| run | stream | client behaviour |
|:--|--:|:--|
| A | 1457 B, `None` for all PYTHON | entity layer **ran**; `onCreate` chain executed; `enterHall` executed and walked its own interface chain; but threw `AttributeError` on `hostID`, `baseLevel`, `childBaseClientPropertyList`, `hallTeamData` |
| B | 1457 B, protocol-1 `].`/`}.` for collections | `cPickle.UnpicklingError: bad pickle data`, then desync, then `Could not create childBaseClientPropertyList` |
| C | 1585 B, protocol-0 `(l.`/`(d.` for collections | **no errors at all**, but entity layer silent and no Lobby |

So making the stream *more* correct made the client *quieter* but stopped it advancing.

## Specific questions

1. In BigWorld, after `createBasePlayer` with a valid property stream, what else must the
   server send or acknowledge before the client will call `onBecomePlayer` / run the
   entity's Python `onCreate` and treat that entity as the player? Is there an
   `enableEntities`-style gate, or an ack the client waits for?
2. Is there a known size threshold where a `createBasePlayer` message is silently dropped
   rather than rejected with a Bundle error? We saw an explicit rejection at a 1751-byte
   payload (`Not enough data on stream at 2 for payload (1465 left, needed 1751)`) but no
   error at 1591 bytes. Could 1591 still be crossing a reliable-channel fragmentation
   boundary that we are not implementing, so the message is simply never reassembled?
3. Does BigWorld's Mercury split a single large message across packets, and if so what
   does the server have to emit (fragment flags, sequence numbers) for the client to
   reassemble it? We currently send `createBasePlayer` as one `sendto`.
4. Given run A reached `enterHall` but with missing attributes, and run C has a clean
   stream but no entity activity — is there a plausible single cause, or are these two
   independent problems?

## Constraints on any answer

- Please ground answers in BigWorld/Mercury protocol behaviour. We work to a strict
  zero-guesswork rule: every claim we act on has to be checkable against a decompile, a
  live memory read, or a captured log line, so please flag clearly which parts of your
  answer are established BigWorld behaviour and which are inference.
- We cannot read the game's Python source: `script.npk` is encrypted (3959 NXPK entries,
  every one beginning `7a 1c` followed by high-entropy bytes). We only see Python
  filenames and line numbers via tracebacks.
- Frida `attach()` fails on every process on this emulator (including benign ones), so
  runtime hooking is not currently available. Static analysis in Ghidra plus live
  `/proc/<pid>/mem` reads are what we have.

## What would help most

Concrete, checkable next steps: which BigWorld message or ack to look for, which function
in the client to decompile next, or a specific log string to grep for that would
distinguish "message never arrived" from "message arrived but entity activation gated".
