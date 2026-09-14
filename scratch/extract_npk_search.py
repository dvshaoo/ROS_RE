import struct, zlib, os

p = r'C:\Users\Raysoo\Downloads\ROS_RE\04_obb\extracted\script.npk'
data = open(p, 'rb').read()
idx_off = 0x308e54c
count = 3959

OUT = r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\npk_extract'
os.makedirs(OUT, exist_ok=True)

hits = []
for i in range(count):
    off = idx_off + i * 28
    h, o, sc, so, v1, v2, flag = struct.unpack_from('<7I', data, off)
    raw = data[o:o+sc]
    content = None
    if sc != so:
        try:
            content = zlib.decompress(raw)
        except Exception:
            try:
                content = zlib.decompress(raw, -15)
            except Exception:
                content = None
    if content is None:
        content = raw
    if b'total_list' in content or b'ResourcePatcher' in content or b'patch_size_calc' in content:
        hits.append((i, h, o, sc, so, content))
        fn = os.path.join(OUT, f'hit_{i}_{h:08x}.bin')
        with open(fn, 'wb') as f:
            f.write(content)
        print(f'HIT idx={i} hash={h:08x} off={o} sc={sc} so={so} -> {fn} ({len(content)} bytes)')

print('total hits:', len(hits))
