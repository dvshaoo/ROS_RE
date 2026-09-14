# -*- coding: utf-8 -*-
# mitm_serve.py -- ROS-RE MITM serve run B (T07 Hypothesis A: G4 text, no-update).
# Serves /pl/npk_version_na_android.plist as b'G4\nversion=1117219\ncount=0\n'.
# Everything else: log-only 404. Logs -> captures/SERVE_B.txt
import os, re, ssl, threading, time, json, base64, hashlib, socket, select
try:
    from http.server import BaseHTTPRequestHandler, HTTPServer
except Exception:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

def generate_whoami_payload():
    payload_dict = {
        "ip": "172.16.1.15",
        "country": {
            "names": {"en": "United States", "zh-CN": "United States"},
            "iso_code": "US"
        },
        "continent": {
            "names": {"en": "North America", "zh-CN": "North America"},
            "iso_code": "NA"
        }
    }
    payload_b64 = base64.b64encode(json.dumps(payload_dict).encode('utf-8')).decode('ascii')
    random_seed = "1234"
    payload_md5 = hashlib.md5(payload_b64.encode('ascii')).hexdigest()
    PRIKEY = 'prikey.57CRaLUV1tHB'
    time_step = int(time.time()) // 60
    to_hash = f"{random_seed},{payload_md5},{PRIKEY},{time_step}".encode('ascii')
    new_sig = hashlib.md5(to_hash).hexdigest()
    full_sig = random_seed + new_sig
    return json.dumps({
        "sig": full_sig,
        "payload": payload_b64
    }).encode('utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
NOTES = r'C:\Users\Raysoo\Downloads\ROS_RE\06_notes'
LOG = os.path.join(HERE, 'captures', 'SERVE_B.txt')
_lock = threading.Lock()

def w(m):
    with _lock:
        print(m, flush=True)
        try:
            f = open(LOG, 'a', encoding='utf-8', errors='replace')
            f.write('%s %s\n' % (time.strftime('%H:%M:%S'), m))
            f.close()
        except Exception:
            pass

def load_triplets():
    trips = []
    for tag in ('main', 'patch'):
        try:
            for ln in open(os.path.join(NOTES, 'LOCAL_MANIFEST_%s.txt' % tag), encoding='utf-8'):
                ln = ln.strip()
                if ' | ' not in ln:
                    continue
                left, md5 = ln.rsplit(' | ', 1)
                m = re.match(r'(\d+)(.+) (main|patch)$', left)
                if m:
                    trips.append((m.group(2), m.group(1), md5.strip()))
        except Exception as e:
            w('manifest load err %s: %s' % (tag, e))
    return trips

import plistlib

def load_manifest_entries():
    out = []
    for tag in ('main', 'patch'):
        try:
            for ln in open(os.path.join(NOTES, 'LOCAL_MANIFEST_%s.txt' % tag), encoding='utf-8'):
                ln = ln.strip()
                if ' | ' not in ln:
                    continue
                left, md5 = ln.rsplit(' | ', 1)
                m = re.match(r'(\d+)(.+) (main|patch)$', left)
                if m:
                    out.append({'path': m.group(2), 'size': int(m.group(1)),
                                'md5': md5.strip(), 'tag': m.group(3)})
        except Exception as e:
            w('manifest entries err %s: %s' % (tag, e))
    return out

PLIST = (
    b'##########\n'
    b'{\n'
    b'  "type": "package",\n'
    b'  "version": "1117219",\n'
    b'  "version_name": "1.610377.506841",\n'
    b'  "min_client_version": 0,\n'
    b'  "min_engine_version": 0,\n'
    b'  "min_patch_client_version": 0,\n'
    b'  "min_patch_engine_version": 0,\n'
    b'  "use_dlc_clothes": false,\n'
    b'  "file_list": ["dummy.npk"],\n'
    b'  "dummy.npk_updated": 0,\n'
    b'  "dummy.npk_size": 1,\n'
    b'  "dummy.npk_md5": "00000000000000000000000000000000",\n'
    b'  "patch.1117219.com.netease.chiji.obb_updated": 0,\n'
    b'  "patch.1117219.com.netease.chiji.obb_size": 1,\n'
    b'  "patch.1117219.com.netease.chiji.obb_md5": "00000000000000000000000000000000"\n'
    b'}\n'
)
w('T14-complete plist: %d bytes' % len(PLIST))

import zlib, pickle
TOTAL_LIST_PAYLOAD = zlib.compress(pickle.dumps({
    'dummy.npk_updated': 0,
    'dummy.npk_size': 1,
    'dummy.npk_md5': '00000000000000000000000000000000',
}, 2))

# T18: server-list 1-line payload (cited: ui/UILogin.py:197-237 positional
# space-delimited schema; single spaces only — split(' ') shifts on doubles).
# 10.0.2.2 = emulator->host route (no adb reverse needed for the later login
# connect); port 25000 is our future fake-loginapp port (nothing there yet).
SERVER_LIST_PAYLOAD = (
    b'North_America 1 1 1 North_America North_America '
    b'127.0.0.1:25000 127.0.0.1:25000 127.0.0.1:25000 10001 127.0.0.1:25000\n'
)
w('T18 server_list_ad.txt: %d bytes' % len(SERVER_LIST_PAYLOAD))
NOTICE_PAYLOAD = b"Welcome to Rules of Survival!\n"


class H(BaseHTTPRequestHandler):
    def _handle(self):
        try:
            length = int(self.headers.get('Content-Length', 0) or 0)
        except Exception:
            length = 0
        body = self.rfile.read(length) if length > 0 else b''
        try:
            host = self.headers.get('Host', '?')
        except Exception:
            host = '?'
        w('REQ %s %s host=%s len=%d' % (self.command, self.path, host, length))
        if body:
            w('  BODY %.512r' % body[:512])
        if self.path == '/pl/h45na_hc':
            w('  -> SERVE h45na_hc (empty hash check -> no patches)')
            res = b'{"code":0,"md5":"","size":0}'
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(res)))
            self.end_headers()
            try:
                self.wfile.write(res)
            except Exception:
                pass
            return
        if self.path == '/pl/npk_version_na_android.plist':
            w('  -> SERVE T14-fixed plist (%d bytes)' % len(PLIST))
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', str(len(PLIST)))
            self.end_headers()
            try:
                self.wfile.write(PLIST)
            except Exception:
                pass
            return
        if '/1117219/total_list' in self.path:
            w('  -> SERVE total_list (%d bytes)' % len(TOTAL_LIST_PAYLOAD))
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Length', str(len(TOTAL_LIST_PAYLOAD)))
            self.end_headers()
            try:
                self.wfile.write(TOTAL_LIST_PAYLOAD)
            except Exception:
                pass
            return
        if self.path == '/server_list_ad.txt':
            w('  -> SERVE server_list_ad.txt (%d bytes)' % len(SERVER_LIST_PAYLOAD))
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', str(len(SERVER_LIST_PAYLOAD)))
            self.end_headers()
            try:
                self.wfile.write(SERVER_LIST_PAYLOAD)
            except Exception:
                pass
            return
        if self.path.startswith('/server_list'):
            w('  -> SERVE server_list (%d bytes)' % len(SERVER_LIST_PAYLOAD))
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', str(len(SERVER_LIST_PAYLOAD)))
            self.end_headers()
            try:
                self.wfile.write(SERVER_LIST_PAYLOAD)
            except Exception:
                pass
            return
        if self.path.startswith('/notice_'):
            w('  -> SERVE notice (%d bytes)' % len(NOTICE_PAYLOAD))
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', str(len(NOTICE_PAYLOAD)))
            self.end_headers()
            try:
                self.wfile.write(NOTICE_PAYLOAD)
            except Exception:
                pass
            return
        if 'httpdns' in host.lower():
            domain = 'g61.gph.easebar.com'
            if 'domain=' in self.path:
                try:
                    domain = self.path.split('domain=')[1].split('&')[0]
                except Exception:
                    pass
            w('  -> SERVE HTTPDNS (host=%s) domain=%s -> 10.0.2.2' % (host, domain))
            # NeoX pharos HttpdnsDomain2IpParams expects: {"domain":"...","addrs":["IP"],"ttl":600}
            res = '{"domain":"%s","addrs":["10.0.2.2"],"ttl":600}' % domain
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(res)))
            self.end_headers()
            try:
                self.wfile.write(res.encode('utf-8'))
            except Exception:
                pass
            return
        if 'whoami.nie.easebar.com' in host or (self.path == '/v1' and 'httpdns' not in host.lower()) or (self.path.startswith('/v1?') and 'domain=' not in self.path):
            w('  -> SERVE whoami /v1')
            res = generate_whoami_payload()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(res)))
            self.end_headers()
            try:
                self.wfile.write(res)
            except Exception:
                pass
            return
        if 'pharos_isp.txt' in self.path:
            w('  -> SERVE pharos_isp.txt')
            res = b'172.16.1.15\tUS\tUS\tTest\n'
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', str(len(res)))
            self.end_headers()
            try:
                self.wfile.write(res)
            except Exception:
                pass
            return
        if 'internalquery' in self.path:
            w('  -> SERVE internalquery')
            res = b'{"ip":"172.16.1.15","country":"US"}'
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(res)))
            self.end_headers()
            try:
                self.wfile.write(res)
            except Exception:
                pass
            return
        if self.path in ('/speed', '/test/echo'):
            w('  -> SERVE speed/echo (200 OK)')
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', '2')
            self.end_headers()
            try:
                self.wfile.write(b'ok')
            except Exception:
                pass
            return
        if 'resolve' in self.path.lower() or 'dns_query' in self.path.lower():
            w('  -> SERVE HTTPDNS resolve -> 10.0.2.2 (our MITM host)')
            domain = 'g61.gph.easebar.com'
            if 'domain=' in self.path:
                try:
                    domain = self.path.split('domain=')[1].split('&')[0]
                except Exception:
                    pass
            res = '{"domain":"%s","addrs":["10.0.2.2"],"ttl":600}' % domain
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(res)))
            self.end_headers()
            try:
                self.wfile.write(res.encode('utf-8'))
            except Exception:
                pass
            return
        if self.path == '/frida-dns-hook.js':
            w('  -> SERVE frida-dns-hook.js')
            try:
                script_path = os.path.join(HERE, 'frida-dns-hook.js')
                with open(script_path, 'rb') as f:
                    res = f.read()
            except Exception:
                res = b'// script not found'
            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript')
            self.send_header('Content-Length', str(len(res)))
            self.end_headers()
            try:
                self.wfile.write(res)
            except Exception:
                pass
            return
        if self.path == '/':
            w('  -> SERVE root / (200 OK)')
            res = b'{"code":200,"status":200,"msg":"ok"}'
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(res)))
            self.end_headers()
            try:
                self.wfile.write(res)
            except Exception:
                pass
            return
        if self.path.startswith('/api/devices/init'):
            w('  -> SERVE /api/devices/init')
            res = b'{"code":0,"msg":"","device":{"id":"11178811c6a412d9"}}'
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(res)))
            self.end_headers()
            try:
                self.wfile.write(res)
            except Exception:
                pass
            return
        if self.path.startswith('/api/games/config'):
            w('  -> SERVE /api/games/config')
            res = (
                b'{"code":0,"msg":"","bound_account_types":[],"game_config":{'
                b'"account_type":{"guest":{"api_type":"guest","enable":true,"priority":1,"login_priority":1,"text":"Guest","color":"#ffffff"}},'
                b'"text":{},"server_list":{"enable":true},"quick_login":{"enable":false},'
                b'"security_email":{"enable":false},"login_style":1,"login_page_style":1,"debug_mode":0,'
                b'"minor":{"enable":false},"birth_stage":{"enable":true,"status":1}}}'
            )
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(res)))
            self.end_headers()
            try:
                self.wfile.write(res)
            except Exception:
                pass
            return
        if self.path.startswith('/api/users/login/guest'):
            w('  -> SERVE /api/users/login/guest (minor_status=102 adult verified)')
            res = (
                b'{"code":0,"msg":"","alert_type":0,"bound_account_types":[],"bound_account_ids":{},'
                b'"confirm_message":"","notify_guest_bind":0,"unknown_bind_guide":0,"minor_status":102,'
                b'"age_status":1,"security_email":"",'
                b'"user":{"id":"guest_11178811c6a412d9","account":"Guest_11178811c6a412d9",'
                b'"login_token":"guest_token_fake_ros_2026","token":"guest_token_fake_ros_2026",'
                b'"quick_login_enable":true}}'
            )
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(res)))
            self.end_headers()
            try:
                self.wfile.write(res)
            except Exception:
                pass
            return
        if self.path.startswith('/api/users/login/v2/sdk_token'):
            w('  -> SERVE /api/users/login/v2/sdk_token (top-level user_id & sdk_token, minor_status=102)')
            res = (
                b'{"code":0,"msg":"","user_id":"guest_11178811c6a412d9","sdk_token":"guest_token_fake_ros_2026",'
                b'"alert_type":0,"minor_status":102,"age_status":1,"security_email":"",'
                b'"user":{"id":"guest_11178811c6a412d9","account":"Guest_11178811c6a412d9",'
                b'"login_token":"guest_token_fake_ros_2026","token":"guest_token_fake_ros_2026",'
                b'"quick_login_enable":true}}'
            )
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(res)))
            self.end_headers()
            try:
                self.wfile.write(res)
            except Exception:
                pass
            return
        if self.path.startswith('/api/users/login'):
            w('  -> SERVE /api/users/login (generic minor_status=102 adult verified)')
            res = (
                b'{"code":0,"msg":"","alert_type":0,"bound_account_types":[],"bound_account_ids":{},'
                b'"confirm_message":"","notify_guest_bind":0,"unknown_bind_guide":0,"minor_status":102,'
                b'"age_status":1,"security_email":"",'
                b'"user":{"id":"guest_11178811c6a412d9","account":"Guest_11178811c6a412d9",'
                b'"login_token":"guest_token_fake_ros_2026","token":"guest_token_fake_ros_2026",'
                b'"quick_login_enable":true}}'
            )
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(res)))
            self.end_headers()
            try:
                self.wfile.write(res)
            except Exception:
                pass
            return
        if self.path.startswith('/api/games/user/info'):
            w('  -> SERVE /api/games/user/info')
            res = (
                b'{"code":0,"msg":"","alert_type":0,"minor_status":102,"age_status":1,'
                b'"user":{"nickname":"Guest","ids":{}},'
                b'"bound_accounts":[],"security_email":""}'
            )
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(res)))
            self.end_headers()
            try:
                self.wfile.write(res)
            except Exception:
                pass
            return
        if self.path.startswith('/api/minors/configs'):
            w('  -> SERVE /api/minors/configs')
            res = (
                b'{"code":0,"msg":"","alert_type":0,'
                b'"country_codes":[["US","United States"]]}'
            )
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(res)))
            self.end_headers()
            try:
                self.wfile.write(res)
            except Exception:
                pass
            return
        if self.path.startswith('/api/minors/'):
            w('  -> SERVE /api/minors/ (minor_status=102, age_status=1 verified adult)')
            res = b'{"code":0,"msg":"","alert_type":0,"minor_status":102,"age_status":1,"alert_msg":""}'
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(res)))
            self.end_headers()
            try:
                self.wfile.write(res)
            except Exception:
                pass
            return
        if self.path.startswith('/api/'):
            w('  -> SERVE generic /api/ (code 0)')
            res = b'{"code":0,"msg":""}'
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(res)))
            self.end_headers()
            try:
                self.wfile.write(res)
            except Exception:
                pass
            return
        if self.path.startswith('/pl/') or 'plist' in self.path.lower() or 'npk_version' in self.path.lower():
            w('  -> SERVE catch-all plist (empty file_list)')
            res = PLIST
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', str(len(res)))
            self.end_headers()
            try:
                self.wfile.write(res)
            except Exception:
                pass
            return
        payload = b'{"code":0,"msg":"ok"}'
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        try:
            self.wfile.write(payload)
        except Exception:
            pass
        return
    def do_GET(self):
        self._handle()
    def do_POST(self):
        self._handle()
    def do_CONNECT(self):
        # Forward CONNECT requests directly to local TLS port 8443
        w('CONNECT %s' % self.path)
        try:
            sock = socket.create_connection(('127.0.0.1', 8443), timeout=5)
            self.send_response(200, 'Connection Established')
            self.end_headers()
            conns = [self.connection, sock]
            self.close_connection = 0
            while True:
                r, wr, x = select.select(conns, [], conns, 10)
                if x:
                    break
                if not r:
                    break
                for s in r:
                    other = conns[1] if s is conns[0] else conns[0]
                    data = s.recv(8192)
                    if not data:
                        return
                    other.sendall(data)
        except Exception as e:
            w('CONNECT error: %s' % e)
        finally:
            try:
                sock.close()
            except Exception:
                pass

def serve_plain():
    w('=== SERVE-A plain :8080 ===')
    HTTPServer(('0.0.0.0', 8080), H).serve_forever()

def serve_tls():
    w('=== SERVE-A tls :8443 ===')
    srv = HTTPServer(('0.0.0.0', 8443), H)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(os.path.join(HERE, 'srv.crt'), os.path.join(HERE, 'srv.key'))
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    srv.serve_forever()

def serve_loginapp_tcp():
    w('=== LOGINAPP TCP :25000 LISTENING ===')
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', 25000))
    s.listen(5)
    while True:
        try:
            conn, addr = s.accept()
            w('LOGINAPP TCP ACCEPT from %s:%d' % addr)
            t = threading.Thread(target=_handle_loginapp_tcp_client, args=(conn, addr))
            t.daemon = True
            t.start()
        except Exception as e:
            w('LOGINAPP TCP accept error: %s' % e)

def _handle_loginapp_tcp_client(conn, addr):
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                w('LOGINAPP TCP %s:%d closed' % addr)
                break
            w('LOGINAPP TCP RECV %d bytes from %s:%d' % (len(data), addr[0], addr[1]))
            w('  HEX: %s' % data.hex())
            w('  ASCII: %r' % data[:128])
    except Exception as e:
        w('LOGINAPP TCP error from %s:%d: %s' % (addr[0], addr[1], e))
    finally:
        try:
            conn.close()
        except Exception:
            pass

def serve_loginapp_udp():
    w('=== LOGINAPP UDP :25000 LISTENING ===')
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', 25000))
    while True:
        try:
            data, addr = s.recvfrom(4096)
            w('LOGINAPP UDP RECV %d bytes from %s:%d' % (len(data), addr[0], addr[1]))
            w('  HEX: %s' % data.hex())
            w('  ASCII: %r' % data[:128])
        except Exception as e:
            w('LOGINAPP UDP error: %s' % e)

def serve_port443():
    """TLS on :443 -- catches native game TLS after VPN DNS redirect.
    Game connects to g61.gph.easebar.com:443 with TLS ClientHello."""
    w('=== SERVE-A tls :443 (VPN DNS catch) ===')
    srv = HTTPServer(('0.0.0.0', 443), H)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(os.path.join(HERE, 'srv.crt'), os.path.join(HERE, 'srv.key'))
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    srv.serve_forever()

def serve_port80():
    """Plain HTTP on :80 -- catches game Java HTTP after https->http patch."""
    w('=== SERVE-A plain :80 (https->http patch catch) ===')
    srv = HTTPServer(('0.0.0.0', 80), H)
    srv.serve_forever()

if __name__ == '__main__':
    w('=== mitm_serve A START ===')
    t1 = threading.Thread(target=serve_tls)
    t1.daemon = True
    t1.start()
    t2 = threading.Thread(target=serve_loginapp_tcp)
    t2.daemon = True
    t2.start()
    t3 = threading.Thread(target=serve_loginapp_udp)
    t3.daemon = True
    t3.start()
    t4 = threading.Thread(target=serve_port443)
    t4.daemon = True
    t4.start()
    t5 = threading.Thread(target=serve_port80)
    t5.daemon = True
    t5.start()
    serve_plain()
