# ROS v1117219 — `LoginReplyRecord` / `LoginHandler::onLoginReply` Analysis

**Honesty note**: this task asked for the same byte-level rigor applied to `LogOnParams`
(see `LOGONPARAMS_SERIALIZATION.md`). That level was **not fully achieved** here in the
time available — the reply-handling function is larger, has more branches (multiple message
types / error paths interleaved), and its exact field layout requires more disassembly than
budget allowed. This document reports what was actually confirmed and is explicit about
what remains STRONG EVIDENCE / UNKNOWN, rather than restating the previous report's table
as fact.

## 1. Function Location (CONFIRMED)

- Region: approximately `0x938100`–`0x9385f8+` in `03_lib/libclient_arm64.so`.
- Located via xref to the string `"sending base app request to %s "` (rodata `0x2a49141`),
  single xref at `0x9384a0`. Full method: `scratch/xref_addtostream.py`-style ADRP/ADD scan
  (see `MERCURY_PACKET_MAP.md` §4 for the same technique applied here).
- This region also contains the strings (all confirmed present, verbatim, in this exact
  order in rodata starting at `0x2a49081`):
  ```
  LoginHandler::onLoginReply: after Endpoint::convertAddress from %s to %s
  LoginHandler::onLoginReply: Address::convertToIPV6  to %s
  LoginHandler::onLoginReply: change baseAddr from %s to %s
  sending base app request to %s
  LoginHandler::handleMessage: Got reply of unexpected size (%d)
  Mercury::REASON_CORRUPTED_PACKET
  Unspecified error.
  Unelaborated error.
  Unable t[o connect to BaseApp: A NAT or firewall error may have occurred?]
  ```
  This confirms the previous report's §4.1–4.2 function names and log strings **verbatim**.

## 2. What Is Actually Confirmed From Disassembly

| Finding | Address | Confidence |
|---|---|---|
| A 20-byte record is read from the incoming bundle via a stream-reader helper (`bl #0x989600`) | `0x938234` | CONFIRMED |
| 16 bytes of that record are stored as a single 128-bit load/store (`ldr q0` / `str q0`) into `this+0x50` | `0x93825c`/`0x938260` | CONFIRMED — size and alignment consistent with a `Mercury::Address`-class structure, but internal field layout (ip/port/family bytes) not decoded |
| A trailing 4-byte field from the same record is stored at `this+0x60` | `0x938258` | CONFIRMED |
| A 32-bit value is compared against the literal constant `0x32ef9816` | `0x938298`–`0x9382a4` | CONFIRMED (the compare exists); INFERRED that this is an interface-fingerprint/version hash, not a session key, based on BigWorld's standard fingerprint-guard pattern and the fact it gates an error-string log path, not further field parsing |
| Length-prefixed strings (identical SSO-string encoding to `LogOnParams`) are read and logged on certain branches | `0x938154`–`0x9381cc`, `0x9382a8`–`0x93831c` | CONFIRMED the read pattern exists; UNKNOWN whether these are protocol fields or purely diagnostic/error strings — the destination buffers (`this+0x68`, a stack temp at `x29-0x70`) look like scratch/log buffers, not permanent object fields, which suggests these are **error message text**, not `SessionKey`/`AccountID` |
| `Address::convertToIPV6` / `Endpoint::convertAddress` are invoked to normalize the BaseApp address after parsing | inferred from log strings + branch structure | STRONG EVIDENCE |

## 3. What Was NOT Confirmed (contradicts nothing, just unresolved)

The previous report's `LoginReplyRecord` table claimed three fields: `Mercury::Address`,
`SessionKey`, `AccountID`. Status after this pass:

| Field | Status |
|---|---|
| `Mercury::Address` (BaseApp IP/port) | STRONG EVIDENCE — a 20-byte address-shaped record is confirmed read and stored; exact sub-field layout (IPv4 vs IPv6, byte order, port position) is UNKNOWN |
| `SessionKey` | UNKNOWN — no field was identified in this pass that is clearly a symmetric session key. It is plausible this is folded into the same 20-byte record (e.g., last 4 bytes at `+0x60` could be a per-connection salt/key seed rather than "extra address data"), but this is speculation, not evidence. Needs further disassembly of what consumes `this+0x60` downstream (e.g., in the `BaseAppLoginRequest` construction — see `BASEAPP_LOGIN_SERIALIZATION.md`). |
| `AccountID` | UNKNOWN — not located in this pass. |

**Recommendation for continuation**: rather than re-guess a `LoginReplyRecord` byte layout,
the highest-value next step is to trace **what `this+0x50`, `this+0x60`, and the object
holding them are used for** in the subsequent `BaseAppLoginRequest` construction — the
consumer side will reveal which of these fields is treated as an address vs. a key vs. an
opaque token, since types of usage (passed to a socket-connect call vs. passed to an
encryption/HMAC routine) are much easier to distinguish than field names in a stripped
binary.

## 4. Classification Summary

- CONFIRMED: function location, log strings, 20-byte record read+store, fingerprint compare.
- STRONG EVIDENCE: the 20-byte record is a BaseApp network address.
- UNKNOWN: SessionKey and AccountID exact location/encoding — **not fabricated**, left
  explicitly open rather than copying the prior report's unverified claim forward.
