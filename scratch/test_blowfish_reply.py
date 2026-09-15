import socket, struct, threading, time, sys
from Crypto.Cipher import Blowfish

BASEAPP_HOST = '172.16.1.2'
BASEAPP_PORT = 25010
KEY = bytes([0xb2, 0x52, 0x5a, 0x3c])  # live-extracted key for PID 9754's connection

def build_body():
    ip_bytes = socket.inet_aton(BASEAPP_HOST)
    addr = ip_bytes + struct.pack('!H', BASEAPP_PORT) + b'\x00\x00'
    record = addr + addr + struct.pack('<I', 0x12345678)
    assert len(record) == 20
    return record + b'\x00\x00\x00\x00'  # pad to 24

MODE = sys.argv[1] if len(sys.argv) > 1 else 'ecb'

def encrypt(body):
    if MODE == 'ecb':
        c = Blowfish.new(KEY, Blowfish.MODE_ECB)
        return c.encrypt(body)
    elif MODE == 'cbc0':
        c = Blowfish.new(KEY, Blowfish.MODE_CBC, iv=b'\x00'*8)
        return c.encrypt(body)
    elif MODE == 'pc_variant':
        # PC-launcher documented variant: XOR each plaintext block against the
        # PREVIOUS PLAINTEXT block (not previous ciphertext), IV=0, then ECB-encrypt.
        c = Blowfish.new(KEY, Blowfish.MODE_ECB)
        blocks = [body[i:i+8] for i in range(0, len(body), 8)]
        prev = b'\x00'*8
        out = b''
        for blk in blocks:
            xored = bytes(a ^ b for a, b in zip(blk, prev))
            enc = c.encrypt(xored)
            out += enc
            prev = blk
        return out
    else:
        raise ValueError(MODE)

body = build_body()
enc_body = encrypt(body)
print('MODE=%s plaintext=%s ciphertext=%s' % (MODE, body.hex(), enc_body.hex()))

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('0.0.0.0', 25000))
s.settimeout(15)
print('Listening on :25000, waiting for ONE LogOnParams request...')
try:
    data, addr = s.recvfrom(8192)
    print('RECV %d bytes from %s' % (len(data), addr))
    counter = struct.unpack('<I', data[5:9])[0]
    inner = struct.pack('<I', counter) + bytes([1]) + enc_body
    reply = (struct.pack('<H', 0x0001) + bytes([0xff])
              + struct.pack('<I', len(inner)) + inner
              + b'\x00\x00')
    s.sendto(reply, addr)
    print('SENT reply id=0x%08x len=%d' % (counter, len(reply)))
except socket.timeout:
    print('TIMEOUT waiting for request')
