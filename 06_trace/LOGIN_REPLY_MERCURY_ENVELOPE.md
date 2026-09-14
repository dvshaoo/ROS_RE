# ROS v1117219 — Mercury LoginReply Envelope Investigation

**Result up front**: the exact wire format the client will accept for a LoginApp reply was
**not determined** in this pass. Three evidence-informed candidate envelopes were tried
against the real, captured client request and all three were rejected identically
(`Mercury::REASON_TIMER_EXPIRED`). Two independent investigation avenues — static
cross-reference analysis and dynamic instrumentation — both hit genuine, well-documented
technical obstacles that are reported honestly below rather than papered over with more
guesses. `LoginHandler::onLoginReply` was **not** confirmed reached.

## 1. Exact Request Envelope (CONFIRMED BY DYNAMIC CAPTURE — carried over, not re-derived)

Unchanged from `PLAY_TO_BASEAPP_CAPTURE.md` §2 — reproduced here for reference since this
document compares candidate replies against it:

```
273 bytes total:
  [0:4]    01 00 00 04        constant, every retry
  [4]      01                 constant, every retry
  [5:7]    <2-byte LE>        increments by 1 each retry (e.g. 0x17d1, 0x18d1, ...)
  [7:11]   00 00 00 00        constant, every retry
  [11:15]  2b 00 00 00        constant = 43 (LE u32), every retry
  [15:271] <256 bytes>        RSA-2048-OAEP ciphertext, DIFFERENT every retry (OAEP padding is randomized)
  [271:273] 02 00             constant, every retry
```

## 2. Static Analysis: Mercury `Nub`/`Channel` Packet-Validation Architecture (STRING EVIDENCE)

`03_lib/libclient_arm64.so` contains an extensive, coherent set of `Mercury::Nub`
diagnostic strings (~40+, all in rodata `0x2a5cd00`-`0x2a5e400`) that describe a classic
BigWorld-style Mercury packet/footer architecture. These are **real strings physically
present in this binary** — not assumed from generic public BigWorld documentation — and
they are quoted verbatim below because their exact wording and implied ordering is the
evidence:

```
Mercury::Nub::Nub: couldn't create a socket
Mercury::Nub::Nub: couldn't bind the socket to %s (%s)
Nub::processPendingEvents: Throwing REASON_GENERAL_NETWORK (1). recvFromEndpoint(-1)_- %s
Nub::processPacket( %s ): Ignoring incoming packet on recently dead channel
Nub(%p)::processFilteredPacket( %s ): received packet with bad flags %x
Nub::processFilteredPacket( %s ): Got FLAG_CREATE_CHANNEL on external nub
Nub::processFilteredPacket( %s ): received undersize packet (%d bytes)
Nub::processFilteredPacket( %s ): Packet too short (%d bytes) for checksum!
Nub::processFilteredPacket( %s ): Packet (flags %hx, size %d) failed checksum (wanted %08x, got %08x)
Nub::processFilteredPacket( %s ): Not enough data for piggyback length (%d bytes left)
Nub::processFilteredPacket( %s ): Got an exception whilst processing piggyback packet: %s
Nub::processFilteredPacket( %s ): Got indexed channel packet with no finder registered
Nub::processFilteredPacket( %s ): Not enough data for indexed channel footer (%d bytes left)
Nub::processFilteredPacket( %s ): Not enough data for ack count footer (%d bytes left)
Nub::processFilteredPacket( %s ): Packet with FLAG_HAS_ACKS had 0 acks
Nub::processFilteredPacket( %s ): Not enough footers for %d acks (have %d bytes but need %d)
Nub::processFilteredPacket( %s ): Not enough data for sequence number footer (%d bytes left)
Nub::processFilteredPacket( %s ): Dropping packet due to illegal request for reliability without related sequence number
Nub::processFilteredPacket( %s ): Dropping illegal once-off-reliable packet
Nub::processPacket( %s ): Not enough data for first request offset (%d bytes left)
Nub::processPacket( %s ): Not enough footers for fragment spec (have %d bytes but need %d)
Nub::processOrderedPacket( %s ): Discarding bundle after hitting unhandled message id %d
Nub::processOrderedPacket( %s ): Discarding bundle due to corrupted header for message id %d
Mercury::Nub::handleMessage( %s ): received the wrong kind of message!
Mercury::Nub::handleMessage( %s ): received a corrupted reply message (length %d)!
Mercury::Nub::handleMessage( %s ): Couldn't find handler for reply id 0x%08x (maybe it timed out?)
Mercury::Nub::handleMessage: Got reply to request %d from unexpected source %s
N4neox8bwclient7Mercury23NubExceptionWithAddressE
N4neox8bwclient7Mercury12NubExceptionE
N4neox8bwclient7Mercury3NubE
N4neox8bwclient7Mercury3Nub19ReplyHandlerElementE
```

### 2.1 What This Evidence Establishes (and at what confidence)

| Claim | Confidence | Reasoning |
|---|---|---|
| The client links a real, non-trivial `neox::bwclient::Mercury::Nub` class (RTTI-confirmed: `N4neox8bwclient7Mercury3NubE`) with `Channel`, `ReplyHandlerElement`, and exception-handling support | CONFIRMED BY BINARY (RTTI strings are unambiguous — a real class of this exact name exists in this binary) | — |
| Incoming packets go through `processFilteredPacket`, then (if they pass) `processPacket` → `processOrderedPacket` → `handleMessage` | STRONG EVIDENCE (ordering inferred from typical validation logic implied by the message wording — "bad flags" and "undersize" are checked first, "checksum" next, footers after, message-id dispatch last) | This is a plausible, self-consistent ordering matching the diagnostic text itself, but the exact call graph was not traced instruction-by-instruction (see §3) |
| Packets carry a `flags` field, checked for validity in `processFilteredPacket` | STRONG EVIDENCE | Explicit string: "received packet with bad flags %x" |
| An optional checksum exists, described as `(flags %hx, size %d) failed checksum (wanted %08x, got %08x)` — a 32-bit value (`%08x`) | STRONG EVIDENCE | Directly quoted string; `%08x` implies a 4-byte (or at least 32-bit-printed) checksum |
| Optional footers, in some order, include: piggyback data, ack count + acks, indexed-channel id, fragment spec, sequence number, and "first request offset" | STRONG EVIDENCE for existence and rough order; **UNKNOWN for exact bit flag values, byte widths, and byte order** | The strings describe each footer's *presence check* ("not enough data for X footer") but never state size or bit value directly, except by generic implication |
| Reply correlation uses a "reply id" the client can fail to find a handler for (`"Couldn't find handler for reply id 0x%08x"`) — implying replies are matched by a 32-bit request/reply id, not by echoing the request's own sequence bytes | STRONG EVIDENCE | Directly quoted string, `%08x` implies 4 bytes |
| Source-address checking exists: `"Got reply to request %d from unexpected source %s"` — a reply from the wrong IP:port for a given pending request id is rejected | STRONG EVIDENCE | Directly quoted string |

**This is new, real information not available before this pass**: it tells us the client's
reply-matching model is keyed by a **32-bit reply/request id** (not the small 2-byte value
we identified in the request header at bytes[5:7], which is more likely a lower-level
packet sequence number, a *different* concept in Mercury's design), **and** it checks the
reply's source address against the address the original request was sent to. Both of our
three tested reply attempts came from our LoginApp responder's own bound socket replying to
the exact source address/port the request came from, so the source-address check should
have passed in all three attempts — the rejection is therefore more consistent with a
flags/checksum/footer-level failure, or a missing/incorrect 32-bit reply-id we never
supplied at all (none of our three attempts included a distinct 32-bit id anywhere in the
20-byte body).

## 3. Why Static Xref Analysis Could Not Locate The Live Code (Bounded, Reported Attempt)

An exhaustive attempt was made to find the actual `.text` code implementing
`processFilteredPacket` and related functions, using the same methodology that worked for
`LogOnParams::addToStream` in earlier passes:

1. **ADRP+ADD scan** (`scratch/xref_lib.py:xrefs`) against all ~7 of the most
   distinctive diagnostic strings above, with search windows from 16 up to 64 bytes: **zero
   hits**.
2. **Wide-window register-tracking scan**: found all 54 `ADRP` instructions in `.text`
   targeting the exact rodata page containing these strings (`0x2a5d000`), then scanned up
   to 6KB forward from each for a matching `ADD` using the same destination register (to
   catch a single `adrp` reused across a large function with many error paths): **zero
   hits** across all 54 candidates.
3. **Direct `ADR` (PC-relative literal) scan** against the same targets: **zero hits**.

**Conclusion**: these strings are very likely **vestigial** — present in the compiled
binary (because the linker's rodata merging does not garbage-collect individual strings
within a shared merge section) but **not referenced by any live code path** in this
specific release build. This strongly suggests the actual, currently-executing packet
validation logic has **diverged** from what this generic/shared Mercury library string set
would imply (e.g., logging was compiled out via a release-mode macro, and possibly the
validation logic itself was simplified, replaced, or heavily inlined without preserving the
original per-check log statements). **This is reported as a genuine dead end for this
method**, not a shortcut skipped.

## 4. Dynamic Instrumentation Attempts (Bounded, Reported)

Per the task's request to "instrument/log the client's receive path if possible," two
Frida-based attempts were made using the working x86_64 frida-server 16.2.1 setup
established in earlier sessions:

### 4.1 Attempt 1 — hook `recvfrom`/`sendto` via `Process.getModuleByName('libc.so')`

Installed successfully and **confirmed working** — captured real, unrelated traffic during
the exact same test window (local IPC-style 232-byte exchanges, and a plain-HTTP 180-byte
response). This proves the hook mechanism itself functions correctly in this environment.
**However, zero Mercury UDP packets were ever seen through this hook**, despite `logcat`
confirming a `ServerConnection::logOnBegin`/`logOnComplete` cycle occurring during the
capture window.

**Root cause identified**: `Process.getModuleByName('libc.so')` resolves to the **host
x86_64** `libc.so`. The actual Mercury traffic is issued by NativeBridge-translated ARM64
code, which calls its *own* ARM64 libc — confirmed present at
`/system/lib64/arm64/nb/libc.so`, separately mapped into the same process (`r--p`, i.e.
**not marked executable** — same pattern previously observed for `libclient.so` itself).
Frida's `Process.enumerateModules()` does not list this ARM64 library at all (same gap
documented for `libclient.so` in `FRIDA_BASEAPP_LOGIN_CAPTURE.md`), so hooking "libc.so" by
module name can never reach it.

### 4.2 Attempt 2 — hook the ARM64 nb-libc's `recvfrom`/`sendto` by raw computed address

To route around the module-visibility gap: pulled `/system/lib64/arm64/nb/libc.so` from
the device, parsed its own ELF `.dynsym` to find `recvfrom` (file offset `0x6f95c`) and
`sendto` (file offset `0x6faf4`), read the library's actual load base from
`/proc/<pid>/maps` (`0x0b604000`, confirmed stable across the process's lifetime), and
called `Interceptor.attach()` on the computed absolute addresses (`0x0b67395c`,
`0x0b673af4`) directly via `ptr(...)`, bypassing module enumeration entirely.

**Result**: `Interceptor.attach()` succeeded with **no exception** on both addresses (the
memory was at least accessible for Frida's patching mechanism). A fresh, `logcat`-confirmed
login attempt was triggered immediately after. **Zero calls were intercepted** — the hooks
never fired, despite the underlying operation (a UDP send + receive) demonstrably
happening.

**Conclusion (STRONG EVIDENCE, not directly proven at the instruction level)**: this is
consistent with NativeBridge executing translated ARM64 code from a **separate, JIT-managed
executable memory region**, never actually fetching CPU instructions from the mapped `r--p`
ARM64 library pages themselves. A standard inline hook (which works by overwriting the
first instructions *at the target address* with a jump) cannot intercept execution that
never visits that address in the first place. This matches the earlier finding that these
ARM64 library segments are mapped **without execute permission**, which independently
supports the same conclusion: the mapped bytes are read as *data* by the translator, not
executed directly by the CPU.

**This is a real, reproducible negative result** from a genuine, correctly-instrumented
experiment — not a theoretical assumption carried over unchecked from a previous session.

## 5. Reply Attempts Made This Pass

Building on the two attempts from `PLAY_TO_BASEAPP_CAPTURE.md` §3 (bare 20-byte body;
20-byte body wrapped in a header-mirroring envelope), one further evidence-constrained
candidate was tried:

**Attempt C** — per §2's finding that `flags` is checked and various footers are
conditionally present based on flag bits, the simplest logically-consistent packet is the
20-byte body followed by a 2-byte `flags = 0x0000` footer (i.e., no optional footers
requested at all):
```
ac10010261b20000ac10010261b20000785634120000
```
(20-byte body + `00 00`, total 22 bytes). **Result**: identical rejection —
`Mercury::REASON_TIMER_EXPIRED`, same retry cadence as Attempts A and B.

**All three attempts are now exhausted for this pass.** Per the task's explicit instruction
not to brute-force further envelope permutations without new evidence, no additional
candidates were generated.

## 6. Where Rejection Occurs (Task Item 4: A/B/C/D)

**Cannot be determined with confidence.** The intended method for distinguishing "rejected
before Mercury parsing" vs. "during envelope validation" vs. "during message dispatch" vs.
"only at `LoginReplyRecord` parsing" was dynamic instrumentation of the receive path (§4),
which did not yield any visibility at all — not even confirmation that the client's
`recvfrom`-equivalent call actually returns our bytes. The only externally observable
signal in this environment is the final outcome after ~9 seconds:
`Mercury::REASON_TIMER_EXPIRED`, which is consistent with **any** of options A through D —
a `REASON_TIMER_EXPIRED` is simply what happens when no valid reply is recognized in time,
regardless of which validation stage silently discarded it.

## 7. Success Condition — Not Met

`LoginHandler::onLoginReply` was **not confirmed reached** in this pass. The client
continued retransmitting its request and ultimately failed with
`Mercury::REASON_TIMER_EXPIRED` for all three tested reply envelopes, identically to the
two tested in the previous session.

## 8. Recommended Next Steps (Not Attempted, Named For The Next Session)

1. **Test on genuine ARM64 hardware or an ARM64-native emulator** (no NativeBridge
   translation layer). Every dynamic-instrumentation obstacle found in §4 is specific to
   this x86_64-host LDPlayer configuration; standard Frida `Interceptor.attach` against
   `libclient.so`/ARM64 `libc.so` addresses should work normally on real ARM64 silicon,
   unlocking full in-process visibility into the Mercury receive path.
2. **Packet-capture-only differential testing** (no in-process visibility needed): since
   `logcat`'s `logOnComplete` outcome is externally observable without any hooking, further
   envelope candidates could still be tested by outcome alone — this remains viable and
   was intentionally not exhausted further this pass per the task's anti-brute-forcing
   instruction, pending a more targeted next candidate informed by new evidence (e.g., a
   found 32-bit "reply id" value from the request, per §2's `handleMessage` string, which
   none of the three attempts so far have supplied).
3. Investigate whether the 4-byte constant `00 00 00 00` at request offset `[7:11]` or the
   4-byte `2b 00 00 00` at `[11:15]` might itself be (or contain) the "reply id" or "request
   id" the client expects echoed back in a correlated reply — this was not tested as a
   candidate field in Attempts A/B/C and is the most evidence-grounded next single-field
   change per the task's "one framing field at a time" guidance.
