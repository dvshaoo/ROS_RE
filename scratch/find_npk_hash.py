"""Find the hash used for NXPK member signatures using known (sig, path) pairs from script.npk (scratch/mobile_script_filemap.txt)."""
import zlib, re, struct

BS = chr(92)
M = 0xffffffff
pairs = []
for l in open(r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\mobile_script_filemap.txt', encoding='utf-8'):
    m = re.match(r'0x([0-9a-f]+) idx=.*? ([^ ]+\.py)\s*$', l)
    if m:
        pairs.append((int(m.group(1), 16), m.group(2)))


def fnv1a(s):
    h = 0x811c9dc5
    for c in s:
        h = ((h ^ c) * 0x01000193) & M
    return h


def fnv1(s):
    h = 0x811c9dc5
    for c in s:
        h = ((h * 0x01000193) & M) ^ c
    return h


def djb2(s):
    h = 5381
    for c in s:
        h = (h * 33 + c) & M
    return h


def sdbm(s):
    h = 0
    for c in s:
        h = (c + (h << 6) + (h << 16) - h) & M
    return h


def oat(s):
    h = 0
    for c in s:
        h = (h + c) & M
        h = (h + (h << 10)) & M
        h ^= h >> 6
    h = (h + (h << 3)) & M
    h ^= h >> 11
    return (h + (h << 15)) & M


def murmur(s, seed=0):
    c1, c2 = 0xcc9e2d51, 0x1b873593
    h = seed
    n = len(s)
    for i in range(0, n - n % 4, 4):
        k = struct.unpack_from('<I', s, i)[0]
        k = (k * c1) & M
        k = ((k << 15) | (k >> 17)) & M
        k = (k * c2) & M
        h ^= k
        h = ((h << 13) | (h >> 19)) & M
        h = (h * 5 + 0xe6546b64) & M
    t = s[n - n % 4:]
    k = 0
    for i, c in enumerate(t):
        k |= c << (8 * i)
    if t:
        k = (k * c1) & M
        k = ((k << 15) | (k >> 17)) & M
        k = (k * c2) & M
        h ^= k
    h ^= n
    h ^= h >> 16
    h = (h * 0x85ebca6b) & M
    h ^= h >> 13
    h = (h * 0xc2b2ae35) & M
    h ^= h >> 16
    return h


def bkdr(s, seed=131):
    h = 0
    for c in s:
        h = (h * seed + c) & M
    return h


FUNCS = {'crc32': lambda s: zlib.crc32(s) & M, 'adler': lambda s: zlib.adler32(s) & M, 'fnv1a': fnv1a, 'fnv1': fnv1,
         'djb2': djb2, 'sdbm': sdbm, 'oat': oat, 'murmur': murmur, 'bkdr131': bkdr, 'bkdr31': lambda s: bkdr(s, 31),
         'bkdr33': lambda s: bkdr(s, 33)}


def variants(n):
    out = [n, n.replace(BS, '/'), n.lower(), n.lower().replace(BS, '/'), n.upper()]
    out += [x[:-3] for x in out if x.endswith('.py')]
    out += [x + 'c' for x in out[:5]] + [x + 'o' for x in out[:5]]
    return out


if __name__ == '__main__':
    print(len(pairs), 'known pairs')
    for sig, name in pairs[:5]:
        for v in variants(name):
            for fn, f in FUNCS.items():
                if f(v.encode()) == sig:
                    print('MATCH', fn, repr(v), hex(sig))
    print('done')
