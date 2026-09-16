# BaseApp Channel Crypto Blocker — Consolidated Summary (E2E-008 through E2E-020)

## READ THIS FIRST (E2E-020 RESOLUTION — BLOCKER SOLVED)

**The BaseApp Crypto Blocker is now SOLVED at the binary disassembly level (E2E-020).**

1. **IV = 0 For Every Packet (No Inter-Packet Chaining)**:
   - Disassembly of `in_place_decrypt` (`0x98924c`, called by `EncryptionFilter::recv` @ `0x989444`) showed that at `0x9892c8`, it executes `mov x26, xzr`.
   - The IV is cleared to all-zeros on **every single received datagram**.
   - BigWorld Mercury Blowfish encryption operates strictly per-packet with IV = 0.
   - Setting `chain_iv = _last_plain_block_by_host` in `mitm/local_baseapp_capture.py` in E2E-012 was XOR-corrupting the first 8 bytes upon client decryption, turning flags `0x0001` into `0x0183`.
   - Flags `0x0183` set Bit 8 (`FLAG_HAS_CHECKSUM = 0x0100`) and Bit 1 (`FLAG_HAS_PIGGYBACKS = 0x0002`), causing the false "failed checksum" and "piggyback unpack" errors.

2. **BigWorld Wastage / Padding Rule (`w21 <= 8`)**:
   - `in_place_decrypt` (`0x989324`-`0x989350`) reads the very last byte of the decrypted packet as the **wastage count**: `w21 = packet[total_len - 1]`.
   - If `w21 <= 8`, it strips `w21` bytes from `packet_obj+0x1a` (`[x19, #0x1a] -= w21`).
   - If `w21 > 8`, it drops the packet with `Dropping packet from %s due to illegal wastage count (%d)`.
   - Padding must therefore end with the byte value `pad_len` (e.g. `b'\x00\x00\x00\x04'` for a 12-byte payload padded to 16 bytes).
   - This cleanly satisfies the `processFilteredPacket` sanity check `(+0x1a)+(+0x1c) > 2` without needing any special trailer sections!

3. **Status**:
   - `mitm/local_baseapp_capture.py` has been updated with IV=0 and wastage padding for both BaseApp reply (`msgID 0xFF`) and `createBasePlayer` push (`msgID 0x04`).

---

## E2E-018 Context (Historical)

The E2E-017 "indexed-channel dispatch" hypothesis has now been **fully resolved — mixed
result, and it does NOT explain or fix the blocker.** Both load-bearing links were checked:

1. **CONFIRMED**: `BaseAppLoginRequest::initNetwork` genuinely DOES register the new BaseApp
   Channel object into the Nub's indexed-channel map (`Nub+0x41f0`/`+0x40e0`/`+0xe0`), via an
   unconditional call to `0x992764` (the map's insert function, fully disassembled and
   confirmed this pass). So the E2E-017 dispatcher (`0x98d38c`, routes packets from a
   registered source address through `channel_obj->vtable[0x18]` instead of the generic
   `processFilteredPacket`) is a real mechanism that genuinely applies to this channel.
2. **REFUTED**: the specific vtable slot (`+0x18`, raw bytes `0xd02fdc`) guessed as the
   decrypt-dispatch target is NOT decrypt code — it disassembles to a red-black-tree
   find/erase routine, and (separately) has no `.rela.dyn`/`.rela.plt` relocation entry at
   all, because it isn't a function pointer in the first place: it's the plain-integer
   "offset-to-top" field of a standard Itanium-ABI multi-base vtable layout. Disassembling
   ALL the real function slots on this vtable blob (`0x98530c`, `0x985b3c`, `0x9879f0`,
   `0x985b34`, `0x985b60`) shows they are plain reference-counted-object plumbing
   (destructor + a stack-overflow-guard check) — **there is no decrypt-shaped function
   anywhere on this Channel's own vtable.**

**Conclusion**: the indexed-channel-dispatch idea, while real as a general mechanism, does
NOT provide an alternate decrypt path to switch to for this blocker — this Channel object's
vtable has no encryption-related method at all. This thread is now closed with an honest
negative result (E2E-018). Per standing instruction, the investigation has fallen back to
the PREVIOUS lead: tracing `packet_obj+0x1a`/`+0x1c`'s origin in the generic
`processFilteredPacket`/`0x98924c` path, and/or characterizing the inline SIMD/NEON checksum
block (`~0x98fce0`-`0x98fd10`) — not yet started as of E2E-018. See the "E2E-017
Alternate-Dispatch Hypothesis" section below, now marked RESOLVED/NEGATIVE, for the full
disassembly evidence.

This document exists so a future pass (human or agent) does not have to re-read five-plus
scattered `END_TO_END_TEST_LOG.md` entries to understand the current state of this
project's single most persistent open blocker. Labels: **CONFIRMED** / **INFERRED** /
**HYPOTHESIS** / **BLOCKED** (this pass's convention, consistent with other recent notes).

## The Headline Problem

The client's BaseApp UDP channel rejects every reply this project has sent to it. Getting
this right is the sole remaining gate before Account → Avatar → Lobby (LoginApp itself
works completely — see `06_notes/PRIVATE_SERVER_REPLACEMENT_STATUS.md`).

## What Is CONFIRMED (not in dispute)

1. **Wire framing**: the BaseApp channel Blowfish-encrypts the ENTIRE packet (flags, msgid,
   length — everything), unlike LoginApp's body-only encryption. (E2E-008, Attempt 3/4.)
2. **Reply-ID correlation**: solved, stable, unrelated to this blocker (4-byte LE at wire
   offset 5). (E2E-006.)
3. **`createBasePlayer` wire format**: `[u16 length][body]` (VARIABLE_LENGTH_MESSAGE), message
   ID 4 within `ClientInterface` (by registration-order inference). (E2E-011.)
4. **The BaseApp channel's key is the LITERAL SAME key as LoginApp's** — not merely
   empirically equal (live memory scan, 10+ reproductions, E2E-012) but **CONFIRMED BY
   DISASSEMBLY** (E2E-015): `BaseAppLoginRequest::initNetwork` reads the EncryptionFilter
   pointer straight out of `ServerConnection+0x148` (the same slot LoginApp uses) and hands
   that SAME pointer (not a copy) into the new BaseApp `Channel` object's own `+0x40` slot,
   with only a refcount increment — no new key material, no new object.
5. **There is no distinct BaseApp-specific decrypt code path — CORRECTED/SHARPENED in E2E-016.**
   Since both channels hold a pointer to the identical `EncryptionFilter` object, both
   dispatch through its identical vtable. **`0x989600` (which E2E-007 through E2E-015 treated
   as "the" decrypt function) turns out to have exactly ONE caller in the entire binary —
   `LoginHandler::onLoginReply` itself** — meaning it is a private helper hardcoded for the
   fixed 20-byte LoginReply body, NOT a generic per-channel decrypt entry point. The REAL
   generic receive-path decrypt is a DIFFERENT function, **`0x98924c`**, reached via the
   filter's actual vtable (recovered from `.rela.dyn`, since the raw file bytes at the vtable
   address are relocation targets, not literal pointers). It implements the identical
   `pc_variant`/IV=0 algorithm, so "is there a different chaining mode for BaseApp?" is still
   answered **no** — but the two functions differ in how they determine decrypt LENGTH (see
   next point), which is a materially different, still-open question. (E2E-015, corrected/
   extended E2E-016.)
6. **The Blowfish cipher mode itself is `pc_variant`** (XOR each plaintext block against the
   PREVIOUS plaintext block, IV=0 at the start of a decrypt call, then ECB-encrypt/decrypt) —
   confirmed correct for LoginApp via disassembly of the `0x989600` loop and live-verified
   (correctly decodes `172.16.1.2:25010`). (E2E-007.) The generic decrypt (`0x98924c`)
   implements the same algorithm structure. (E2E-016.)
7. **The generic decrypt (`0x98924c`) starts at the correct wire offset (0, the flags field,
   at `packet_obj+0x60`) but computes its LENGTH from two 16-bit fields
   (`packet_obj+0x1a` and `+0x1c`, summed) that the receive path populates BEFORE calling
   decrypt — NOT simply "the number of bytes received."** These two fields get
   reclassified relative to each other (sum unchanged) when certain Mercury footer flags are
   set on the packet. Where the BASE-CASE values of these two fields come from (for a packet
   with no special footer flags, like this project's own replies) was not fully traced to its
   origin as of E2E-016 — this is the concrete open question blocking further progress.
   (E2E-016.)

## What Has Been TRIED and DISPROVEN (do not re-attempt these exact forms)

| Attempt | What was tried | Result |
|---|---|---|
| E2E-008 Attempt 4 | Whole-packet `pc_variant` encrypt, IV=0, using LoginApp's key | Decrypts to garbage (`authenticate`/msgid=0 misparse) |
| E2E-009 | Live re-scan for a SEPARATE BaseApp key (small-region + full-region search) | Inconclusive at the time due to a since-fixed scan bug; later superseded by #4 above |
| E2E-012 | Chain IV from LoginApp's own last-sent plaintext block | Initial live test showed a NEW error (checksum failure at flags=183) — looked promising |
| E2E-013 | Same chain-IV, fresh process/key | Reproduced the checksum-failure error, still inconclusive |
| E2E-014 | Same chain-IV, but this time isolated to the FIRST ack of a fresh test (not confounded by a `createBasePlayer`-tail-block bug found and fixed this pass) | **CLEAN NEGATIVE**: still `bad flags 5679`, not decoded correctly. Chain-from-last-plaintext-block is DISPROVEN as the correct IV source. |

**Do not re-try**: IV=0 with the shared key (disproven, E2E-008); IV=chained-from-
LoginApp's-last-plaintext-block (disproven cleanly, E2E-014). **Caveat added in E2E-016**:
both of these attempts used a packet LENGTH equal to "however many bytes we chose to send"
— per E2E-016's finding that decrypt length actually comes from packet-object metadata
fields (`+0x1a`/`+0x1c`), it is not yet confirmed whether these attempts also had the
correct LENGTH for those fields to resolve to. The IV conclusions above remain valid
(IV=0 is structurally the only correct starting state, per direct disassembly of the
decrypt loop — a length mismatch doesn't change that), but a length-corrected retest of
IV=0 has NOT yet been done and is not the same experiment as E2E-008's original attempt.

## What Was Investigated and Found NOT To Be The Answer (dead ends, not disproven hypotheses)

- **A standard CRC-32 checksum on the packet**: the binary DOES contain a genuine, exact,
  zlib-compatible CRC-32 implementation (table + update function + init/finalize
  convention), but its 4 known callers are in a distant, unrelated part of the binary
  (probably asset/resource-name hashing). Not confirmed to be the Mercury packet checksum.
  (E2E-014.)
- **The checksum error string's real call site**: confirmed unlocatable via 5 independent
  static methods across two passes (corrected-offset ADRP+ADD scan, widened window,
  full-file raw-pointer scan, manual disassembly of `processFilteredPacket`'s known body,
  and exhaustive backward-resolution across all 2019 combined callers of both the WARNING-
  and ERROR-level shared log functions). This is a well-corroborated negative result, not
  an unexplored gap. (E2E-014.) **Likely explanation found in E2E-016**: while tracing
  `processFilteredPacket`'s length-field bookkeeping, found a block of NEON/SIMD
  instructions (`~0x98fce0`-`0x98fd10`) directly inline in the function body — consistent
  with an INLINED checksum/hash computation, not a separate callable function at all. If
  correct, this fully explains why 5 independent function-call-based search methods could
  never find it: there is no function to find. **Not yet characterized** (algorithm, input
  byte range) — a concrete next step, not a closed finding.

## The Core Unresolved Puzzle — REFRAMED this pass (E2E-015 continued)

Object, key, and code path are ALL confirmed identical between the two channels. This pass
went further and **ruled out hidden chaining state entirely**:

- `EncryptionFilter`'s `operator new` call site (`0x93a8f0: mov w0, #0x38`) confirms the
  WHOLE object is exactly 56 (`0x38`) bytes — vtable(8) + refcount(8) + key-string(0x18) +
  length(4, padded) + enabled-bool(1, padded) + `BF_KEY*`(8) = 56 bytes exactly. **Zero
  bytes left over for a hidden IV/state field.**
- Directly disassembled the decrypt function itself (`0x989600`, full dump in
  `scratch/trace_989600.txt`): the "previous plaintext block" pointer (`x25`) is a **local
  register, explicitly reset to `xzr` (NULL) at the top of EVERY call**
  (`0x9896a4: mov x25, xzr`) — there is categorically NO persistent chaining state carried
  between separate `decrypt()` invocations. IV=0 (functionally: skip the XOR for the first
  block) is the ONLY structurally correct starting state, for every call, always. This also
  re-confirmed the sibling encrypt function (`0x989590`-`0x9895fc`) matches this project's
  `bf_encrypt()` `pc_variant` implementation exactly, block-for-block.

**This closes out hypotheses 1-3 from the original framing** (no hidden state exists to
advance, mutate, or incorporate anything). Given (a) the key is CONFIRMED correct (same
object as LoginApp, which decrypts correctly with it), (b) the algorithm is CONFIRMED
correctly implemented (matches disassembly exactly), and (c) IV=0 is CONFIRMED the only
structurally valid starting state — decryption of the BaseApp message STILL fails while
LoginApp's succeeds, with every crypto-parameter variable now identical between the two.

**The question is therefore NOT "which crypto parameters" (fully closed out) but "which
exact byte range of the wire packet is the ciphertext"** — a framing/offset question.

**ANSWERED IN PART, E2E-016**: `0x989600` turned out to have exactly ONE caller in the
entire binary (`onLoginReply` itself) — it is NOT the generic decrypt function this
question needed. The real generic receive-path decrypt is `0x98924c` (found via the
filter's TRUE vtable, recovered from `.rela.dyn` since raw file bytes at the vtable address
are relocation targets, not literal pointers). It **starts at the correct offset**
(`packet_obj+0x60` == confirmed wire byte 0, the flags field) but its **LENGTH comes from
two 16-bit fields in the packet object (`+0x1a` and `+0x1c`, summed)** that the receive
path populates BEFORE calling decrypt — not simply "the number of bytes received." These
two fields get reclassified relative to each other (sum unchanged) when certain footer
flags are set. **Where the base-case values of these two fields originate (for a packet
with no special footer flags) was not fully traced this pass** — this is now the single
most concrete open question.

**Recommended next static target**: trace `processFilteredPacket`'s EARLIEST write to
`packet_obj+0x1a` (before any footer-flag reclassification) back to its source — most
plausibly the raw UDP `recvfrom()` byte count or an explicit wire length field, but not yet
confirmed which. Separately, characterize the inline SIMD checksum block found this pass
(see above) to determine if it's the real "failed checksum" mechanism and, if so, its
input byte range and algorithm.

**SUPERSEDED IN PRIORITY by E2E-017's finding below** — pursue that first, since if
`processFilteredPacket` is never even reached for BaseApp packets, tracing its internal
field origins further would be solving the wrong problem.

## The E2E-017 Alternate-Dispatch Hypothesis — RESOLVED/NEGATIVE in E2E-018 (found while looking for `processFilteredPacket`'s caller)

While searching for what calls `processFilteredPacket` (it has zero direct `BL` callers;
only reached via tail-call `B` instructions), found that its ACTUAL caller is a real,
separate dispatcher function (`0x98d38c`) that does something unexpected:

```
0x98d38c: this=Nub*, x2=packet_obj
  x0 = Nub + 0x41f0                    ; a per-source-address CHANNEL MAP
  bl 0x9950d8                          ; map::find()-shaped lookup, keyed by the
                                          packet's source address
  compare result against Nub+0x41f8    ; the map's "end" sentinel
  IF FOUND (a registered/"indexed" channel exists for this source address)
     AND channel_obj+0xf8 flag is set:
    ldr x8, [x22]        ; x22 = found channel object; load ITS OWN vtable ptr
    ldr x8, [x8, #0x18]  ; vtable slot +0x18
    blr x8                ; VIRTUAL DISPATCH -- processFilteredPacket is
                            NEVER CALLED for this packet
  ELSE:
    falls through to processFilteredPacket (the generic path analyzed above)
```

**Why this could explain everything**: `BaseAppLoginRequest::initNetwork` (confirmed,
E2E-015) explicitly constructs a `Channel`-shaped object for the new BaseApp socket,
sharing LoginApp's `EncryptionFilter`, BEFORE any packets are exchanged on it. If that
construction (or code shortly after) also REGISTERS this new channel into the SAME
`Nub+0x41f0` map — plausible, matching BigWorld's own "indexed channel" terminology already
seen in this project's earlier vestigial-string survey — then **every packet on the
BaseApp socket, including every reply this project has sent, would route through this
channel-specific virtual method instead of the generic decrypt path**. This would mean
`processFilteredPacket`/`0x98924c` were simply never reached for BaseApp traffic at all,
making the E2E-014/E2E-016 length/offset analysis correct but irrelevant to this specific
channel — a structurally different explanation than "wrong parameters on the right path."

**STATUS (E2E-018): BOTH links now checked — mixed, and net RESULT is negative for this
hypothesis as a fix**:
1. **CONFIRMED**: `initNetwork` calls `0x992764` (map insert, fully disassembled: validates
   `index<0x400`, sets a bitmap bit at `Nub+0x40e0`, stores the value at
   `Nub+index*8+0xe0`) unconditionally with `x1` = the new BaseApp Channel object. It also
   conditionally calls the mirror-image remove function `0x992994` first (stale-slot
   cleanup). Registration is real.
2. **REFUTED**: `0xd02fdc` is a red-black-tree find/erase routine, not decrypt code. A full
   `.rela.dyn`/`.rela.plt` scan of the vtable-blob range `[0x37dd280, 0x37dd2e0)` shows
   `+0x18` has no relocation because it isn't a pointer at all — it's the plain-integer
   "offset-to-top" field of a two-virtual-base Itanium vtable layout (the object's second
   stored pointer, `object+0x08 = 0x37dd2a8`, is the secondary base's own vtable, whose two
   real slots — `0x985b34`, `0x985b60` — are also just destructor thunks). Every one of the
   5 real function slots on this combined vtable blob (`0x98530c`, `0x985b3c`, `0x9879f0`,
   `0x985b34`, `0x985b60`) was disassembled: all are reference-counted-object plumbing
   (destructor worker, two deleting-destructor thunks, a stack-guard check). **No
   decrypt-shaped function exists anywhere on this vtable.**

**Net conclusion**: registration into the indexed-channel map is real, but this specific
Channel object's own vtable has no alternate decrypt method to dispatch to — so the
hypothesis does not explain the blocker after all (either this isn't actually the object
`0x98d38c`'s map lookup finds for BaseApp login traffic, or the dispatch is real but simply
uninteresting for decrypt purposes on this object). Do not pursue this thread further
without new evidence (e.g. a live trace showing `0x98d38c`'s map lookup actually firing and
which object it finds). Falling back per standing instruction to tracing
`packet_obj+0x1a`/`+0x1c`'s origin in the generic path and/or the inline SIMD checksum block
— see `07_ros_legacy_approach/END_TO_END_TEST_LOG.md` E2E-018 for the full writeup.

## Tooling Constraints (why this hasn't been resolved dynamically)

- Frida-based introspection is blocked on the emulator by a native-bridge (x86_64-host,
  ARM64-guest translation) module-visibility wall (E2E-004), and blocked on real ARM64
  hardware by the orchestrating session's own security classifier refusing APK
  repackaging for gadget injection (E2E-005/E2E-008 pass).
- Live `/proc/pid/mem` heap scanning (used successfully for the key itself) can locate
  static object contents at a point in time, but cannot observe state CHANGES over time
  without either repeated racing snapshots (proven unreliable at the needed precision,
  E2E-009) or actual code-level instrumentation (blocked, above).

## Live Environment Notes (for whoever runs the next live test)

- The key changes every fresh app process (`RAND_bytes(4)` at `ServerConnection`
  construction) — always re-extract it fresh per process via the (now-reliable, single-
  atomic-read) scan in `mitm/local_baseapp_capture.py`'s `find_baseapp_key_async`/
  `_scan_region_for_pattern` before testing.
- **CPU monitoring is now standard practice** (adopted after an ANR incident, E2E-012):
  check `adb shell top -n 1 -b | grep chiji` after every live test; force-stop promptly if
  it stays elevated (>80%) for more than a few seconds after your own server stops sending.
- Pace live tests conservatively — one iteration at a time, not rapid-fire loops.

## Where To Look

- Full blow-by-blow history: `07_ros_legacy_approach/END_TO_END_TEST_LOG.md`, TEST_ID
  E2E-008 through E2E-015.
- Current overall project status: `06_notes/PRIVATE_SERVER_REPLACEMENT_STATUS.md`.
- Wire framing details: `06_trace/BASEAPP_LOGIN_SERIALIZATION.md`,
  `06_trace/MERCURY_PACKET_MAP.md` §2b.
- Original Blowfish key lifecycle (LoginApp side): `06_notes/FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md`.
- This pass's shared-object disassembly proof: `scratch/confirm_shared_filter_object.py`.
