# -*- coding: utf-8 -*-
# local_baseapp_capture.py -- ROS_RE dynamic capture harness for baseAppLogin.
#
# Reuses mitm_serve.H (already-proven G0/G1 HTTP patch+auth handler) for
# ports 80/443/8443, adds:
#   - a LoginApp UDP responder on :25000 that replies to ANY incoming packet
#     with a crafted 20-byte LoginReplyRecord (best-effort guess, see
#     06_trace/LOGIN_REPLY_RECORD.md) pointing the client at a BaseApp
#     address of BASEAPP_HOST:BASEAPP_PORT
#   - a BaseApp UDP capture listener on BASEAPP_PORT that logs the raw bytes
#     of every packet it receives -- this IS the baseAppLogin wire capture.
#
# Traffic reaches this host via on-device iptables OUTPUT DNAT rules
# (see 06_trace/FRIDA_BASEAPP_LOGIN_CAPTURE.md) rather than DNS/hosts
# rewriting, because this LDPlayer instance's NAT topology (host reachable
# at 172.16.1.2 from the guest) made DNS/hosts-file redirection unnecessary
# and /etc/hosts turned out to be unwritable (dm-verity / read-only rootfs).
import os
import sys
import socket
import struct
import subprocess
import threading
import time
import pickle

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mitm_serve as base  # reuse H, generate_whoami_payload, PLIST, etc.

try:
    from Crypto.Cipher import Blowfish as _Blowfish
except Exception:
    _Blowfish = None

# E2E-006 (2026-09-15): ATTEMPT_L -- live Blowfish key test. A live /proc/<pid>/mem
# read (scratch/scan_heap_for_filter.py, made possible by ptrace/mem-read access
# being unexpectedly restored this pass -- see MERCURY_REPLY_ID_TRACE.md addendum)
# located the client's live EncryptionFilter object by scanning heap-tagged memory
# for its known vtable pointer (0x37dd3a0 + libclient.so's live load base), and
# read out a 4-byte SSO-encoded std::string key at object+0x11 (length confirmed
# via the SSO control byte at +0x10 = 0x08 -> length 4, exactly matching the
# RAND_bytes(4) key documented in FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md). This is
# a ONE-SHOT manual capture for a specific PID/connection (BFKEY_HEX env var),
# NOT yet a live per-request re-scan -- see END_TO_END_TEST_LOG.md E2E-006 for the
# full writeup and next-step plan to make this automatic per-connection.
_BFKEY_HEX = os.environ.get('BFKEY_HEX', '6187a604')
_BF_MODE = os.environ.get('BF_MODE', 'pc_variant')


def bf_encrypt(body, key_hex=None, mode=None, iv=None):
    key_hex = key_hex or _BFKEY_HEX
    mode = mode or _BF_MODE
    if not key_hex or _Blowfish is None:
        return None
    key = bytes.fromhex(key_hex)
    if mode == 'ecb':
        c = _Blowfish.new(key, _Blowfish.MODE_ECB)
        return c.encrypt(body)
    elif mode == 'cbc0':
        c = _Blowfish.new(key, _Blowfish.MODE_CBC, iv=b'\x00' * 8)
        return c.encrypt(body)
    elif mode == 'pc_variant':
        # PC ROS launcher's documented non-standard chaining: XOR each plaintext
        # block against the PREVIOUS PLAINTEXT block (not ciphertext), IV=0, then
        # ECB-encrypt -- see PC_LAUNCHER_STUDY.md SS3. `iv` (E2E-012 addition):
        # override the "previous block" seed for the FIRST block, default zero.
        # Motivated by the E2E-012 discovery that the BaseApp channel's
        # EncryptionFilter shares the EXACT SAME key as LoginApp's (confirmed
        # live, single-atomic-read scan, repeatable) -- if it is literally the
        # SAME filter OBJECT (not just coincidentally the same key value),
        # its chaining state would carry over from the last block of the
        # previous (LoginApp) message rather than resetting to zero for a
        # "new" channel, since nothing in the object's own state was ever
        # actually reset -- only the destination socket changed.
        c = _Blowfish.new(key, _Blowfish.MODE_ECB)
        blocks = [body[i:i + 8] for i in range(0, len(body), 8)]
        prev = iv if iv is not None else b'\x00' * 8
        out = b''
        for blk in blocks:
            xored = bytes(a ^ b for a, b in zip(blk, prev))
            out += c.encrypt(xored)
            prev = blk
        return out
    return None


def bf_decrypt(body, key_hex=None, mode=None, iv=None):
    key_hex = key_hex or _BFKEY_HEX
    mode = mode or _BF_MODE
    if not key_hex or _Blowfish is None or len(body) % 8 != 0:
        return None
    key = bytes.fromhex(key_hex)
    if mode == 'ecb':
        c = _Blowfish.new(key, _Blowfish.MODE_ECB)
        return c.decrypt(body)
    elif mode == 'cbc0':
        c = _Blowfish.new(key, _Blowfish.MODE_CBC, iv=b'\x00' * 8)
        return c.decrypt(body)
    elif mode == 'pc_variant':
        c = _Blowfish.new(key, _Blowfish.MODE_ECB)
        blocks = [body[i:i + 8] for i in range(0, len(body), 8)]
        prev = iv if iv is not None else b'\x00' * 8
        out = b''
        for blk in blocks:
            dec = c.decrypt(blk)
            plain = bytes(a ^ b for a, b in zip(dec, prev))
            out += plain
            prev = plain
        return out
    return None



# E2E-009 (2026-09-15): async live BaseApp-channel key discovery. E2E-008 found
# the BaseApp channel Blowfish-encrypts the WHOLE packet and rejects LoginApp's
# key, strongly suggesting a SEPARATE EncryptionFilter/key is constructed for
# the new BaseApp Nub/socket. Since baseAppLogin only gets a ~5s single-shot
# Mercury retry window (BASEAPP_LOGIN_SERIALIZATION.md SS3: one logical request,
# channel-level retransmission only), the heap scan must run in the background,
# started the moment the FIRST baseAppLogin packet arrives, so a later retry
# within the same window can use the freshly-discovered key. Uses on-device
# `dd | grep -F` (toybox grep, confirmed to support -a/-b/-o binary-safe fixed-
# string search) instead of transferring the ~500MB heap to the host -- measured
# at ~2.2s per 130MB region live against PID 9754, so scanning is done directly
# on-device and only match offsets (plus small follow-up reads) cross the wire.
ADB = os.environ.get('ADB_PATH', r'C:\LDPlayer\LDPlayer9\adb.exe')
DEVICE_SERIAL = os.environ.get('DEVICE_SERIAL', 'emulator-5554')
LIBCLIENT_VTABLE_FILE_ADDR = 0x37dd3a0  # EncryptionFilter vtable, FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md
_key_cache = {}  # {client_addr: key_hex}
_key_scan_started = set()  # client (ip,port) addrs for which a per-connection scan already ran
_onchannellogin_retry_started = set()  # (ip,port) addrs for which the onChannelLogin retry loop already started, E2E-037
_early_scan_hosts = set()  # host IPs for which the early (LoginApp-triggered) scan already ran
_early_key_by_host = {}  # {host_ip: key_hex} -- populated by the early (LoginApp-triggered) scan, E2E-012
_last_plain_block_by_host = {}  # {host_ip: last 8-byte plaintext block of our last LoginApp reply}, E2E-012
_keepalive_started = set()  # client_addr set for which a keep-alive thread is already running, E2E-022


def _start_keepalive(sock, addr, key_hex, interval=5.0):
    """E2E-022 (per a parallel static-analysis session's finding,
    06_notes/LOBBY_ENTRY_TRACE.md Task A): the ~10s reconnect loop is very
    likely BigWorld's generic, stock ServerConnection `InactivityTimeout`
    (live-logged as "InactivityTimeout 10.000000", disassembled at
    0x93888c/0x9849c8 -- a process-wide "no packet received in N seconds"
    watchdog on the Channel, NOT specific to identifyVersionPoint or any
    other single RPC). Answering identifyVersionPoint alone would silence
    the reconnect only ONCE; the same 10s timeout would refire later
    unless something keeps resetting it. This starts a background thread,
    one per client address (idempotent -- safe to call from multiple call
    sites), that sends a trivial ClientInterface `setGameTime` push
    (msgID 3, FIXED 4-byte body per 06_trace/MERCURY_PACKET_MAP.md SS2a,
    confirmed-by-binary registration order per SS2b/E2E-022) every
    `interval` seconds (well under the 10s ceiling) for as long as this
    server process runs, to keep the Channel's inactivity clock reset.
    """
    if addr in _keepalive_started:
        return
    _keepalive_started.add(addr)

    SETGAMETIME_MSGID = 3

    def _loop():
        log('BASEAPP KEEPALIVE: started for %s (setGameTime msgID=%d every %.1fs)' % (
            addr, SETGAMETIME_MSGID, interval))
        while True:
            time.sleep(interval)
            try:
                game_time = int(time.time()) & 0xffffffff
                sgt_body = struct.pack('<I', game_time)  # 4-byte fixed body
                # Ghidra trace 06_notes/GHIDRA_PACKET_PARSER_TRACE.md: on-channel
                # packets (flags=0x0008) do NOT have bit 0 set (FLAG_HAS_REQUESTS),
                # so no 2-byte first request offset is stolen. Appending b'\x00\x00'
                # causes the parser to read 0x00 as message ID 0 (authenticate).
                # Fixed: exact message bounds, no dummy footer.
                sgt_flags = int(os.environ.get('KEEPALIVE_FLAGS', '0x0008'), 16)
                sgt_plain = (struct.pack('<H', sgt_flags) + bytes([SETGAMETIME_MSGID])
                             + sgt_body)
                sgt_pad_len = 8 - (len(sgt_plain) % 8)
                sgt_padded = sgt_plain + b'\x00' * (sgt_pad_len - 1) + bytes([sgt_pad_len])
                sgt_enc = bf_encrypt(sgt_padded, key_hex=key_hex, iv=b'\x00' * 8)
                sgt_reply = sgt_enc if sgt_enc else sgt_padded
                sock.sendto(sgt_reply, addr)
                log('BASEAPP KEEPALIVE: sent setGameTime t=%d to %s (%d bytes)' % (
                    game_time, addr, len(sgt_reply)))
            except Exception as e:
                log('BASEAPP KEEPALIVE error for %s: %s' % (addr, e))

    threading.Thread(target=_loop, daemon=True).start()


def _adb(args, timeout=20):
    cmd = [ADB, '-s', DEVICE_SERIAL] + args
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout).stdout
    except Exception as e:
        log('BASEAPP KEYSCAN: adb call failed: %s' % e)
        return b''


def _get_pid():
    out = _adb(['shell', 'pidof', 'com.netease.chiji']).decode(errors='replace').strip()
    return out.split()[0] if out else None


def _get_libclient_base_and_regions(pid):
    maps = _adb(['shell', 'su', '0', 'cat', '/proc/%s/maps' % pid]).decode(errors='replace')
    base_addr = None
    regions = []
    for line in maps.splitlines():
        if 'libclient.so' in line and base_addr is None:
            rng = line.split()[0]
            start_hex, _ = rng.split('-')
            # only the FIRST (file offset 0) mapping is the true load base
            parts = line.split()
            if parts[2] == '00000000':
                base_addr = int(start_hex, 16)
        if 'libc_malloc' in line or '[heap]' in line:
            rng = line.split()[0]
            s, e = rng.split('-')
            regions.append((int(s, 16), int(e, 16)))
    return base_addr, regions


def _scan_region_for_pattern(pid, region_start, region_end, pattern_bytes):
    """Run dd|grep entirely on-device; returns list of absolute VA matches."""
    # BUG FOUND + FIXED THIS PASS (the real root cause of "0 candidates" even
    # for the already-known-good object, after the shell-quoting bug above was
    # also fixed): `bs=4096` on these high (0x7638...) 48-bit user-space
    # addresses makes `skip` a page COUNT around 3*10^10 -- comfortably over
    # 2^31 (2,147,483,648). toybox `dd`'s skip/seek arithmetic on this device
    # overflows a 32-bit int at that size, silently seeking to a WRONG (but
    # deterministic, hence repeatable) offset while still returning data and
    # exit code 0 -- no error, just wrong bytes. Confirmed live: a `grep`
    # match reported at a given absolute VA, immediately read back with a
    # separate one-off `dd`, showed completely unrelated bytes every time,
    # not a race condition (same wrong bytes on repeat reads). Per this
    # project's own established operational note ("toybox dd needs
    # bs=1048576 not bs=1M"), using a 1MB block size keeps the skip count
    # (region_start // 1048576) safely under 2^31 for all realistic region
    # addresses. Since regions aren't guaranteed 1MB-aligned (only 4096-page
    # aligned), round the skip down to the enclosing MB boundary and track
    # the resulting byte offset adjustment so absolute VAs stay correct.
    aligned_start = (region_start // 1048576) * 1048576
    skip_mb = aligned_start // 1048576
    count_mb = -(-(region_end - aligned_start) // 1048576)  # ceil div
    if count_mb <= 0:
        return []
    # NOTE (two bugs found + fixed this pass, verified against a live device):
    # the outer `sh -c '...'` wrapper uses SINGLE quotes, inside which the
    # shell does NOT interpret backslashes at all, and `subprocess.run([...])`
    # sends this Python string to `adb shell` VERBATIM (no host shell in
    # between to do its own unescaping, unlike typing the equivalent command
    # into an interactive/bash context). Bug 1: an earlier version added `\"`
    # around the printf argument -- inside single quotes those backslashes
    # are never consumed, so printf received literal backslash+quote
    # characters polluting the pattern (confirmed live: 21/21 regions, 0
    # candidates, even for the already-known-good LoginApp filter object).
    # Bug 2 (found fixing bug 1): printf's argument must still be
    # DOUBLE-quoted (`"$(printf "\xHH...")"`, quotes literal/unescaped since
    # we're already inside single quotes) -- command substitution `$(...)`
    # opens its own fresh quoting context, so a nested `"..."` inside it is
    # valid and required for toybox printf to treat the `\xHH` sequence as
    # one argument rather than needing quotes at all; empirically, leaving
    # it fully unquoted (`printf %s` with no surrounding quotes at all) also
    # returned zero matches against a live re-test -- only the doubly-quoted
    # form was verified live to work.
    # THIRD BUG FOUND + FIXED THIS PASS: `grep -b` on this toybox build reports
    # a byte offset RELATIVE TO THE START OF THE CURRENT LINE (1-indexed),
    # not an absolute stream offset -- confirmed with a minimal on-device
    # repro (`printf "AAAA\nBBBB<pattern>CCCC" | grep -a -b -o pattern`
    # reported offset 5, i.e. 1-indexed position within the SECOND line, not
    # the true absolute offset 9). Since random binary heap data contains a
    # 0x0a byte roughly every 256 bytes on average, a 100+MB region has
    # hundreds of thousands of line resets, making the previously-computed
    # "absolute VA" wrong for almost any real match (this, not the dd skip
    # overflow alone, was the full explanation for why a reported "hit"
    # consistently read back as unrelated bytes even after the dd fix).
    # Fix: use grep only as a fast on-device EXISTENCE check (-q, exit code
    # only, unaffected by the offset bug), then -- only for a region that
    # reports a match -- pull that one region's bytes to the host via
    # `adb exec-out` (binary-safe, no shell text-mode/newline issues at all)
    # and find the exact offset locally in Python, exactly like the original
    # one-shot scratch/scan_heap_for_filter.py did.
    pattern_escaped = ''.join('\\x%02x' % b for b in pattern_bytes)
    check_cmd = (
        "su 0 sh -c 'dd if=/proc/%s/mem bs=1048576 skip=%d count=%d 2>/dev/null "
        '| grep -qa -o "$(printf "%s")"\''
    ) % (pid, skip_mb, count_mb, pattern_escaped)
    res = subprocess.run([ADB, '-s', DEVICE_SERIAL, 'shell', check_cmd], capture_output=True, timeout=20)
    if res.returncode != 0:
        return []
    # Match confirmed present somewhere in this region -- pull it to host via
    # exec-out (binary-safe) and locate the exact offset locally.
    dump_cmd = "su 0 dd if=/proc/%s/mem bs=1048576 skip=%d count=%d 2>/dev/null" % (pid, skip_mb, count_mb)
    data = subprocess.run([ADB, '-s', DEVICE_SERIAL, 'exec-out', dump_cmd], capture_output=True, timeout=30).stdout
    hits = []
    idx = 0
    while True:
        idx = data.find(pattern_bytes, idx)
        if idx == -1:
            break
        # FOURTH BUG FOUND + FIXED THIS PASS: a SEPARATE follow-up `dd` read
        # at the reported VA -- done in an earlier version of this function,
        # and by the caller (`_read_key_at`) -- races against real memory
        # churn: live-confirmed multiple times (E2E-012) that a genuine,
        # unambiguous 8-byte exact match found in THIS download shows
        # completely different, unrelated bytes (once even a different
        # object entirely, string "onSpaceHeartbeat" visible nearby) when
        # re-read moments later via a fresh `dd` call. An 8-byte coincidental
        # match is statistically negligible (~3x10^6 positions in a 24MB
        # region vs 2^64 possible values), so the match itself is real at
        # scan time -- the memory simply changes between two separate reads.
        # Fix: slice the key bytes directly out of THIS already-downloaded
        # snapshot (single atomic read, no second round-trip, no window for
        # the object to change) instead of issuing a follow-up `dd`.
        key_bytes_raw = data[idx + 0x10:idx + 0x10 + 24]
        hits.append((aligned_start + idx, key_bytes_raw))
        idx += 1
    return hits


def _read_key_at(pid, obj_va):
    """Read the SSO-encoded std::string key at EncryptionFilter object+0x10
    (control byte) / +0x11 (inline chars), per FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md
    object layout. Returns hex string of the key bytes, or None.

    Same bs=1048576 fix as _scan_region_for_pattern: `bs=1 skip=<huge byte
    address>` overflows toybox dd's 32-bit skip arithmetic on these high
    addresses and silently returns wrong bytes (confirmed live -- this was
    the actual reason the async scan reported 0 usable candidates even after
    the pattern match itself was fixed). Read the enclosing 1MB block instead
    and slice out the needed bytes in Python.
    """
    read_start = obj_va + 0x10
    aligned_start = (read_start // 1048576) * 1048576
    skip_mb = aligned_start // 1048576
    local_offset = read_start - aligned_start
    remote_cmd = "su 0 sh -c 'dd if=/proc/%s/mem bs=1048576 skip=%d count=1 2>/dev/null | xxd -p'" % (pid, skip_mb)
    out = _adb(['shell', remote_cmd], timeout=10).decode(errors='replace').strip().replace('\n', '')
    if len(out) < (local_offset + 24) * 2:
        return None
    try:
        block = bytes.fromhex(out)
    except ValueError:
        return None
    raw = block[local_offset:local_offset + 24]
    if len(raw) < 24:
        return None
    return _parse_sso_key(raw)


def _parse_sso_key(raw):
    """Parse a libc++ SSO-encoded std::string's raw bytes (control byte at
    +0, inline chars from +1) into a hex key string, or None if it doesn't
    look like a short (<=22 byte) inline string. Shared by _read_key_at and
    the single-atomic-read path in find_baseapp_key_async's scan_one."""
    if len(raw) < 1:
        return None
    ctrl = raw[0]
    if ctrl & 1:  # long-form string, not expected for a 4-byte RAND_bytes key
        return None
    length = ctrl >> 1
    if length == 0 or length > 22 or len(raw) < 1 + length:
        return None
    key_bytes = raw[1:1 + length]
    return key_bytes.hex()


_scanned_pid = None
_scanned_key = None
_scan_lock = threading.Lock()
_key_ready_event = threading.Event()


def _check_range(pid, skip_mb, count_mb, pattern_escaped):
    check_cmd = (
        f"su 0 sh -c 'dd if=/proc/{pid}/mem bs=1048576 skip={skip_mb} count={count_mb} 2>/dev/null "
        f'| grep -qa -o "$(printf "{pattern_escaped}")"\''
    )
    res = subprocess.run([ADB, '-s', DEVICE_SERIAL, 'shell', check_cmd], capture_output=True, timeout=10)
    return res.returncode == 0


def fast_find_session_key(pid=None):
    """Sub-2-second binary-search heap scanner for live EncryptionFilter key."""
    global _scanned_pid, _scanned_key
    with _scan_lock:
        t0 = time.time()
        if not pid:
            pid = _get_pid()
        if not pid:
            log('KEYSCAN: no live chiji PID found, aborting scan')
            return None
        if _scanned_pid == pid and _scanned_key:
            return _scanned_key

        base_addr, regions = _get_libclient_base_and_regions(pid)
        if base_addr is None:
            log('KEYSCAN: could not find libclient.so base, aborting')
            return None

        # Scan every region >= 2MB, prioritising the ones where EncryptionFilter usually
        # lives. The old cutoff (sz > 16) skipped the region that actually held the filter
        # on some launches -- scratch/scan_all_regions.py found the live key in a 10MB
        # region (763854e00000-763855800000) that the cutoff excluded, so KEYSCAN reported
        # "no key found" while the key was sitting in memory. Heap layout differs per
        # launch, which is why the scan succeeded on some runs and not others. Regions
        # under 2MB are still skipped: the binary search below bottoms out at 2MB.
        large_regions = []
        for s, e in regions:
            sz = (e - s) // (1024 * 1024)
            if sz >= 2:
                large_regions.append((s, e, sz))
        large_regions.sort(key=lambda r: 0 if (r[0] >> 32) == 0x7638 and ((r[0] >> 24) & 0xff) in (0x46, 0x47, 0x48, 0x49, 0x4a, 0x4b, 0x4c) else 1)

        target_va = base_addr + LIBCLIENT_VTABLE_FILE_ADDR
        pattern = struct.pack('<Q', target_va)
        pattern_escaped = ''.join('\\x%02x' % b for b in pattern)

        found_key = None
        for s, e, sz in large_regions:
            aligned_start = (s // 1048576) * 1048576
            skip_mb = aligned_start // 1048576
            count_mb = -(-(e - aligned_start) // 1048576)

            if not _check_range(pid, skip_mb, count_mb, pattern_escaped):
                continue

            # Binary search down to 2MB
            low = skip_mb
            high = skip_mb + count_mb
            while (high - low) > 2:
                mid = (low + high) // 2
                c_left = (mid - low) + 1
                if _check_range(pid, low, c_left, pattern_escaped):
                    high = mid + 1
                else:
                    low = mid

            dump_cmd = f"su 0 dd if=/proc/{pid}/mem bs=1048576 skip={low} count={high - low} 2>/dev/null"
            data = subprocess.run([ADB, '-s', DEVICE_SERIAL, 'exec-out', dump_cmd], capture_output=True, timeout=10).stdout
            idx = 0
            while True:
                idx = data.find(pattern, idx)
                if idx == -1:
                    break
                raw = data[idx + 0x10:idx + 0x10 + 24]
                k = _parse_sso_key(raw)
                if k:
                    found_key = k
                    break
                idx += 1
            if found_key:
                break

        elapsed = time.time() - t0
        if found_key:
            _scanned_pid = pid
            _scanned_key = found_key
            _early_key_by_host['172.16.1.15'] = found_key
            _early_key_by_host['127.0.0.1'] = found_key
            _key_ready_event.set()
            log('KEYSCAN: SUCCESS in %.2fs! pid=%s key=%s' % (elapsed, pid, found_key))
            return found_key
        else:
            # Remember that the watcher already probed this process.  Before the
            # first LoginApp request the EncryptionFilter often does not exist yet,
            # so a miss is expected.  Leaving _scanned_pid on the previous process
            # made the 1.5s watcher immediately scan again and monopolise
            # _scan_lock; the request-triggered scan then sat behind several stale
            # scans until the Mercury login request had already timed out.  An
            # explicit fast_find_session_key(pid) still re-scans because the cache
            # fast path above requires both this PID *and* a non-empty key.
            _scanned_pid = pid
            _scanned_key = None
            log('KEYSCAN: no key found in %.2fs for pid=%s' % (elapsed, pid))
            return None


def get_or_wait_session_key(host='172.16.1.15', timeout=6.0):
    """Retrieve the verified live session key, waiting synchronously if a scan is in progress."""
    global _scanned_pid, _scanned_key
    pid = _get_pid()
    if pid and _scanned_pid == pid and _scanned_key:
        return _scanned_key

    # Start scan in background thread if needed and wait
    _key_ready_event.clear()
    threading.Thread(target=fast_find_session_key, args=(pid,), daemon=True).start()
    if _key_ready_event.wait(timeout=timeout):
        return _scanned_key or _early_key_by_host.get(host) or _BFKEY_HEX
    return _early_key_by_host.get(host) or _scanned_key or _BFKEY_HEX


def find_baseapp_key_async(client_addr, old_key_hex, done_callback):
    def _worker():
        key = fast_find_session_key()
        done_callback(key, [key] if key else [])
    threading.Thread(target=_worker, daemon=True).start()


def _pid_watcher_loop():
    """Background watcher that automatically detects game launch and acquires the key before PLAY."""
    global _scanned_pid
    while True:
        try:
            pid = _get_pid()
            if pid and pid != _scanned_pid:
                log('PID WATCHER: detected game pid=%s (was %s) - running fast keyscan...' % (pid, _scanned_pid))
                fast_find_session_key(pid)
        except Exception as e:
            pass
        time.sleep(1.5)

CAPTURE_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'captures', 'BASEAPP_LOGIN_CAPTURE.txt')

BASEAPP_HOST = '172.16.1.2'   # address the CLIENT (emulator guest) can reach us at
BASEAPP_PORT = 25010          # our fake BaseApp capture port
LOGINAPP_PORT = 25000

_lock = threading.Lock()

# Attempt J (2026-09-15, post-E2E-001 regression): per source-address "sticky"
# first-seen counter cache. E2E-001 found Attempt H's per-retry echoed counter
# fails 10/10 on a clean run, contradicting the earlier "confirmed 3 times"
# result. One untested hypothesis: Mercury retries resend the SAME logical
# pending request (same internally-tracked reply id, assigned once at first
# send), not a new id per retry -- so echoing whatever counter value arrives
# on retry N may be *wrong* once N>1, if the client's internal id stays fixed
# at retry 1's value. This cache lets ATTEMPT_J=1 always reply with the FIRST
# counter value seen from a given (ip,port), for every subsequent packet from
# that same source, instead of echoing each retry's own incremented counter.
_first_counter_seen = {}


def log(msg):
    with _lock:
        now = time.time()
        ts = '%s.%03d' % (time.strftime('%H:%M:%S', time.localtime(now)), int((now % 1) * 1000))
        line = '%s %s' % (ts, msg)
        print(line, flush=True)
        try:
            with open(CAPTURE_LOG, 'a', encoding='utf-8', errors='replace') as f:
                f.write(line + '\n')
        except Exception:
            pass


def build_login_reply_record(baseapp_ip, baseapp_port, session_key=0x12345678):
    """Best-effort LoginReplyRecord: two back-to-back Mercury::Address-shaped
    8-byte records (ip:4 BE, port:2 BE, pad:2) + a 4-byte trailing value.
    Total 20 bytes, matching the confirmed static read size (w1=0x14) in
    LoginHandler::onLoginReply. See LOGIN_REPLY_RECORD.md for the evidence
    and INFERRED/UNKNOWN status of this exact layout -- this is a dynamic
    experiment, not a confirmed-correct payload.
    """
    ip_bytes = socket.inet_aton(baseapp_ip)  # 4 bytes, network byte order
    addr = ip_bytes + struct.pack('!H', baseapp_port) + b'\x00\x00'  # 8 bytes
    record = addr + addr + struct.pack('<I', session_key)  # 8+8+4 = 20
    assert len(record) == 20
    return record


def serve_loginapp_udp_responder():
    log('=== FAKE LOGINAPP UDP :%d LISTENING (will reply with LoginReplyRecord) ===' % LOGINAPP_PORT)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', LOGINAPP_PORT))
    body = build_login_reply_record(BASEAPP_HOST, BASEAPP_PORT)
    while True:
        try:
            data, addr = s.recvfrom(8192)
            log('LOGINAPP UDP RECV %d bytes from %s:%d' % (len(data), addr[0], addr[1]))
            log('  HEX: %s' % data.hex())
            # Attempt D (2026-09-14, MERCURY_REPLY_DISPATCH_TRACE.md S6f) established
            # flags=0x0001 (a real value from our own captured client traffic) as the
            # correct first 2 wire bytes, fixing a "bad flags" rejection. Superseded below
            # by Attempt F, which replaces Attempt D's body/footer entirely once the
            # message-ID layer (msgID=172 collision) was understood -- see
            # MERCURY_MESSAGE_ID_TRACE.md for the full history.
            # Attempt F (2026-09-15, MERCURY_MESSAGE_ID_TRACE.md) -- current default,
            # supersedes Attempt D. A live /proc/<pid>/mem dump of the Nub's message
            # dispatch table (heap array at this+0x40, indexed by message ID, 32 bytes/
            # entry) shows message ID 255 (0xFF) is named "Reply" -- BigWorld's
            # Mercury::REPLY_MESSAGE_ID -- using a 4-byte variable-length prefix, with its
            # "handler" field self-referencing the Nub object (unlike every other named
            # message, which points to a distinct handler). This is the code-confirmed
            # message ID for ANY Mercury reply, including LoginReply. The trailing 2 zero
            # bytes are a mandatory footer (confirmed arithmetically: two independent
            # "not enough data" rejections, for msgid 172 and msgid 255, both showed a
            # "left" byte count exactly 2 less than the packet's actual remaining bytes).
            # Structure: [2-byte flags=1][1-byte msgID=0xFF][4-byte length=4]
            # [4-byte replyID][2-byte footer]. This eliminates EVERY
            # REASON_CORRUPTED_PACKET/framing rejection seen so far (Attempts A-E) -- the
            # packet is now fully accepted at the packet AND bundle-parsing level. The
            # remaining, more specific rejection is
            # "Mercury::Nub::handleMessage(...): Couldn't find handler for reply id
            # 0x00000000" -- i.e. the replyID value itself (currently a 0 placeholder,
            # deliberately NOT guessed further) must match whatever ID the client assigned
            # its own outgoing LogOnParams request. That correlation value has not yet
            # been located -- see MERCURY_MESSAGE_ID_TRACE.md's NEXT BLOCKER.
            # Attempt G (2026-09-15, MERCURY_REPLY_ID_TRACE.md): a live /proc/<pid>/mem
            # inspection of the Nub's reply-id hashtable (this+0x88 bucket array,
            # this+0x90 count) gave an ambiguous result. Rather than guess blindly, this
            # step instead echoes back the ONE per-request, client-generated,
            # plaintext-visible numeric value observable directly: the 2-byte
            # little-endian counter at request wire offset [5:7] (confirmed incrementing
            # by 1 on every retry, e.g. 0x4837, 0x4838, 0x4839...), zero-extended to the
            # confirmed 4-byte replyID width. This immediately eliminated
            # "Couldn't find handler for reply id" entirely.
            #
            # Attempt H (2026-09-15, MERCURY_REPLY_ID_TRACE.md) -- current default,
            # supersedes Attempt F. With only the replyID (Attempt G), the client moved to
            # a new, single-shot outcome: "logOnComplete: Logon failed / Unelaborated
            # error." Disassembly of LoginHandler::handleMessage (0x938070) shows it reads
            # a 1-byte status code first via a vtable read(1) call (0x9380a4: ldrb
            # w8,[x0]; cmp w8,#1) -- Attempt G's payload had zero bytes after the replyID,
            # so this read hit an exhausted stream. If status==1, the code proceeds
            # (confirmed at 0x938248: "mov w1,#0x14"/blr) to read exactly 20 more bytes,
            # matching the existing 20-byte LoginReplyRecord body exactly. This sends
            # [4-byte replyID][1-byte status=1][20-byte body], length=4+1+20=25.
            #
            # Attempt H's "CONFIRMED LIVE, reproduced twice" claim (2-byte counter at
            # wire offset [5:7], zero-extended) turned out NOT to be durable -- E2E-001/
            # E2E-002 (2026-09-15 later same day) found it failed 10/10 on two
            # independent fresh runs, and a "sticky first counter" variant also failed
            # 10/10. See PRIVATE_SERVER_REPLACEMENT_STATUS.md / END_TO_END_TEST_LOG.md
            # E2E-005 for the regression writeup.
            #
            # Attempt K (2026-09-15, E2E-006) -- CURRENT DEFAULT, supersedes Attempt H.
            # Per the PC ROS launcher's own documented fix for the identical bug class
            # (their correlation ID turned out to be a uint32 at offset 5, not a uint16
            # at offset 6 as originally assumed -- PC_LAUNCHER_STUDY.md SS2), a live
            # offset/width/endianness sweep (scratch/reply_id_sweep.sh) against this
            # exact client found the real field is a **4-byte little-endian value at
            # wire offset 5** (i.e. widen Attempt H's field by 2 bytes, same start
            # offset) -- CONFIRMED LIVE, reproduced twice with clean timestamp-isolated
            # logcat captures (adb logcat -T, since `logcat -c` was found this pass to
            # NOT actually clear the buffer on this device/build -- a new, reproducible
            # environmental quirk, not a script bug): both runs reach
            # "LoginHandler::onLoginReply" and "ServerConnection::checkScriptBaseAppAddr"
            # on the very FIRST attempt (23-37ms round-trip), zero retries needed --
            # stronger evidence than Attempt H's original claim, which relied on
            # retries. See END_TO_END_TEST_LOG.md E2E-006 for the full sweep record.
            if len(data) < 7:
                continue
            # 2026-09-18: the literal 9-byte ASCII payload b'hello ros' arrives on this
            # port too (confirmed present in the live client's own heap,
            # scratch/heap_dump/region_763849000000.bin -- this is genuine
            # client-originated traffic, not our own leftover test tooling). It has been
            # treated identically to a real 273-byte LogOnParams request for this
            # project's whole history (garbage replyID derived from interpreting " ros"
            # as a 4-byte LE counter), sending back a full crafted LoginReplyRecord in
            # reply to what is very likely a pre-Mercury reachability probe, not a real
            # login attempt. Never investigated as a possible source of the
            # connectLoginHostCallback status:1/2 non-determinism -- skip it now instead
            # of guessing a "correct" reply, since no reply format has ever been evidenced
            # for it, and sending a WRONG one may be actively confusing the client's own
            # session/attempt-counting state ahead of the real request.
            if data == b'hello ros':
                log('LOGINAPP: skipping probe packet (b"hello ros", %d bytes) from %s -- not replying' % (len(data), addr))
                continue
            # Kept configurable (not hardcoded) so a future regression or a still-
            # untested candidate can be swept again without editing this file --
            # see scratch/reply_id_sweep.sh. Defaults now reflect Attempt K.
            sweep_offset = int(os.environ.get('SWEEP_OFFSET', '5'))
            sweep_width = int(os.environ.get('SWEEP_WIDTH', '4'))
            sweep_endian = os.environ.get('SWEEP_ENDIAN', 'little')
            if len(data) < sweep_offset + sweep_width:
                log('SWEEP: packet too short for offset=%d width=%d (len=%d), skipping' % (sweep_offset, sweep_width, len(data)))
                continue
            raw_field = data[sweep_offset:sweep_offset + sweep_width]
            counter = int.from_bytes(raw_field, byteorder=sweep_endian, signed=False)
            if os.environ.get('SWEEP_ACTIVE') == '1':
                log('SWEEP: offset=%d width=%d endian=%s -> extracted=0x%x (raw=%s)' % (
                    sweep_offset, sweep_width, sweep_endian, counter, raw_field.hex()))
            if os.environ.get('ATTEMPT_J') == '1':
                # Sticky first-counter hypothesis -- see comment at top of file.
                if addr not in _first_counter_seen:
                    _first_counter_seen[addr] = counter
                    log('ATTEMPT_J: first packet from %s, caching counter=0x%04x' % (addr, counter))
                else:
                    log('ATTEMPT_J: retry from %s, wire counter=0x%04x but echoing CACHED first counter=0x%04x' % (addr, counter, _first_counter_seen[addr]))
                counter = _first_counter_seen[addr]
            inner = struct.pack('<I', counter) + bytes([1]) + body
            reply = (struct.pack('<H', 0x0001) + bytes([0xff])
                      + struct.pack('<I', len(inner)) + inner
                      + b'\x00\x00')
            log('ATTEMPT_H-shape (20-byte body): replyID=0x%08x status=1 + 20-byte body, length=%d' % (counter, len(inner)))
            # Attempt I / now CURRENT DEFAULT (2026-09-15, E2E-006): pads the 20-byte
            # body to 24 bytes (next multiple of 8), the single, minimal change the
            # "EncryptionFilter::decrypt: Input stream size (20) is not a multiple of
            # the block size (8)" WARNING names. Originally flagged UNKNOWN
            # (inconsistent/unreproduced under the OLD, broken Attempt-H reply-ID
            # extraction) -- re-tested this pass under the now-fixed Attempt K
            # reply-ID extraction (4-byte LE @ offset 5) and found to work cleanly,
            # twice: the decrypt WARNING disappears entirely and
            # `checkScriptBaseAppAddr` logs a non-zero, non-garbled-by-framing address
            # (still cryptographically WRONG content -- e.g. one run decoded
            # `217.217.193.87:13706`, not our intended 172.16.1.2:25010 -- because
            # this reply body is sent PLAINTEXT while the client unconditionally
            # Blowfish-DECRYPTS it with its own live per-connection key; see
            # END_TO_END_TEST_LOG.md E2E-006 and FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md
            # -- but the FRAMING/block-size problem this flag targets is genuinely
            # fixed). Kept opt-out (ATTEMPT_I=0) rather than removed, in case a future
            # regression needs the old 20-byte shape for comparison.
            if os.environ.get('ATTEMPT_I', '1') == '1':
                padded_body = body + b'\x00\x00\x00\x00'
                use_login_key = get_or_wait_session_key(addr[0], timeout=6.0)
                _key_cache[addr] = use_login_key
                _early_key_by_host[addr[0]] = use_login_key
                enc_body = bf_encrypt(padded_body, key_hex=use_login_key)
                # E2E-012: remember this message's LAST plaintext block, keyed
                # by client host -- if the BaseApp channel really does share
                # the SAME EncryptionFilter object (confirmed same key this
                # pass), its pc_variant chaining state would carry over from
                # here rather than resetting to zero for the "new" channel.
                _last_plain_block_by_host[addr[0]] = padded_body[-8:]
                if enc_body:
                    log('ATTEMPT_L: encrypted 24-byte body with Blowfish key=%s mode=%s -> %s' % (
                        use_login_key, _BF_MODE, enc_body.hex()))
                    payload_body = enc_body
                else:
                    payload_body = padded_body
                inner = struct.pack('<I', counter) + bytes([1]) + payload_body

                # E2E-038: optional trailing key-update block (0x32ef9816 magic +
                # length-prefixed blob), per re-disassembly of the marker this
                # project already fully mapped (see FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md).
                # Re-characterized this pass: NOT a version guard -- an entirely
                # unused (by us) optional mechanism that, when present, has the
                # client construct a SECOND keyed EncryptionFilter context from
                # ServerConnection+0x148. Content unknown; this is a placeholder
                # experiment (reusing the known Blowfish key bytes as filler) to
                # see if presence ALONE produces any observable client-side
                # effect, before worrying about correct content.
                if os.environ.get('ATTEMPT_KEYBLOCK', '0') == '1':
                    key_bytes = bytes.fromhex(use_login_key)
                    blob = key_bytes  # placeholder content -- see comment above
                    if len(blob) < 255:
                        len_prefix = bytes([len(blob)])
                    else:
                        len_prefix = bytes([0xFF]) + struct.pack('<I', len(blob))[:3]
                    keyblock = struct.pack('<I', 0x32ef9816) + len_prefix + blob
                    inner = inner + keyblock
                    log('ATTEMPT_KEYBLOCK: appended magic=0x32ef9816 + %d-byte blob (placeholder=key bytes %s)' % (
                        len(blob), use_login_key))

                reply = (struct.pack('<H', 0x0001) + bytes([0xff])
                          + struct.pack('<I', len(inner)) + inner
                          + b'\x00\x00')
                log('ATTEMPT_I (default): replyID=0x%08x status=1 + 24-byte %sbody, length=%d (key=%s)' % (
                    counter, 'ENCRYPTED ' if enc_body else 'padded ', len(inner), use_login_key))
            if os.environ.get('DEBUG_BADFLAGS') == '1':
                # Diagnostic-only toggle (MERCURY_MESSAGE_ID_TRACE.md Phase 2): deliberately
                # resend the OLD invalid flags value to make the client reprint
                # "Nub(<pointer>)::processFilteredPacket(...)" so we can capture a live
                # Nub object address for a one-shot /proc/<pid>/mem table dump. Not a new
                # protocol hypothesis - purely an instrumentation aid.
                reply = struct.pack('<H', 0x10ac) + body + b'\x00\x00'
            if os.environ.get('NO_REPLY') == '1':
                log('LOGINAPP UDP: NO_REPLY=1 set, deliberately NOT sending a reply (control experiment)')
            else:
                s.sendto(reply, addr)
                log('LOGINAPP UDP SENT framed reply (%d bytes) to %s:%d: %s' % (len(reply), addr[0], addr[1], reply.hex()))
        except Exception as e:
            log('LOGINAPP UDP error: %s' % e)


_SUPPLEMENT_CACHE = {}


def _supplement_runtime_record(record):
    """Build the dynamic record shape consumed by the Supply UIs.

    The static data_supplement row stores its price in the CURRENCY_OPTION
    variant.  UISupplyPackage reads the flattened fields below from the
    server-supplied dict (verified from decrypted client bytecode).
    """
    value = dict(record['value'])
    # SupplementBoxBase.KIND has schema default 1.  literal table rows omit
    # fields that use their inherited/default value.
    value.setdefault('KIND', 1)
    option = value.get('CURRENCY_OPTION')
    if isinstance(option, dict) and isinstance(option.get('value'), dict):
        option_type = option.get('type')
        fields = option['value']
        if option_type == 'ConstantCurrencyTypeWithMultiBuyPrice':
            value['CURRENCY_ID'] = fields.get('CURRENCY_TYPE')
            value['BUY_TIMES_PRICE'] = fields.get('PRICE')
            value['BUY_MULTIPLE_TIMES_PRICE'] = fields.get('MULTIPLE_BUY_PRICE')
        elif option_type == 'DoubleCurrencyTypeAndConstPrice':
            value['CURRENCY_ID'] = (fields.get('CURRENCY_TYPE1'), fields.get('CURRENCY_TYPE2'))
            value['BUY_TIMES_PRICE'] = (fields.get('PRICE1'), fields.get('PRICE2'))
        elif option_type == 'DoubleCurrencyTypeWithMultiBuyPrice':
            value['CURRENCY_ID'] = (fields.get('CURRENCY_TYPE1'), fields.get('CURRENCY_TYPE2'))
            value['BUY_TIMES_PRICE'] = (fields.get('PRICE1'), fields.get('PRICE2'))
            value['BUY_MULTIPLE_TIMES_PRICE'] = (
                fields.get('MULTIPLE_BUY_PRICE1'), fields.get('MULTIPLE_BUY_PRICE2'))
    # UISupplyPackage._showSupplementResult reads availSupplement[id]['NEXT_BUY_TIMES_PRICE'] (same shape as BUY_TIMES_PRICE).
    if 'BUY_TIMES_PRICE' in value:
        value.setdefault('NEXT_BUY_TIMES_PRICE', value['BUY_TIMES_PRICE'])
    return value


def supplement_avail_payload(per_kind=2, now=None):
    """Pickle (protocol 0) of {supplementID: record} for Athlete.onQueryAvailableSupplement.

    Records are the client's own data_supplement rows (APK assets.npk member 9e1c8652, tools/load_table.py) that are online and
    in sale; only `per_kind` of each KIND/type are sent so the RPC stays small. The record shape is an inference from
    common/supplement_utils (timeFilter/isInSaleFilter/preprocessOneSupplementBox) and is being verified live."""
    now = now or time.strftime('%Y.%m.%d %H:%M:%S')
    key = (per_kind, now[:10])
    if key in _SUPPLEMENT_CACHE:
        return _SUPPLEMENT_CACHE[key]
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
    import load_table as LT
    text = LT.read_member(0x9e1c8652).decode('utf-8')
    data = LT.parse_table(text)
    picked, count = {}, {}
    send_all = os.environ.get('ROS_SUPPLEMENT_ALL', '1') == '1'
    # Fields the Supply UIs read from the server dict (everything static comes from the client's own tables):
    # verified from decrypted UISupplyPackage / iSupplement code (NAME, CURRENCY_ID, BUY_TIMES_PRICE, NEXT_BUY_TIMES_PRICE,
    # BUY_MULTIPLE_TIMES_PRICE, CURRENT_DISCOUNT, ...). 248 records in this form are ~39 KB, under the 65,535-byte method limit.
    keep = ('NAME', 'CURRENCY_ID', 'BUY_TIMES_PRICE', 'NEXT_BUY_TIMES_PRICE', 'BUY_MULTIPLE_TIMES_PRICE', 'CURRENT_DISCOUNT',
            'KIND', 'IS_PREVIOUS_BOX', 'SORT_KEY', 'PURCHASE_LIMIT_NUM', 'CONTINUE_LOTTERY_TIMES')
    for sid in sorted(data):
        rec = data[sid]
        v = _supplement_runtime_record(rec)
        if not send_all:
            on = str(v.get('ONLINE_TIME', '')).replace('-', '.')
            off = str(v.get('OFFLINE_TIME', '')).replace('-', '.')
            if not (on <= now <= off) or not v.get('IS_IN_SALE', True):
                continue
            kind = v['KIND']
            is_prev = bool(rec['value'].get('IS_PREVIOUS_BOX'))
            if is_prev and per_kind and count.get(kind, 0) >= per_kind:
                continue
            if is_prev:
                count[kind] = count.get(kind, 0) + 1
        else:
            count[v['KIND']] = count.get(v['KIND'], 0) + 1
        picked[sid] = {k: v[k] for k in keep if k in v}
    payload = pickle.dumps(picked, protocol=0)
    if len(payload) > 65000:
        log('SUPPLEMENT: WARNING payload %d B exceeds the 2-byte method length; lower ROS_SUPPLEMENT_PER_KIND' % len(payload))
    log('SUPPLEMENT: %d of %d records, %d bytes pickled (kinds=%s)' % (len(picked), len(data), len(payload), sorted(count.items())))
    _SUPPLEMENT_CACHE[key] = payload
    return payload


# Client -> server exposed base-method indices (first payload byte of a 0xfa..0xfd message in a decrypted bundle), derived from live
# captures: the Supply page sends `fa 01 00 dd` (no args) each time it opens, and UIAdvanceSupplyPackage.on_enter calls
# base.queryAvailableSupplement() (base table idx 470). Everything else is logged so the mapping can be extended.
EXPOSED_METHODS = {0xdd: 'queryAvailableSupplement', 0xda: 'openSupplyBox', 0xdb: 'openSupplyBoxFree', 0xdc: 'openMultipleSupplyBox'}
# wire method index = base-method table index - 249 in this region (openSupplyBox 467 -> 0xda, queryAvailableSupplement 470 -> 0xdd; both live-verified).
_dev_yb = {'free': int(os.environ.get('ROS_DEV_FREE_YB_BALANCE', '999999'))}
_seen_exposed = set()


def parse_upstream_messages(unpadded):
    """Yield (msg_id, payload) for the [id][len16][payload] messages of a decrypted client packet (flags 0x0040 = 4-byte seq footer)."""
    if len(unpadded) < 8:
        return
    flags = struct.unpack('<H', unpadded[0:2])[0]
    body = unpadded[2:-4] if flags & 0x0040 else unpadded[2:]
    pos = 0
    while pos + 3 <= len(body):
        mid = body[pos]
        ln = struct.unpack('<H', body[pos + 1:pos + 3])[0]
        if mid < 0xfa or pos + 3 + ln > len(body):
            return
        yield mid, body[pos + 3:pos + 3 + ln]
        pos += 3 + ln


def handle_upstream_calls(sock, addr, key, unpadded):
    for mid, payload in parse_upstream_messages(unpadded):
        if not payload:
            continue
        method = payload[0]
        name = EXPOSED_METHODS.get(method)
        sig = (method, len(payload))
        if sig not in _seen_exposed:
            _seen_exposed.add(sig)
            log('UPSTREAM CALL: msg=0x%02x method=0x%02x (%d) %s args=%s' % (
                mid, method, method, name or '?', payload[1:1 + 24].hex()))
        if name in ('openSupplyBox', 'openMultipleSupplyBox') and len(payload) >= 9:
            sid, cur = struct.unpack_from('<ii', payload, 1)
            n = 10 if name == 'openMultipleSupplyBox' else 1
            prizes = supplement_pick_prizes(sid, n)
            blob = pickle.dumps(prizes, protocol=0)
            if name == 'openSupplyBox':
                reply = struct.pack('<i', sid) + _packed_int(len(blob)) + blob + bytes(1)
                ridx = 387      # onOpenSupplyBox(INT32 id, PYTHON appearanceIDs, BOOL isWatchAd)
            else:
                reply = struct.pack('<i', sid) + _packed_int(len(blob)) + blob
                ridx = 389      # onMultiOpenSupplyBox(INT32 id, PYTHON appearanceIDs)
            send_entity_method(sock, addr, key, 1, ridx, reply, flags=0x0008, num_methods=1131)
            log('BASEAPP: %s(id=%d cur=%d) -> prizes=%s (client idx %d)' % (name, sid, cur, prizes, ridx))
            price = supplement_cost(sid, cur, n)
            if cur == 2 and price and os.environ.get('ROS_DEV_FREE_SPEND', '1') == '1':
                # diamonds (YUANBAO) are freeYuanbao+payYuanbao: charge freeYuanbao and tell the client via onYBUpdated(INT64 free, INT64 pay, INT32 src) idx 203
                _dev_yb['free'] = max(_dev_yb['free'] - price, 0)
                send_entity_method(sock, addr, key, 1, 203, struct.pack('<qqi', _dev_yb['free'], 0, 0), flags=0x0008, num_methods=1131)
                log('BASEAPP: charged %d diamonds -> balance %d (onYBUpdated idx 203)' % (price, _dev_yb['free']))
            continue
        if name == 'queryAvailableSupplement':
            sup = supplement_avail_payload(int(os.environ.get('ROS_SUPPLEMENT_PER_KIND', '2')))
            delay = float(os.environ.get('ROS_SUPPLEMENT_REPLY_DELAY', '0'))

            def _reply(sup=sup, addr=addr, key=key):
                send_entity_method(sock, addr, key, 1, 392, _packed_int(len(sup)) + sup, flags=0x0008, num_methods=1131)
                log('BASEAPP: replied to queryAvailableSupplement with onQueryAvailableSupplement(%d B) to %s (delay %.2fs)' % (
                    len(sup), addr, delay))
            if delay > 0:
                threading.Timer(delay, _reply).start()
            else:
                _reply()


def _hall_prop_table():
    """Client hall-prop table (assets.npk member 5081e268 'chest props'): container props are PROP_TYPE RandomItem with a weighted PROP_LIST."""
    if 'props' not in _SUPPLEMENT_CACHE:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
        import load_table as LT
        _SUPPLEMENT_CACHE['props'] = LT.parse_table(LT.read_member(0x5081e268).decode('utf-8'))
    return _SUPPLEMENT_CACHE['props']


def _expand_prop(pid, depth=0):
    """Weighted expansion of a container prop down to a real item id (what the real server rolls when a box is opened)."""
    import random
    rec = _hall_prop_table().get(pid)
    if rec is None or depth > 6:
        return pid
    pt = rec.get('value', {}).get('PROP_TYPE') or {}
    if pt.get('type') != 'RandomItem':
        return pid
    lst = pt.get('value', {}).get('PROP_LIST') or []
    if not lst:
        return pid
    weights = [max(int(x.get('PROBABILITY', 1)), 0) for x in lst]
    if sum(weights) <= 0:
        weights = [1] * len(lst)
    pick = random.choices(lst, weights=weights, k=1)[0]
    return _expand_prop(int(pick['PROP_ID']), depth + 1)


def supplement_pick_prizes(sid, count):
    """Prize hall-prop ids for a draw. Pool = the box's own guarantee targets + SUPPLEMENT_LIST prop ids (client table data_supplement);
    every pick is expanded through the weighted RandomItem containers of the hall-prop table so the client shows real items.
    Guarantee counters and the real weights between pool entries are not modelled yet (uniform over the pool)."""
    import random
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
    import load_table as LT
    data = _SUPPLEMENT_CACHE.get('data')
    if data is None:
        data = LT.parse_table(LT.read_member(0x9e1c8652).decode('utf-8'))
        _SUPPLEMENT_CACHE['data'] = data
    v = data.get(sid, {}).get('value', {})
    pool = []
    for g in v.get('GUARANTEE_LIST') or []:
        val = g.get('value', {}) if isinstance(g, dict) else {}
        if 'GUARANTEE_PROP_ID' in val:
            pool.append(int(val['GUARANTEE_PROP_ID']))
    for it in v.get('SUPPLEMENT_LIST') or []:
        if isinstance(it, dict) and 'PROP_ID' in it:
            pool.append(int(it['PROP_ID']))
    if not pool:
        pool = [361154]
    return [_expand_prop(random.choice(pool)) for _ in range(count)]


def supplement_cost(sid, currency_id, times):
    """Price of `times` draws in `currency_id` from the box's CURRENCY_OPTION (single price for 1x, MULTIPLE_BUY_PRICE for 10x)."""
    data = _SUPPLEMENT_CACHE.get('data')
    opt = ((data or {}).get(sid, {}).get('value', {}).get('CURRENCY_OPTION') or {}).get('value', {})
    if 'CURRENCY_TYPE' in opt:
        return opt.get('MULTIPLE_BUY_PRICE' if times > 1 else 'PRICE', 0) if opt['CURRENCY_TYPE'] == currency_id else 0
    for i in ('1', '2'):
        if opt.get('CURRENCY_TYPE' + i) == currency_id:
            return opt.get(('MULTIPLE_BUY_PRICE' if times > 1 else 'PRICE') + i, opt.get('PRICE' + i, 0) * times) or 0
    return 0


def _packed_int(n):
    if n < 0xff:
        return bytes([n])
    return b'\xff' + struct.pack('<I', n)[:3]


_mercury_out_seq = {}
_mercury_out_seq_lock = threading.Lock()


def _send_encrypted_datagram(sock, dest, key, plain):
    """Pad, encrypt, and send one Mercury UDP datagram."""
    pad_len = 8 - (len(plain) % 8)
    padded = plain + b'\x00' * (pad_len - 1) + bytes([pad_len])
    enc = bf_encrypt(padded, key_hex=key, iv=b'\x00' * 8)
    wire = enc if enc else padded
    sock.sendto(wire, dest)
    return len(wire)


def send_mercury_message(sock, dest, key, message, flags=0x0008):
    """Send message bytes, fragmenting a bundle when it exceeds one UDP packet.

    ``message`` starts at the Mercury message ID (the packet flags are supplied
    separately). BigWorld fragment packets carry the same logical byte stream
    across packet bodies and end in three uint32 footers: fragment-begin,
    fragment-end, then this packet's sequence number.
    """
    # BigWorld Packet::maxCapacity() is 1472 - 2-byte header - 27 bytes of
    # reserved footer capacity. Staying at that official chunk size also leaves
    # enough room for the 12 bytes of actual fragment/sequence footers and the
    # Blowfish padding added by this client build.
    # The encrypted ROS client accepts a 1472-byte datagram. With a 2-byte
    # packet header and PKCS-style wastage padding, up to 1468 message bytes
    # fit in one packet (measured live: createBasePlayer stream <= 1459 B).
    single_packet_message_max = 1468
    fragment_body_max = 1443
    if len(message) <= single_packet_message_max:
        return [_send_encrypted_datagram(sock, dest, key,
                                         struct.pack('<H', flags) + message)]

    chunks = [message[i:i + fragment_body_max]
              for i in range(0, len(message), fragment_body_max)]
    with _mercury_out_seq_lock:
        first_seq = _mercury_out_seq.get(dest, 0)
        _mercury_out_seq[dest] = first_seq + len(chunks)
    last_seq = first_seq + len(chunks) - 1

    # Fragment identity requires FLAG_IS_FRAGMENT and a sequence footer. Do not
    # force FLAG_IS_RELIABLE here: reliability is a property of the declared
    # message, while fragment sequence numbers are also valid on their own.
    # The ROS client otherwise routes these ad-hoc sequence IDs through its
    # reliable receive window before the fragment collector sees them.
    fragment_flags = flags | 0x0020 | 0x0040
    wire_sizes = []
    for index, chunk in enumerate(chunks):
        seq = first_seq + index
        footer = struct.pack('<III', first_seq, last_seq, seq)
        plain = struct.pack('<H', fragment_flags) + chunk + footer
        wire_sizes.append(_send_encrypted_datagram(sock, dest, key, plain))
    log('MERCURY: sent fragmented bundle packets=%d seq=%d..%d message=%d B wire=%s flags=0x%04x' % (
        len(chunks), first_seq, last_seq, len(message), wire_sizes, fragment_flags))
    return wire_sizes


def send_entity_method(sock, dest, key, entity_id, method_index, args=b'', flags=0x0008, num_methods=1131):
    """Encodes and sends an entity method call using BigWorld Mercury's exact wire protocol
    reversed from libclient.so (FUN_00a478a8 and 0xad03b0).
    """
    div = (num_methods + 192) // 255
    threshold = 62 - div

    if method_index < threshold:
        w1 = method_index
        extra_byte = b''
    else:
        diff = method_index - threshold
        w1 = threshold + (diff // 256)
        extra_byte = bytes([diff % 256])

    msgid = 128 + w1
    width = 2 if w1 < 64 else 1

    payload = struct.pack('<I', entity_id) + extra_byte + args
    lenfield = struct.pack('<I', len(payload))[:width]

    if len(payload) > 65535 and width == 2:
        raise ValueError('method payload %d B exceeds the 2-byte length field' % len(payload))
    if 1 + len(lenfield) + len(payload) > 1468:
        # The client drops any datagram above ~1472 B (EncryptionFilter::recv, see notes Checkpoint 20). Large method calls
        # (e.g. onQueryAvailableSupplement, tens of KB) must be sent as a Mercury fragment bundle like createBasePlayer.
        send_mercury_message(sock, dest, key, bytes([msgid]) + lenfield + payload, flags=flags)
        return
    plain = struct.pack('<H', flags) + bytes([msgid]) + lenfield + payload
    pad_len = 8 - (len(plain) % 8)
    plain_padded = plain + b'\x00' * (pad_len - 1) + bytes([pad_len])
    enc = bf_encrypt(plain_padded, key_hex=key, iv=b'\x00' * 8)
    sock.sendto(enc if enc else plain_padded, dest)


def send_create_cell_player(sock, dest, key, space_id=1, vehicle_id=0, pos=(0.0, 0.0, 0.0), dir_rot=(0.0, 0.0, 0.0), stream=b'', flags=0x0008):
    """Encodes and sends createCellPlayer (ClientInterface msgID 6) using BigWorld Mercury's wire protocol.
    Reversed from libclient.so FUN_00a47e8c (handler) -> slot 1 FUN_00a1894c -> slot 6 FUN_00a19b1c -> Entity::readCellPlayerData.
    Header: spaceID(u32 LE), vehicleID(u32 LE), pos(3*f32 LE), dir(3*f32 LE) = 32 bytes prefix.
    Payload: prefix (32 bytes) + stream (empty stream b'' triggers newDictionary(domain=1) to populate all 454 client properties with defaults).
    Length prefix: uint16 LE (ClientInterface msgID 6 has lenfield=2).
    """
    x, y, z = pos
    yaw, pitch, roll = dir_rot
    body = struct.pack('<IIffffff', space_id, vehicle_id, x, y, z, yaw, pitch, roll) + stream
    plain = struct.pack('<H', flags) + bytes([0x06]) + struct.pack('<H', len(body)) + body
    pad_len = 8 - (len(plain) % 8)
    plain_padded = plain + b'\x00' * (pad_len - 1) + bytes([pad_len])
    enc = bf_encrypt(plain_padded, key_hex=key, iv=b'\x00' * 8)
    sock.sendto(enc if enc else plain_padded, dest)


def send_character_creation_response_chain(sock, dest, key, athlete_eid, char_type=None, nick=None):
    """Sends the authoritative response sequence for character creation / lobby entry."""
    if char_type is None:
        char_type = int(os.environ.get('ROS_BASE_CHAR_TYPE', '10002'))
    if nick is None:
        nick = os.environ.get('ROS_BASE_NICKNAME', 'Dev | Raysoo').encode('utf-8')
    elif isinstance(nick, str):
        nick = nick.encode('utf-8')

    # 1. Athlete.onCreateCharacter(True, "") (idx 1084)
    occ_args = struct.pack('<B', 1) + _packed_int(0)
    send_entity_method(sock, dest, key, athlete_eid, 1084, occ_args, flags=0x0008, num_methods=1131)
    log('BASEAPP: sent Athlete.onCreateCharacter(ret=1, reason="") idx=1084 to eid=%d %s' % (athlete_eid, dest))

    # 2. Athlete.onRoleCreateSuc(char_type) (idx 1085)
    if os.environ.get('ROS_SEND_ROLE_CREATE_SUC', '1') == '1':
        time.sleep(0.05)
        orcs_args = struct.pack('<i', char_type)
        send_entity_method(sock, dest, key, athlete_eid, 1085, orcs_args, flags=0x0008, num_methods=1131)
        log('BASEAPP: sent Athlete.onRoleCreateSuc(%d) idx=1085 to eid=%d %s' % (char_type, athlete_eid, dest))

    # 3. Athlete.updateBaseCharacter(char_type) (idx 1087)
    time.sleep(0.05)
    ubc_args = struct.pack('<i', char_type)
    send_entity_method(sock, dest, key, athlete_eid, 1087, ubc_args, flags=0x0008, num_methods=1131)
    log('BASEAPP: sent Athlete.updateBaseCharacter(%d) idx=1087 to eid=%d %s' % (char_type, athlete_eid, dest))

    # 4. Athlete.updateBaseNickname(nick) (idx 1088)
    time.sleep(0.05)
    ubn_args = _packed_int(len(nick)) + nick
    send_entity_method(sock, dest, key, athlete_eid, 1088, ubn_args, flags=0x0008, num_methods=1131)
    log('BASEAPP: sent Athlete.updateBaseNickname(%r) idx=1088 to eid=%d %s' % (nick, athlete_eid, dest))

    # 5. Athlete.onLeaveHallTeam() (idx 59) -- KNOWN INEFFECTIVE, disabled by default.
    # Retracted (06_notes/GHIDRA_PACKET_PARSER_TRACE.md, commit 5b7b911): onLeaveHallTeam
    # itself calls isInFormedTeam() -> reads self.hallTeamData, which is exactly the
    # attribute this call was meant to work around. Calling an RPC that depends on the
    # missing property cannot substitute for the property actually existing.
    # The real mechanism (property-stream deserialization via EntityType::newDictionary /
    # FUN_00acf5ec / FUN_00acf8ac) is documented in that file; hallTeamData itself has
    # BASE-only flags (0x08), not BASE_AND_CLIENT, so it is never sent to the client at
    # all via that path either -- its origin remains unresolved. Left gated behind an
    # opt-in env var rather than deleted, in case a future session wants to re-probe it.
    if os.environ.get('ROS_SEND_LEAVE_TEAM', '0') == '1':
        time.sleep(0.05)
        send_entity_method(sock, dest, key, athlete_eid, 59, b'', flags=0x0008, num_methods=1131)
        log('BASEAPP: sent Athlete.onLeaveHallTeam() idx=59 to eid=%d %s' % (athlete_eid, dest))

    # 6. Athlete.enterHall(True) (idx 1091)
    time.sleep(0.1)
    eh_args = struct.pack('<B', 1)
    send_entity_method(sock, dest, key, athlete_eid, 1091, eh_args, flags=0x0008, num_methods=1131)
    log('BASEAPP: sent Athlete.enterHall(True) idx=1091 to eid=%d %s' % (athlete_eid, dest))

    # Server-pushed interface state that is not part of the Athlete property stream.  Keep the
    # verified character/lobby RPC order above intact; these initializers run only afterwards,
    # while the hall scene is still loading.  Method 745 was verified from the live 1,131-entry
    # Athlete client-method table (neighbors 749..751 are sync/onShowOld/onShowNewCarnivalBg).
    lucky_carnival = {
            'operation': 0,
            'luckySeasonDraws': 0,
            'luckyRoundCloseTime': 0,
            'luckySeasonNo': 0,
            'luckyRoundBuff': 0,
            'luckyRoundState': 0,
            'luckySeasonEndTime': 0,
            'luckySeasonGiftGotState': [],
            'luckyRoundGotIndex': [],
            'luckyRoundGift': [],
            'luckyRoundDraws': 0,
            'luckyRoundNo': 0,
            'luckySeasonCharge': 0,
            'luckyRoundGiftValue': [],
            'luckyRoundRefreshTime': 0,
            'luckyRoundIsSuper': False,
            'luckyRoundByRecommend': False,
    }
    lucky_carnival_pickle = pickle.dumps(lucky_carnival, protocol=0)
    hall_state_rpcs = [
        # gmsyncRedPoints(ARRAY<RED_POINT>): UIMain.displayAll passes Globals.redPoints
        # directly to showRedPoint(), so the server must initialize it even when empty.
        (1099, struct.pack('<I', 0), 'Athlete.gmsyncRedPoints([])'),
        (745, _packed_int(len(lucky_carnival_pickle)) + lucky_carnival_pickle,
         'Athlete.onUpdateLuckyCarnivalData'),
        # These two attributes are BASE-only, so the property stream cannot carry them, yet UIMain reads them on
        # enter (UIMain.on_enter -> iMonthPayRebateSpecialAward.is_all_award_done, UIMainLiveIcon.showActivityRedBadge).
        # The uncaught AttributeError aborts the rest of UIMain.on_enter. Indices 768 / 754 read from the live
        # 1,131-entry Athlete method-name table (scratch/dump_athlete_methods.py).
        # syncMonthPayRebateSpecialAwardInfo(PYTHON info)
        # is_all_award_done does info['awards'] (live KeyError with {}), so the dict needs an 'awards' key.
        (768, _packed_int(len(pickle.dumps({'awards': {}}, protocol=0))) + pickle.dumps({'awards': {}}, protocol=0),
         "Athlete.syncMonthPayRebateSpecialAwardInfo({'awards': {}})"),
        # onPersonalRecommendStateUpdated(INT32 state, INT32 refreshTime, PYTHON gift, INT32 version)
        (754, struct.pack('<ii', 0, 0) + _packed_int(len(pickle.dumps({}, protocol=0))) +
         pickle.dumps({}, protocol=0) + struct.pack('<i', 0),
         'Athlete.onPersonalRecommendStateUpdated(0,0,{},0)'),
    ]
    # onQueryAvailableSupplement(PYTHON availSupplementDict) idx 392 (live table). Without it the Supply page is empty and DRAW sends nothing.
    _sup_n = int(os.environ.get('ROS_SUPPLEMENT_PER_KIND', '2'))
    if _sup_n >= 0 and os.environ.get('ROS_SUPPLEMENT', '1') == '1':
        _sup = supplement_avail_payload(_sup_n)
        hall_state_rpcs.append((392, _packed_int(len(_sup)) + _sup, 'Athlete.onQueryAvailableSupplement(%d B)' % len(_sup)))
    # ---- RPCs that only take visible effect once UIMain exists (sent again at ROS_HALL_LATE_DELAYS seconds) ----
    # UIMain is built roughly 60-90 s after enterHall (depends on when "Please select controls" is confirmed); an
    # earlier call finds no widget to update. All of these are idempotent, so they are simply resent.
    late_rpcs = []
    # onGetAnniversaryAirShipRank(INT64 rank, INT64 score, STRING isOpen, INT64 leftTime, INT64 rankListLength):
    # UIMain.refreshAirShipPanel(isOpen, leftTime) drives btn_airship's panel_coming/panel_ready/panel_finish.
    # Without it all three panels render at once (overlapping "Finish" / "check the <time>" above Ranked).
    # Index 873 derived from the entity_0177 ClientMethods order anchored on live-verified names at 853/859/860/864.
    # isOpen values seen in the script constants: 'end', 'over', 'open', 'ready'; 'end' verified live = "Finish".
    # OPT-IN (ROS_AIRSHIP_STATE=end): default off because the RPC also opens the full-screen AIRSHIP BATTLE page (live-verified,
    # even with a single send); the label fix is a side effect of that. NOT idempotent: the RPC also calls UIAirShipRankList.refreshUI/enter_ui, so a second call pops the full-screen
    # "AIRSHIP BATTLE" page over the hall (seen live). Send it exactly once, ROS_AIRSHIP_DELAY seconds after enterHall.
    airship_state = os.environ.get('ROS_AIRSHIP_STATE', '-').encode('utf-8')
    if airship_state != b'-':
        airship_payload = (struct.pack('<qq', 0, 0) + _packed_int(len(airship_state)) + airship_state +
                           struct.pack('<qq', 0, 0))
        airship_label = 'Athlete.onGetAnniversaryAirShipRank(isOpen=%s)' % airship_state.decode('utf-8')

        def _send_airship_once():
            send_entity_method(sock, dest, key, athlete_eid, 873, airship_payload, flags=0x0008, num_methods=1131)
            log('BASEAPP: (once) sent %s idx=873 to eid=%d %s' % (airship_label, athlete_eid, dest))
        threading.Timer(float(os.environ.get('ROS_AIRSHIP_DELAY', '90')), _send_airship_once).start()
    # iCurrency client methods (entity_0385), runtime indices read straight from the live Athlete method table:
    # onSPUpdated(INT64 sp, INT32 src)=201, onGPUpdated(INT64 gp, INT32 src)=202,
    # onYBUpdated(INT64 freeYuanbao, INT64 payYuanbao, INT32 src)=203. Each sets the property and calls
    # onCurrencyChangedToUI, which is what refreshes the top-bar CurrencyBarComp (it otherwise keeps the prefab "283283").
    dev_gp = int(os.environ.get('ROS_DEV_GP', '100000'))
    dev_sp = int(os.environ.get('ROS_DEV_SP', '5000'))
    dev_free_yb = int(os.environ.get('ROS_DEV_FREE_YB', '10000'))
    dev_pay_yb = int(os.environ.get('ROS_DEV_PAY_YB', '0'))
    if os.environ.get('ROS_DEV_CURRENCY', '0') == '1':
        late_rpcs.append((202, struct.pack('<qi', dev_gp, 0), 'Athlete.onGPUpdated(%d)' % dev_gp))
        late_rpcs.append((201, struct.pack('<qi', dev_sp, 0), 'Athlete.onSPUpdated(%d)' % dev_sp))
        late_rpcs.append((203, struct.pack('<qqi', dev_free_yb, dev_pay_yb, 0),
                          'Athlete.onYBUpdated(free=%d, pay=%d)' % (dev_free_yb, dev_pay_yb)))
    if os.environ.get('ROS_CURRENCY_PROBE', '0') == '1':
        # Discovery aid: onCurrencyUpdated(INT32 id, INT64 val, INT32 src)=204 with val = 1000 + id for each MallCurrencyType id.
        # The number that appears in the top-bar coin slot reveals which id that slot (UIMain.curExchangeCoin) shows.
        for cid in list(range(1, 24)) + [30, 31, 32, 91, 199, 201, 202, 207, 208, 209, 210, 211, 212, 213, 214, 99999]:
            if cid not in (2, 7):       # YUANBAO / PAY_YUANBAO are derived from freeYuanbao/payYuanbao
                late_rpcs.append((204, struct.pack('<iqi', cid, 1000 + cid, 0), 'Athlete.onCurrencyUpdated(id=%d, %d)' % (cid, 1000 + cid)))
    late_delays = [float(x) for x in os.environ.get('ROS_HALL_LATE_DELAYS', '45,90,150').split(',') if x.strip()]

    def _send_late_rpcs(delay):
        for method_index, payload, label in late_rpcs:
            send_entity_method(sock, dest, key, athlete_eid, method_index, payload,
                               flags=0x0008, num_methods=1131)
            log('BASEAPP: (late %.0fs) sent %s idx=%d to eid=%d %s' % (delay, label, method_index, athlete_eid, dest))
            time.sleep(0.05)

    if late_rpcs:
        for d in late_delays:
            threading.Timer(d, _send_late_rpcs, args=(d,)).start()
    for method_index, payload, label in hall_state_rpcs:
        time.sleep(0.05)
        send_entity_method(sock, dest, key, athlete_eid, method_index,
                           payload, flags=0x0008, num_methods=1131)
        log('BASEAPP: sent %s idx=%d to eid=%d %s' %
            (label, method_index, athlete_eid, dest))

    # Optional post-hall leave team reassert -- same known-ineffective workaround, see above.
    if os.environ.get('ROS_SEND_LEAVE_TEAM_POST', '0') == '1':
        time.sleep(0.1)
        send_entity_method(sock, dest, key, athlete_eid, 59, b'', flags=0x0008, num_methods=1131)
        log('BASEAPP: sent Athlete.onLeaveHallTeam() idx=59 (post-hall) to eid=%d %s' % (athlete_eid, dest))


_stage_machine_started = set()


def run_baseapp_stage_machine(sock, addr, key):
    """Clean 5-stage BigWorld entity lifecycle for mobile track:
    Stage 1: createBasePlayer(Account, type 38, eid=1)
    Stage 2: Account.onChannelLogin(19) + Account.onLogin(18)
    Stage 3: createBasePlayer(Athlete, type 51, eid=1, stream=b'') (empty stream bypasses unpack via PyDict_New)
    Stage 4: Athlete.showSelectCharacter([]) idx=1083 (Candidate A: msgID 101, Candidate B: msgID 187)
    Stage 5: HOLDING (no re-push; keepalive and ACK continue in background)
    """
    try:
        # Stage 1: createBasePlayer for Account
        time.sleep(0.05)
        use_key = _key_cache.get(addr) or _early_key_by_host.get(addr[0]) or key or _BFKEY_HEX
        account_eid = int(os.environ.get('ROS_ACCOUNT_EID', '1'))
        account_type = int(os.environ.get('ROS_ACCOUNT_TYPE', '38'))
        cbp_flags = int(os.environ.get('CBP_FLAGS', '0x0008'), 16)

        cbp_body = struct.pack('<I', account_eid) + struct.pack('<H', account_type)
        filler = b'\x00\x00' if (cbp_flags & 1) != 0 else b''
        cbp_plain = (struct.pack('<H', cbp_flags) + bytes([0x05])
                      + struct.pack('<H', len(cbp_body)) + cbp_body
                      + filler)
        cbp_pad_len = 8 - (len(cbp_plain) % 8)
        cbp_padded = cbp_plain + b'\x00' * (cbp_pad_len - 1) + bytes([cbp_pad_len])
        cbp_enc = bf_encrypt(cbp_padded, key_hex=use_key, iv=b'\x00' * 8)
        sock.sendto(cbp_enc if cbp_enc else cbp_padded, addr)
        log('BASEAPP STAGE 1: sent createBasePlayer(Account type=%d, eid=%d) to %s' % (
            account_type, account_eid, addr))

        # Stage 2: Account onChannelLogin and onLogin
        time.sleep(0.1)
        use_key = _key_cache.get(addr) or _early_key_by_host.get(addr[0]) or key or _BFKEY_HEX
        import pickle
        # Live-confirmed (2026-09-19, scratch/live_logcat_charcreate_test.txt):
        #   entities\Account.py:56 onChannelLogin -> helpers\channel\channel_login.py:411
        #   onLoginByServerSauth -> KeyError: 'aid'
        # The client indexes sauth by keys we don't know the full set of, and script.npk is
        # encrypted so the key list can't be read statically. ROS_SAUTH_DEFAULTDICT=1 (default)
        # ships a collections.defaultdict instead of a plain dict so every unknown key yields
        # '' instead of raising, letting one live test reveal the whole downstream path at once
        # rather than one KeyError per server restart.
        sauth_known = {
            'uid': '900000001',
            'aid': '900000001',
            'session': 'sess_local_fake_token',
            'sdk_version': '1.0.0',
            'channel': 'netease_global',
        }
        if os.environ.get('ROS_SAUTH_DEFAULTDICT', '1') == '1':
            import collections
            sauth = collections.defaultdict(str, sauth_known)
        else:
            sauth = sauth_known
        p = pickle.dumps(sauth, protocol=2)
        ocl_args = struct.pack('<B', 0) + _packed_int(len(p)) + p
        ol_args = struct.pack('<i', 0) + _packed_int(0)

        send_entity_method(sock, addr, use_key, account_eid, 19, ocl_args, flags=0x0008)
        log('BASEAPP STAGE 2: sent Account.onChannelLogin(idx=19) to eid=%d %s' % (account_eid, addr))
        time.sleep(0.04)
        send_entity_method(sock, addr, use_key, account_eid, 18, ol_args, flags=0x0008)
        log('BASEAPP STAGE 2: sent Account.onLogin(idx=18, OK) to eid=%d %s' % (account_eid, addr))

        # Stage 3: replace player with Athlete (type 51) + empty property stream
        # Disassembly proof (0x92a58c EntityType::newDictionary): empty stream jumps directly
        # to PyDict_New(), bypassing the property stream unpack and setting defaults cleanly!
        time.sleep(0.15)
        use_key = _key_cache.get(addr) or _early_key_by_host.get(addr[0]) or key or _BFKEY_HEX
        athlete_eid = int(os.environ.get('ROS_ATHLETE_EID', '1'))
        athlete_type = int(os.environ.get('ROS_ATHLETE_TYPE', '51'))

        # Empty stream by default
        athlete_stream = b''
        if os.environ.get('ROS_ATHLETE_USE_STREAM_FILE') == '1':
            stream_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'athlete_mobile_stream.bin')
            if os.path.isfile(stream_path):
                try:
                    with open(stream_path, 'rb') as f:
                        athlete_stream = f.read()
                    log('BASEAPP STAGE 3: loaded %d bytes from athlete_mobile_stream.bin' % len(athlete_stream))
                except Exception as e:
                    log('BASEAPP STAGE 3: error loading stream: %s' % e)

        athlete_cbp_body = struct.pack('<I', athlete_eid) + struct.pack('<H', athlete_type) + athlete_stream
        athlete_filler = b'\x00\x00' if (cbp_flags & 1) != 0 else b''
        athlete_cbp_message = (bytes([0x05])
                               + struct.pack('<H', len(athlete_cbp_body))
                               + athlete_cbp_body + athlete_filler)
        athlete_wire_sizes = send_mercury_message(
            sock, addr, use_key, athlete_cbp_message, flags=cbp_flags)
        log('BASEAPP STAGE 3: sent createBasePlayer(Athlete type=%d, eid=%d, stream=%d B) to %s' % (
            athlete_type, athlete_eid, len(athlete_stream), addr))
        log('BASEAPP STAGE 3: createBasePlayer wire datagrams=%s' % athlete_wire_sizes)

        # Stage 3.5: createCellPlayer for Athlete (ClientInterface msgID 6, 0x06)
        # Transition entity to cell domain: fires Entity::readCellPlayerData -> EntityType::newDictionary(domain=1),
        # which sets defaults for all 454 client properties in PyDict_New() and updates self.__dict__,
        # then executes ClientApp vtable slot 3, calling onBecomeCellPlayer!
        if os.environ.get('ROS_SEND_CELL_PLAYER', '0') == '1':
            time.sleep(0.05)
            space_id = int(os.environ.get('ROS_SPACE_ID', '1'))
            send_create_cell_player(sock, addr, use_key, space_id=space_id, vehicle_id=0, stream=b'', flags=0x0008)
            log('BASEAPP STAGE 3.5: sent createCellPlayer(spaceID=%d, eid=%d, stream=0 B) to %s' % (
                space_id, athlete_eid, addr))

        # Stage 4: Athlete character activation & enterHall
        # Root cause of _realEnterHall crash:
        # In Athlete.py:656, _realEnterHall calls GameObject.Find('Scene').GetComponent('SceneSystem').loadHallScene(...)
        # If the 3D scene (HALL_BASE_SCENE) was never loaded, GameObject.Find('Scene') returns None!
        # Athlete.showSelectCharacter(idx 1083) runs _loadDefaultScene() which sets world.set_active_scene(HALL_BASE_SCENE).
        # Disassembly evidence (libclient.so 0x9a4b74): SequenceDataType reads a 4-byte uint32 LE count prefix (mov w1, #4; blr read; ldr w21, [x0]).
        # Therefore ARRAY<STRING> with 0 elements requires struct.pack('<I', 0) (4 zero bytes, not 1 zero byte).
        time.sleep(0.1)
        use_key = _key_cache.get(addr) or _early_key_by_host.get(addr[0]) or key or _BFKEY_HEX

        # Step 4a: Athlete.showSelectCharacter([]) (idx 1083) to initialize 3D scene / Character UI
        if os.environ.get('ROS_SHOW_SELECT', '1') == '1':
            ssc_args = struct.pack('<I', 0) # 4-byte LE count = 0
            send_entity_method(sock, addr, use_key, athlete_eid, 1083, ssc_args, flags=0x0008, num_methods=1131)
            log('BASEAPP STAGE 4: sent Athlete.showSelectCharacter([]) idx=1083 (ARRAY<STRING> count=0, 4 bytes) to eid=%d %s' % (athlete_eid, addr))

        # Step 4b: Auto enter hall if configured
        if os.environ.get('ROS_AUTO_ENTER_HALL', '1') == '1':
            scene_delay = float(os.environ.get('ROS_SCENE_LOAD_DELAY', '2.5'))
            log('BASEAPP STAGE 4: waiting %.1fs for client _loadDefaultScene to instantiate Scene GameObject...' % scene_delay)
            time.sleep(scene_delay)
            send_character_creation_response_chain(sock, addr, use_key, athlete_eid)
        else:
            log('BASEAPP STAGE 4: ROS_AUTO_ENTER_HALL=0 -> Waiting in Character Creation UI for user interaction / upstream RPC.')

        # Stage 5: HOLDING
        log('BASEAPP STAGE 5: All entity lifecycle stages complete. Entering HOLDING state for %s' % (addr,))
    except Exception as e:
        log('BASEAPP STAGE MACHINE error: %s' % e)


def serve_baseapp_udp_capture():
    # E2E-008 (2026-09-15): first BaseApp reply attempt. Per
    # 06_trace/BASEAPP_LOGIN_SERIALIZATION.md SS2, `baseAppLogin` (method ID 0 in
    # BaseAppExtInterface, confirmed by the captured wire byte [2]=0x00) is a
    # VARIABLE_LENGTH_MESSAGE with a u16 length prefix; the request's 11-byte body
    # starts with what looks like a 4-byte LE correlation value (e5 32 00 00, ...,
    # incrementing by 1 across Mercury's own reliable-channel retransmissions of the
    # SAME logical request -- BASEAPP_LOGIN_SERIALIZATION.md SS3 confirms the client
    # only builds ONE BaseAppLoginRequest per ServerConnection, so these repeats are
    # Mercury channel-level retransmission, not new logical attempts).
    #
    # ATTEMPT_BASEAPP_REPLY (default ON): echoes back a Mercury reply using the SAME
    # generic [flags=1][msgID=0xFF][u32 length][u32 replyID][statusByte] shape that
    # unblocked LoginApp (Attempt H/K), on the theory that Mercury's generic
    # request/reply correlation mechanism is shared infrastructure across interfaces,
    # not specific to LoginApp. This is a HYPOTHESIS, not yet confirmed correct for
    # BaseApp -- the exact `baseAppLogin` reply body fields are UNKNOWN
    # (BASEAPP_LOGIN_SERIALIZATION.md SS4). No entity/DEF-encoded payload is attempted
    # here; this is deliberately the smallest possible experiment first.
    log('=== FAKE BASEAPP UDP :%d LISTENING (Attempt-BaseApp-Reply active) ===' % BASEAPP_PORT)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', BASEAPP_PORT))
    while True:
        try:
            data, addr = s.recvfrom(65536)
            log('*** BASEAPP UDP RECV %d bytes from %s:%d ***' % (len(data), addr[0], addr[1]))
            log('  HEX: %s' % data.hex())
            log('  ASCII: %r' % data)
            # 1. Check for initial PLAINTEXT baseAppLogin request BEFORE any decryption
            # Wire format: [flags: 0x0001][method: 0x00][len: 0x000b][corr: u32 LE @ 5..9]...
            if os.environ.get('ATTEMPT_BASEAPP_REPLY', '1') == '1' and len(data) >= 9 and data[0:2] == b'\x01\x00' and data[2] == 0:
                method_id = data[2]
                corr = struct.unpack('<I', data[5:9])[0]
                if addr not in _key_cache and addr[0] in _early_key_by_host:
                    _key_cache[addr] = _early_key_by_host[addr[0]]
                    log('BASEAPP: using key=%s from EARLY scan for %s' % (_early_key_by_host[addr[0]], addr))
                if addr not in _key_scan_started:
                    _key_scan_started.add(addr)
                    _key_cache.setdefault(addr, _BFKEY_HEX)
                    def _on_scan_done(new_key, all_keys, addr=addr):
                        if new_key:
                            _key_cache[addr] = new_key
                            log('BASEAPP KEYSCAN: using NEW distinct key=%s for %s' % (new_key, addr))
                        else:
                            log('BASEAPP KEYSCAN: no key distinct from LoginApp (%s) found for %s' % (_BFKEY_HEX, addr))
                    find_baseapp_key_async(addr, _BFKEY_HEX, _on_scan_done)

                use_key = _key_cache.get(addr) or _early_key_by_host.get(addr[0]) or _BFKEY_HEX
                inner = struct.pack('<I', corr) + bytes([1])
                plain = (struct.pack('<H', 0x0001) + bytes([0xff])
                          + struct.pack('<I', len(inner)) + inner
                          + b'\x00\x00')
                pad_len = 8 - (len(plain) % 8)
                plain_padded = plain + b'\x00' * (pad_len - 1) + bytes([pad_len])
                enc = bf_encrypt(plain_padded, key_hex=use_key, iv=b'\x00' * 8)
                reply = enc if enc else plain_padded
                s.sendto(reply, addr)
                log('BASEAPP UDP SENT whole-packet-encrypted ack for method=0x%02x corr=0x%08x key=%s (%d bytes): %s' % (
                    method_id, corr, use_key, len(reply), reply.hex()))

                # Start coordinated Stage Machine for this connection
                if addr not in _stage_machine_started:
                    _stage_machine_started.add(addr)
                    threading.Thread(target=run_baseapp_stage_machine,
                                      args=(s, addr, use_key), daemon=True).start()

                if os.environ.get('ATTEMPT_KEEPALIVE', '1') == '1':
                    _start_keepalive(s, addr, use_key)
                continue

            # 2. Decrypt encrypted channel packets
            unpadded = None
            if len(data) % 8 == 0 and len(data) >= 8:
                use_k = _key_cache.get(addr) or _early_key_by_host.get(addr[0]) or _BFKEY_HEX
                dec = bf_decrypt(data, key_hex=use_k, iv=b'\x00' * 8)
                if dec:
                    w = dec[-1]
                    if 1 <= w <= 8:
                        unpadded = dec[:-w]
                        log('  DECRYPTED (%d bytes, wastage=%d): %s' % (len(unpadded), w, unpadded.hex()))
                    else:
                        unpadded = dec
                        log('  DECRYPTED (%d bytes): %s' % (len(dec), dec.hex()))

            if unpadded is not None:
                try:
                    handle_upstream_calls(s, addr, _key_cache.get(addr) or _early_key_by_host.get(addr[0]) or _BFKEY_HEX, unpadded)
                except Exception as _e:
                    log('UPSTREAM CALL handler error: %r' % (_e,))

            # 3. Channel ACK responder
            if os.environ.get('ATTEMPT_CHANNEL_ACK', '1') == '1' and unpadded is not None and len(unpadded) >= 6:
                pkt_flags = struct.unpack('<H', unpadded[0:2])[0]
                FLAG_ON_CHANNEL = 0x0008
                FLAG_HAS_SEQUENCE_NUMBER = 0x0040
                if (pkt_flags & FLAG_ON_CHANNEL) and (pkt_flags & FLAG_HAS_SEQUENCE_NUMBER):
                    seq = struct.unpack('<I', unpadded[-4:])[0]
                    if seq < 65536:
                        use_key = _key_cache.get(addr) or _early_key_by_host.get(addr[0]) or _BFKEY_HEX
                        ack_plain = struct.pack('<H', 0x000c) + struct.pack('<I', seq) + bytes([1])
                        ack_pad_len = 8 - (len(ack_plain) % 8)
                        ack_padded = ack_plain + b'\x00' * (ack_pad_len - 1) + bytes([ack_pad_len])
                        ack_enc = bf_encrypt(ack_padded, key_hex=use_key, iv=b'\x00' * 8)
                        ack_reply = ack_enc if ack_enc else ack_padded
                        s.sendto(ack_reply, addr)
                        log('BASEAPP CHANNEL ACK: pkt_flags=0x%04x seq=%d key=%s (%d bytes): %s' % (
                            pkt_flags, seq, use_key, len(ack_reply), ack_reply.hex()))
                        continue
                    else:
                        log('BASEAPP CHANNEL ACK: ignoring out-of-range seq=%d' % seq)

            # 4. identifyVersionPoint reply
            VERSIONPOINT_IDENTITY_MSGID = 94
            BASEAPPEXT_IDENTIFYVERSIONPOINT_MSGID = 12
            _REPLY_FLAGS = int(os.environ.get('BASEAPP_REPLY_FLAGS', '0x0008'), 16)
            if (os.environ.get('ATTEMPT_VERSIONPOINT_REPLY', '1') == '1'
                    and unpadded is not None and len(unpadded) >= 8
                    and unpadded[2] == BASEAPPEXT_IDENTIFYVERSIONPOINT_MSGID):
                checkpoint_id = struct.unpack('<H', unpadded[5:7])[0] if len(unpadded) >= 7 else 0
                use_key = _key_cache.get(addr) or _early_key_by_host.get(addr[0]) or _BFKEY_HEX
                vpi_body = struct.pack('<H', checkpoint_id) + b'\x00' * 6  # 8 bytes total
                vpi_plain = (struct.pack('<H', _REPLY_FLAGS) + bytes([VERSIONPOINT_IDENTITY_MSGID])
                             + vpi_body)
                vpi_pad_len = 8 - (len(vpi_plain) % 8)
                vpi_padded = vpi_plain + b'\x00' * (vpi_pad_len - 1) + bytes([vpi_pad_len])
                vpi_enc = bf_encrypt(vpi_padded, key_hex=use_key, iv=b'\x00' * 8)
                vpi_reply = vpi_enc if vpi_enc else vpi_padded
                s.sendto(vpi_reply, addr)
                log('BASEAPP UDP SENT versionPointIdentity push id=94 flags=0x%04x checkpoint_id=%d key=%s IV=0 (%d bytes): %s' % (
                    _REPLY_FLAGS, checkpoint_id, use_key, len(vpi_reply), vpi_reply.hex()))
                if os.environ.get('ATTEMPT_KEEPALIVE', '1') == '1':
                    _start_keepalive(s, addr, use_key)
                continue

            # 5. Log and dispatch any client upstream RPCs
            if unpadded is not None and len(unpadded) >= 3:
                up_msgid = unpadded[2]
                log('BASEAPP UPSTREAM RECV: msgid=0x%02x (%d) len=%d: %s' % (
                    up_msgid, up_msgid, len(unpadded), unpadded.hex()))
                if up_msgid not in (VERSIONPOINT_IDENTITY_MSGID, BASEAPPEXT_IDENTIFYVERSIONPOINT_MSGID):
                    log('  UPSTREAM PAYLOAD RAW: %r' % unpadded)
                    # If waiting in interactive Character Creation mode (ROS_AUTO_ENTER_HALL=0):
                    if os.environ.get('ROS_AUTO_ENTER_HALL', '1') == '0':
                        log('BASEAPP: interactive mode received upstream message (msgid=%d)! Dispatching character creation response chain...' % up_msgid)
                        use_key = _key_cache.get(addr) or _early_key_by_host.get(addr[0]) or _BFKEY_HEX
                        athlete_eid = int(os.environ.get('ROS_ATHLETE_EID', '1'))
                        threading.Thread(target=send_character_creation_response_chain,
                                         args=(s, addr, use_key, athlete_eid), daemon=True).start()
        except Exception as e:
            log('BASEAPP UDP error: %s' % e)


def serve_http_plain(port):
    log('=== HTTP plain :%d ===' % port)
    base.HTTPServer(('0.0.0.0', port), base.H).serve_forever()


def serve_http_tls(port):
    import ssl
    log('=== HTTP TLS :%d ===' % port)
    srv = base.HTTPServer(('0.0.0.0', port), base.H)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'srv.crt'),
                         os.path.join(os.path.dirname(os.path.abspath(__file__)), 'srv.key'))
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    srv.serve_forever()


if __name__ == '__main__':
    os.makedirs(os.path.dirname(CAPTURE_LOG), exist_ok=True)
    log('=== local_baseapp_capture START ===')
    threads = [
        threading.Thread(target=serve_http_plain, args=(80,), daemon=True),
        threading.Thread(target=serve_http_tls, args=(443,), daemon=True),
        threading.Thread(target=serve_http_tls, args=(8443,), daemon=True),
        threading.Thread(target=serve_loginapp_udp_responder, daemon=True),
        threading.Thread(target=serve_baseapp_udp_capture, daemon=True),
        threading.Thread(target=_pid_watcher_loop, daemon=True),
    ]
    for t in threads:
        t.start()
    log('All listeners started. Waiting...')
    while True:
        try:
            time.sleep(60)
        except KeyboardInterrupt:
            break
        except Exception as e:
            log('MAIN LOOP error: %s' % e)
