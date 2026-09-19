# Handoff to Gemini/Antigravity — find the property-push mechanism (3 concrete tasks)

> **Project**: Rules of Survival Mobile Private Server Emulation (Game Preservation)
> **Workspace**: `C:\Users\Raysoo\Downloads\ROS_RE`
> **Client**: `com.netease.chiji`, v1.610377.506841, vCode 1117219, arm64-v8a
> **Written by**: Claude, after a long session that advanced this a lot but did not close it.
> **Read first**: `06_notes/GHIDRA_PACKET_PARSER_TRACE.md`, the last two sections
> ("Checkpoint 16" and "Attempt 6"). They contain the full evidence trail for
> everything summarized below.

---

## Standing rules (do not violate)

- Local/LAN only. Never touch real NetEase servers.
- **Zero guesswork.** Every packet format, entity type, property, method index and
  struct offset must be backed by a decompile, a live memory read, or a captured log
  line. Cite the evidence (address, file, line) for every claim you make.
- Commit frequently with descriptive messages.
- Do not send speculative payloads to the live client. A prior session's blind guess
  at a property stream caused a native-level crash — strictly worse than the current
  Python-level exception.

## The actual problem we are trying to solve

Four properties on the live `Athlete` entity are missing / `None`, each producing
`AttributeError: 'PlayerAthlete' object has no attribute 'X'` in unrelated code paths:

| Property | Where it breaks |
|:---|:---|
| `hallTeamData` | `iHallTeam.isInFormedTeam` / `isInTeam` → breaks `UIModes._refresh_members`, blocks the Start button |
| `weekendPushRewardsHaveGotten` | `iWeekendPush.tryActiveWeekendPushRedBadge` |
| `timerRefreshMSToken` | `Athlete._realEnterHall` via `UISelectMode.selectDone` |
| `monthPayRebateSpecialAwardInfo` | `iMonthPayRebateSpecialAward.have_award_can_receive` |

These are **not** four separate bugs. They are one systemic problem: our server never
pushes real property values onto the entity, so every property falls back to a bare
default. Patching them one at a time with RPC calls does not work and has already been
tried and refuted (commit `7ae0f3e`'s `onLeaveHallTeam` fix failed because that method
itself reads `hallTeamData`).

**We need the wire mechanism that sets entity property values.** That is the whole task.

---

## Confirmed — build on this, do not re-derive

- **`createBasePlayer` cannot carry properties.** Its domain flag is a hardcoded literal
  `0` at its only call site (`ClientApp::onBasePlayerCreate` = `FUN_00a18504`, calling
  `FUN_00a2ac04(entityType, eid, &DAT_04677340, 0, 0, stream, 0)`). `newDictionary`
  raises a native exception whenever domain<2 **and** the stream is non-empty. Dead end,
  fully confirmed.
- **`updateEntity` (ClientInterface msgID 10) is a real, separate property-push message**,
  registered in `_INIT_44` as `variable, 2-byte length prefix`. Wire shape:
  `[msgID:10][len:u16][entity_id:u32][property_stream...]`.
- **Its handler is `FUN_00a49590`**:
  ```c
  void FUN_00a49590(long param_1, long *param_2) {
    if (*(long *)(param_1 + 0x110) != 0) {
      puVar1 = (**(code**)(*param_2 + 0x10))(param_2, 4);   // read u32 entity_id
      (**(code**)(**(long**)(param_1+0x110) + 0x38))        // manager vtable slot 0x38
          (*(long**)(param_1+0x110), *puVar1, param_2, *(undefined1*)(param_1+0xe98));
    }
  }
  ```
  **The function at the manager's vtable slot `+0x38` is the actual property-stream
  decoder. Finding and decompiling it is the single highest-value unknown.**
- **The generic dispatcher is `ClientVarLenMessageHandler::handleMessage` = `FUN_00a4c540`**
  (named by its own embedded log string, so this is certain). It resolves the object
  passed as `param_1` above via `lVar8 = *(long *)(*(long *)(header + 0x10) + 0x4458)`
  and calls the registered callback as `callback(lVar8, stream, header.length)`.
- **`lVar8` is the live `ServerConnection` instance** (class `neox::bwclient::ServerConnection`,
  confirmed via the RTTI string `N4neox8bwclient16ServerConnectionE` @ `02b4b340`).
  Proof: `ServerConnection::createBasePlayer` = `FUN_00a47dc4` (named by its own log
  string `"ServerConnection::createBasePlayer: id %d\n"`) uses the same `param_1` field
  layout: `+0x110` = manager pointer, `+0x118` = entity id, `+0xe98` = mode byte,
  `+0xec8`/`+0xed8`/`+0xee0`/`+0xef0` = buffered createCellPlayer bookkeeping.
- **`createBasePlayer` calls the manager's vtable slot `0`; `updateEntity` calls slot `0x38`.**
  Same manager object, two different virtual entry points.
- **Property descriptors are `0x68` (104) bytes each.** A previous session confirmed
  `FUN_00ad0348` / `FUN_00ad02fc` / `FUN_00ad02ec` / `FUN_00ad0338` are index-scaled
  property-descriptor table lookups of the form `base + index*0x68`.
- Live-memory technique that works: libclient.so's load base is **stable at `0x03308000`**
  across process launches (verified on two different pids). Heap addresses are not.
  `EntityType` vector = `base + 0x45785f0` (172 entries); `Athlete` = index 51; its
  method table is at `EntityType + 0x1e8` (1131 entries, 24-byte stride).

## Ruled out with evidence — do NOT spend time re-trying these

1. **`onBasePlayerCreate`'s xrefs are not vtable slots.** Both (`033ef8e0`, `03315978`)
   are in `.eh_frame` / `.eh_frame_hdr` — DWARF unwind metadata. Verified by
   `MemoryBlock` lookup. Chasing function xrefs to find the manager vtable this way
   does not work.
2. **Generic-signature heap scanning does not work.** Scanning for "int32 `1` at
   `+0x118` + heap pointer at `+0x110` + plausible vtable at its target" produced
   **thousands** of false positives per region across 466MB. The signature is far too
   common in this engine's heap.
3. **`EntityType` offsets `+0x1b8` / `+0x1c8` / `+0x1d0` are not the property table.**
   None of the four missing property names appear in the memory they point to.
4. **Symbol-table search is useless** — the binary is fully stripped. All the
   `ServerConnection` "symbols" found are `.rodata` strings (RTTI / `std::function`
   type-erasure names), not linkable symbols.

---

# Task 1 (highest value, purely static, start here)

**Find the property-descriptor table's offset inside the `EntityType` struct** — the
property-side analogue of the already-known method table at `EntityType + 0x1e8`.

Decompile `FUN_00ad0348`, `FUN_00ad02fc`, `FUN_00ad02ec`, `FUN_00ad0338` and determine
where the `base` in `base + index*0x68` comes from. Follow it back to the field within
`EntityType` that holds it (expect a `std::vector`-style begin/end/capacity triple, the
same shape as the methods vector at `+0x1e8`).

Then verify it live (once the emulator is back up — see "Environment" below):
walk `load_base + 0x45785f0` → element 51 (`Athlete`) → that new offset → confirm the
entries are 0x68 bytes apart and that the names `hallTeamData`,
`weekendPushRewardsHaveGotten`, `timerRefreshMSToken`, `monthPayRebateSpecialAwardInfo`
appear among them.

**Deliverable**: the confirmed `EntityType` offset, the entry stride, the layout of a
`0x68`-byte property descriptor (where its name string, type pointer, and index live),
and a full dump of `Athlete`'s property list **in table order with indices**. We need
that ordering regardless of which push mechanism we end up using.

# Task 2 (static, mechanical, bounded)

**Find the manager class's vtable by brute force over `.data.rel.ro`**, since xref
chasing is ruled out (see "Ruled out" #1).

`.data.rel.ro` spans `038cd610`–`039f3327`. `.text` spans `00909200`–`02b38663`.
Scan `.data.rel.ro` for runs of 8-byte values that all fall inside `.text` — those runs
are candidate vtables. For every candidate with at least 8 slots, decompile
**slot 7** (byte offset `0x38`) and look for a function whose body matches this shape:

- signature roughly `(manager, uint32 entity_id, stream*, byte mode)`
- looks up an entity by id (expect an indexed container access, likely via the
  `+0xfc0` map seen in `ClientApp::onBasePlayerCreate`)
- then iterates properties and reads values off the stream

Cross-check: the same vtable's **slot 0** should be the `createBasePlayer`-side entry
(signature `(manager, entity_id, type_u16, stream*, byte mode)`), because
`FUN_00a47dc4` calls `(**(code**)*puVar4)(puVar4, id, type, stream, mode)` on the same
object. **A candidate vtable where slot 0 and slot 7 both match those two shapes is
almost certainly the right one** — that pairing is a strong, checkable constraint.

**Deliverable**: the vtable's address, the slot-7 function's address, its full
decompile, and — the actual goal — **the byte-level wire format of the property stream
it reads**: is it a presence bitmask followed by values? a sequence of
`(property_index, value)` pairs? What integer widths? How is each `DataType` decoded?

# Task 3 (environment — unblocks everything, can run in parallel)

**Get Frida `attach()` working on the LDPlayer emulator.**

Current exact state (all verified today):
- `frida-server` **is already installed and was running** at `/data/local/tmp/frida-server`,
  version **17.16.4**. Two older builds also present (`frida-server-16`,
  `frida-server-x64`, both 16.2.1).
- Host side is ready: `frida` 17.18.0 + `frida-tools` 14.10.4 globally, plus a
  version-matched venv at `scratch/fridaenv` with `frida==17.16.4`.
- **Device-level operations work**: `enumerate_processes()` returns 97 processes and
  correctly shows the game as pid 4964 / name `Rules of Survival`.
- **`attach()` fails on every single process** — the game, `surfaceflinger`, `Chrome`,
  `android.process.media`, all of them — with
  `frida.ServerNotRunningError: unable to connect to remote frida-server: closed`.
  Version mismatch is **not** the cause (the matched-version venv fails identically).
  The game's anti-debug is **not** the cause either (it fails on benign system
  processes too). frida-server stays alive after the failed attach.
- Likely root cause to investigate: the guest is **x86_64** (`ro.product.cpu.abi` =
  `x86_64`) running the game's **arm64-v8a** native libraries through LDPlayer's
  binary-translation bridge (`ro.product.cpu.abilist` =
  `x86_64,x86,arm64-v8a,armeabi-v7a,armeabi`). Frida's injector may be failing against
  translated processes. This matches the "native-bridge x86/ARM64 translation wall"
  already flagged in `06_notes/ACCOUNT_HANDSHAKE_SYNTHESIS.md`.

Things worth trying, in rough order of cheapness:
1. Read `/data/local/tmp/frida_v.log` (a `-v` verbose run was started but the emulator
   went down before it could be read) — the injector usually logs the real reason there.
2. Try the arm64 frida-server build instead of x86_64, since the target's native code
   is arm64 under translation.
3. Try `frida-server -l 0.0.0.0:27042` plus an explicit `adb forward`, and connect with
   `frida.get_device_manager().add_remote_device('127.0.0.1:27042')` instead of
   `get_usb_device()` — this bypasses Frida's own USB/adb transport layer.
4. Try frida-gadget loaded via `LD_PRELOAD` on app start instead of runtime injection.

**Note**: we do NOT need `Interceptor.attach` / native code hooking for this to be
useful. Plain `Memory.scan` + `readPointer()` from an attached session is enough, and
those are OS-level operations unaffected by instruction translation. If you can attach
at all, hook-free memory inspection will do the job.

**Why this matters**: with a working attach, one hook or even one well-timed memory read
inside `FUN_00a47dc4` gives us `param_1` — the live `ServerConnection` — directly, and
from there `+0x110` → manager → its vtable → slot `0x38`. That single read replaces the
six static techniques that have now failed.

# Task 4 (added 2026-09-19 — do this after Task 1) — make the Character Creation UI actually appear

**A previously documented "design fact" has been retracted.** An earlier handoff
(`HANDOFF_PROMPT_GEMINI_2026-09-18_lobby_polish.md`) stated "there is no interactive
Character Creation UI in this client." **That is wrong.** The user supplied a reference
screenshot from another dev team's working setup showing the real screen: the 3D
character standing on the hall terrace, a **"Tap to Enter NAME"** field, and a
**"CREATE"** button. The screen exists and is reachable. Do not treat its absence as
by-design.

## What Claude already fixed and verified today (build on this)

Running the first properly-controlled test with `ROS_AUTO_ENTER_HALL=0` (server sends
only `showSelectCharacter([])` and then holds, instead of force-marching the client into
the Lobby 2.5s later) exposed a real bug that the auto-sequence had been hiding:

```
File "entities\Account.py", line 56, in onChannelLogin
File "helpers\channel\channel_login.py", line 411, in onLoginByServerSauth
KeyError: 'aid'
```

Our `sauth` dict lacked `'aid'`, so login completion aborted. **Fixed** in
`mitm/local_baseapp_capture.py` (added `'aid'`, plus a `collections.defaultdict(str, …)`
under `ROS_SAUTH_DEFAULTDICT=1` so unknown keys return `''` instead of raising).
**Verified live**: `KeyError: 'aid'` went 1 → 0, no new `KeyError`, and the full entity
`onCreate` chain now runs. See the "2026-09-19" section of
`06_notes/GHIDRA_PACKET_PARSER_TRACE.md`.

## The exact remaining symptom

With that fix in and `ROS_AUTO_ENTER_HALL=0`:
1. Login completes; the whole `onCreate` interface chain runs.
2. `showSelectCharacter([])` is delivered and `_loadDefaultScene()` runs.
3. The `Scene` GameObject is created —
   `GetAllSubObj set([<Scene (GameObject) at 0x763838542390>])`.
4. **Then nothing.** That is the last `<SCRIPT>` line in the log. The client sits on the
   title screen. No name-entry field, no CREATE button.

Evidence: `scratch/live_logcat_sauthfix.txt` (and `scratch/live_logcat_charcreate_test.txt`
for the pre-fix run).

## Constraint that narrows this a lot

`showSelectCharacter` is the **only** character-UI-shaped method in Athlete's entire
1131-entry client method table (`scratch/athlete_methods_all.txt`):

```
[1083] showSelectCharacter   [1084] onCreateCharacter   [1085] onRoleCreateSuc
[1086] onChangeNickname      [1087] updateBaseCharacter [1088] updateBaseNickname
[1089] preloadMap            [1091] enterHall
```

So the trigger is **not** some other server→client RPC we've failed to call. Either
`showSelectCharacter` is being called with the wrong argument, or the UI it tries to
build fails/short-circuits on missing client state.

## What to investigate

1. **The `oldNames` argument.** We send an empty `ARRAY<STRING>` (`struct.pack('<I', 0)`).
   The method is named show***Select***Character — an empty list may drive a
   "nothing to select" path that renders nothing, while the CREATE form may require
   different input. Test non-empty values and see if the UI behaves differently. The
   4-byte-count wire encoding for `ARRAY<STRING>` is already confirmed
   (`libclient.so:0x9a4b74`), so you can construct a populated array safely.
2. **Find the UI code path.** `showSelectCharacter` lives in the encrypted `script.npk`,
   but its *effects* are observable: `_loadDefaultScene()` → `HALL_BASE_SCENE` →
   `Scene` GameObject. Work out what that Python method does after the scene loads, and
   what condition makes it skip building the UI. Live memory / logcat instrumentation
   around the UI classes (`UICreateRole`-style names) may be more productive than
   static work here.
3. **Consider that it may need the properties from Task 1.** The character-creation UI
   very plausibly reads Athlete properties that are currently `None`. If Task 1 lands
   and we can push real property values, re-test this immediately — the two tasks may
   turn out to be the same bug.

**Deliverable**: either the Character Creation screen rendering on our server (verified
by screenshot), or a precisely-evidenced statement of what it is waiting for. Also
determine **what the CREATE button sends back to the server** (a client→server entity
method), because we will have to handle it.

---

## Environment

- **The emulator is currently DOWN.** `adb devices` is empty; LDPlayer must be
  restarted before any live work. After a reboot, re-apply the iptables DNAT rules
  (they do not survive reboots, though they do survive app force-stops).
- adb: `C:\LDPlayer\LDPlayer9\adb.exe`, device `emulator-5554`. Root works (`su 0`, uid=0).
- Server: `python mitm/local_baseapp_capture.py` (binds :80/:443/:8443 + :25000 + :25010).
  Restart after any code change; force-stop + relaunch the app for a fresh session key.
- Capture logcat on every live test:
  `adb logcat -c && adb logcat > scratch/live_logcat_<label>_<timestamp>.txt &`
- Getting to the Lobby, in order: wait ~12s after launch → dismiss the "slow connection"
  dialog if present (tap `951 701`) → close the Events popup (tap `1841 108`, it
  intercepts the PLAY button) → tap PLAY (`960 740`) → Classic Mode "Confirm"
  (`960 953`) → Lobby loads. `ServerConnection::createBasePlayer: id 1` in logcat
  confirms the entity was created.
- Ghidra headless (this project's standard invocation):
  ```powershell
  $env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-21.0.12.101-hotspot"
  $env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
  & "C:\Users\Raysoo\ghidra\ghidra_12.1.3_PUBLIC\support\analyzeHeadless.bat" `
    "C:\Users\Raysoo\Downloads\ROS_RE\scratch\ghidra_project" ROS_RE `
    -process libclient_arm64.so -noanalysis `
    -scriptPath "C:\Users\Raysoo\Downloads\ROS_RE\scratch\ghidra_scripts" `
    -postScript <YourScript>.java
  ```
  Existing scripts in `scratch/ghidra_scripts/` are working templates — note the
  `ghidra.* cannot be resolved` IDE errors are expected and harmless (no Ghidra jars on
  the IDE classpath); they run fine headless.

## Division of labour

You investigate and implement; Claude live-tests (emulator control, logcat, screenshots)
and independently verifies before anything is called "working". Commit your findings with
clear messages, and state in the commit or in
`06_notes/GHIDRA_PACKET_PARSER_TRACE.md` exactly what Claude should run to reproduce and
verify. Update that notes file as you go rather than in one batch at the end, so the
live-testing can proceed incrementally.

If you conclude a task is not achievable, say so explicitly with the evidence that led
you there — a well-evidenced negative result is worth as much here as a fix, and this
project has already wasted effort re-treading paths that were never documented as dead.
