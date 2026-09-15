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

CAPTURE_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'captures', 'BASEAPP_LOGIN_CAPTURE.txt')

BASEAPP_HOST = '172.16.1.2'   # address the CLIENT (emulator guest) can reach us at
BASEAPP_PORT = 25010          # our fake BaseApp capture port
LOGINAPP_PORT = 25000

_lock = threading.Lock()


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
            reply = (struct.pack('<H', 0x0001) + bytes([0xff])
                      + struct.pack('<I', 4) + struct.pack('<I', 0)
                      + b'\x00\x00')
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
