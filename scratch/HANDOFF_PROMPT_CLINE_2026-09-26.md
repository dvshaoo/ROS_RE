# Handoff to Cline — "Link Account" Nag Popup / Native Channel Timing (Checkpoint 26 follow-up)

> **STATUS (2026-09-26, continued by Cline → Checkpoint 27):** the trigger chain is found and
> documented in `CLAUDE.md` §0.4. In short: the popup is `UILogin.showGuestAccountRemind`, invoked
> only from `ChannelHelper.onLoginSucceed` via
> `Globals.uiMgr.UILogin.exceptionHandleFunc('showGuestAccountRemind')`; the gate needs
> `Globals.market_record_points.cur_market_record_point['first_download_login_game']` to be falsy, and
> the 24 h suppression window lives in `market_record_point_<uuid>.txt` — a file that is **never
> written in this environment** (`MarketRecordPoints.get_uuid()` returns `''`, and all four record
> functions early-return on that), so the nag re-arms on every launch. §3's Hypothesis A had the right
> function but the wrong "live" condition, and §4's native-channel angle is not on the critical path.
> §6 item 1 (fix the Frida native hook) is only needed for the one remaining measurement, described at
> the end of §0.4 E.

## Summary for Cline

You are taking over from Claude Code on the Rules of Survival (ROS Android `com.netease.chiji`,
LDPlayer 9 `emulator-5554`) private server emulation project. The email+password auth flow
(`EmailAuthActivity`) works end-to-end and is **committed and currently installed on the device** —
do not touch that part unless it breaks. The remaining open problem is a **UI nag popup** that
should not be appearing, plus a related stuck-loading-spinner symptom. Both are believed to share
one root cause that has **not yet been found**.

**Read `CLAUDE.md` first** (project root) for full standing context — environment setup, the
Checkpoint 25/26 history, and the "Do not re-attempt" list of previously-rejected approaches.

---

## 1. Current Known-Good State (do not regress this)

- Git HEAD: commit `5dd27251` ("fix: EmailAuthActivity saved session before GameConfig appId was
  set") — this is what's currently built, signed, and `adb install -r`'d onto `emulator-5554`.
- `local_baseapp_capture.py` and `mitm_serve.py` should be running in the background (check with
  `grep KEYSCAN scratch/server_stdout.log` for a recent `SUCCESS`; restart if stale).
- End-to-end verified working: `EmailAuthActivity` (LAUNCHER activity) shows a Sign-in dialog ->
  POSTs to `/custom/auth/login` (checked against Supabase) -> on success, starts
  `com.netease.neox.Launcher`, polls `GameConfig.q()` until the SDK's real appId ("123") is
  available, THEN saves the MPay session via reflection (`j.a.f$a` -> `j.d.d`). This ordering fix
  is what resolved the earlier "account login failed" dialog (Checkpoint 26, see CLAUDE.md).
- Test account that's known to work: `paleraciojoey68@gmail.com` / `C@lina2004` (real Supabase
  account, already has a saved session).
- To relaunch clean and log in via adb (useful for repro):
  ```
  "C:\LDPlayer\LDPlayer9\adb.exe" -s emulator-5554 shell am force-stop com.netease.chiji
  "C:\LDPlayer\LDPlayer9\adb.exe" -s emulator-5554 shell monkey -p com.netease.chiji -c android.intent.category.LAUNCHER 1
  :: wait ~2s for the Sign-in dialog, then:
  "C:\LDPlayer\LDPlayer9\adb.exe" -s emulator-5554 shell input tap 960 528
  "C:\LDPlayer\LDPlayer9\adb.exe" -s emulator-5554 shell input text "paleraciojoey68@gmail.com"
  "C:\LDPlayer\LDPlayer9\adb.exe" -s emulator-5554 shell input tap 960 662
  "C:\LDPlayer\LDPlayer9\adb.exe" -s emulator-5554 shell input text "C@lina2004"
  "C:\LDPlayer\LDPlayer9\adb.exe" -s emulator-5554 shell input tap 1400 863
  :: then wait ~40-50s for the patched loading screen to finish and reach the title screen.
  ```

---

## 2. The Open Problem

After a fully successful login (real Supabase account, no errors), the title screen shows a
native-looking **"Link Account"** popup every single time:

> You are using a guest account and will lose all account data if you delete the game. We
> recommend linking your account now to protect your data. You will receive a reward of 1,000
> Gold for the first time linking your account.
> [Not Now] [Link Now]

The user (project owner) explicitly does **not** want this auto-dismissed (already rejected that
as "not a real fix", same standing objection as the earlier `login_expired` auto-tap approach —
see CLAUDE.md's "Do not re-attempt" list). They want the actual root cause found and fixed, or the
popup's trigger condition genuinely resolved so it never fires.

**A second, related symptom**: tapping "Link Now" opens some kind of window that dismisses itself
almost immediately (user-reported, not yet screen-recorded). This is now understood (see §4) — the
native `guest_bind` handler is almost certainly calling into an account-linking backend flow this
project has never implemented server-side, so it fails closed immediately. Not yet fully confirmed
live, but very likely a symptom of the same "no real linking backend" gap rather than a separate bug.

**A third, currently-unconfirmed-as-connected symptom**: during the "patched" loading segment
(before the title screen), a small centered loading spinner sometimes appears that in earlier
checkpoints (24/25) was tied to a *different, already-fixed* stuck-`MpayActivity`-overlay bug
(auto-recovered by `MpayWatcherService`'s accessibility-service BACK-press). Whether the spinner
seen *this session* is that already-solved issue re-manifesting, or a new/different stall, is
**not confirmed** — don't assume they're the same thing without checking `MpayWatcherService` is
actually enabled and firing (`adb logcat` for `performGlobalAction(BACK)`).

---

## 3. What WAS Investigated and Ruled Out This Session

**Hypothesis A (WRONG, ruled out): "first_download_login_game" flag semantics.**
Traced the Python UI script `ui/UILogin.py`'s `showGuestAccountRemind` function (disassembled via
`tools/script_disas.py "ui/UILogin.py" showGuestAccountRemind` — see §5 for tooling). Its logic:
```
if Globals.channel:
  if Globals.market_record_points:
    if not cur_market_record_point.get('first_download_login_game', True):   # default True -> skip
      last_remind_time = cur_market_record_point.get('last_remind_time', 0)
      need_remind = True if last_remind_time == 0 else (time.time() - last_remind_time > 86400)
      if Globals.channel.name == 'netease_global' and Globals.channel.get_auth_type() == 2 and need_remind:
        Globals.uiMgr.enter_ui('UIGuestAccountRemind')
        ...persist last_remind_time...
else:
  cur_market_record_point['first_download_login_game'] = False
  ...persist...
```
`get_auth_type() == 2` matches the `GUEST` enum ordinal (confirmed earlier via
`com.netease.mpay.oversea.j.a.g` — GUEST's `a()` returns 2). Since our account is intentionally
kept as MPay type=GUEST (required for BaseApp wire-protocol uid compatibility — **do not change
this**, see CLAUDE.md's Checkpoint 25 architecture notes), this check will always evaluate true
*if reached*. The real question was always **why the `first_download_login_game` gate opens at
all** (it defaults to `True`, i.e. skip, unless explicitly flipped to `False`) — the only write site
found in this function is the `if not Globals.channel:` branch. This led to a timing theory:

**Hypothesis B (WRONG, tested and disproven): main-thread contention in `EmailAuthActivity`.**
Theorized that `EmailAuthActivity`'s post-login polling loop (`Handler(getMainLooper())`
re-posting every 200ms while `com.netease.neox.Launcher` — sharing the same process/main thread —
was also trying to initialize) was starving Launcher's native init, leaving `Globals.channel`
falsy long enough for the above branch to fire. **Implemented and tested this fix** (moved the
session-save polling to a plain background `Thread` instead of a main-thread `Handler` loop,
plus moved the `su` accessibility-enable shell-out off the main thread too) — **the popup still
appeared after this fix**. This hypothesis is therefore likely wrong, or at best incomplete. The
code for this attempt was **reverted** (not committed) after it failed to fix the issue — do not
re-attempt this exact change without new evidence it's on the right track.

**Channel bundle discovery (context, not yet conclusively tied to the bug):** `script.npk` only
bundles `helpers/game_sdk/sdk_base.py`, `sdk_const.py`, and `sdk_nearme_vivo.py` — there is **no**
`sdk_netease_global.py` module in the actual asset bundle this client uses, even though
`showGuestAccountRemind` checks `Globals.channel.name == 'netease_global'`. This *might* mean
`Globals.channel` isn't sourced from the `helpers.game_sdk.sdk_*` Python mechanism at all for the
`.name`/`.get_auth_type()` properties used here (see §4) — or it might mean nothing (the
`nearme_vivo` channel could just be an artifact of this OBB's build target and coexist fine with a
natively-hardcoded "netease_global" display name). Not resolved.

---

## 4. Key New Finding: `Globals.channel` Is a NATIVE Object, Not a Script Class

This is the most concrete lead from this session, found via **Ghidra static analysis of
`libclient_arm64.so`** (the game's native engine library, NOT the `com.netease.mpay.oversea.*`
Android/Java SDK we'd been analyzing before — this is a different binary, the actual NeoX/BigWorld
engine).

Searched `libclient_arm64.so` for the exact string `"get_auth_type"` (the method name
`Globals.channel.get_auth_type()` calls) and found it **exactly once**, at `0x02b3c3a6`, referenced
from a **data-only xref** at `0x03a1a640` — i.e. a static table entry, not code. Dumping the raw
8-byte words around that address revealed a classic **`PyMethodDef`-style table** (the standard
CPython C-extension method registration pattern: `{name_ptr, func_ptr, flags, doc_ptr}` per entry,
repeating every 32 bytes):

```
03a1a5c0: "open_manager"          -> FUN_00973ec0
03a1a5e0: "get_announcement_info" -> FUN_00973ef4
03a1a600: "display_achievement"   -> FUN_00973f28
03a1a620: "update_achievement"    -> FUN_00973f5c
03a1a640: "get_auth_type"         -> FUN_00973ffc   <-- Globals.channel.get_auth_type()
03a1a660: "get_auth_type_name"    -> FUN_00974020
03a1a680: "exit_app"              -> FUN_009740c4
03a1a6a0: "guest_bind"            -> FUN_009740f8   <-- the "Link Now" button's actual handler!
```

This **confirms `Globals.channel` is a native C++ object** exposed to the Python script VM via a
PyMethodDef table, not a pure-Python class from `script.npk`. This also explains the
"Link Now dismisses immediately" symptom: `guest_bind`'s decompile is trivial —
```c
void FUN_009740f8(long param_1) {
    (**(code **)(**(long **)(param_1 + 0x10) + 0x118))();   // one vtable dispatch, fire-and-forget
    *(long *)PTR_DAT_03a16aa0 = *(long *)PTR_DAT_03a16aa0 + 1;  // increments some global counter
    return;
}
```
It just fires a single vtable call into some other native subsystem (likely the actual account-link
UI/network flow) and returns immediately — if that downstream flow fails fast (e.g. hits an
endpoint this project's `mitm_serve.py` doesn't implement, or expects a real NetEase account-link
backend that doesn't exist here), the dismiss-immediately behavior is exactly what you'd expect.

`get_auth_type` itself (`FUN_00973ffc`) is equally trivial:
```c
void FUN_00973ffc(long param_1) {
    iVar1 = (**(code **)(**(long **)(param_1 + 0x10) + 0x128))();  // vtable dispatch, no null-check
    FUN_01e07064((long)iVar1);   // presumably int -> PyObject conversion
    return;
}
```
**No readiness gate of any kind** — it unconditionally dereferences `*(param_1+0x10)` (an inner
vtable pointer) and calls through it. If that pointer were null/uninitialized this would crash, not
misbehave silently — so if this function is genuinely being called before the underlying SDK
bridge is ready, either (a) it doesn't crash because the pointer is already valid quite early
(pointing to a not-yet-fully-configured-but-non-null implementation), or (b) this isn't the
function path that's actually causing the incorrect `first_download_login_game` flip at all, and
**Hypothesis A above may itself need re-examination** — it's possible the popup is being triggered
through some other code path entirely that hasn't been found yet.

**What was NOT completed**: finding where the *object itself* (the thing at `param_1`, i.e. what
`Globals.channel` actually points to) gets **constructed and assigned** onto the Python `Globals`
module. The method table's own address (`0x03a1a5c0`) had **zero discovered xrefs** in this
session's Ghidra scripts — almost certainly because the project's headless Ghidra invocation runs
with `-noanalysis` (see `scratch/run_ghidra_script.bat`), which skips full auto-analysis and often
misses xrefs to addresses only reachable via computed `ADRP`/`ADD` instruction pairs (very common
for referencing a static table by address in ARM64). **Next step for whoever picks this up**:
either re-run analysis with full auto-analysis enabled (slow, but thorough — consider a scoped
`analyzeHeadless` pass instead of `-noanalysis`, or manually add a small script that scans for
`ADRP`/`ADD` instruction pairs whose resolved target equals `0x03a1a5c0` since Ghidra's importer may
not always auto-create those references even with analysis enabled), or approach it from the
Frida/live side instead (see §6).

**Live Frida attempt not completed**: wrote `scratch/frida_native_channel_trace.py` to hook
`get_auth_type`/`get_auth_type_name`/`guest_bind` directly at their `libclient.so`-relative
offsets (`0x973ffc`/`0x974020`/`0x9740f8`) and log call timing + the `*(param1+0x10)` pointer value
live during a real login. **The app crashed/closed to the home screen during this test** before the
hooks ever fired (the script's `Module.findBaseAddress('libclient.so')` polling never found the
module in ~80s of waiting, which is itself suspicious since `logcat` shows `libclient.so` loaded
successfully via breakpad_callback around the same time). Root cause of that crash **not
diagnosed** — logcat around the crash only showed an SELinux avc denial for frida-server's
`sys_nice` capability (`scratch/crash_check.txt`), which may be unrelated noise rather than the
actual cause. Retry this hook, but consider: (a) attaching to `com.netease.neox.Launcher` earlier
in its lifecycle (spawn+resume, not attach-after-start, so Frida is present before `libclient.so`
even loads), (b) checking whether Frida's presence itself trips an anti-tamper check in this native
engine (the project has an existing `scratch/ghidra_scripts/AntiTamperSearch.java` from an earlier,
different investigation — re-run it or check its prior output for hints), (c) simplifying the hook
to just log entry with no memory reads at first, to isolate whether the crash is from the hook body
or from something else entirely coincidental.

---

## 5. Tooling Reference (all already working, reuse rather than rebuild)

- **`tools/script_index.py`**: decrypts/indexes every module in the real `script.npk` (from
  `04_obb/extracted/script.npk`, this project's actual OBB asset, not a generic reference tree) into
  `scratch/script_index.txt` — one `FILE :: name-or-const-string` line per entry. Already run; the
  file exists and is current.
- **`tools/script_query.py <file-substring> [name-regex]`**: greps `script_index.txt` for a file and
  prints its matching names/consts (truncated to ~3000 chars per file — for files with 500+ names,
  grep the raw `script_index.txt` directly instead, e.g. `grep "UILogin.py ::.*Guest"`).
- **`tools/script_disas.py "path/File.py" funcName [funcName2 ...]`**: disassembles named
  functions/methods from a module (walks nested code-object consts to find them by name). Bytecode
  is genuinely Python-2.7-shaped but with **NeoX-shuffled opcode numbers** — most opcodes disas
  correctly by name (`LOAD_GLOBAL`, `POP_JUMP_IF_FALSE`, etc.), but some show as `??neox=N arg=M`
  where the mapping isn't known; treat those as gaps, not errors — they can hide real logic
  (multiple `??neox` ops appeared adjacent to `STORE_MAP` sequences in this session's transcript,
  for example, without full certainty about their effect).
  - **This decompiler is READ-ONLY.** `C:\Users\Raysoo\Downloads\RulesOfSurvivalOld (2)\RulesOfSurvivalOld\tools\re\ros_script_decrypt.py`
    (the underlying decrypt engine `tools/script_index.py` imports) has no encode/marshal-dump/
    re-encrypt function at all. If a future approach wants to **patch and reinject** modified script
    bytecode back into the running game, that entire write-side pipeline (bytecode patcher respecting
    the NeoX opcode shuffle + Py2.7 marshal writer + `reverse_string`/`deob` re-obfuscation + rotor
    re-encryption + container repackaging) **does not exist yet** and would need to be built from
    scratch. Do not assume this is a "quick" alternative to native RE — it is comparably large.
- **Ghidra**: existing analyzed project at `scratch/ghidra_project/ROS_RE.gpr` (program
  `libclient_arm64.so` already imported). Run any script via:
  ```
  scratch\run_ghidra_script.bat <ScriptName.java> <output-log-path>
  ```
  (the script must live in `scratch/ghidra_scripts/`, `//@category ROS_RE` header required). This
  session added four new scripts there, all working and reusable as patterns:
  - `FindChannelString.java` — locates exact string literals in defined data + their xrefs.
  - `FindAuthTypeXrefs.java` — xrefs + decompile of callers to a specific string's address.
  - `DumpAuthTypeTable.java` — raw pointer-table dump/resolution around an address (the
    PyMethodDef-table-finding technique — reusable for any similar native table).
  - `DecompileAuthType.java` — batch decompile of several known function addresses at once.
  - Existing older scripts (`FindDatXrefs.java`, `AntiTamperSearch.java`, etc.) are further
    examples of the same patterns from earlier checkpoints — see `06_notes/GHIDRA_*.md` for their
    findings/history.
- **Frida**: `frida-server-x64-1621` binary already on device at `/data/local/tmp/`. Start with:
  ```
  adb shell "su -c '/data/local/tmp/frida-server-x64-1621 -l 0.0.0.0:27042 &'"
  adb forward tcp:27042 tcp:27042
  ```
  (**important gotcha**: `adb shell "su -c '...'"` must pass the ENTIRE remote command as one
  quoted string to `-c` — splitting it across separate shell args, even via a variable, makes `su`
  misparse the first word after `-c` as a target *user id* and fail with a confusing `Unknown id:`
  error). Attach by **numeric pid**, not package name (`device.attach("com.netease.chiji")` throws
  `ProcessNotFoundError` even when `adb shell pidof` sees the process fine) — get the pid via
  `adb shell pidof com.netease.chiji` or use `device.spawn([...])` and read the returned pid.
  Always run frida-launched Python with `python -u` (or explicit `flush=True` on every `print`) —
  otherwise stdout buffering means a background-redirected log file stays empty for the entire run
  even though the script is working.
- **PowerShell vs Bash tool**: adb commands with real file paths (screenshots, pulls) work reliably
  from PowerShell; the Bash tool (git-bash) mangles Windows paths passed as adb arguments (e.g.
  `/sdcard/screen.png` gets rewritten). Use PowerShell's `adb.exe` invocations for anything
  filesystem-path-sensitive; Bash is fine for `python`, `git`, and other non-adb work.

---

## 6. Suggested Next Steps (not prescriptive — use judgment)

1. Fix the Frida native-hook crash (§4's "Live Frida attempt not completed") and actually capture
   live call timing/state for `get_auth_type`/`guest_bind` during a real login. This is the fastest
   path to ground truth if it can be made to work reliably.
2. In parallel or as a fallback, find the actual construction/assignment site of the `Globals.channel`
   object (who calls `PyModule_AddObject`/equivalent with this method table) — likely requires a
   fuller Ghidra auto-analysis pass (dropping `-noanalysis`) to resolve the missing xrefs to
   `0x03a1a5c0`, or a manual ADRP/ADD pattern scan.
3. Consider whether the popup's *true* trigger is even `showGuestAccountRemind` at all — that was
   an assumption from string-matching the popup's displayed English text, not confirmed via a
   live stack trace or breakpoint. A cheap sanity check once Frida hooking works: log every call to
   `Globals.uiMgr.enter_ui(...)` (or its native backing call) with its argument, filtered for
   `'UIGuestAccountRemind'`, to get an authoritative call site and stack.
4. Keep the standing constraint in mind throughout: **MPay account type must stay GUEST** — the
   BaseApp/Mercury wire protocol is hardcoded around the guest-shaped uid
   (`guest_11178811c6a412d9`); this was tested and breaks the whole game-world connection if
   changed (Checkpoint 25 notes in CLAUDE.md). Any fix must work within that constraint, not around
   it.
5. Update `CLAUDE.md` with whatever is found, per this project's standing rule (see its §1
   "Standing Rules") — the user has been explicit across this whole investigation that they want
   real root causes documented, not workarounds, and has twice rejected auto-dismiss-style fixes.
