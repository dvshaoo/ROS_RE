"""Find where the DataType pointer lives inside a 0x68-byte property descriptor,
then group all 832 properties by their DataType vtable.

The XML-derived types are unreliable (same property name is declared with different
types across interfaces, and the client's runtime type wins). The descriptor's own
DataType object is authoritative.
"""
import struct, subprocess, os, collections

ADB = r'C:\LDPlayer\LDPlayer9\adb.exe'
DEV = 'emulator-5554'
OUT = r'C:\Users\Raysoo\Downloads\ROS_RE\scratch'


def sh(c):
    return subprocess.run([ADB, '-s', DEV, 'shell', c], capture_output=True, text=True).stdout


def read_mem(pid, addr, size):
    aligned = (addr // 4096) * 4096
    skip, inner = aligned // 4096, addr - aligned
    count = (inner + size + 4095) // 4096
    sh(f"su 0 sh -c 'dd if=/proc/{pid}/mem bs=4096 skip={skip} count={count} "
       f"of=/data/local/tmp/_d.bin 2>/dev/null; chmod 666 /data/local/tmp/_d.bin'")
    lp = os.path.join(OUT, '_d.bin')
    if os.path.exists(lp):
        os.remove(lp)
    subprocess.run([ADB, '-s', DEV, 'pull', '/data/local/tmp/_d.bin', lp],
                   capture_output=True, text=True)
    return open(lp, 'rb').read()[inner:inner + size]


pid = sh('pidof com.netease.chiji').strip().split()[0]
base = int(sh(f"su 0 sh -c 'grep libclient.so /proc/{pid}/maps | head -1'").split('-')[0], 16)
print(f'pid={pid} base=0x{base:x}')

begin, end, _ = struct.unpack('<QQQ', read_mem(pid, base + 0x45785f0, 24))
athlete = struct.unpack('<Q', read_mem(pid, begin + 51 * 8, 8))[0]
p_begin, p_end = struct.unpack('<QQ', read_mem(pid, athlete + 0x58, 16))
total = (p_end - p_begin) // 0x68
raw = read_mem(pid, p_begin, total * 0x68)
print(f'{total} descriptors')


def is_heap(v):
    return 0x700000000000 <= v < 0x800000000000


# Which 8-byte slot in the descriptor is a pointer for (almost) every property?
cand = []
for off in range(0, 0x68, 8):
    n = sum(1 for i in range(total)
            if is_heap(struct.unpack_from('<Q', raw, i * 0x68 + off)[0]))
    if n > total * 0.9:
        cand.append((off, n))
print('pointer-ish slots:', cand)

# For each candidate slot, deref and read the first qword (vtable) of the target.
for off, _n in cand:
    ptrs = sorted({struct.unpack_from('<Q', raw, i * 0x68 + off)[0] for i in range(total)})
    # DataType objects are scattered across the heap, so read them as contiguous
    # clusters instead of one giant span.
    clusters, cur = [], [ptrs[0], ptrs[0]]
    for p in ptrs[1:]:
        if p - cur[1] <= 64 * 1024:
            cur[1] = p
        else:
            clusters.append(tuple(cur))
            cur = [p, p]
    clusters.append(tuple(cur))
    print(f'slot +0x{off:02x}: {len(ptrs)} unique targets in {len(clusters)} clusters')

    vtab = {}
    for clo, chi in clusters:
        blob = read_mem(pid, clo, chi - clo + 8)
        for p in ptrs:
            if clo <= p <= chi:
                o = p - clo
                if 0 <= o <= len(blob) - 8:
                    vtab[p] = struct.unpack_from('<Q', blob, o)[0]

    vt = collections.Counter()
    for i in range(total):
        p = struct.unpack_from('<Q', raw, i * 0x68 + off)[0]
        if p in vtab:
            vt[vtab[p]] += 1
    incode = sum(c for v, c in vt.items() if 0x3000000 <= v < 0x8000000)
    print(f'slot +0x{off:02x}: {len(vt)} distinct first-qwords, '
          f'{incode}/{total} look like code pointers')
    if incode > total * 0.9 and 2 <= len(vt) <= 60:
        print('   ==> DataType vtable slot found')
        for v, c in vt.most_common():
            print(f'      vtable 0x{v:x}  count={c}')
        with open(os.path.join(OUT, 'datatype_vtables.txt'), 'w') as f:
            for i in range(total):
                p = struct.unpack_from('<Q', raw, i * 0x68 + off)[0]
                f.write(f'{i}\t0x{vtab.get(p, 0):x}\n')
        print('   wrote scratch/datatype_vtables.txt')
        break
