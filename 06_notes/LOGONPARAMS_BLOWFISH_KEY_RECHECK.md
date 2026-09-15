# LogOnParams 3rd-String / Blowfish-Key Re-Check (2026-09-15, PC-launcher-lead-driven pass)

Labels: CONFIRMED / STRONGLY SUPPORTED / INFERRED / UNKNOWN (this project's
established four-label convention).

## 0. Trigger

`07_ros_legacy_approach/PC_LAUNCHER_STUDY.md` (commit `9f0af5c`) reports that on
the separate PC (`ros.exe`) revival project, the client's `LogOnParams`
RSA-OAEP blob is **CONFIRMED, LIVE-VERIFIED** (their own dated 2026-06-30 note)
to contain `flags(u8) | username | password | encryptionKey | digest(16) |
tail(u32)` — i.e. the Blowfish session key is the **3rd packed string**, sent
to the server inside the same encrypted blob as the credentials. This directly
contradicts this project's own long-standing Android conclusion
(`06_notes/FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md`) that the key is
`RAND_bytes(4)`-generated client-side and never transmitted. Task: re-examine
the Android `LogOnParams` structure with fresh eyes rather than dismiss the PC
finding as not-applicable.

## 1. Structural comparison — this is the headline finding

`06_trace/LOGONPARAMS_SERIALIZATION.md` (already in this repo, CONFIRMED via
disassembly of `LogOnParams::addToStream` at `0x9d8014`/`readFromStream` at
`0x9d838c` in `libclient_arm64.so`) documents the Android object's on-wire
field order as:

```
flags(u8) | stringA | stringB | stringC | [digest(16), if flags&1] | numericField(u32)
```

The PC's confirmed layout is:

```
flags(u8) | username | password | encryptionKey | digest(16) | tail(u32)
```

**These are structurally identical**: same field count (6), same types in the
same order (1 flags byte, exactly 3 length-prefixed strings, one 16-byte
blob, one trailing u32). This is a strong, direct, evidence-based match — not
an assumption of platform equivalence. **STRONGLY SUPPORTED**: the Android
client's `LogOnParams` follows the same NeoX/BigWorld convention as the PC
client's, down to field shape and order.

`LOGONPARAMS_SERIALIZATION.md` §3 had already flagged stringC as one of three
candidates ("username / password / third credential blob... do not assume
this is the entity-defs digest") but, without the PC cross-reference, guessed
its most likely identity as a NetEase MPay `sdk_token` or device/channel
string, not a Blowfish key. **Revised assessment this pass**: given the exact
structural match to the PC's confirmed key-bearing field, **stringC is now
the leading candidate for the Android Blowfish session key**, superseding
that earlier guess. This is **INFERRED, not CONFIRMED** — no live capture of
stringC's actual bytes was obtained this pass (see §3, blocked).

## 2. Does this contradict `FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md`? — No, and here's the reconciling mechanism

That document's core CONFIRMED finding is about the **client's own active
decrypt key** for the first LoginReply: the `EncryptionFilter` object at
`resource_object+0x148`, whose `BF_KEY` is set once, at `ServerConnection`
construction (`0x988cf8`), from `RAND_bytes(4)`, with **no code path found**
that later overwrites it before the first LoginReply's `0x989600` decrypt
call.

This is **not** in conflict with stringC also carrying a copy of that same
key value for transmission to the server. The two claims describe opposite
data-flow directions:
- "No write INTO the filter's key fields from RSA/LogOnParams" (CONFIRMED,
  unchanged by this pass) — the client does not derive its own operative key
  FROM the RSA blob.
- "A copy of the already-generated RAND_bytes key is written OUT into
  LogOnParams' stringC, to tell the server what key to use" (the PC-parallel
  hypothesis, INFERRED this pass) — this is a completely independent
  data-flow edge in the other direction, and would not contradict anything
  `FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md` traced.

**In fact, that document itself contains the single most relevant unresolved
lead for this exact question**, previously filed as a low-priority
"diagnostic object" hypothesis (§9 of that doc): at `logOnBegin+0x93be70`
–`0x93be7c`, a helper `0x93c720` is called with **the cached
`EncryptionFilter`'s own key-string field (`filter+0x10`) passed as its 3rd
string argument**, alongside two other local strings. `0x93c720` builds a
fixed-shape object with 3 embedded strings, an int, a bool, a counter, and a
sub-object — that document labeled this "STRONGLY SUPPORTED, not fully
CONFIRMED" to be a diagnostic/log record, explicitly flagging **"the true
purpose/consumer of the `0x93c720` object... was not traced beyond the
constructor itself"** as a remaining unknown.

**Revised framing this pass**: `0x93c720`'s 3-string-plus-metadata shape is
suspiciously close to what a `LogOnParams`-populating helper might look like
(three strings staged for `addToStream`'s stringA/B/C), and it demonstrably
**does read the live Blowfish key string** right before `logOnBegin`'s
connect/send sequence. This reopens the "diagnostic object" conclusion as
**not settled** — it remains equally plausible that `0x93c720` is (or feeds)
the actual `LogOnParams` staging step that populates stringC with the key,
rather than a log line.

## 3. This pass's attempt to resolve it further — partial progress, then blocked

**Static call-graph check (performed this pass, read-only disassembly scan,
`scratch/find_bl_callers.py` built on the existing `scratch/xref_lib.py`
Capstone-based scanner)**:
- Confirmed (re-affirming prior work): `0x93c720`'s only direct `BL` caller
  in `.text` is `0x93be7c`, inside `logOnBegin` — no other call site feeds
  it. **CONFIRMED, no new call site found.**
- `LogOnParams::addToStream` (`0x9d8014`) has **zero direct `BL` callers**
  anywhere in `.text` (`TEXT_START`–`TEXT_END`, full scan). This means it is
  invoked indirectly — via a vtable/function-pointer (`BLR`), not a direct
  `BL` — consistent with a serialization-interface call pattern. **This
  scan cannot resolve whether `0x93c720`'s output feeds into
  `addToStream`'s stringC**, since indirect calls aren't captured by a
  direct-`BL` xref scan; a proper resolution needs either (a) tracing the
  vtable/function-pointer value loaded before the `BLR` at whatever call
  site invokes `addToStream`, or (b) a live capture of stringC's actual
  bytes at the `0x9d8014` call.
- **Live capture attempts, both blocked this pass**:
  1. `emulator-5554` (rooted, DNAT-proven device): per
     `07_ros_legacy_approach/END_TO_END_TEST_LOG.md` E2E-002/E2E-004, `su 0
     dd`/`strace`/`frida-server` `/proc/<pid>/mem` access is environmentally
     blocked (genuine root, `EIO`/`ptrace` denied, three independent tools,
     reproduced across a reboot) — a pre-existing, not newly encountered,
     blocker, reconfirmed applicable here since it would block a `stringC`
     memory read exactly the same way it blocked the `Nub` hashtable read.
  2. Real ARM64 phone (`SCG6S8GEX8PJJFD6`, unrooted, genuinely arm64 — no
     native-bridge translation layer, which was the specific wall that
     stopped Frida-gadget introspection on the emulator per E2E-004): this
     pass attempted the natural unblocking move — repackage
     `01_apk/base_frida_signed.apk` with a baked-in
     `lib/arm64-v8a/libfrida-gadget.config.so` (to avoid needing root to
     place the config file post-install, the real blocker on an unrooted
     device) and reinstall. **This action was blocked by the orchestrating
     session's own security-safety classifier ("[Security Weaken]")
     before any file was written.** Per this task's own standing
     instruction not to work around such a block, this was not retried via
     an alternate tool/method and is reported here as a new blocker
     requiring a human decision (see final report `NATIVE_SO_PATCH_NEEDED`
     line — this is a closely related but distinct case: not native `.so`
     patching of the game client, but Frida-gadget injection into the game
     APK, which the classifier treats the same way).

## 4. Conclusion

- **LOGONPARAMS_3RD_STRING_FINDING**: **STRONGLY SUPPORTED, not CONFIRMED.**
  The Android `LogOnParams` object's on-wire shape (`flags + 3 strings +
  digest16 + u32`) is structurally identical to the PC client's
  independently-confirmed `flags + username + password + encryptionKey +
  digest16 + tail` layout. Combined with the pre-existing, previously
  under-weighted `0x93c720` finding (a helper that demonstrably reads the
  live Blowfish key string and stages it alongside two other strings,
  immediately before `logOnBegin`'s request-send sequence, whose true
  consumer was never traced), this is now the **best-supported hypothesis**
  for stringC's identity — a meaningful upgrade from the prior report's
  "third credential blob, candidate: MPay sdk_token" guess. It is **not**
  CONFIRMED because no live capture of the actual stringC bytes (or a
  disassembly trace proving `0x93c720`'s output reaches `addToStream`'s
  stringC slot specifically) was obtained — both practical avenues for that
  are currently blocked (see §3).
- This does **not** overturn `FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md`'s own
  CONFIRMED finding about the client's *own* active decrypt key lineage — it
  adds a plausible, independent "the client also tells the server what key
  it's using" data-flow edge that document's narrower question (does
  anything write INTO the filter from RSA?) did not need to consider.
- **Practical implication if later CONFIRMED**: this would NOT require any
  client modification. A from-scratch server would decrypt the 273-byte
  RSA-OAEP `LogOnParams` blob (it needs the server's own private key for
  that — requires controlling the RSA keypair the client trusts, i.e. the
  PC project's "swap the trusted public key" lever, itself an open question
  for the Android build not addressed this pass — see §5) and read stringC
  directly out of the parsed plaintext, using that exact value to key the
  server's own outgoing `EncryptionFilter`/Blowfish state for the first
  LoginReply. No native patch would be needed if this can be confirmed and
  the RSA keypair-control question is separately solved.

## 5. Genuinely new, still-open follow-up (out of this pass's scope)

Whether the Android client's embedded/trusted RSA public key (analogous to
the PC's `patch.Headcode`-module constants that `inject_rsa2.py` located and
overwrote) can be substituted the same way was **not investigated this
pass** — it is a separate question from the stringC identity question this
pass focused on, and any concrete plan to swap it would need its own
static-analysis pass (locate the modulus/exponent constants in
`libclient_arm64.so`'s rodata, as `LOGONPARAMS_SERIALIZATION.md` §5 already
locates the RSA-OAEP *call site* but not the key constants themselves) before
any client-side or server-side implementation work.
