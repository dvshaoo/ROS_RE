# HANDOFF TO GEMINI: Dead-Touch Bug on Carnival Draw + START Buttons (native touch-dispatch investigation)

> **Target Client**: Rules of Survival Mobile (Android `com.netease.chiji`, v1.610377.506841, vCode 1117219, arm64-v8a)
> **Environment**: LDPlayer 9 (`emulator-5554`, Android guest `172.16.1.15`, Gateway/Host `172.16.1.2`)
> **Primary Server Script**: `mitm/local_baseapp_capture.py`
> **Prepared By**: Claude (Sonnet 5)
> **Date**: 2026-09-25

---

## 1. The bug, in one sentence

Two independent, unrelated buttons in the hall UI — the **Lucky Carnival "Draw" button** and the
**START button** (enters a match) — both produce **zero effect** when tapped: no visible reaction, no
Python-level script execution of any kind, and no upstream Mercury RPC reaches our server. The only
sign the tap is even recognized is that START plays its click sound.

Because two independently-implemented buttons in different UI modules fail identically, this looks
like a **systemic native touch-dispatch issue** in this client build (or the current hall layout/skin
state) rather than two separate per-button script bugs.

## 2. What has been verified (do not re-derive these — build on them)

### 2.1 Carnival Draw button (`06_notes/LUCKY_CARNIVAL_COMING_SOON.md`, 2026-09-25 entries)
- The Lucky Carnival wheel itself is fully functional server-side: real active-round data, correct
  reward pool, wheel renders with icons, countdown ticks. Only the Draw button itself is dead.
- Verified via **both** `adb input tap` and the human tester's own finger, multiple times, with a
  clean `adb logcat -c` immediately before each attempt:
  - Zero `<SCRIPT>`-tagged output of any kind (not even a non-error print) in the logcat window
    around the tap.
  - Zero upstream Mercury call reaches `mitm/local_baseapp_capture.py` — checked via its
    `_seen_exposed` tracker in `handle_upstream_calls()`, which logs **every** distinct
    `(method, len)` upstream pair it ever sees, including completely unmapped ones. Nothing new ever
    appears after a Draw tap.
  - No visible reaction: no toast, no button dim/bright state change, no popup.
- `uiautomator dump` on this client returns a single opaque `android.view.View` covering the full
  `1920x1080` surface (no accessibility tree — this is a custom-rendered native UI, not standard
  Android widgets), and separately confirmed the touch coordinate system is a 1:1 match to
  screenshot pixels (ruled out any DPI/scaling bug in `adb input tap` coordinates).
- Disassembled (`tools/script_disas.py`) `ui/UILuckyCarnival.py` / `UILuckyCarnivalAdvance.py` /
  `UILuckyCarnivalSuper.py`'s `onLotteryBtnClicked` + `genNeedYB`: the gating logic (feature-switch
  check, `checkLastLotteryIsMark`, `checkWelfareValid`, currency check) all resolve favorably for a
  fresh account's first draw — none of it should abort before reaching
  `player.base.onDoLuckyLottery(roundNo)`. Since **no Python code runs at all** (not even the
  touch-phase-`Ended` guard at the very top of the function), the touch is being consumed **before**
  it ever reaches this widget's registered callback.
- Working theory (unconfirmed): another overlay node with an oversized invisible touch-catcher sits
  on top of the interactive wheel — the panel also renders a "Congratulations! ... Claim `<N>`
  Diamond" winner-broadcast ticker that may be the culprit, but this has not been proven.

### 2.2 START button (`06_notes/GATE7_BATTLE_GAMEPLAY_PLAN.md`, 2026-09-25 entry)
- Live-tested (real finger tap): START plays its click sound (touch IS recognized at the
  engine/audio level) but produces **zero** other effect.
- Zero upstream Mercury call (same `_seen_exposed` check as above — this would also be the discovery
  point for `matchBattleGround`'s exposed wire id per `06_notes/GATE7_BATTLE_GAMEPLAY_PLAN.md` §4.1,
  which is currently unknown and blocks all of Gate 5/7 battle-entry work).
- Zero `<SCRIPT>`-tagged output in a clean logcat capture bracketing the tap.
- This is the exact same signature as the Draw button: engine-level ack, zero script execution.

**Conclusion so far**: this is very likely one shared root cause affecting (at least) two buttons,
not two separate bugs. Finding and fixing it would unblock both the Carnival draw feature and all
of Gate 5/7 (entering a real match).

## 3. What was attempted today and where it got stuck: Frida touch-dispatch hook

The plan was to hook the native touch-dispatch / hit-test path in `libclient.so` (this build's only
game-engine native library — see §4) to log which widget/node actually claims a touch at a given
screen coordinate, which would definitively show whether an invisible overlay is stealing the tap.

**This was not completed.** Progress and blockers, in order:

1. Confirmed `frida-server` is already deployed on the emulator at `/data/local/tmp/frida-server`
   and is startable: `su -c 'nohup /data/local/tmp/frida-server -D >/data/local/tmp/frida_start.log 2>&1 &'`.
2. `frida.get_device_manager().get_device('emulator-5554')` connects fine, and
   `dev.enumerate_processes()` works (lists ~90 processes, correctly finds
   `"Rules of Survival"` by name with its current pid).
3. **`dev.attach(<pid>)` fails every time** with:
   ```
   frida.ServerNotRunningError: unable to connect to remote frida-server: closed
   ```
   even though the same `dev` object's `enumerate_processes()` call succeeds moments earlier on the
   same connection.
4. Found and fixed a real version mismatch: the deployed `frida-server` binary reports
   `/data/local/tmp/frida-server --version` → `17.16.4`, while the local Python `frida` package was
   `17.18.0`. Downgraded the local package to match: `pip install frida==17.16.4`
   (do **not** also pin `frida-tools` to an old version in the same command — `frida-tools` has a
   `frida<17.0.0` constraint on some releases that conflicts; installing bare `frida==17.16.4` alone
   worked fine and left `frida-tools` alone).
5. **Attach still failed identically after the version fix.** This means the version mismatch was
   real but not the (or not the only) cause.
6. Noticed the `frida-server` process's PID kept changing between checks
   (`pgrep -f frida-server` returned a different pid group each time — 15008/15010/15011, then
   15186/15188/15189, then 15482/15484/15485, then 15757/15759/15760 — across a span of only a few
   minutes) **without anything intentionally restarting it**. This strongly suggests `frida-server`
   is crashing or being killed and something (unclear what — LDPlayer itself? a leftover shell loop
   from earlier in this session? the target app's own anti-tampering code?) is restarting it.
7. Checked `/data/local/tmp/frida_restart2.log` (the redirect target of the last manual start) —
   empty, no crash output captured.
8. Checked `adb logcat -d -t 50 | grep -i "frida|ptrace|inject"` right after a failed attach — no
   hits. No visible SELinux denial or crash signature was found in the brief window checked (this
   was not an exhaustive search).
9. **Working hypothesis, not confirmed**: `com.netease.chiji` ships
   `libcom_netease_ps_codescanner.so` and `libcom_netease_androidcrashhandler_AndroidCrashHandler.so`
   (see full native lib list in §4) — NetEase's own games are known to have anti-tampering/anti-cheat
   layers, and it's plausible the app detects `frida-server`'s presence (by port scan, by
   `/proc/<pid>/maps` inspection of its own process for injected libraries, by named-pipe/thread
   name heuristics, etc.) and either kills the connection or kills `frida-server` itself. This has
   **not** been verified from disassembly or logs — it is the leading theory only because it fits the
   symptom (attach specifically fails while simpler operations don't, and the server churns pids
   without an obvious innocent explanation) — treat it as an unconfirmed and this needs live
   evidence before you act on it, not a fact per project CLAUDE.md rules (zero guesswork).

## 4. Native library surface (for planning the hook, once attach works)

Full `arm64` lib list from `/data/app/com.netease.chiji-*/lib/arm64/` (dumped via
`adb shell su -c 'ls /data/app/com.netease.chiji-*/lib/arm64/'`):

```
libAudioCCReName.so       libAudioCore.so           libAudioEngine.so
libAudioEngineJni.so      libc++_shared.so          libclient.so
libcom_netease_androidcrashhandler_AndroidCrashHandler.so
libcom_netease_ps_codescanner.so
libfmodevent.so  libfmodex.so  libijkffmpeg.so  libijkplayer.so
libijksdl.so  libijkutil.so  libntunisdk.so  libstreammgr.so
libunisdkdctool.so
```

**Important, already-established fact**: despite script disassembly showing Unity-style API names
(`GameObject`, `AddComponent`, `CreateGameObject`, etc. — visible throughout
`scratch/script_index.txt` and every `tools/script_disas.py` dump), **this is NOT a Unity/IL2CPP or
Mono build** — there is no `libil2cpp.so`, `libmono.so`, or `libunity.so` in the lib list above. The
game engine is the proprietary **NeoX engine**, all inside `libclient.so`, which exposes a
Unity-*like* scripting API to the custom Python-esque bytecode VM this whole project already
disassembles with `tools/script_disas.py` (see `CLAUDE.md` §5 for the wire-encoding rules already
reverse-engineered for this VM, and `scratch/disassemble_targets.py` for the opcode table). **Do not
go looking for IL2CPP metadata or try to use an IL2CPP Frida bridge — it does not apply here.**

This means: the touch-dispatch entry point to hook is a native C/C++ function inside `libclient.so`
itself, not a managed-runtime API. `mitm/enum_exports.js` already exists as a starting point for
listing exports of `libclient.so` (currently filtered for loader/decrypt-related keywords, would need
new keywords like `touch`/`input`/`dispatch`/`raycast`/`hittest`/`pointer` — this was queued to run
today but blocked by the attach failure above before it could execute).

## 5. Suggested next steps, in order

1. **Get Frida attach working first** — nothing else in this doc can proceed without it.
   - Try `frida.get_usb_device()` instead of `get_device_manager().get_device('emulator-5554')` in
     case the device-manager path is the flaky one, not the server.
   - Try `frida-ps -U` / `frida-trace` from the `frida-tools` CLI (already installed) instead of
     the raw Python bindings, in case it surfaces a clearer error.
   - Try spawning the app fresh under Frida (`frida.get_device(...).spawn([...])` +
     `resume()`) instead of attaching to an already-running process, as a different code path that
     might not hit the same failure.
   - If pid churn continues, capture `logcat` continuously (`adb logcat > file &`, not `-d` snapshot)
     spanning an attach attempt, and grep the **entire** capture (not just the last 50 lines) for
     `frida`, `crash`, `SIGSEGV`, `tombstone`, or anything naming `frida-server`'s pid.
   - Check `/data/tombstones/` on the device for a native crash dump coinciding with a failed attach
     attempt — this would directly confirm or refute the anti-tampering theory.
   - If the anti-tampering theory is confirmed, the standard mitigations (renaming the frida-server
     binary and its process name, or using a Frida gadget baked into the APK instead of a
     device-wide frida-server, or an unpinned re-signed APK) are a **separate, larger** effort — flag
     that clearly to the user before starting it, since it changes the client binary and is a bigger
     scope than this touch-dispatch investigation alone.
2. **Once attach works**: enumerate `libclient.so` exports for touch/input/dispatch/raycast keywords
   (extend `mitm/enum_exports.js`'s pattern), identify candidate native functions.
3. **Hook the touch-dispatch entry point** (once identified) to log, per touch-down event: the
   screen coordinate and whatever internal node/widget identifier the engine resolves it to. Tap the
   Draw button and the START button with this hook active and compare against a tap on a
   known-working button (e.g. BACK, which reliably works) to see what differs.
4. Write findings back into `06_notes/LUCKY_CARNIVAL_COMING_SOON.md` and
   `06_notes/GATE7_BATTLE_GAMEPLAY_PLAN.md` (both already have today's dated entries on this bug —
   append, don't duplicate) and commit per the project's "every change needs a live test + note +
   atomic commit" rule (`CLAUDE.md` §1).

## 6. Constraints (from `CLAUDE.md`, still binding)

- Local/LAN only — never let this investigation touch real NetEase production servers.
- Zero guesswork — every claim in this doc that isn't marked VERIFIED must be re-checked live before
  being acted on, especially the anti-tampering theory in §3.9, which is currently just the
  best-fitting guess.
- Commit frequently, with notes updated alongside code.
- This is the mobile `com.netease.chiji` client — do not confuse with PC client structures.

## 7. Key files

| File | Purpose |
|---|---|
| `mitm/local_baseapp_capture.py` | Main server; `handle_upstream_calls()` / `_seen_exposed` is where a newly-discovered exposed method call would first appear in logs |
| `06_notes/LUCKY_CARNIVAL_COMING_SOON.md` | Full history of the Carnival Draw dead-touch investigation |
| `06_notes/GATE7_BATTLE_GAMEPLAY_PLAN.md` | Gate 5/7 battle-entry research; START button dead-touch entry is at the bottom |
| `mitm/enum_exports.js` | Existing (narrow) Frida export-enumeration script for `libclient.so`, needs new keywords |
| `mitm/frida_run.py` | Existing helper: `python frida_run.py <pid> <script.js> <outfile>` — attaches, loads a JS script, logs `send()` messages to a file |
| `tools/script_disas.py`, `tools/script_query.py`, `tools/load_table.py` | Static analysis tooling for the NeoX script VM and `assets.npk` tables — unrelated to this native investigation but referenced throughout the codebase's other notes |
| `/data/local/tmp/frida-server` (on-device) | Deployed frida-server binary, confirmed version `17.16.4` |
