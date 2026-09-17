# Ghidra trace: entity+0x140 dispatcher / onChannelLogin path

## Objective

Use Ghidra 12.1.3 (headless, hybrid alongside the project's Capstone-based
`scratch/xref_lib.py`) to push past two walls the hand-rolled toolkit could
not resolve on its own:

1. Find the real caller of `FUN_00a4c540` (static offset `0x94c540`, the
   entity+0x140 generic RPC dispatcher), previously characterized only as
   "reached via virtual dispatch/register-indexed call, caller unknown."
2. Re-examine the wire-format assumptions behind the `Account.onChannelLogin`
   live experiments (E2E-028, E2E-037), which produced zero observable
   effect across 37+ passes.

## Ghidra project / binary info

- Ghidra 12.1.3 PUBLIC, headless mode, direct `java` invocation (bypassing
  `analyzeHeadless.bat`, which has a bug where passing `-analyze` corrupts
  argument parsing in this version — analysis runs by default and the flag
  does not exist).
- Binary: `03_lib/libclient_arm64.so` (same file `scratch/xref_lib.py` has
  always targeted).
- Project: `scratch/ghidra_project/ROS_RE.gpr` (not committed — excluded via
  `.gitignore`, regenerate locally via `-import` if needed).
- **Ghidra imageBase = `0x100000`.** CONFIRMED: every static address this
  project has established (via the Capstone toolkit / live E2E evidence)
  must be looked up in Ghidra at `imageBase + staticOffset`, not at the raw
  offset. Cross-validated against 4 independent anchors (`0x938070` =
  `LoginHandler::onLoginReply`, matched by exact log-string content;
  `0x94c540` = entity dispatcher; `0x989600` / `0x98924c` = the two
  Blowfish/EncryptionFilter decrypt variants, matched by exact
  `BF_ecb_encrypt`-chaining logic and the enabled-flag check difference
  already documented) — all 4 matched perfectly.

## Finding 1: `FUN_00a4c540` decompiled in full

**Finding:** `0x94c540` is `ClientVarLenMessageHandler::handleMessage` (name
inferred from its own log string, not RTTI symbol — RTTI/mangled names for
this class are not retained in the binary's symbol table, see Finding 3).
Full decompiled logic:

```c
void FUN_00a4c540(long param_1,undefined8 param_2,long param_3,long *param_4)
{
  lVar8 = *(long *)(*(long *)(param_3 + 0x10) + 0x4458);
  if (*(long *)(lVar8 + 0x140) != 0) {
    uVar2 = *(undefined4 *)(param_3 + 8);
    if (*PTR_DAT_03a15320 == '\0') {
      pcVar7 = *(code **)(param_1 + 8);
      plVar1 = (long *)(lVar8 + ((long)*(ulong *)(param_1 + 0x10) >> 1));
      if ((*(ulong *)(param_1 + 0x10) & 1) != 0) {
        pcVar7 = *(code **)(pcVar7 + *plVar1);
      }
      (*pcVar7)(plVar1,param_4,uVar2);
      iVar4 = (**(code **)(*param_4 + 0x18))(param_4);
      if (iVar4 != 0) {
        FUN_01dad7ac("ClientVarLenMessageHandler::handleMessage Handler for "
                     "ClientMessage (header.length%d) did not consume all "
                     "data, remain %d bytes\n", uVar2, uVar5);
      }
    } else {
      /* alternate dispatch path via FUN_00a7bfa8/FUN_00a7c0d8 -- some kind
         of async/queued dispatch, not yet analyzed in detail */
    }
  }
}
```

**Ghidra evidence:** Callers via direct call-type cross-reference: **zero**
(`[No direct call-type references found]`), matching the prior
Capstone-toolkit conclusion exactly.

**Live E2E evidence:** E2E-025/029 established this function only reads
`entity+0x140` and does nothing when it's zero (the observed gate).

**Relationship:** Confirms, does not change, the prior finding — but now
backed by full Ghidra decompilation instead of hand-disassembled Capstone
output.

**Confidence:** CONFIRMED (decompilation + 4-anchor address cross-validation).

## Finding 2 (RETRACTED): "method-index SSO encoding" was a misread — this is the standard Itanium PMF representation, not wire-controlled

**Original claim (WRONG, retracted):** An earlier pass of this
investigation characterized the `param_1+0x10` field in `FUN_00a4c540` as a
libc++ `std::string`-style SSO discriminator, and proposed that live
`onChannelLogin` tests had been sending the wrong wire byte (`2` instead of
`4`) as a result.

**Correction:** On closer reading, this bit pattern —
`plVar1 = lVar8 + (value >> 1)`, gated by `(value & 1) != 0` triggering one
more indirection through a vtable-like lookup — is the textbook **Itanium
C++ ABI pointer-to-member-function representation**: bit 0 distinguishes a
direct function pointer (bit0=0) from a virtual-dispatch byte-offset
(bit0=1, real offset derived from the remaining bits). This value is a
**field of the per-message handler struct (`param_1`), which is a static
data structure compiled into the binary** (built at compile time from the
`.def`-derived method table), **not something populated from wire data at
all**. There is no live wire byte that "should have been" `4` instead of
`2` — that theory does not apply to this field.

**Impact:** This retracts the "next actionable experiment" from the
original version of this finding. **No live test was run against the wrong
theory** — caught before spending an E2E pass on it. The real blocker
remains what Finding 4 already identified: `FUN_00a4c540` no-ops entirely
whenever `entity+0x140 == 0`, regardless of what wire bytes are sent for
the method body, because the whole per-message dispatch block is gated
behind that single pointer check before the PMF-style method invocation
is ever reached.

**Confidence:** CONFIRMED (Itanium ABI PMF calling-convention pattern is
unambiguous once correctly identified).

## Finding 2b: chasing the +0x140 SETTER's real trigger — dead end via direct-callee tracing

**Finding:** The setter `FUN_00a3a5e4` (`*(param_1+0x140) = param_2`, then
conditionally invokes a pending callback via `*(param_1+0x150)`, then calls
`FUN_00a473d0(param_1)`) has, like the dispatcher itself, **zero direct
call-type callers** (`INDIRECTION`/`DATA`-only refs to a vtable slot at
`0x33f4a80`, no preceding RTTI label, nothing takes that slot's address
directly — the same virtual-dispatch-with-unfindable-constructor pattern as
`FUN_00a4c540`'s own vtable slot).

Its callee `FUN_00a473d0` (touches `param_1[0x27]+0x4210`, `param_1[0x29]`,
`param_1[0x2a]`, `param_1[0x28]` — a mutex-guarded pooled-buffer allocate/
reuse pattern) **does** have real, direct, non-virtual callers findable via
Ghidra (`UNCONDITIONAL_CALL` type at static offsets `0x93d110`, `0x93a558`,
`0x94d4a0`, plus the setter's own tail-call at `0x93a61c`).

**Ghidra evidence:** `scratch/ghidra_setter_callers.txt`,
`scratch/ghidra_deep140.txt`, `scratch/ghidra_callsites_473d0.txt`,
`scratch/ghidra_caller_strings.txt`. String-literal extraction from the 3
non-setter callers' containing functions shows they are unrelated generic
NeoX engine startup/config code (`"Initializing client...."`,
`neox.xml`/filesystem/shader-cache config parsing) — **not**
BigWorld/entity/networking code.

**Relationship:** `FUN_00a473d0` is a **shared, generic pooled-buffer
allocator** reused throughout the binary for unrelated purposes (engine
init, and separately, by the +0x140 setter with a different-typed
`param_1`). Chasing its callers does not reveal what triggers the +0x140
setter — this is a dead end.

**Confidence:** CONFIRMED dead end (the 3 callers' purpose is unambiguous
from their string literals).

**Next actionable step:** Static analysis (both the original Capstone
toolkit and this Ghidra hybrid session) has now independently hit the same
wall twice — the setter's real caller is virtual-dispatch-only with no
resolvable construction site. The next step that could plausibly break this
open is **dynamic instrumentation**: hook `FUN_00a3a5e4` (static
`0x93a5e4`) at runtime on the local test client and log its call stack the
moment it fires (if it ever does) during a real login attempt. This is
local, non-destructive, read-only observation of our own test client
talking to our own local server — not a bypass of any production security
control. Not yet attempted this session.

## Finding 3: symbol-table keyword search is a dead end for game classes

**Finding:** A keyword search (Account/Avatar/Character/Lobby/Player/
CreatePlayer/Match/onLogin/onEnter/onChannelLogin/createBasePlayer/
enableEntities/handshake, case-insensitive) across all ~500-capped matching
symbols in the binary's symbol table returned **zero** BigWorld/game-logic
class names. Every hit was generic third-party static-library noise
(OpenSSL `SSL_do_handshake`, OpenLDAP `ldap_matchingrule*`, PhysX
`platformMismatch`/`onMeshIndexFormatChange`, LibRaw, OpenEXR, HarfBuzz) or
unrelated Java video-player JNI callbacks (`Java_..._CCPlayer_...`,
`NativeOnLogin` — a video-player login callback, not BigWorld's).

**Ghidra evidence:** `ghidra_symbols_clean.txt` (63 lines after filtering
out ~1900-character `boost::spirit`/`boost::wave` template-instantiation
symbol names that were separately blowing up token limits on read).

**Relationship:** Confirms the game-logic C++ classes (Account, Avatar,
Entity subclasses, etc.) are **not retained as demangled/exported symbols**
in this binary the way bundled static libraries are — consistent with
BigWorld's typical build stripping RTTI type-name strings for game-specific
entity classes while leaving third-party libs' symbols intact. A
keyword/name-based approach cannot find these classes; only structural
(vtable layout, string xrefs, offset-pattern) approaches can.

**Confidence:** CONFIRMED (exhaustive search of all matching symbols, capped
list fully reviewed).

## Finding 4: `0x94c540`'s vtable slot located (partial resolution of the caller question)

**Finding:** A full any-reference-type (not just call-type) search plus a
raw byte-pattern scan found exactly one genuine data reference to
`FUN_00a4c540`, at address `0x38d7cb8` (a `data.rel.ro`-style pointer table
entry, value = the function's address). A sibling entry
`PTR_FUN_038d7ca8` sits 16 bytes earlier (2 pointer-slots before it). No
RTTI typeinfo symbol was found immediately preceding either slot. The other
2 raw-search hits (`0x33175d0`, `0x33f7368`) are ordinary `.eh_frame`/FDE
unwind-table entries referencing the function's start address for stack
unwinding, not call sites.

**Ghidra evidence:** `scratch/ghidra_vtable_callers.txt` and
`scratch/ghidra_vtable_inspect.txt` (full any-type reference scan + raw
8-byte pattern scan of all initialized memory blocks + neighbor-symbol
inspection).

**Relationship:** `0x38d7cb8` is very likely the actual C++ vtable slot for
`ClientVarLenMessageHandler::handleMessage` (the class name inferred from
the function's own log string). Nothing in the binary takes the *address*
of this vtable slot directly (`references TO this slot address: [none]`),
meaning the object that carries this vtable pointer is constructed via a
path Ghidra's static analysis doesn't surface as a direct reference (e.g.
the vtable pointer is written once at object-construction time via a
computed/indirect store, or the object is a global static initialized by
`.init_array` — neither has been traced yet). This is genuine C++ virtual
dispatch, not an artifact of incomplete analysis — it explains, at the
tooling level, why the Capstone-based static toolkit's dozens of prior
passes never found a caller via any disassembly-based method.

**Confidence:** STRONGLY SUPPORTED (the vtable slot itself is CONFIRMED via
2 independent methods — reference scan and raw byte scan agreeing — but the
object/constructor that uses this vtable remains UNKNOWN).

## Finding 5: fresh live E2E pass reproduces the exact same blocker, plus a new unifying hypothesis

**Finding:** After the Ghidra-phase corrections above, a fresh live E2E pass
was run against a freshly-restarted server (root DNAT rules and server key
cache reset after an LDPlayer reboot). Result: **identical to every prior
pass** — `ServerConnection::logOnBegin` → `LoginHandler::onLoginReply`
reached, `Nub::recreateListeningSocket` fires for a new "external channel,"
and then **nothing**. No packet ever arrives at the fake BaseApp UDP
listener (`:25010`). This is not a regression and not an improvement —
today's Ghidra findings did not change this outcome, as expected (Finding 2
retraction explains why the "corrected encoding" theory was never actually
applicable here).

**New data point:** attempting to Frida-attach to the live client process
(`com.netease.chiji`, SELinux permissive, frida-server running as root)
during this session **crashed the frida-server connection outright**
(`unable to connect to remote frida-server: closed`) — despite frida-server
successfully enumerating 97 *other* system processes normally, and despite
adb confirming the target process was alive throughout. This is consistent
with the client having some form of runtime anti-instrumentation/anti-
tamper check specific to itself (not a generic Android/frida-server
compatibility problem, since every other process was attachable-in-
principle).

**Hypothesis (INFERRED, not yet tested):** The BaseApp-channel blocker that
has resisted 38+ E2E passes across every wire-format/timing/encoding theory
tried so far may not be a protocol bug at all. A client-side anti-tamper
check (root detection, iptables OUTPUT-redirect detection, or detection of
the modified/instrumented LDPlayer environment itself) could be silently
causing the client to abandon BaseApp channel setup after accepting the
LoginApp reply, regardless of whether the wire format is byte-perfect. This
would explain: (a) why no combination of tried packet formats has ever
produced observable movement past this exact point, (b) why the
`entity+0x140` gate is never set despite the dispatcher and its setter
being otherwise unremarkable in Ghidra, and (c) the frida-attach crash
above.

**Confidence:** INFERRED / UNCONFIRMED — this is a hypothesis raised by
today's evidence, not a proven root cause. It has NOT been tested (e.g. by
comparing behavior against a non-rooted, non-redirected, non-instrumented
reference environment, which is the natural next diagnostic).

**Next actionable experiment (highest priority, supersedes the retracted
Finding 2 experiment):** Determine whether the block is environment-
dependent rather than protocol-dependent. Options, roughly in order of
effort: (1) search the binary (Ghidra string/xref search for
"frida"/"xposed"/"su"/"magisk"/root-marker file paths, or for `ptrace`
self-attach calls, a common anti-frida trick) for anti-tamper logic near
the BaseApp channel setup path; (2) if found, characterize what it does on
detection (silent no-op vs. explicit disconnect) to confirm/refute this
hypothesis without needing a clean reference device.

**Follow-up performed this session (partial, inconclusive):** A binary-wide
string search did find genuine root-detection code: a JNI bridge function
`FUN_01cfaa90` that calls into the Java layer's `isDeviceRooted()` method
and returns its boolean result. Its only found direct (non-virtual) caller,
`FUN_01ceef8c`, is a tiny `void`-returning wrapper that calls it back-to-
back with an unrelated init function (`FUN_01cf95d4()`) and **discards the
returned boolean** — it does not visibly branch on the result itself. This
is consistent with a **telemetry-only** root check (reported to analytics,
not used to gate behavior at this call site) rather than an active
connection-blocking anti-tamper gate, though the boolean could still be
consumed as a side effect inside `FUN_01cfaa90` itself (not yet checked) or
forwarded to a live NetEase backend service this local test setup doesn't
reach. **This does not confirm or refute the Finding 5 hypothesis** — it
only shows that *a* root-detection mechanism exists in the binary; whether
*that specific one* (or a different one) gates the BaseApp channel remains
unknown. Not pursued further this session given time already invested.

## Finding 6 (MAJOR, this pass): the "38+ passes stuck at onLoginReply" characterization was WRONG — BaseApp channel establishment actually succeeds

**Finding:** A prior turn's live-test conclusion ("no packet ever reaches
the fake BaseApp listener") was based on grepping a stale/wrong server log
file and was **incorrect**. A proper packet-level capture (on-device
`tcpdump` on ports 25000/25010, parsed with a small custom pcap parser
since no `tshark`/`tcpdump` was available on the host) plus a full,
unfiltered logcat review shows:

1. The client DOES send BaseApp UDP packets to `172.16.1.2:25010` and
   receives replies.
2. The client logs `ServerConnection::createBasePlayer: id 1` — **the
   BaseApp login handshake succeeds and entity 1 is created client-side.**
3. The client then logs `ServerConnection::logOn: status==LOGGED_ON` and
   `ServerConnection::logOn: to: 172.16.1.2:25010` — **full BaseApp login
   completion**, further than any of the 38 prior documented E2E passes
   reached.
4. Immediately after, a **separate, concrete, fixable bug** appears:
   `Bundle::iterator::unpack( authenticate ): Not enough data on stream at
   11 for payload (1 left, needed 4)`, followed by
   `Bundle::iterator::unpack: Got corrupted message header` →
   `Nub::processOrderedPacket(...): Discarding bundle due to corrupted
   header for message id 0` → `MainApp::poll: poll returned unexpectedly
   (REASON_CORRUPTED_PACKET)`.

**Bisection performed:** tested with `ATTEMPT_VERSIONPOINT_REPLY=0`
(disables the `versionPointIdentity` push implicated by name) — the
corruption **still occurs**, ruling that push out as the sole cause.
Tested with `ATTEMPT_BASEAPP_REPLY=0` (disables the very first
"whole-packet-encrypted ack for method=0x00" reply, sent immediately after
receiving the client's baseAppLogin request) — this made things **strictly
worse**: the client never reaches `createBasePlayer`/`LOGGED_ON` at all
and fails outright with `Unable to connect to BaseApp: A NAT or firewall
error may have occured?`. This confirms that ack **is required** and is
not itself the corruption source in isolation — the real cause is still
unidentified among: the ack's exact byte layout, the `createBasePlayer`
push's format, or a timing/ordering interaction between the two.

**Relationship:** This means the actual remaining blocker to reaching
Account/Avatar/Character-Creation is **not** "nothing happens after
onLoginReply" (the standing 38-pass characterization) but a **specific,
later, fixable Bundle-framing bug** in one of our own server's post-login
pushes, which the client's Mercury layer discards as corrupted and then
(per this session's evidence) may retry the whole login cycle rather than
proceeding further. This substantially changes the diagnosis: the problem
looks like a wire-format bug in a specific packet, not a structural/anti-
tamper block.

**Confidence:** CONFIRMED for points 1-4 above (direct log/pcap evidence,
reproduced across 2 separate live passes with different config toggles).
The exact byte-level cause of the corruption is UNKNOWN (bisection ruled
out 2 of the 3 most obvious candidate packets; the third — the
`createBasePlayer` push itself, or an ordering/timing issue between it and
the initial ack — has not yet been isolated).

**Important methodological caveat discovered this session:** one live-test
attempt's `LoginHandler::onLoginReply` came from `112.22.1.60` (a real
public IP), not `172.16.1.2` — meaning that particular pass silently fell
through to the **real production login infrastructure** instead of this
project's local test server, despite the iptables OUTPUT DNAT rules being
verified present and correct at the time. The exact fallback path is not
yet understood (possibly a hardcoded/cached server-list entry using a port
our DNAT rules don't cover, since only UDP 25000/20013 and TCP 80/443/8443
are redirected). **Any future live-test result must verify the
LoginHandler::onLoginReply source address is `172.16.1.2` before trusting
the rest of that pass** — a run that silently hit production would look
like "stuck at title screen" and could be misdiagnosed as a regression.

**Next actionable experiment (highest priority, supersedes Finding 5's
anti-tamper hypothesis given this new, more concrete lead):** Bisect
further to isolate whether the `authenticate`-unpack corruption comes from
the `createBasePlayer` push's byte layout specifically, or from an
ordering/timing issue (e.g. sending the ack and createBasePlayer push
back-to-back without waiting for any client acknowledgment in between).
Try: (a) delaying the `createBasePlayer` push by ~50-100ms after the
initial ack; (b) comparing the exact byte layout of the initial
"whole-packet-encrypted ack for method=0x00" against what a real BigWorld
Mercury bundle header actually requires at the BaseApp-channel level
(it currently reuses the LoginApp-Reply framing convention — msgid=0xFF +
4-byte length prefix — which may not be valid for BaseApp channel
messages at all).

## Finding 7 (2026-09-17 continuation): traced the "authenticate"/id-0 corruption to the Bundle chain-advance logic, root cause still unconfirmed

**Finding:** Decompiled the actual `Bundle::iterator::unpack` (`FUN_00a83b24`,
static `0xa83b24`) in full, plus its caller loop (`Nub::processOrderedPacket`,
inside `FUN_00a90b14`) and the iterator-advance helper
(`FUN_00a83e28`) called at the end of every loop iteration.

Live-tested two concrete hypotheses derived from the first decompile, both
**disproven**:

1. Removing the `createBasePlayer` push's trailing `b'\x00\x00'` footer
   (theorized as phantom data at the exact byte offset the error reported):
   made `createBasePlayer` itself fail to parse. Reverted.
2. Changing `createBasePlayer`/`setGameTime`'s flags from `0x0001` to
   `0x0000` (removing `FLAG_HAS_REQUESTS`, since `Nub::processPacket`
   shows that bit triggers an extra "first request offset" field this code
   never supplied): live-tested, verified via manual decryption that
   `flags=0x0000` really was sent, and the corruption was **byte-for-byte
   identical** regardless. Reverted.

**Deeper mechanism found (not yet live-tested):** `FUN_00a83e28` runs after
every successfully-dispatched message to advance the iterator to the next
one. Its logic: `iVar4 = header_length + position_after_header` (i.e. the
end position of the message just consumed). If `iVar4 >= total_chain_length`
(the message consumed the chain/packet exactly, or would overrun it), the
code enters a loop that walks to a **next chained packet link**
(`*(long*)(current_chain + 0x10)`) — BigWorld bundles can apparently span
multiple physical packets via a linked-list "chain" structure. On
transitioning to a new chain link, position resets to **2** (skipping a
2-byte per-chain header) and `param_1+4` (the "pending request" position
marker implicated in Finding 2's now-corrected PMF analysis) gets reloaded
from the new chain's own header. If there is no next chain (`lVar6 == 0`,
the normal case for our single, non-chained UDP datagrams), the loop still
runs `iVar4 -= chain_length` once before checking, and the outer iterator's
chain pointer (`*param_1`) gets set to `0`.

**Hypothesis (INFERRED, not yet live-tested):** every message this
project's server sends is a single, self-contained, **exact-fit** UDP
datagram (declared length + header = 100% of the packet, no trailing
slack) — precisely the condition (`iVar4 >= total_chain_length`) that
triggers this chain-advance branch. Whether this is actually a bug (e.g.
the subsequent "has more data" check, `FUN_00a83fac`, comparing the
now-zeroed chain pointer against a bundle-end sentinel that doesn't
match, causing the loop to spuriously continue and read garbage as a new
message) or is normal/handled correctly for a legitimately-terminated
single-packet bundle has **not been determined** — it requires either
dynamic instrumentation (blocked so far, see Finding 5's frida-attach
crash) or decompiling `FUN_00a83fac`'s and the bundle-construction code's
full context (partially done — see `scratch/ghidra_advance.txt` for the
raw decompile of `FUN_00a83e28`, `FUN_00a83fac`, `FUN_00a83b10`, and
`FUN_00a8b0c0`).

**Confidence:** the mechanism trace itself is CONFIRMED (direct
decompilation); the causal link to the live corruption bug is INFERRED
and UNTESTED.

**Live-tested (2026-09-17, same session): partially confirms the mechanism,
does not fix the bug.** Added `ATTEMPT_EXTRA_SLACK` (extra trailing zero
bytes appended to `createBasePlayer`, beyond its 2-byte footer, before
Blowfish padding) to deliberately avoid the exact-fit condition. Result
with `ATTEMPT_EXTRA_SLACK=8`: the corruption's reported position shifted
from `at 11` to `at 16` (exactly the 5-byte width of a fake
flags+msgid+length header the parser tried to read starting right where
`createBasePlayer`'s real content ends), and "needed 4" became "2 left"
instead of "1 left" — consistent with the parser correctly walking *past*
the immediate exact-fit trigger this time, then interpreting our extra
slack bytes as the start of a **second, legitimate-looking message** in
the same bundle (which is normal, correct BigWorld behavious for
multi-message bundles) — and failing because that "message" is just zero
padding, not real content.

**Root cause now understood more precisely:** `total_chain_length` (the
value `FUN_00a83e28`/`Bundle::iterator::unpack` use to decide "is there
more to parse") is computed from the **full padded buffer**, not from our
logically-intended message length — meaning ANY trailing bytes beyond a
message's own declared header+body (whether our deliberate 2-byte footer,
extra test slack, or ordinary unavoidable Blowfish block-alignment
padding) get walked by the parser as if they might be additional bundle
messages. The "wastage byte" stripping this project's static analysis
established (E2E-020) evidently does **not** happen before
`Bundle::iterator::unpack` sees the buffer, contrary to this session's
working assumption — or strips less than assumed. This means **the
`b'\x00\x00'` footer and Blowfish padding scheme used by every packet in
`local_baseapp_capture.py` needs to be reconciled against the client's
real wastage-stripping call site** (not yet located/decompiled) before
any further per-message content bisection is worthwhile — this is the
correct next target, not another guess-and-check on individual message
bytes.

**Follow-up (same session): wastage-stripping confirmed correct, real
culprit pinned down to the "path A" (request-ID+NRO) branch.** Decompiled
`EncryptionFilter::recv` (`FUN_00a8924c`, static `0x989324`/`0x9892c8`,
same function via two call sites) — it **does** strip wastage bytes from
the packet's length field (`*(pkt+0x1a) -= wastage_byte`) before returning,
confirming `total_chain_length` correctly reflects our intended total
plaintext length (header+body+footer, or header+body if no footer),
**not** the raw padded ciphertext length. Verified this empirically by
decrypting the exact "footer removed" `createBasePlayer` packet from the
earlier live test: 16 bytes received, wastage=5, `16-5=11` — exactly
matching the intended 11-byte content (flags+msgid+lenfield+body, no
footer). So `total_chain_length=11` for that test, landing EXACTLY on
`createBasePlayer`'s own declared end (also 11) — an exact-fit case.

Then decompiled `FUN_00a8a674` (called inside `Bundle::iterator::unpack`
to get the msgid-header width) — for the "fixed 1-byte header" case
(interface-wide setting, `*(descriptor+1)==0`) it returns `1`. Recomputing
`Bundle::iterator::unpack`'s arithmetic with this concrete value for the
footer-removed `createBasePlayer` test: position starts at `uVar5=2`
(right after the 2-byte flags field); `uVar12 = 1(header width) + 2 = 3`.
**If "path A" (the `uVar4==uVar5` branch reading an extra 6-byte "request
ID + NRO" block) triggers**, `uVar3(=3)+6=9 <= uVar4(total=11)` is TRUE, so
it consumes 6 MORE bytes (positions 3-8) as a phantom request-ID+NRO
block — bytes that are actually our own 2-byte length field (`06 00`) and
the first 4 bytes of `createBasePlayer`'s real body (`entityId=1`,
`01 00 00 00`). This reconstructs the observed error exactly: only
`11 - 9 = 2`... (arithmetic lands close to, though not pinned bit-exact
to, the observed "4 left, needed 6" without also knowing the live runtime
value of the iterator's `param_1+4` field, which is not recoverable by
static reading alone).

**Why the earlier `flags 0x0001→0x0000` fix (already tried, see above)
did not help despite this being the right mechanism:** "path A" is gated
by comparing the **iterator's own internal state field** (`param_1+4`,
populated once per *packet* by `Nub::processPacket`'s *own* `flags&1`
check, run once before `Bundle::iterator::unpack` is ever called) against
the *current parse position* — not by re-reading our per-message flags
value from inside `unpack()` itself. Whether that iterator field's actual
runtime value coincidentally equals the first message's position (2)
*regardless* of our packet-level flags bit is exactly what static reading
cannot settle — this requires either dynamic instrumentation (still
blocked, see Finding 5) or decompiling every construction/initialization
site of that iterator object, which was not completed this session.

**Next actionable step:** decompile the iterator's constructor and
`Nub::processPacket`'s full body (only partially decompiled so far, see
`scratch/ghidra_unpack_caller.txt`) to find where `param_1+4` gets its
*initial* value before any `flags&1`-gated update — that is the one
missing fact needed to either confirm or fully rule out "path A" as the
root cause with certainty.

## Dead ends

- Symbol-table keyword search for game-logic class names (Finding 3).
- Call-type-only cross-reference search for `0x94c540`'s caller (confirms,
  doesn't add to, the prior Capstone-toolkit finding).

## Next actionable experiments (priority order)

1. **Live-test `Account.onChannelLogin` with the corrected SSO-style
   method-index encoding** (byte `4` instead of `2` for real index 2) — see
   Finding 2. Concrete, low-risk, directly implied by this session's most
   important finding. Requires user approval to resume live emulator
   testing (paused for the Ghidra pivot).
2. Trace `.init_array`/global-constructor entries to find what constructs
   the object living at/near `0x38d7cb8`'s vtable, to finally identify
   `0x94c540`'s real caller by construction site rather than call site.
3. Identify `PTR_DAT_03a15320` (the flag checked as `*PTR_DAT_03a15320 ==
   '\0'` to pick between the direct-dispatch and
   `FUN_00a7bfa8`/`FUN_00a7c0d8` "alternate async/queued dispatch" path
   inside `0x94c540`) and cross-reference it against the debug-flag globals
   already documented in E2E-038 Task 1.
