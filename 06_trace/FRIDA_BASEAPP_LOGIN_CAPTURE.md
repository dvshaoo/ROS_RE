# ROS v1117219 — Dynamic Capture Attempt: `baseAppLogin` via Frida + Local Server

**Result up front**: the dynamic capture environment was successfully built and debugged to
the point of being reusable, and two real bugs in the project's local patch server were
found and fixed, advancing the client further through its boot sequence than any prior
session's notes record — but the client did **not** reach the PLAY button in this session,
so **no `baseAppLogin` bytes were captured**. This document is written so the next session
does not repeat the same multi-hour environment debugging.

## 1. Environment

| Item | Value |
|---|---|
| Client version | v1117219 / 1.610377.506841, `com.netease.chiji` |
| Emulator | LDPlayer 9 (`dnplayer.exe`), device id `emulator-5554` |
| Guest ABI | primary `x86_64`; ARM app libraries run via NativeBridge (`libhoudini`/`nb`) translation — confirmed via `/system/lib64/arm64/nb/*.so` paths in `/proc/<pid>/maps` |
| Native lib under test | `libclient.so`, mapped at `03204000` in the live process (`/data/app/com.netease.chiji-.../lib/arm64/libclient.so`) |
| Root | available via `su` (uid 0) |
| Frida (host) | `frida`/`frida-tools` downgraded from 17.16.4 to **16.2.1** (see §2) |
| Frida-server (device) | **16.2.1, android-x86_64** build (see §2) |
| Local server host reachability | `172.16.1.2` from the guest (see §3) — **not** `10.0.2.2` as several existing project files assume |

## 2. Frida Setup — Two Environment Bugs Found and Worked Around

1. **frida-server 17.16.4 (arm64) segfaults on startup on this LDPlayer build.**
   `logcat` shows it crashes inside its SELinux "policy softener" step
   (`avc: denied { read } for name="policy" ... ` immediately followed by
   `Fatal signal 11 (SIGSEGV) ... in tid ... (frida-server)`). This reproduced with both
   the default and `--policy-softener=internal` options. **Fix**: downgraded to
   frida-server **16.2.1** (predates this policy-softener code path), which starts
   cleanly. The matching Python `frida`/`frida-tools` (16.2.1 / 12.2.1) must be installed
   on the host — Frida enforces major-version compatibility between client and server.
2. **The ARM64 build of frida-server 16.2.1 attaches but fails all operations with
   `unable to perform ptrace getregs: Device or resource busy`.** This is because
   frida-server itself is an ARM64 binary running under NativeBridge translation on this
   x86_64 host image — ptrace syscalls issued by translated code are unreliable in this
   configuration. **Fix**: use the **x86_64** build of frida-server instead (it is the
   *injector/host* process, not the thing being reverse-engineered, so it does not need to
   match the target app's architecture). This resolved the ptrace error completely; attach
   and `enumerateProcesses()` work normally afterward.
3. Frida's `enumerateProcesses()` lists the app by its **display name**
   ("Rules of Survival"), not its package name — `frida.get_device_manager()...attach('com.netease.chiji')`
   fails with "unable to find process with name"; attach by PID instead.
4. **Important, unresolved caveat for future hooking work**: `Process.enumerateModules()`
   inside an attached session does **not** list `libclient.so`, even though it is
   genuinely mapped in the process (confirmed via `/proc/<pid>/maps`, which shows it at
   `r--p` — **not** `r-xp` — protection). This is consistent with NativeBridge executing
   translated ARM64 code from a separately-managed JIT region rather than the CPU directly
   executing the mapped ARM64 bytes, meaning **`Interceptor.attach()` at a statically
   confirmed ARM64 address is not guaranteed to intercept anything** in this environment.
   This was the reason this session pivoted to a socket/server-level capture strategy (§4)
   instead of address-level hooking — matching the task's own prescribed fallback order.

## 3. Network Topology — Why DNS/hosts Redirection Wasn't Used

The existing project files (`dns_hosts.txt`, several `mitm_serve.py` comments) assume the
client reaches the host either via `10.0.2.2` (standard AVD/Genymotion convention) or via
DNS rewriting to the host's real LAN IP (`192.168.100.8`, itself dependent on being on a
specific Wi-Fi network). Neither worked from this LDPlayer instance:

- The guest's own IP is `172.16.1.15/24`; it could **not** ping `192.168.100.8` (the host's
  real Wi-Fi IP) or `10.0.2.2` — no route.
- `/etc/hosts` on the guest is **not writable**, even as root (`mount -o rw,remount /`
  fails: `'/dev/root' is read-only` — this image enforces a read-only rootfs at the block
  level, not just via a mount flag).
- **What does work**: LDPlayer's NAT gateway is reachable at **`172.16.1.2`** (found via
  ARP table + ping, confirmed with an actual TCP connect test). This is LDPlayer's
  equivalent of the `10.0.2.2` convention, just a different address.
- Rather than fight DNS/hosts, this session used **on-device `iptables` OUTPUT-chain DNAT**
  (root already available, no filesystem write needed):
  ```
  iptables -t nat -F OUTPUT
  iptables -t nat -A OUTPUT -p tcp --dport 80    -j DNAT --to-destination 172.16.1.2:80
  iptables -t nat -A OUTPUT -p tcp --dport 443   -j DNAT --to-destination 172.16.1.2:443
  iptables -t nat -A OUTPUT -p udp --dport 25000 -j DNAT --to-destination 172.16.1.2:25000
  iptables -t nat -A OUTPUT -p udp --dport 20013 -j DNAT --to-destination 172.16.1.2:20013
  ```
  This redirects the relevant ports to the host **regardless of what IP or domain the
  client thinks it's connecting to** — it worked immediately, confirmed by the local HTTP
  server receiving real client requests. This is a more robust technique than DNS/hosts
  rewriting for this kind of work and is recommended for all future sessions on this
  emulator instance (the rules are process-lifetime only, in the `su` shell environment —
  they do **not** survive an emulator reboot and must be reapplied).

## 4. Capture Strategy Actually Used

Per the task's own fallback ordering ("if Frida cannot directly hook... fall back
progressively... 3. socket/send syscall boundary... 4. packet capture"), this session used
the most robust available option: **run the actual LoginApp/BaseApp endpoints ourselves**,
so the "capture" is simply what our own server's `recvfrom()` sees — no in-process
instrumentation required for the capture itself (Frida is still set up and working for
follow-up in-process work, per §2).

New file: `mitm/local_baseapp_capture.py` — reuses `mitm_serve.H` (the already-proven
G0/G1 HTTP patch+auth handler) for ports 80/443/8443, and adds:
- A **LoginApp UDP responder** on `:25000` that replies to any incoming packet with a
  crafted 20-byte `LoginReplyRecord` (best-effort experimental layout — see
  `LOGIN_REPLY_RECORD.md`; NOT claimed to be correct, this is exactly the kind of thing
  dynamic testing is meant to validate empirically, but the run never reached this point —
  see §6).
- A **BaseApp UDP capture listener** on `:25010` that logs the raw hex of anything it
  receives. This is where `baseAppLogin`'s bytes would appear if the client reached that
  stage.

Both are running and confirmed listening; neither has received a Mercury/UDP packet yet
because the client has not gotten past the HTTP patch-list stage (§6).

## 5. Real Bugs Found and Fixed Along the Way

Two genuine bugs in `mitm/mitm_serve.py` were identified and fixed this session (both
committed):

1. **`/1117219/total_list` was never served.** The client requests this using an
   **absolute-URI HTTP request line** (`GET https://g61.gph.easebar.com/1117219/total_list`)
   rather than a relative path — confirmed directly from the server's own request log,
   which recorded `self.path` as the full URL. The existing handler checked
   `self.path.startswith('/1117219/total_list')`, which can never match an absolute URI.
   **Fixed** to `'/1117219/total_list' in self.path`.
2. **Empty `file_list` in the patch plist crashes the client's Python engine.**
   Logcat showed `patch\ResourcePatcher.py:1285, in patch_size_calc: ZeroDivisionError:
   float division by zero` immediately after the plist was parsed with `"file_list": []`.
   **Worked around** by adding one placeholder entry (`dummy.npk`, size 1) to the plist's
   `file_list` — this avoids the crash, but is a workaround, not a real fix (see §6).

These are committed to `mitm/mitm_serve.py` and measurably advanced the client past a point
it was stuck at before this session (per `PROGRESS.md`/`IMPLEMENTATION_PROGRESS.md`, the
patch gate was previously marked cleared under different — and it turns out, environment
IP-specific — conditions that no longer held for this LDPlayer instance/session).

## 6. Current Blocker (why no packet was captured)

After the two fixes above, the client successfully:
- Fetches the patch plist and hash-check (`/pl/h45na_hc`, `/pl/npk_version_na_android.plist`)
- Resolves domains via the fake HTTPDNS endpoint
- Fetches `/1117219/total_list` (now served, 14 bytes — an empty pickled+zlib'd dict)

...then displays **"Retrieving patch lists 0.00%"**, which never advances, and after
roughly 60 seconds the client gives up with the original **"Failed to retrieve patches"**
dialog. No further HTTP requests are logged in that window (confirmed via the server's own
request log) — the client is not retrying or requesting a specific missing file, it is
simply waiting on something that our empty `total_list` payload does not satisfy.

**Honest assessment**: the `total_list` response schema (an empty `pickle.dumps({}, 2)`
compressed with `zlib`) is very likely insufficient — the placeholder `dummy.npk` entry
added to the plist's `file_list` (§5.2) probably needs a **matching entry inside the
`total_list` pickle** describing that same file (size/md5/status), which was not
reverse-engineered in this session. Doing so requires decompiling
`patch/ResourcePatcher.py` out of `script.npk` to learn the exact pickle schema
`patch_mgr`/`ResourcePatcher` expect — a distinct, self-contained follow-up task.

## 7. State Left Running For The Next Session

To avoid repeating the environment setup:
- `frida-server` (16.2.1, x86_64 build) is running on `emulator-5554` as root, listening on
  `27042`, forwarded via `adb forward tcp:27042 tcp:27042`.
- `mitm/local_baseapp_capture.py` is running on the Windows host, serving 80/443/8443 and
  listening for LoginApp (`:25000`) and BaseApp-capture (`:25010`) UDP traffic.
- The iptables OUTPUT DNAT rules from §3 are active on the emulator (root shell,
  non-persistent — reapply after any emulator restart).
- `scratch/frida-server-16.2.1-x86_64` and `scratch/xref_lib.py` are the reusable
  artifacts; `scratch/list_modules.js` is a minimal Frida module-enumeration script for
  quick re-verification of the module-visibility caveat in §2.4.

## 8. Answers To The Task's Specific Questions

1. **Frida script path**: `scratch/list_modules.js` (module enumeration proof-of-concept
   only — no `baseAppLogin`-specific hook script was written, because the client never
   reached a state where such a hook could be exercised).
2. **Hook address/function**: none installed against `libclient.so` this session, for the
   reasons in §2.4 and §6 (client never reached PLAY). The intended hook point (documented
   for the next session) is the socket send syscall boundary (`sendto`/`sendmsg` in
   `libc.so`, a genuinely and normally-loaded x86_64 module, unlike `libclient.so`) —
   **not** the ARM64 addresses from prior static-analysis passes, per the module-visibility
   caveat in §2.4.
3. **Captured packet length**: N/A — no packet captured.
4. **Raw packet/body bytes**: N/A.
5. **Reconstructed field layout**: unchanged from `BASEAPP_LOGIN_SERIALIZATION.md` — no new
   evidence obtained.
6. **Does the 24-byte context appear on the wire?**: not determined — capture never
   occurred.
7. **Does a SessionKey appear on the wire?**: not determined — capture never occurred.
8. **Is `baseAppLogin` implementable by a minimal local BaseApp now?**: no change from the
   prior static-analysis conclusion — still blocked on the same unresolved wire-body
   question, now additionally blocked by an unrelated local-patch-server schema gap (§6)
   that must be solved first just to reach the PLAY button in this environment.
9. **Next blocker**: reverse-engineer `patch/ResourcePatcher.py`'s expected `total_list`
   pickle schema (decompile from `script.npk`) so the client's patch-list wait resolves and
   boot can proceed to the login/PLAY screen. Once that is solved, the capture
   infrastructure in `mitm/local_baseapp_capture.py` is already in place and should not
   need further changes to actually catch `baseAppLogin`.
