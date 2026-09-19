"""Recover the exact field layout of each FIXED_DICT used by the Athlete stream.

Structure found by probing: the DataType object holds a vector at +0xe0 of field
records, 5 qwords (40 bytes) each, with the field's own DataType pointer at qword 3
of the record. Resolve every child DataType by reading ITS vtable, so nested types
are named even when they are not used by any top-level Athlete property.
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
SIZE = {'INT32': 4, 'INT8': 1, 'INT64': 8, 'FLOAT': 4, 'UINT64': 8, 'UINT32': 4,
        'UINT8': 1, 'INT16': 2, 'STRING': 1, 'BLOB': 1, 'PYTHON': 3, 'ARRAY': 4}


def sh(c):
    return subprocess.run([ADB, '-s', DEV, 'shell', c], capture_output=True, text=True).stdout


def read_mem(pid, addr, size):
    a = (addr // 4096) * 4096
    skip, inner, cnt = a // 4096, addr - a, (addr - a + size + 4095) // 4096
    sh(f"su 0 sh -c 'dd if=/proc/{pid}/mem bs=4096 skip={skip} count={cnt} "
       f"of=/data/local/tmp/_g.bin 2>/dev/null; chmod 666 /data/local/tmp/_g.bin'")
    lp = os.path.join(OUT, '_g.bin')
    if os.path.exists(lp):
        os.remove(lp)
    subprocess.run([ADB, '-s', DEV, 'pull', '/data/local/tmp/_g.bin', lp],
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


def type_of(obj):
    if not (0x700000000000 <= obj < 0x800000000000):
        return None
    v = struct.unpack_from('<Q', read_mem(pid, obj, 8), 0)[0]
    return VT.get(hex(v))


def fields_of(obj, depth=0):
    """Return [(type, size_or_None)] for a FIXED_DICT DataType object."""
    blob = read_mem(pid, obj, 0x100)
    b, e2, _ = struct.unpack_from('<QQQ', blob, 0xe0)
    if not (0x700000000000 <= b < 0x800000000000 and b < e2 <= b + 8192):
        return None
    n = (e2 - b) // 8
    vec = read_mem(pid, b, e2 - b)
    out = []
    for rec in range(n // 5):
        p = struct.unpack_from('<Q', vec, (rec * 5 + 3) * 8)[0]
        t = type_of(p)
        if t == 'FIXED_DICT' and depth < 3:
            sub = fields_of(p, depth + 1)
            out.append(('FIXED_DICT', sub))
        else:
            out.append((t, None))
    return out


rows = json.load(open(os.path.join(OUT, 'athlete_prop_types.json'), encoding='utf-8'))
inc = [r for r in rows if r['included']]
result = {}
for ordinal, r in enumerate(inc):
    if type_of(dt[r['idx']]) != 'FIXED_DICT':
        continue
    f = fields_of(dt[r['idx']])
    print(f"\nord {ordinal}  idx {r['idx']}  {r['name']}")
    print(f"   fields: {f}")
    if f and all(t in SIZE for t, _ in f):
        print(f"   computed wire size = {sum(SIZE[t] for t, _ in f)} bytes")
    result[str(ordinal)] = [t for t, _ in (f or [])]

json.dump(result, open(os.path.join(OUT, 'fixed_dict_fields.json'), 'w'), indent=1)
print('\nwrote scratch/fixed_dict_fields.json')
