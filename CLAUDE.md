# CLAUDE.md — Rules of Survival (ROS) Mobile RE & Private Server Guide

> **Project**: Rules of Survival Mobile Private Server Emulation (Game Preservation)  
> **Client**: Android APK `com.netease.chiji`, v1.610377.506841, vCode 1117219, arm64-v8a  
> **Target Environment**: LDPlayer 9 (`emulator-5554`, Android guest `172.16.1.15`, Gateway host `172.16.1.2`)  
> **ADB Path**: `C:\LDPlayer\LDPlayer9\adb.exe`  
> **Primary Script**: `mitm/local_baseapp_capture.py`  
> **Last Updated**: 2026-09-26 (Checkpoint 24: `launch_game.bat` now auto-recovers from the stuck-`MpayActivity`-overlay issue with a single timed BACK press, confirmed live to cut the hang from 90+s to ~10s)

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
