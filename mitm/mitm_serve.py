# -*- coding: utf-8 -*-
# mitm_serve.py -- ROS-RE MITM serve run B (T07 Hypothesis A: G4 text, no-update).
# Serves /pl/npk_version_na_android.plist as b'G4\nversion=1117219\ncount=0\n'.
# Everything else: log-only 404. Logs -> captures/SERVE_B.txt
import os, re, ssl, threading, time, json, base64, hashlib, socket, select
try:
    from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
except Exception:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
    ThreadingHTTPServer = HTTPServer

import session_store

# LDPlayer's current guest network is 172.16.1.0/24; the host-side
# endpoint reachable from the guest is 172.16.1.2 (not the old emulator
# alias 10.0.2.2 used by earlier captures).
MITM_HOST = os.environ.get('ROS_MITM_HOST', '172.16.1.2')

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
# Keep one persistent handle instead of open()/close() on every single log line.
# Under ThreadingHTTPServer, every request thread serializes on _lock to log --
# with a fresh open()+close() (each a real syscall, slower still under Windows AV
# scanning) on every line, a burst of concurrent requests during the client's
# loading phase can stack up enough latency on this shared lock to look like a
# slow server response even though request handling itself is fast, plausibly
# contributing to the "Slow connection" dialog seen mid-loading.
_log_fh = open(LOG, 'a', encoding='utf-8', errors='replace')

def w(m):
    with _lock:
        print(m, flush=True)
        try:
            now = time.time()
            ts = '%s.%03d' % (time.strftime('%H:%M:%S', time.localtime(now)), int((now % 1) * 1000))
            _log_fh.write('%s %s\n' % (ts, m))
            _log_fh.flush()
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
    b'  "file_list": ["patch.1117219.com.netease.chiji.obb"],\n'
    b'  "patch.1117219.com.netease.chiji.obb_updated": 0,\n'
    b'  "patch.1117219.com.netease.chiji.obb_size": 1,\n'
    b'  "patch.1117219.com.netease.chiji.obb_md5": "00000000000000000000000000000000"\n'
    b'}\n'
)
w('T15-complete plist: %d bytes' % len(PLIST))

import zlib, pickle
# ResourcePatcher contract: empty file_list in PLIST and empty dict in total_list.
# Validated by tools/test_patch_contract.py.
TOTAL_LIST_PAYLOAD = zlib.compress(pickle.dumps({}, 2))

# T18: server-list 1-line payload (cited: ui/UILogin.py:197-237 positional
# space-delimited schema; single spaces only — split(' ') shifts on doubles).
# 10.0.2.2 = emulator->host route (no adb reverse needed for the later login
# connect); port 25000 is our future fake-loginapp port (nothing there yet).
_server_host = os.environ.get('ROS_LOGINAPP_HOST', MITM_HOST).encode('ascii')
SERVER_LIST_PAYLOAD = (
    b'North_America 1 1 1 North_America North_America ' +
    _server_host + b':25000 ' + _server_host + b':25000 ' +
    _server_host + b':25000 10001 ' + _server_host + b':25000\n'
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
            w('  BODY %r' % body)
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
        # The current client uses a versioned absolute URI such as
        # /220330002853_android/total_list; older captures used /1117219.
        # Match the endpoint suffix so both forms receive the compressed
        # pickle payload instead of falling through to the generic JSON.
        if self.path.endswith('/total_list'):
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
        if '/file_list_' in self.path:
            # File lists use the same compressed-pickle envelope as
            # total_list; return an empty mapping, not JSON or a zero-byte
            # body, so the updater can complete its comparison.
            w('  -> SERVE empty file list')
            payload = zlib.compress(pickle.dumps({}, 2))
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
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
            w('  -> SERVE HTTPDNS (host=%s) domain=%s -> %s' % (host, domain, MITM_HOST))
            # NeoX pharos HttpdnsDomain2IpParams expects: {"domain":"...","addrs":["IP"],"ttl":600}
            res = '{"domain":"%s","addrs":["%s"],"ttl":600}' % (domain, MITM_HOST)
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
            w('  -> SERVE HTTPDNS resolve -> %s (our MITM host)' % MITM_HOST)
            domain = 'g61.gph.easebar.com'
            if 'domain=' in self.path:
                try:
                    domain = self.path.split('domain=')[1].split('&')[0]
                except Exception:
                    pass
            res = '{"domain":"%s","addrs":["%s"],"ttl":600}' % (domain, MITM_HOST)
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
            # "persistence" (-> c/a/c.q, read by c/a/c.a()/g/e.d()) is a real field the
            # official protocol sends; harmless and correct to include. NOTE (2026-09-26):
            # this field is NOT the fix for netease_mpay_oversea__login_expired -- traced
            # that dialog instead to g/e.a(type) being called with a literal null `type`
            # (com/netease/mpay/oversea/ui/l;->a, `final`, set once at construction) on
            # the automatic pre-title login attempt. A null type isn't one of g/e.a()'s
            # three always-true sentinels (UNKNOWN/TOKEN/MORE) and isn't a key any
            # account_type entry can ever be registered under (HashMap keyed by the
            # j/a/g enum, populated via literal JSON keys like "guest"->GUEST -- verified
            # that mapping IS correct and would succeed if type were actually GUEST).
            # Open question: which caller constructs the login flow with type=null for
            # the automatic attempt, and why (see CLAUDE.md checkpoint 22 for the full
            # trace); not yet root-caused to a fix.
            res = (
                b'{"code":0,"msg":"","bound_account_types":[],"game_config":{'
                b'"account_type":{"guest":{"api_type":"guest","enable":true,"priority":1,"login_priority":1,"text":"Guest","color":"#ffffff"}},'
                b'"text":{},"server_list":{"enable":true},"quick_login":{"enable":true},'
                b'"security_email":{"enable":false},"login_style":0,"login_page_style":0,"debug_mode":0,'
                b'"persistence":2,'
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
            player_id = 'guest_11178811c6a412d9'
            rec = session_store.create_session(player_id, source='guest_login')
            sid = rec['session_id']
            w('  -> SERVE /api/users/login/guest (minor_status=102 adult verified, session=%s...)'
              % session_store._short(sid))
            # com/netease/mpay/oversea/d/a/a/e.smali's response parser reads
            # bound_account_types/bound_account_ids/notify_guest_bind/unknown_bind_guide/
            # minor_status/age_status/security_email from the NESTED "user" object, not
            # the response root (only "confirm_message" is read from the root). Previously
            # these were sent at the root only, so that parser's optInt() defaults kicked in
            # (minor_status=0, age_status=2) regardless of what we sent, which is what
            # actually triggers the "User Age Setting" dialog before the title screen --
            # confirmed by reading the smali directly (2026-09-25). Fix: send them in BOTH
            # places (additive, not moved) -- nested for this parser, and still at the root
            # in case another response consumer reads them there; extra JSON keys are free.
            res = json.dumps({
                'code': 0, 'msg': '', 'alert_type': 0, 'bound_account_types': [],
                'bound_account_ids': {}, 'confirm_message': '', 'notify_guest_bind': 0,
                'unknown_bind_guide': 0, 'minor_status': 102, 'age_status': 1,
                'security_email': '',
                'user': {
                    'id': player_id, 'account': 'Guest_11178811c6a412d9',
                    'login_token': sid, 'token': sid,
                    'quick_login_enable': True,
                    'bound_account_types': [], 'bound_account_ids': {},
                    'notify_guest_bind': 0, 'unknown_bind_guide': 0,
                    'minor_status': 102, 'age_status': 1, 'security_email': '',
                },
            }).encode('utf-8')
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
            player_id = 'guest_11178811c6a412d9'
            rec = session_store.create_session(player_id, source='sdk_token')
            sid = rec['session_id']
            w('  -> SERVE /api/users/login/v2/sdk_token (top-level user_id & sdk_token, '
              'minor_status=102, session=%s...)' % session_store._short(sid))
            # Same fix as /api/users/login/guest: com/netease/mpay/oversea/d/a/a/e.smali's
            # shared login-response parser (used by every provider in the j/a/g enum,
            # sdk_token included) reads minor_status/age_status from the NESTED "user"
            # object, not the response root. This is the silent-relogin path taken on the
            # 2nd+ app launch (fresh installs go through /api/users/login/guest instead),
            # so leaving only the root-level copy here let the age gate reappear on every
            # relaunch after the first (2026-09-25, confirmed live). Fix is additive (both
            # root and nested), same reasoning as the guest handler above.
            res = json.dumps({
                'code': 0, 'msg': '', 'user_id': player_id, 'sdk_token': sid,
                'alert_type': 0, 'bound_account_types': [], 'bound_account_ids': {},
                'notify_guest_bind': 0, 'unknown_bind_guide': 0,
                'minor_status': 102, 'age_status': 1, 'security_email': '',
                'user': {
                    'id': player_id, 'account': 'Guest_11178811c6a412d9',
                    'login_token': sid, 'token': sid,
                    'quick_login_enable': True,
                    'bound_account_types': [], 'bound_account_ids': {},
                    'notify_guest_bind': 0, 'unknown_bind_guide': 0,
                    'minor_status': 102, 'age_status': 1, 'security_email': '',
                },
            }).encode('utf-8')
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
            # Same nested-"user" fix as /api/users/login/guest and .../v2/sdk_token above,
            # additive (both root and nested).
            res = (
                b'{"code":0,"msg":"","alert_type":0,"bound_account_types":[],'
                b'"bound_account_ids":{},"confirm_message":"","notify_guest_bind":0,'
                b'"unknown_bind_guide":0,"minor_status":102,"age_status":1,"security_email":"",'
                b'"user":{"id":"guest_11178811c6a412d9","account":"Guest_11178811c6a412d9",'
                b'"login_token":"guest_token_fake_ros_2026","token":"guest_token_fake_ros_2026",'
                b'"quick_login_enable":true,"bound_account_types":[],"bound_account_ids":{},'
                b'"notify_guest_bind":0,"unknown_bind_guide":0,"minor_status":102,'
                b'"age_status":1,"security_email":""}}'
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
        if self.path.startswith('/feature/') and self.path.endswith('.json.md5'):
            # unisdk.update.netease.com feature-flag manifest MD5 check (fetched right
            # after StartPatch/JumpVersionStage, before JumpBirthStage). Previously fell
            # through to the generic {"code":0,"msg":"ok"} catch-all, which isn't a valid
            # MD5 hex digest -- the client's integrity check on the paired .json fetch
            # then fails, producing "Failed to retrieve patches." Return the real MD5 of
            # the empty-object body served for the .json path so the check passes clean.
            w('  -> SERVE /feature/*.json.md5 (md5 of empty feature json)')
            body = b'{}'
            res = hashlib.md5(body).hexdigest().encode('ascii')
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', str(len(res)))
            self.end_headers()
            try:
                self.wfile.write(res)
            except Exception:
                pass
            return
        if self.path.startswith('/feature/') and self.path.endswith('.json'):
            w('  -> SERVE /feature/*.json (empty feature flags)')
            res = b'{}'
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
    def do_HEAD(self):
        # Force Content-Length: 0 on the headers we actually send. Previously only
        # wfile.write() was stubbed, so _handle()'s normal GET-sized Content-Length
        # (e.g. from the "/" root catch-all) still went out on the wire with zero
        # body bytes following it. A strict HTTP client that reads exactly
        # Content-Length bytes after headers (rather than special-casing HEAD per
        # RFC 7231 4.3.2) then hangs waiting for bytes that never arrive, until its
        # own timeout -- a plausible cause of the connectivity-probe HEAD requests
        # (www.sogou.com/hao.360.cn/m.baidu.com, all routed to us via DNAT) always
        # reporting failed/negative timing and contributing to "PrePatchStage.FAIL"
        # (2026-09-25 investigation).
        orig_write = self.wfile.write
        orig_send_header = self.send_header
        self.wfile.write = lambda *args, **kwargs: None
        def patched_send_header(keyword, value):
            if keyword.lower() == 'content-length':
                value = '0'
            orig_send_header(keyword, value)
        self.send_header = patched_send_header
        try:
            self._handle()
        finally:
            self.wfile.write = orig_write
            self.send_header = orig_send_header
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
