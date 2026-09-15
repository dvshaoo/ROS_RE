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


def bf_encrypt(body):
    if not _BFKEY_HEX or _Blowfish is None:
        return None
    key = bytes.fromhex(_BFKEY_HEX)
    if _BF_MODE == 'ecb':
        c = _Blowfish.new(key, _Blowfish.MODE_ECB)
        return c.encrypt(body)
    elif _BF_MODE == 'cbc0':
        c = _Blowfish.new(key, _Blowfish.MODE_CBC, iv=b'\x00' * 8)
        return c.encrypt(body)
    elif _BF_MODE == 'pc_variant':
        # PC ROS launcher's documented non-standard chaining: XOR each plaintext
        # block against the PREVIOUS PLAINTEXT block (not ciphertext), IV=0, then
        # ECB-encrypt -- see PC_LAUNCHER_STUDY.md SS3.
        c = _Blowfish.new(key, _Blowfish.MODE_ECB)
        blocks = [body[i:i + 8] for i in range(0, len(body), 8)]
        prev = b'\x00' * 8
        out = b''
        for blk in blocks:
            xored = bytes(a ^ b for a, b in zip(blk, prev))
            out += c.encrypt(xored)
            prev = blk
        return out
    return None

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
        except Exception as e:
            log('LOGINAPP UDP error: %s' % e)


def serve_baseapp_udp_capture():
    log('=== FAKE BASEAPP UDP :%d LISTENING (capture-only, no reply) ===' % BASEAPP_PORT)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', BASEAPP_PORT))
    while True:
        try:
            data, addr = s.recvfrom(65536)
            log('*** BASEAPP UDP RECV %d bytes from %s:%d ***' % (len(data), addr[0], addr[1]))
            log('  HEX: %s' % data.hex())
            log('  ASCII: %r' % data)
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
