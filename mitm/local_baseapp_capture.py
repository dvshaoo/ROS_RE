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
_BFKEY_HEX = os.environ.get('BFKEY_HEX', 'b2525a3c')
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
_early_scan_hosts = set()  # host IPs for which the early (LoginApp-triggered) scan already ran
_early_key_by_host = {}  # {host_ip: key_hex} -- populated by the early (LoginApp-triggered) scan, E2E-012
_last_plain_block_by_host = {}  # {host_ip: last 8-byte plaintext block of our last LoginApp reply}, E2E-012


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
                enc_body = bf_encrypt(padded_body)
                # E2E-012: remember this message's LAST plaintext block, keyed
                # by client host -- if the BaseApp channel really does share
                # the SAME EncryptionFilter object (confirmed same key this
                # pass), its pc_variant chaining state would carry over from
                # here rather than resetting to zero for the "new" channel.
                _last_plain_block_by_host[addr[0]] = padded_body[-8:]
                if enc_body:
                    log('ATTEMPT_L: encrypted 24-byte body with Blowfish key=%s mode=%s -> %s' % (
                        _BFKEY_HEX, _BF_MODE, enc_body.hex()))
                    payload_body = enc_body
                else:
                    payload_body = padded_body
                inner = struct.pack('<I', counter) + bytes([1]) + payload_body
                reply = (struct.pack('<H', 0x0001) + bytes([0xff])
                          + struct.pack('<I', len(inner)) + inner
                          + b'\x00\x00')
                log('ATTEMPT_I (default): replyID=0x%08x status=1 + 24-byte %sbody, length=%d' % (
                    counter, 'ENCRYPTED ' if enc_body else 'padded ', len(inner)))
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
            if os.environ.get('ATTEMPT_BASEAPP_REPLY', '1') == '1' and len(data) >= 9:
                # data[2] = method id, data[3:5] = u16 body length, data[5:9] = the
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

                use_key = _key_cache.get(addr, _BFKEY_HEX)
                # E2E-012: use the last plaintext block from our own LoginApp
                # reply to this host as the pc_variant chaining seed, instead
                # of assuming a fresh IV=0 -- see the bf_encrypt docstring
                # addition above for the rationale (same key now CONFIRMED
                # shared between LoginApp and BaseApp channels, suggesting a
                # literally-shared, state-carrying filter object).
                chain_iv = _last_plain_block_by_host.get(addr[0])
                plain = (struct.pack('<H', 0x0001) + bytes([0xff])
                          + struct.pack('<I', 5) + struct.pack('<I', corr) + bytes([1]))
                pad = (-len(plain)) % 8
                plain += b'\x00' * pad
                enc = bf_encrypt(plain, key_hex=use_key, iv=chain_iv)
                if enc:
                    reply = enc
                    log('BASEAPP: encrypted WHOLE %d-byte (padded) reply with key=%s mode=%s chain_iv=%s' % (
                        len(plain), use_key, _BF_MODE, chain_iv.hex() if chain_iv else 'zero'))
                else:
                    reply = plain
                s.sendto(reply, addr)
                log('BASEAPP UDP SENT whole-packet-encrypted ack for method=0x%02x corr=0x%08x key=%s (%d bytes): %s' % (
                    method_id, corr, use_key, len(reply), reply.hex()))
                # This reply's own last plaintext block becomes the chaining
                # seed for the NEXT message (the createBasePlayer push below).
                _last_plain_block_by_host[addr[0]] = plain[-8:]

                # E2E-011 (2026-09-15): createBasePlayer push attempt. Per
                # 06_trace/BASEAPP_CELLAPP_FLOW.md SS2.1 ("Trigger: BaseApp accepts
                # BaseAppLoginRequest" -> "Native Call:
                # ServerConnection::createBasePlayer(entityId, stream)"),
                # createBasePlayer is a PUSH-style ClientInterface message (BaseApp
                # -> client), NOT the reply to baseAppLogin itself -- confirmed
                # architecturally by E2E-010's re-read, and now given a concrete wire
                # shape this pass by decoding the client's own interface-registration
                # table (scratch/decode_clientinterface_table.py, walks every BL
                # caller of the shared registrar function 0x98b30c): createBasePlayer
                # is VARIABLE_LENGTH_MESSAGE with a u16 length prefix (CONFIRMED BY
                # BINARY, same framing as baseAppLogin), and by registration order is
                # ClientInterface method index 4 (bandwidthNotification=0,
                # updateFrequencyNotification=1, setGameTime=2, resetEntities=3,
                # createBasePlayer=4) -- STRONGLY SUPPORTED (registration-order
                # evidence, same method already independently confirmed correct for
                # baseAppLogin=0 via live wire capture), not yet independently
                # wire-confirmed for this specific ID. Body content (entityId +
                # Account property stream) is UNKNOWN/best-effort: Account.def.xml
                # has only one BASE_AND_CLIENT property (isMobileAccount, BOOL), so a
                # near-empty stream is plausible -- this sends just a 4-byte LE
                # entityId (arbitrary placeholder 1) with no property data, the
                # smallest plausible experiment, same whole-packet pc_variant
                # encryption as the ack above (same unresolved key-mismatch caveat
                # from E2E-008/E2E-009 applies equally here).
                if os.environ.get('ATTEMPT_CREATEBASEPLAYER', '1') == '1':
                    entity_id = 1
                    cbp_body = struct.pack('<I', entity_id)
                    cbp_plain = (struct.pack('<H', 0x0001) + bytes([0x04])
                                  + struct.pack('<H', len(cbp_body)) + cbp_body)
                    cbp_pad = (-len(cbp_plain)) % 8
                    cbp_plain += b'\x00' * cbp_pad
                    # E2E-012: chain from the ack's own last plaintext block
                    # (updated just above), same rationale as the ack itself.
                    cbp_chain_iv = _last_plain_block_by_host.get(addr[0])
                    cbp_enc = bf_encrypt(cbp_plain, key_hex=use_key, iv=cbp_chain_iv)
                    cbp_reply = cbp_enc if cbp_enc else cbp_plain
                    s.sendto(cbp_reply, addr)
                    log('BASEAPP UDP SENT createBasePlayer push id=4 entityId=%d key=%s chain_iv=%s (%d bytes): %s' % (
                        entity_id, use_key, cbp_chain_iv.hex() if cbp_chain_iv else 'zero', len(cbp_reply), cbp_reply.hex()))
                    _last_plain_block_by_host[addr[0]] = cbp_plain[-8:]
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
