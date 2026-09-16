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
_BFKEY_HEX = os.environ.get('BFKEY_HEX', 'fa490e60')
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
                sgt_plain = (struct.pack('<H', 0x0001) + bytes([SETGAMETIME_MSGID])
                             + sgt_body + b'\x00\x00')
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


def find_baseapp_key_async(client_addr, old_key_hex, done_callback):
    """Spawned on the FIRST baseAppLogin packet from client_addr. Scans heap for
    ALL EncryptionFilter-shaped objects (matching the vtable pointer's low 4
    bytes, since these are all sub-4GB process addresses with a zero upper
    half), reads each candidate's key, and reports the first one that is NOT
    old_key_hex (i.e. a genuinely new/different key, consistent with the
    BaseApp channel using its own filter) via done_callback(key_hex_or_None,
    all_keys_found). Runs entirely in a background thread; the caller does not
    block on this."""
    def _worker():
        t0 = time.time()
        pid = _get_pid()
        if not pid:
            log('BASEAPP KEYSCAN: no live chiji PID found, aborting scan')
            done_callback(None, [])
            return
        base_addr, regions = _get_libclient_base_and_regions(pid)
        if base_addr is None:
            log('BASEAPP KEYSCAN: could not find libclient.so base, aborting')
            done_callback(None, [])
            return
        target_va = base_addr + LIBCLIENT_VTABLE_FILE_ADDR
        # Use the FULL 8-byte pointer (not just the low 4 bytes) as the search
        # pattern. A first version of this scan used only the low 4 bytes to
        # dodge a (mistaken) worry about embedding \x00 in a shell argument --
        # but the \x00 here is the literal TEXT "\x00" interpreted by the
        # device's own `printf`, not a raw embedded NUL byte in argv, so there
        # was never a real problem to avoid. The low-4-byte-only pattern is
        # matched by pure chance elsewhere in a large heap dump often enough
        # to be a real bug: live-confirmed this pass -- the same "candidate"
        # VA was found reliably across repeated scans, but a direct follow-up
        # read at that address showed completely unrelated bytes (not even a
        # plausible vtable pointer), proving it was a 4-byte coincidental
        # collision, not the real object. The full 8-byte pattern (as used by
        # the original one-shot scratch/scan_heap_for_filter.py, which found
        # exactly one match in ~500MB) does not have this problem.
        pattern = struct.pack('<Q', target_va)
        log('BASEAPP KEYSCAN: pid=%s base=0x%x target_vtable_va=0x%x pattern=%s, scanning %d regions...' % (
            pid, base_addr, target_va, pattern.hex(), len(regions)))
        found_keys = []
        lock = threading.Lock()

        def scan_one(rs, re_):
            # E2E-012: _scan_region_for_pattern now returns (va, raw_bytes)
            # pairs, with raw_bytes sliced from the SAME already-downloaded
            # snapshot the match was found in (no separate follow-up read,
            # avoiding the memory-churn race documented there).
            hits = _scan_region_for_pattern(pid, rs, re_, pattern)
            for va, raw_bytes in hits:
                key_hex = _parse_sso_key(raw_bytes)
                if key_hex:
                    with lock:
                        found_keys.append((va, key_hex))
                        log('BASEAPP KEYSCAN: candidate EncryptionFilter at 0x%x key=%s' % (va, key_hex))

        # E2E-012 (2026-09-15): narrower-scope search, per the coordinator's own
        # NEXT_HIGHEST_VALUE_EXPERIMENT. E2E-009's scan treated every heap-tagged
        # region as one search unit, including two enormous (161-277MB) arenas
        # -- the exact-match host-side verification step for those alone took
        # 3-13s, most of the ~5s retry window. `EncryptionFilter` is only
        # ~0x38 bytes, so it far more plausibly lives in one of the SMALL
        # (2-10MB) heap regions (allocator size-class segregation puts small,
        # frequently-allocated objects in dedicated small arenas, not the
        # giant catch-all ones) -- scan those FIRST and only fall back to the
        # huge regions if nothing turns up small, so a real hit in a small
        # region resolves in a fraction of a second instead of waiting on (or
        # racing against) the slow huge-region transfers.
        SMALL_REGION_CUTOFF = 16 * 1024 * 1024  # 16MB
        small_regions = [(rs, re_) for (rs, re_) in regions if (re_ - rs) <= SMALL_REGION_CUTOFF]
        large_regions = [(rs, re_) for (rs, re_) in regions if (re_ - rs) > SMALL_REGION_CUTOFF]
        log('BASEAPP KEYSCAN: %d small (<=16MB) regions, %d large regions' % (len(small_regions), len(large_regions)))

        def run_batch(batch, join_timeout):
            threads = []
            for (rs, re_) in batch:
                th = threading.Thread(target=scan_one, args=(rs, re_), daemon=True)
                th.start()
                threads.append(th)
            for th in threads:
                th.join(timeout=join_timeout)

        run_batch(small_regions, join_timeout=6)
        if not any(k != old_key_hex for _, k in found_keys):
            log('BASEAPP KEYSCAN: no distinct key in small regions, falling back to %d large region(s)' % len(large_regions))
            run_batch(large_regions, join_timeout=15)
        elapsed = time.time() - t0
        distinct = sorted(set(k for _, k in found_keys))
        log('BASEAPP KEYSCAN: done in %.2fs, found %d candidate object(s), %d distinct key(s): %s' % (
            elapsed, len(found_keys), len(distinct), distinct))
        new_key = None
        for k in distinct:
            if k != old_key_hex:
                new_key = k
                break
        done_callback(new_key, distinct)

    th = threading.Thread(target=_worker, daemon=True)
    th.start()

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
        line = '%s %s' % (time.strftime('%H:%M:%S'), msg)
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
                use_login_key = _early_key_by_host.get(addr[0]) or _key_cache.get(addr) or _BFKEY_HEX
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
                # E2E-012 (2026-09-15): start the BaseApp-channel key scan as soon
                # as possible after a LoginApp reply that could plausibly succeed,
                # rather than waiting for the first baseAppLogin packet. FIRST
                # ATTEMPT this pass fired the scan IMMEDIATELY on send -- live
                # result: 0 candidates found anywhere (even after the small-region
                # optimization below correctly ran fast), because the scan ran
                # and finished BEFORE the client had even received/decrypted this
                # reply, let alone reached `Nub::recreateListeningSocket` for the
                # new BaseApp socket -- i.e. the object being searched for did not
                # exist yet. Fixed by deferring the scan start with a short delay
                # (empirically, `checkScriptBaseAppAddr`/`recreateListeningSocket`
                # fire within ~20-40ms of the reply being processed per every
                # prior live logcat capture this project has recorded) so the
                # object has time to be constructed first, while still starting
                # well before the first baseAppLogin packet would otherwise
                # trigger it (typically 1-3s later, since the client does its own
                # internal setup/socket-bind work first). Keyed by the LOGINAPP
                # host (not yet known which port the BaseApp socket will use).
                # Uses its OWN dedup set (_early_scan_hosts), separate from
                # serve_baseapp_udp_capture's per-connection one
                # (_key_scan_started) -- both are allowed to run independently
                # (different timing, different odds), rather than one blocking
                # the other, since a first live test of this early trigger alone
                # found 0 candidates (see E2E-012) and losing the later,
                # differently-timed per-connection attempt as a fallback would
                # have been a regression.
                if os.environ.get('ATTEMPT_I', '1') == '1' and addr[0] not in _early_scan_hosts:
                    _early_scan_hosts.add(addr[0])

                    def _on_early_scan_done(new_key, all_keys, host=addr[0]):
                        if new_key:
                            log('BASEAPP KEYSCAN (early, from LoginApp reply): NEW key=%s for host=%s (candidates: %s)' % (new_key, host, all_keys))
                            # Seed the cache for ANY future baseapp client addr from
                            # this host -- serve_baseapp_udp_capture's own dedup
                            # keys by the BaseApp (ip,port) pair, which differs from
                            # this LoginApp (ip,port) pair, so store by host only
                            # and let the per-connection lookup fall back to it.
                            _early_key_by_host[host] = new_key
                        else:
                            log('BASEAPP KEYSCAN (early): no distinct key found yet for host=%s (candidates: %s)' % (host, all_keys))

                    def _delayed_start(host=addr[0]):
                        time.sleep(0.25)
                        find_baseapp_key_async(host, _BFKEY_HEX, _on_early_scan_done)

                    threading.Thread(target=_delayed_start, daemon=True).start()
        except Exception as e:
            log('LOGINAPP UDP error: %s' % e)


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

            # E2E-022 (GEMINI.md S3 / "Immediate Next Steps" #1): reliable-channel
            # ACK responder. Once our baseAppLogin ack + createBasePlayer push are
            # accepted, the client opens its EXTERNAL RELIABLE CHANNEL and sends a
            # Mercury bundle with FLAG_ON_CHANNEL(0x0008)|FLAG_IS_RELIABLE(0x0010)|
            # FLAG_HAS_SEQUENCE_NUMBER(0x0040) = 0x0058 set, retrying it every
            # ~1s ("Resending unacked packet #0 due to inactivity") until we ack
            # it. Per GEMINI.md S3 (Nub::processFilteredPacket 0x990364-0x9904fc,
            # Channel::handleAck 0x986898): the 4-byte LE sequence number is the
            # last 4 bytes of the unpadded (wastage-stripped) decrypted payload.
            # The ack itself is a minimal standalone Mercury packet with
            # FLAG_ON_CHANNEL|FLAG_HAS_ACKS (0x000c), an empty bundle footer, and
            # an ack-list footer of [ack_seq: u32 LE][ack_count: u8=1] -- whole-
            # packet pc_variant-encrypted with IV=0, same as every other BaseApp-
            # channel packet in this file.
            if os.environ.get('ATTEMPT_CHANNEL_ACK', '1') == '1' and unpadded is not None and len(unpadded) >= 6:
                pkt_flags = struct.unpack('<H', unpadded[0:2])[0]
                FLAG_ON_CHANNEL = 0x0008
                FLAG_HAS_SEQUENCE_NUMBER = 0x0040
                if (pkt_flags & FLAG_ON_CHANNEL) and (pkt_flags & FLAG_HAS_SEQUENCE_NUMBER):
                    seq = struct.unpack('<I', unpadded[-4:])[0]
                    use_key = _key_cache.get(addr) or _early_key_by_host.get(addr[0]) or _BFKEY_HEX
                    ack_plain = struct.pack('<H', 0x000c) + b'\x00\x00' + struct.pack('<I', seq) + bytes([1])
                    ack_pad_len = 8 - (len(ack_plain) % 8)
                    ack_padded = ack_plain + b'\x00' * (ack_pad_len - 1) + bytes([ack_pad_len])
                    ack_enc = bf_encrypt(ack_padded, key_hex=use_key, iv=b'\x00' * 8)
                    ack_reply = ack_enc if ack_enc else ack_padded
                    s.sendto(ack_reply, addr)
                    log('BASEAPP CHANNEL ACK: pkt_flags=0x%04x seq=%d key=%s (%d bytes): %s' % (
                        pkt_flags, seq, use_key, len(ack_reply), ack_reply.hex()))
                    continue

            # E2E-021/E2E-022: identifyVersionPoint reply attempt.
            # After the channel ACK above, the client calls BaseAppExtInterface
            # method 12 (identifyVersionPoint, CONFIRMED against
            # 06_trace/MERCURY_PACKET_MAP.md's binary-extracted registration-order
            # walk -- scratch/dump_clientinterface_registration_order.py) with a
            # VARIABLE_LENGTH body [u16 checkpoint_id][u8 strlen][strlen bytes],
            # sent with flags=0x0008 (FLAG_ON_CHANNEL only, NOT
            # FLAG_HAS_SEQUENCE_NUMBER) -- i.e. NOT part of the reliable/acked
            # stream at all (E2E-021 finding 1). It resends ~10x over ~10s then
            # abandons the whole BaseApp session and restarts LoginApp.
            #
            # E2E-021 finding 2 (disassembly of ClientInterface's own
            # "versionPointIdentity" handler, 0x94bf48): that push message is a
            # FIXED_LENGTH_MESSAGE with an 8-byte body, and its handler simply
            # echoes the 8 bytes it receives back out via the same descriptor --
            # a plausible (not fully proven) reply mechanism paired 1:1 by name
            # with identifyVersionPoint.
            #
            # E2E-022: versionPointIdentity's exact ClientInterface msgID was
            # resolved with certainty (not hand-counted) by programmatically
            # walking all 122 interface-method registration call sites in
            # program order (scratch/dump_clientinterface_registration_order.py):
            # msgID = 94. Cross-validated against the independently-confirmed
            # createBasePlayer=5 (both derived from the SAME walk, matching the
            # value already in production use below from a totally different
            # disassembly method) -- this is CONFIRMED BY BINARY, not a guess.
            #
            # First-guess 8-byte payload (per the coordinator's own suggested
            # starting point): echo the client's own checkpoint_id (first 2
            # bytes of the identifyVersionPoint body) back as the first 2 bytes
            # of the reply, zero-pad the remaining 6 bytes. This is a hypothesis
            # about content, NOT yet confirmed -- if the resend loop continues
            # unchanged after this, the content (or the whole echo-reply
            # mechanism) is wrong and the fallback is the generic-watchdog
            # explanation below.
            #
            # E2E-023 UPDATE: live-tested with flags=0x0001 -- keep-alive fix
            # CONFIRMED WORKING (no more INACTIVITY reconnects), but the
            # client keeps resending identifyVersionPoint unchanged every ~1s
            # even though our msgID-94 reply is sent back immediately every
            # time. Re-disassembled 0x94bf48 in FULL (all 19 instructions,
            # entry to `ret`): it contains ZERO comparison/branch instructions
            # of any kind -- it unconditionally builds a new outgoing message
            # and copies the 8 bytes verbatim, no validation whatsoever. This
            # DISPROVES the "wrong content" theory (there's nothing to get
            # right -- any 8 bytes would pass through this handler
            # identically) and raises real doubt about whether our reply is
            # even being ROUTED to this handler at all, vs. being accepted at
            # the socket/decrypt layer but mis-dispatched or silently dropped
            # before reaching any ClientInterface handler.
            #
            # New hypothesis (untested as of this comment): our reply's FLAGS
            # (0x0001, the same generic flag used for the pre-channel
            # createBasePlayer push) may be wrong now that the reliable
            # channel is established. `identifyVersionPoint` ITSELF is sent by
            # the client with flags=0x0008 (FLAG_ON_CHANNEL, no sequence
            # number, no requests flag) -- i.e. the client's own convention
            # for "on this established channel, but not part of the strictly
            # ordered/acked stream" traffic at this stage. Our channel ACK
            # reply (already confirmed working) also sets FLAG_ON_CHANNEL
            # (0x0008, as part of 0x000c). Switching our post-channel-
            # established application pushes (this one and the setGameTime
            # keep-alive) to flags=0x0008 to match the client's own observed
            # convention is a concrete, evidence-grounded next experiment --
            # overridable via BASEAPP_REPLY_FLAGS for quick A/B without a
            # code change.
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
                             + vpi_body + b'\x00\x00')
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

            if os.environ.get('ATTEMPT_BASEAPP_REPLY', '1') == '1' and len(data) >= 9 and data[2] == 0:
                # data[2] = method id 0 (baseAppLogin), data[3:5] = u16 body length, data[5:9] = the
                # candidate 4-byte LE correlation field observed at the start of the
                # 11-byte body (see comment above).
                method_id = data[2]
                corr = struct.unpack('<I', data[5:9])[0]
                # Attempts 1-3 (E2E-008, plaintext / body-only-encrypted / no-length
                # variants): all REJECTED -- see END_TO_END_TEST_LOG.md E2E-008 for
                # the full record. Attempt 4 established the correct WHOLE-PACKET
                # pc_variant-encrypted [flags][msgid=0xFF][length=5][replyID][status]
                # shape (padded to a multiple of 8) but decrypted to garbage using
                # LoginApp's key -- strong evidence of a SEPARATE BaseApp-channel key.
                #
                # E2E-009 (this pass): on the FIRST packet from a given client
                # address, kick off an async heap re-scan (find_baseapp_key_async)
                # for a second EncryptionFilter object distinct from LoginApp's
                # known key. Every reply (including this first one) uses whatever
                # key is in _key_cache for this address at send time -- initially
                # the LoginApp key (best-effort, likely wrong per E2E-008), but a
                # LATER retry within the same ~5s Mercury retry window will pick up
                # the freshly-discovered key once the background scan completes.
                # E2E-012: if the early (LoginApp-reply-triggered) scan for this
                # client's host already found a distinct key, use it immediately
                # -- no need to wait for or duplicate a per-connection scan.
                if addr not in _key_cache and addr[0] in _early_key_by_host:
                    _key_cache[addr] = _early_key_by_host[addr[0]]
                    log('BASEAPP: using key=%s from EARLY scan (triggered at LoginApp reply time) for %s' % (
                        _early_key_by_host[addr[0]], addr))
                if addr not in _key_scan_started:
                    _key_scan_started.add(addr)
                    _key_cache.setdefault(addr, _BFKEY_HEX)  # seed with LoginApp's key as fallback

                    def _on_scan_done(new_key, all_keys, addr=addr):
                        if new_key:
                            _key_cache[addr] = new_key
                            log('BASEAPP KEYSCAN: using NEW distinct key=%s for %s (all candidates: %s)' % (new_key, addr, all_keys))
                        else:
                            log('BASEAPP KEYSCAN: no key distinct from LoginApp\'s (%s) found for %s (candidates: %s) -- key is likely SHARED, not separate' % (_BFKEY_HEX, addr, all_keys))

                    find_baseapp_key_async(addr, _BFKEY_HEX, _on_scan_done)

                use_key = _key_cache.get(addr) or _early_key_by_host.get(addr[0]) or _BFKEY_HEX
                # E2E-020 (2026-09-15) & E2E-021:
                # 1. 0x9892c8 unconditionally clears IV (x26 = xzr) for EVERY packet.
                # 2. 0x989324-0x989350 reads packet[total_len - 1] as BigWorld wastage
                #    count (w21). If w21 <= 8, it strips w21 bytes from packet length
                #    (+0x1a -= w21). Padding MUST end with the byte value pad_len!
                # 3. Mercury bundles require a mandatory 2-byte zero footer (b'\x00\x00')
                #    at the end of the unpadded plaintext payload (before wastage padding).
                inner = struct.pack('<I', corr) + bytes([1])
                plain = (struct.pack('<H', 0x0001) + bytes([0xff])
                          + struct.pack('<I', len(inner)) + inner
                          + b'\x00\x00')
                pad_len = 8 - (len(plain) % 8)
                plain_padded = plain + b'\x00' * (pad_len - 1) + bytes([pad_len])
                # Each datagram uses IV=0 (default zero in bf_encrypt)
                enc = bf_encrypt(plain_padded, key_hex=use_key, iv=b'\x00' * 8)
                if enc:
                    reply = enc
                    log('BASEAPP: encrypted WHOLE %d-byte (wastage-padded) reply with key=%s mode=%s IV=0' % (
                        len(plain_padded), use_key, _BF_MODE))
                else:
                    reply = plain_padded
                s.sendto(reply, addr)
                log('BASEAPP UDP SENT whole-packet-encrypted ack for method=0x%02x corr=0x%08x key=%s (%d bytes): %s' % (
                    method_id, corr, use_key, len(reply), reply.hex()))

                # E2E-021: createBasePlayer push attempt.
                # ClientInterface method index 5: createBasePlayer (VARIABLE_LENGTH_MESSAGE with u16 length).
                # Body: [entityID: uint32 (4)][entityType: uint16 (2)] = 6 bytes.
                # Entity type 127 corresponds to <Account> from entities.xml.
                # Followed by 2-byte Mercury bundle zero footer b'\x00\x00' and BigWorld wastage padding.
                if os.environ.get('ATTEMPT_CREATEBASEPLAYER', '1') == '1':
                    import time
                    time.sleep(0.05)
                    entity_id = 1
                    entity_type = 127  # Account in entities.xml
                    cbp_body = struct.pack('<I', entity_id) + struct.pack('<H', entity_type)
                    cbp_plain = (struct.pack('<H', 0x0001) + bytes([0x05])
                                  + struct.pack('<H', len(cbp_body)) + cbp_body
                                  + b'\x00\x00')
                    cbp_pad_len = 8 - (len(cbp_plain) % 8)
                    cbp_padded = cbp_plain + b'\x00' * (cbp_pad_len - 1) + bytes([cbp_pad_len])
                    cbp_enc = bf_encrypt(cbp_padded, key_hex=use_key, iv=b'\x00' * 8)
                    cbp_reply = cbp_enc if cbp_enc else cbp_padded
                    s.sendto(cbp_reply, addr)
                    log('BASEAPP UDP SENT createBasePlayer push id=5 entityId=%d type=%d key=%s IV=0 (%d bytes): %s' % (
                        entity_id, entity_type, use_key, len(cbp_reply), cbp_reply.hex()))

                    # E2E-028: Account.onChannelLogin push attempt via the generic
                    # shortEntityMessage(100)/longEntityMessage(101) entity-RPC
                    # dispatch, per E2E-025/026/027's static investigation.
                    # `handshake`'s own numeric msgID is UNRECOVERABLE (data-driven
                    # via script.npk, itself an established, separate blocker) --
                    # this sidesteps that entirely by using the generic dispatch
                    # path instead. `0x94c540`'s own method-index encoding could
                    # NOT be resolved after 4 independent static techniques across
                    # 3 passes (E2E-025/026/027) -- these are EXPLICITLY LABELED
                    # GUESSES, not confirmed wire formats. onChannelLogin = local
                    # ClientMethods index 2 (CONFIRMED from Account.def.xml's
                    # declared order). No entityID field included (0x94c540's own
                    # dispatch was traced to pull the target entity from internal
                    # connection state, not the wire body).
                    ONCHANNELLOGIN_VARIANT = os.environ.get('ONCHANNELLOGIN_VARIANT', '0')

                    def _build_onchannellogin(variant):
                        import pickle
                        import marshal
                        method_index = 2  # Account.onChannelLogin, Account.def.xml ClientMethods order
                        account_data = {'characters': []}
                        if variant == '1':
                            ocl_msgid = 100
                            ocl_body = bytes([method_index]) + bytes([0]) + pickle.dumps(account_data, protocol=2)
                            ocl_length_bytes = bytes([len(ocl_body)]) if len(ocl_body) < 256 else None
                        elif variant == '2':
                            ocl_msgid = 101
                            ocl_body = struct.pack('<H', method_index) + bytes([0]) + pickle.dumps(account_data, protocol=2)
                            ocl_length_bytes = struct.pack('<H', len(ocl_body))
                        else:  # '3'
                            ocl_msgid = 100
                            ocl_body = bytes([method_index]) + bytes([0]) + marshal.dumps(account_data)
                            ocl_length_bytes = bytes([len(ocl_body)]) if len(ocl_body) < 256 else None
                        if ocl_length_bytes is None:
                            return None, ocl_msgid
                        ocl_plain = (struct.pack('<H', 0x0001) + bytes([ocl_msgid])
                                      + ocl_length_bytes + ocl_body + b'\x00\x00')
                        ocl_pad_len = 8 - (len(ocl_plain) % 8)
                        ocl_padded = ocl_plain + b'\x00' * (ocl_pad_len - 1) + bytes([ocl_pad_len])
                        return ocl_padded, ocl_msgid

                    if ONCHANNELLOGIN_VARIANT in ('1', '2', '3'):
                        time.sleep(0.05)
                        ocl_padded, ocl_msgid = _build_onchannellogin(ONCHANNELLOGIN_VARIANT)
                        if ocl_padded is not None:
                            ocl_enc = bf_encrypt(ocl_padded, key_hex=use_key, iv=b'\x00' * 8)
                            ocl_reply = ocl_enc if ocl_enc else ocl_padded
                            s.sendto(ocl_reply, addr)
                            log('BASEAPP UDP SENT onChannelLogin GUESS variant=%s msgid=%d key=%s IV=0 (%d bytes): %s' % (
                                ONCHANNELLOGIN_VARIANT, ocl_msgid, use_key, len(ocl_reply), ocl_reply.hex()))
                        else:
                            log('BASEAPP: onChannelLogin GUESS variant=%s body too long for u8 length prefix, skipped' % ONCHANNELLOGIN_VARIANT)

                    # E2E-035: gate-toggle discovery -- entity+0x140 (the field
                    # 0x94c540's dispatch checks before invoking a bound entity
                    # method) is NOT a one-time init flag; live snapshots show it
                    # OSCILLATING between 0x0 and a stable non-zero pointer every
                    # ~2-3s. A single one-shot onChannelLogin send (E2E-028) may
                    # simply have landed in a zero window every time. Retry the
                    # SAME push repeatedly for a while to raise the odds of
                    # landing inside a non-zero window.
                    if os.environ.get('ONCHANNELLOGIN_RETRY', '0') == '1' and addr not in _onchannellogin_retry_started:
                        _onchannellogin_retry_started.add(addr)
                        retry_variant = os.environ.get('ONCHANNELLOGIN_RETRY_VARIANT', '1')
                        retry_interval = float(os.environ.get('ONCHANNELLOGIN_RETRY_INTERVAL', '0.5'))
                        retry_duration = float(os.environ.get('ONCHANNELLOGIN_RETRY_DURATION', '15'))

                        def _retry_onchannellogin(dest=addr, key=use_key, sock=s):
                            padded, msgid = _build_onchannellogin(retry_variant)
                            if padded is None:
                                return
                            n = int(retry_duration / retry_interval)
                            for i in range(n):
                                time.sleep(retry_interval)
                                enc = bf_encrypt(padded, key_hex=key, iv=b'\x00' * 8)
                                pkt = enc if enc else padded
                                try:
                                    sock.sendto(pkt, dest)
                                    log('BASEAPP UDP SENT onChannelLogin RETRY #%d variant=%s msgid=%d key=%s (%d bytes)' % (
                                        i + 1, retry_variant, msgid, key, len(pkt)))
                                except Exception as e:
                                    log('BASEAPP onChannelLogin retry error: %s' % e)
                                    return

                        threading.Thread(target=_retry_onchannellogin, daemon=True).start()

                    # E2E-022: start the periodic keep-alive as soon as the
                    # channel is known to exist (createBasePlayer accepted),
                    # not only once identifyVersionPoint happens to arrive --
                    # belt-and-suspenders per 06_notes/LOBBY_ENTRY_TRACE.md
                    # Task A, since the generic InactivityTimeout watchdog is
                    # independent of any specific RPC.
                    if os.environ.get('ATTEMPT_KEEPALIVE', '1') == '1':
                        _start_keepalive(s, addr, use_key)
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
    ]
    for t in threads:
        t.start()
    log('All listeners started. Waiting...')
    while True:
        time.sleep(60)
