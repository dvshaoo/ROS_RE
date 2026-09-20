# GDB Remote Serial Protocol tools (Frida/lldb-server unblock attempt)

Built 2026-09-20 while investigating why Frida `attach()` fails on this LDPlayer
image (see `06_notes/GHIDRA_PACKET_PARSER_TRACE.md`, "Attempt 7" and "Attempt 8").

## What these are

- `fetch_lldb_server.py` / `extract_lldb_server.py`: extract a single file (an
  android-arm64 `lldb-server` binary) out of a remote Android NDK ZIP **without
  downloading the whole ~660-700MB archive**, using HTTP range requests against the
  ZIP's central directory via Python's `zipfile` module. Usage:
  ```
  python fetch_lldb_server.py <ndk_zip_url>      # lists matching entries + sizes
  python extract_lldb_server.py <ndk_zip_url> <out_path>
  ```
  Known-good source URLs (official, `Accept-Ranges: bytes` confirmed):
  - `https://dl.google.com/android/repository/android-ndk-r23c-linux.zip` (targets
    Android 29 -- the one that actually survives `--attach` on this image)
  - `https://dl.google.com/android/repository/android-ndk-r27c-linux.zip` (targets
    Android 30 -- segfaults immediately on this image, kept only for reference)

- `gdbrsp.py`: a minimal hand-rolled GDB Remote Serial Protocol client. No host
  `gdb`/`lldb` binary is required -- the wire format is simple enough to implement
  directly (`$<payload>#<2-hex-checksum>` packets, `+`/`-` acks). Run standalone for
  a quick smoke test against a live `lldb-server ... --attach <pid>`:
  ```
  python gdbrsp.py
  ```

## Known status (do not re-derive without reading this first)

`PTRACE_ATTACH` and syscall-level tracing (`strace -p <pid>`) work fine on this
LDPlayer image. `lldb-server` (NDK r23c build) survives `--attach`, but **crashes the
instant it must answer any client packet at all** (tested `qSupported` and the
minimal `?` query -- same result for both), i.e. before ever reaching
command-specific logic. This lines up with Frida's arm64 build failing with an
explicit `ptrace getregs: Device or resource busy`. The likely root cause is a
kernel-level limitation reading an arm64 thread's register set
(`PTRACE_GETREGSET`/`GETREGS`) via ptrace on this specific image -- not something
fixable by trying yet more tool builds. See the notes file for the full evidence
trail before spending more time here.

**Safety note**: a `PTRACE_ATTACH` sends `SIGSTOP` to the target. If the tracer dies
(crashes) without detaching, the target can be left stuck in state `T` (stopped) --
this happened during this investigation. Check `/proc/<pid>/stat` (3rd field) after
any attach attempt and `kill -CONT <pid>` if it shows `T`.
