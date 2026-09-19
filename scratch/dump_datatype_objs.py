"""Dump the 36 unique DataType objects and look for a cached stream-size field.

If DataType carries its fixed wire size, we can size every property exactly --
including FIXED_DICT, whose field list is currently guessed from XML and is the
prime suspect for the remaining 1-byte desync.
"""
import struct, subprocess, os, collections

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
KNOWN_SIZE = {'INT32': 4, 'INT8': 1, 'INT64': 8, 'FLOAT': 4, 'UINT64': 8,
              'UINT32': 4, 'UINT8': 1, 'INT16': 2}


def sh(c):
    return subprocess.run([ADB, '-s', DEV, 'shell', c], capture_output=True, text=True).stdout


def read_mem(pid, addr, size):
    a = (addr // 4096) * 4096
    skip, inner, cnt = a // 4096, addr - a, (addr - a + size + 4095) // 4096
    sh(f"su 0 sh -c 'dd if=/proc/{pid}/mem bs=4096 skip={skip} count={cnt} "
       f"of=/data/local/tmp/_o.bin 2>/dev/null; chmod 666 /data/local/tmp/_o.bin'")
    lp = os.path.join(OUT, '_o.bin')
    if os.path.exists(lp):
        os.remove(lp)
    subprocess.run([ADB, '-s', DEV, 'pull', '/data/local/tmp/_o.bin', lp],
                   capture_output=True, text=True)
    return open(lp, 'rb').read()[inner:inner + size]


pid = sh('pidof com.netease.chiji').strip().split()[0]
base = int(sh(f"su 0 sh -c 'grep libclient.so /proc/{pid}/maps | head -1'").split('-')[0], 16)
begin, end, _ = struct.unpack('<QQQ', read_mem(pid, base + 0x45785f0, 24))
athlete = struct.unpack('<Q', read_mem(pid, begin + 51 * 8, 8))[0]
p_begin, p_end = struct.unpack('<QQ', read_mem(pid, athlete + 0x58, 16))
total = (p_end - p_begin) // 0x68
raw = read_mem(pid, p_begin, total * 0x68)

# property index -> DataType object pointer (slot +0x18)
dt = {i: struct.unpack_from('<Q', raw, i * 0x68 + 0x18)[0] for i in range(total)}
uniq = sorted(set(dt.values()))
print(f'{len(uniq)} unique DataType objects')

objs = {}
for p in uniq:
    objs[p] = read_mem(pid, p, 0x40)

# label each object by the vtable at offset 0
labelled = []
for p in uniq:
    v = struct.unpack_from('<Q', objs[p], 0)[0]
    labelled.append((p, VT.get(hex(v), hex(v))))

print('\nobjects by type:')
for p, name in labelled:
    users = [i for i in range(total) if dt[i] == p]
    print(f'  0x{p:x}  {name:12s}  used_by={len(users):3d}')

# hunt for an offset whose value equals the known fixed size for the primitive types
print('\nsearching for a cached stream-size field...')
for off in range(8, 0x40, 4):
    ok = bad = 0
    for p, name in labelled:
        if name not in KNOWN_SIZE:
            continue
        val = struct.unpack_from('<i', objs[p], off)[0]
        if val == KNOWN_SIZE[name]:
            ok += 1
        else:
            bad += 1
    if ok and bad == 0:
        print(f'  +0x{off:02x}: MATCHES all {ok} primitive types')
        for p, name in labelled:
            val = struct.unpack_from('<i', objs[p], off)[0]
            print(f'     {name:12s} size={val}')
