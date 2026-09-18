# Continuation prompt for next AI session (ROS_RE mobile track)

> [!WARNING]
> **SUPERSEDED BY `CLAUDE.md` & `scratch/HANDOFF_PROMPT_CLAUDE.md`!**
> The notes below regarding `type=56` and capping indices at 127 are outdated.
> - `Athlete` is verified as **Type 51** (Type 56 is `RobotShadow`).
> - `showSelectCharacter` is verified as index **1083** (total 1131 methods).
> Please refer directly to [CLAUDE.md](file:///c:/Users/Raysoo/Downloads/ROS_RE/CLAUDE.md) or [HANDOFF_PROMPT_CLAUDE.md](file:///c:/Users/Raysoo/Downloads/ROS_RE/scratch/HANDOFF_PROMPT_CLAUDE.md).

---

You are continuing a multi-day, git-committed reverse-engineering project
in `C:\Users\Raysoo\Downloads\ROS_RE`: a **local/LAN-only private server
reimplementation** of the Rules of Survival mobile client
(`com.netease.chiji`, v1117219), for game preservation. This is NOT about
bypassing production auth/DRM/anti-cheat.

**Standing rules (do not violate):**
- Local/LAN only. Never touch the real production servers.
- No brute-forcing, no credential theft.
- **Never guess packet formats/indices without evidence.** Every claim
  must cite a file + line, a Ghidra function address, or a live-capture
  log line. If something is unknown, say so explicitly and trace it —
  don't fabricate an answer.
- Commit to git frequently with descriptive messages as work lands
  (already established pattern in this repo's history).
- Read `06_notes/GHIDRA_PACKET_PARSER_TRACE.md` in full before doing
  anything — it has the complete, evidence-labeled history of this
  investigation up to this point.

## Where things stand right now (2026-09-18, end of session)

**CONFIRMED FIXED:** the phantom `authenticate`/id-0 Bundle-corruption bug
that blocked all progress for days. Root cause: the server
(`mitm/local_baseapp_capture.py`) was appending a dummy 2-byte `00 00`
footer to packets whose flags didn't set `FLAG_HAS_REQUESTS` (bit 0),
leaving stray bytes the client's Bundle parser misread as a truncated
`authenticate` (msg id 0) call. Fixed by only appending that footer when
bit 0 is actually set. Verified via a 9000+-line live capture with zero
corruption errors.

**IMPLEMENTED THIS SESSION, NOT YET LIVE-VERIFIED:**
1. Fixed `Account.onLogin`/`onChannelLogin` wire-index guessing. The
   server's old sweep list never tried indices 18/19 — the exact values
   already derived (from the client's own def-XML entity tables, not
   guessed) by the sibling project `D:\PROJECTS\ros_mobile_revival`
   (**same APK**, different derivation method — read its `MEMORY.md` and
   `docs/MOBILE_INDEX_MAP.md`, they're a goldmine of already-proven
   indices for this exact client). Added `(19, 18)` as the first
   candidate pair in `push_login_completion`'s sweep.
2. Added an **Athlete entity** (`createBasePlayer type=56`) — the server
   previously only ever created an `Account` entity (type=38) and NEVER
   created an Athlete entity at all. Without it, `showSelectCharacter`
   (the RPC that opens Character Creation) has nowhere to be pushed to,
   so Character Creation could never have appeared no matter how correct
   everything else was.
3. Added `push_show_select_character()` — sweeps candidate wire indices
   0-127 for `Athlete.showSelectCharacter(ARRAY<STRING>=[])` (empty-array
   encoding = single `0x00` byte). The absolute index isn't locked even
   in `ros_mobile_revival` (still sweep-mode there too). **Hard
   constraint: `send_entity_method()` packs msgid as ONE byte
   (`bytes([msgid])`), so `128+idx` must stay <=255 — idx capped at 127.**
   If you ever need idx > 127, you must first add a 2-byte extended-msgid
   encoding path — don't just remove the cap.

## THE ACTUAL BLOCKER RIGHT NOW — read this before doing anything else

A **precise, reproducible diagnostic signal** was found this session: the
client POSTs a `sigma-keypoint-h45na.proxima.nie.easebar.com` telemetry
event with `"keypoint": "connectLoginHostCallback"` right after every
LoginApp reply. Its `extraData` carries `{"status": 1}` on runs that go
on to reach BaseApp, or `{"status": 2}` on runs that never dial BaseApp
at all. **Just grep any capture log for `connectLoginHostCallback` to
instantly know if that run is even worth analyzing further** — don't
waste time staring at screenshots or timing gaps.

**This status flips unpredictably and is now the #1 priority to
root-cause before any further protocol work can be live-tested.**
Findings so far (all in the live-test log entries near the bottom of
`06_notes/GHIDRA_PACKET_PARSER_TRACE.md`, search for "connectLoginHostCallback"):
- Originally looked like "same-session relaunch degrades, full reboot
  fixes it" — but this was **disproven** later the same session: a clean
  post-reboot first attempt still scored `status: 2` once.
- The raw LoginApp reply bytes and RECV-to-reply timing were compared
  between a `status:1` run and a `status:2` run and are **byte-identical
  in structure** with sub-second latency in both — the difference is NOT
  in the server's reply content or speed.
- Root cause is UNKNOWN. Do not assume reboot fixes it. Do not assume
  same-session relaunch is the only cause. Trace it properly:
  - Try packet-capturing the raw UDP LoginApp exchange (not just the
    HTTP telemetry) for a status:1 run vs a status:2 run at finer time
    resolution than the log's 1-second timestamps — look for
    retransmissions, duplicate replies, or a race between multiple
    in-flight LoginApp requests.
  - Check whether stale sockets/threads from a PREVIOUS attempt are still
    bound or interfering (the Python server process was restarted
    between some attempts this session but not consistently between
    every single one — check `_key_cache`/`_early_key_by_host` module
    globals for stale entries).
  - Check the emulator's own network stack state (`conntrack -L`, ARP
    cache) between attempts — a full reboot should clear these, but the
    one disproving case suggests something isn't fully reset even then.
  - `mitm_serve.py`'s HTTP body-truncation bug was already fixed this
    session (was silently cutting logged POST bodies at 512 bytes) — the
    fix is already committed, so full telemetry bodies are visible now;
    use them.

**Do not attempt to test the Athlete/showSelectCharacter sweep further
until this flakiness itself is understood** — you can't tell whether a
sweep "failed" because the index was wrong or because the run never even
reached BaseApp.

## Practical environment notes (LDPlayer + adb)

- Emulator: LDPlayer, device id `emulator-5554`. adb path:
  `/c/LDPlayer/LDPlayer9/adb.exe`. Reboot: `/c/LDPlayer/LDPlayer9/ldconsole.exe reboot --index 0`
  (takes ~5-8 poll cycles of 5s to come back as `device` in `adb devices`).
- **iptables DNAT rules are wiped on every emulator reboot** — must
  reapply after every reboot, before testing:
  ```
  adb shell "su -c 'iptables -t nat -A OUTPUT -p tcp --dport 80    -j DNAT --to-destination 172.16.1.2:80
  iptables -t nat -A OUTPUT -p tcp --dport 443   -j DNAT --to-destination 172.16.1.2:443
  iptables -t nat -A OUTPUT -p tcp --dport 8443  -j DNAT --to-destination 172.16.1.2:8443
  iptables -t nat -A OUTPUT -p udp --dport 25000 -j DNAT --to-destination 172.16.1.2:25000
  iptables -t nat -A OUTPUT -p udp --dport 20013 -j DNAT --to-destination 172.16.1.2:20013'"
  ```
- Server: `python mitm/local_baseapp_capture.py` (binds :80/:443/:8443 HTTP
  MITM + :25000 UDP LoginApp + :25010 UDP BaseApp). **Must be restarted
  after ANY code change** (it's a long-running process, doesn't hot-reload),
  and the CLIENT must then be relaunched too (force-stop + `monkey -p
  com.netease.chiji -c android.intent.category.LAUNCHER 1`) to get a
  fresh session key — old sessions' cached Blowfish keys won't decrypt
  against a freshly-restarted server.
- Launch app: `adb shell monkey -p com.netease.chiji -c android.intent.category.LAUNCHER 1`
- A **"Slow connection" dialog reliably appears once at the very early
  splash** (before title screen), tied to `file_list_assets`/
  `file_list_res/*` HTTPS manifest-fetch requests timing out — dismiss it
  (tap Confirm) and the flow proceeds normally. This is a SEPARATE,
  lower-priority, not-yet-root-caused issue from the LoginApp-stage
  status 1/2 flakiness — don't conflate the two.
- Screenshot: `adb shell screencap -p /sdcard/x.png` then
  `adb pull /sdcard/x.png <windows path>` (use `export MSYS_NO_PATHCONV=1`
  in git-bash so `/sdcard/...` isn't mangled into a Windows path).
- PLAY button is at roughly (955, 795) in the 1920x1080 screenshot
  coordinate space; the early "Slow connection" dialog's Confirm button
  is at roughly (951, 701).

## Related sibling projects (read, don't blindly copy)

- `D:\PROJECTS\ros_mobile_revival` — same APK, parallel effort using
  Python/def-XML derivation instead of Ghidra binary tracing. Has
  already-proven entity type IDs and method indices. Read its
  `MEMORY.md` and `docs/MOBILE_INDEX_MAP.md` before guessing any index.
- `D:\PROJECTS\ros_new_gen_pc` — a separate PC-client track (different
  binary, different platform, NOT the same investigation) — don't mix
  its findings into this mobile track.

## Immediate next action

Root-cause `connectLoginHostCallback` status 1 vs 2. Do not move on to
verifying the Athlete/showSelectCharacter sweep, or any other protocol
work, until you understand why this flips.
