# ROS Private Server Adaptation Plan

Scope: design/planning only, for LOCAL/private-server LAN testing of
`com.netease.chiji` v1117219 against infrastructure we fully own. No original
NetEase production server is contacted or depended upon anywhere in this
plan. No third-party (ROS Legacy) production server is contacted, probed, or
depended upon. No brute-forcing, key-guessing, anti-cheat bypass, or fake
success-state patching is proposed. Every conclusion is labeled CONFIRMED /
STRONGLY SUPPORTED / INFERRED / UNKNOWN per this project's convention, citing
the specific prior document each claim comes from.

---

## 1. Objective

Reach a genuine, un-faked client → LocalAuthServer → LoginApp → BaseApp →
Lobby/Avatar progression on LAN/localhost, using our own private-server
implementation end to end, while stopping short of re-solving the
already-well-scoped-as-UNRESOLVED first-LoginReply Blowfish key paradox by
brute force, guessing, or client crypto patching. Where that paradox still
blocks BaseApp entry, this plan says so explicitly rather than routing around
it with a fake success state (which the task's constraints forbid).

This plan does **not** attempt Battle/CellApp (Phase 7) and does not copy any
ROS Legacy proprietary code — only the general architectural *pattern* their
build demonstrates ("an authenticated client carries a server-recognizable
session identity") is considered, and only where it actually maps onto our
own client's real traffic shape.

---

## 2. Original ROS Flow

CONFIRMED / STRONGLY SUPPORTED, cited from `06_notes/LOGIN_FLOW_TRACE.md`,
`06_notes/NATIVE_LOGON.md`, `06_notes/G2_GAME_SESSION_TRACE.md`,
`06_trace/NATIVE_BOUNDARIES.md`, `06_trace/LOGONPARAMS_SERIALIZATION.md`,
`06_trace/LOGIN_REPLY_RECORD.md`, `06_trace/CHECK_SCRIPT_BASEAPP_ADDR_TRACE.md`:

```
Java: NetEase MPay/UniSDK web-auth UI (Channel/SdkMgr, com.netease.mpay.oversea.*)
  -> HTTP POST /api/users/login/guest, /api/users/login/v2/sdk_token, /api/minors/*
  -> SdkNeteaseGlobal$LoginCallback.onLoginSuccess/onFailure  [loginDone step]
  -> ntOnLogin(unisdk_code)                                    [JNI into native]
  -> Python: ui/UILogin.py -> requestServerList() -> reads server_list_ad.txt
  -> Python: doLoginGame()
  -> Native: ServerConnection::logOnBegin(host, port, ...)      [0x93bcc8]
       - constructs EncryptionFilter with RAND_bytes(4) key BEFORE any I/O (0x917070->0x93a620->0x988cf8)
       - builds LogOnParams {flags, stringA, stringB, stringC, digest[16], u32} (0x9d8014)
       - RSA-OAEP-2048-encrypts {flags,stringA,stringB,stringC} with entities/loginapp.pubkey
       - sends 273-byte Mercury bundle to LoginApp :25000 (10 retries, ~0.43s cadence)
  -> LoginApp (original, dead): decrypts LogOnParams, replies with LoginReply
       (Mercury REPLY_MESSAGE_ID 0xFF, 20-byte LoginReplyRecord body, Blowfish-CBC
       encrypted under the client's own never-transmitted RAND_bytes(4) key)
  -> Native: LoginHandler::onLoginReply (0x938070) decrypts body (0x989600, unconditional)
       -> BaseApp address string built (this+0x24) -> checkScriptBaseAppAddr (log only)
       -> createBaseAppLoginRequest (0x9387cc) -> BaseAppExtInterface::baseAppLogin sent once, 5s timeout
  -> BaseApp (original, dead): accepts baseAppLogin, creates Account entity,
       pushes ClientInterface::createBasePlayer / createCellPlayer
  -> Lobby (Athlete entity) / eventually CellApp for battle
```

Key CONFIRMED facts that constrain everything below:
- The HTTP auth tier (`/api/users/login/guest`, `/api/users/login/v2/sdk_token`,
  `/api/minors/*`) is a plain JSON-over-HTTP(S) API the client's own UniSDK/MPay
  stack already speaks — **not** something that requires a new client-side
  network call to be written (`06_notes/LOCAL_SESSION_CONTRACT.md`,
  `06_notes/LOGIN_FLOW_TRACE.md`).
- `server_list_ad.txt` is a plain-text/HTTP-served resource naming the
  LoginApp host:port the client will `logOnBegin` against
  (`06_trace/LAN_FEASIBILITY.md` §2 row C, `06_notes/LOGIN_FLOW_TRACE.md`
  "Existing Creation/Offline Path").
- `LogOnParams`'s RSA-OAEP block only covers 4 of 6 wire fields
  (flags+stringA/B/C); a 16-byte digest and a u32 are always plaintext
  (`06_trace/LOGONPARAMS_SERIALIZATION.md` §5, CONFIRMED).
- The Blowfish key used to decrypt the **first** LoginReply is a
  process-local `RAND_bytes(4)` value, generated before any network I/O,
  never transmitted in any request, with no discovered data-flow edge from
  the RSA path, the JNI/session layer, or the script/Python layer into that
  key (`06_notes/FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md`,
  `06_trace/CHECK_SCRIPT_BASEAPP_ADDR_TRACE.md` — both CONFIRMED as a
  well-scoped absence, not an unexplored gap).
- The client's own dynamic capture harness (`mitm/local_baseapp_capture.py`)
  already gets Mercury framing fully correct (Attempt H reaches
  `LoginHandler::onLoginReply` and `checkScriptBaseAppAddr` live) but the
  BaseApp address it decodes is garbled because the local server does not
  know the client's Blowfish key — CONFIRMED live, reproduced twice
  (comment block in `mitm/local_baseapp_capture.py`, cross-referenced with
  `06_trace/CHECK_SCRIPT_BASEAPP_ADDR_TRACE.md`).

---

## 3. ROS Legacy Flow

Cited from `07_ros_legacy_approach/ROS_LEGACY_APPROACH_STUDY.md` (already
completed this project, not re-derived here):

```
Gate 1 (Java/smali, INFERRED architecture, not independently tested by us):
  RosAuth (custom class) -> SdkMgr.setPropStr/setPropInt + Channel.loginDone(0)
  -> short-circuits the MPay web-auth UI entirely -> ntOnLogin fires as if a
  real SDK login succeeded

Gate 2 (native, CONFIRMED by full disassembly of libmsaoaidsec_arm64.so):
  A from-scratch ~2.7KB library, loaded as a normal JNI lib impersonating an
  OAID/anti-fraud stub name, does two unrelated things:
   (a) hooks a JNIEnv-table string-accessor slot, FNV-1a(0x811c9dc5,0x1000193)
       hashes some observed string (likely a ticket), caches the hash globally
   (b) manually PLT/GOT-patches libclient.so's own sendto() relocation entry
       (via /proc/self/maps parsing + hand-rolled ELF symtab walk + mprotect,
       NOT LD_PRELOAD/Zygote/seccomp) so that any OUTGOING 24-byte packet
       matching signature `01 00 00 0b ...` gets its bytes [0xb..0xf) stamped
       with the cached FNV hash before the real sendto() is called
```

**What Legacy actually solved (CONFIRMED)**: a way to stamp a
server-recognizable session identifier onto one specific outgoing UDP
handshake packet, entirely via GOT-patching a transport-layer syscall — a
pure session/routing tag at the UDP envelope layer, with **zero** contact
with OpenSSL, `RAND_bytes`, `BF_set_key`, or `EncryptionFilter` anywhere in
its ~2.7KB of code (exhaustively confirmed: no crypto import, no
`libcrypto.so`/`libssl.so` `DT_NEEDED` linkage, no crypto string anywhere in
`.rodata`/`.dynstr`, entire `.text` section disassembled and accounted for).

**What Legacy did NOT solve (CONFIRMED negative result, Study §4)**: the
Blowfish-key paradox for the first LoginReply. Their own `libclient.so`/game
engine (same NeoX/BigWorld lineage) would independently generate the same
kind of process-local `RAND_bytes(4)` key that ours does; Gate 2 never
touches it. The Study explicitly flags two open readings for how their
*server* nonetheless works for their unmodified client (a hidden
`libclient.so`-level patch we have no access to audit, or their server
tolerating/exploiting weak post-decrypt validation) — both **UNKNOWN**, both
about a third party's live infrastructure this project has no standing
permission to probe.

**Direct structural mismatch with our client (CONFIRMED, Study §2)**: Gate
2's hook only fires on a 24-byte packet with magic bytes `01 00 00 0b`. Our
own client's actual first LoginApp datagram is **9 bytes**
(`mitm/captures/BASEAPP_LOGIN_CAPTURE.txt`, dozens of occurrences, zero
24-byte or `01 00 00 0b`-prefixed datagrams anywhere in the capture set).
Reusing Gate 2's exact hook against our client's traffic would never fire —
the length check alone rejects it. Our client also ships **no**
`libmsaoaidsec*.so` under any name (full recursive Glob/grep of
`01_apk/`, `02_dex/`, `03_lib/` returns zero hits), so there is no drop-in
slot to swap it into even if the signature were adapted.

**Verdict for this project**: Legacy's Gate 2 mechanism is architecturally
interesting but not adoptable as a mechanism — different packet shape,
different library surface, and (per its own study) it does not solve the
one problem (Blowfish key) that would make adopting it worthwhile. Gate 1's
*pattern* (a custom login-shortcut class calling the SDK's own
`setPropStr`/`setPropInt`/`loginDone` to fake a completed SDK login) has a
structurally equivalent target in our own client
(`com/netease/neox/Channel.smali` `loginDone(I)`, `setPropStr`/`setPropInt`
forwarding to `GamerInterface` — STRONGLY SUPPORTED, Study §3) — but see §5
below: **we do not need it**, because our HTTP auth tier already achieves
the same outcome without any smali patch at all.

---

## 4. Proposed Private Server Flow

```
                      ┌─────────────────────────────────────────┐
                      │        Private Server Host (PC)          │
                      │                                           │
  Android Client      │  ┌───────────────┐   ┌─────────────────┐ │
  (unmodified Java/   │  │ HTTP(S) Auth   │   │  Session Store   │ │
   smali auth path;   │  │ Tier (mitm_    │──▶│  (sqlite/flat    │ │
   asset-level RSA    │  │ serve.py, ALREADY│  │  file)           │ │
   pubkey swap only,  │  │ WORKING)       │   │  session_id ->   │ │
   see §9)            │  │  /login/guest  │   │  player_id       │ │
        │             │  │  /login/v2/... │   └────────┬─────────┘ │
        │  HTTP(S)    │  │  /api/minors/* │            │           │
        ├────────────▶│  └───────┬───────┘            │           │
        │             │          │ embeds session_id    │           │
        │             │          │ in user_id/token      │           │
        │             │          ▼                       │           │
        │             │  server_list_ad.txt ──────────▶ points at   │
        │             │                                 LoginApp    │
        │  UDP :25000 │                                   host:port │
        ├────────────▶│  ┌───────────────┐               │          │
        │  LogOnParams│  │  LoginApp      │◀──────────────┘          │
        │  (RSA block)│  │  :25000        │                          │
        │             │  │  - own keypair │  lookup session_id in    │
        │             │  │  - decrypts    │  Session Store           │
        │             │  │    stringB/C   │                          │
        │             │  │  - builds      │                          │
        │             │  │    LoginReply  │                          │
        │             │  └───────┬────────┘                          │
        │◀────────────┤          │ 20-byte LoginReplyRecord           │
        │  LoginReply │          │ (Blowfish-CBC — SEE §13 BLOCKER)   │
        │             │          ▼                                    │
        │  UDP        │  ┌───────────────┐                            │
        ├────────────▶│  │  BaseApp       │  creates Account entity,  │
        │ baseAppLogin│  │  :2501x        │  pushes createBasePlayer  │
        │             │  └───────┬────────┘                           │
        │◀────────────┤          │                                    │
        │ createBase- │          ▼                                    │
        │ Player/Lobby│  ┌───────────────┐                            │
        └─────────────┤  │ (Phase 7, NOT │                            │
                      │  │ IN SCOPE)     │                            │
                      │  │ CellApp        │                            │
                      │  └───────────────┘                            │
                      └─────────────────────────────────────────┘
```

Everything left of "SEE §13 BLOCKER" is either already working
(`06_trace/LAN_FEASIBILITY.md` T15–T17b, `DECISIONS.md`) or a small, additive
change to a server we already run. Everything right of it is the one
genuinely unresolved dependency, carried forward honestly rather than
papered over.

---

## 5. Authentication Boundary

**Where the external NetEase auth result becomes internal "logged in"
state**: not at a single Java call site as the task's naive hypothesis
suggested, but at the **HTTP response tier**, one layer earlier than
`Channel.loginDone`/`ntOnLogin`. Evidence:

- `06_notes/LOCAL_SESSION_CONTRACT.md` (status: FOUND, PASS) already
  demonstrates that `/api/users/login/v2/sdk_token` returning a
  schema-compliant JSON body (`user_id`, `sdk_token`, `code:0`, `msg:""`)
  is parsed successfully by `com.netease.mpay.oversea.h.a.a`
  (`optString("user_id")` at Dalvik `0x3d34cc`, `optString("sdk_token")` at
  `0x3d34d8`) and is sufficient to avoid the `onFailure(1000, "Cancel
  login")` path documented in `06_notes/LOGIN_FLOW_TRACE.md`.
- `06_notes/LOGIN_FLOW_TRACE.md` "Root Cause"/"Recommended Legitimate Fix"
  independently reaches the same conclusion: serving schema-compliant
  `/api/users/login/guest` and `/api/users/login/v2/sdk_token` responses is
  what lets `onLoginSuccess` fire via `h.c.c$7`, without touching
  `Channel.smali` or any native code.
- This is **already implemented and live-verified** in `mitm/mitm_serve.py`
  and exercised through `DECISIONS.md` T15–T17b, which record the client
  reaching the title screen, PLAY button, and `requestServerList`/
  `channelLogin` with **zero** patch to any `.smali`, `.dex`, or `.so` file.

**Conclusion (CONFIRMED, not the naive hypothesis)**: the boundary is
`HTTP JSON response body -> com.netease.mpay.oversea.h.a.a parser ->
onLoginSuccess -> Channel.loginDone -> ntOnLogin -> requestServerList ->
doLoginGame -> ServerConnection::logOnBegin`. A private auth result is
substituted **at the HTTP layer**, which is the smallest possible patch
surface: **zero client code changes**, only a server response body we
already control. The naive assumption that `Channel.loginDone` itself is the
substitution point is **incorrect** — that method is a downstream *effect*
of a successful HTTP response, not an injection point we need to touch.

**Why not use ROS Legacy's Gate 1 (smali `loginDone` short-circuit)
instead**: it would require a client-side smali edit (violates "prefer
Java/Smali/Python over native" is satisfied, but "minimum client
modification" is not — HTTP-layer substitution requires **zero** client
edits and is strictly smaller). Gate 1 is documented here as a fallback
option only, not the chosen path.

**Requirement not yet satisfied by the existing HTTP tier**: it does not yet
mint or carry a private-server *session identifier* usable by LoginApp. §6–7
close this gap.

---

## 6. Session Lifecycle

1. **Creation**: Client's existing UniSDK/MPay HTTP calls
   (`/api/users/login/guest`, then `/api/users/login/v2/sdk_token`) reach
   `mitm_serve.py`. On the `sdk_token` call, the server generates a random
   session id — a UUID4 or equivalent OS-random nonce (INFERRED design
   choice, explicitly **not** a cryptographic key derivation — per the
   task's own instruction this is not the Blowfish problem and does not
   need to be unguessable against a hostile actor, only unique per local
   test session).
2. **Delivery to client**: the session id is placed in the existing JSON
   response fields the client already parses and retains —
   `user_id`/`sdk_token` (both CONFIRMED-parsed string fields per
   `06_notes/LOCAL_SESSION_CONTRACT.md`). No new field, no new client-side
   parsing code. Example: `sdk_token = "sess_" + uuid4hex`.
3. **Client-side retention**: **INFERRED, not independently re-derived this
   pass** (out of this task's re-derivation budget; cited from the existing
   `com.netease.mpay.oversea.*` package tree confirmed present in Study §3)
   — the NetEase MPay SDK already persists `user_id`/`token` into its own
   SharedPreferences file (`06_notes/LOGIN_FLOW_TRACE.md` "has_minor Source":
   `com.netease.mpay.202cb962ac59075b964b07152d234b70.xml`, HashMap keys
   `'3'`=token, `'4'`=has_minor). Our session id rides inside that
   **existing** storage mechanism — we do not need to add SharedPreferences
   code or in-memory state of our own.
4. **Carry into LoginApp**: the retained `sdk_token`-as-session-id is placed
   by the client's own native `LogOnParams` construction into one of its
   three existing string fields (see §7 — this is a Python/script.npk
   change, not a native one, if a change is needed at all).
5. **Association**: LoginApp looks the session id up in a local flat-file or
   sqlite session store (`session_id -> {player_id, created_at}`) populated
   by the same HTTP tier at step 1 (single shared process or shared file
   between HTTP tier and LoginApp for a first LAN prototype — see §10 F).
6. **Expiry**: for a LAN test server, sessions can be process-lifetime only
   (in-memory dict) or persisted to sqlite for restart survival — either is
   acceptable; INFERRED, not a hard requirement of any client-observed
   behavior.
7. **Failure case**: if LoginApp receives a `LogOnParams` whose session
   field does not match any known session, this plan's default behavior is
   to still reply with a well-formed `LoginReply` pointing at a default/
   guest `player_id` (permissive local-server behavior — consistent with
   `06_trace/LOCAL_SERVER_MINIMUM.md`'s own finding that BaseApp login
   likely does not require a resubmitted validated secret). Strict rejection
   is a config option for later hardening, not required for Phase 1–5.

---

## 7. LoginApp Integration

Per `06_trace/LOGONPARAMS_SERIALIZATION.md` (CONFIRMED object layout),
`LogOnParams` already carries three general-purpose length-prefixed string
fields (`stringA`/`+0x10`, `stringB`/`+0x28`, `stringC`/`+0x40`) whose
semantic identity was **never confirmed** by static analysis (labeled
UNKNOWN, candidates "username/password/third credential" only by
plausibility). This is exactly the existing-field slot the task's Step 3/6
questions ask about.

**Chosen option: Option B (private session envelope carried in existing
LogOnParams fields), with the RSA layer made genuinely functional rather
than bypassed.**

Rationale over the three options in the task's Step 6:

- **Option A (modified LogOnParams struct)**: rejected — would require
  changing the native wire format (`addToStream`/`readFromStream`), i.e. a
  `libclient.so` patch. Explicitly the kind of native modification this
  project's constraints say to avoid unless proven unavoidable, and it is
  not: the existing 3 string fields are sufficient carrying capacity for a
  UUID-length session id.
- **Option C (existing handshake, locally-generated credentials, no
  envelope change)**: this is actually a **subset** of Option B once we
  observe that "locally-generated credentials" and "session envelope" are
  the same string field from the wire's point of view. We fold C into B: no
  distinction needed in practice for our client.
- **Option B (chosen)**: whatever populates `stringA`/`B`/`C` today (Python
  layer, per `06_trace/NATIVE_LOGON.md`/`06_notes/G2_GAME_SESSION_TRACE.md`,
  cited not re-derived) is left alone if it already forwards the
  MPay-retained token faithfully — in which case **zero** client change is
  needed at all, since our session id is already riding in `sdk_token`
  (§6.2–6.4) and the existing Python→native call chain simply carries
  whatever string value was already there. If (UNKNOWN until tested)
  the Python layer discards or overwrites that value before calling
  `logOnBegin`, the minimal fallback is a `script.npk` (Python) edit — not
  smali, not native — to explicitly pass the retained session token as one
  of the three strings.

**RSA key handling (new insight this pass, not previously stated as
architecture in prior docs)**: `06_trace/NATIVE_BOUNDARIES.md` and
`06_trace/LAN_FEASIBILITY.md` §4.2 both independently note that
`entities/loginapp.pubkey` is a client-side **data asset**, loaded (not
hardcoded in `.text`) by `logOnBegin` — **STRONGLY SUPPORTED by both
documents' architectural framing, but the actual `loginapp.pubkey` file was
not located on disk in this pass's Glob search of the repo**, so its
existence as an extractable/replaceable asset is **UNKNOWN pending a
concrete file-level confirmation**, not CONFIRMED. *If* it is a swappable
data asset (as both prior documents assume), then for OUR OWN private
server we can legitimately generate our own RSA-2048 keypair, replace the
public half in the client's asset package, and hold the matching private
key at our own LoginApp — this is **not** a DRM/anti-cheat bypass (it is
literally the documented, intended configuration point: "which server's key
do I trust"), **not** brute-forcing (we generate a fresh valid key, we do
not need NetEase's), and lets LoginApp perform real RSA-OAEP decryption of
`stringA/B/C` rather than "ignore the credential block entirely" as
`06_trace/LOCAL_SERVER_MINIMUM.md`'s permissive-fallback noted was also
possible. This is presented as the **preferred** path if the asset is
confirmed swappable, with the permissive/ignore-ciphertext fallback from
`LOCAL_SERVER_MINIMUM.md` kept as a documented degraded mode. **Locating and
confirming `entities/loginapp.pubkey`'s presence and format is listed as a
concrete Phase 3 task in §14, not assumed complete here.**

**What LoginApp does on receipt** (regardless of whether decryption is real
or skipped): parse the confirmed 273-byte / RSA-2048 envelope shape
(`LOGONPARAMS_SERIALIZATION.md` §5), extract the session-id string (from
whichever of stringA/B/C carries it, to be confirmed empirically — the
existing recommendation in that same document, "needs dynamic
instrumentation," applies), look it up in the session store (§6.5), resolve
a `player_id`, and proceed to §8.

---

## 8. BaseApp Integration

Per `06_trace/LOCAL_SERVER_MINIMUM.md` (Stage 3) and
`06_trace/CHECK_SCRIPT_BASEAPP_ADDR_TRACE.md` (CONFIRMED, complete call-graph
trace): the BaseApp address the client actually connects to comes
**exclusively** from the decrypted 20-byte `LoginReplyRecord` body — no
alternate/override/fallback source exists anywhere in the six functions
traced (`onLoginReply`, `checkScriptBaseAppAddr`, `finalizeLoginAttempt`,
`createBaseAppLoginRequest`, and its two helpers). This means:

- LoginApp must send a `LoginReply` whose body, **once decrypted by the
  client's own Blowfish key**, contains our BaseApp's real host:port in
  whatever the correct sub-field layout is (STRONG EVIDENCE the record is
  address-shaped; exact IPv4/IPv6/port byte layout UNKNOWN,
  `LOGIN_REPLY_RECORD.md`).
- Framing above the encrypted body (Mercury message ID 0xFF/REPLY,
  4-byte length, replyID echoing the client's own request counter, 1-byte
  status, then the 20-byte body) is **CONFIRMED LIVE** via
  `mitm/local_baseapp_capture.py` Attempt H — this part of the protocol is
  solved and requires no further design work.
- The only remaining blocker before BaseApp ever receives a packet is §13.

**Once BaseApp receives `baseAppLogin`** (framing CONFIRMED: variable-length
message, `u16` length prefix, sent exactly once with a 5s timeout, no
client-side retry — `06_trace/MERCURY_PACKET_MAP.md` §2a): the body content
is UNKNOWN, but `06_trace/LOCAL_SERVER_MINIMUM.md`'s "Minimum Information
Breakdown" point 3 gives a permissive design we adopt: **BaseApp accepts any
well-formed packet on this port without deep body validation** (no evidence
a LoginApp-issued secret is resubmitted here), reads/discards the body if it
cannot be interpreted, associates the connection with the `player_id`
already resolved from the UDP source address + a short-lived server-side
mapping created when LoginApp sent the LoginReply (INFERRED design: LoginApp
and BaseApp share the session store, so BaseApp can look up "who is
`(srcIP,srcPort)`" using the same store rather than needing the wire body to
carry it), then sends `createBasePlayer` with a minimal but well-formed
`Account` entity property blob per `05_entities/out/Account.def.xml`
(INFERRED FROM ENTITY DEFINITIONS, unchanged confidence from
`LOCAL_SERVER_MINIMUM.md`).

---

## 9. Client Changes

Ranked smallest-to-largest, each with its evidence-based justification:

1. **None (preferred, HTTP tier only)** — §5 already shows the auth
   boundary substitution requires zero client changes. This alone gets the
   client from Title Screen through `requestServerList`/`doLoginGame`,
   already CONFIRMED live (`DECISIONS.md` T17b).
2. **`server_list_ad.txt` content** — not a client binary change; it is a
   server-served text resource. Point it at our LoginApp's LAN address (see
   §11). No client modification.
3. **`entities/loginapp.pubkey` asset swap** (conditional on §7's Phase-3
   confirmation that this file exists and is swappable as a plain data
   asset, not baked into `.so`) — an **asset replacement**, not a code
   patch. This is the only "client change" candidate that touches anything
   under the APK/OBB, and it is a data file, not `.smali`/`.dex`/`.so`.
4. **`script.npk` (Python) edit** — only if empirical testing (§7) shows the
   existing Python login call does not already forward the MPay-retained
   session token into one of `LogOnParams`'s three strings. This is a
   Python source change inside `script.npk`, reusing the project's existing
   AES key/decrypt tooling (`MASTER_SPEC.md` "AES Key" section) — no
   `.smali`/`.dex`/`.so` change.
5. **Not planned, not needed**: any `.smali`/`.dex` patch (Gate 1-style
   `loginDone` short-circuit) — superseded by the HTTP-layer substitution in
   §5, which is strictly smaller.
6. **Explicitly ruled out**: any `libclient.so`/`libclient_arm64.so` native
   patch (RAND_bytes call site, BF_set_key, decrypt routine, or
   `checkScriptBaseAppAddr`). Nothing in this plan requires it; see §13 for
   why the Blowfish blocker is not solved by a native patch under this
   project's constraints.

---

## 10. Server Components

**A. Files that must change**
- `mitm/mitm_serve.py` (or a new module importing it, as
  `mitm/local_baseapp_capture.py` already does): extend the
  `/api/users/login/v2/sdk_token` handler to mint and persist a session id
  into the shared session store instead of (or alongside) the current
  static `guest_token_fake_ros_2026` value.
- `server_list_ad.txt` (served resource, not a code file): point at the
  chosen LoginApp LAN address (see §11).
- A new LoginApp module (extending `mitm/local_baseapp_capture.py`'s
  already-working `serve_loginapp_udp_responder`): add session-id lookup
  from the decrypted/plain `stringA/B/C` field before building the
  `LoginReplyRecord`.
- A new BaseApp module (extending the existing
  `serve_baseapp_udp_capture` capture-only stub into a real, minimal reply
  path once §13's blocker is cleared): add `createBasePlayer` push logic.
- A shared session-store module (new, small — sqlite or a JSON flat file)
  imported by both the HTTP tier and the LoginApp/BaseApp UDP tier.

**B. Files that should NOT change**
- Anything under `01_apk/`, `02_dex/` (no `.smali`/`.dex` patch is planned
  per §9).
- `03_lib/libclient*.so` (no native patch is planned or needed per §9/§13).
- `05_entities/out/*.def.xml` (read, not modified — they define what a
  well-formed `Account`/`Athlete` entity push must contain).
- `mitm/local_baseapp_capture.py` was **not** modified in this task per the
  task's own instruction (documentation/planning only); Phase 1–3
  implementation work should extend it as a new module rather than edit it
  in place, preserving it as a known-good reference capture harness.

**C. Exact Java/Smali boundary**: none required (§5, §9). If Gate-1-style
fallback is ever needed, the boundary is `Channel.smali`'s `loginDone(I)V`
(line 2044) and `setPropStr`/`setPropInt` (lines 3679/3692) — STRONGLY
SUPPORTED per Study §3, not currently planned.

**D. Exact Python boundary**: `script.npk`'s login-call site that populates
`LogOnParams` (candidate: whatever calls into the native binding wrapping
`0x9d8014`/`addToStream` — not yet located by symbol name, per
`LOGONPARAMS_SERIALIZATION.md` §7 point 3, "callers of addToStream ... not
traced yet"). Locating this call site is a concrete Phase 3/4 task (§14),
not assumed already known.

**E. Exact native boundary**: none touched. The plan's only asset-level
touch point is `entities/loginapp.pubkey` (a data file loaded by native
code, not native code itself) — conditional on Phase 3 confirming its
existence/location (§7).

**F. Exact server components required**:
1. HTTP(S) auth/patch tier — **already exists and works** (`mitm_serve.py`).
2. LoginApp UDP `:25000` — extend existing `serve_loginapp_udp_responder`.
3. BaseApp UDP (`:2501x`, currently capture-only) — extend into a real
   minimal responder.
4. Shared session store (new, small).
5. Optional: local RSA keypair + `loginapp.pubkey` asset generation tooling
   (Phase 3, conditional).

---

## 11. Packet/Data Flow

- **HTTP tier**: unchanged wire format from what already works
  (`06_notes/LOCAL_SESSION_CONTRACT.md`) — only the *value* of `user_id`/
  `sdk_token` changes from a static string to a per-login-attempt random
  session id.
- **`server_list_ad.txt`**: unchanged format (plain text/line, per
  `06_trace/LAN_FEASIBILITY.md` §2 row C); only its *content* changes to our
  LoginApp's real LAN-reachable address. Per this project's own prior
  finding (`06_trace/LAN_FEASIBILITY.md` "2026-09-14 (PLAY reached)"
  update): **do not** use `127.0.0.1` if the client runs inside an emulator
  whose NAT layer cannot route loopback traffic back to the host (observed
  concretely on LDPlayer: iptables OUTPUT DNAT rules match `127.0.0.1` but
  the packet never leaves `lo`) — use the emulator's real host-reachable
  gateway address, or on real hardware LAN, the host's actual LAN IP. This
  project's prior `dns_hosts.txt`/iptables DNAT experience
  (`06_trace/MERCURY_WIRE_CAPTURE.md`, `06_trace/FRIDA_BASEAPP_LOGIN_CAPTURE.md`
  cited) is the direct precedent for this redirection step — no new
  redirection mechanism needs to be invented, only pointed at the right
  address for whichever test device is in use.
- **`LogOnParams`**: unchanged wire format (CONFIRMED,
  `LOGONPARAMS_SERIALIZATION.md`); only which string(s) carry the session id
  is new information to confirm empirically.
- **`LoginReplyRecord`**: unchanged target format (20-byte address-shaped
  body inside the already-CONFIRMED Mercury REPLY_MESSAGE_ID framing); the
  session id resolved server-side determines which `player_id`'s BaseApp
  address (if per-player BaseApp routing is ever needed — for a first LAN
  prototype, there is only one BaseApp, so this reduces to "always the same
  address") is placed in the body.
- **`baseAppLogin`**: unchanged framing (CONFIRMED,
  `06_trace/MERCURY_PACKET_MAP.md` §2a); body content treated permissively
  per §8.

No protocol field is invented or renamed; every field used already exists
in the CONFIRMED wire formats above.

---

## 12. Local Test Environment

```
PC (single host, matches the task's Step 9 target):
  - HTTP(S) tier: mitm_serve.py on 80/443/8443 (already working)
  - LoginApp UDP :25000 (extended local_baseapp_capture.py-style module)
  - BaseApp UDP :2501x (extended, currently capture-only)
  - Session store: sqlite file or JSON, shared by all three

Android device (emulator, per this project's existing LDPlayer setup, or
real hardware on the same LAN):
  - Unmodified com.netease.chiji APK/OBB, network-redirected to the PC via
    the SAME mechanism already proven for this environment (on-device
    iptables OUTPUT DNAT for the emulator's NAT topology, per
    06_trace/FRIDA_BASEAPP_LOGIN_CAPTURE.md; or dns_hosts.txt-style DNS
    override for a device where /etc/hosts or a DNS redirect is writable)
  - server_list_ad.txt served by the PC's HTTP tier, pointing at the PC's
    LoginApp address as reachable from THIS device's specific network
    topology (not assumed to be the same IP across emulator vs. hardware —
    this project has already hit this exact class of bug once,
    06_trace/LAN_FEASIBILITY.md "127.0.0.1 cannot be DNAT'd off loopback")
```

Target for this plan: Android -> HTTP auth (session minted) -> server list
(LoginApp address resolved) -> LoginApp :25000 (session recognized) ->
LoginReply sent -> [§13 blocker] -> BaseApp -> Lobby.

---

## 13. Risks / Unknowns

| Risk/Unknown | Status | Evidence |
|---|---|---|
| Whether `entities/loginapp.pubkey` is a swappable data asset or baked into `.so` | UNKNOWN — architecturally assumed swappable by two prior docs, but the file was not located on disk in this pass's search | `06_trace/NATIVE_BOUNDARIES.md`, `06_trace/LAN_FEASIBILITY.md` §4.2 (INFERRED); Glob/find this pass: no `.pubkey` file located |
| Which of `LogOnParams`'s three strings the Python layer already uses for the MPay-retained token, if any | UNKNOWN | `06_trace/LOGONPARAMS_SERIALIZATION.md` §3/§7 |
| Exact sub-field byte layout of the 20-byte `LoginReplyRecord` (IPv4 vs IPv6, port position) | UNKNOWN, two candidate layouts untested beyond the already-tried ones | `06_trace/LOGIN_REPLY_RECORD.md`, `mitm/local_baseapp_capture.py` build_login_reply_record() comment |
| Whether BaseApp needs to validate any resubmitted secret in `baseAppLogin`'s body | UNKNOWN, tentatively "no" by absence of evidence | `06_trace/LOCAL_SERVER_MINIMUM.md` §"Minimum Information Breakdown" point 3, `06_trace/BASEAPP_LOGIN_SERIALIZATION.md` §5 |
| **The first-LoginReply Blowfish key** | **CONFIRMED UNRESOLVED — see below, this is the one blocker this plan cannot design around** | see this section's remainder |

### The Blowfish blocker, stated exactly (Step 8 of the task)

Reasoning through the task's own framing: since *we* control both LoginApp
and BaseApp for a private server, the natural question is whether we can
just implement "the correct, unmodified client-expected behavior" —
encrypt our `LoginReply` with the *same* key the client generated, for this
connection only, without needing to know it in advance.

That reframing does not remove the blocker, because of one CONFIRMED fact,
not an assumption: **the key is never transmitted to the server in any
form, at any protocol layer, before the first LoginReply is due.**
`06_notes/FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md` and
`06_trace/CHECK_SCRIPT_BASEAPP_ADDR_TRACE.md` each independently, and
exhaustively, trace every function between `ServerConnection` construction
and the `0x989600` decrypt call (`ServerConnection` ctor chain, the full
body of `logOnBegin`, `onLoginReply`'s pre-decrypt code, the RSA
`LogOnParams` plaintext structure, and the native `logOnBegin` body's
interaction with the JNI/session/script layers) and find **zero** data-flow
edges carrying the key, or any value derived from it, anywhere the server
could observe. This is not "we haven't looked hard enough" — it is reported
in both documents as a well-scoped absence after multiple full-function
disassembly passes.

Being the party that must **encrypt** (rather than decrypt) does not change
this: encryption under Blowfish-CBC requires the same key as decryption
(symmetric cipher). Our LoginApp, no matter how much of the rest of the
protocol we own, faces exactly the same problem the original NetEase
LoginApp would have faced: it must produce ciphertext the client will
successfully decrypt with a key **the client alone possesses and never
reveals**. There is no "observe it from the request" trick available,
because the request (`LogOnParams`) is a **separate cryptosystem** (RSA-OAEP
over stringA/B/C) with **no CONFIRMED data-flow edge into the Blowfish
filter object** (`06_notes/FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md` §7,
"RSA path and the Blowfish filter's key are structurally and temporally
independent").

**This blocker is therefore STILL LIVE for a private server we fully
control** — controlling both endpoints of the *protocol* does not help when
the missing value is generated and kept **only** in the client process's own
memory and never crosses the wire in either direction before the moment it
is needed. This is not a new problem to solve in this document; it is a
carry-forward from `06_trace/CHECK_SCRIPT_BASEAPP_ADDR_TRACE.md`'s own
conclusion, re-verified against the specific "what if we own the server"
framing the task asked for, and found to be unchanged by that framing.

**What this means for the plan**: Phases 1–4 (§14) are unaffected and fully
achievable — they only require the HTTP tier, session store, server list,
and correct Mercury *framing* up to and including sending *a* `LoginReply`.
Phase 5 (BaseApp reachability) is blocked exactly at "the client must
successfully decrypt our `LoginReply` body" — every `LoginReply` this
project's own dynamic tests have sent so far has been accepted at the
*framing* level (CONFIRMED, Attempt H) but produces a garbled BaseApp
address at the *content* level because the encryption key mismatches
(CONFIRMED live: `EncryptionFilter::decrypt` warning about a non-block-size
input in one variant, and simply garbled address bytes in the working
variant — both symptoms of encrypting/decoding under the wrong key).

**Do not treat this as resolved by any workaround listed above** (asset-key
swap, session-id-in-LogOnParams, permissive BaseApp) — none of those touch
the Blowfish filter at all; they solve *different*, real problems
(credential/session identification, BaseApp body validation) that are
independent of this one. If a genuine resolution is later found (e.g. a
still-undiscovered legitimate key-establishment channel — the "next
experiment" `06_trace/CHECK_SCRIPT_BASEAPP_ADDR_TRACE.md` itself proposes is
to look for MPay/UniSDK HTTPS-layer key material this project has not yet
correlated with the Blowfish key), it should be documented as its own
investigation, not folded into this plan retroactively.

---

## 14. Implementation Order

```
PHASE 1: Private local auth only.
  - Extend mitm_serve.py's /api/users/login/v2/sdk_token handler to mint a
    random session id (UUID4) and store it (session_id -> player_id) in a
    new shared session-store module.
  - No client changes. Verify via existing DECISIONS.md-style live test
    that the client still reaches PLAY/title screen with a per-run unique
    sdk_token.

PHASE 2: Connect authenticated client to local server list.
  - Point server_list_ad.txt at the LoginApp host:port reachable from the
    specific test device's network topology (emulator NAT gateway or real
    LAN IP — confirm per-device, do not assume 127.0.0.1 works, per
    06_trace/LAN_FEASIBILITY.md's own prior finding).
  - Verify requestServerList/doLoginGame proceed (already observed in prior
    sessions per DECISIONS.md T17b) with the session-bearing sdk_token now
    in play.

PHASE 3: Reach LoginApp :25000.
  - Confirm/locate entities/loginapp.pubkey's existence and format (closes
    the §13 table's first UNKNOWN row) — if present and swappable, generate
    our own RSA-2048 keypair and replace the asset; if not swappable or not
    found, fall back to the permissive ignore-ciphertext mode already
    validated architecturally by 06_trace/LOCAL_SERVER_MINIMUM.md.
  - Extend local_baseapp_capture.py-style LoginApp module to actually
    decrypt (or, in fallback mode, skip) stringA/B/C and locate which one
    (if any) already carries the MPay-retained sdk_token/session id.

PHASE 4: Establish local session identity.
  - LoginApp looks up the extracted session id against the shared session
    store from Phase 1, resolves a player_id, and logs the association.
  - No BaseApp traffic yet — this phase's success criterion is purely
    "LoginApp can name which player just connected."

PHASE 5: Reach BaseApp.
  - Send a LoginReply using the already-CONFIRMED-live framing (Attempt H)
    with the resolved BaseApp address.
  - BLOCKED by §13 until a legitimate Blowfish-key-establishment path is
    found or the task's own future scope explicitly revisits this. Do not
    attempt to work around it by patching decrypt(), disabling encryption
    checks, or faking a decrypted address — this plan's constraints (and
    the task's) forbid it.

PHASE 6: Create Account/Lobby state.
  - Once Phase 5's blocker clears: BaseApp accepts baseAppLogin
    permissively (per §8), creates an Account entity from
    05_entities/out/Account.def.xml, pushes createBasePlayer, and later an
    Athlete entity for Lobby.

PHASE 7: Only after Lobby works, investigate Avatar/match flow.
  - Explicitly out of scope for this plan; noted only for completeness per
    the task's own instruction.
```

---

## 15. Explicit Non-Goals

- Not attempting to contact, probe, or interoperate with the original
  NetEase production LoginApp/BaseApp/CellApp infrastructure, or with ROS
  Legacy's own private-server infrastructure.
- Not brute-forcing, guessing, or otherwise attempting to recover the
  original `entities/loginapp.pubkey` private key or any client's
  process-local `RAND_bytes(4)` Blowfish key.
- Not patching `RAND_bytes`, `BF_set_key`, `BF_KEY`, `EncryptionFilter`, or
  any decrypt/encrypt call site inside `libclient.so`/`libclient_arm64.so`.
- Not modifying the client to fake a successful BaseApp/Lobby state (no
  stubbed `createBasePlayer` fired client-side, no skipped
  `onLoginReply`/`checkScriptBaseAppAddr` validation).
- Not reusing ROS Legacy's compiled `libmsaoaidsec_arm64.so` binary or its
  literal `RosAuth`/smali patch — only the general Gate 1 *pattern* is
  referenced, and even that pattern is not adopted in this plan's chosen
  design (§5 uses the HTTP-layer boundary instead, which is smaller).
- Not attempting Phase 7 (Battle/CellApp) in this plan.
- Not distributing or referencing `ROS_RE_LEGACY/ros_auth.txt`'s value in
  any form (consistent with the prior Study's own handling of that file).

---

## Phase 1 Implementation

Implements §14 PHASE 1 only. Labels: CONFIRMED / STRONGLY SUPPORTED /
INFERRED / UNKNOWN, per this project's convention.

### Code changes (CONFIRMED — directly made and compiled/run this pass)

- **New file `mitm/session_store.py`**: a minimal, dependency-free,
  JSON-file-backed session store (`mitm/session_store.json`, written
  atomically via a `.tmp` + `os.replace` swap). No sqlite dependency exists
  anywhere else in this repo (checked: zero `import sqlite3` hits under
  `mitm/` or elsewhere), so per the task's own instruction this uses a flat
  JSON file rather than adding a new dependency.
  - `create_session(player_id, source='guest_login', ttl_seconds=6h)` —
    mints `session_id = 'sess_' + uuid.uuid4().hex` (CSPRNG via
    `os.urandom`, **not** derived from any password/credential) and
    persists `{session_id, player_id, created_at, expires_at, source}`.
  - `get_session(session_id)`, `validate_session(session_id)` (checks
    existence + not-expired), `expire_session(session_id)` (idempotent,
    zeroes `expires_at`), `all_sessions()` (debug/test helper only).
  - `_short(session_id)` returns an 8-char prefix for safe logging — used
    everywhere the server logs a session id, so the full value never lands
    in `captures/SERVE_B.txt` (a git-tracked file — confirmed via
    `git ls-files`/`git check-ignore`, both `mitm/captures/*.txt` and
    `scratch/*.log` are tracked, so this matters).
- **Modified `mitm/mitm_serve.py`**:
  - Added `import session_store`.
  - `/api/users/login/guest` handler: now calls
    `session_store.create_session(player_id, source='guest_login')` per
    request and returns that session's id as `login_token`/`token` inside
    the `user` object, replacing the previous hardcoded
    `"guest_token_fake_ros_2026"`. JSON field set/types are otherwise
    byte-for-byte identical to the prior response (same keys, same
    `minor_status=102`/`age_status=1` adult-verified values).
  - `/api/users/login/v2/sdk_token` handler: same change, additionally
    setting the top-level `sdk_token` field (the field
    `06_notes/LOCAL_SESSION_CONTRACT.md` confirms is parsed by
    `com.netease.mpay.oversea.h.a.a` via `optString("sdk_token")` at Dalvik
    `0x3d34d8`) to the new session id instead of the old static string.
    `user_id` is left as the existing fixed guest player id
    (`guest_11178811c6a412d9`) — only the token value is now per-session,
    per the task's Step 1 instruction ("never derive the session id from a
    password"; the player identity and the session identity are
    deliberately kept as separate concepts here).
  - No other handler, port, or response shape was touched.

### Session generation method (CONFIRMED)

`uuid.uuid4()` (Python stdlib, CSPRNG-backed), hex-encoded, prefixed
`sess_` — chosen over `secrets.token_hex`/`token_urlsafe` because the field
it rides in (`sdk_token`/`login_token`/`token`) is already confirmed
(`LOCAL_SESSION_CONTRACT.md`) to be parsed as an **opaque string**, not a
canonical-form UUID or a byte array with a fixed expected length — any
sufficiently-random printable string satisfies the client's `optString()`
parse. A new value is minted on every successful login request; nothing is
cached or reused across requests.

### Session storage design (CONFIRMED)

Flat JSON file (`mitm/session_store.json`), one object keyed by
`session_id`, each value `{session_id, player_id, created_at, expires_at,
source}`. `threading.RLock`-guarded read-modify-write (load whole file,
mutate, atomic replace) — adequate for this single-process, low-concurrency
local test server; **not** designed for concurrent-writer safety beyond
that, which is acceptable per the task's own "throwaway/test infra, not
production-grade" framing. The file itself is **not** committed to git
(it is runtime-generated local state, analogous to `mitm/mitm_stdout*.txt`
already present but untouched by this task).

### JSON response field changes (CONFIRMED)

Only value changes, zero schema/field changes, in both
`/api/users/login/guest` and `/api/users/login/v2/sdk_token`:
`login_token`, `token` (both handlers) and `sdk_token` (sdk_token handler
only) now carry a fresh `sess_<uuid4hex>` string per request instead of the
static `"guest_token_fake_ros_2026"`. Verified via direct HTTP round-trip
against the running server this pass (see
`mitm/captures/PHASE1_SESSION_TEST.txt`, tokens redacted to 8-char
prefixes) — Run A and Run B against `/api/users/login/v2/sdk_token`
produced distinct `sdk_token` values while every other field matched byte
-for-byte, and the corresponding `session_store.json` held two (later
three, including the guest-login run) distinct records with distinct
`session_id`/`created_at`/`expires_at`.

### Client storage path (INFERRED, not independently re-traced this pass)

Cited, not re-derived: `06_notes/LOGIN_FLOW_TRACE.md` "has_minor Source"
finding that the NetEase MPay SDK persists `user_id`/`token` into its own
SharedPreferences file
(`com.netease.mpay.202cb962ac59075b964b07152d234b70.xml`). This pass did
not re-verify that finding against the new per-session values (no
emulator/device was reachable this session — see below), so it remains at
its prior INFERRED confidence, not upgraded to CONFIRMED.

### Whether sdk_token reaches LogOnParams (honest negative/unresolved result)

**UNRESOLVED this pass — could not be tested, static or dynamic, beyond
what was already known before this task.** Specifically:

- **Dynamic/runtime verification (Step 2's primary method) could not be
  performed**: this session has no reachable Android device or emulator.
  `adb` is not installed/on `PATH` in this execution environment and
  `adb devices` fails outright (`adb: command not found`). The task's Step
  0–3 runtime plan (start server, confirm iptables DNAT, launch the app,
  capture UDP `LogOnParams` traffic, correlate against the minted session,
  optionally `/proc/<pid>/mem` read of the pre-RSA plaintext buffer) is
  **entirely** contingent on that device and was not attempted with a
  fabricated result. This is reported honestly per the task's own
  instruction rather than inventing a pass.
- **Static analysis this pass did not find a new answer either.** The
  existing, already-thorough disassembly in
  `06_trace/LOGONPARAMS_SERIALIZATION.md` §3/§7 point 1 explicitly leaves
  the semantic identity of `LogOnParams`'s three string fields (`stringA`
  at `+0x10`, `stringB` at `+0x28`, `stringC` at `+0x40`) as **UNKNOWN,
  needs dynamic instrumentation** — candidates only by plausibility
  (username / password / third credential), not by any traced data-flow
  edge from the Python/HTTP layer into `addToStream`'s three string
  arguments. `06_trace/ROS_LOGIN_PLAY_TRACE.md` §8.1 independently confirms
  the call shape `ServerConnection.logOnBegin(host, port, username,
  password)` from `ui.UILogin.doLoginGame()` in `res/script.npk`, but does
  **not** show what values `doLoginGame()` passes for `username`/`password`
  — i.e., whether the MPay-retained `sdk_token` (now our session id) is one
  of them is exactly the open question in
  `06_trace/LOGONPARAMS_SERIALIZATION.md` §7 point 3 ("callers of
  `addToStream` ... not traced yet"), and this pass did not close it (would
  require either decompiling `script.npk`'s Python bytecode for
  `doLoginGame()`'s body, or the live memory-read method — both out of this
  pass's reach: the former was not attempted as it falls outside this
  task's Step 2 static-trace instruction to reuse prior docs rather than
  re-derive; the latter requires the unavailable device).
- **Server-side differential test performed instead (does not answer the
  client-forwarding question, but satisfies the task's fallback
  instruction to still report a useful result)**: two full HTTP round trips
  against the live `mitm_serve.py` process, `session_store.create_session`
  called for each, confirmed `session_id_A != session_id_B` at the server
  boundary (see `mitm/captures/PHASE1_SESSION_TEST.txt`). This proves the
  **server half** of Phase 1 works — unique session per login, correctly
  persisted, correctly returned in the schema-unchanged HTTP response — but
  says nothing about whether the client subsequently carries that value
  into `LogOnParams`.

**LOGONPARAMS_FIELD: UNKNOWN** — unchanged from before this task; not
newly determined.

### LoginApp preparation (Step 4, documentation only)

Because whether/where the session token reaches `LogOnParams` is
UNRESOLVED (not merely "reaches an unusable field" — genuinely untested),
this section documents both branches rather than picking one:

- **If a future dynamic-instrumentation pass (with a reachable emulator)
  confirms the session token lands in `stringA`/`B`/`C`**: our own LoginApp
  would need to (1) receive the 273-byte Mercury bundle on `:25000`
  (framing already CONFIRMED live per `mitm/local_baseapp_capture.py`
  Attempt H), (2) RSA-OAEP-2048-decrypt the 256-byte ciphertext block
  covering `{flags, stringA, stringB, stringC}` using the private half of
  whatever key corresponds to `entities/loginapp.pubkey`, (3) extract the
  session-id string from whichever field is confirmed to carry it, (4)
  call `session_store.get_session(...)`/`validate_session(...)` (both
  already implemented this pass and directly reusable by a LoginApp
  module) to resolve a `player_id`. **`entities/loginapp.pubkey` was
  searched for this pass** (`Glob **/loginapp.pubkey` across the whole
  repo) **and was not found** — zero matches. This upgrades
  `06_trace/LAN_FEASIBILITY.md` §4.2's prior "UNKNOWN pending a concrete
  file-level confirmation" to a **confirmed-negative search result on this
  repo's current extracted contents**: the asset is not present at that
  path in whatever was extracted so far (it may still exist unextracted
  inside `01_apk/`/`04_obb/`, which `.gitignore` excludes from the repo and
  which this pass did not re-extract). Locating it (or confirming it is
  genuinely absent from the OBB/APK) remains a concrete Phase 3
  prerequisite, not newly resolved here.
- **If the session token does NOT reach `LogOnParams` at all** (a real
  possibility per the honest UNRESOLVED status above — `doLoginGame()`
  could pass fixed/empty `username`/`password` values unrelated to the
  MPay `sdk_token`): stated plainly, not softened — in that case Option B
  from §7 above would require the fallback in §9 point 4, a `script.npk`
  (Python) edit to `ui.UILogin.doLoginGame()` to explicitly forward the
  retained session token as one of the three `LogOnParams` strings. This
  is a Python source change, not `.smali`/`.dex`/`.so`, consistent with
  §9's ranking, and remains exactly the fallback §7/§9 already
  anticipated — this pass did not newly discover a need for it, but also
  did not rule it out.

### Unresolved fields / honest gaps from this pass

- `SESSION_REACHES_LOGONPARAMS`: **UNKNOWN** (untested this pass; device
  unavailable).
- `entities/loginapp.pubkey` existence: **UNKNOWN → confirmed absent at
  that literal path in the currently-extracted, git-tracked repo
  contents**; still UNKNOWN whether it exists unextracted inside
  `01_apk/`/`04_obb/`.
- Client-side SharedPreferences retention of the new per-session token:
  **INFERRED only**, not re-verified live this pass.
- `doLoginGame()`'s exact `username`/`password` argument values: **UNKNOWN**,
  same as before this task; would need `script.npk` decompilation or a live
  Frida hook, neither performed this pass.
- The first-LoginReply Blowfish key (§13): **untouched, out of scope for
  this task, unchanged CONFIRMED-UNRESOLVED status.**

### Success criteria scorecard (§ task Step 6, reported honestly)

| Criterion | Result |
|---|---|
| Every login creates a unique local session | **PASS** — CONFIRMED via direct HTTP test, `session_id_A != session_id_B` |
| Session stored server-side | **PASS** — CONFIRMED, `mitm/session_store.json` persists all three test-run records |
| Client accepts the HTTP response | **NOT INDEPENDENTLY VERIFIED THIS PASS** — no device available; INFERRED likely from unchanged JSON schema (same keys/types as the already-PASS-tested `LOCAL_SESSION_CONTRACT.md` contract, only values changed) |
| Client continues through the existing login flow | **NOT VERIFIED THIS PASS** — no device available |
| Session/token propagation traced | **PARTIAL** — server-side propagation (HTTP response -> session store) CONFIRMED; client-side propagation (response -> `LogOnParams`) UNKNOWN, untested |
| Two independent runs produce distinct session identities | **PASS** — CONFIRMED |
| No original ROS server contacted | **PASS** — only localhost `mitm_serve.py` was contacted this pass |
| No Blowfish workaround introduced | **PASS** — `mitm/local_baseapp_capture.py` and the Blowfish-key problem were not touched |
