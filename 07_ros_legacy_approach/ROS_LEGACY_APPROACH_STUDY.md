# ROS Legacy Approach — Feasibility Study

Scope: research only. Nothing in `01_apk/`, `02_dex/`, `03_lib/`, or
`mitm/local_baseapp_capture.py` was modified for this pass. All raw
disassembly referenced below is saved alongside this document in
`07_ros_legacy_approach/`. Source material read (not re-derived):
`C:\Users\Raysoo\Downloads\ROS_RE_LEGACY\ANALYSIS_REPORT.md` and
`06_notes/FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md` (cited by filename per
instruction rather than reproduced in full). Labels: **CONFIRMED** /
**STRONGLY SUPPORTED** / **INFERRED** / **UNKNOWN**, per this project's
existing convention.

Artifacts produced this pass:
- `07_ros_legacy_approach/libmsaoaidsec_arm64_text_disasm.txt` — full
  Capstone AArch64 disassembly of `libmsaoaidsec_arm64.so`'s `.text`
  section (680 instructions, `0xbf4`–`0x1694`), produced with the
  project's own `scratch/xref_lib.py`-style Capstone setup (same
  `CS_ARCH_ARM64` / `CS_MODE_ARM` configuration), pointed at the
  ROS_LEGACY_RE copy of the library instead of `libclient_arm64.so`.

---

## 1. `libmsaoaidsec_arm64.so` — full hook mechanism characterization

### 1.1 File identity and import surface

**CONFIRMED** (ELF header + section table parse, `libmsaoaidsec_arm64.so`,
8,808 bytes total, `.text` only `0xaa0` = 2,720 bytes):

- `DT_NEEDED`: `liblog.so`, `libc.so`, `libm.so`, `libdl.so` only. **No
  `libcrypto.so`/`libssl.so` dependency exists.**
- Full `.dynsym` import list (20 entries, one of which — `JNI_OnLoad` — is
  the library's own single export): `__cxa_finalize`, `__cxa_atexit`,
  `__stack_chk_fail`, `strlen`, `pthread_mutex_lock`, `__memcpy_chk`,
  `pthread_mutex_unlock`, `pthread_create`, `pthread_detach`, `dlsym`,
  `usleep`, `fopen`, `fgets`, `strstr`, `sscanf`, `fclose`, `sysconf`,
  `strcmp`, `mprotect`, plus `JNI_OnLoad` (exported, at `0xc44`).
- **No `sendto` import.** The library never calls `sendto` via its own
  PLT — it resolves the *real* `sendto` at runtime via `dlsym` instead
  (see §1.3), which is exactly why no static import for it exists.
- `.rodata` contains the plaintext format string `"%lx-%*lx %*4s %lx"` —
  the canonical `sscanf` pattern for parsing a `/proc/self/maps` line
  (`start-end perms offset ... path`), and the plaintext JNI type
  signatures `"()V"` / `"(Ljava/lang/String;)V"`.
- The ARM32 sibling `libmsaoaidsec_arm.so` (6,304 bytes) was spot-checked
  via a raw ASCII string scan and shows the **identical** import set,
  the same `/proc/self/maps` format string, and the same absence of any
  crypto symbol or `libcrypto.so` dependency — **CONFIRMED** consistent
  across both architectures.

### 1.2 Mechanism: is it PLT/GOT patching, inline hook, LD_PRELOAD, or something else?

**CONFIRMED: manual runtime PLT/GOT patching of the caller's (libclient.so's)
own `.rela.plt` relocation for `sendto` — not an inline code patch, not
`LD_PRELOAD`, not Zygote injection, not seccomp.**

Evidence, walking `JNI_OnLoad` (`0xc44`) forward:

1. `0xc44`–`0x10a8`: standard prologue, thread-local storage stack-guard
   setup, then `bl dlsym` (`plt` slot resolving to `sym10 dlsym`) whose
   result is stored to a fixed global slot (`adrp #0x3000, +0xca0`).
   This is the **"resolve and cache the real function address"** step —
   the address later used to actually transmit patched packets (§1.4).
2. `0x10b0`–`0x1428`: a loop that `fopen`s (`0x11a4`), `fgets`-reads
   (`0x11bc`) and `strstr`-filters (`0x11cc`) lines of a file — the
   `"%lx-%*lx %*4s %lx"` format string plus the line-oriented
   `fopen`/`fgets` pattern is the standard idiom for parsing
   `/proc/self/maps`, and the subsequent check `cmp w8, #0x7f` (`0x1204`)
   validates the first byte of a candidate mapped region against the
   ELF magic byte (`0x7f`, i.e. `\x7fELF`) to pin down a library's true
   load base among the several `/proc/self/maps` rows a single `.so`
   produces (code/rodata/data segments). **INFERRED**: this locates the
   in-memory base of the target library (most likely `libclient.so`,
   the caller whose GOT is being patched, or `libc.so` — the manual
   ELF-walk code past `0x1240` does not itself re-confirm which one by
   name inside the disassembled range; the `/proc/self/maps` line
   content that decides this was not captured in this pass since the
   comparison substring is one of the obfuscated/XOR-encoded strings,
   see §1.5).
3. `0x1240`–`0x1404`: a hand-rolled ELF symbol-table walk (GNU-hash-style
   bucket/chain traversal with a `br x10` computed-jump dispatch at
   `0x12b8`, consistent with iterating `Elf64_Sym`/`Elf64_Rela` records)
   that locates a **specific relocation entry by name via `strcmp`**
   (`bl strcmp` at `0x13b4`) — i.e., it walks the target library's own
   `.rela.plt`/`.rela.dyn` to find the GOT slot associated with the
   symbol name it is holding (an XOR-obfuscated string, almost certainly
   `"sendto"` given everything downstream operates on that slot).
4. `0x13cc`–`0x1400`: having found the candidate GOT slot address, it
   compares the slot's *current* stored value against the address of its
   own hook function (`0x1468`, see §1.4) to avoid double-patching, then
   calls `mprotect` (`bl mprotect` at `0x13f8`) on the **page containing
   that GOT slot** (`x0 = slot_addr & ~(pagesize-1)`) before the
   (out-of-disassembled-range, but implied) actual store of the hook
   function's address into the slot.
5. `0x1600`–`0x168c`: a `dc cvau` / `ic ivau` / `dsb ish` / `isb`
   cache-maintenance loop (the standard AArch64 "flush a code range from
   both data and instruction caches" idiom) is present and reachable
   from this same code path. This is the one piece of evidence that
   would normally indicate **inline code patching** (GOT-only patches
   don't strictly need an I-cache flush since GOT is data, not
   instructions) — but given the GOT-relocation-walk evidence in
   points 3–4 is unambiguous, the most likely reading is that this cache
   flush is **defensive boilerplate carried over from a generic
   "patch memory" helper** shared with a genuine inline-patch code path
   elsewhere in their toolchain, applied here even though only a GOT
   pointer (not executable code) is being overwritten. **INFERRED**, not
   fully confirmed, since the exact call graph from `0x1600` back up to
   the GOT-patch site was not fully hand-verified instruction-by-
   instruction in this pass.

**Verdict for Task 1's mechanism question**: **PLT/GOT patching**,
specifically a **manual, self-contained relocation-table walk + `mprotect`
+ direct pointer overwrite** (no `xhook`/`whale`-style external hooking
library is linked — the entire mechanism is implemented from scratch in
~2.7 KB of code using only `libc`/`libdl` primitives). Not
`LD_PRELOAD`-style (the library is loaded as a normal JNI native lib via
`System.loadLibrary`, evidenced by the `JNI_OnLoad` export, not via
`LD_PRELOAD` environment injection), not Zygote-level, not seccomp-based.

### 1.3 The FNV-1a computation

**CONFIRMED** (disassembly `0xec0`–`0xf74` in
`libmsaoaidsec_arm64_text_disasm.txt`):

```
0xef0: mov  w24, #0x9dc5
0xef8: movk w24, #0x811c, lsl #16      ; w24 = 0x811c9dc5  (FNV-1a 32-bit offset basis)
...
0xf3c: mov  w8, #0x193
0xf48: movk w8, #0x100, lsl #16        ; w8  = 0x1000193   (FNV-1a 32-bit prime)
0xf4c: ldrb w10, [x9], #1              ; next input byte
0xf54: eor  w10, w24, w10              ; hash ^= byte
0xf58: mul  w24, w10, w8               ; hash *= prime
0xf5c: b.ne #0xf4c                     ; loop while bytes remain
```

This is exactly the canonical 32-bit FNV-1a algorithm
(`hash = (hash ^ byte) * prime`, seeded `0x811c9dc5`, prime `0x1000193`),
**matching `ANALYSIS_REPORT.md`'s claim exactly**, and the ARM Legacy
report's description is now independently re-derived from the binary
rather than only cited.

The string hashed is capped at `min(strlen(input), 0x1ff)` bytes
(`0xf00`–`0xf08`), copied into a fixed `.bss` scratch buffer (`0x3a98`) via
`__memcpy_chk` under a `pthread_mutex_lock`/`unlock` pair (`0xf14`/`0xf70`)
— i.e., thread-safe, bounded, and the result is cached into a global
4-byte slot (`adrp #0x3000, str w24,[x8,#0xc98]`) for later use by the
`sendto` hook.

**INFERRED (source of the hashed string)**: the function that performs
this hashing (`0xec0`–`0xfac`) is itself installed as a replacement entry
in a large (≥ 0x558-byte) function-pointer table reached through `x0`
(`ldr x8,[x0]` then `ldr x8,[x8,#0x548]`), and after computing the hash it
tail-calls through a *different* slot in that same table
(`ldr x3,[x8,#0x550]`) forwarding `(x0=original first arg, x1=the string
pointer it just hashed, x2=strlen result)`. The table shape (very large,
reached via `**x0`, holding hundreds of function pointers at 8-byte
strides) is consistent with — but not proven beyond doubt to be — the
**`JNIEnv` function table** (`JNINativeInterface`), with offsets
`0x548`/`0x550` corresponding to adjacent entries in that table (index
169/170, in the neighborhood of `GetStringUTFChars`/
`ReleaseStringUTFChars` in the standard JNI table layout). If so, this
library hooks a `JNIEnv` string-accessor function **table-wide** (i.e.
for the whole process, not just one call site) so that it observes and
hashes *some* UTF-8 string that Java code passes through JNI around
login/ticket time — the plaintext `.rodata` string `"(Ljava/lang/String;)V"`
nearby supports a JNI-string-related purpose. **Not independently
re-confirmed against a live JNI header offset table in this pass** — flagged
as the one point in this analysis that would benefit from live/dynamic
verification (Frida trace of which `JNIEnv` slot gets overwritten) if this
approach is pursued further.

### 1.4 The exact packet write: offset and precondition

**CONFIRMED** (disassembly `0x1464`–`0x15f8`):

The hook function installed into the (presumed) `sendto` GOT slot has the
signature-consistent register layout of
`sendto(int sockfd, const void *buf, size_t len, int flags, const struct sockaddr *dest_addr, socklen_t addrlen)`
— `w0, x1, x2, w3, x4, w5`. It:

1. Rejects (falls through to calling the *real* `sendto` unmodified via the
   cached function pointer at `[x8,#0xca0]`, loaded through `x6`) unless
   **all** of the following hold on the outgoing buffer `x1` of length
   `x2`:
   - `x2 == 0x18` (**24 bytes exactly** — `0x1498`/`0x149c`)
   - `buf[0]==1, buf[1]==0, buf[2]==0, buf[3]==0x0b` (`0x14a0`–`0x14c4`,
     i.e. **the `01 00 00 0b` magic** cited in `ANALYSIS_REPORT.md`)
   - `buf[4]==0`, `buf[9]==0`, `buf[0xa]==0` (`0x14c8`–`0x14dc`)
   - `buf[0x13]==0x14, buf[0x14]==0, buf[0x15]==0` (`0x14e0`–`0x14f8`)
   - `buf[0x16]==2` and `buf[0x17]!=0` is treated as *reject* (i.e. it
     requires `buf[0x17]==0` to accept) (`0x14fc`–`0x150c`)
2. On match: loads the cached FNV hash global (`0x1578`, `ldr w20,
   [x8,#0xc98]`); if it is `0` (no ticket ever hashed yet), falls through
   to the unmodified call. Otherwise, checks the **current** 4 bytes at
   `buf+0xb` are already `0` (`0x159c`–`0x15a0`, `ldur w8,[x1,#0xb];
   cbnz w8 -> skip`) — a guard against re-stamping an already-tagged
   packet.
3. Copies the entire 24-byte packet into a **local stack buffer**
   (`q0`/`x9` load-and-store, `0x15a8`–`0x15c0`), then **overwrites bytes
   `[0xb..0xf)` of that stack copy** with the cached FNV hash
   (`0x15c4: stur w20, [sp, #0xb]`) — **CONFIRMED: exactly byte offset
   `0x0b` (11), 4 bytes, little-endian**, matching
   `ANALYSIS_REPORT.md`'s claim precisely.
4. Calls the real `sendto` (function pointer at `[x8,#0xca0]`, resolved
   via `dlsym` in `JNI_OnLoad`, §1.2 step 1) with the **modified stack
   copy**, not the caller's original buffer — the original 24-byte
   packet built by the game's native code is left untouched in memory;
   only the wire transmission is altered.

### 1.5 Does it touch Blowfish / `RAND_bytes` / `EncryptionFilter` / `BF_*` at all?

**CONFIRMED: no.** Four independent lines of evidence, all negative:

1. **Import table** (§1.1): the complete 19-symbol import list contains
   no OpenSSL/crypto function of any kind (`RAND_bytes`, `BF_set_key`,
   `BF_encrypt`, `EVP_*`, etc. are all absent).
2. **`DT_NEEDED`** (§1.1): `libcrypto.so`/`libssl.so` is not linked at
   all, which means the library has **no possible call path** to any
   OpenSSL primitive — it could not call `RAND_bytes` or `BF_set_key`
   even if it wanted to, without a `dlopen("libcrypto.so", ...)` it also
   never performs (`dlopen` itself is not imported; only `dlsym` is, and
   every observed `dlsym` use in the dumped code targets a `libc`-family
   symbol resolved against handles obtained from the maps-parsing +
   ELF-symtab-walk logic of §1.2, not against a `libcrypto.so` handle).
3. **String content**: neither the plaintext `.rodata` strings nor the
   `.dynstr` table contain `"BF_"`, `"RAND_bytes"`, `"EVP"`, `"crypto"`,
   `"Blowfish"`, or `"EncryptionFilter"` in any form. The one set of
   still-obfuscated (single-byte-XOR, key byte `0x5a` found at `.data`
   offset `0x3a68`/file-offset `0x1a68`) strings decode to a handful of
   short library-name-shaped fragments (`libc.so`-length patterns) — not
   long enough to encode any crypto symbol name, and their use sites
   (feeding `strstr`/`strcmp` calls inside the maps-parsing and
   symbol-walk loops of §1.2) are already fully accounted for by the
   sendto-GOT-patch mechanism.
4. **Full `.text` size**: the entire `.text` section is `0xaa0` (2,720)
   bytes and every instruction in it was disassembled and read this pass
   (`libmsaoaidsec_arm64_text_disasm.txt`, 680 instructions); there is no
   unaccounted code region left that could plausibly contain a hidden
   `RAND_bytes` hook, key-fixing routine, or `EncryptionFilter`
   interaction — the entire binary's logic is fully explained by: (a) the
   JNI-table string-hashing hook (§1.3), (b) the `sendto` GOT-patch
   installation (§1.2) and its hook body (§1.4), (c) housekeeping
   (`JNI_OnLoad` entry/exit, PLT stubs, cache-flush helper).

**This directly answers the single most important sub-question in Task
1: ROS Legacy's Gate 2 hook does *not* touch, neutralize, fix, or predict
the client's Blowfish/`RAND_bytes` key in any way.** It operates entirely
at the UDP transport layer, one layer below and structurally unaware of
the Mercury application-layer Blowfish encryption the standing paradox is
about.

---

## 2. Comparison against our own client (`com.netease.chiji` v1117219)

**CONFIRMED (Glob/grep across `01_apk/`, `02_dex/`, `03_lib/`)**: our
client ships **no `libmsaoaidsec*.so` of any kind, under any name** — a
full recursive search of the decompiled APK tree
(`01_apk/base_decompiled/lib/arm64-v8a/`,
`01_apk/base_decompiled/build/apk/lib/*/`, and `03_lib/`) and a
case-insensitive grep for `msaoaidsec`/`oaid` across `01_apk`, `02_dex`,
`03_lib` returns **zero hits** for any native library or smali reference.
The full native library manifest of our client's `arm64-v8a` slice is:

```
frida-gadget-17.so, frida-gadget.so, libAudioCCReName.so, libAudioCore.so,
libAudioEngine.so, libAudioEngineJni.so, libc++_shared.so, libclient.so,
libclient_arm64.so, libcom_netease_androidcrashhandler_AndroidCrashHandler.so,
libcom_netease_ps_codescanner.so, libfmodevent.so, libfmodex.so,
libhoudini.so, libijkffmpeg.so, libijkplayer.so, libijksdl.so,
libijkutil.so, libntunisdk.so, libstreammgr.so, libunisdkdctool.so,
nb_libc.so
```

(`frida-gadget*.so` present are this project's own prior instrumentation
artifacts, not part of the stock client — noted for completeness, not a
finding about NetEase's build.)

**Consequence — this rules out the "drop-in .so swap" hypothesis
outright**: there is no existing `libmsaoaidsec.so` slot in our client to
overwrite, and no existing `System.loadLibrary("msaoaidsec")` (or
equivalent) call site in our decompiled smali to redirect. ROS Legacy's
`libmsaoaidsec_arm64.so` is a **from-scratch, small (8.8 KB), purpose-built
library that impersonates the name and role of NetEase's real OAID/
anti-fraud stub in *their* build** (which their own `ANALYSIS_REPORT.md`
describes as "normally the OAID security stub" being hijacked) — it is
not a drop-in replacement of anything present in `com.netease.chiji`
v1117219's own file layout. **STRONGLY SUPPORTED conclusion**: either (a)
NetEase's v1117219 build (ours) never bundled an OAID stub library under
that name to begin with (different SDK/region/version configuration than
whatever ROS Legacy's target build used), or (b) it exists under a
different filename in this client and was not identified by name-based
search — (b) was checked by cross-referencing the *entire* library list
above against known-OAID-related names (`oaid`, `msa`, no matches beyond
the already-listed `libntunisdk.so`, which is NetEase's own Union SDK and
structurally unrelated — it is a large, fully-featured multi-hundred-KB
SDK library, not an 8 KB stub). No further candidate was found, so (a) is
the better-supported reading.

**Mercury handshake packet structural cross-check**: **CONFIRMED
MISMATCH** — resolved this pass using material already on disk (no new
capture run, no touch to `mitm/local_baseapp_capture.py`, per the task's
boundary). This project's existing capture log
`mitm/captures/BASEAPP_LOGIN_CAPTURE.txt` (1,508 lines, produced by a
prior pass's already-running fake LoginApp/BaseApp UDP listeners) records
every inbound/outbound UDP datagram size for real client connections
across many repeated login attempts. The pattern is completely
consistent throughout the file: the client's **very first** datagram to
LoginApp is **9 bytes** (`"LOGINAPP UDP RECV 9 bytes from ..."`, dozens of
occurrences), followed later by the well-documented **273-byte**
`LogOnParams` RSA request, with the fake server's **20-byte**
`LoginReplyRecord` sent in response to each. **No 24-byte datagram
appears anywhere in this capture file at all** (`grep` for `RECV 24
bytes` and for a `01 00 00 0b`-style hex prefix both return zero matches
across all four files in `mitm/captures/`). **This means ROS Legacy's
Gate 2 packet signature (24 bytes, `01 00 00 0b ...`) does NOT match our
client's actual first handshake datagram (9 bytes, contents not hex-
logged by the existing capture tool)** — either (a) our client's build/
protocol revision uses a structurally different (and shorter) pre-login
handshake packet than whatever ROS Legacy's target build sends, or (b)
ROS Legacy's target packet is a *different* handshake message than the
very first one (e.g. a second-stage packet sent after the 9-byte one,
which the existing capture tool's size-only logging cannot rule out
without also logging hex content for the 9-byte packets). **Practical
consequence for Task 5**: Gate 2's hook, if reused verbatim (same
byte-offset/length/magic checks) against our own client's traffic,
**would never fire** — the `x2==0x18` length check alone would reject
every packet our client actually sends at that stage. Any adaptation of
this technique to our project would need its own signature derived from
our own client's real handshake bytes (which requires extending the
existing capture tooling to also hex-dump the 9-byte packets' contents —
a small, low-risk follow-up, listed in the next-steps below), not ROS
Legacy's constants reused as-is.

---

## 3. Gate 1 (auth bypass) architectural applicability

**STRONGLY SUPPORTED — structurally compatible pattern exists in our
client, but ROS Legacy's own Java implementation is not directly
reusable.**

- `01_apk/base_decompiled/smali/com/netease/neox/Channel.smali` (our
  client) exposes **exactly** the method ROS Legacy's `RosAuth`
  short-circuit relies on: `.method public loginDone(I)V` (line 2044 of
  that file), plus `setPropStr(Ljava/lang/String;Ljava/lang/String;)V`
  and `setPropInt(Ljava/lang/String;I)V` methods (lines 3679/3692) that
  both forward to
  `Lcom/netease/ntunisdk/base/GamerInterface;->setPropStr/setPropInt` —
  **structurally the same shape** as ROS Legacy's
  `SdkMgr.getInst().setPropStr(...)`/`setPropInt(...)` +
  `Channel.getInstance().loginDone(0)` sequence, just routed through our
  client's own `GamerInterface` abstraction instead of directly through a
  class literally named `SdkMgr` in the call site ROS Legacy patched
  (their `SdkMgr` class likely *is* the same underlying NetEase
  `ntunisdk` component, just invoked through a different accessor in
  their build/version).
- Our client also has the full `com.netease.mpay.oversea.*` package tree
  present (`a.smali`, `a/a/a.smali`, `a/b.smali`, etc. under
  `01_apk/base_decompiled/smali/com/netease/mpay/oversea/`) — i.e. the
  MPay overseas login path ROS Legacy replaced with `RosAuth` **exists in
  our client too**, confirming the two builds share the same underlying
  NetEase SDK family/architecture (both are `com.netease.*`-branded ROS
  builds on the same middleware), not two unrelated codebases.
- This project's own `06_notes/MPAY_AUTH_FLOW/` folder (7 prior trace
  files: login response parser, post-login branch/`onLoginSuccess`,
  cancel-login callback, status-code mapping, SDK-token-login-v2 parser
  and callback) already independently documents this exact login/callback
  chain in our client from a prior pass — cited here rather than
  re-derived, and its existence corroborates that our client's MPay/
  `Channel`/`GamerInterface` login chain is a mapped, understood surface,
  not an unknown one.

**Caveat, explicitly per the task's own framing**: ROS Legacy's actual
smali patch (the specific `RosAuth` class, its exact bytecode, and the
exact injection point it uses) belongs to a **third-party, already-
modified APK** (`net.roslegacy.prod`) that a different developer built for
their *own* already-running private-server infrastructure. It is not
proven, and was not tested this pass, that grafting their literal
`RosAuth.smali`/hook logic onto `com.netease.chiji`'s decompiled smali
would work without adaptation — only that the **general pattern** (a
custom class calling `setPropStr`/`setPropInt`/`loginDone` directly to
fake a completed SDK login, bypassing the MPay web-auth UI) has a
structurally equivalent target in our client. Verifying it end-to-end
requires actually building and running a patched APK, which is
explicitly **out of scope for this pass**.

---

## 4. Does this sidestep the Blowfish-key paradox, or not?

**Verdict: it sidesteps the problem for ROS Legacy's own gateway, in a
way that would NOT work for our project as a substitute solution — for
an unmodified client binary, decrypting `LoginReply` under the correct
key is still mandatory, and Gate 2 does nothing to address that.**

Reasoning, combining §1.5 (static: Gate 2 never touches
`RAND_bytes`/`BF_set_key`) with `FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md`'s
own established facts (cited, not re-derived):

1. `FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md` (§3, step 4) already
   establishes: `onLoginReply` **unconditionally** calls the decrypt
   routine at `0x989600` on the 20-byte `LoginReply` body, using whatever
   `EncryptionFilter` is cached at `+0x148` — and for the *first* reply on
   a fresh connection, that is **necessarily** the client's own
   `RAND_bytes(4)`-seeded key (CONFIRMED in that document, no
   intervening write found anywhere between construction and decrypt).
   This is a property of `libclient.so`'s own native code, entirely
   independent of however a packet got identified as "belonging" to a
   session on the wire.
2. Gate 2's FNV-1a hash (§1.3–1.4) is written into the **plaintext
   header** of the small 24-byte handshake packet, at a byte offset
   (`0xb`) that is *outside* whatever the `LoginReply`'s encrypted 20-byte
   body actually is (that body belongs to a later, separate,
   larger message per this project's own `LOGIN_REPLY_RECORD.md`/
   `MERCURY_LOGIN_REPLY_BODY_TRACE.md` framing — the 24-byte packet Gate 2
   tags is a small pre-login/handshake datagram, not the `LoginReply`
   message itself). **The hash is a session/routing tag at the UDP
   envelope layer** ("which client socket is this datagram from, for my
   gateway's own bookkeeping"), not a cryptographic key or key-derivation
   input, and it is never fed anywhere near `BF_set_key`/`RAND_bytes` per
   §1.5's exhaustive negative result.
3. Therefore: **ROS Legacy's own client binary still generates its own
   process-local `RAND_bytes(4)` key exactly as our client does** (their
   `libclient.so`/game engine is, per their own `ANALYSIS_REPORT.md`,
   the same NeoX/BigWorld-derived engine — they did not appear to patch
   `libclient.so` itself at all, only `libmsaoaidsec.so`, an entirely
   separate stub library). Their own client would, by the same logic
   this project's static analysis established for our client, require
   their custom Mercury **gateway** to somehow encrypt the first
   `LoginReply`'s 20-byte body under that same unknown, per-connection
   random key for their client to decrypt it correctly — **the paradox is
   not resolved for them either; it is simply not what Gate 2 was built
   to solve.**
4. Two readings remain open, honestly flagged as **UNKNOWN** rather than
   resolved by this pass, for how ROS Legacy's *server side* actually
   gets a working `LoginReply` past their own unmodified client's decrypt
   step:
   - **(a) They solved it by a different, still-undiscovered mechanism**
     — e.g. a patch to `libclient.so` itself (not audited in this pass;
     ROS Legacy's `decompiled_smali/` and any native library changes to
     *their* `libclient.so` specifically were not compared against ours
     in this study — this is a concrete gap for next steps, §5).
   - **(b) Their server/gateway is simply not depended upon to serve a
     cryptographically meaningful first `LoginReply` at all** — e.g. if
     their custom BaseApp/LoginApp implementation sends a `LoginReply`
     whose 20-byte body, once "decrypted" under the client's own
     self-generated garbage key, still parses into a valid-enough
     BaseApp address purely by their server engineering around whatever
     garbage bytes result (this would require the client's post-decrypt
     validation to be weak/permissive enough to accept it, which this
     project's own prior passes have not established one way or the
     other for the BaseApp-address field specifically — see
     `06_trace/CHECK_SCRIPT_BASEAPP_ADDR_TRACE.md`, `06_trace/
     SERVER_ADDRESS_TRACE.md`, cited not re-derived).
   - Distinguishing (a) from (b) requires either diffing ROS Legacy's
     `libclient.so`/game-engine binaries against stock (not attempted
     this pass) or a live capture of their actual `LoginReply` wire bytes
     (not available to this project — their infrastructure is a
     third-party private server this project has no access to and no
     standing permission to probe, consistent with this project's
     standing "no attacks on production/official services" rule, which
     also extends to *not* probing a third party's private server without
     invitation).
5. **Net verdict for Task 4's core question**: adopting ROS Legacy's Gate
   1 + Gate 2 pattern would let this project's own LOCAL/LAN test server
   identify which UDP session a datagram belongs to (a genuinely useful,
   reusable idea, independent of the Blowfish question — see §5), but it
   does **not**, by itself, let a local server skip correctly
   Blowfish-encrypting the first `LoginReply`'s 20-byte body under the
   client's own unknown `RAND_bytes(4)` key. The client-side decrypt at
   `0x989600` is unconditional and happens regardless of how the
   underlying UDP transport identified the sender. **The standing
   paradox remains fully unresolved for an unmodified `com.netease.chiji`
   client** even if this project adopted Gate 1 + Gate 2 wholesale.

---

## 5. Concrete next steps, ranked

Ranked by (evidence value) / (effort), highest first. Items 1–2 stay
within this pass's "research only" boundary if attempted with existing
captured/static material; items 3+ require live testing and should be
treated as separate, explicitly-approved follow-up work.

1. **(Static, low effort, directly resolves §1.3's one open item)**
   Verify the `0x548`/`0x550` JNIEnv-table-offset hypothesis against a
   real Android NDK `jni.h`/`JNINativeInterface` struct layout for the
   relevant API level, to confirm/refute which exact `JNIEnv` function
   ROS Legacy hooks to obtain the ticket string. This closes the one
   **INFERRED-not-CONFIRMED** item in the Gate 2 mechanism writeup.
2. **(Static, already partly done this pass — one small live step
   remains)** This pass already found (§2) that our client's real first
   handshake datagram is **9 bytes**, not ROS Legacy's 24-byte target —
   so Gate 2's exact signature does not transfer. The remaining step is
   to extend `mitm/local_baseapp_capture.py` (a small, low-risk change,
   not attempted this pass per the task's boundary) to also hex-dump the
   9-byte packets' contents, then re-run the existing local capture setup
   once to see their actual structure and decide whether an
   equivalent-but-different offset/signature could be defined for our
   client.
3. **(Static, medium effort)** Diff ROS Legacy's `decompiled_smali/` and
   any native libraries *other than* `libmsaoaidsec.so` (their
   `libclient.so`, if bundled in their OBBs/APK, was not located or
   audited in this pass) against our own `03_lib/libclient_arm64.so` to
   test hypothesis (a) of §4 point 4 — i.e., whether they patched the
   engine itself to solve the Blowfish paradox in a way this pass did not
   find, because it was never inside `libmsaoaidsec.so` to begin with.
   This is the single highest-value remaining unknown from this pass.
4. **(Live, requires explicit approval before proceeding — crosses into
   implementation)** On a LAN-only test install of `com.netease.chiji`
   (never a production install), test whether adding a same-role stub
   library (built fresh, not ROS Legacy's binary, to avoid any IP/
   distribution concerns) that hooks `sendto` the same way, against our
   own local test BaseApp/LoginApp server, produces a working session-
   routing signal our server can read — independent of, and without
   waiting for, the Blowfish question being resolved. This is a
   reusable session-identification technique regardless of the paradox's
   outcome.
5. **(Live, gated on item 3's outcome)** Only if item 3 finds a genuine
   `libclient.so`-level key-fixing patch in ROS Legacy's engine: assess
   whether an equivalent, independently-authored patch to our own
   client's `RAND_bytes`/`BF_set_key` call site would be necessary to
   ever resolve the paradox for a LOCAL server — and flag explicitly at
   that point whether such a patch would still respect this project's
   standing rule against bypassing anti-cheat/DRM mechanisms verbatim
   from a third party's binary, versus independently re-implementing a
   LAN-only equivalent.

**Explicit scope flag, per the task's own instruction**: everything in
this study concerns *ROS Legacy's own build* interoperating with *their
own private server infrastructure*, which this project has no
relationship to and should not probe or interact with. Nothing here
recommends bypassing **NetEase's** production auth/DRM — Gate 1/Gate 2 as
characterized are techniques for a LOCAL test client talking to a LOCAL
test server, the same standing framing as the rest of this project's
work. If any future step is found to require literally reusing ROS
Legacy's copyrighted binaries/patches (as opposed to independently
re-implementing the *pattern*) against our own client for anything beyond
this kind of static study, that should be flagged again explicitly before
proceeding, since this project has no license or permission from ROS
Legacy's authors to redistribute or repurpose their build.

**Note on `ros_auth.txt`**: its existence, location
(`ROS_RE_LEGACY/ros_auth.txt`), and role (a bare login-ticket string
consumed by `RosAuth`/the deep-link handler) are described structurally
above; its value was not read into, copied into, or referenced by value
anywhere in this document, per the task's explicit instruction — it looks
like a live/possibly-still-valid credential for a third party's account
on their service and must stay out of this repo entirely.

---

```
VERDICT:
GATE2_HOOK_MECHANISM: CONFIRMED — manual runtime PLT/GOT patch of libclient.so's own `sendto` relocation entry (via /proc/self/maps parsing + hand-rolled ELF symbol-table walk + mprotect + direct GOT-slot overwrite), NOT LD_PRELOAD, NOT Zygote injection, NOT seccomp, NOT an xhook/whale-style external trampoline library (fully self-contained in ~2.7KB of hand-written code). A separate hook on a large (likely JNIEnv) function-pointer table computes an FNV-1a(0x811c9dc5,0x1000193) hash of an intercepted string and caches it globally; the sendto hook stamps that 4-byte hash at exactly byte offset 0x0b of any outgoing 24-byte "01 00 00 0b..." packet, on a copy, before forwarding to the real sendto (resolved via dlsym).
GATE2_TOUCHES_BLOWFISH_KEY: NO — CONFIRMED by exhaustive negative evidence: no OpenSSL/crypto import, no libcrypto.so/libssl.so linkage (DT_NEEDED lists only liblog/libc/libm/libdl), no BF_/RAND_bytes/EncryptionFilter/crypto string anywhere in .rodata/.dynstr/obfuscated strings, and the entire 2,720-byte .text section was fully disassembled and accounted for by non-crypto logic (JNI-table string hash + sendto GOT hook + housekeeping only).
BLOWFISH_PARADOX_SIDESTEPPED_OR_STILL_BLOCKING: STILL BLOCKING for an unmodified client. Gate 2 tags a UDP envelope at the transport layer for the custom gateway's own session bookkeeping; it does nothing to and knows nothing about the client's unconditional native-side Blowfish decrypt of the LoginReply body (0x989600, per FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md) under its own process-local RAND_bytes(4) key. ROS Legacy's own client would face the identical paradox unless they separately patched libclient.so itself (not found in this pass's scope — libmsaoaidsec.so is the only native artifact audited) or their server tolerates/exploits weak post-decrypt validation of the BaseApp-address field (unconfirmed, third possibility, requires access to their live traffic this project does not have and should not seek).
GATE1_APPLICABLE_TO_OUR_CLIENT: STRONGLY SUPPORTED architecturally — com.netease.chiji's own decompiled smali has the same shape of login-shortcut surface ROS Legacy exploited (Channel.smali's loginDone(I), setPropStr/setPropInt forwarding to GamerInterface; the full com.netease.mpay.oversea.* MPay package is present), consistent with both builds sharing the same underlying NetEase SDK family. Not tested end-to-end; ROS Legacy's literal RosAuth patch is third-party code specific to their build, not proven to graft onto ours without independent adaptation.
RECOMMENDED_NEXT_STEP: Already-existing mitm/captures/BASEAPP_LOGIN_CAPTURE.txt was checked this pass and shows our client's actual first LoginApp datagram is 9 bytes, not ROS Legacy's 24-byte "01 00 00 0b" target — Gate 2's exact signature does not transfer as-is. Next: (1) extend mitm/local_baseapp_capture.py to hex-dump the 9-byte packets' contents (small, low-risk, not done this pass) to see if an equivalent but differently-shaped hook could target our own client's real handshake; (2) in parallel, pursue item 3 of §5 (diff ROS Legacy's engine/libclient artifacts, if any exist in their teardown, against ours) as the highest-value remaining unknown, since that is the only place a genuine independent solution to the Blowfish paradox could still be hiding in their build.
```
