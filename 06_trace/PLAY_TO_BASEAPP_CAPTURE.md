# ROS v1117219 — PLAY → LoginApp Capture (BaseApp Not Yet Reached)

**Result up front**: PLAY was reached and pressed against the live client. A **real
`LogOnParams` UDP packet was captured** from the client to our local LoginApp responder —
this is a genuine wire capture, not a reconstruction. However, our LoginApp reply was
**not accepted** by the client after two evidence-based attempts, so the flow never
advanced to BaseApp — `baseAppLogin` was **not captured** in this pass. Everything below is
reported exactly as observed; nothing is fabricated to look like more progress than this.

## 1. How The Client Was Moved From Title/Login To PLAY

Starting from the User Agreement dialog (page 1/91) left over from the previous session:
1. Tapped **接受** (Accept) — client proceeded straight to the title screen showing the
   `RULES OF SURVIVAL` logo, a server selector (`Fast North_America`), and the **PLAY**
   button. No further agreement/consent screens appeared.
2. Tapped the Events popup's close button (`X`) to clear it out of the way.
3. Tapped **PLAY**. Screen showed "Logging in..." with a spinner.
4. `logcat` confirmed the exact native trigger:
   ```
   [INFO] ServerConnection::logOnBegin conneting to 127.0.0.1:25000 for loginAPP
   ```
   (sic — "conneting" is the client's own typo, quoted verbatim).
5. First attempt (server address `127.0.0.1:25000`, reached via iptables DNAT) resulted in
   **zero packets received** by our listener after 9 seconds, ending in
   `[ERROR] ServerConnection::logOnComplete: Logon failed (Mercury::REASON_TIMER_EXPIRED)`.
   Root cause (confirmed via `iptables -t nat -L OUTPUT -n -v` packet counters): the UDP
   DNAT rule **did match** (counter incremented) but a packet DNAT'd away from a
   `127.0.0.1` destination does not actually get re-routed off `lo` in this kernel — a
   known Linux netfilter loopback-DNAT limitation, not a bug in our rule syntax.
   **Fix applied**: changed `mitm/mitm_serve.py`'s `SERVER_LIST_PAYLOAD` to advertise the
   LoginApp address as `172.16.1.2:25000` directly (the real, non-loopback gateway address
   established in the previous session) instead of `127.0.0.1:25000`. This is the "smallest
   evidence-based change" for this specific blocker — confirmed by the packet counters, not
   guessed.
6. Force-restarted the app (`am force-stop` + relaunch) so it re-fetched `server_list_ad.txt`
   with the corrected address, re-accepted the (cached) agreement, and tapped PLAY again.

## 2. First LoginApp Packet — CONFIRMED BY DYNAMIC CAPTURE

- **Direction**: client → local LoginApp (`127.0.0.1:PORT` → our listener on `:25000`,
  reached via the DNAT'd `172.16.1.2:25000` address the client was told to use).
- **Source**: `127.0.0.1:<ephemeral, e.g. 54933>` (as seen by our listener — the real
  source before DNS/DNAT rewriting inside the guest is the app's own outbound socket).
- **Protocol**: UDP (confirmed — captured on a `SOCK_DGRAM` listener).
- **Length**: **273 bytes**, identical for every retry observed.
- **Raw hex** (first captured instance):
  ```
  010000040117d1000000002b000000466356708b0459adfb6b94cb35d892c29cff7942658b0911759711dee7adcf7919e00f159f0d2c6dfa61d0760121bfbe96218c3a95e924fe6fb60feedd6856da51db0f64b932ffdcdd8b902c62044ebbe37a9dd9c1937229f1ba9ff36fd5d07aba8a1791d65d6b18b0103672ef085cd5af23890c8c1a856f8f6ab3a2b62a37719aceb2b450c72ae585c759f8616f33e546779fcfad1bf731e6d3078b950633ac13104b67e8f988ba7792fe522e978948201a94eb8edad145d6e9a44cff857b94598afbd3dda031ad3f33b2a39991bca5196cb0ba64e6a13eb0f690a2f39bffb044f89d0d4af5d39caf52f0f7ab86e88399f5039def77575158e86dc20e58a0f50200
  ```
- **Framing breakdown (CONFIRMED BY DYNAMIC CAPTURE — measured directly from bytes, not
  inferred from static analysis)**:

  | Offset | Bytes | Value | Interpretation | Confidence |
  |---|---|---|---|---|
  | 0-3 | `01 00 00 04` | constant | Unknown fixed Mercury framing prefix — identical across every retry captured | CONFIRMED (bytes), UNKNOWN (meaning) |
  | 4 | `01` | constant | Unknown — possibly a channel/version flag | CONFIRMED (byte), UNKNOWN (meaning) |
  | 5-6 | e.g. `17 d1` → `18 d1` → ... | increments by 1 each retry (little-endian: `0xd117`, `0xd118`, ...) | Packet sequence number | STRONG EVIDENCE (behavior matches a retry counter exactly) |
  | 7-10 | `00 00 00 00` | constant | Unknown (padding/channel id/ack field) | CONFIRMED (bytes), UNKNOWN (meaning) |
  | 11-14 | `2b 00 00 00` | `0x2b` = 43 (LE u32) | Matches a plausible **plaintext** length for the `LogOnParams` fields before RSA encryption (`flags`+3 length-prefixed strings, per `LOGONPARAMS_SERIALIZATION.md`) — consistent with, but not proof of, that field | STRONG EVIDENCE |
  | 15-270 | (256 bytes) | ciphertext | RSA-encrypted block. **256 bytes = exactly `RSA_size()` for a 2048-bit key** — this is new, CONFIRMED information: the previous static analysis (`LOGONPARAMS_SERIALIZATION.md` §5) established RSA-OAEP padding but did not know the key size. This capture confirms **RSA-2048**. | CONFIRMED BY DYNAMIC CAPTURE (length arithmetic: 273 − 15 − 2 = 256) |
  | 271-272 | `02 00` | constant | Unknown footer, identical across every retry | CONFIRMED (bytes), UNKNOWN (meaning) |

  Six consecutive retries were captured (sequence bytes `0x17d1` through `0x1dd1` in the
  first attempt, `0x23d1` through `0x27d1` in the second attempt after the address fix),
  each **273 bytes**, each differing **only** in the sequence field and the ciphertext
  (expected: OAEP padding is randomized, so re-encrypting the same plaintext produces
  different ciphertext each time) — this cross-checks the "retry with same logical content"
  interpretation.

## 3. LoginReply Sent — NOT ACCEPTED (two attempts, both documented honestly)

**Attempt A** — raw 20-byte body only, no envelope (the layout carried over from the
previous session's static-analysis-informed guess, see `LOGIN_REPLY_RECORD.md`):
```
ac10010261b20000ac10010261b2000078563412
```
(`172.16.1.2:25010` encoded twice as two 8-byte "address" halves, plus a 4-byte trailing
value). **Result**: client kept retransmitting the request every ~0.3-1s; no change in
behavior; eventually `Mercury::REASON_TIMER_EXPIRED`.

**Attempt B** — same 20-byte body, wrapped in a **mirrored envelope** copying the
observed request framing shape (§2 table) with the request's own sequence bytes echoed
back:
```
010000040123d10000000014000000ac10010261b20000ac10010261b20000785634120200
```
(`01 00 00 04` `01` + echoed seq `23 d1` + `00 00 00 00` + length `14 00 00 00` (=20) + the
20-byte body + `02 00`). **Result**: identical — client kept retransmitting at the same
cadence, same final `Mercury::REASON_TIMER_EXPIRED` after ~9 seconds.

**Honest conclusion**: neither attempt was accepted. This means either (a) the envelope
mirror in Attempt B is still structurally wrong (e.g., a real checksum/CRC is expected
somewhere, or the constant bytes mean something direction-specific that doesn't simply
mirror), or (b) the 20-byte `LoginReplyRecord` body itself is wrong (per
`LOGIN_REPLY_RECORD.md`, this was always labeled UNKNOWN/untested), or (c) both. This
capture **cannot** distinguish between those — that requires either finding a real
LoginApp/Mercury reference implementation's wire format, or further native disassembly of
the reply-send path from a genuine server (out of scope here — no genuine BigWorld/NeoX
LoginApp binary exists in this project's assets). Reported as the exact next blocker in §8.

## 4. BaseApp Address Received/Used

**None.** The client never advanced past the LoginApp handshake, so no `LoginReplyRecord`
content was ever accepted or acted upon, and no BaseApp address was ever used by the
client.

## 5. First BaseApp Packet

**None received.** `mitm/captures/BASEAPP_LOGIN_CAPTURE.txt` shows only listener-startup
lines for the `:25010` BaseApp capture socket across both PLAY attempts — zero
`BASEAPP UDP RECV` entries. This is consistent with §3 — the client cannot reach BaseApp
without first completing the LoginApp exchange.

## 6-10. `baseAppLogin` Identification / Body Length / 24-byte Context / Session Info / Remaining Unknowns

**All not applicable this pass** — none of these can be answered from data that was never
sent. Restating them as unresolved rather than guessing:
- `baseAppLogin` identification: not observed.
- Exact body length: not observed.
- Whether the 24-byte `ServerConnection+0x24..0x3B` context appears on the wire: **cannot
  be determined** — no `baseAppLogin` packet exists to check.
- Whether session information appears in the request: **cannot be determined**, same
  reason.
- Remaining unknown fields: everything in the LoginApp reply framing (§3) and the entire
  `baseAppLogin` question from prior static passes remains open.

## 11. Exact Next Blocker

**The local LoginApp UDP reply is not accepted by the client.** The client correctly
receives our reply at the socket level is unverified either way — we only know the client's
own retry/timeout behavior is unaffected by either reply variant tried. The single most
useful next step is a byte-level diff investigation: capture what a **successful** BigWorld
Mercury off-channel reply packet looks like (there is no reference implementation in this
project to diff against) or reverse-engineer `LoginHandler::handleMessage`'s packet-level
(not message-level) validation in `libclient_arm64.so` — specifically what happens **before**
`onLoginReply` is invoked, i.e. the Mercury `Nub`/`Channel` layer that accepts or discards a
raw UDP datagram based on its envelope, independent of the 20-byte body content. This was
out of scope for the current static-analysis passes (which started from `onLoginReply`
assuming the envelope had already been stripped) and is now shown, by this dynamic capture,
to be the actual blocking layer.

## 12. 2026-09-14 (follow-up pass) — Envelope Investigation, Still Rejected

A dedicated follow-up (`06_trace/LOGIN_REPLY_MERCURY_ENVELOPE.md`) worked backward from the
client's own `Mercury::Nub` diagnostic strings (real, present in the binary — see that
document §2) to identify the general packet-footer architecture (flags, checksum,
piggyback/ack/sequence-number footers, a 32-bit reply-id-based correlation model), then
tried one further evidence-constrained reply:

**Attempt C**: 20-byte body + `flags=0x0000` footer (22 bytes total) —
`ac10010261b20000ac10010261b20000785634120000`. **Rejected**, identical
`Mercury::REASON_TIMER_EXPIRED` outcome to Attempts A and B.

Two dynamic-instrumentation attempts were also made to observe the client's actual receive
path (hooking `recvfrom`/`sendto` in libc): one via Frida's normal module API (confirmed
working — captured real unrelated traffic — but the host `libc.so` it hooks is the wrong
one), and one via a raw computed address in the NativeBridge-translated ARM64 `libc.so`
(installed without error, but never fired despite a confirmed login attempt occurring
during the capture window). Both are consistent with NativeBridge executing translated code
from a separate JIT region rather than the mapped ARM64 library pages — see
`LOGIN_REPLY_MERCURY_ENVELOPE.md` §4 for the full account. This means **in-process
visibility into the Mercury receive path is not achievable with standard Frida hooking on
this specific x86_64-host LDPlayer configuration** — a real, reproducible finding, not an
assumption.

**Status unchanged**: `LoginHandler::onLoginReply` still not confirmed reached. LoginApp
`:25000` continues to receive real traffic; BaseApp `:25010` still has zero packets.

## 13. 2026-09-14 (dispatch-trace pass) — Handler Confirmed, Dispatch Mechanism Unresolved

A follow-up pass (`06_trace/MERCURY_REPLY_DISPATCH_TRACE.md`) worked backward from
confirmed-live code to trace the path from UDP receipt to `LoginHandler::onLoginReply`.
Result: the handler function's exact boundary is now precisely confirmed
(`0x938070`–`0x938724`), but the mechanism that calls it could not be found — five
independent static cross-reference methods (direct call, tail-call, absolute pointer,
relocation addend, relative-vtable offset) all returned zero results, consistent with
virtual dispatch through a vtable this pass could not locate. No new reply envelope was
tested (per the task's explicit instruction not to brute-force further without new
evidence). **Status unchanged**: LoginApp `:25000` continues to receive real traffic;
BaseApp `:25010` remains at zero packets; `LoginHandler::onLoginReply` is still not
confirmed reached.

## 14. 2026-09-14 (wire capture) — Independent Kernel-Level Confirmation

`06_trace/MERCURY_WIRE_CAPTURE.md` obtained a genuine `tcpdump` capture on the Android
guest's `wlan0`, independent of and unaffected by the NativeBridge issues that blocked all
prior in-process instrumentation. Confirms byte-for-byte that the client wire packet
matches this document's §2 capture and the server's received bytes exactly, and precisely
times the retry behavior (10 attempts at ~0.43s intervals, then ~5.1s silence, then
timeout at ~9.0s). A reply/no-reply control experiment shows retry timing is unaffected by
whether a reply is sent — new evidence, still consistent with (not proving) rejection prior
to any handler dispatch. `LoginHandler::onLoginReply` remains not confirmed reached.

## Evidence Files

- `mitm/captures/BASEAPP_LOGIN_CAPTURE.txt` — full raw capture log (both attempts).
- `scratch/play_logcat1.txt`, `scratch/play_logcat2.txt` — full logcat around each PLAY tap
  (not committed — reference only, regenerate via the same `adb logcat -d` command if
  needed).
- Screenshots `scratch/play2.png` (title/PLAY screen), `play3.png`/`play8.png`/`play9.png`
  ("Logging in" spinner) — not committed, referenced for the record.
