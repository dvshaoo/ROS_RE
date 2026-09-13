# -*- coding: utf-8 -*-
# mitm_log.py -- ROS-RE MITM log-only server (Phase: capture BEFORE crafting).
# HTTP :8080 (plain) + HTTPS :8443 (srv.crt/srv.key). Logs every request line,
# headers (Host/SNI), body (first 2KB) to captures/MITM.txt. Replies 404 JSON.
# Emulator reaches us via DNAT (80->8080, 443->8443) + bind-mounted system CA.
import os, ssl, time, threading
try:
    from http.server import BaseHTTPRequestHandler, HTTPServer
except Exception:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
CAP = os.path.join(HERE, 'captures')
try:
    os.makedirs(CAP)
except Exception:
    pass
LOG = os.path.join(CAP, 'MITM.txt')
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
        sni = getattr(self.connection, '_sni_host', '?')
        w('REQ %s %s host=%s sni=%s len=%d' % (self.command, self.path, host, sni, length))
        try:
            for k in ('User-Agent', 'Content-Type', 'jf_gameid', 'unisdk_deviceid', 'transid'):
                v = self.headers.get(k)
                if v:
                    w('  H %s: %s' % (k, v))
        except Exception:
            pass
        if body:
            w('  BODY %.2048r' % body[:2048])
        payload = b'{"code":404,"msg":"mitm-log-only"}'
        self.send_response(404)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        try:
            self.wfile.write(payload)
        except Exception:
            pass
    def do_GET(self):
        self._handle()
    def do_POST(self):
        self._handle()
    def do_PUT(self):
        self._handle()
    def log_message(self, *a):
        pass

class SNIHTTPServer(HTTPServer):
    def get_request(self):
        conn, addr = self.socket.accept()
        conn._sni_host = '?'
        return conn, addr

def serve_plain():
    w('=== MITM plain :8080 ===')
    HTTPServer(('0.0.0.0', 8080), H).serve_forever()

def serve_tls():
    w('=== MITM tls :8443 ===')
    srv = SNIHTTPServer(('0.0.0.0', 8443), H)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(os.path.join(HERE, 'srv.crt'), os.path.join(HERE, 'srv.key'))
    def sni_cb(sock, name, ctx2):
        try:
            sock._sni_host = name or '?'
        except Exception:
            pass
    try:
        ctx.sni_callback = sni_cb
    except Exception:
        pass
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    srv.serve_forever()

if __name__ == '__main__':
    w('=== mitm_log START ===')
    t = threading.Thread(target=serve_tls)
    t.daemon = True
    t.start()
    serve_plain()
