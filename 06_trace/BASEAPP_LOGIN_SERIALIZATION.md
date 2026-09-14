# ROS v1117219 — BaseApp Login Request (`baseAppLogin`) — Status

## Confirmed

- The Mercury method name `baseAppLogin` is the **first** entry in the client's
  `BaseAppExtInterface` method table, extracted verbatim from `libclient_arm64.so` rodata
  (see `MERCURY_PACKET_MAP.md` §2). This directly confirms the previous report's claim that
  a `BaseAppExtInterface::baseAppLogin` message exists and is the client's first message to
  BaseApp after the LoginApp handshake.
- `LoginHandler::onLoginReply` (see `LOGIN_REPLY_RECORD.md`) is confirmed to read a 20-byte
  address-shaped record and log `"sending base app request to %s "` immediately after
  processing the LoginApp reply, which is the observable trigger point for the BaseApp
  connection attempt.

## Not Completed In This Pass

The exact serialization of the `baseAppLogin` Mercury bundle (its argument list — session
key, account ID, entity-defs digest, etc.) was **not traced at the byte level**. This would
require:

1. Locating the `BaseAppLoginRequest` constructor and its `setNubAndSend()` / bundle-build
   code (the class name and `initNetwork`/`recreateListeningSocket` strings are confirmed
   present at rodata `0x2a48fdd`, but the actual field-serialization body was not
   disassembled in this pass).
2. Applying the same ADRP/ADD xref + prologue-boundary method used successfully for
   `LogOnParams::addToStream` (see `LOGONPARAMS_SERIALIZATION.md` §1) to find the function
   start/end.
3. Walking its vtable-dispatch writes the same way (each `blr` through a `BinaryOStream`
   vtable slot with a literal size in `w1`/`w2` reveals field boundaries, as demonstrated for
   `LogOnParams`).

**Do not treat any specific byte layout for `baseAppLogin` as confirmed** — none was
produced. This is flagged as the top-priority follow-up task (see
`LOCAL_SERVER_MINIMUM.md` §3, Stage 3).

## What This Means For Local-Server Feasibility

Because the reply-side consumer of `LoginReplyRecord`'s fields (`this+0x50`, `this+0x60`,
see `LOGIN_REPLY_RECORD.md`) has not been traced into the `baseAppLogin` bundle builder, we
cannot yet state with confidence:

- Whether the client re-sends a server-issued session key/token back to BaseApp for
  validation (typical BigWorld pattern — LoginApp issues a key, BaseApp verifies it matches
  what LoginApp told it out-of-band), which would require **any** local LoginApp/BaseApp
  pair to implement matching key-issuance and validation, OR
- Whether BaseApp trusts the LoginApp handoff implicitly (simpler — a local prototype could
  skip key validation entirely).

This is the single biggest open question standing between "we understand the login packet"
and "we can write a minimal local BaseApp that the real client will accept."
