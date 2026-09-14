# ROS v1117219 — Frida Stalker Runtime Trace of a Live Login Attempt

**Result up front**: Stalker successfully attached and captured real, bounded (call-summary
mode, not raw instruction dumps) execution data during three live login attempts. This
**positively identifies, for the first time, the actual JIT translation-cache library**
(`/system/lib64/arm64/nb/libtcb.so`) where NativeBridge's translated code runs, and shows
**timing-correlated evidence** of new code being translated/executed exactly when
`ServerConnection::logOnBegin` fires. However, semantic attribution — mapping specific
observed addresses back to specific `libclient_arm64.so` source functions such as
`LoginHandler::onLoginReply` — was **not achieved**, for reasons explained in §5.
`LoginHandler::onLoginReply` is **not** claimed to have been reached.

## 1. Stalker Setup

- **Process**: `com.netease.chiji`, PID `16332` (same live process used throughout this
  project's dynamic-capture sessions).
- **Thread selected**: TID `16424` — identified directly from `logcat`, which tags every
  `ServerConnection::logOnBegin`/`logOnComplete` line with this exact TID
  (`16332 16424 I [...] M : [INFO] ServerConnection::logOnBegin ...`). Confirmed present
  and in `waiting` state via `Process.enumerateThreads()` immediately before each run.
- **Frida**: same working 16.2.1 (x86_64 build) setup established in prior sessions,
  reused without changes.
- **Mode**: `Stalker.follow(tid, { events: { call: true }, onCallSummary: fn })` — an
  aggregated call-target→count map per flush, **not** per-instruction (`exec`) tracing.
  This was a deliberate choice per the task's explicit instruction to avoid an enormous raw
  dump; `onCallSummary` bounds the output to "which addresses were called, how many times,"
  which was sufficient to answer the questions asked.
- Scripts: `scratch/stalker_login.js` (the Frida agent), `scratch/run_stalker.py` /
  `run_stalker2.py` / `run_stalker3.py` (drivers for the single-window, baseline-diff, and
  time-sliced experiments respectively).

## 2. NativeBridge/JIT Execution — Directly Observed (Phase 2)

A single 12-second follow spanning one full login attempt captured **688,128 calls across
386 unique target addresses**. Resolving each target's containing memory range
(`Process.findRangeByAddress`) gives a direct, dynamic confirmation of where execution
actually happens:

| Range | Protection | Hits | Role |
|---|---|---|---|
| `/system/lib64/libhoudini.so` (3 sub-ranges) | `r-x` | 1505 + 192 + 64 = 1761 | **Houdini's own native x86_64 code** — the ARM64→x86 translator/dispatcher itself |
| `/system/lib64/arm64/nb/libtcb.so` (`0xd208000`–`0xd34e000`) | **`r-x`** | 958 | **CONFIRMED BY DYNAMIC CAPTURE: this is Houdini's JIT translation-cache library** — a real, file-backed, executable mapping distinct from `libclient.so`'s own (non-executable, `r--p`) pages. This is the first direct evidence of *where* NativeBridge-translated code actually executes. |
| `/system/lib64/libc.so`, `libm.so`, `liblog.so`, `libz.so` (host x86_64) | `r-x`/`rwx` | hundreds each | Normal host-side library calls (matches the earlier finding that host `libc.so` hooks see real, but unrelated, traffic) |

**This directly answers the task's Phase 2 question**: yes, Stalker reports genuine
x86_64 addresses (not ARM64 `libclient.so` addresses), and — new this pass — those
addresses resolve to a **real, named, mapped, executable file** (`libtcb.so`), not pure
anonymous JIT memory as previously assumed. This means, in principle, addresses within
`libtcb.so`'s range *could* be targeted by `Interceptor.attach` (they are genuinely
executable), which is a materially different situation from `libclient.so`'s own
non-executable pages — see §5 for why this was not yet exploited successfully.

The single hottest address in the unfiltered 12-second capture, `0xd270970` (114,070 hits),
falls inside `libtcb.so`'s range — i.e., the busiest code during this whole window is
**translated, cached code**, not Houdini's dispatcher itself. This is consistent with a
tight, already-warm loop (most likely UI/render-thread ticking, since this same thread
appears to also drive general script execution — see §4).

## 3. Login Timeline Correlation (Phase 3)

A time-sliced capture (`scratch/run_stalker3.py`, ~1-second slices via repeated
follow/unfollow cycles) was cross-referenced against `logcat`:

```
t=0.00s   PLAY tapped
t≈0.7s    (Stalker slice 0 begins)
t≈1.5s    ServerConnection::logOnBegin fires (logcat, absolute time 21:53:41.532)
t=0-2.6s  slice 0: 115 NEW addresses vs. idle baseline, dominated by two addresses in
          libhoudini.so at 2,097 hits each (highest of any slice) — consistent with
          "cold" translation of previously-unvisited ARM64 code triggered by logOnBegin
t=2.6-8.3s (slices 1-3): the same two addresses continue firing but at steadily
          decreasing "new" counts (1183 → 308 → 850) — consistent with most of the
          relevant code becoming "warm" (already translated/cached) after the first pass
t≈9.6s    Mercury::REASON_TIMER_EXPIRED (logcat, absolute time 21:53:50.411, i.e. ~8.9s
          after logOnBegin — matches the ~9s timeout figure established in prior sessions)
t=8.3-9.9s (slice 4): activity drops sharply to just 2 new addresses — consistent with
          the retry loop having ended and no new code being exercised right at/after
          the timeout
t=9.9s+   (slices 5,6,8,10,11): the SAME two libhoudini.so addresses resume firing at
          high counts (1521, 1482, 2046, 1964, 2114) — see §4 for why this is likely
          NOT further Mercury activity
```

**Confirmed**: `logOnBegin`'s onset and the initial Stalker activity burst align within
roughly one slice boundary (~1s resolution, the finest this method provides). The
`REASON_TIMER_EXPIRED` timeout also aligns with a sharp, brief activity drop. This is
real, direct temporal correlation — not an assumption.

## 4. Why Semantic Attribution Failed (Phase 4 — Honest Limitation)

The two dominant addresses (`0x76388ea5b860`, `0x76388eab9440`, always appearing together
with **identical hit counts** — strongly suggesting an enter/exit trampoline pair for the
same dispatch mechanism) sit inside `libhoudini.so` itself, not inside `libtcb.so`'s
translated-code cache. This means they are **Houdini's own generic block-lookup/dispatch
routines** — the machinery Houdini uses to find or create a translated block for *any*
ARM64 program counter — not a trampoline specific to Mercury or `LoginHandler`.

**Evidence this is generic, not Mercury-specific**: these same two addresses continued
firing at high volume in slices 5, 6, 8, 10, and 11 — **well after** the `logOnComplete`
timeout, when no further LoginApp networking should be occurring. The most likely
explanation is that this same thread (TID `16424`) also drives general embedded-Python
script execution and/or UI state transitions (the "Failed to login" style flow, or the
title screen animation resuming), all of which is *also* ARM64 code requiring the exact
same Houdini dispatch path. **Without reverse-engineering Houdini's own internal
data structures (its ARM64-PC → translated-block lookup table), there is no way to
determine which *specific* ARM64 source address triggered any individual dispatch call** —
the call-summary view is fundamentally too coarse for this, since `onCallSummary` reports
only the **translated x86_64 call target**, never the original ARM64 program counter that
was being translated.

**This is reported as the precise, bounded reason semantic attribution failed** — not
a vague "it didn't work." A finer-grained approach (e.g., `onReceive` with raw `compile`
events, which Stalker exposes specifically to observe *which ARM64 blocks are being
compiled*, if NativeBridge's Houdini integration surfaces this to Stalker at all — untested
in this pass) is the concrete next step, named in §7.

## 5. Why `Interceptor`-Based Hooking Still Wasn't Retried Here

`libtcb.so` being genuinely `r-x` and file-backed (§2) is new information suggesting
`Interceptor.attach` *might* work there in principle — but the cache's contents are
dynamically populated at runtime (translated per-ARM64-block, in an order and at offsets
that depend on execution history), so there is **no static way to compute in advance**
which `libtcb.so` offset will hold the translation of a specific `libclient_arm64.so`
function like `0x938070` (`LoginHandler::onLoginReply`). Hooking would require first
observing, at runtime, which cache offset corresponds to that function — circularly
requiring the same attribution problem from §4 to be solved first. This was not attempted
in this pass; it is named as a candidate follow-up in §7.

## 6. Controlled LoginReply Experiment (Phase 5)

The capture server (`mitm/local_baseapp_capture.py`) was already running its existing
reply logic (the flags=0x0000-footer candidate from `LOGIN_REPLY_MERCURY_ENVELOPE.md` §5,
Attempt C) throughout all three Stalker runs in this pass — so every login attempt
captured here already included a real local reply being sent back to the client on every
retry, exactly as in prior non-Stalker sessions. No new reply variant was introduced.

**Answers to the task's A–F, based on combined Stalker + logcat + capture-log evidence
from this pass**:

| # | Question | Answer | Evidence |
|---|---|---|---|
| A | Does the client receive the UDP response? | **UNKNOWN from Stalker** (could not isolate a `recvfrom`-equivalent call in the coarse call-summary view); **STRONG EVIDENCE it's delivered at the OS/socket level** — the capture server logged a successful `sendto()` to the exact source port the request came from on every retry, consistent with prior sessions | `mitm/captures/BASEAPP_LOGIN_CAPTURE.txt` (unchanged pattern from prior sessions) |
| B | Does Mercury process it? | **UNKNOWN** — not distinguishable from general script/UI dispatch activity in the Stalker data (§4) | — |
| C | Rejected before handler dispatch? | **UNKNOWN** — same limitation | — |
| D | Reply-ID lookup performed? | **UNKNOWN** — same limitation | — |
| E | Reaches `LoginHandler::onLoginReply`? | **NOT CONFIRMED** — `logcat` still shows `Mercury::REASON_TIMER_EXPIRED` in every attempt this pass, identical to all prior passes | `logcat`, this pass and all prior |
| F | Generates traffic toward BaseApp `:25010`? | **NO** — confirmed zero `BASEAPP UDP RECV` entries, consistent with every prior session | `mitm/captures/BASEAPP_LOGIN_CAPTURE.txt` |

No claim of success is made for B–E: the task explicitly required runtime evidence of
actual handler execution, and none was obtained.

## 7. Concrete Next Steps (Not Attempted This Pass)

1. **Try Stalker's `compile` event type** (if supported for this NativeBridge
   configuration) instead of `call` — this event fires when Houdini/Stalker compiles a new
   block and, depending on how deeply Stalker can see into NativeBridge's own JIT (as
   opposed to just observing the x86_64 side), may expose the *original* ARM64 address
   being translated, which would directly solve the §4 attribution problem. Not tested in
   this pass — a materially different Stalker configuration than what was tried.
2. **Correlate `libtcb.so` cache growth over time**: snapshot `libtcb.so`'s written
   (dirty) memory region size/content before and after a login attempt; a newly-written
   region appearing exactly when `logOnBegin` fires would at least narrow down *where* in
   the cache the relevant translated code landed, even without full attribution.
3. **Repeat this exact experiment on genuine ARM64 hardware** (no NativeBridge) — every
   attribution difficulty in this document is specific to the translation layer; on real
   silicon, `libclient_arm64.so` addresses would be directly Stalkable/Interceptable and
   this whole class of problem disappears.

## 8. Summary Answers To The Deliverable's Required Points

1. **Stalker setup**: §1.
2. **Process/thread**: PID `16332`, TID `16424` (identified via `logcat` tagging).
3. **NativeBridge/JIT execution observed?** **Yes** — directly, via real call-target
   addresses resolving into `libhoudini.so` and `libtcb.so`.
4. **Executable/JIT ranges observed**: `libhoudini.so` (`0x76388e760000`-`0x76388edb7000`,
   `r-x`), `/system/lib64/arm64/nb/libtcb.so` (`0xd208000`-`0xd34e000`, `r-x`) — the latter
   newly identified as the JIT code cache.
5. **Login timeline**: §3, cross-referenced against real `logcat` timestamps.
6. **Relevant runtime execution around send/receive**: a reproducible burst of Houdini
   dispatch activity within ~1s of `logOnBegin`, tapering as code warms — §3/§4.
7. **Evidence of Mercury receive/dispatch specifically**: **not isolated** — the observed
   activity cannot be distinguished from general script/UI dispatch on the same thread.
8. **Evidence of the 32-bit reply ID**: **none obtained** — out of reach of call-summary
   granularity.
9. **Was `LoginHandler::onLoginReply` reached?** **Not confirmed.**
10. **Did BaseApp `:25010` receive anything?** **No.**
11. **Exact blockers**: (a) `onCallSummary` reports only translated x86_64 addresses, never
    the original ARM64 PC, making semantic attribution to specific `libclient.so` functions
    impossible at this granularity; (b) the two dominant hot addresses are generic Houdini
    dispatch machinery shared by all ARM64 execution on this thread, not Mercury-specific;
    (c) `libtcb.so`'s cache layout is runtime-dependent, so no static hook address can be
    computed in advance even though the region is now known to be genuinely executable.

## 9. 2026-09-14 (follow-up) — `compile` Events Tested, Same Attribution Gap Confirmed

A follow-up pass (`06_trace/MERCURY_STALKER_COMPILE_TRACE.md`) tested `events.compile`
specifically (the next concrete step named in §7 above) and confirmed it reports the
**same address space** as `call` events — no original ARM64 PC, no architecture tag. It
also found a second, larger (~62.5MB) anonymous `rwx` JIT heap adjacent to `libtcb.so`, and
**cleanly ruled out** a new alternative hypothesis (Mercury UDP I/O via Java's
`DatagramSocket`) via live `Java.perform()` hooks left active through a full confirmed
login attempt with zero invocations. `LoginHandler::onLoginReply` remains not observed to
execute, by any method tried across both Stalker passes.
