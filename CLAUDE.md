# CLAUDE.md — Rules of Survival (ROS) Mobile RE & Private Server Guide

> **Project**: Rules of Survival Mobile Private Server Emulation (Game Preservation)  
> **Client**: Android APK `com.netease.chiji`, v1.610377.506841, vCode 1117219, arm64-v8a  
> **Target Environment**: LDPlayer 9 (`emulator-5554`, Android guest `172.16.1.15`, Gateway host `172.16.1.2`)  
> **ADB Path**: `C:\LDPlayer\LDPlayer9\adb.exe`  
> **Primary Script**: `mitm/local_baseapp_capture.py`  
> **Last Updated**: 2026-09-26 (§0.9: deeper read of the same server log behind §0.8's confirmed 90s-reconnect finding shows **the client, not the server, goes silent** -- the server's periodic keepalive to the correct port never stops (confirmed 10 minutes past the reconnect), but the client sends nothing at all for 63.997s starting almost exactly when the first post-Confirm loading screen begins. DISPROVEN: "missing server response" causes the reconnect. HYPOTHESIS (favored): a client-side socket-inactivity watchdog fires because the client's main thread is starved by the same long synchronous scene-load already responsible for the "slow first loading" symptom -- i.e. Phase 3 (slow loading) and Phase 4 (duplicate cycle) are one root cause, not two. Repeat runs + static analysis of the timeout constant are NOT YET TESTED. See §0.9. Previous entry (§0.8): confirmed the client re-initiates a full LoginApp/BaseApp handshake ~90s after the first succeeds, driving the duplicate `createBasePlayer` cycle -- see §0.8 for the full CONFIRMED/HYPOTHESIS table.)

---

## 0. Environment Setup After Every LDPlayer Restart (READ THIS FIRST if traffic isn't reaching the server)

LDPlayer wipes both of the following on every VM reboot/restart. If you see "Failed to retrieve
patches", "Slow connection", or the game stuck on a blank screen right after a restart, run
**`scratch/reapply_env_setup.sh`** before debugging anything else:
1. iptables DNAT (tcp 80/443/8443, udp 25000/20013 -> `172.16.1.2`) — without this, no traffic
   reaches `mitm_serve.py`/`local_baseapp_capture.py` at all.
2. `srv.crt` installed as a system-trusted CA (tmpfs overlay on `/system/etc/security/cacerts/`)
   — without this, any subsystem using standard Android TLS validation (the `mpay_oversea` login
   SDK, bundled 3rd-party SDKs) rejects our self-signed cert with a `certificate_unknown` TLS
   alert. The game's own NeoX HTTP client trusts everything unconditionally, so most traffic
   works even without this — but mpay's login/config-fetch calls don't, which is what causes the
   "Slow connection" dialog and a broken age-gate response (2026-09-25, see
   `06_notes/GATE7_BATTLE_GAMEPLAY_PLAN.md`).

After running the script, restart `local_baseapp_capture.py`, `adb shell pm clear com.netease.chiji`
(fresh app state after a cert change), then force-stop + relaunch the game.

---

## 0.1 CRITICAL: Never Uninstall/Reinstall the APK Without Re-Pushing the OBB Files First

**2026-09-26 incident**: patching/repackaging the APK requires `adb uninstall` + `adb install` (a
re-signed APK cannot upgrade-install over the old signature). This wipes
`/storage/emulated/0/Android/obb/com.netease.chiji/` on this LDPlayer image, even though normal
`pm clear` does NOT touch it. Without those files, the game is not just missing the login-popup
fix target — it **hard-crashes on every launch** (`NullPointerException` in
`Launcher$CopyFile.copyAssetFromObb`, `Launcher.java:1117`, because
`ZipResourceFile.getInputStream()` is called on a null object once the OBB is gone), bouncing
straight back to the LDPlayer home screen after the "Downloading game data requires Device storage
Permissions" prompt. This looks unrelated to whatever you were patching and is easy to mistake for
a new regression in your own change.

- Required files: `main.1117219.com.netease.chiji.obb` (~1.98 GB) and
  `patch.1117219.com.netease.chiji.obb` (~1.52 GB).
- Known-good local copies exist at `04_obb/main.1117219.com.netease.chiji.obb` and
  `04_obb/patch.1117219.com.netease.chiji.obb` in this repo (also duplicated under
  `ros_offline_server_backup/` and `ROS_VIVO_LAN/` — any of these is fine as a source).
- **Before** any `adb uninstall com.netease.chiji` / repackage-and-reinstall workflow, back up
  whatever's currently on the device at `/sdcard/Android/obb/com.netease.chiji/` (or just confirm
  the two files above are still available from the `04_obb/` copies).
- **After** every fresh install, restore them:
  ```
  adb shell mkdir -p /sdcard/Android/obb/com.netease.chiji
  adb push 04_obb/main.1117219.com.netease.chiji.obb  /sdcard/Android/obb/com.netease.chiji/main.1117219.com.netease.chiji.obb
  adb push 04_obb/patch.1117219.com.netease.chiji.obb /sdcard/Android/obb/com.netease.chiji/patch.1117219.com.netease.chiji.obb
  ```
  (~3.5 GB combined; expect a couple of minutes over adb.) Also re-push
  `ros_offline_server_backup/patchVersion` to
  `/sdcard/Android/data/com.netease.chiji/files/netease/h45na/patchVersion` — a fresh install wipes
  that too, and its absence separately reproduces the old "stuck/slow patch screen" symptom
  described in section 0.

---

## 0.2 "Invalid login. Please log in again." — RESOLVED (2026-09-26, Checkpoint 23)

**Root cause found and fixed**: the dialog was **not** caused by a bug in the client's login-decision
code (that theory, extensively traced in the Checkpoint 22 log kept below for history, was a dead
end). It was caused by **stale/corrupted local session state left over from this project's own
patch-testing cycles** (repeated `adb uninstall`/`install` with different signatures across the
v1-v4 APK patch attempts, interrupted logins mid-test, etc.). That corrupted state made
`j/d/d.g()` (the saved-session loader) return a `LoginInfo` whose account-type field decoded to
`UNKNOWN` (see the `j/a/g.a(int)` decoder below — any unrecognized/missing type-code integer
silently falls back to the `UNKNOWN` sentinel with no error), which `HandlerFactory.b()` then
forwarded unchanged into the enum-based dispatcher, hitting `l$c.aOrig()`'s dedicated
`if (type == UNKNOWN)` branch that unconditionally shows `login_expired`.

**Fix**: a full `adb shell pm clear com.netease.chiji` (clears app-private data, including the
corrupted session cache) followed by restoring the OBB files and `patchVersion` per §0.1 (pm clear
wipes `patchVersion` too, since it lives under the app's own external files dir — but does **not**
touch `/sdcard/Android/obb/...`, so the OBBs themselves survive a `pm clear`). After that, a
completely fresh login was traced live end-to-end with Frida and confirmed correct:
- First launch: `POST /api/users/login/guest` succeeds, `raw_msg` in the client's own log shows
  `loginType=1` (the correct GUEST code) — the corrupted-cache scenario doesn't even arise on a
  clean session.
- Relaunch (silent re-login): `j.d.d.g()` loads a valid non-null session, `l.<init>` is constructed
  with `type=TOKEN` (the always-allowed sentinel), `channelLoginSuc` fires server-side with
  `code=0`. No `UNKNOWN` decode, no `login_expired` dialog, at any point.
- Verified visually all the way through: Guest badge shows correctly on the title screen, PLAY
  works, "Please select controls" screen appears cleanly with no dialog in front of or behind it.

**Separate bug found along the way (real, but not the dialog): `MpayActivity` doesn't always call
`finish()` after a successful silent relogin.** On both the fresh-install and the relaunch test,
after the TOKEN silent relogin succeeded server-side (`channelLoginSuc code=0`), `MpayActivity`
stayed as `mResumedActivity` — a full-screen, otherwise-invisible native Android activity showing
only its own `netease_mpay_oversea__loading` spinner — sitting on top of and **capturing all touch
input** meant for the actual game underneath (which was already fully rendered and interactive:
title screen, Agreement dialog, Events panel all visibly present but untouchable). Tapping
anywhere in the visible UI did nothing because the touches were going to the invisible activity on
top, not the game. **Workaround: press the device/emulator BACK button once** — this finishes the
stuck `MpayActivity` and immediately hands focus back to `com.netease.neox.Client` (the real game
activity), after which the game responds normally to touches (confirmed: Agreement-accept,
Link-Account-dismiss, PLAY, and Select-Controls-confirm all worked immediately after one BACK
press). This is a real, not-yet-root-caused SDK-side bug (likely: the login success callback path
that should call `Activity.finish()` isn't reached, or the callback itself isn't wired for the
same TOKEN-relogin path that `ui/o.smali`'s success case takes — no `finish()` call was found
anywhere in `ui/o.smali` itself, so it must depend on inherited/base-class behavior that isn't
firing). The true root cause (why `finish()` isn't reached) is still **not found** — that remains a
small, well-scoped question for whoever picks this up next (start by checking what calls
`Activity.finish()` in the base `ui/l.smali`/`ui/a.smali` success path and whether `ui/o`'s success
callback actually reaches it).

**2026-09-26, Checkpoint 24 — confirmed 100% reproducible, and automated the recovery.** Polled
`mResumedActivity` every 2s across a fresh relaunch: `MpayActivity` became resumed at ~t=11-14s and
was *still* resumed at t=94s with zero further network activity from the client (server log showed
the login had already succeeded — only unrelated BaseApp UDP keepalives continued) — i.e. this is a
genuine, deterministic hang, not a slow-but-eventually-finishing race. `launch_game.bat` was
rewritten to poll for this specific condition (`MpayActivity` resumed continuously for
`MPAY_STUCK_THRESHOLD` = 10s) and send exactly **one** `KEYCODE_BACK` the moment that threshold is
crossed. Live-tested: cuts the hang from 90+s down to ~10s, with the game landing in the correct
post-login state every time (Guest badge, Link Account prompt) — no dialog was ever tapped through,
since there is no dialog to tap in this state (no buttons, no text prompt, just a spinner). This is
a deliberately narrow, safe automation: it fires on an activity-identity + duration condition, not
on pattern-matching a real user-facing dialog, and it is a different thing in kind from the
earlier-rejected auto-tap-the-login_expired-dialog approach (see the "Do not re-attempt" list in
§0.2a) — that dialog no longer exists on a clean device; this is recovering an already-succeeded
login screen that simply failed to close itself.

**Do not re-run `pm clear` casually** — it wipes `patchVersion` (see §0.1) and, if there ever is a
real corrupted-session recurrence, this is the fix, but it also throws away any legitimately-saved
guest account on the device. Only use it to recover from a suspected corrupted-session-state
`login_expired` loop, and always restore OBB + `patchVersion` immediately after per §0.1.

---

## 0.2a Investigation Log Leading to the Above (2026-09-26, Checkpoint 22, kept for history)

This dialog (string `netease_mpay_oversea__login_expired`, shown by
`com.netease.mpay.oversea.MpayActivity` via `widget.a$b.a`) appears both automatically pre-title
and on every PLAY tap. **Root cause is not fully found yet** — two earlier theories in this
checkpoint were each disproven by the next layer down. Recorded in order so nobody re-walks the
same disproven paths:

**Theory 1 (disproven): GameConfig-cache timing race.** A Frida hook
(`scratch/frida_mpay_login_expired.py`, logs `scratch/frida_run_auto.log`/`frida_run_retry.log`)
first suggested `g/e.a(type)` fails because `g/e`'s cached `GameConfig` field is still null when
the check runs, and would populate ~1-3s later on its own. Built and live-tested an APK patch
(decompile -> insert a non-blocking `Handler.postDelayed` retry loop in `ui/l$c.a()`, wait up to
25s for the cache -> rebuild -> resign -> reinstall). **Still failed after the full wait**, proving
this wasn't actually a timing race.

**Theory 2 (disproven): missing `persistence` field.** Reading `c/a/c.smali`/`c/a/b.smali` directly
found `g/e`'s cache-readiness flag (`c/a/c.q`, checked by `c/a/c.a()`) is populated from
`/api/games/config`'s `game_config.persistence` JSON field (default `1` if absent; needs `2` to be
"ready"). Added `"persistence":2` to `mitm_serve.py`'s response (harmless and correct to keep —
it's a real field the official protocol sends). **Still failed** — because `g/e.a(type)` (the
actual method the login flow calls) doesn't consult `q`/`d()` at all in the failing path; that was
a misreading of the method carried over from the first Frida pass. `d()`/`q` gate a *different*
accessor, unused by the login-attempt check.

**Theory 3 (confirmed mechanism, root cause of the mechanism still open):** `g/e.a(type)`
(`smali/com/netease/mpay/oversea/g/e.smali`) actually does:
```
if type in {UNKNOWN(a), TOKEN(q), MORE(p)}: return true   # always-allowed sentinels
else: return (g/e.d != null) && (g/e.d.n != null) && g/e.d.n.get(type) != null && that_entry.enable
```
`g/e.d.n` is a `HashMap<j/a/g, c/a/c$d>` built in `c/a/b.smali` by iterating **literal** JSON key
names under `game_config.account_type` (`"guest"`->`GUEST`, `"google"`->`GOOGLE`, etc. — verified
line-by-line; our `"guest"` key + `"enable":true` maps correctly to `GUEST` and *would* pass this
check). The Frida trace's `l$c.a() ENTRY outer l.a = [null]` means the actual `type` used for the
failing call is a **literal Java `null`**, not `GUEST` — and `null` is not one of the three
sentinels and can never be a HashMap key match, so this branch is mathematically guaranteed to
return `false` regardless of anything the server sends or how long the client waits.
`com.netease.mpay.oversea.ui.l;->a` (the type field) is `protected final`, set exactly once in
`l`'s constructor from a caller-supplied argument — **not reassignable, not a race**. Confirmed
call sites: `ui/j.smali` always passes `GUEST`, `ui/h.smali` always passes `GOOGLE`, `ui/o.smali`
always passes `TOKEN` (silent-relogin, always-allowed sentinel anyway) — none of these three ever
pass null. `ui/w.smali` and `ui/k.smali` pass through a caller-supplied type verbatim, so one of
*those* two is almost certainly what's instantiated for the automatic pre-title attempt (and
possibly the first PLAY tap), with its caller passing `null` for a reason not yet traced.

**Update (same day, continued investigation):** live Frida hooks (not more static reading) on
`g/e.a(type)`, `widget.a$b.a` (the login_expired dialog shower), and `l`'s constructor gave a
corrected picture: the actual type reaching the failing check on a fresh install is **`UNKNOWN`**,
not literal `null` (the very first Frida pass's `l.a = [null]` log line was imprecise/misread).
`UNKNOWN` doesn't go through the `g/e.a(type)` HashMap-lookup branch at all — `l$c.aOrig()` has an
earlier, separate check (`if (type == UNKNOWN) -> unconditionally build+show login_expired`) that
fires first. Traced the call chain that produces `UNKNOWN` all the way up through 7 layers of
`HandlerFactory`'s heavily-overloaded static dispatch methods
(`a(Activity,int,Wrapper)` -> `a(Activity,int,LoginData)` -> `b(Activity,LoginData)` ->
`a(Activity,j/a/g,LoginData)`) using live stack traces (`scratch/frida_final_trace.py`) — confirmed
`HandlerFactory.b()` is the direct caller passing `UNKNOWN`, but its own smali (read multiple times,
carefully) never references the `UNKNOWN` constant at all, only `GUEST`/`GOOGLE`/`TOKEN` — a
static-vs-live contradiction not resolved (checked and ruled out: decompiled tree does exactly
match the live installed APK by MD5). Likely explanation: `b()`'s "new account login" branch
(reached when `j/d/d.g()` returns null, i.e. no saved session — our exact test condition) should
resolve to `GUEST` per its own smali, but something upstream of it (not yet found) is instead
constructing the whole login attempt with `UNKNOWN` before `b()` even runs, and ordinary
static reading of `b()` in isolation doesn't show it because the decision was already made by an
even earlier caller.

**Tried and reverted: patching `l$c.aOrig()`'s `UNKNOWN` branch to behave like `GUEST`** (redirect
`if (type==UNKNOWN) goto login_expired` to instead run the same code as `if (type==GUEST)`, which
is `l.i()`). This measurably changed behavior — the login_expired dialog stopped appearing — but
uncovered the next layer of the same underlying problem: `l.i()` calls a method on instance field
`l.g` (a third-party-SDK-check interface), and **that field is never initialized, including by the
genuine dedicated `ui/j` GUEST subclass's own constructor** (confirmed by reading `j.smali`'s
`<init>` in full — it only calls `super(activity, GUEST, loginData, g)` and returns, never touches
`g`). So `l$c.aOrig()`'s `type==GUEST -> l.i()` branch is not actually the normal/primary path a
real, successful guest login takes either — it's some other edge-case handler, and calling it
directly just hangs the client on an unresolved loading spinner instead of showing the dialog
(confirmed live: no crash, no new logcat FATAL, just an indefinitely-spinning loading icon on the
title screen). This patch was reverted; the original untouched APK is what should currently be
installed (see `scratch/apk_backup/base_original_20260925_233735.apk`, md5 `cf15a74f075bb3d9c3d00f55f0c33854`).

**Where this stands:** the actual, successful guest-login call chain (the one that works when the
official/production servers are used, or empirically when this project's own docs describe reaching
the Lobby) does **not** go through `l$c.aOrig()`'s `GUEST`/`l.i()` branch at either the type-check
or the third-party-interface-init step. That real chain has not been found yet. The `UNKNOWN`
type's true origin (which caller upstream of `HandlerFactory.b()` decides on it) also has not been
found. Both are needed before another patch attempt. Live Frida infra for this remains set up and
working (`frida-server-x64-1621` running on device, port-forwarded; see
`scratch/frida_final_trace.py`, `scratch/frida_dialog_trace.py`, `scratch/frida_enum_convert_trace.py`
for reusable hook patterns) — prefer extending these over more static smali reading, which has
repeatedly produced incomplete or contradicted-by-runtime conclusions in this investigation.

**Do not re-attempt:** the auto-tap/dismiss-script workaround (works, but was explicitly rejected
by the user as "not a real fix"), the GameConfig-timing-race theory, the missing-`persistence`-field
theory, or naively redirecting `l$c.aOrig()`'s `UNKNOWN` branch to `GUEST`'s `l.i()` call — all
tried and disproven/incomplete as of 2026-09-26.

---

## 0.3 Checkpoint 25 (2026-09-26): Guest Login Replaced with Real Supabase Email+Password Auth

**Goal**: replace the shared, hardcoded guest identity with real per-person accounts, gated by
a native "Sign in" screen inside the APK, checked against the project's Supabase project.

### Architecture

- **New native Activity `com.netease.chiji.EmailAuthActivity`** is now the app's `LAUNCHER`
  activity (moved the `<intent-filter>` off `com.netease.neox.Launcher`, which is otherwise
  unchanged). It shows a plain `AlertDialog` (title/message/EditText-email/EditText-password,
  built entirely in code, no new layout XML) before anything else loads.
- On submit, it POSTs JSON `{email, password}` to a new server endpoint, **`/custom/auth/login`**
  (`mitm/mitm_serve.py`, added near the existing `/api/users/login/guest` block, same
  send_response/json.dumps style). That endpoint calls `mitm/supabase_db.py`'s new
  `authenticate(email, password)`:
  1. Checks `pre_registrations` table (the allowlist — a marketing/early-access signup list,
     email only, no password) via the existing REST pattern.
  2. Tries `create_auth_account` (Supabase Auth `/auth/v1/signup`) first; if the account already
     exists, falls back to `verify_auth_login` (`/auth/v1/token?grant_type=password`).
  3. Returns `{"ok": true, "uid", "token", "nickname"}` or `{"ok": false, "reason"}`.
  - **Known Supabase-side caveat**: if "Confirm email" is enabled under Authentication →
    Providers → Email, a fresh signup can't log in again until the confirmation link is
    clicked — impossible on this offline setup. Turn it OFF for this project to work.
- On success, `EmailAuthActivity.onLoginSuccess` hands off to the MPay SDK's own,
  already-proven session-save chain **via reflection** — `j.a.f$a` (Builder) → `.a()` → `j.b`
  → `j.d.d.a(j.a.f)` — instead of re-implementing the SDK's file format. This guarantees
  byte-for-byte compatibility since it's the SDK's real code being called, not a guess.
  - **Important:** the `uid` written into this session is hardcoded to
    `GAME_ACCOUNT_UID = "guest_11178811c6a412d9"` (the device-id-shaped identity the deep
    BaseApp/Mercury binary protocol in `local_baseapp_capture.py` is built entirely around) --
    **not** the real Supabase uid. Swapping in a differently-shaped uid there broke the BaseApp
    handshake (`account login failed` client-side error, no `createBasePlayer` ever logged).
    The real per-person Supabase identity is tracked at the `/custom/auth/login` layer only
    (session_store + Supabase), not threaded through to the wire protocol. **Follow-up not yet
    done**: `local_baseapp_capture.py`'s player-state load/save (`_load_player_state`,
    `supabase_db.get_player()`) still always uses the one hardcoded uid/local files -- it does
    not yet look up "who most recently authenticated" to load their own stats/inventory. A
    server-side "active account" mapping (set by `/custom/auth/login`, read by the state
    load/save functions) is the planned way to do this without ever touching the uid on the
    wire.
- New **`com.netease.chiji.MpayWatcherService`** (`AccessibilityService`) watches for
  `MpayActivity` becoming the foreground window and staying there 10s+ with no further window
  changes, then calls `performGlobalAction(GLOBAL_ACTION_BACK)` once. This is the automated,
  in-APK version of the manual BACK-press workaround from Checkpoint 24, and it works: log
  proof `performGlobalAction(BACK) -> true` reliably released the stuck activity in live tests.

### Toolchain notes for anyone adding another native class this way

- Building blocks used: `javac` (any JDK; `-source 8 -target 8` to match this app's old
  bytecode style) against `android.jar` (`…\Sdk\platforms\android-34\android.jar`) → `d8.bat`
  (`…\Sdk\build-tools\34.0.0\d8.bat`) → **baksmali, invoked programmatically** (a tiny driver
  class calling `com.android.tools.smali.baksmali.Baksmali.disassembleDexFile(...)`, since
  apktool.jar bundles baksmali but its CLI `Main` isn't a runnable entry point on its own — see
  `scratch/email_auth_build/BaksmaliDriver.java`) → copy the resulting `.smali` files into a
  **new `smali_classesN` folder** in the decompiled tree (apktool auto-compiles each
  `smali_classesN` into its own `classesN.dex` on `apktool b`, so this never touches the
  existing `classes.dex`/`2`/`3`). Whole workflow is scripted informally in
  `scratch/email_auth_build/` — recompile with the same javac/d8/baksmali three-liner, copy over
  the `smali_classes4/com/netease/chiji/*.smali` files, `apktool b`, zipalign, apksigner, `adb
  install -r` (same debug keystore across every rebuild this checkpoint = no uninstall needed,
  so **OBB survives** — only fall back to full uninstall+reinstall, with the full OBB-restore
  dance from §0.1, when actually changing the signing key or doing a from-scratch test).
- **d8 in this toolchain (build-tools 34.0.0) is a broken dev snapshot that crashes with a
  `NullPointerException` while dexing ANY class carrying an implicit outer-class reference**
  (`this$0`) — i.e. any non-static inner class, anonymous class, or local class, regardless of
  whether it's actually used. Confirmed with a minimal repro outside the app entirely. Fix:
  write every helper class as a **named `static` nested class**, passing the outer
  instance/activity in explicitly through its constructor instead of relying on an implicit
  outer reference. Every class in `EmailAuthActivity.java`/`MpayWatcherService.java` follows
  this pattern.
- Calls into private SDK classes (`com.netease.mpay.oversea.j.a.f$a`, `j.b`, `j.d.d`, `g.c`)
  are all done via `java.lang.reflect` so the new class compiles standalone against
  `android.jar` alone — no need to extract/stub the app's own classes for the build.

### Environment/process gotchas hit along the way (all resolved, keep in mind for next time)

- **AccessibilityServices get silently disabled by Android whenever their owning app is
  force-stopped** (`adb shell am force-stop` — which every relaunch cycle in this project's
  testing does). `dumpsys accessibility` will show `services:{}` after a force-stop even though
  nothing changed on disk. Re-running `adb shell settings put secure
  enabled_accessibility_services com.netease.chiji/com.netease.chiji.MpayWatcherService` +
  `settings put secure accessibility_enabled 1` **after the app process has actually
  (re)started** (not right after force-stop, before the app runs again — that write doesn't
  stick) re-binds it. `launch_game.bat` should run these two commands after every launch if this
  service needs to survive normal test cycles; this was not yet wired in as of this checkpoint.
- **The mitm server's own `BASEAPP KEYSCAN` background watcher (which extracts the live session
  encryption key from the game process's memory by finding `libclient.so`'s base address) can be
  silently starved by unrelated heavy adb traffic** — its own internal `adb shell pidof
  com.netease.chiji` polling call has a 20s timeout, and if enough *other* adb commands are
  queued on the same adb server at the same time (large `adb push`, `dumpsys` calls run back to
  back, etc.), it can time out repeatedly and **give up entirely** after a fixed number of
  retries, without any further retry on subsequent app launches. Symptom: the client's actual
  LoginApp/BaseApp UDP packets never get a reply (`account login failed` client-side error), yet
  every log line only ever shows harmless, unrelated `hello ros` 9-byte probe packets from
  `127.0.0.1` — **check `grep 'KEYSCAN' scratch/server_stdout.log` for whether the most recent
  entry is `SUCCESS` or a long run of `adb call failed`/`could not find libclient.so base`
  before assuming a login/network bug** whenever real BaseApp traffic seems to vanish. Fix:
  restart `mitm/local_baseapp_capture.py` and avoid running other heavy/overlapping adb commands
  for the few seconds right after a fresh game launch, letting its own PID watcher get a clear
  shot at the keyscan.
- Large sequential `adb push` operations (the ~3.5GB combined OBB files) can destabilize the
  LDPlayer instance's adb bridge if overlapped with other adb traffic (observed: emulator went
  fully `offline`, requiring `ldconsole.exe reboot --index 0` to recover, plus a full
  `scratch/reapply_env_setup.sh` re-run afterward since the reboot wipes the CA-trust/DNAT setup
  from §0 again). Push OBB files **one at a time, sequentially**, not overlapped with anything
  else.
- A `HttpURLConnection` from newly-added app code must use `https://`, not `http://` — this
  app's `targetSdkVersion` (29) blocks cleartext HTTP by default with no network-security-config
  override present, even though the game's own bundled traffic mostly already uses HTTPS to the
  same mitm server. Also: use one of the mitm TLS cert's actual `subjectAltName` hostnames (e.g.
  `sdk-os.mpsdk.easebar.com`) rather than the raw DNAT target IP (`172.16.1.2`) as the URL host —
  the cert has no SAN entry for that literal IP, so hostname verification fails even though the
  certificate chain itself is trusted; the DNAT rule (matches by destination *port*, not host)
  redirects it to the same server regardless of which allowed hostname is used.

### Checkpoint 26 (2026-09-26): "account login failed" dialog root-caused and fixed

**Root cause found via live Frida introspection (static smali reading alone gave the
wrong answer here — see below).** `EmailAuthActivity.onLoginSuccess()` built the correct
`j.a.f` (LoginInfo) object via reflection (`f$a` builder) with `type=GUEST` and the real
token every time -- confirmed live: `f$a.a()`'s build result and every step of the
`j.d.d.b(f)` -> `a(f)` -> `c(f)` save-method call chain showed the object intact. The bug
was earlier in the pipeline: `com.netease.mpay.oversea.g.c;->b().q()` (`GameConfig.q()`,
the SDK's `appId`, which the SharedPreferences filename is keyed on as
`com.netease.mpay.<md5(appId)>.xml`) **returns an empty string `""`while
`EmailAuthActivity` is on screen**, because `appId` is a hardcoded literal (`"123"`,
confirmed live) that gets set inside `com.netease.neox.Launcher`'s own `onCreate` --
code that, since Checkpoint 25 moved the `LAUNCHER` intent-filter onto
`EmailAuthActivity`, simply hadn't run yet at the point `onLoginSuccess` used to do its
reflection save. So the save silently wrote to the *wrong* prefs file
(`com.netease.mpay.d41d8cd98f00b204e9800998ecf8427e.xml`, `md5("")`), while the real
silent-relogin later (once `Launcher` actually started and set `appId="123"`) read from
`com.netease.mpay.202cb962ac59075b964b07152d234b70.xml` (`md5("123")`) -- which still had
stale, corrupted `type=UNKNOWN`/`token=null` data left over from pre-Checkpoint-25 guest
testing. That `UNKNOWN` type is exactly what hits `ui/l.smali`'s `dealApiLoginFailed` ->
`login_connect_retry` dialog path (the "account login failed. Try again? (#uid--code)"
popup, string `netease_mpay_oversea__login_connect_retry`).

**Verified live with Frida** (`Java.choose('com.netease.chiji.EmailAuthActivity', ...)`
+ calling `onLoginSuccess()` directly with test uid/token, bypassing the network call):
hooking `com.netease.mpay.oversea.g.c;->b().q()` while `neox.Launcher` is running (real
init path, launched via `am start -n .../com.netease.neox.Launcher`) showed `appId="123"`
already present at t=0s (not a network-fetched value, so no need to wait/poll for a
server round-trip -- just needs `Launcher.onCreate` to have run at all). Hooking the same
call from `EmailAuthActivity` (launched directly, `LAUNCHER`'s real entry point) showed
`appId=""`. Hooking `j.d.d.g()` (the session loader) immediately after a save done with
the empty appId returned **`null`** -- proving the old code's save was truly going
nowhere useful, not just to a stale file.

**Fix** (`scratch/email_auth_build/src/EmailAuthActivity.java`, `onLoginSuccess`):
reordered to `startActivity(Launcher)` **first** (same process; this Activity and its
`Handler` keep running even after `Launcher` is pushed on top), then poll
`GameConfig.q()` every 200ms (up to an 8s timeout, though in practice it resolves
same-tick since it's a hardcoded literal, not a fetch) via a `Handler.postDelayed` loop
(`trySaveSession`/`SessionSaveRunnable`, both required to be **static nested classes** --
same d8-NPE-on-inner-class constraint as every other class in this file, see the
toolchain notes below), and only performs the `j.b`/`f$a` reflection save once `appId` is
non-empty. `finish()` moved to fire after the save completes (or times out), not
immediately after starting `Launcher`.

**Verified end-to-end live** (Frida-driven fake login, bypassing the Supabase network
call to isolate the session-save/reload path): after the fix, `j.d.d.g()` inside the
now-running `Launcher` process reloaded the exact object just saved
(`type=GUEST`, `token` intact) -- then, a few polls later, the SDK's own real GUEST login
flow kicked in on its own (as designed, since type is now correctly `GUEST` and not
`UNKNOWN`) and replaced the token with a real server-issued session token
(`sess_...`, from `mitm_serve.py`'s `/api/users/login/guest`). Screenshot confirms: app
reaches the title screen cleanly, `Guest` badge top-right, Events panel and "Link
Account" prompt visible, **no `login_connect_retry` dialog at any point**. Rebuilt via
the existing `scratch/email_auth_build/build.py` -> `scratch/rebuild_and_install_apk.py`
pipeline (same debug keystore, `adb install -r`, OBB untouched, no `pm clear` needed --
the old corrupted `md5("123")` session file gets correctly overwritten by the new code's
first real save instead of needing to be manually cleared).

**Frida debugging notes for next time (things that cost real time here):**
- `frida.get_usb_device().attach("com.netease.chiji")` by package name fails
  (`ProcessNotFoundError`) even though `adb shell pidof` sees it fine -- attach by numeric
  pid (`device.attach(<pid>)`) instead.
- `device.spawn(["com.netease.chiji"])` launches via the package's registered `LAUNCHER`
  (now `EmailAuthActivity`, not `neox.Launcher`) -- to test the SDK's real
  `neox.Launcher` init path in isolation, `adb shell am start -n
  com.netease.chiji/com.netease.neox.Launcher` (or `/.EmailAuthActivity`) to pick the
  activity directly, then `frida.attach(pid)` (not spawn) once it's already running.
- **Do not trust field names/order from the decompiled smali tree without confirming
  against a live `getClass().getDeclaredFields()`/`getDeclaredConstructors()` dump
  first** -- in this checkpoint, `j.a.f`/`j.a.f$a`'s field layout in
  `scratch/vivo_apk_new` happened to match the live installed APK exactly (verified), but
  the earlier investigation's stale-vs-live contradictions (Checkpoint 22's `HandlerFactory.b()`
  mismatch) show this isn't guaranteed across APK variants/builds. Cheap to check first
  with a small `Java.use(cls).class.getDeclaredFields()` dump.
- Python `print()` to a file redirect from inside a background-launched process needs
  `python -u` (or explicit `flush=True`) -- otherwise stdout buffering means the log file
  stays empty for the whole run even though the script is working correctly.
- `adb shell su -c '...'` needs the ENTIRE remote command as one quoted string passed to
  `-c` (e.g. `shell "su -c 'ls /some/path'"`) -- passing it as separate shell args (even
  via a PowerShell variable) makes `su` swallow the first word after `-c` as a target
  *user id* instead, failing with a confusing `Unknown id: ...` error.

### Checkpoint 25 follow-up (2026-09-26, NEW, OPEN): full observed flow is slow, not broken

With the new `EmailAuthActivity` + `MpayWatcherService` build and the KEYSCAN fix above, the user
walked the entire flow end to end and reported it back exactly as this sequence -- recorded
verbatim/step-by-step here before any further fix attempt, per this project's standing rule of
documenting an issue before working on it:

1. Open app -> first splash image.
2. Patched-part splash image loads up to ~50%, then shows the small centered loading spinner with
   a dimmed overlay (the `MpayActivity` stuck-overlay pattern from Checkpoint 24, now confirmed to
   also occur at this *pre-title* point, not only after PLAY) -- this persists until the title page
   appears.
3. Title page -> PLAY.
4. "Please select controls" screen -> its confirm button has a countdown; must wait for the full
   countdown before tapping Confirm (tapping early causes the already-documented loop-back, see
   the note above this one).
5. **Loading after Confirm is very slow ("sobrang bagal").**
6. Loops back to "Please select controls" **once**.
7. **Loading again is very slow ("sobrang bagal").**
8. Reaches Daily Claim.
9. Hall/Lobby starts.

**Open question, not yet investigated**: whether steps 5 and 7's slowness is (a) inherent to this
LDPlayer/emulator + mitm-server setup and was always this slow (plausible -- this project's own
Gate 4 notes already describe the hall UI as sometimes non-deterministic/slow to settle), (b) a
new side effect of today's changes (e.g. the accessibility service's `postDelayed` polling, or the
extra `su` shell-out added to `EmailAuthActivity.onCreate`, adding overhead), or (c) related to the
still-not-fully-diagnosed BaseApp/KEYSCAN timing sensitivity from the section above. Needs a timed,
controlled comparison (same account, same device, stopwatch on each loading segment) against the
pre-Checkpoint-25 guest-only flow before concluding which.

---

## 0.4 Checkpoint 27 (2026-09-26): "Link Account" nag popup — trigger chain found; state persistence is dead

Continued from `scratch/HANDOFF_PROMPT_CLINE_2026-09-26.md`. The investigation that was assumed to
need Frida/Ghidra turned out to be answerable from the **decrypted scripts + on-device state files
alone**, and it now has a bytecode-verified chain from the popup back to its gate. Everything below
is read out of the real `script.npk` (via `tools/script_disas.py` / the new
`scratch/dump_module_funcs.py`, `scratch/dump_module_consts.py`) or off the device.

### A. The popup's one and only entry point (authoritative — string-level proof)

`ui/UIGuestAccountRemind.py` is the "Link Account" / `guest_attention` panel
(`ui/g89na/ui_guest_account/guest_account.csb`, buttons `btn_bindnow` / `btn_later` / `btn_guanbi`,
handlers `onBindNowBtnClicked` → native `Globals.channel.guest_bind`, `onLaterBtnClicked`,
`onCloseBtnClicked`).

The string `'UIGuestAccountRemind'` appears in exactly **one** script in the whole bundle:
`ui/UILogin.py`, inside `UILogin.showGuestAccountRemind` → `Globals.uiMgr.enter_ui('UIGuestAccountRemind')`.
There is therefore no second code path that can open this panel.

That method is **not called from UILogin itself**. The name appears in `helpers/channel/channel_helper.py`
as a *string constant* at bytecode offset 797 of `ChannelHelper.onLoginSucceed`:

```
Globals.uiMgr.UILogin.extractNeteaseWinSauthInfo()
...
Globals.uiMgr.UILogin.exceptionHandleFunc('showGuestAccountRemind')      <-- the only trigger
Globals.uiMgr.UILogin.checkQiyu()
Globals.uiMgr.UILogin.setDefaultServerNickname()
```

So the trigger is **`ChannelHelper.onLoginSucceed` → `Globals.uiMgr.UILogin.exceptionHandleFunc('showGuestAccountRemind')`**
(a name-string dispatch, which is why `showGuestAccountRemind` never shows up as a `LOAD_ATTR`
anywhere). Timing matches what is observed: the panel appears right after a successful channel
(= MPay) login, i.e. on the log-in/title screen.

### B. The gate logic, verified instruction-by-instruction

`ui/UILogin.py :: showGuestAccountRemind` (3 locals, `VARNAMES=['self','last_remind_time','need_remind']`,
`NAMES=['Globals','channel','market_record_points','cur_market_record_point','get','True','time','False','name','get_auth_type','uiMgr','enter_ui','saveMarketRecordPoint']`):

```python
def showGuestAccountRemind(self):
    if (Globals.channel and Globals.market_record_points
            and not Globals.market_record_points.cur_market_record_point.get(
                    'first_download_login_game', True)):
        last_remind_time = Globals.market_record_points.cur_market_record_point.get('last_remind_time', 0)
        if last_remind_time != 0:
            need_remind = time.time() - last_remind_time > 86400
        else:
            need_remind = True
        if (Globals.channel.name == 'netease_global'
                and Globals.channel.get_auth_type() == 2        # 2 == GUEST (verified earlier)
                and need_remind):
            Globals.uiMgr.enter_ui('UIGuestAccountRemind')
            Globals.market_record_points.cur_market_record_point['last_remind_time'] = time.time()
            Globals.market_record_points.saveMarketRecordPoint()
            return
    # single shared "else" block, reached from ANY of the three failed guard tests above
    Globals.market_record_points.cur_market_record_point['first_download_login_game'] = False
    Globals.market_record_points.saveMarketRecordPoint()
```

(All three guard tests `POP_JUMP_IF_FALSE 227` into the same block; the `need_remind`/name/auth
tests `POP_JUMP_IF_FALSE 256` = plain return. Offsets 0..256 verified.)

Consequences worth internalising:
1. The popup is gated by `channel.name == 'netease_global'` **and** `get_auth_type() == 2` **and**
   `need_remind`. Our emulation is *permanently* `auth_type == 2` (the hardcoded guest identity the
   BaseApp/Mercury protocol is built around — **do not change**), so that half of the condition is a
   constant in our environment.
2. `need_remind` is the only schedule control, and it is computed **only** from
   `cur_market_record_point['last_remind_time']` — a 24 h re-nag, not a one-shot.
3. `first_download_login_game` is written **only** in two places in the whole script set:
   `INIT_MARKET_RECORD_POINT[...] = True` (see C below), and this function, which sets it to
   **False** on the "gate was closed" path. Nothing ever calls
   `doSomething('first_download_login_game')`; that string occurs in only
   `helpers/market_record_points.py` and `ui/UILogin.py`. **So once `showGuestAccountRemind` runs
   successfully, the flag is False for good and the panel is purely `last_remind_time`-gated.**

### C. `INIT_MARKET_RECORD_POINT`, bytecode-reconstructed (the piece the handoff was missing)

`helpers/market_record_points.py` builds it in the **class body** — which is why `__init__` reads it
as `self.INIT_MARKET_RECORD_POINT` (the `??neox=129 arg=0` before that `LOAD_ATTR` is `LOAD_FAST self`,
not a global load). Class-body listing (offsets 6..51), with `157 = STORE_NAME` and
`153 = LOAD_NAME/LOAD_GLOBAL` (both indexed by `co_names` — the indices line up exactly, e.g.
`??neox=157 arg=3` → `STORE_NAME co_names[3] = 'INIT_MARKET_RECORD_POINT'`, and
`??neox=157 arg=4..10` → `__init__`, `get_uuid`, `hasDoneSomething`, `doSomething`,
`thirty_min_done`, `loadMarketRecordPoint`, `saveMarketRecordPoint` in order):

```
 6 BUILD_MAP 6
 9..29  {} 'first_game_done' | {} 'first_friend_added' | {} 'first_match_successed'
30 LOAD_NAME 'True'                (co_names[2] == 'True')
33..36 'first_download_login_game'
37..43 0 'last_remind_time'
44..50 {} 'first_on_plane'
51 STORE_NAME INIT_MARKET_RECORD_POINT
```

⇒

```python
INIT_MARKET_RECORD_POINT = {
    'first_game_done': {}, 'first_friend_added': {}, 'first_match_successed': {},
    'first_download_login_game': True,          # <-- gate is CLOSED on a virgin state
    'last_remind_time': 0,
    'first_on_plane': {},
}
```

So on virgin state the gate is closed and the function only *arms* it (writes `False`). The panel
can never appear on the first evaluation of a fresh state; it appears on the **second** evaluation
in the life of that state, and then whenever `last_remind_time` is over 24 h old. That is the
signature of a "state that is expected to survive across launches" — which is exactly what is
broken here.

### D. Why it re-fires on *every* launch: the market-record-point persistence is dead

`helpers/market_record_points.py` (fully decompiled — see `scratch/disas_market_record_points.txt`,
`scratch/consts_market_record_points.txt`):

* `loadMarketRecordPoint()` → builds `recordPath = os.path.join(Application.persistentDataPath,
  'market_record_point_%s.txt' % uuid)`; if it does not exist it calls **`self.saveMarketRecordPoint()`**
  (and migrates the legacy `market_record_point.txt`), otherwise it `json.loads`s the file into
  `self.cur_market_record_point`.
* `saveMarketRecordPoint()` → `json.dumps(self.cur_market_record_point, sort_keys=True, indent=4,
  separators=(',', ' : '))` into that same path.
* `hasDoneSomething(k)` / `doSomething(k)` (the AppsFlyer-style "record points") also early-return.
* **All four start with `uuid = self.get_uuid(); if uuid == '': return`.**

`get_uuid()` returns `''` unless *all* of these hold, and otherwise returns `str(gid) + '_' + str(serverGroupId)`:
1. `BigWorld.player()` is truthy (`gid = BigWorld.player().gid`),
2. `helpers.ConnectMonitor.ConnectMonitor.getInstance().loginHostRecord` is truthy,
3. `loginHostRecord.get('groupid', '')` is non-empty.

(`loginHostRecord` is set by `UILogin.startLogin` → `ConnectMonitor.getInstance().setLoginHostInfo(
username, defaultServerName, defaultServerIP, defaultServerPort, defaultGroupId)` →
`loginHostRecord = {..., 'groupid': groupid}`; `user_info.txt` shows `defaultGroupId: "10001"`, so
condition 3 is satisfied in practice. `BigWorld.player()` is the suspect: `showGuestAccountRemind`
runs from `onLoginSucceed`, i.e. before any world/player entity exists.)

**Device-level proof that this path is dead** (2026-09-26, `emulator-5554`):
* `Application.persistentDataPath` is confirmed to be
  `/sdcard/Android/data/com.netease.chiji/files/netease/h45na/Documents` (the only `user_info.txt`
  on the device lives there, and `UILogin.readUserInfo`/`writeUserInfo` join exactly
  `persistentDataPath + 'user_info.txt'`).
* That directory is writable and full of runtime-written state (`user_info.txt`,
  `basic_settings.txt`, `character_info.txt`, `notice_once_config.txt`, `patchVersion`, …).
* **Neither `market_record_point_<uuid>.txt` nor the legacy `market_record_point.txt` exists
  anywhere on the device** (`find /sdcard` + `su -c find /data`, and `selinux`/`ls` checks).
  Because `loadMarketRecordPoint()` *creates the file* the moment `get_uuid()` can resolve, the
  file's total absence means **`get_uuid()` has returned `''` at every single call, ever**.

⇒ The in-memory `cur_market_record_point` is therefore always the pristine
`copy.deepcopy(self.INIT_MARKET_RECORD_POINT)`: `first_download_login_game` starts `True`, gets
flipped to `False` by the first `showGuestAccountRemind` call of the session, and `last_remind_time`
is written **only in memory**. Every process restart throws that away, so the 24 h suppression window
never survives a restart — the nag re-arms and re-fires on every launch. That is the whole of the
"it shows up every single time" symptom; nothing else is needed to explain it.

**Two corollaries that close the loop without any instrumentation:**

1. **`get_uuid()` really does fail at the login-time call site.** The branch that *arms* the gate
   (the `227` block) is also the branch that calls `Globals.market_record_points.saveMarketRecordPoint()`,
   and arming is the only way the gate ever opens later. Since the panel does appear, that branch has
   run, so the save has been attempted, so a resolvable `get_uuid()` would have created
   `market_record_point_<uuid>.txt`. No such file exists ⇒ **`get_uuid()` returns `''` at
   `ChannelHelper.onLoginSucceed` time** (i.e. `BigWorld.player()` is falsy there, and/or the login-host
   record has no group id yet). That is inherent to calling this at *channel*-login time, and no
   server-side change can alter it.
2. **Even a working file would not have suppressed the panel.** `showGuestAccountRemind` only ever
   *saves*; it never loads. `loadMarketRecordPoint()` — the only thing that refreshes
   `Globals.market_record_points.cur_market_record_point` from disk — is referenced **only inside
   `helpers/market_record_points.py` itself** (i.e. only from `hasDoneSomething()`/`doSomething()`;
   `script_index.txt` shows no external caller), and those are only called from in-world events that
   are rare or unreachable here: `ui/UIMain.py::_on_match_succeed` (match won **and**
   `player.hallTeamSize >= 2`), `entities/Avatar.py` (`first_on_plane`),
   `entities/iFriend.py` (`first_friend_added`), `entities/iBattleGround.py` (`first_game_done`).
   Nothing calls it at login, on entering the hall, or from `UIMain`'s normal hall path. So for a whole
   session the record stays the pristine `INIT_MARKET_RECORD_POINT` copy:
   `first_download_login_game` starts `True`, the first `showGuestAccountRemind` call of the session
   arms it, and the next one reminds with `last_remind_time == 0` ⇒ `need_remind == True`.

⇒ **Conclusion: this panel is unavoidable by design for a `netease_global` client whose MPay auth
type is GUEST, and it fires once per launch regardless of what our private server does.** The
"state never persists" finding is real and worth documenting (it silently disables the whole `af_*`
market-record-point feature), but it is *not* what makes the nag repeat — fixing persistence alone
would not stop it.

Also note `user_info.txt` carries `"remindGuestBindTimestamp": 0`: `UILogin.readUserInfo/writeUserInfo`
round-trip that field but **no code path ever sets it non-zero, and `showGuestAccountRemind` does not
read it** — it is dead state, not the gate. Do not chase it.

### E. What this settles, and what the remaining options actually are

Ruled out by the above (do not re-attempt these framings):
* **"native `Globals.channel` isn't ready yet"** — irrelevant. `channel.name`/`get_auth_type()` are
  evaluated only *after* the gate has already opened; the gate itself only touches `Globals.channel`
  for truthiness and `Globals.market_record_points`. The handoff's §4 native `get_auth_type`
  decompile is correct but not on the critical path.
* **EmailAuthActivity / session-save ordering / main-thread contention** (Checkpoint 26 work) — those
  explain a different dialog; the nag's chain never involves them.
* **`remindGuestBindTimestamp`** — dead field (see above).
* **"just make the first call skip the popup"** — the 24 h clock starts at the *first* call, so the
  popup can never appear then; it always appears on a later call in a *fresh* state. Any patch that
  only touches the first call does nothing.

Which brings the options down to a short, honest list, because D's corollaries bound them:

1. **"Fix the persistence" is a real defect worth fixing, but it is not this fix.** `get_uuid()`
   returning `''` silently no-ops the entire market-record-point feature (`af_first_match`,
   `af_thirty_min`, `first_friend_added`, `first_game_done`, `first_on_plane`, `first_match_successed`)
   — that is a genuine bug to repair on its own merits. It cannot stop the nag, though: D.2 shows the
   panel's decision never consults the file, and D.1 shows the save cannot succeed at this call site.
   **No server-side change can reach any of this** — the gate consumes only `Globals.channel` (already
   truthy), the in-process market-record container, and a 24 h clock.
2. So for this project the popup is *authentic client behaviour for the exact situation we force
   ourselves into*: MPay auth type is pinned to GUEST (required for
   the BaseApp/Mercury uid shape — see Checkpoint 25) **and** the client is the `netease_global`
   build, and the popup's own guard is `name == 'netease_global' and get_auth_type() == 2`.
   The only levers that make it *never* fire are therefore client-side, not server-side: making the
   channel stop reporting `netease_global` (it comes from the native side via
   `social.get_channel()` in `helpers/channel/channel_init.py::initAppChannel`), or making
   `get_auth_type()` != 2 (forbidden). Note that making `Globals.market_record_points` falsy would
   make the function raise instead of showing the panel — an error path, not a fix.
3. The auto-dismiss route remains explicitly rejected by the project owner (see the handoff and this
   file's history). Do not offer it as the deliverable.

**Diagnostic follow-up (no longer blocking):** *which* of `get_uuid()`'s three preconditions fails is
still unmeasured, and is now only of interest for fixing the persistence defect itself:
   a. A Frida hook that only logs `get_uuid()`'s return value plus
      `ConnectMonitor.getInstance().loginHostRecord` — the native-hook crash from handoff §4 has to be
      fixed first (spawn+resume instead of attach-after-start, an entry-only hook body with no memory
      reads, and check `scratch/ghidra_scripts/AntiTamperSearch.java` output).
   b. The `<SCRIPT>` logcat channel (see F) — watch for an exception out of
      `market_record_points.get_uuid` / `loadMarketRecordPoint` during a launch.
   c. Static: the `setLoginHostInfo`/`connectLoginHost` call graph in `helpers/ConnectMonitor.py`
      (`scratch/disas_connectmonitor.txt`, already dumped) — the weakest option, because that listing
      desyncs around `connectLoginHost` (a `??neox` opcode in that region is being sized wrong, which
      shifts every following offset).

### F. New, reusable: script-side Python tracebacks are in logcat

The engine's `libclaudia` writes full Python tracebacks (with script file + line number) to logcat
under the tag `<SCRIPT>`:

```
adb logcat -d | grep -F '<SCRIPT>'
I/[15:44:12.135] M   <SCRIPT> : Traceback (most recent call last):
I/[15:44:12.135] M   <SCRIPT> :   File "ui\UIMonthlySupplyPackage.py", line 44, in Awake
I/[15:44:12.140] M   <SCRIPT> :   File "common\decorators.py", line 304, in FuncParamInTracebackInnerFunc
I/[15:44:12.142] M   <SCRIPT> : AttributeError: 'NoneType' object has no attribute 'ExtraGiftParam' ((None,) {})
```

This is the cheapest script-side observability this project has (no Frida, no native hook), and it
also proves the decrypted script's line numbers are the same ones the live client reports.
`pytrace.log` in the NeoX root
(`/sdcard/Android/data/com.netease.chiji/files/netease/h45na/pytrace.log`) additionally logs the
module-load stack — useful to confirm which modules are really loaded and in what order.

### G. Tooling added this checkpoint (reusable)

* `scratch/dump_module_funcs.py <script-file> [name-regex]` — resolves a module through
  `scratch/script_module_sigs.json` (falling back to one full `script.npk` scan, which it then caches)
  and disassembles **every** code object with names/consts annotations. Much faster than
  `tools/script_disas.py`, which re-decrypts all modules whenever the sig cache misses.
* `scratch/dump_module_consts.py <script-file> [name-regex]` — prints `varnames`/`names`/`consts` for
  every nested code object; this is what makes listings with many `??neox=N` opcodes reconstructible
  (see C).
* Both are read-only readers over `04_obb/extracted/script.npk`; **no patching capability was added**
  and the write-side pipeline described in handoff §5 still does not exist.
* Local outputs used for this checkpoint: `scratch/disas_market_record_points.txt`,
  `scratch/consts_market_record_points.txt`, `scratch/disas_uilogin_full.txt`,
  `scratch/disas_channel_helper.txt`, `scratch/disas_connectmonitor.txt`,
  `scratch/disas_channel_init.txt`.
* Note for anyone re-running these: the tooling in `tools/` and `scratch/disassemble_targets.py` is
  hard-coded against `C:\Users\Raysoo\Downloads\ROS_RE` (the main checkout, where `04_obb/` and
  `scratch/script_module_sigs.json` live) — the new scripts import from there by absolute path, so
  they work from a git worktree too.

---

## 0.5 Checkpoint 28 (2026-09-26): EmailAuthActivity/Supabase reverted -- project owner decision, isolation-tested

**Context**: after Checkpoint 27 root-caused the "Link Account" popup's trigger chain but left one
open question (which of `get_uuid()`'s two preconditions actually fails), a live attempt to patch
the popup out of existence at the `script.npk` bytecode level (see the now-obsolete write-side
pipeline described below) was followed by a stuck-loading/spinner-overlay symptom on the very next
test launch. The project owner's judgment call, independent of whatever caused that specific stuck
launch, was to stop layering more changes on top of the Checkpoint 25-27 custom-auth work and
**revert it entirely**, returning the project to a purely local, guest-only baseline with no
Supabase or Playit.gg dependency at all.

**Before reverting, an isolation test was run to separate "caused by today's changes" from
"pre-existing"**: a from-scratch guest-only APK (confirmed via string search to predate
`EmailAuthActivity` entirely -- see `scratch/verify_current.apk`) was installed fresh (full
`adb uninstall`/`install` + OBB restore per §0.1), paired with `ros_offline_server_backup`'s
snapshot server (no Supabase, no Playit.gg, nothing from Checkpoints 25-27). On this pristine
baseline, **both symptoms reproduced identically**:
- The stuck-loading spinner overlay (dimmed background, small centered spinner, all touches
  swallowed) appeared during both the pre-title loading segment and on the first-launch
  91-page User Agreement dialog. A single `KEYCODE_BACK` reliably cleared it each time -- this
  is the same not-fully-root-caused `MpayActivity` missing-`finish()` bug documented back in
  Checkpoint 24, not something introduced by any of today's work.
- The "Link Account" nag popup (`UIGuestAccountRemind`) appeared on this pristine baseline too,
  confirming Checkpoint 27's conclusion stands on its own: it is unconditional for any
  guest-type account on the `netease_global` channel, given this environment's `get_uuid()`
  persistence bug. Nothing built in Checkpoints 25-27 caused or worsened it.

**Conclusion**: neither symptom was caused by `EmailAuthActivity`, the Supabase integration, or the
script.npk patch attempt. The revert was a scope decision by the project owner (keep the project
purely local going forward), not a bug-driven rollback -- record this distinction so a future
session doesn't waste time re-diagnosing "what did Checkpoint 25-27 break" when the honest answer,
tested live, is "nothing, but we're not using it anymore."

**What was reverted**, all in the main checkout (not the Cline worktree, which is untouched):
- `AndroidManifest.xml` (in the apktool-decompiled tree used for rebuilds -- see Checkpoint 25's
  toolchain notes for its path): the `LAUNCHER` intent-filter moved back onto
  `com.netease.neox.Launcher`; the `EmailAuthActivity` `<activity>` and `MpayWatcherService`
  `<service>` entries removed entirely (they no longer exist in the manifest at all, not merely
  unreferenced).
- `smali_classes4/` (the dex slot Checkpoint 25's toolchain used exclusively for these two new
  classes) deleted outright -- confirmed the tree still rebuilds cleanly via `apktool b` with it
  gone (`smali`/`smali_classes2`/`smali_classes3`, the original app's own dex slots, are
  untouched).
- `res/xml/mpay_watcher_service_config.xml` (the now-orphaned accessibility-service config)
  deleted.
- `mitm/mitm_serve.py`: the `import supabase_db` block and the entire `/custom/auth/login`
  endpoint handler removed.
- `mitm/supabase_db.py` deleted.
- `mitm/local_baseapp_capture.py`'s several `if supabase_db:`-guarded optional save/load calls
  (player state, inventory) were **left in place** -- they were already written to degrade
  gracefully when the module import fails (`supabase_db = None` in a `try`/`except` at import
  time, confirmed still present and correct), so with the module gone they're simply permanent
  dead branches, functionally equivalent to removal without the risk of hand-editing a
  2000+ line file for no behavioral difference.
- The currently-installed, currently-running device state matches this reverted source exactly:
  guest-only APK (`scratch/verify_current.apk`, predates `EmailAuthActivity`), OBB restored,
  `mitm/local_baseapp_capture.py` running standalone (no `supabase_db`, confirmed by its own
  startup log no longer printing the old `[Supabase] import failed` line at all).
- **Left untouched, on purpose**: `scratch/email_auth_build/` (the EmailAuthActivity/
  MpayWatcherService Java source and its javac/d8/baksmali build pipeline) and this file's own
  Checkpoint 25-27 history above are kept as historical/reference material, not deleted --
  they're inert (nothing in the active manifest or server references them anymore) and cost
  nothing to keep in case a future session revisits per-person auth.
- The `scratch/npk_*.py` script-patching pipeline (rotor encrypt/decrypt, byte-offset-tracking
  parser, OBB zip in-place patcher) built during this same checkpoint **works correctly** and
  is **not the cause** of the stuck-launch that prompted the revert (that repro'd on the
  pristine baseline too, per above) -- it's left in `scratch/` as reusable, verified tooling for
  any future script.npk patch, should the project ever want one again. Do not assume it's broken
  just because of the timing of this revert.

---

## 0.6 Checkpoint 29 (2026-09-26, OPEN/UNRESOLVED): new stuck-pre-title-loading state after stacking two independent fixes

**Context**: after the Checkpoint 28 revert (EmailAuthActivity/Supabase removed, project purely
local), the project owner asked to bring back just the narrow, previously-proven
`MpayWatcherService` auto-BACK-press safety net (not the rest of Checkpoint 25) to deal with the
Checkpoint 24 `MpayActivity`-doesn't-call-`finish()` bug. Independently, in the same shared
decompiled-build worktree (`.claude/worktrees/agent-a26a6b361cc71d3b5`), a different agent session
("Gemini", per its own handoff) had already applied a **real smali-level fix** for the same root
bug. Both changes now coexist in that tree. Stacking them uncovered a **new, different** stuck
state that neither change addresses, and that is not yet understood.

### A. The `ui/g.smali` finish() patch -- verified real (do not re-litigate)

At `smali/com/netease/mpay/oversea/ui/g.smali`, a new method was added:
```smali
.method private a(Lcom/netease/mpay/oversea/ui/g$e;)V
    .locals 2
    const-string v0, "MPay"
    const-string v1, "PATCHED: Closing MpayActivity via a(g$a)"
    invoke-static {v0, v1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    invoke-virtual {p0, p1}, Lcom/netease/mpay/oversea/ui/g;->a(Lcom/netease/mpay/oversea/ui/g$a;)V
    return-void
.end method
```
Verified independently this session, not just taken on the other agent's word:
- `g$e` `.super`s `g$a` (confirmed by reading both class headers), so passing a `g$e` into the
  `a(g$a)` overload is a safe upcast, not a type error.
- `g;->a(Lcom/netease/mpay/oversea/ui/g$a;)V` (the method actually being called, at smali offset
  825) does check `Activity.isFinishing()`, check `instance-of MpayActivity`/`MpayActivityStub`,
  `setResult(...)`, and does call `Landroid/app/Activity;->finish()V` at line 880 -- this is
  genuinely the finish-handling method, not a red herring.
- The new `a(g$e)` method is wired in via the standard Dalvik synthetic-accessor pattern (a
  `static synthetic a(g, g$e)` bridge) from two inner-class call sites, `ui/g$1$1.smali` and
  `ui/g$2.smali` -- i.e. it is reachable from real success-callback code paths, not dead code.
- **Live-fired, confirmed in logcat**: `I MPay: PATCHED: Closing MpayActivity via a(g$a)` was
  observed at least once this session, immediately followed by no further stuck-overlay symptom
  for that particular launch.

This is a real fix for the Checkpoint 24 bug and should be kept. Do not re-derive or second-guess
it without new contradicting evidence.

### B. `MpayWatcherService` re-added as a safety net (not the rest of Checkpoint 25)

Re-built and re-added to the same decompiled tree, standalone:
- `scratch/email_auth_build/src/MpayWatcherService.java` (unchanged from Checkpoint 25 -- always
  was self-contained, no dependency on `EmailAuthActivity`) built via a new
  `scratch/email_auth_build/build_mpaywatcher_only.py` (compiles/dexes/disassembles only this one
  class, leaving `EmailAuthActivity.java` out of the build entirely).
- `AndroidManifest.xml`: re-added the `<service android:name="com.netease.chiji.MpayWatcherService" .../>`
  block (same as Checkpoint 25's), `com.netease.neox.Launcher` **stays** the sole `LAUNCHER`
  (Checkpoint 28's revert was not undone).
- `res/xml/mpay_watcher_service_config.xml` recreated from scratch (the original was deleted, and
  not git-tracked, during the Checkpoint 28 revert -- standard accessibility-service config,
  `typeWindowStateChanged` events, `com.netease.chiji` package filter).
- Rebuilt via `apktool b` + the existing zipalign/apksigner/`adb install -r` pipeline
  (`scratch/rebuild_and_install_apk.py`) -- same debug keystore, so this was a normal `install -r`
  over the existing app, **no uninstall, OBB untouched**.

**Known operational gotcha, reconfirmed this session**: the accessibility service does not
self-enable, and Android disables it on every `force-stop`. The two-liner from Checkpoint 25's
toolchain notes,
```
adb shell settings put secure enabled_accessibility_services com.netease.chiji/com.netease.chiji.MpayWatcherService
adb shell settings put secure accessibility_enabled 1
```
still has to be run **after** the app process has (re)started, every relaunch cycle, for the
watcher to be armed at all -- Checkpoint 25 flagged this as "not yet wired in" and it is **still**
not automated anywhere (not in this repo's `start_server.bat`/relaunch flow, not on-device). A
launch where these two commands were not re-run has no working safety net even though the service
exists in the APK.

### C. The new, unresolved symptom

On at least one clean relaunch this session (fresh `am force-stop` -> `monkey -c LAUNCHER`,
**after** a full `scratch/reapply_env_setup.sh` re-run and a from-scratch `local_baseapp_capture.py`
restart with no stale connections), the client:
- Stayed on the plain pre-title "Loading..." splash (yellow progress bar, **no dimming, no small
  centered spinner** -- visually distinct from the Checkpoint 24/25 stuck-`MpayActivity`-overlay
  symptom) for multiple minutes without any visible change across repeated screenshots.
- `adb shell input keyevent KEYCODE_BACK` had **no effect** (unlike the classic stuck-overlay case,
  where one BACK reliably unblocks it).
- logcat did confirm `ActivityManager: START ... MpayActivity` fired during this window, but
  **neither** the `ui/g.smali` "PATCHED" log line **nor** `MpayWatcher`'s own log lines appeared
  at all for this particular launch -- i.e. neither fix's code path was observed to run. (The
  `MpayWatcherService` half of that is at least partially explained by §B's re-enable gotcha: it
  had not been manually re-armed after this specific relaunch.)
- `local_baseapp_capture.py`'s own log showed `KEYSCAN: SUCCESS` for the new pid promptly, but
  **zero further HTTP or BaseApp/LoginApp UDP activity** from that pid afterward -- i.e. the stall
  looks like it's on the client side, before the client has even made its post-login requests, not
  a server-responsiveness problem.
- OBB files were checked and confirmed intact and correctly sized
  (`main.1117219.com.netease.chiji.obb` = 1977238353 bytes,
  `patch.1117219.com.netease.chiji.obb` = 1523738987 bytes, matching §0.1's documented sizes) --
  ruling out OBB corruption/truncation from this session's several uninstall/reinstall cycles.
- The server's own log separately showed **stale `BASEAPP KEEPALIVE` sends to old, no-longer-valid
  local ports** left over from earlier relaunches this session, persisting across a `force-stop` of
  the client -- a real server-side connection-tracking cruft bug in `local_baseapp_capture.py`
  worth fixing on its own merits (it doesn't detect a client is gone and keeps sending), though not
  yet shown to be the cause of C's stall.

**Not yet tried**: re-running the two `settings put secure ...` accessibility-enable commands
immediately after the process restarts, then relaunching again to see whether an armed
`MpayWatcherService` alone resolves this specific new stall (as opposed to the finish() patch,
which apparently didn't get the chance to run for this launch). This is the most likely next step
and was flagged to the project owner but not yet executed/verified as of this checkpoint.

### D. Honest assessment: this session's churn is a real confound

Before concluding anything more about root cause, whoever continues this should discount how much
happened in a single session on the **same shared decompiled-build worktree**
(`.claude/worktrees/agent-a26a6b361cc71d3b5/scratch/apk_work/decompiled2`):
- At least two agent sessions (this one and a separate "Gemini" session) edited the same tree's
  `AndroidManifest.xml` and smali concurrently, without a lock or turn-taking protocol.
- Several full `adb uninstall`/`install` cycles (APK signature changes, OBB wipes + restores per
  §0.1), plus many same-keystore `install -r` upgrades on top.
- Multiple `pm clear`-adjacent operations and at least one `reapply_env_setup.sh` re-run mid-session.
- Large sequential `adb push` operations (OBB restores, ~3.5 GB) interleaved with frequent
  screenshot/logcat polling -- exactly the pattern §0.3's toolchain notes already warn can destabilize
  the LDPlayer adb bridge and starve the KEYSCAN watcher.

Any one of these could plausibly produce a flaky, hard-to-reproduce stall on top of two otherwise-
verified-correct fixes. **The recommended way to make progress is a clean-slate, single-variable
test**, not more debugging inside this same churned session state:
1. Fully uninstall, restore OBB + `patchVersion` fresh from `04_obb/`/`ros_offline_server_backup/`
   per §0.1, install the current combined APK (`g.smali` finish() fix + `MpayWatcherService`) once,
   from a cold start.
2. Re-run `reapply_env_setup.sh` once, start a single fresh `local_baseapp_capture.py`.
3. Run the two accessibility-enable `settings put` commands once, confirm with
   `adb shell dumpsys accessibility | grep -A2 MpayWatcher` that the service is actually bound
   before launching.
4. One single launch, timed, with continuous `adb logcat | grep -E "PATCHED|MpayWatcher|<SCRIPT>|FATAL"`
   running throughout (not polled after the fact) so the exact moment and cause of any stall is
   captured live rather than inferred afterward.

That protocol has not yet been run end-to-end this checkpoint -- do that before adding any new
theory or patch.

---

## 0.7 Checkpoint 29 continued (2026-09-26): A/B isolation test — B (finish-patch alone) reaches Hall cleanly; regression is not in the patch itself

Ran the clean-slate single-variable protocol from §0.6.D, same server process, same OBB/patchVersion,
same DNAT/cert setup, continuous logcat throughout, one clean launch per candidate.

### Candidate A — last known-good baseline (`base_original_20260925_233735.apk`, md5 `cf15a74f...`)

No `g.smali` finish patch, no `MpayWatcherService`. Full CMD sequence captured
(`scratch/candA_logcat.txt`): two separate `MpayActivity START`s, CMD 11 appeared (never seen in
D's captured stuck run), CMD 20 ("Show Virtual Keyboard") fired normally and was **not** followed
by a stall. After dismissing the pre-existing, already-documented (§0.2/§0.2a) dismissible
"Invalid login. Please log in again." dialog, **reached the title screen cleanly** -- `NeoXMain`
settled to idle (`S` state, ~4% CPU), not spinning. This confirms CMD 20 is not causal (it fires on
both healthy and stuck runs) and gives a concrete healthy-run CMD sequence to diff against.

### Candidate B — A + `ui/g.smali` finish() patch ONLY, no `MpayWatcherService`

Built fresh this checkpoint: `apktool d` on candidate A's own APK (not the shared, churned
`decompiled2` worktree) into `scratch/apk_work/decompiledB`, patched only
`ui/g.smali`'s `a(Lcom/netease/mpay/oversea/ui/g$e;)V` method, rebuilt/aligned/signed via the
standard apktool -> zipalign -> apksigner pipeline, installed clean (uninstall -> install -> OBB
+ patchVersion restore, same as A/D's protocol).

**Important nuance found while building B**: that method slot in candidate A is not a vanilla
stock method -- it already contained a *different*, pre-existing single-purpose patch, logged as
`"PATCHED: Age dialog bypassed"` (presumably from the Sept 22 age-gate testing, see the
`build/apk_agegate_test/` artifacts). The Checkpoint 29 `g.smali` fix (credited to the "Gemini"
agent session) did not add a new method -- it **replaced that existing method's body** with the
finish()-calling version (confirmed via `diff` against the pristine decompile: `.locals 1`->`2`,
log string renamed, one `invoke-virtual` line added calling `g;->a(g$a)V`, i.e. the real finish()
path documented in §0.6.A). Candidate B's patch reproduces exactly this diff, nothing more.

**Result: Candidate B reached the full Hall/Lobby successfully**, end to end. Full observed
sequence, precise step-by-step per the project owner's own walkthrough (more granular than the
first pass recorded above -- this is the authoritative version):

1. Launch -> white screen -> NetEase logo -> image splash "checking for updates".
2. "Loading patch" -- the dismissible "Invalid login. Please log in again." dialog (§0.2/§0.2a)
   appears here, and again once more on the title page after it's reached.
3. **Timing-sensitive branch, newly observed this checkpoint**: on the *first* tap of Confirm,
   if the player is slow to tap Confirm again / interact further, the "Invalid login" dialog
   **keeps reappearing repeatedly**. If instead the player dismisses it and taps through
   **quickly**, it does **not** loop -- it proceeds straight into "Please select controls" with no
   further repeats. This is a real timing/race characteristic of the dialog-retry path, not
   previously documented -- it implies whatever silent-relogin retry loop drives this dialog is
   itself timing-sensitive (plausibly a short-lived token/session window that a fast tap sequence
   stays inside, and a slow one falls outside of, re-triggering the retry). Not yet root-caused at
   the code level -- flagged here as a concrete lead for later, not yet traced into `ui/l.smali`'s
   retry logic.
4. "Please select controls" -> Confirm (after its countdown) -> loading image (fast this time) ->
   back to "Please select controls" (fast) -> loading again (**this one slow**) -> Daily Claim
   panel -> Hall/Lobby.
5. **New detail**: on first entering the Hall, there is still a residual overlay/transition state
   present -- it only fully clears once the player taps **START**, after which the Hall is clean
   with no overlay (avatar rendered, motorcycle prop, 999999/999999 dev currency, START button,
   side menu all present and interactive).

Verbatim, as reported by the project owner (kept alongside the structured breakdown above so no
wording/nuance is lost to paraphrasing):

> launch white screen > netease logo > image splash checking for updates > loading patch with
> invalid login > title page nagpapakita invalid login > first tap show again invalid login kapag
> matagal kang pumindot is magpapakita paulit ulit yung invalid login kapag binilisan mo mag load
> sya sa select control > loading image > loading image mabilis sya > balik select control mabilis
> > loading ulit matagal and then > daily claim > start sa hall para mawala overlay click start >
> hall lobby na wala ng overlay ganyan flow ngayon at issue

**This overall shape (slow-load / loop-back / slow-load / Daily Claim / Hall) matches the
already-documented Checkpoint 25 follow-up note** (see §0.3), but the timing-sensitivity of the
"Invalid login" repeat (step 3) and the START-click-clears-overlay detail (step 5) are new,
more precise observations from this checkpoint that were not previously on record. Neither is the
Checkpoint 29 permanent stuck-loading regression -- CPU stayed idle throughout (`NeoXMain` never
exceeded single-digit % during any of the "slow loading" segments observed), and the flow always
eventually completed to a fully interactive Hall.

One more real-but-separate wrinkle observed during B's run: the pre-existing dismissible "Invalid
login" dialog (§0.2/§0.2a) recurred **on repeated PLAY taps** during manual testing/spamming, each
time correlating with a fresh `MpayActivity` START + CMD 6/CMD 11 in logcat -- consistent with
Checkpoint 22's original description ("appears both automatically pre-title and on every PLAY
tap"). During one of these cycles `MpayActivity` became `mResumedActivity` and stayed there
(the classic Checkpoint 24 touch-capturing overlay state) -- CPU stayed idle/low the whole time
(not the CMD-20-adjacent busy-spin from D), and a single manual `KEYCODE_BACK` press immediately
released it back to `com.netease.neox.Client`, exactly per the original Checkpoint 24 workaround.
This is expected: Candidate B intentionally has no `MpayWatcherService`, so this particular
resumed-overlay path (one that apparently doesn't route through the patched `g$1$1`/`g$2` bridge
call sites -- see §0.6.A) has no automatic safety net in this build. Not evidence of a new bug --
it's the pre-existing, already-understood behavior this project has documented since Checkpoint 24.

### What this settles

**The `ui/g.smali` finish() patch, in isolation, does not cause the Checkpoint 29 permanent
stuck-loading regression.** Candidate B completes the entire login-to-Hall flow reliably using
only this patch. This directly weighs against the hypothesis that automatic/earlier `finish()`
timing (vs. the old manual-BACK workflow) is itself the source of a lifecycle/focus/IME race --
B *is* that automatic-finish() timing, alone, and it does not reproduce D's hang.

**This shifts the regression boundary to Candidate C (`MpayWatcherService` alone) or to the
interaction between B and C when stacked together (= Candidate D, the current combined build).**
Plausible mechanism, not yet verified: the accessibility service's auto-`GLOBAL_ACTION_BACK` and
the smali patch's `finish()` call could both be racing to close the *same* `MpayActivity` instance
at nearly the same time (watcher fires after its 10s-resumed threshold; patch fires immediately on
its specific success callback) -- a double-close, or a BACK dispatched into an activity mid-
transition from `finish()`, could plausibly desync whatever state the post-login loading sequence
depends on. This is a hypothesis for the next step (building and testing Candidate C in isolation,
then D again with fresh logcat), not yet confirmed.

**Next step**: build Candidate C (A + `MpayWatcherService` only, no `g.smali` patch) the same way
B was built (fresh `apktool d` off candidate A, not the shared churned worktree), run the same
clean-slate single-launch protocol, and compare. If C alone also reaches Hall cleanly, the
regression is specifically in the B+C interaction, not either patch alone -- narrowing the next
investigation to the timing/ordering between the accessibility service's BACK dispatch and the
smali patch's finish() call on a shared `MpayActivity` instance.

---

## 0.8 Phase 0 timeline instrumentation on Candidate B (2026-09-26): CONFIRMED root cause of duplicate loading + a new CREATE-stuck symptom

Per the project owner's request, `scratch/candidates/candidate_B_known_good.apk` (SHA256
`27bebaceb9f1e97759aa184849af14b7d51bbdcccb860e83162158ce8f7cc590`) was frozen as the immutable
baseline before any further experiments (git HEAD at freeze time: `f9f63dd2`). Logs from that
freeze are preserved under `scratch/candidates/logs_candB_baseline/`.

A timeline-instrumentation harness was built and run clean (continuous full `adb logcat`
+ a 1s-interval PowerShell screenshot loop, both armed **before** launch, per the project owner's
explicit pre-run checklist) against this frozen Candidate B build. Two runs were done
(`scratch/timeline_run1/`, `scratch/timeline_run2/`) -- the second is the clean, gap-free one
referenced below.

### A. Invalid Login timing (Phase 1) -- refined, not fully resolved

- T4 (first "Invalid login. Please log in again." dialog) appears within ~1s of the first
  `MpayActivity START` in every observed case -- it is tied to an MpayActivity (re)launch event,
  not a fixed delay after the patch-loading splash.
- **Every fresh MpayActivity cycle can (but does not always) redisplay the dialog** -- this
  includes cycles triggered by tapping **PLAY**, not only the automatic pre-title one. This is a
  more precise trigger correlation than the earlier "fast vs slow dismiss" framing.
- Two controlled tests this run: one Confirm tap deliberately delayed ~47s (T5 far later than
  instructed) resulted in **no further repeat** on title; a later PLAY-tap cycle with a **~16s**
  delay before Confirm **did** trigger further MpayActivity retries. A fast, immediate Confirm tap
  (project owner tapping directly, sub-second) still triggered **8 rapid MpayActivity retry
  cycles in ~8 seconds** (21:08:58.812 -> 21:09:26.908, ~1-1.5s apart) before finally breaking
  through to a successful `createBasePlayer`. **This contradicts a simple "fast dismiss avoids the
  loop" rule** -- fast dismissal this run still produced the longest retry burst observed all
  session. HYPOTHESIS, not confirmed: the real variable may be *how many* MpayActivity cycles have
  already fired this session (retry-count-based backoff/give-up), not raw human reaction time.
  NOT YET TESTED: instrumenting the actual retry-count/condition inside `ui/l.smali`'s retry path.

### B. CONFIRMED ROOT CAUSE -- the "duplicate loading" / second Select-Controls-adjacent cycle (Phase 4)

Directly observed in `mitm/local_baseapp_capture.py`'s own server log
(`scratch/timeline_run1/server.log`), not inferred:

```
21:09:27.536  LOGINAPP UDP RECV 273 bytes from 127.0.0.1:51169      <- 1st LoginApp handshake
21:09:27.651  BASEAPP KEYSCAN: using NEW key for ('127.0.0.1', 51170)
21:09:27.654  BASEAPP STAGE 1: createBasePlayer(Account type=38, eid=1)
21:09:27.957  BASEAPP STAGE 3: createBasePlayer(Athlete type=51, eid=1, stream=5771 B)
21:09:28.058  BASEAPP STAGE 4: Athlete.showSelectCharacter([])          <- 1st "Select Controls"
21:09:33.153  Athlete.onCreateCharacter(ret=1)
21:09:33.204  Athlete.onRoleCreateSuc(10002)
21:09:33.255  Athlete.updateBaseCharacter(10002)
21:09:33.306  Athlete.updateBaseNickname(b'Dev | Raysoo')
21:09:33.407  Athlete.enterHall(True)                                   <- 1st cycle "complete"

21:10:57.554  LOGINAPP UDP RECV 273 bytes from 127.0.0.1:58828      <- 2nd LoginApp handshake,
                                                                          NEW ephemeral port
21:10:57.682  BASEAPP KEYSCAN: using NEW key for ('127.0.0.1', 58829)
21:10:57.693  BASEAPP STAGE 1: createBasePlayer(Account type=38, eid=1)     <- full repeat
21:10:57.992  BASEAPP STAGE 3: createBasePlayer(Athlete type=51, eid=1, stream=5771 B)
21:10:58.093  BASEAPP STAGE 4: Athlete.showSelectCharacter([])          <- 2nd cycle
21:11:00.595  Athlete.onCreateCharacter(ret=1)
21:11:00.646  Athlete.onRoleCreateSuc(10002)
21:11:00.696  Athlete.updateBaseCharacter(10002)
21:11:00.747  Athlete.updateBaseNickname(b'Dev | Raysoo')
21:11:00.848  Athlete.enterHall(True)
```

**The client itself re-initiates a brand-new LoginApp/BaseApp handshake from a new local ephemeral
port, exactly 90.018 seconds after the first handshake** (21:09:27.536 -> 21:10:57.554). This is
not a server bug and not a UI redraw glitch -- `local_baseapp_capture.py` is simply answering a
second, genuine "new player" session the client itself opened. This matches option **D** from the
project owner's Phase 4 hypothesis list ("LoginApp/BaseApp reconnect") -- **CONFIRMED**, not
hypothesis, via direct timestamp correlation in the server's own log.

**Live client-side observation during this exact window (project owner, real-time)**: the
user-visible symptom of this second cycle was **not** the "Select Controls" panel reappearing --
it was the **loading/tips screen returning a second time** (the panel itself was only seen once;
the loading screen was what repeated). This refines/corrects the earlier informal description in
§0.7's verbatim flow ("balik select control") -- the more precise description, confirmed by
directly watching this run, is a **second loading period**, not a second Select-Controls UI panel,
that corresponds to the second `createBasePlayer` cycle above.

**HYPOTHESIS, not yet confirmed**: why does the client reconnect at ~90s? The round number and
consistency (single data point so far, needs repeat runs to confirm it's fixed-interval and not
coincidental) suggests a client-side session/heartbeat timeout constant, not a random race. NOT
YET TESTED: whether a server-side keepalive/ack sent within that 90s window would suppress the
reconnect entirely (would directly prove the timeout theory and give a one-line server-side
mitigation if true) -- this is the strongest next investigation target for Phase 4, and does not
require any client-side patch.

### C. NEW SYMPTOM this run, not previously documented: a full Character Creation prompt, with a possibly-unresponsive CREATE button

In this specific run, the second (~90s-later) cycle surfaced client-side not as a loading screen
that resolves on its own, but as a **full "Tap to Enter NAME" / CREATE character-creation screen**
-- confirmed by the project owner as **the first time this exact screen has been observed** in
this project's testing history. Screenshots: `scratch/timeline_run2/shots/211202_752.png` onward.

While on this screen, the project owner reported **tapping CREATE appears to have no effect**.
Cross-checked against the server log for the same window (`scratch/timeline_run1/server.log`,
~21:13:29-21:13:31): the only traffic present is a repeating, unrelated `versionPointIdentity`
push/ack exchange (`checkpoint_id=20`, same 24-byte payload, every ~0.5s) -- **no
character-creation-related client request was observed reaching the server while CREATE was being
tapped**. HYPOTHESIS, not confirmed: the two overlapping sessions (the original from 21:09:27 and
the reconnect from 21:10:57) may be leaving the client's UI bound to a stale/wrong session
context, so CREATE taps either target the wrong (already-resolved) session or never get dispatched
into a network call at all. NOT YET TESTED: whether force-stop + relaunch recovers cleanly, whether
this repros on a from-scratch launch (not just after the ~90s reconnect), and whether the
`versionPointIdentity`/`checkpoint_id=20` repeating exchange is related at all or just unrelated
background noise (it also appears in earlier, non-stuck runs, e.g. `scratch/timeline_run1/server.log`
lines 3026+ from run1 at 21:09:12, well before any stuck state -- weak evidence it's unrelated).

### D. Summary table (CONFIRMED vs HYPOTHESIS vs NOT YET TESTED, per the project owner's labeling requirement)

| # | Finding | Status |
|---|---|---|
| 1 | CMD 20 ("Show Virtual Keyboard") occurs on both healthy and stuck runs, not causal | CONFIRMED (Checkpoint 29/§0.7) |
| 2 | `ui/g.smali` finish() patch alone does not cause permanent stuck-loading | CONFIRMED (§0.7, Candidate B reaches Hall) |
| 3 | Invalid Login dialog is tied to MpayActivity (re)launch events, including PLAY-triggered ones | CONFIRMED (this run) |
| 4 | "Fast dismiss avoids the repeat loop" | NOT CONFIRMED -- contradicted by the 8-cycle fast-tap burst this run |
| 5 | Client re-initiates a full new LoginApp/BaseApp session ~90s after the first | CONFIRMED (timestamp correlation, this run) |
| 6 | This reconnect is what drives the second `createBasePlayer`/loading cycle | CONFIRMED (same server log) |
| 7 | Second cycle manifests as a repeated loading screen, not a repeated Select-Controls panel | CONFIRMED (live observation, this run) |
| 8 | Second cycle can also manifest as a full Character Creation prompt | CONFIRMED observed once; frequency/trigger conditions NOT YET TESTED |
| 9 | CREATE button is unresponsive in this state | CONFIRMED observed once (no server-side RPC seen); root cause HYPOTHESIS only |
| 10 | Why the client reconnects at ~90s (fixed timeout vs coincidence) | HYPOTHESIS -- single data point, needs repeat runs |
| 11 | Server-side keepalive could suppress the reconnect | HYPOTHESIS -- not yet tested, no client patch required to test it |

**No patches applied.** Per explicit instruction, this checkpoint is read-only investigation only.
Candidate B's frozen APK/SHA256 in §0.7/above is untouched. Raw artifacts for this checkpoint:
`scratch/timeline_run1/server.log`, `scratch/timeline_run1/logcat_full.txt`,
`scratch/timeline_run2/logcat_full.txt`, `scratch/timeline_run2/shots/*.png`.

---

## 0.9 Why the client reconnects at ~90s (2026-09-26): the client goes silent for 64s, not the server

Continuing §0.8 with a deeper read of the *existing* `scratch/timeline_run1/server.log` (the same
session already analyzed -- this did not require a new run to extract). Only **one** real
R0-R3 data point exists so far (see table below); **repeat runs to confirm reproducibility are
still NOT YET TESTED** and are the natural next step, not yet executed this checkpoint.

### A. R0-R3 for the one available data point

| Marker | Timestamp | Value |
|---|---|---|
| R0 (1st LoginApp handshake) | 21:09:27.536 | client port 51169 |
| R1 (1st BaseApp session starts) | 21:09:27.651 | KEYSCAN picks up new key for port 51170 |
| R2 (1st enterHall) | 21:09:33.407 | |
| R3 (2nd LoginApp handshake) | 21:10:57.554 | client port 58828 (**new ephemeral port**) |
| R3 - R0 | **90.018s** | |
| R3 - R1 | 89.903s | |
| R3 - R2 | 84.147s | |

### B. Traffic in the R2-R3 window -- what's actually periodic, and what stops

Three independent periodic exchanges are present in this window, and they behave very differently:

1. **Server-side `setGameTime` keepalive, sent to the correct active port (51170), every 5.000s**
   (`21:09:37.762, 21:09:42.763, ...`). **This never stops** -- confirmed by grepping the full log
   far past the reconnect (still sending to the now-abandoned port 51170 as late as `21:20:07.877`,
   ten minutes later). This rules out "the server stopped sending keepalives" as a cause.
2. **Server-side `setGameTime` keepalive ALSO sent to a stale, unrelated port 53219** every 5s,
   the whole time -- this is the already-documented (§0.3 Checkpoint 25 toolchain notes) stale-
   connection-tracking cruft in `local_baseapp_capture.py`. Confirmed still present; confirmed
   harmless to this specific investigation (it's a different, leftover client instance's port from
   earlier in the session, not related to the 90s reconnect).
3. **Client-initiated 24-byte request, decrypting to a fixed `checkpoint_id=20`
   "This document s..." payload, answered by the server with an identical
   `versionPointIdentity push id=94 checkpoint_id=20` reply every time.** This one starts right
   after `enterHall` (21:09:33.927), has one longer 9.86s gap, then settles into a **steady
   ~0.53s interval** from 21:09:43.782 onward. It does **not** accelerate, degrade, or show any
   sign of a failing/retrying exchange -- it looks like a normal, working, steady-state poll.

### C. THE key finding: the client goes completely silent 64 seconds before it reconnects

The last packet received from the client on the original session (port 51170), of any kind, is:

```
21:09:53.557  BASEAPP UDP RECV 32 bytes from 127.0.0.1:51170   (an UPSTREAM CALL batch)
```

**Nothing else arrives from that port ever again** -- not the steady 0.53s `checkpoint_id=20`
poll, not any other traffic -- for **63.997 seconds**, until the fresh LoginApp handshake at
21:10:57.554. The server, meanwhile, keeps faithfully sending its 5s `setGameTime` keepalive into
the void the entire time (per §B.1) -- it is never acknowledged, but it never stops being sent
either.

**This 64-second silence begins right around T11/T12** (Confirm tap on "Please select controls"
-> first loading screen start, timestamped independently in §0.8 at ~21:09:54-55.117) -- i.e. the
client stops servicing its own BaseApp UDP socket at almost exactly the moment the first "slow
loading" screen (Phase 3) begins, and only resumes (via a full reconnect, not a resume) once that
loading finally lets go of whatever was blocking it.

### D. Report, in the requested format

- **CONFIRMED**: The client, not the server, is the party that goes silent. The server's periodic
  `setGameTime` keepalive to the correct, still-open port never stops (proven past the reconnect,
  10 minutes later).
- **CONFIRMED**: The client-initiated `checkpoint_id=20` poll is a normal, steady, non-failing
  exchange right up until the client goes silent -- it does not degrade or retry-storm beforehand.
- **CONFIRMED**: The silence window is 63.997s, starting at 21:09:53.557 -- essentially coincident
  with the Confirm-tap / first-loading-start moment already timestamped in §0.8.
- **DISPROVEN (for this data point)**: "a missing periodic server response/ack causes the
  reconnect." The server's expected periodic response was never missing -- it kept sending,
  unacknowledged, the whole time. A server-side fix of "send the correct response earlier" is
  therefore unlikely to prevent the reconnect, because the client was not processing incoming UDP
  at all during the silence window, regardless of what the server sent.
- **HYPOTHESIS, strongly favored by this evidence**: the reconnect is triggered by a **client-side
  watchdog/timeout keyed off socket inactivity** (on the order of ~60-65s), which fires because the
  client's own main thread stops servicing the BaseApp socket during a long synchronous
  scene-load operation (the same one responsible for the already-documented "slow first loading"
  symptom, Phase 3) -- not because anything is missing from the server's side of the exchange.
  This reframes Phase 3 and Phase 4 as **one root cause, not two**: whatever makes the first
  post-Confirm loading slow is the same thing that starves the client's own network thread long
  enough to trigger its self-reconnect logic.
- **NOT YET TESTED**: repeat runs (2+ more) to confirm the ~64s silence window and ~90s
  handshake-to-handshake interval are consistent and not coincidental to this one run. Static
  analysis of client scripts/native code for the actual timeout constant (search terms from the
  task spec: `90`, `90000`, `reconnect`, `heartbeat`, `timeout`, `relogin` -- not yet run against
  the decrypted `script.npk` or `libclient.so`). The controlled server-side experimental variant
  (sending an extra/different keepalive during the silence window) is now **lower priority** given
  the disproven "missing server response" framing above, but could still be tried as a cheap
  negative-control test (predicted to NOT prevent the reconnect, which would further support the
  client-side-watchdog hypothesis if confirmed).

No patches applied this checkpoint either -- read-only log analysis only, per instruction.

---

## 0.10 New symptom found during Phase 10 forensic audit + control run (2026-09-26): a stuck WebView panel after every Confirm tap

Before the timing control run itself, a full read-only forensic audit confirmed the environment is
clean: the installed APK is byte-identical to the frozen `candidate_B_known_good.apk`
(SHA256 `27bebace...`), no EmailAuthActivity/Supabase/MpayWatcherService/Playit residue exists in
the APK, on-device preferences, or the active packet path (LDPlayer's DNAT sends everything
straight to `172.16.1.2` -> `local_baseapp_capture.py`; Playit, though running on the Windows host,
has no listener on any ROS port and is proven not to be in the traffic path). Full matrix and
per-question answers are in the session log; the short version is **CONFIRMED clean environment,
safe to run the control test**.

### The new finding, during the control run itself

On the very next clean launch (Run 1 of the planned 3-run Phase 10 control test), a previously
undocumented UI element appeared: a **full-width white panel with a dark left sidebar, an X close
button top-left, and an indefinite spinning loader centered in the white area** -- visually
distinct from the known "Invalid login" `AlertDialog` (screenshot:
`scratch/phase10_run1/shots/` around 21:40 local). `dumpsys activity activities` confirmed
`mResumedActivity` stayed on `com.netease.neox.Client` the entire time this panel was visible --
**this is an in-game overlay/WebView panel rendered inside the Client activity, not a separate
Android Activity or MpayActivity instance.**

Per the project owner's own real-time observation, confirmed reproducible:
- **This panel appears immediately after every Confirm tap** on the "Invalid login. Please log in
  again." dialog -- both the first occurrence (during patch-loading) and later occurrences
  (post-PLAY, post-title).
- Most of the time it **resolves quickly on its own** (matches what was seen during patch-loading).
- At least once this run, it **did not resolve** and stayed on screen indefinitely with the spinner
  never completing, while logcat showed `MpayActivity` continuing to cycle in the background
  (`ActivityManager: START ... MpayActivity` firing repeatedly every few seconds during this exact
  window).

**HYPOTHESIS, not yet confirmed**: this panel is a strong candidate for the actual mechanism behind
the previously-observed "Invalid login repeats when interaction is slow/fast is inconsistent"
finding from §0.8/§0.9 -- rather than dismiss-timing being the variable, the real gate may be
**whether this WebView panel's own content load succeeds or hangs**. If its content fetch hangs
(e.g. a GM webview panel, ad-network webview, or a web-based notice fetch that depends on an HTTP
endpoint this local server doesn't fully emulate), that could itself be what's re-triggering
MpayActivity/the Invalid Login retry cycle, not raw human reaction time. This reframes the entire
Invalid-Login-repeat investigation from §0.8's "Phase 1" and is a **stronger, more specific lead
than the earlier fast/slow-dismiss framing**, which was never fully consistent across runs.

NOT YET TESTED: identifying which Activity/View class renders this panel (candidates from the
manifest audit in §Phase-2: `GMWebviewActivity`, `GMWebviewActivityEx`, or an ad-network webview
like `AudienceNetworkActivity`/`AdActivity`/`GoogleApiActivity` -- though those are separate
Activities per the manifest, which would show up as a different `mResumedActivity`; since
`mResumedActivity` never left `Client`, this is more likely a `Cocos2d`/NeoX-internal in-engine
WebView widget, not one of the manifest's declared Activities). Capturing `dumpsys window windows`
and a full logcat grep for `WebView`/`chromium`/network-request tags while this panel is stuck is
the natural next diagnostic step, deferred here since the project owner asked to document first.

This finding does not change any conclusion from §0.7/§0.8/§0.9 -- it adds a new, more specific
candidate mechanism for the already-known Invalid-Login-repeat behavior. No patch applied; this
is still read-only observation, and Phase 10's timing control run (R0-R10, 3 runs) is still in
progress/incomplete as of this commit.

---

## 1. Standing Rules (Strict Constraints)
- **Local/LAN Only**: Never interact with real production NetEase servers.
- **Zero Guesswork**: Every packet format, entity type, and method index must be verified by live memory inspection or Ghidra decompilation.
- **Commit Frequently**: Always make atomic git commits with clear descriptive messages.
- **Mobile Only**: Do not confuse with PC client structures — use `com.netease.chiji` Android constants.

---

## 2. Gate Milestones Status

| Gate | Component | Protocol | Status | Resolution |
|:---|:---|:---|:---:|:---|
| **Gate 0** | Patch / CDN Server | HTTP :80/:443 | **PASS** | `mitm_serve.py` / `local_baseapp_capture.py` bypasses patch checks. |
| **Gate 1** | UniSDK / Auth / Sigma | HTTP :80/:443/:8443 | **PASS** | Guest auth token and Sigma keypoints handled cleanly. |
| **Gate 2** | LoginApp Handshake | Mercury UDP :25000 | **PASS** | 4-byte LE ReplyID correlation @ wire offset 5. Blowfish encrypted `LoginReplyRecord` redirecting to BaseApp :25010. |
| **Gate 3** | BaseApp Handshake | Mercury UDP :25010 | **PASS** | `createBasePlayer(Account, type=38, eid=1)` accepted; client packet #0 decrypted; 864-byte `Account.handshake` ACKed; `Account.onChannelLogin(19)` + `Account.onLogin(18)` sent. Client reported `accountOnBecomePlayer`, `onChannelLogin(code=0)`, and `Login Succ`. |
| **Gate 4** | Character Select / Lobby | Mercury RPC / DEF | **PASS (Lobby renders)** | **2026-09-20: the real 3D Lobby renders** (START, Ranked, Invite 0/0, currency bar, side menu) using the runtime-DataType-driven Athlete stream (`python scratch/gen_stream_v3.py`). The hall UI is **non-deterministic**: some runs show the avatar model and a clean solo state, others show duplicated overlapping promo boxes, a stray "Leave Team" and no avatar until the Ranked page is visited. Open: `extconfigs.getServiceAccessPoint` TypeError in `onBecomePlayer`. |

---

## 3. Verified Entity Type IDs (Live Memory Citation: `libclient.so:base + 0x45785f0`)

| Entity Type ID | Hex | Entity Class Name | Role / Notes |
|:---:|:---:|:---|:---|
| **37** | `0x25` | `LoginProxy` | Interim proxy |
| **38** | `0x26` | `Account` | **Base Account entity** (verified live in heap `pPlayerEntity_` @ `0x763892626820`, `eid=1`) |
| **39** | `0x27` | `BattleAccount` | In-battle proxy |
| **40** | `0x28` | `Avatar` | In-game avatar |
| **51** | `0x33` | **`Athlete`** | **Lobby player entity** (CRITICAL: Do NOT use 56; 56 is `RobotShadow`!) |
| **56** | `0x38` | `RobotShadow` | Not Athlete! |

---

## 4. Verified Client Method Vectors (Live Memory Citation: `EntityType[id] + 0x1e8`)

### A. `Account` (Type 38)
- **`[18] msgid=146`**: **`onLogin(INT32 ret, STRING reason)`** (`ret=0, reason=''`)
- **`[19] msgid=147`**: **`onChannelLogin(UINT8 ret, PYTHON sauth)`** (`ret=0, sauth={'uid':'900000001', ...}`)

### B. `Athlete` (Type 51) — 1131 Methods Total
- `[  54] msgid= 182`: `onEnterHallTeam`
- `[  59] msgid= 187`: `onLeaveHallTeam()` **(does NOT prevent the `hallTeamData` crash — retracted; see below)**
- `[1081] msgid=1209`: `onRefreshMSToken(STRING, STRING)`
- `[1082] msgid=1210`: `onKickOff()`
- **`[1083] msgid=1211`**: **`showSelectCharacter(ARRAY<STRING> oldNames)`** (Preloads 3D scene; required before enterHall)
- **`[1084] msgid=1212`**: **`onCreateCharacter(BOOL success, STRING reason)`** (Character creation confirmation)
- **`[1085] msgid=1213`**: **`onRoleCreateSuc(INT32 roleId)`** (Role create success, roleId=10002)
- **`[1087] msgid=1215`**: **`updateBaseCharacter(INT32 charType)`** (10002=MALE, 10005=FEMALE per `getCharactersData`)
- **`[1088] msgid=1216`**: **`updateBaseNickname(STRING nick)`**
- **`[1091] msgid=1219`**: **`enterHall(BOOL isFirstLoginOfDay)`** (Lobby entry!)
- `[1103] msgid=1231`: `onLogin(INT32, STRING)`


---

## 5. BigWorld Mercury Extended Method Wire Encoding (Reversed from `libclient.so:0xad03b0` & `0xa478a8`)

For entities where method index exceeds the single-byte limit:
1. **Threshold**:
   $$\text{div} = \lfloor(\text{num\_methods} + 192) / 255\rfloor$$
   $$\text{threshold} = 62 - \text{div}$$
   - For `Athlete` (`num_methods = 1131`): $\text{div} = 5 \implies \text{threshold} = 57$.
2. **Encoding**:
   - If $\text{method\_index} < \text{threshold}$: $w_1 = \text{method\_index}$, extra byte = `b''`.
   - If $\text{method\_index} \ge \text{threshold}$:
     $$\text{diff} = \text{method\_index} - \text{threshold}$$
     $$w_1 = \text{threshold} + \lfloor\text{diff} / 256\rfloor$$
     $$\text{extra\_byte} = \text{diff} \pmod{256}$$
3. **Wire Message ID & Width**:
   $$\text{msgID} = 128 + w_1$$
   $$\text{width} = 2 \text{ bytes (uint16 LE) if } w_1 < 64 \text{ else } 1 \text{ byte (uint8)}$$
4. **Wire Payload**:
   $$\text{payload} = [\text{entity\_id: uint32 LE}] + [\text{extra\_byte}] + [\text{args}\dots]$$

### Proof of Client-Side Execution (`scratch/live_logcat_verified_wire.txt`)
Sending `showSelectCharacter` (idx 1083) produced:
`MethodDescription::getArgsAsTuple: Failed to get arg 0 (of type ARRAY of STRING) for method showSelectCharacter from the stream.`
`MethodDescription::callMethod: Couldn't stream off args for showSelectCharacter correctly, aborting method call!`
The client parsed the entity ID, decoded method 1083, and entered `MethodDescription::callMethod` for `showSelectCharacter`!

---

## 6. Official Server Ground Truth Sequence & `_realEnterHall` Resolution

### A. Proof of `updateBaseNickname` Success
- Telemetry in `mitm/captures/SERVE_B.txt:32050` verified: `"user_name": "Survivor"` was populated on the client immediately following `updateBaseNickname("Survivor")` (was empty prior to call).

### B. Root Cause of `_realEnterHall` Crash
- In `entities\Athlete.py:656`:
  `sc = GameObject.Find('Scene')`
  `ss = sc.GetComponent('SceneSystem')`
  `ss.loadHallScene(onHallSceneReady)`
- Calling `enterHall` without preloading the scene returned `sc = None`, raising `AttributeError: 'NoneType' object has no attribute 'GetComponent'`.
- `Athlete.showSelectCharacter([])` (idx 1083) is the required method that runs `_loadDefaultScene()` $\to$ `HALL_BASE_SCENE` $\to$ creates the `Scene` GameObject!

### C. `SequenceDataType` Wire Encoding Fix for `showSelectCharacter`
- Disassembly at `libclient.so:0x9a4b74-0x9a4b88`:
  `SequenceDataType` reads a **4-byte uint32 LE length prefix** (`mov w1, #4; blr stream.read; ldr w21, [x0]`).
- For empty `ARRAY<STRING>` (`oldNames = []`), the correct argument is:
  `struct.pack('<I', 0)` (`b'\x00\x00\x00\x00'`, 4 bytes).

---

## 7. Checkpoint 18: Definitive Root Cause of the Two Missing Attributes & Teardown

See detailed breakdown in [HANDOFF_TO_CLAUDE_WEEKENDPUSH_LOBBY.md](file:///c:/Users/Raysoo/Downloads/ROS_RE/scratch/HANDOFF_TO_CLAUDE_WEEKENDPUSH_LOBBY.md).

### The Root Cause:
1. `iHallTeam.onCreate()` line 45 sets `self.hallTeamData = {}`.
2. `Athlete.onCreate()` line 365 sets `self.timerRefreshMSToken = None`.
3. Both methods are chained via `safesuper(Class, self).onCreate()` over 143 interfaces.
4. In `entities\iWeekendPush.py:14`, `onCreate` calls `tryActiveWeekendPushRedBadge()`.
5. At line 66, it does `set(rewardsCanGet) - set(self.weekendPushRewardsHaveGotten)`.
6. Because `weekendPushRewardsHaveGotten` has `<Flags> BASE_AND_CLIENT </Flags>` and NO default in `entity_0376.xml`, sending an empty stream in `createBasePlayer(Athlete)` initializes it as `None`.
7. `set(None)` raises `TypeError: 'NoneType' object is not iterable` (verified in `live_logcat_charcreate_test.txt:153421`).
8. This unhandled `TypeError` **aborts the unwinding of the entire `onCreate()` chain**!
9. Consequently:
   - `self.hallTeamData = {}` never runs $\to$ `AttributeError: hallTeamData` in `UIModes.on_enter`.
   - `self.timerRefreshMSToken = None` never runs $\to$ `AttributeError: timerRefreshMSToken` in `onBecomeNonPlayer`.
   - `onBecomeNonPlayer` crash causes `setPlayer::new player is null` $\to$ `App CMD 31` (Quit) $\to$ `Level Destroy (-1)`.

### Resolution Strategy:
Neutralize `TypeError` in `tryActiveWeekendPushRedBadge` or supply default in `createBasePlayer` property stream.
Once `onCreate()` finishes cleanly, `hallTeamData` and `timerRefreshMSToken` exist automatically, allowing the client to transition past the "Please select controls" screen (`hall_entry_t12s.png`) into the interactive 3D Lobby!


---

## 8. Checkpoint 20 (2026-09-20): property-stream ground truth (supersedes anything older that conflicts)

- **`createBasePlayer(Athlete)` property stream is real and parsed sequentially** (`EntityType::newDictionary` ->
  `FUN_00acf8ac`, flag mask `0x0b`): a bare ordered concatenation of the 454 properties passing
  `(f&0x10)==0 && (f&0x08) && (f&0x06)`. No bitmask, no index tags. (The old "domain=0 + non-empty stream =
  exception" claim was wrong.)
- **Fixed-size arrays have NO count on the wire.** `SequenceDataType::createFromStream` (`FUN_00aa4b14`) reads the
  4-byte count only when the DataType's fixed size (`+0x30`) is 0. `childBaseClientPropertyList` and
  `childClientPropertyList2` are `ARRAY <of> FIXED_DICT ... <size> 1 </size>`: the element (a large FIXED_DICT)
  is written inline with no count. Encoding them as "count 0" desyncs the whole stream from ordinal 207.
  The generator must be built from the **runtime** DataType tree, not XML regexes (`scratch/dump_runtime_types.py`).
- **One Mercury packet carries at most ~1459 B of `createBasePlayer` stream.** Larger messages must be fragmented
  (`send_mercury_message` in `mitm/local_baseapp_capture.py`); an oversize single datagram is dropped by the
  client with `EncryptionFilter::recv: Dropping packet ... illegal wastage count`, which looks like "the entity
  layer went silent" and logs only ONE `createBasePlayer` instead of two.
- **Session-key scan:** `fast_find_session_key()` must scan every heap region >= 2 MB (was > 16 MB, which skipped the
  10 MB region holding the EncryptionFilter on some launches). Load base and heap layout change every launch.
- **Use ONE adb binary** (LDPlayer 34.0.4 vs SDK 37.0.1 fight over the adb server); start the server with `ADB_PATH`.
- **Do not trust "no error" as "in sync".** Verify alignment with a specific client error whose numbers match a
  known stream offset (see `06_notes/GHIDRA_PACKET_PARSER_TRACE.md`, Checkpoint 20).

- **Milestone (2026-09-20):** with the v3 stream the client consumes all 2178 B exactly (no DataType errors, no "still N bytes left"), `Athlete.onBecomePlayer` runs, and the real Lobby renders (`scratch/lobby_avatar_2026-09-20.png`). The old `hallTeamData` / `timerRefreshMSToken` / `hostID` / `baseLevel` AttributeErrors are gone. `gen_stream_v2.py` output is desynced at ordinal 207 -- do not use it.
- **RETRACTED (2026-09-20): "declared XML defaults make the Lobby clean".** Six no-interaction runs of the same 2178 B layout: `min` messy, `xml` clean, A messy, B clean, B1 messy, B2 messy -- and an exact replicate of B came out **messy**. The identical stream gave both outcomes, so the clean/messy hall state is NOT determined by the property values (likely timing or a UI refresh; the user reports it becomes clean after visiting the Ranked page). See `06_notes/GHIDRA_PACKET_PARSER_TRACE.md`, Checkpoint 20d.

- **Checkpoint 20j (2026-09-20): hall UI root cause found.** `UIMain.on_enter` aborted on two BASE-only attributes (`personalRecommendState`, `monthPayRebateSpecialAwardInfo`); the server now sends `onPersonalRecommendStateUpdated` (idx 754) and `syncMonthPayRebateSpecialAwardInfo` (idx 768) after Stage 4. Result: 0 script errors on fresh login, real top bar (diamond = freeYuanbao+payYuanbao; coin slot = `currencyList` id 213), correct timers, no stacked labels. Dev balance 999999/999999 via `scratch/gen_stream_v3.py`. Full method-name table: `scratch/dump_athlete_methods.py`. Client scripts can be decrypted/searched with `tools/script_index.py|script_query.py|script_disas.py` (disassembly opcodes unreliable; names lists are fine). Details and open items: `06_notes/GHIDRA_PACKET_PARSER_TRACE.md` 20j.
