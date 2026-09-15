# PC ROS Launcher Study — Login-Bypass Architecture Lessons

Source studied (read-only, not part of this repo): `C:\Users\Raysoo\Desktop\launcher`, a
separate git repo belonging to the same user. This document reports what was found there and
what, if anything, transfers to this project's (`ROS_RE`, Android `com.netease.chiji`) Mercury
reply-ID and Blowfish-key blockers. Evidence labels follow this project's convention:
CONFIRMED (directly read in source/logs) / STRONGLY SUPPORTED (consistent multi-file evidence) /
INFERRED (plausible reading, not directly proven) / UNKNOWN.

## 1. What this launcher is

- **CONFIRMED**: PC client, binary `ros.exe` (BigWorld/NeoX engine, Windows), install paths seen
  in scripts: `C:\ros`, `C:\Users\User\Desktop\RulesOfSurvival\_RUNTIME\ros-revival\client_full\app`.
  This is a different platform/binary from the Android `com.netease.chiji` client this project
  targets, confirming the task brief's assumption.
- **CONFIRMED**: An Electron shell (`main.js`, `preload.js`, ~100 lines total) is a thin UI
  wrapper only. `main.js` line 55-59 just spawns `app_engine/IN_Launcher.py` via
  `child_process.spawn`; it has no network or login logic of its own. All real work happens in
  the Python `app_engine` layer.
- **CONFIRMED**: This is a **from-scratch local revival**, not a client of NetEase's live
  servers nor of the third-party "ROS Legacy" service this project already studied (no
  `net.roslegacy.prod` references found anywhere in the launcher, `.aider.chat.history.md`, or
  the tools). The launcher's own local Python processes implement LoginApp/BaseApp themselves
  (`app_engine/tools/servers/loginapp_server.py`, `baseapp_server.py`).
- **CONFIRMED**: `app_engine/IN_Launcher.py` (17.7KB, last modified Aug 17) is the current/live
  entry point — it is what `main.js` spawns and what `ros_launcher.log` (the most recently
  written log, entries through 2026-08-17 10:59) records. `IN_Launcher_2020.py` and
  `IN_Launcher_ROS2.py` are smaller (4.9KB/6.6KB), older (Aug 15), and their own logs
  (`ros2020_launcher.log`, `ros2_launcher.log`) stop on Aug 15 — superseded, not current.
- **CONFIRMED**: `.aider.chat.history.md` is mostly noise for this purpose — it's a stalled
  aider (AI pair-programming CLI) session log dominated by OpenRouter/model-selection errors
  in its first ~100 lines and general boilerplate; it contains no narrative about login,
  Mercury, Blowfish, or RSA (grepped for all those terms — zero substantive hits). The real
  narrative lives in code comments inside the Python tools themselves, which are extensively
  and usefully self-documented with dated findings.

## 2. How it solves login/session — hybrid of network-server AND client-state patching

This is the single most valuable finding for this project. The launcher uses **two
complementary techniques together**, not one:

### (a) A real local LoginApp/BaseApp UDP server (network-protocol level)

**CONFIRMED** from `app_engine/tools/servers/loginapp_server.py` and `baseapp_server.py`:

- They run actual UDP listeners on the client's real LoginApp (20013) and BaseApp (20015)
  ports, speaking the real Mercury framing back to the client — this is architecturally the
  same idea as this project's own `mitm_serve.py` local-server-substitution approach, just for
  BigWorld/NeoX's specific wire format instead of ROS's Android-side one.
- **RSA key substitution, not RSA break**: the client's baked-in RSA public key (used to encrypt
  the login LogOnParams blob) is patched at runtime via Frida to a key pair the launcher
  generated itself (`our_loginapp.priv.pem` / `our_loginapp.pub.pem`, referenced in
  `loginapp_server.py` line 26 and built by `app_engine/tools/re/inject_rsa2.py`, with
  `inject_rsa.py` as the earlier RE/extraction step that located the RSA modulus/exponent
  constants in the embedded Python 2 interpreter's `patch.Headcode` module). This is why the
  local server's private key can decrypt real client traffic: **the client isn't tricked into
  skipping encryption — its trusted public key is swapped for one the operator controls before
  the client ever encrypts anything.**
- **The Blowfish session key IS transmitted by the client — inside the same RSA-OAEP blob.**
  This is the answer to this project's standing blocker. `loginapp_server.py`'s `parse_params()`
  (lines 121-144) documents, as a dated, "LIVE-VERIFIED" finding (2026-06-30, confirmed across
  two boots): the decrypted `LogOnParams` blob layout is
  `flags(u8) | username(packed-str) | password(packed-str) | encryptionKey(packed-str) | digest(16) | tail(u32)`,
  and the **third packed string is the per-session Blowfish key** the client uses to initialize
  its own `Mercury::EncryptionFilter`. They proved this empirically: across two fresh client
  boots, only that field changed (`0391deeb` → `dfc59eb9`) while username/password/digest stayed
  constant, and the full blob parses to exactly 52 bytes with nothing left over — ruling out
  their earlier, wrong heuristic (`rstrip('\x00')[-16:]`, which was actually reading the digest
  tail as garbage, only "working" because a separate Frida hook was force-overwriting the
  client's live cipher context anyway).
  - **STRONGLY SUPPORTED, not fully closed out**: as of the last comment in that function
    (still present in the current file), the *reply* path had not yet been cut over to
    self-keying from this recovered key on a clean boot — a `ROS_REPLY_BFKEY` env flag lets it
    toggle between using the recovered `bf_key` directly (the intended, "self-keying" endpoint)
    and falling back to a previously Frida-captured fixed context (`bfctx.bin`, `_bfctx`) as a
    known-good fallback. The code comment explicitly frames self-keying as "the foundation for
    ... deletes forcectx + the 0x242df0 validity-force + the disconnect-NOP" — i.e., an
    in-progress migration off the force-context crutch, not a finished, verified-clean-boot
    result at time of last edit.
- **Mercury reply-ID correlation bug found and fixed**: a dated comment in `loginapp_server.py`
  (around line 288) records that the request/reply correlation ID is a **uint32 at offset 5**
  in the client's request packet (after a 2-byte flags/msgid area and a 2-byte length field at
  offset 3), not a uint16 at offset 6 as they'd originally assumed — the wrong offset produced
  "Couldn't find handler for reply id" client-side errors until corrected. This is the same
  *category* of bug this project has been chasing (reply-ID correlation not working as
  documented) — the PC finding doesn't hand over the Android offsets, but it is direct evidence
  that Mercury's request-ID field position is a common, easy-to-mis-locate source of this exact
  symptom class, and that brute-force offset sweeping against a real client is how they found it.
- **CONFIRMED, dated 2026-07-30**: they also had to reverse-engineer the login **reply envelope
  shape** itself, not just its content — `loginapp_server.py` supports a `ROS_REPLY_SWEEP` mode
  that cycles multiple candidate header/framing variants (different length fields, flag bytes,
  whether a reply-ID is echoed inline) against the live client and watches whether the client
  stops retrying LoginApp and starts talking to BaseApp instead. A code comment in
  `IN_Launcher.py` (~line 139) records the empirical result: "of the 10 candidate baseApp reply
  envelopes, attempt 7 ('plain canonical key=bfctx', u32 length field) was the one the client
  ACCEPTED." **The bug-hunting method — sweep framing variants and use the client's own next
  observable action (does it retry, or move on?) as the pass/fail oracle — is the reusable
  lesson here, independent of the specific byte offsets, which are PC-binary-specific and do not
  transfer.**

### (b) Frida-based patching of the client's own embedded Python state (client-state level)

**CONFIRMED** from `app_engine/tools/re/login_fix_hall.py` and its invocation in
`IN_Launcher.py`'s `run_injector()`:

- The BigWorld/NeoX PC client embeds a Python 2 interpreter running the game's own `.py`/`.pyc`
  script layer (same architecture the Android client's `.nxs` scripting layer is presumed to
  share, per this project's own prior findings).
- Even after the local LoginApp/BaseApp servers get the client to accept a login reply, the
  client's own login-completion script code (`channel_login.py`, per the comment) still crashes:
  it references `Globals.channel` (the real NetEase SDK connection object), which is `None` in
  this offline setup, and code paths like `onLoginByServerSauth`/`onLoadCharacter` dereference it
  and abort before reaching `enterHall`.
- Their fix is **not** a binary patch — it's a **live monkey-patch of the client's own Python
  namespace**, injected via Frida by hooking `PyEval_EvalFrameEx` (deferred until ~5000 frames
  and 3+ seconds after attach, specifically to avoid firing before the interpreter's subsystems
  are constructed — an earlier, too-early attempt hit access violations) and using it to call
  back into the embedded interpreter (`PyRun_SimpleString`-equivalent) with code that replaces
  `Globals.channel` with a stub object presenting the attributes/methods the login-completion
  code expects, so those calls no-op successfully instead of crashing.
- **Reusable architectural lesson**: when the client embeds its own interpreted scripting layer,
  a from-scratch server does not have to get every protocol detail byte-perfect — some of the
  client's brittleness is in its own script glue code (expecting a real SDK object that a local
  server can never fully emulate), and that can be neutralized more cheaply by patching the
  client's runtime script state directly than by trying to make the server's protocol replies
  satisfy every downstream consumer.

## 3. Network protocol / Mercury / crypto handling — summary

- **Not avoided — implemented.** They did not bypass Mercury networking via pure Frida
  state-forcing (e.g., forcing the client straight into "already in lobby"); they built real
  LoginApp/BaseApp UDP responders and drove the client through actual (if imperfect) protocol
  exchanges, only patching the embedded Python script layer for the specific downstream crash
  described in §2(b). `run_baseapp_force()`/`run_injector()` in `IN_Launcher.py` show both
  techniques are wired up and run together on every launch — network-level server plus
  Frida-based client patches, not either/or.
- **The Blowfish key transmission answer, restated plainly for this project's blocker**: on the
  PC client, the "randomly generated, never transmitted" framing is **wrong** — the key is
  generated client-side, yes, but it IS transmitted, packed inside the very first RSA-OAEP
  encrypted login request as one of several packed strings alongside username/password. A
  from-scratch server does not need to guess or pre-share this key; it needs to (1) control the
  RSA keypair the client encrypts with (by patching the client's baked-in public key, since the
  real NetEase private key is obviously unavailable) and (2) parse the decrypted blob correctly
  to pull the key out. **If the Android client's LoginApp handshake follows the same NeoX/Mercury
  `LogOnParams` convention (RSA-OAEP-wrapped blob containing username/token/session-key/digest as
  packed strings), the equivalent fix there is: get the ability to decrypt that first blob (by
  controlling the RSA key the client trusts, e.g. via a Frida/Xposed hook overwriting the
  compiled-in public key or modulus/exponent constants before the client's key-encrypt call
  fires), then read the session key back out of the parsed structure — not try to derive or
  intercept it after the fact.** This is INFERRED as a hypothesis to test on Android, not
  confirmed to be identical there — the PC and Android clients could still differ in field order,
  packing format, or whether the key even lives in the same message.
- Their own crypto RE method for the Blowfish cipher itself is also documented and may be a
  useful technique reference: `BlowfishCtx` in `loginapp_server.py` implements the exact
  bit-for-bit Blowfish core (P-array/S-box Feistel rounds) plus a **non-standard CBC chaining
  variant** they reverse-engineered from the client's disassembly (offsets `0x1501080` /
  `0x14b50b0` / `0x242d6a` in their PC binary) — the client XORs each plaintext block against the
  *previous plaintext* block (not the previous ciphertext, as textbook CBC would), with IV=0.
  This non-standard chaining was apparently necessary to get from "server sends bytes the client
  doesn't reject" to "client actually recovers the intended plaintext" — a reminder that even once
  a key is known, EncryptionFilter's exact chaining mode still has to be independently verified
  against disassembly rather than assumed to be textbook CBC/ECB.

## 4. Current working status — honest assessment: partially working, gameplay entry still broken

- **CONFIRMED, NOT fully working today.** The gameplay.md claim "Login & Session Management
  (Na-bypass na)" is checked off, and the evidence supports that the *login handshake itself*
  (LoginApp accept → BaseApp accept, i.e. the client stops retrying and starts sending normal
  channel keepalive/ack traffic) was achieved and reproducible as of 2026-07-30 (dated comment,
  `IN_Launcher.py` ~line 139-143).
- **CONFIRMED, this is where it currently stalls**: getting further — the client creating a real
  game entity (`createBasePlayer(Avatar)` + `createCellPlayer` + space data, i.e. actually
  entering the hall/lobby with a live avatar) — causes a **native crash inside `ros.exe` every
  time it's been tried**, three independent confirmed crashes across two rounds of attempts
  (`IN_Launcher.py` lines 120-127, dated 2026-07-31). The code comment explicitly states: "Root
  cause remains unidentified (no crash-dump symbol tooling available in this environment...). Do
  not re-enable without either (a) proper crash-dump analysis tooling, or (b) a fundamentally
  different approach... discussed with the user first." The corresponding feature flag
  (`ROS_PUSH_KEEPALIVE_ADVANCE`) is left commented-out/disabled in the current file.
  `app_engine/tools/servers/CRASH_*.bin` (100+ crash-dump-like files) in the servers directory is
  consistent with a long, still-unresolved crash-hunting history, though those specific dumps
  looked NetEase-appdump-upload-related (`appdump.x.netease.com POST /upload`) rather than local
  `ros.exe` process dumps — UNKNOWN whether they are the same crashes referenced in the code
  comments or a different (SDK-side) crash channel entirely.
- **CONFIRMED**: the most recent log evidence (`app_engine/ros_launcher.log`, entries through
  2026-08-17 10:59) shows the last recorded run exiting `ros.exe` after only ~2 seconds
  ("ros.exe launched with PID 21252" → "ros.exe exited; launcher shutting down" essentially
  immediately), and the corresponding `LOGINAPP.txt`/`BASEAPP.txt` server logs from that same
  session (Aug 16 23:17 run, the last one with content) show only server-startup banner lines —
  **no actual login attempt was logged in the most recent captured session**, unlike earlier
  sessions (`LOGINAPP_OLD.txt`) which do contain full hex-dumped accepted exchanges. This is
  consistent with either a regression, an environment change (e.g. `ros.exe` failing before it
  even reaches the point of dialing LoginApp), or simply a short manual test that was killed
  early — **UNKNOWN which**, and this launcher's own state should be treated as "was demonstrated
  working for login-only, gameplay-entry unresolved, most recent run inconclusive" rather than
  "currently confirmed fully working."
- The `live.log` from the HTTPS/SDK-side MITM server (a separate, non-Mercury piece of the
  puzzle handling NetEase's `matrix.netease.com`/`update.netease.com`/etc. HTTP(S) SDK calls via
  hosts-file redirection + a local CA + a `connect()`/`WSAConnect()` Frida hook forcing all
  outbound TCP to 127.0.0.1) shows those HTTP-layer SDK calls succeeding locally (hotfix check
  OK, sdk-init OK, `listerr` OK) up through the point the client proceeds to dial the game
  server IPs (`123.58.173.219:443` etc., also redirected to loopback) — i.e., the SDK/login-portal
  layer above Mercury is handled and working; the remaining wall is specifically inside the
  Mercury/BigWorld game-session layer described above.

## 5. Lessons applicable to the Android (`ROS_RE`) project

1. **Re-examine whether the Android LoginApp request actually carries its own Blowfish key.**
   The PC finding that the session key is one of several RSA-OAEP-wrapped packed strings
   alongside username/password is a concrete, testable hypothesis: if the Android client's
   first LoginApp packet is similarly RSA-encrypted and this project can get visibility into the
   decrypted plaintext (even just once, via a runtime hook logging the buffer right after the
   client's own RSA decrypt/encrypt call), check whether a plausible session key sits alongside
   the credentials rather than assuming it must be derived or intercepted separately.
2. **Controlling the trusted RSA public key is the lever, not breaking RSA.** The PC approach
   never attacked NetEase's real RSA key — it patched the client's copy of the *public* key
   (which the client itself uses to encrypt, so swapping it is enough to let an
   operator-controlled private key decrypt everything) before the client's first encrypt call.
   The Android equivalent is finding wherever the client's embedded/compiled public
   key/modulus/exponent constants live and confirming they can be overwritten pre-handshake via
   Frida/Xposed, the same way `inject_rsa2.py` does on the PC binary.
3. **Sweep-and-observe is a valid method for framing/offset uncertainty.** Both the reply-ID
   offset bug and the reply envelope shape were resolved not by pure static analysis but by
   generating multiple candidate byte layouts and using the live client's subsequent behavior
   (does it retry LoginApp, or move on to BaseApp?) as ground truth. If this project's reply-ID
   correlation continues to fail "as documented," a similar brute-force sweep against a live
   Android client (varying candidate offsets/widths for the request/reply-ID field) may find the
   real offset faster than continuing to trust the documented layout.
4. **A from-scratch server does not need to be perfect if the client's own script layer can be
   patched too.** If the Android `.nxs` layer has an analogous "expects a real SDK/channel
   object, crashes when null" pattern, the two-pronged approach (network server gets the
   handshake far enough + a runtime script patch stubs the specific object the client scripts
   dereference) may be more tractable than trying to make the network layer alone perfectly
   satisfy every downstream consumer.
5. **Treat "login/session bypassed" and "can enter live gameplay" as two separate milestones with
   independent failure modes.** The PC project's own experience is a cautionary tale directly
   relevant to this project's recent "native-bridge visibility wall" findings (E2E-003/E2E-004
   commits): even after LoginApp/BaseApp accept a session, the step of instantiating a real
   player entity client-side can hit an unrelated native crash wall that requires its own
   separate investigation (crash-dump/symbol tooling) — solving Mercury correlation and Blowfish
   keying does not guarantee gameplay entry follows automatically.

## 6. Lessons NOT applicable / platform differences to keep in mind

1. **No byte offsets, RVAs, or memory addresses transfer.** Every specific offset in this
   document (`0x176ce0`, `0x1501080`, RSA hook RVAs, the "offset 5" reply-ID field, the exact
   `LogOnParams` field order) was reverse-engineered against a specific Windows PC `ros.exe`
   build and its x86 disassembly. The Android client is a different binary, likely a different
   protocol-library build/version, and almost certainly has different field layouts even if the
   underlying NeoX/Mercury concepts (RSA-wrapped LogOnParams, EncryptionFilter Blowfish, replyID
   correlation) are shared in spirit.
2. **Different injection substrate.** The PC approach hooks `PyEval_EvalFrameEx` in a native x86
   process via Frida's standard `Interceptor.attach`/`NativeFunction` on a desktop OS with full
   process/module introspection. Android's equivalent (per this project's own recent work) faces
   a distinct native-bridge/visibility problem set (ARM64, app sandboxing, Frida-gadget
   constraints already noted in this project's own E2E-004 log) that is not solved by anything
   found in the PC launcher.
3. **PC client's crash-debugging gap (no symbol/minidump tooling) is a known limitation of that
   project, not a solved problem to import.** Its native-entity-creation crash is explicitly
   unresolved; nothing here provides a way around Android's own equivalent gap.
4. **The HTTP(S)/SDK-layer MITM (hosts file + local CA + `connect()` hijack)** solves a portal/SDK
   problem (NetEase login-portal, hotfix, error-reporting endpoints) that is architecturally
   simple (ordinary HTTPS MITM) and likely already familiar territory for this project's own
   Android MITM work — it is not the hard or novel part of the PC launcher's solution, and is
   included here only for completeness (§4).
5. **This is a single hobbyist's evolving, partially-broken personal project, not a maintained or
   authoritative reference.** Its code comments show multiple abandoned experiments, disabled
   flags, and an explicitly "root cause unidentified" open crash bug. Treat its documented
   findings as leads to independently verify against the Android client, not as settled facts to
   build directly on top of.
