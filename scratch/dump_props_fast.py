"""Dump Athlete's live property-descriptor table (EntityType+0x58, 0x68 stride).

Uses block-aligned dd (not bs=1) so 87KB comes back in one fast read.
"""
import struct, subprocess, os, sys

ADB = r'C:\LDPlayer\LDPlayer9\adb.exe'
DEV = 'emulator-5554'
OUT = r'C:\Users\Raysoo\Downloads\ROS_RE\scratch'


def sh(cmd):
    return subprocess.run([ADB, '-s', DEV, 'shell', cmd],
                          capture_output=True, text=True).stdout


def read_mem(pid, addr, size):
    """Block-aligned read of [addr, addr+size) via dd + adb pull."""
    aligned = (addr // 4096) * 4096
    skip = aligned // 4096
    inner = addr - aligned
    count = (inner + size + 4095) // 4096
    # chmod is required: dd runs as root and creates the file 0600, but `adb pull`
    # runs as the shell user and cannot read it otherwise.
    sh(f"su 0 sh -c 'dd if=/proc/{pid}/mem bs=4096 skip={skip} count={count} "
       f"of=/data/local/tmp/_rd.bin 2>/dev/null; chmod 666 /data/local/tmp/_rd.bin'")
    local = os.path.join(OUT, '_rd.bin')
    if os.path.exists(local):
        os.remove(local)
    r = subprocess.run([ADB, '-s', DEV, 'pull', '/data/local/tmp/_rd.bin', local],
                       capture_output=True, text=True)
    if not os.path.exists(local):
        raise RuntimeError(f'pull failed for addr=0x{addr:x} size={size}: {r.stdout} {r.stderr}')
    with open(local, 'rb') as f:
        blob = f.read()
    return blob[inner:inner + size]


pid = sh('pidof com.netease.chiji').strip().split()[0]
maps = sh(f"su 0 sh -c 'grep libclient.so /proc/{pid}/maps | head -1'")
base = int(maps.split('-')[0], 16)
print(f'pid={pid} base=0x{base:x}')

vec = read_mem(pid, base + 0x45785f0, 24)
begin, end, cap = struct.unpack('<QQQ', vec)
n_types = (end - begin) // 8
print(f'EntityType vector: {n_types} types')

athlete_ptr_raw = read_mem(pid, begin + 51 * 8, 8)
athlete = struct.unpack('<Q', athlete_ptr_raw)[0]
print(f'Athlete EntityType @ 0x{athlete:x}')

pt = read_mem(pid, athlete + 0x58, 16)
p_begin, p_end = struct.unpack('<QQ', pt)
total = (p_end - p_begin) // 0x68
print(f'property table: begin=0x{p_begin:x} end=0x{p_end:x} count={total} (stride 0x68)')

raw = read_mem(pid, p_begin, total * 0x68)
print(f'read {len(raw)} bytes of descriptors')

# Names use libc++ std::string: SSO when (byte0 & 1) == 0 (len = byte0 >> 1, chars inline
# at +1), otherwise heap-allocated with [cap@0][len@8][ptr@16]. Long property names exceed
# the 22-char SSO budget, so the heap case must be dereferenced or they read as blanks.
heap_reads = [(i, struct.unpack_from('<Q', raw, i * 0x68 + 8)[0],
               struct.unpack_from('<Q', raw, i * 0x68 + 16)[0])
              for i in range(total) if raw[i * 0x68] & 1]
print(f'{len(heap_reads)} heap-allocated names to resolve')

heap_names = {}
if heap_reads:
    lo = min(p for _, _, p in heap_reads)
    hi = max(p + l + 1 for _, l, p in heap_reads)
    span = read_mem(pid, lo, hi - lo)
    for i, slen, sptr in heap_reads:
        off = sptr - lo
        heap_names[i] = span[off:off + slen].decode('latin1', 'ignore')

lines = []
for i in range(total):
    d = raw[i * 0x68:(i + 1) * 0x68]
    b0 = d[0]
    name = heap_names.get(i) if (b0 & 1) else d[1:1 + (b0 >> 1)].decode('latin1', 'ignore')
    flags = d[0x20:0x28].hex()
    lines.append(f'[{i:4d}] {name:52s} f@0x20={flags}')

path = os.path.join(OUT, 'athlete_props_full.txt')
with open(path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print(f'wrote {path}')

for pat in ('weekendPushRewardsHaveGotten', 'hallTeamData', 'timerRefreshMSToken',
            'monthPayRebateSpecialAwardInfo'):
    hits = [l for l in lines if pat in l]
    print(f'{pat}: {hits if hits else "NOT FOUND"}')
