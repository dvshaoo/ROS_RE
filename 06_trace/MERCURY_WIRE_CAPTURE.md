# ROS v1117219 — Mercury Wire-Level Capture (LoginApp Boundary)

**Result up front**: this pass obtained a **genuine kernel-level packet capture** (`tcpdump`
on the Android guest's `wlan0`) of a real login attempt, completely independent of
NativeBridge/Houdini — this sidesteps every in-process attribution problem from the prior
Stalker passes. The wire bytes are **byte-for-byte identical** to what our Python server
independently logged, in both directions. A controlled reply/no-reply A/B experiment shows
**client retry timing is completely unaffected by whether we reply at all**, which is new,
strong, and precisely bounded evidence about where the problem is *not*.
`LoginHandler::onLoginReply` was **not** observed to execute — no claim of reaching it is
made.

## 1. Environment (Verified Fresh, Not Assumed)

| Item | Value | How verified |
|---|---|---|
| Emulator/package | LDPlayer 9, `com.netease.chiji`, PID `16332` | `ps -A` on device, same PID as all recent sessions |
| Mercury login thread | TID `16424` | `logcat`'s own thread tagging on `logOnBegin`/`logOnComplete` lines |
| Guest IP | `172.16.1.15/24` on `wlan0` | `ip addr show` on device |
| Gateway (LoginApp test endpoint) | `172.16.1.2:25000` | `ip route`, matches `server_list_ad.txt` config from prior sessions |
| iptables OUTPUT DNAT | still active, `udp dpt:25000 → 172.16.1.2:25000` (30+ packets counted from prior sessions) | `iptables -t nat -L OUTPUT -n -v` |
| Host-side virtual adapter | **none found** — `Get-NetAdapter`/`Get-NetIPAddress` on the Windows host show no interface carrying `172.16.x.x` | Checked directly; LDPlayer's gateway is emulated entirely in userspace (slirp-style NAT), never appearing as a real Windows NIC — consistent with the client-observed source address `127.0.0.1` seen in all prior server-side capture logs |
| Capture method used | `tcpdump -i wlan0` **inside the Android guest**, root shell, writing a real `.pcap` file pulled via `adb pull` | This is the correct choice per the task's Phase 7 ordering — a genuine kernel-level capture, unrelated to NativeBridge, obtained on the first attempt (no fallback needed) |
| Ports captured | `udp port 25000 or udp port 25010` | tcpdump filter |

**Phase 1 conclusion**: the Android kernel's own `wlan0` capture point is the correct, least
invasive, and successful boundary. A host-side capture was not attempted because it isn't
necessary (the guest-side capture already succeeded and is closer to the actual traffic
origin) and because no real host NIC carries this traffic to capture on in the first place.

## 2. Packet Timeline (Real Capture, `wire_capture.pcap`, Reply Enabled)

All timestamps relative to packet 0 (which itself lands within ~1ms of `logcat`'s
`ServerConnection::logOnBegin` line, `22:17:08.647` vs. pcap `22:17:08.6486` — direct,
precise timestamp correlation, not an assumption).

| # | t (s) | Direction | Src | Dst | Len | Packet ID |
|---|---|---|---|---|---|---|
| 0 | 0.000 | C→S | 172.16.1.15:26684 | 172.16.1.2:25000 | 273 | P1 |
| 1 | 0.002 | S→C | 172.16.1.2:25000 | 172.16.1.15:26684 | 22 | P2 |
| 2 | 0.428 | C→S | (same) | (same) | 273 | P3 |
| 3 | 0.429 | S→C | | | 22 | P4 |
| 4 | 0.858 | C→S | | | 273 | P5 |
| 5 | 0.859 | S→C | | | 22 | P6 |
| 6 | 1.288 | C→S | | | 273 | P7 |
| 7 | 1.290 | S→C | | | 22 | P8 |
| 8 | 1.718 | C→S | | | 273 | P9 |
| 9 | 1.719 | S→C | | | 22 | P10 |
| 10 | 2.147 | C→S | | | 273 | P11 |
| 11 | 2.149 | S→C | | | 22 | P12 |
| 12 | 2.577 | C→S | | | 273 | P13 |
| 13 | 2.578 | S→C | | | 22 | P14 |
| 14 | 3.007 | C→S | | | 273 | P15 |
| 15 | 3.008 | S→C | | | 22 | P16 |
| 16 | 3.437 | C→S | | | 273 | P17 |
| 17 | 3.439 | S→C | | | 22 | P18 |
| 18 | 3.868 | C→S | | | 273 | P19 |
| 19 | 3.870 | S→C | | | 22 | P20 |
| *(none)* | 3.870–~8.99 | *(silence — no packets at all)* | | | | |
| — | ~8.997 | `Mercury::REASON_TIMER_EXPIRED` (native log, not a packet) | | | | |

**CONFIRMED**: exactly **10 request/reply pairs**, at a **remarkably constant ~0.43s
interval** (0.428, 0.430, 0.430, 0.430, 0.429, 0.430, 0.430, 0.430, 0.430s between
successive client sends — essentially a fixed timer, not exponential backoff). Round-trip
time for our reply is **1–2ms** (packet 1 arrives 2ms after packet 0 — local relay, as
expected). The client reuses the **same source port (`26684`)** for every retry — a single
persistent UDP socket, not rebound per attempt.

**New, precise finding not previously established**: after the 10th request at t=3.868s,
**there is complete network silence for ~5.1 seconds** before `logOnComplete` fires at
~8.997s total. This means retransmission is capped at (or naturally stops after) 10
attempts over ~3.9 seconds, followed by a separate ~5.1-second "wait before giving up"
period with zero further network activity — two distinct timers, not one.

## 3. Raw Packet Hex

**P1 (first real client request, 273 bytes)**:
```
01000004018cd1000000002b0000008ec7316b7cccb79aeaec93cf19e82a2aa3088e7db66f91e131ef0190845a22f1aebdb6e7a93b101611bbaa1f91a69ec2fa9ec6b33f6e6f5e343cbc26e893c68b2cb5599f368a97c4804910f9f17d695396ee32d827df9ee3956e19478161d5e40727b8908b39d4ba5e9d65364df75058e44b953225b384657a733838d327040c2647fe68ee0c29006b74431f0c81287ca42531eed8a6c19252ffabbcb7af49ba12c7d19bfdf367048dfbabf5ce14269a6569d0e0b196e80da5eca50ce0e1e162285338de005eecd4de1964a64bd3b4b387e7d0d80e405a48a9a4d0072ef5beea98bbcc5a22996f98bc6b18834a094898f3b8a61b9b34d37814d60cff972beaaf0200
```
Framing (unchanged from `PLAY_TO_BASEAPP_CAPTURE.md` §2, now re-confirmed on a fresh,
independently-captured packet): `01 00 00 04` / `01` / 2-byte incrementing value (`018c` →
LE `0x8c01`... consistently incrementing per retry) / `00 00 00 00` / `2b 00 00 00` (43) /
256-byte RSA-2048 ciphertext / `02 00` footer.

**P2 (our reply, 22 bytes, as it actually arrived at the client)**:
```
ac10010261b20000ac10010261b20000785634120000
```
Identical, byte-for-byte, to what `mitm/local_baseapp_capture.py` logged as sent.

## 4. Request Comparison — Wire Capture vs. Server-Received vs. Prior Session

Directly diffed packet 4 (index 4 in the pcap, sequence `018e`) against the corresponding
line in `mitm/captures/BASEAPP_LOGIN_CAPTURE.txt`:

```
Wire (tcpdump, guest kernel):
  01000004018ed1000000002b0000006df5a0fff05d30fa67213ae1a46e439f64d56d6033825defd849c2bf...

Server log (mitm/local_baseapp_capture.py, independent process on the Windows host):
  01000004018ed1000000002b0000006df5a0fff05d30fa67213ae1a46e439f64d56d6033825defd849c2bf...
```

**CONFIRMED IDENTICAL**, full 273 bytes, both directions of comparison checked. This
formally establishes: **client wire packet == server-received packet.** Nothing in the
local network path (guest kernel → LDPlayer's userspace NAT → Windows host → Python socket)
alters the bytes. The framing structure (header shape, 256-byte RSA block, footer) also
exactly matches the `271f275`-session capture's shape, confirming that finding was not an
artifact of the earlier capture method.

## 5. Reply Comparison — What We Send vs. What Arrives

```
Server log (sendto() call in Python): ac10010261b20000ac10010261b20000785634120000
Wire (tcpdump, packet as it left the guest's kernel toward the app):
                                       ac10010261b20000ac10010261b20000785634120000
```

**CONFIRMED IDENTICAL.** Our 22-byte reply reaches the guest, at the network level,
completely unmodified. This rules out the local network/NAT path as a source of corruption
— whatever causes rejection happens **inside the client application itself**, not in
transit.

## 6. Retry/Timeout Behavior — Reply vs. No-Reply Control Experiment

A second full capture was taken with the LoginApp responder's `sendto()` call disabled
(`NO_REPLY=1` environment flag added to `mitm/local_baseapp_capture.py` for this
controlled test) — the client's UDP packets still arrive at our listener (confirmed via its
own `RECV` log lines) but nothing is sent back.

| | With reply (P1-P20 above) | No reply (control) |
|---|---|---|
| Number of client requests | 10 | **10** |
| Retry timestamps (s) | 0, .428, .858, 1.288, 1.718, 2.147, 2.577, 3.007, 3.437, 3.868 | 0, .429, .859, 1.288, 1.720, 2.148, 2.578, 3.008, 3.438, 3.868 |
| Source port reused | yes (`26684`) | yes (`35268`) |
| `logcat` outcome | `Mercury::REASON_TIMER_EXPIRED` at +8.995s | `Mercury::REASON_TIMER_EXPIRED` at +8.997s |

**CONFIRMED**: the retry count, cadence, and overall timeout are **indistinguishable**
between "we reply every time" and "we never reply at all." The two timing sequences agree
to within 2ms at every single retry point — well within normal scheduling jitter. This is
a controlled, reproducible result (both captures independently show exactly 10 attempts at
~0.43s intervals, then ~5.1s of silence, then the same error).

**What this proves**: the client's retransmission schedule is **not adaptively driven by
reply receipt** in any way that produces observable behavioral difference — it fires the
same fixed burst of packets whether or not anything answers. This does **not** tell us
whether our reply is received-and-rejected vs. dropped even earlier (that still requires
in-process visibility this project's tools cannot currently obtain — see
`MERCURY_STALKER_COMPILE_TRACE.md` §9). What it **does** rule out: any theory in which a
correctly-shaped-but-imperfect reply would at least *delay* or *reduce* retransmissions
(e.g., "reply is read far enough to reset a keepalive timer, then rejected later"). No such
effect is observed — CONFIRMED, not merely inferred.

## 7. Client-Side Behavior After Receiving the Reply (Phase 5)

From the wire capture: after **every single** P2/P4/P6/.../P20 reply, the client's **only**
subsequent action is to resend the **exact same class of packet** (P3, P5, ..., a fresh
273-byte `LogOnParams` request with an incremented 2-byte field) at the next scheduled
retry tick. **No distinct acknowledgment packet, no different-sized packet, no packet to a
different port** was observed at any point in either capture. Neutral labeling per the
task's instruction:

```
P1  client->server  (273 bytes)
P2  server->client  (22 bytes)
P3  client->server  (273 bytes)   <- structurally identical class to P1, not a new message type
P4  server->client  (22 bytes)
...
```

Byte-level comparison across `P1, P3, P5, ..., P19` (all client→server): the **only**
bytes that change between them are (a) the 2-byte field at offset `[5:7]` (increments by
`0x0100` in little-endian terms each time — i.e., byte 5 increments by 1, consistent across
both this and the prior session's captures) and (b) the 256-byte RSA ciphertext block
(expected to differ every time due to OAEP's randomized padding, even if the underlying
plaintext is identical). **Every other byte position — the `01 00 00 04`/`01` prefix, the
4 zero bytes, the `2b 00 00 00` length-shaped field, and the `02 00` footer — is
bit-for-bit constant across all 10 retries in both captures.** This is now confirmed across
two independent capture sessions (this pass and the `271f275` session), not a one-off
observation.

## 8. Correlation With Prior Static/Dynamic Findings (Phase 6)

- **`VARIABLE_LENGTH_MESSAGE`/`u16` length prefix** (`MERCURY_LOGIN_FLOW.md`,
  `BASEAPP_LOGIN_SERIALIZATION.md`): this wire capture is of the **LoginApp** leg
  (`LogOnParams`), not `baseAppLogin` — that framing finding remains untested by this
  capture and is neither confirmed nor contradicted here.
- **Footer behavior / sequence fields** (`LOGIN_REPLY_MERCURY_ENVELOPE.md` §2): the wire
  evidence is **consistent with** a footer-style trailing constant (`02 00`) but does not
  newly confirm the specific BigWorld flag-bit semantics claimed there — this capture adds
  precision (exact byte offsets, exact constancy across retries) without proving the
  semantic labels (`flags`, `checksum`, etc.) previously assigned to those byte ranges.
  Those labels remain STRONGLY SUPPORTED at best, not CONFIRMED, per that document's own
  standard.
- **32-bit reply-id correlation model** (`MERCURY_REPLY_DISPATCH_TRACE.md` §4): no wire
  evidence either confirms or refutes this — our reply contains no such field by
  construction (it is the pre-existing 20-byte body + `0000` footer), and the client's
  observed behavior (§6) does not distinguish "reply lacks the expected id" from "reply
  rejected for any other reason."
- **`LoginHandler::onLoginReply`/`processFilteredPacket`/`handleMessage`**: **no evidence
  either way**. This capture cannot see inside the process — it only proves what crosses
  the network boundary, which is now fully accounted for (§4, §5).

**No earlier hypothesis was contradicted by this wire evidence** — everything observed is
consistent with (though does not newly prove) the existing model. This is stated plainly
per the task's instruction not to force the data into the old model where it doesn't fit,
and it genuinely does fit without needing to be forced.

## 9. Evidence-Based Conclusions

**CONFIRMED**:
- Exact network path: guest `wlan0` (`172.16.1.15`) → LDPlayer userspace NAT (no real host
  NIC involved) → Windows Python socket (`172.16.1.2:25000` mapping via iptables DNAT).
- Client wire packet == server-received packet, byte-for-byte, both directions.
- Retry cadence: exactly 10 attempts at ~0.43s intervals, then ~5.1s of silence, then
  `Mercury::REASON_TIMER_EXPIRED` at ~9.0s total — reproduced identically across two
  independent capture sessions.
- Retry behavior is **completely unaffected** by whether a reply is sent at all (reply vs.
  no-reply control experiment, byte-identical timing to within 2ms).
- Only two byte ranges vary across retries in the client's request: the `[5:7]` counter and
  the 256-byte ciphertext (expected for OAEP); every other byte is constant.
- Client reuses a single source port across all retries (no socket rebinding).

**STRONGLY SUPPORTED** (consistent with wire evidence, not newly proven by it):
- The `01 00 00 04` / `01` / counter / `00000000` / `2b000000` header shape and `02 00`
  footer are genuine, stable Mercury/engine framing (now seen identically across two
  independent sessions' captures) — but their semantic meaning (which byte is "flags,"
  which is a "reply id," etc.) remains an open question this capture does not resolve.

**UNKNOWN**:
- Whether our reply is received by the application and rejected, or discarded before
  reaching any Mercury-level logic at all.
- Whether `LoginHandler::onLoginReply` executes on any attempt — **not claimed**, no
  evidence obtained either way.
- The reason retransmission stops at exactly 10 attempts, and the reason for the ~5.1s
  additional wait before the final timeout (two distinct constants, source not identified).

## 10. Next Blocker

The **smallest remaining unknown** is: **whether the client's UDP receive call
(`recvfrom`/equivalent) is ever invoked with our reply's bytes at all.** This wire capture
proves the bytes arrive at the guest's network stack — it cannot prove they are read by the
application layer (that boundary is exactly where all prior in-process instrumentation
attempts — `libc.so` hooks, raw ARM64 address hooks, Stalker `call`/`compile` events, Java
`DatagramSocket` hooks — have each independently failed or come up empty, for the
reasons documented in `MERCURY_STALKER_COMPILE_TRACE.md`). Confirming or refuting that one
fact would immediately resolve the A/B/C/D distinction from
`LOGIN_REPLY_MERCURY_ENVELOPE.md` §6. No new instrumentation method is proposed here per
this task's explicit scope (wire capture only) — this is named as the next blocker for a
future pass, not attempted in this one.
