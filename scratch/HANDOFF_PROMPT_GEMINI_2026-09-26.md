# Handoff — ROS_RE: Invalid-Login/MPay retry loop + post-login reconnect investigation

Written for: Gemini, picking up this session's diagnostic work cold, with no shared conversation
history with the previous (Claude) session. This file replaces an older, now-obsolete handoff of
the same filename (that one was about the since-fully-reverted EmailAuthActivity/Supabase work —
ignore anything you might recall or find elsewhere about that; it is dead history, see §4 below).

## 1. Project context

Repo: `C:\Users\Raysoo\Downloads\ROS_RE`, branch `master`. Private-server
reverse-engineering/emulation project for the Android game **Rules of Survival**
(`com.netease.chiji`, v1.610377.506841, vCode 1117219, arm64-v8a), running on **LDPlayer 9**
(`emulator-5554`) against a fully local Python server (`mitm/local_baseapp_capture.py`). **Local/
offline only — never interact with real NetEase production servers.** Read `CLAUDE.md` in the repo
root first; it is the authoritative, continuously-updated project doc. This handoff summarizes
sections §0.7 through §0.11 (all written 2026-09-26, today) — read those sections directly for full
detail, exact log excerpts, and file paths; this document is a guide to what's already known, not a
replacement for it.

Latest relevant commits (newest first): `bab71176` (forensic audit + WebView panel finding),
`97995d36` (client-silence-before-reconnect finding), `3a39f1cf` (90s-reconnect root cause),
`f9f63dd2` (Candidate B A/B isolation result).

User communicates in Taglish, is hands-on (runs the emulator themselves, watches the screen,
reports back in real time), and has repeatedly corrected over-eager conclusions this session (e.g.
"the WebView panel is not the root cause, it appears in both failing and succeeding cycles" — see
§7). Treat their live observations as ground truth that must match the log analysis, not the other
way around.

## 2. Current verified environment (CONFIRMED via full read-only forensic audit, today)

- **Candidate B is installed and hash-matched.** SHA256
  `27bebaceb9f1e97759aa184849af14b7d51bbdcccb860e83162158ce8f7cc590`, frozen copy at
  `scratch/candidates/candidate_B_known_good.apk`. Candidate B = pre-EmailAuth guest-only baseline
  + `ui/g.smali` `MpayActivity` `finish()` patch ONLY + **no** `MpayWatcherService`. This is the
  frozen, do-not-overwrite baseline for all further experiments.
- **EmailAuthActivity: NOT PRESENT** — zero matches in `classes.dex`/`classes2.dex`/`classes3.dex`,
  no manifest entry; `com.netease.neox.Launcher` is the sole `LAUNCHER`.
- **Supabase: STALE FILE ONLY, INACTIVE** — `mitm/local_baseapp_capture.py` still has a
  `try: import supabase_db / except: supabase_db = None` guard and a few `if supabase_db:` blocks,
  but `mitm/supabase_db.py` was deleted (Checkpoint 28 revert), so the import always fails and every
  guarded block is permanently dead code. No SUPABASE env vars set.
- **MpayWatcherService: NOT PRESENT** — no dex match, no manifest `<service>`, no accessibility
  declaration.
- **Playit.gg: ACTIVE on the Windows host (4 processes) but CONFIRMED NOT in the game's packet
  path.** LDPlayer's `iptables -t nat -L OUTPUT` DNATs all relevant ports straight to
  `172.16.1.2:80/443/8443/25000/20013` (the Windows host running the local server) — no Playit
  hostname or address anywhere. Playit's only network activity is 2 established HTTPS connections
  to its own cloud relay (control-plane only); no listener on any ROS port. Stopped for the Phase
  10 control run anyway, purely to eliminate background-resource noise, per project owner's
  request — not because it was implicated.
- **Server processes: exactly one** — `python.exe -u mitm/local_baseapp_capture.py`, no separate
  auth proxy, no tunnel bridge.
- No stale DNAT/portproxy/DNS-bypass residue found (one harmless `adb forward tcp:27042→27042`
  left over from earlier Frida tooling — this is actually still useful, see §9).

**Conclusion: the environment is clean. Nothing found in this audit explains the symptoms below —
do not spend time re-auditing Supabase/Playit/EmailAuth residue unless new evidence specifically
points back to one of them.**

## 3. Current observed user flow (verbatim shape, confirmed reproducible)

```
Launch
→ White screen
→ NetEase logo
→ "Checking for Updates" / patch-loading splash (same screen serves both — no distinct
   visual state was found between these two labels)
→ "Invalid login. Please log in again." dialog (AlertDialog, real Android widget)
→ Confirm tap
→ small loading
→ white in-engine WebView-like panel (see §7 — NOT yet proven causal)
→ Title page
→ PLAY tap
→ "Invalid login" appears again
→ Confirm tap
→ small loading
→ WebView panel again
→ MPay/MpayActivity cycles repeat, sometimes many times (see §5 — up to 24 cycles/~8 min
   observed in one run)
→ eventually a real LoginApp network handshake succeeds
→ "Please select controls" (Select Controls)
→ Confirm button has a countdown (~10s, matches a previously-documented fixed timer)
→ Confirm tap
→ slow loading (see §6 — this is where the client silently stops servicing its BaseApp socket)
→ ~88-90s later: a full second LoginApp/BaseApp handshake + second createBasePlayer cycle fires
  automatically, client-side-triggered
→ Daily Claim panel / Hall, OR (observed once) a full Character Creation prompt with a
  Tap-to-Enter-NAME field and an apparently unresponsive CREATE button
```

## 4. Corrections already proven this session — do not re-litigate these

- **App CMD 20 = "Show Virtual Keyboard"** (confirmed via Ghidra decompile of
  `FUN_01cf2b78`/case `0x14`, and via live IME dumpsys showing it never touches Android's real
  IME). **CMD 20 is NOT causal** for any stuck-loading symptom — it fires identically on both
  healthy and (formerly) stuck runs.
- **The `ui/g.smali` `MpayActivity.finish()` patch, in isolation, is NOT the cause of any permanent
  stuck-loading regression** — Candidate B (which has only this patch) reaches the full Hall
  reliably. This ruled out an earlier hypothesis that automatic-vs-manual `finish()` timing caused
  a lifecycle race.
- **"Dev | Raysoo" (the nickname visible in Hall/character-creation screens) is NOT a login-success
  marker.** It is purely a hardcoded value from **our own server's** `ROS_BASE_NICKNAME` env var
  (default `'Dev | Raysoo'`), sent via `Athlete.updateBaseNickname` — the 4th of 5 fixed,
  unconditional RPCs in `local_baseapp_capture.py`'s `createBasePlayer` chain (see §8). It appeared
  identically in both a first-success cycle and a reconnect cycle 90s later. **Do not treat its
  appearance as revealing any client-side state transition.**
- **The white in-engine WebView-like panel (§7) is NOT yet proven causal.** It appears during
  *both* failing/retrying login cycles and the eventually-successful one. The project owner
  explicitly corrected an earlier over-eager conclusion that this panel was the root cause — it is
  a secondary UI element present throughout, not (yet) shown to gate anything.
- **Fast-vs-slow Confirm-tap timing is NOT a reliable explanation** for whether the Invalid Login
  dialog repeats. Multiple controlled tests this session contradicted a simple "fast dismiss avoids
  the loop" rule (one run: a 47s-delayed tap did NOT trigger a repeat; another run: an
  immediate/fast tap triggered an 8-cycle retry burst). See §5 for what actually seems to matter.
- **Playit is NOT in the current game traffic path** (§2) and **Supabase/EmailAuth residue is NOT
  contaminating Candidate B** (§2) — both explicitly ruled out by forensic audit, not assumption.

## 5. PRE-LOGIN major finding: most "Invalid Login" cycles never reach the network at all

From a single clean Candidate B launch (`scratch/phase10_run1/`), every `MpayActivity (has extras)`
Android `START` event in `logcat.txt` was extracted and compared against every genuine 273-byte
`LOGINAPP UDP RECV` in `server.log`:

- **24 MpayActivity START cycles** occurred over **~8 minutes** (21:38:19.948 → 21:46:26.372).
- **Only ONE real LoginApp handshake packet ever reached the server**, at **21:46:53.197** —
  immediately after the *last* MpayActivity cycle in that burst.
- **The other ~22-23 cycles produced zero server-visible network traffic.** The server never saw
  them at all.

**CONFIRMED**: the repeated "Invalid login" behavior is overwhelmingly an **MPay-SDK-internal /
client-local phenomenon** — the client is re-checking something in its own local/cached session
state and failing *before* ever attempting a real network login, for the vast majority of cycles.
**UNKNOWN / NOT YET TESTED**: what specific internal condition (retry counter reaching a
threshold, a cache-expiry timer, a callback result finally flipping, or something tied to the
WebView panel's own load completion) causes the client to eventually attempt one real network
LoginApp handshake after so many silent local cycles. This is the #1 open question for you to
investigate (see §10, Priority A).

## 6. POST-LOGIN major finding: the client goes silent ~64s before a ~88-90s self-reconnect

Independent of §5, **after** a LoginApp/BaseApp session has already succeeded and `enterHall` has
already fired, the client reliably reconnects from scratch:

- Two independent measurements so far: **90.018s** (first run, `scratch/timeline_run1/`) and
  **87.975s** (second run, `scratch/phase10_run1/`) between the first successful LoginApp handshake
  and a second, brand-new LoginApp handshake from a new ephemeral port. **CONFIRMED reproducible
  twice**, ~88-90s, ~2s variance.
- Deeper log analysis (`scratch/timeline_run1/server.log`) found the **client's last packet on the
  original session arrives at 21:09:53.557**, then **nothing at all for 63.997 seconds**, until the
  reconnect. This 64s silence begins almost exactly when the first post-Confirm "slow loading"
  screen starts.
- **DISPROVEN**: "a missing periodic server response causes the reconnect." The server's own
  `setGameTime` keepalive to the correct, still-open port **never stops** — confirmed sent
  continuously even 10 minutes past the reconnect, to a now-abandoned port. The server was never
  the problem; nothing was missing on its side.
- **HYPOTHESIS, favored but NOT CONFIRMED**: a client-side socket-inactivity watchdog (order of
  ~60-65s) fires because the client's own main thread is starved during a long synchronous
  scene-load operation — the same one responsible for the "slow first loading" symptom. This would
  mean the "slow loading" and "duplicate/reconnect" symptoms are **one root cause, not two**. Not
  yet confirmed at the code level; needs either (a) static analysis of the actual timeout constant,
  or (b) thread/CPU sampling during the silence window (partially done already, see
  `scratch/cp29_thread_snapshots.txt`/`cp29_proc_detail.txt` from an earlier, separate stuck-state
  investigation — re-run fresh during an actual §6 silence window for a clean comparison, since
  those were captured under a different, now-superseded regression state).

**Keep §5 and §6 as separate questions unless you find direct evidence linking them.** They were
investigated independently and nothing so far proves they share a mechanism, even though both
involve "the client goes quiet, then reconnects."

## 7. New, not-yet-explained UI element: an in-engine WebView-like panel

A full-width white panel with a dark left sidebar, an **X** close button top-left, and an
indefinite spinning loader appears **immediately after every Confirm tap** on the Invalid Login
dialog — during patch-loading, and again after PLAY/title. `dumpsys activity activities` confirms
`mResumedActivity` stays on `com.netease.neox.Client` the whole time it's visible — **this is an
in-engine overlay (likely a Cocos2d/NeoX-internal WebView widget), not a separate Android
Activity**. Usually it closes itself quickly; at least once it was observed stuck indefinitely,
with `MpayActivity` still cycling in the background during the stall. **Not yet identified**: the
exact View/widget class, what URL/content it loads, or what callback closes it. Per §4, do not
assume it's causal — investigate it as a secondary/parallel element, not the primary suspect.

## 8. Known-working server bootstrap chain (for reference — this part is solid, not in question)

Every successful `createBasePlayer` cycle (both the first login and every ~90s reconnect) follows
this exact, unconditional 5-6-step sequence, sent by `mitm/local_baseapp_capture.py`:

```
createBasePlayer(Account, type=38, eid=1)
createBasePlayer(Athlete, type=51, eid=1, stream=5771 B)
Athlete.showSelectCharacter([])            idx=1083
Athlete.onCreateCharacter(ret=1, reason="") idx=1084
Athlete.onRoleCreateSuc(10002)              idx=1085
Athlete.updateBaseCharacter(10002)          idx=1087
Athlete.updateBaseNickname('Dev | Raysoo')  idx=1088   <- server-side ROS_BASE_NICKNAME, not a state signal
Athlete.enterHall(True)                     idx=1091
```

This chain completes in ~5-6 seconds server-side every single time it's triggered — it is never
the bottleneck. Don't waste time re-verifying this sequence; it's solid.

## 9. Reusable tooling already in the repo

- **Frida is set up and working**: `frida-server-x64-1621` is running on-device as root (confirmed
  live, PID varies per boot — check with `adb shell su -c 'ps -A | grep frida'`), reachable via
  `adb forward tcp:27042 tcp:27042` (already active). Existing scripts in `scratch/frida_*.py`
  (from Checkpoints 22/23/26) already have working hook patterns for exactly the MPay classes you
  need — **read `scratch/frida_loginfo_save_trace.py` first**, it already hooks:
  - `com.netease.mpay.oversea.j.d.d.g()` — session **load** (returns `null` or a `LoginInfo` with
    `.a` = uid, `.f` = type)
  - `com.netease.mpay.oversea.j.d.d.a(LoginInfo)` — session **save**
  - `com.netease.mpay.oversea.j.b.b.a(LoginInfo)` / `.b(LoginInfo)` — in-memory session cache
    create/update
  - `scratch/frida_final_trace.py` hooks `com.netease.mpay.oversea.ui.HandlerFactory.a` (all
    overloads) with a stack trace — useful for finding the MPay→NeoX handoff point (§10 Task 1/3).
  - **Verify every class/method name against the live, installed Candidate B APK before hooking**
    — do not assume Checkpoint 22/23's obfuscated names (`j.d.d`, `j.b.b`, `ui.HandlerFactory`,
    etc.) are still accurate for this exact build without checking
    `Java.use(cls).class.getDeclaredMethods()`/`getDeclaredFields()` live first. CLAUDE.md's own
    Checkpoint 26 notes flag this as a real, previously-hit gotcha (stale-vs-live obfuscation
    mismatches).
  - **Attach by PID, not by spawning fresh** if you want to observe an already-running retry loop
    live (`device.attach(pid)` after `adb shell pidof com.netease.chiji`) — spawning
    (`device.spawn([PKG])`) launches via the current `LAUNCHER` (`neox.Launcher`) from scratch,
    which is fine for a clean-run capture but won't let you catch an in-progress loop.
- **Timeline/screenshot harness pattern** (PowerShell, NOT Bash — Bash mangles `/sdcard/...` device
  paths, a repeatedly-hit gotcha this session): start continuous `adb logcat -v threadtime` FIRST,
  then a 1s-interval PowerShell screenshot loop SECOND, both running in background BEFORE
  `adb shell monkey -p com.netease.chiji -c android.intent.category.LAUNCHER 1`. See
  `scratch/timeline_run2/` and `scratch/phase10_run1/` for exact working scripts/output structure
  to copy.
- **Ghidra project** already analyzed at `scratch/ghidra_project/ROS_RE.gpr`; run new scripts via
  `scratch/run_ghidra_script.bat <Script.java> <output.log>`. Useful for §10 Priority D (static
  analysis for timeout constants) if the Java-layer search comes up empty.

## 10. Your next task (Gemini) — READ-ONLY diagnostics first, in priority order

**Do NOT patch the APK/smali. Do NOT modify Frida-hooked return values, write process memory,
alter SharedPreferences, inject/fabricate sessions, force login success, bypass authentication, or
use Frida Stalker. Do NOT change server keepalive/timing yet. Do NOT reintroduce
EmailAuthActivity/Supabase/MpayWatcherService. Do NOT use Playit for the local diagnostic path. Do
NOT touch unrelated Store/Supply/Hall gameplay systems. This phase is measurement only.**

### Priority A — Java-layer Frida tracing: failed cycle vs. the one that succeeds

Using the existing hook patterns (§9), trace **every** MpayActivity cycle in one continuous capture
and record, per cycle:

```
cycle_number, timestamp, onCreate/onResume/onPause/onDestroy,
callback_invoked, callback_result,
session_present (yes/no), login_type/auth_type,
account_id_present (yes/no), token_present (yes/no),
token_len_or_sha256_prefix_ONLY (never print raw token contents),
retry_counter (if discoverable), next_retry_delay (if discoverable)
```

Then specifically find: **the exact method/callback that hands control from MPay's local session
logic to NeoX's LoginApp network connection** — i.e. the first function call that actually causes
the 273-byte UDP packet to be constructed and sent. `HandlerFactory.a` (all overloads, per
`frida_final_trace.py`) is a promising starting point; trace forward from there.

Produce a diff table (session state / login type / auth type / account id / token presence /
retry count / callback result / handoff callback / network send) between a **failed internal
cycle** and the **final cycle that actually produces network traffic**. Find the **first** value
that differs — that's the real answer to §5's open question.

### Priority B — Repeat runs (2-3) to confirm reproducibility

For each run, using the harness pattern from §9, report:
- number of MPay cycles before the first real LoginApp packet
- time from first MpayActivity to that LoginApp handshake
- the ~88-90s reconnect interval (does it reproduce again?)
- the ~64s client-silence duration before that reconnect
- whether the slow first loading aligns with when BaseApp traffic actually stops (correlate
  against your Frida trace's timestamps, not just the logcat/server.log timestamps used so far)

### Priority C — Thread/CPU state during the slow loading window

During one of the "slow loading" episodes (after Select Controls Confirm, or during the §6 silence
window), capture non-destructively:
- `NeoXMain` and `NeoXRender` CPU%/state (`top -H -b -n 1 -p <pid>`)
- Android UI thread and any network/socket-related thread
- `/proc/<pid>/task/<tid>/{status,wchan,stat}` for each
- a non-destructive native backtrace (`su -c 'debuggerd -b <tid>'`) if useful

(Earlier, unrelated-regression-era captures exist at `scratch/cp29_thread_snapshots.txt` etc. —
useful as a methodology reference, but re-capture fresh under the *current* Candidate B state
rather than relying on those old snapshots, since they were taken under a different, since-reverted
build combination.)

### Priority D — Static analysis, if A-C don't pin down the exact constant

Search decrypted client scripts (`tools/script_index.py`/`script_query.py`/`script_disas.py` over
`04_obb/extracted/script.npk`) and/or `libclient_arm64.so` (via Ghidra, §9) for: `90`, `90000`,
`60`, `60000`, `reconnect`, `timeout`, `heartbeat`, `socket inactivity`, `relogin`, `LoginApp
retry`, and the scene-loading call path that runs immediately after Select Controls' Confirm is
pressed.

## 11. Report format — use exactly these labels, and answer these questions

```
CONFIRMED / REPRODUCED / DISPROVEN / HYPOTHESIS / NOT YET TESTED
```

A. What exact state changes on the final MPay cycle, immediately before the first real LoginApp
   packet?
B. What exact method hands control from MPay to NeoX/LoginApp?
C. Is a retry-count/backoff threshold involved?
D. Is session/token presence or type changing between failed and successful cycles?
E. Does the ~88-90s reconnect reproduce again in your new runs?
F. Which thread/function becomes abnormal (busy-spinning, blocked, or simply idle-but-not-
   servicing-network) during the slow loading window?
G. What is the strongest next concrete fix target, given everything above?

Do not report a hypothesis as confirmed. Then stop — no fixes yet, per the strict-don'ts in §10.
