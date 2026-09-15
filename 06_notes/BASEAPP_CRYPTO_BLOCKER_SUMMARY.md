# BaseApp Channel Crypto Blocker — Consolidated Summary (E2E-008 through E2E-015)

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
5. **There is no distinct BaseApp-specific decrypt code path.** Since both channels hold a
   pointer to the identical object, virtual dispatch means they execute the exact same
   `decrypt`/`encrypt` machine code (the `0x989600`-region implementation already
   characterized for LoginApp). (E2E-015.) This directly answers "is there a different
   chaining mode for BaseApp?" — no, by construction.
6. **The Blowfish cipher mode itself is `pc_variant`** (XOR each plaintext block against the
   PREVIOUS plaintext block, IV=0 at the start of a decrypt call, then ECB-encrypt/decrypt) —
   confirmed correct for LoginApp via disassembly of the `0x989600` loop and live-verified
   (correctly decodes `172.16.1.2:25010`). (E2E-007.)

## What Has Been TRIED and DISPROVEN (do not re-attempt these exact forms)

| Attempt | What was tried | Result |
|---|---|---|
| E2E-008 Attempt 4 | Whole-packet `pc_variant` encrypt, IV=0, using LoginApp's key | Decrypts to garbage (`authenticate`/msgid=0 misparse) |
| E2E-009 | Live re-scan for a SEPARATE BaseApp key (small-region + full-region search) | Inconclusive at the time due to a since-fixed scan bug; later superseded by #4 above |
| E2E-012 | Chain IV from LoginApp's own last-sent plaintext block | Initial live test showed a NEW error (checksum failure at flags=183) — looked promising |
| E2E-013 | Same chain-IV, fresh process/key | Reproduced the checksum-failure error, still inconclusive |
| E2E-014 | Same chain-IV, but this time isolated to the FIRST ack of a fresh test (not confounded by a `createBasePlayer`-tail-block bug found and fixed this pass) | **CLEAN NEGATIVE**: still `bad flags 5679`, not decoded correctly. Chain-from-last-plaintext-block is DISPROVEN as the correct IV source. |

**Do not re-try**: IV=0 with the shared key (disproven, E2E-008); IV=chained-from-
LoginApp's-last-plaintext-block (disproven cleanly, E2E-014).

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
  an unexplored gap. (E2E-014.)

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
exact byte range of the wire packet is the ciphertext"** — a framing/offset question. This
project's working assumption (established in E2E-008, from a block-size-error observation)
that the WHOLE packet is the ciphertext may be wrong in some detail for the BaseApp channel
specifically (e.g. a different start offset, a different length calculation, or an extra
header/trailer byte range this project hasn't isolated).

**Recommended next static target**: find the CALLER of `0x989600` specifically on the
BaseApp/`Nub::processFilteredPacket` receive path (not the already-characterized LoginApp/
`onLoginReply` path) to read exactly what source pointer, destination pointer, and length
it passes for an incoming BaseApp-channel packet — this would show empirically where the
decrypt call believes the ciphertext begins and ends, resolving the framing question
directly from disassembly instead of further trial-and-error on packet layout.

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
