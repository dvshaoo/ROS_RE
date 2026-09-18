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

def read_pystring(va, maxlen=200):
    # va points at the START of the PyStringObject (ob_refcnt field)
    if not in_window(va):
        return None
    off = va_to_off(va)
    if off < 0 or off + 40 > len(data):
        return None
    ob_size = struct.unpack_from('<q', data, off + 16)[0]
    if ob_size < 0 or ob_size > maxlen:
        return None
    text_off = off + 40
    if text_off + ob_size > len(data):
        return None
    raw = data[text_off:text_off + ob_size]
    try:
        return raw.decode('latin1')
    except Exception:
        return repr(raw)

def read_pytuple_of_strings(va, maxitems=80):
    # PyTupleObject: ob_refcnt(8) ob_type(8) ob_size(8) ob_item[0](8)...
    if not in_window(va):
        return None
    off = va_to_off(va)
    if off < 0 or off + 24 > len(data):
        return None
    ob_size = struct.unpack_from('<q', data, off + 16)[0]
    if ob_size < 0 or ob_size > maxitems:
        return None
    items = []
    base = off + 24
    if base + ob_size * 8 > len(data):
        return None
    for i in range(ob_size):
        ptr = struct.unpack_from('<Q', data, base + i * 8)[0]
        s = read_pystring(ptr)
        items.append(s if s is not None else '0x%x' % ptr)
    return items

targets = [b'Athlete.py', b'iWeekendPush.py']
HEADER_LEN = 40

for t in targets:
    print("=" * 20, t.decode(), "=" * 20)
    idx = 0
    while True:
        idx = data.find(t, idx)
        if idx == -1:
            break
        text_va = WINDOW_BASE_VA + idx
        obj_va = text_va - HEADER_LEN
        pattern = struct.pack('<Q', obj_va)
        pidx = 0
        while True:
            pidx = data.find(pattern, pidx)
            if pidx == -1:
                break
            ref_va = WINDOW_BASE_VA + pidx
            code_obj_va = ref_va - 80  # co_filename is at offset +80 in PyCodeObject
            co_name_ptr = read_u64(code_obj_va + 88)
            co_names_ptr = read_u64(code_obj_va + 48)
            co_firstlineno = None
            off = va_to_off(code_obj_va + 92 + 8)  # co_firstlineno after co_lnotab? recompute below
            fn_name = read_pystring(co_name_ptr) if co_name_ptr else None
            names_tuple = read_pytuple_of_strings(co_names_ptr) if co_names_ptr else None
            if fn_name:
                print("code_obj_va=0x%x  co_name=%r" % (code_obj_va, fn_name))
                if names_tuple:
                    print("    co_names=%r" % (names_tuple,))
            pidx += 1
        idx += 1
