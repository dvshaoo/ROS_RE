"""Dump MethodDescription records (0x68 bytes each) of the Athlete EntityType vectors +0x160 (1393 entries) and +0x1b8 (1131 = client
methods) from the live client and print index/name/flags. Goal: map client->server (base) method indices for decoding upstream bundles."""
import struct, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dump_runtime_types as D
D.ADB[0] = os.environ.get('ADB_PATH', D.ADB[0])
D.PID = D.pid_of()
maps = D.sh(f"su 0 grep libclient.so /proc/{D.PID}/maps | head -1")
base = int(maps.split('-')[0], 16)
vb, ve = struct.unpack('<QQ', D.rd(base + 0x45785f0, 16))
athlete = D.u64(D.rd(vb + 51 * 8, 8), 0)
off = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x160
b, e = struct.unpack('<QQ', D.rd(athlete + off, 16))
n = (e - b) // 0x68
raw = D.rd(b, n * 0x68)
print('vector +0x%x entries %d' % (off, n))
def strat(o):
    if raw[o] & 1 == 0:
        return raw[o + 1:o + 1 + (raw[o] >> 1)].decode('latin1')
    ln, ptr = struct.unpack_from('<QQ', raw, o + 8)
    return D.rd(ptr, ln).decode('latin1') if 0 < ln < 200 else '?'
out = []
for i in range(n):
    o = i * 0x68
    # find a std::string among the first 0x68 bytes: try offsets 0,0x18,0x30
    names = [strat(o + k) for k in (0, 0x18, 0x30)]
    out.append((i, names, raw[o:o + 0x68].hex()))
with open(r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\athlete_desc_%x.txt' % off, 'w', encoding='utf-8') as f:
    for i, nm, hx in out:
        f.write('[%4d] %s | %s\n' % (i, ' / '.join(nm), hx))
for i, nm, hx in out[:8]:
    print(i, nm, hx[:64])
