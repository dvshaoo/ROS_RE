# Synthesis: Where the Account/Lobby Investigation Actually Stands (2026-09-16, after E2E-037)

Written on explicit request for a step-back synthesis, not a new investigation. Labels:
CONFIRMED / STRONGLY SUPPORTED / INFERRED / UNKNOWN, this project's standing convention.

## 1. What is CONFIRMED and durable — will not need revisiting

- **Full LoginApp handshake**: reply-ID correlation, Blowfish `pc_variant` cipher (IV=0
  per-datagram, wastage-byte padding), live-verified repeatedly. Not at risk from anything
  in this synthesis.
- **BaseApp login accepted**: `status==LOGGED_ON`, `createBasePlayer` succeeds (`Account`,
  type 127, msgID 5 — cross-validated by two independent methods, E2E-022).
- **Reliable-channel keep-alive**: the generic `ServerConnection`/`Channel`
  `InactivityTimeout` watchdog (10s) is fully solved by a periodic `setGameTime` push —
  live-verified to prevent reconnect for 90+ seconds (E2E-022/023).
- **`enableEntities`**: fires once, bundled with the client's first `identifyVersionPoint`
  call, and is satisfied by the ALREADY-WORKING transport-level channel ACK — no distinct
  application-level reply needed (E2E-024).
- **`identifyVersionPoint`/`versionPointIdentity` are a dead end, not the real blocker** —
  this is now confirmed from THREE independent angles, not just one:
  1. Its native handler (`0x94bf48`) has zero validation logic (E2E-023).
  2. It never invokes any script/Python callback, unlike a real handler like
     `restoreClient`'s (E2E-025).
  3. Empirically: neither wire-format content (pickle vs marshal, 3 variants) nor wire
     flags (`0x0001` vs `0x0008`) changed the client's behavior at all, even under a
     407-packet retry flood over ~20s (E2E-023, E2E-028, E2E-037).
  **This thread should not be revisited without genuinely new evidence.**
- **The full `ClientInterface`/`BaseAppExtInterface` numeric msgID table (0-101 and 0-17
  respectively)** is resolved with certainty via a programmatic registration-order walk,
  cross-validated against an independently-known value (E2E-022).
- **The `script.npk`/`.nxs` stream cipher is unbreakable by this project's static tooling**,
  and the NeoX VFS script-override mechanism does NOT provide a plaintext bypass — override
  files use the identical encrypted format, copied byte-for-byte with zero transformation
  (E2E-033, direct byte + smali evidence). ROS Legacy's own working override files are
  themselves evidence that dynamic instrumentation (not static analysis) is the only proven
  way past this cipher — a path already explicitly blocked in THIS project's own environment
  (native-bridge x86/ARM64 translation wall on the emulator, APK-repackaging classifier
  block on real hardware — both pre-existing, not new).
- **`Account.handshake`'s numeric wire ID cannot be recovered from native disassembly** —
  no entity method name exists as a string anywhere in the binary, unlike the core Mercury
  interfaces (E2E-025/026). This is a hard, structural limit of the static approach, not an
  effort gap.
- **`entity_ptr+0x140` (call it `ServerConnection` or `Channel` — see open question below)
  is NOT a one-time initialization flag — it's a live, toggling field**, oscillating between
  `0x0` and a stable non-null pointer with a period of roughly 2-3 seconds (E2E-035, six
  consecutive live reads on the same session). This overturned the working hypothesis of
  E2E-029/030/032/034 (which assumed a single missing setter call) — there is no single
  "make it non-null forever" fix to find for this field.

## 2. What has been tried on the `onChannelLogin`/`entity+0x140` thread specifically, and is now genuinely exhausted

- **Static setter-hunting** for `entity+0x140`, across 4 independent techniques spanning
  4 passes (E2E-030 narrow-range scan, E2E-034 whole-binary shape-filtered scan, E2E-036
  targeted Channel-code-region scan, plus the original E2E-029 discovery): every real
  candidate found is either a confirmed false positive (coincidental offset reuse by
  unrelated classes — vectors, maps, destructors) or a real hit whose caller/construction
  site is reachable ONLY via virtual dispatch or register-indexed addressing that this
  project's ADRP+ADD/direct-reference-based disassembly tooling cannot trace. This same
  specific wall was hit independently for THREE different target functions (`0x94c540`,
  `0x93a5e4`, and the Channel-destructor-adjacent code in E2E-036). This is a structural
  tooling limit for this class of problem, not a lack of effort — a symbolic-execution or
  proper decompiler (Ghidra/IDA with an actual C++ vtable/RTTI-aware analysis, rather than
  a hand-rolled Capstone script) would very likely resolve it in minutes; this project has
  not had that tool available.
- **Wire-format guessing** for `onChannelLogin`'s payload: 3 labeled variants (pickle/u8-index,
  marshal, u16-index via `longEntityMessage`), tested live, repeated 407 times over ~20s
  under a fixed retry-flood — zero observable effect in ALL cases (E2E-027/028/037).
- **Live memory verification** of the actual gate value at multiple points in the session
  timeline — this DID produce a real, surprising result (the toggle, E2E-035), correcting a
  wrong assumption, but did not by itself unblock progress once the retry-flood follow-up
  also came back null.

**Honest assessment**: continuing to iterate on this exact thread (more wire-format guesses,
more static setter-hunting) has a low expected payoff right now. Both the "is our format
right" question and "is the gate open long enough" question have been tested about as far as
this project's current tools allow, and the combined result (407 packets, all 3 formats, all
null) is a genuinely ambiguous negative — it does not cleanly point to "keep trying" or "give
up," which is itself informative: it suggests the missing piece is NOT a small parameter
tweak, but something more structural (see options below).

## 3. Genuinely different angles NOT yet tried (not variations of what's been ruled out)

These are cheap, don't require solving the two big standing blockers (script.npk, native
tooling limits), and haven't been attempted:

1. **Enable the engine's own diagnostic/debug logging, rather than guessing at wire bytes.**
   This project has found MANY instances of a debug-flag-gated verbose-logging pattern in
   the native code (`ldrb w8, [0x3915000+0x320]`-style checks, seen in `processFilteredPacket`,
   the entity-message dispatch stubs, `Channel::send`, etc. — at least 6+ distinct sites
   across this investigation). If ANY of these flags is controllable from outside the
   encrypted script layer (an Android system property, a world-writable config file on
   `/sdcard`, a command-line/intent-extra flag, or a NeoX-specific debug resource) — NOT
   yet checked — flipping it could produce dramatically more informative logcat output
   about what the client's native AND script layers are actually doing with our packets,
   without needing to decrypt anything. This is a concrete, bounded static-analysis task
   (find what controls that debug-flag byte) that hasn't been attempted at all so far.
2. **Check the entity-defs/interface fingerprint validation this project already found early
   on** (`06_trace/MERCURY_PACKET_MAP.md`/LoginApp reply analysis: a comparison against the
   literal constant `0x32ef9816`, inferred as a version-mismatch guard) — has anyone
   confirmed THIS check actually passes cleanly in our current session, or could it be
   silently failing in a way that leaves entity RPC dispatch in some degraded/inert state
   even though `createBasePlayer` itself (a lower-level mechanism) still succeeds? Not
   independently re-verified since it was first noted.
3. **Just wait longer, doing nothing new.** Every live test so far has run for at most
   ~20-90 seconds. Given BigWorld's own timeout literals seen in this binary are sometimes
   much longer (the `InactivityTimeout` was 10s, but other timers — resource/version-check
   retry backoff, connection-quality grace periods — could plausibly be tens of seconds to
   a few minutes). A single long-duration (5-10 minute), completely passive observation
   (server just does what it already does — createBasePlayer, channel ACK, keep-alive — no
   new experimental pushes at all) to see if the client EVER spontaneously calls `handshake`
   or shows any new behavior on its own has not been explicitly tried as its own controlled
   experiment (it's always been intermixed with active experimentation).
4. **Real ARM64 hardware + dynamic instrumentation** (the option the coordinator named) —
   this is the one PROVEN path (ROS Legacy's own working `.nxs` overrides are direct
   evidence someone solved this exact problem with it). It is a legitimate, standing
   human-decision point (infrastructure/environment change, previously flagged back in
   E2E-004/005), not a new idea — but worth naming explicitly as "the only approach with
   direct proof-of-concept evidence that it works," as opposed to the native-only threads,
   which have no comparable existence proof of a solution reachable this way.

## 4. What I would NOT recommend spending more time on right now

- Further guessing at `onChannelLogin`'s exact byte layout without a new oracle — the
  format-guessing space is large and mostly unfalsifiable without better observability.
- Further static hunting for `entity+0x140`'s setter using the same class of technique
  (ADRP+ADD/direct-reference scanning) — this has failed on 3 independent targets now for
  the same structural reason (virtual dispatch), and a 4th attempt with the same tools is
  unlikely to behave differently.
- Continuing to treat `identifyVersionPoint` as a live thread — it is closed, on 3
  independent lines of evidence.

## 5. Recommendation

This is a genuine, well-earned pause point for a human decision, not a dead end reached by
giving up early. The two standing structural blockers (script.npk's cipher, and this
project's disassembly tooling's inability to trace virtual/indexed dispatch) both still
apply. Options 1-3 in section 3 are cheap enough to be worth a bounded attempt before
committing to option 4's bigger infrastructure investment — none of them require new tools
or environment changes, just different static-analysis targets than what's been tried. Option
4 is the only approach with direct proof that it can work at all, at the cost of needing new
hardware/environment setup this project has flagged as a human decision since E2E-004/005.
