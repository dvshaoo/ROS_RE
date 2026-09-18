# Handoff prompt for Gemini/Antigravity — investigate the `_realEnterHall` crash

> **Project**: Rules of Survival Mobile Private Server Emulation (Game Preservation)
> **Workspace**: `C:\Users\Raysoo\Downloads\ROS_RE`
> **Client**: `com.netease.chiji`, v1.610377.506841, vCode 1117219, arm64-v8a
> **This file**: written by Claude after independently live-testing your Gate 4 wire-encoding fix. It worked. There's one more crash after it — read this before doing anything else.

---

## Standing rules (do not violate)

- Local/LAN only. Never touch real NetEase servers.
- Zero guesswork: every packet format, entity type, and method index must be verified by live memory inspection, Ghidra decompilation, or a captured log line — not assumed.
- Commit frequently with descriptive messages.
- Read `06_notes/GHIDRA_PACKET_PARSER_TRACE.md` in full before doing anything — it has the complete, evidence-labeled history of this investigation, including the section at the very end documenting what's described below.

## What you got right — confirmed independently, live

Your threshold-based extended wire-index encoding formula (committed as `7e0d6fa`/`6b72a97`) is **correct**. I live-tested it myself with `adb logcat` capturing:

- Sent `Athlete.onCreateCharacter(True, "")` (idx 1084) → the client emitted `{"keypoint": "onCreateCharacter", "extraData": "{\"ret\": 1, \"msg\": \"\"}"}` via its own Sigma telemetry. That's not a guess or an arg-parse error — that's the real `entities/Athlete.py` `onCreateCharacter` method running to completion successfully.
- No crash, no reconnect loop — one stable connection held through the whole Stage 4 sequence (`onCreateCharacter` → `updateBaseCharacter` → `updateBaseNickname` → `enterHall`).
- `enterHall(True)` (idx 1091) was also correctly dispatched — logcat shows it reached the real function body:
  ```
  File "entities\Athlete.py", line 674, in enterHall
  File "entities\Athlete.py", line 656, in _realEnterHall
  AttributeError: 'NoneType' object has no attribute 'GetComponent'
  ```

This conclusively closes the "wire encoding for method_index >= 128 is unknown" question that both of us were stuck on earlier. Good work — don't touch the encoding formula again, it's done.

## What's still broken: `_realEnterHall` crashes on a None GameObject/Scene reference

`GetComponent` is a Unity/engine-style call, not a plain data property access — this is a **different class of bug** than the earlier `iWeekendPush.tryActiveWeekendPushRedBadge` crash (which was a missing default value for a plain `PYTHON`-typed data property, root-caused in the same notes file). This one is almost certainly:

- A 3D hall scene, or a specific `GameObject` inside it, that a real BaseApp would have caused the client to load via some earlier step (a resource/scene-preload push, or a side effect of an RPC not yet in our Stage 4 sequence) — and that step is missing from our server.
- OR a property on the Athlete entity itself (some kind of scene/GameObject handle) that, like `weekendPushRewardsHaveGotten`, has no sensible default and needs the real BaseApp Python `__init__`/`onCreate` logic to have set it — logic our raw protocol emulator doesn't run.

## What I need you to investigate (in order, zero guesswork)

1. **Confirm `updateBaseCharacter`/`updateBaseNickname` actually succeeded.** They produced no error output in logcat during my test, which is consistent with success but not proof — I did not find a telemetry keypoint or other independent confirmation for either one the way `onCreateCharacter`'s keypoint confirmed it. Check for one, or find another way to confirm these two calls' side effects actually applied.
2. **Find what `_realEnterHall` (entities/Athlete.py line 656) is calling `.GetComponent` on.** We can't read the encrypted `script.npk` directly (established blocker, see `06_notes/ACCOUNT_HANDSHAKE_SYNTHESIS.md`), but you can:
   - Search live process memory (the same technique Claude used to find the real `MethodDescription` array — see the "MAJOR CORRECTION" section of `06_notes/GHIDRA_PACKET_PARSER_TRACE.md` for the method: walk `libclient.so`'s live load base → the `std::vector<EntityType*>` global at `+0x45785f0` → element `#51` → read its structure) for any nearby string literals referencing scene/hall-related property or class names close to where `_realEnterHall`/`enterHall` would be referenced, the same way `showSelectCharacter`'s real index was found.
   - Check whether there's a `ClientInterface`/`BaseAppExtInterface` message for scene/resource loading that a real server sends before `enterHall` (`06_notes/CLIENTINTERFACE_MESSAGE_TABLE.md` already has the full confirmed message list — cross-check it for anything scene/resource-preload-shaped that our Stage 4 sequence currently skips).
   - Check `mitm/captures/SERVE_B.txt` (the real captured NetEase traffic this project has been using as ground truth) for what messages a real server sends between `updateBaseNickname` and `enterHall`, or immediately after `createBasePlayer(Athlete)`, that we are not currently sending.
3. **Do not guess a fix and send it blindly.** The `iWeekendPush` crash taught us that a wrong guess at property/object initialization can produce a *worse* result than doing nothing (a prior session's fully-guessed property stream caused a native-level crash, worse than the current Python-level exception). Find the actual missing step or property first.
4. Update `06_notes/GHIDRA_PACKET_PARSER_TRACE.md` with whatever you find (proven or ruled out), and commit/push.

## How to test live yourself if you want to, but the plan is: you investigate + implement, Claude tests live

Per the user's instruction, the working split for this next round is: **you (Gemini) figure out and implement the fix candidate, then Claude will run the live test** (emulator control, logcat capture, screenshot verification) rather than each of us doing both halves independently and duplicating effort. So:

- Do your static analysis / memory scanning / capture review here.
- Implement your best evidence-based fix in `mitm/local_baseapp_capture.py`.
- Commit it with a clear message describing the evidence, but don't consider it "confirmed working" until Claude has live-tested it — the same way this handoff exists because Claude independently verified your wire-encoding fix rather than taking it on faith.
- If you want a specific live experiment run (a particular env var, a particular sequence, a particular thing to check in logcat), spell it out precisely in your commit message or in the notes file so Claude can run exactly that.

## Environment quick reference

- Emulator: LDPlayer, device `emulator-5554`. adb: `C:\LDPlayer\LDPlayer9\adb.exe`.
- Server: `python mitm/local_baseapp_capture.py` (binds :80/:443/:8443 HTTP + :25000 LoginApp UDP + :25010 BaseApp UDP). Restart after any code change; the app must be force-stopped and relaunched too (fresh session key).
- Capture logcat during every live test from now on: `adb logcat -c && adb logcat > scratch/live_logcat_<label>_<timestamp>.txt &` — this is how both the `iWeekendPush` root cause and the wire-encoding confirmation were found. Don't skip it.
- The "Slow connection" dialog at early splash is a known, separate, low-priority cosmetic issue — dismiss it (tap Confirm) and move on, not related to anything in this document.
