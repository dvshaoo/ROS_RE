"""For the FIXED_DICT properties in the stream, recover their child field types from
the runtime DataType object instead of from XML.

Recognition trick: we already know every DataType object address in the process, so
any pointer inside a FIXED_DICT object that lands on one of them is a child field's
DataType.
"""
import struct, subprocess, os, json

ADB = r'C:\LDPlayer\LDPlayer9\adb.exe'
DEV = 'emulator-5554'
OUT = r'C:\Users\Raysoo\Downloads\ROS_RE\scratch'

VT = {
    '0x6af6c38': 'INT32', '0x6af7a28': 'PYTHON', '0x6af69d8': 'INT8',
    '0x6af6448': 'ARRAY', '0x6af6050': 'STRING', '0x6af7228': 'INT64',
    '0x6af7778': 'FLOAT', '0x6af5f90': 'FIXED_DICT', '0x6af7418': 'UINT64',
    '0x6af84f8': 'BLOB', '0x6af70f8': 'UINT32', '0x6af6778': 'UINT8',
    '0x6af6b08': 'INT16',
}


def sh(c):
    return subprocess.run([ADB, '-s', DEV, 'shell', c], capture_output=True, text=True).stdout


def read_mem(pid, addr, size):
    a = (addr // 4096) * 4096
    skip, inner, cnt = a // 4096, addr - a, (addr - a + size + 4095) // 4096
    sh(f"su 0 sh -c 'dd if=/proc/{pid}/mem bs=4096 skip={skip} count={cnt} "
       f"of=/data/local/tmp/_f.bin 2>/dev/null; chmod 666 /data/local/tmp/_f.bin'")
    lp = os.path.join(OUT, '_f.bin')
    if os.path.exists(lp):
        os.remove(lp)
    subprocess.run([ADB, '-s', DEV, 'pull', '/data/local/tmp/_f.bin', lp],
                   capture_output=True, text=True)
    return open(lp, 'rb').read()[inner:inner + size]


pid = sh('pidof com.netease.chiji').strip().split()[0]
base = int(sh(f"su 0 sh -c 'grep libclient.so /proc/{pid}/maps | head -1'").split('-')[0], 16)
begin, _e, _c = struct.unpack('<QQQ', read_mem(pid, base + 0x45785f0, 24))
athlete = struct.unpack('<Q', read_mem(pid, begin + 51 * 8, 8))[0]
p_begin, p_end = struct.unpack('<QQ', read_mem(pid, athlete + 0x58, 16))
total = (p_end - p_begin) // 0x68
raw = read_mem(pid, p_begin, total * 0x68)

dt = {i: struct.unpack_from('<Q', raw, i * 0x68 + 0x18)[0] for i in range(total)}
known = {}
for p in set(dt.values()):
    v = struct.unpack_from('<Q', read_mem(pid, p, 8), 0)[0]
    known[p] = VT.get(hex(v), hex(v))

rows = json.load(open(os.path.join(OUT, 'athlete_prop_types.json'), encoding='utf-8'))
inc = [r for r in rows if r['included']]

targets = [(o, r) for o, r in enumerate(inc) if known.get(dt[r['idx']]) == 'FIXED_DICT']
print(f'FIXED_DICT properties in the stream: {len(targets)}')

for ordinal, r in targets:
    obj = dt[r['idx']]
    print(f"\n=== ord {ordinal} idx {r['idx']} {r['name']}  obj=0x{obj:x} ===")
    blob = read_mem(pid, obj, 0x120)
    fields = []
    for off in range(0, 0x120 - 8, 8):
        v = struct.unpack_from('<Q', blob, off)[0]
        if v in known:
            fields.append((off, v, known[v]))
    if fields:
        print('  direct child DataType pointers inside the object:')
        for off, v, nm in fields:
            print(f'    +0x{off:02x} -> 0x{v:x} {nm}')
    # also follow any heap vector of pointers
    for off in range(0, 0x120 - 24, 8):
        b, e2, _c2 = struct.unpack_from('<QQQ', blob, off)
        if not (0x700000000000 <= b < 0x800000000000 and b < e2 <= b + 4096):
            continue
        n = (e2 - b) // 8
        if not (1 <= n <= 64):
            continue
        vecb = read_mem(pid, b, (e2 - b))
        kids = [struct.unpack_from('<Q', vecb, k * 8)[0] for k in range(n)]
        named = [known.get(k) for k in kids]
        if any(named):
            print(f'  vector @ +0x{off:02x}: {n} entries -> {named}')
