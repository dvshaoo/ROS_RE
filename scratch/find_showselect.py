import struct

WINDOW_PATH = r"C:\Users\Raysoo\Downloads\ROS_RE\scratch\heap_dump_2\window_athlete.bin"
WINDOW_BASE_VA = 0x7638501d4a80
WINDOW_END_VA = WINDOW_BASE_VA + 40051290

with open(WINDOW_PATH, 'rb') as f:
    data = f.read()

def va_to_off(va):
    return va - WINDOW_BASE_VA

def in_window(va):
    return WINDOW_BASE_VA <= va < WINDOW_END_VA

def read_u64(va):
    off = va_to_off(va)
    if off < 0 or off + 8 > len(data):
        return None
    return struct.unpack_from('<Q', data, off)[0]

def read_pystring(va, maxlen=300):
    if not in_window(va):
        return None
    off = va_to_off(va)
    if off < 0 or off + 40 > len(data):
        return None
    ob_size = struct.unpack_from('<q', data, off + 16)[0]
    if ob_size < 0 or ob_size > maxlen:
        return None
    text_off = off + 40
    if text_off + ob_size > len(data) or text_off < 0:
        return None
    raw = data[text_off:text_off + ob_size]
    try:
        s = raw.decode('latin1')
        if all(32 <= ord(c) < 127 or c in '\n\t' for c in s):
            return s
    except Exception:
        pass
    return None

# 1. find raw occurrences of showSelectCharacter
idx = 0
occ = []
while True:
    idx = data.find(b'showSelectCharacter', idx)
    if idx == -1:
        break
    occ.append(idx)
    idx += 1
print("raw occurrences in window:", [hex(WINDOW_BASE_VA + o) for o in occ])

HEADER_LEN = 40
for text_off in occ:
    text_va = WINDOW_BASE_VA + text_off
    obj_va = text_va - HEADER_LEN
    print()
    print("=== showSelectCharacter string object candidate obj_va=0x%x ===" % obj_va)
    pattern = struct.pack('<Q', obj_va)
    pidx = 0
    refs = []
    while True:
        pidx = data.find(pattern, pidx)
        if pidx == -1:
            break
        refs.append(pidx)
        pidx += 1
    print("referenced by %d pointer(s) in window" % len(refs))
    for r in refs:
        ref_va = WINDOW_BASE_VA + r
        print("  ref at VA=0x%x" % ref_va)
        # dump the surrounding qwords to inspect structure context
        base_off = r - 96
        for k in range(0, 25):
            off_k = base_off + k * 8
            if 0 <= off_k < len(data) - 8:
                val = struct.unpack_from('<Q', data, off_k)[0]
                rel = (off_k - r)
                marker = '  <-- REF' if rel == 0 else ''
                s = read_pystring(val)
                print("    rel=%4d VA=0x%x val=0x%016x %s%s" % (rel, WINDOW_BASE_VA + off_k, val, ('str=%r' % s) if s else '', marker))
