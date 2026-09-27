# Handoff — ROS_RE: fix the remaining reconnect-loop delay (crash + UI-skip already done)

Written for: Gemini, picking up this session's diagnostic work cold. Read `CLAUDE.md` in the repo
root first, especially **§0.12 (Checkpoint 30)** — that section is this handoff's full source
material; this file only summarizes it and gives you a prioritized next-steps list. Repo:
`C:\Users\Raysoo\Downloads\ROS_RE`, branch `master`, latest relevant commits: `54fa631c` (exact
cycle-count measurement), `cf91a373` (end-to-end success confirmation), `9f40f6c4` (crash fix +
Select Controls removal).

## 1. What's already fixed today — do not re-touch these without strong new evidence

- **The native SIGSEGV crash is fixed.** An earlier bad hand-computed bytecode patch (mid-function
  `JUMP_FORWARD` injected at the wrong offset in `entities/Athlete.py::enterHall()`) corrupted the
  interpreter stack and crashed `NeoXMain`. Replaced with a **1-byte-safe** fix: retargeting an
  *existing* `POP_JUMP_IF_FALSE` instruction's jump argument (113->103) instead of injecting new
  bytecode, reusing the function's own built-in `enterSelectModeFinished` skip path. Script:
  `scratch/apply_safe_lobby_patch.py`. Frozen working artifact:
  `scratch/candidates_cp30/patch_no_crash_no_selectcontrols.obb`.
- **The "Please select controls" screen and Character Creation UI are both gone**, safely, via the
  same patch (see CLAUDE.md §0.12.A/B for the exact bytecode-level reasoning).
- **A second, separate crash** (`AttributeError: 'NoneType' object has no attribute 'GetComponent'`
  in `_realEnterHall`, a scene-preload race) is also fixed — server-side only,
  `ROS_SCENE_LOAD_DELAY=10` (was `2.0`) gives the async scene load enough time before
  `_realEnterHall()` runs immediately (since skipping the UI countdown removed the ~10s buffer that
  used to hide this race).
- **The full flow now completes end to end**: PLAY -> loading -> Daily Claim -> Hall, verified live
  with screenshots (avatar, currency, full menu, START button, no crash, no overlay).

**Current known-good launch command:**
```
ROS_ATHLETE_USE_STREAM_FILE=1 ROS_AUTO_ENTER_HALL=1 ROS_BASE_NICKNAME="Dev | Raysoo" ROS_SCENE_LOAD_DELAY=10 python -u mitm/local_baseapp_capture.py
```
paired with `scratch/candidates_cp30/patch_no_crash_no_selectcontrols.obb` deployed as
`patch.1117219.com.netease.chiji.obb` on device (main OBB untouched, still the pristine `04_obb/`
copy).

## 2. What's still open: the pre-existing self-reconnect loop makes it SLOW, not broken

This is a **much older** issue (documented since CLAUDE.md §0.8, well before today's session) that
today's fixes did not cause and do not fix. The client repeatedly, silently reconnects
(new LoginApp handshake from a new ephemeral port) before finally landing on Daily Claim. It is no
longer a hard blocker (§1's fixes mean it *does* eventually complete), but it makes every launch
take minutes instead of seconds, which is the actual UX problem left to solve.

### Hard data from one fully-instrumented run today (§0.12.G) — READ THIS BEFORE THEORIZING

| Event | Timestamp | Interval from previous |
|---|---|---|
| PLAY tapped | 18:55:48.790 | -- |
| Cycle 1 handshake | 18:55:49.565 | 0.775s after PLAY |
| Cycle 2 handshake | 18:56:55.080 | **65.515s** |
| Cycle 3 handshake | 18:57:44.426 | **49.346s** |
| Cycle 4 handshake | 18:58:30.192 | **45.766s** |
| Cycle 5 handshake | 18:59:10.942 | **40.750s** |
| Daily Claim visible | ~19:00:37-40 | within ~1m25s of cycle 5 |

**Exactly 5 cycles, ~4m51s total.** Every cycle's *server-side* chain (`createBasePlayer` through
`STAGE 5`/`enterHall`/`onShowSignedPanel`) completed cleanly in 1-11 seconds, every single time —
the server is never the bottleneck. The entire delay is client-side silence between cycles.

**The critical new observation, not previously known**: the inter-cycle interval **shrinks every
cycle** (65.5s -> 49.3s -> 45.8s -> 40.8s), a clean monotonic decrease. This is NOT consistent with
a simple fixed-duration socket-inactivity watchdog (which would produce roughly constant
intervals). It looks like each cycle does real, cumulative progress — e.g. a scene/asset cache
that's progressively more "warm," so each successive scene-load attempt has less work left and
therefore stalls the client's network thread for less time before either finishing or hitting
whatever internal condition triggers the next reconnect.

**This reframes the whole problem.** The fix target may not be "stop the client from
reconnecting" — it may be **"why is cycle 1's scene-load so much slower than cycle 5's, and can
that gap be closed or front-loaded?"** If the client is progressively warming some cache across
attempts, forcing it to do that warming *once*, up front (e.g. before the first `enterHall` is even
sent, or via a different bootstrap sequencing), could collapse 5 cycles into 1.

## 3. Your task — READ-ONLY investigation first, in this priority order

**Do not patch APK/smali/script.npk without independently verifying byte-for-byte what you're
changing first** (see §1 — the crash this session fixed came from exactly this mistake:
a hand-computed offset that wasn't checked against live disassembly). **Do not use Frida Stalker,
do not write process memory, do not force/fake session state, do not bypass authentication.**

### Priority A — Confirm or disprove the "decreasing interval" pattern (2-3 more repeat runs)

Only one run has this data so far. Repeat the exact same measurement (continuous server log,
count every 273-byte LoginApp handshake, note timestamps, confirm when Daily Claim visually
appears) 2-3 more times. Report:
- Does the cycle count stay near 5, or vary?
- Does the interval keep shrinking every time, or was this run's pattern coincidental?
- Is there a consistent floor (e.g. does it always bottom out around ~40s, or keep shrinking
  further on longer runs)?

### Priority B — Identify what's actually happening client-side during the silence gaps

This project has tried and failed to pin this down purely from server-side logs before
(CLAUDE.md §0.9-§0.11). What's new and worth trying now:
- **`<SCRIPT>` logcat channel** (tag `<SCRIPT>`, see CLAUDE.md §0.4.F): watch continuously during
  a live reconnect-loop run for any traceback, warning, or print that correlates with when a
  cycle's silence begins or ends. This is free, already-proven-useful observability with zero
  Frida setup.
- **Thread/CPU sampling** (`top -H -b -n 1 -p <pid>`, `/proc/<pid>/task/<tid>/{status,wchan,stat}`,
  non-destructive `debuggerd -b`) during one silence window, ideally comparing an EARLY cycle's
  silence window against a LATE cycle's — if the "warming cache" hypothesis is right, you should
  see the same thread (likely `NeoXMain`) busy for a long time on an early cycle and busy for a
  much shorter time on a late cycle, doing conceptually the same work.
- **Frida, Java-layer only** (reuse patterns from `scratch/frida_*.py`, already proven working
  this project): if thread sampling shows `NeoXMain` busy (not blocked) during the silence, that's
  native/script code, not obviously Frida-Java-hookable — but if it's the MPay/session layer
  retrying independently of scene load, the existing `frida_loginfo_save_trace.py` hook patterns
  (session load/save, LoginInfo) could reveal it. Try thread sampling first — it's cheaper and
  already has proven value this project.

### Priority C — Check what's cached/persisted across cycles within one process lifetime

Since all 5 cycles happen within the *same client process* (same PID, never restarts) but from new
UDP ports each time, anything that's an in-process cache (not written to disk) would naturally
explain "warms up across cycles but resets on a fresh app launch." Look for:
- Whether `Athlete.showSelectCharacter([])`'s scene-preload (`_loadDefaultScene()`,
  `HALL_BASE_SCENE`) is being re-triggered on every cycle or only once (the server's own
  `_scene_preloaded_hosts` guard, per `local_baseapp_capture.py`, already tries to only send it
  once per host — verify client-side whether repeated `enterHall` calls also re-run scene
  construction work redundantly, independent of whether the server resent the RPC).
- Whether asset/texture loading for the Hall scene has any obvious warm-cache behavior
  (first-load-slow, subsequent-loads-fast) that's a known engine characteristic rather than
  something server-controllable at all.

### Priority D — Static analysis, if A-C don't explain it

Search decrypted client scripts (`tools/script_index.py`/`script_query.py`/`script_disas.py` over
`04_obb/extracted/script.npk`) for cache/warm-related terms in `entities/Athlete.py` and whatever
scene-loading module `_loadDefaultScene`/`loadHallScene` belongs to (per CLAUDE.md §6.B/§7).

## 4. Report format

Use exactly: `CONFIRMED / REPRODUCED / DISPROVEN / HYPOTHESIS / NOT YET TESTED`. Specifically
answer:
1. Does the decreasing-interval pattern reproduce across repeat runs?
2. What is `NeoXMain` (or whichever thread is actually responsible) doing during an early-cycle
   silence window vs. a late-cycle one — busy-spinning, blocked, or something else?
3. Is there evidence of a warming cache/progressive-completion mechanism, and if so, what
   specifically is it?
4. What is the strongest concrete next fix target, given the above?

Do not report a hypothesis as confirmed. Update `CLAUDE.md` §0.12 (add a new lettered subsection,
don't rewrite existing ones) with whatever you find, and commit with a clear message, same as this
session's own commits (`9f40f6c4`, `cf91a373`, `54fa631c` are good examples of the expected
granularity/style).
