import struct

dex = open(r'02_dex\classes.dex', 'rb').read()
type_ids_off = 175856
string_ids_off = 112
class_defs_size = 5323
class_defs_off = 863488
method_ids_off = 558112

def get_str(idx):
    off = struct.unpack_from('<I', dex, string_ids_off + idx * 4)[0]
    p = off
    while dex[p] & 0x80: p += 1
    p += 1
    end = dex.find(b'\x00', p)
    return dex[p:end].decode('latin1', errors='replace')

def get_type(idx):
    descriptor_idx = struct.unpack_from('<I', dex, type_ids_off + idx * 4)[0]
    return get_str(descriptor_idx)

def get_method(idx):
    class_idx = struct.unpack_from('<H', dex, method_ids_off + idx * 8)[0]
    name_idx = struct.unpack_from('<I', dex, method_ids_off + idx * 8 + 4)[0]
    return f'{get_type(class_idx)}->{get_str(name_idx)}'

def read_uleb128(data, off):
    res = 0; shift = 0
    while True:
        b = data[off]; off += 1
        res |= (b & 0x7f) << shift
        if not (b & 0x80): break
        shift += 7
    return res, off

targets = [0x1e1a1c, 0x1e2454]
for c_i in range(class_defs_size):
    c_off = class_defs_off + c_i * 32
    class_idx = struct.unpack_from('<I', dex, c_off)[0]
    class_data_off = struct.unpack_from('<I', dex, c_off + 24)[0]
    if not class_data_off: continue
    off = class_data_off
    sf, off = read_uleb128(dex, off); inf, off = read_uleb128(dex, off)
    dm, off = read_uleb128(dex, off); vm, off = read_uleb128(dex, off)
    for _ in range(sf + inf):
        _, off = read_uleb128(dex, off); _, off = read_uleb128(dex, off)
    m_idx = 0
    for _ in range(dm + vm):
        m_diff, off = read_uleb128(dex, off); m_idx += m_diff
        _, off = read_uleb128(dex, off)
        code_off, off = read_uleb128(dex, off)
        if code_off:
            insns_size = struct.unpack_from('<I', dex, code_off + 12)[0]
            insns_start = code_off + 16
            insns_end = insns_start + insns_size * 2
            for t in targets:
                if insns_start <= t < insns_end:
                    print(f'Target 0x{t:x}: Class={get_type(class_idx)} code_off=0x{code_off:x}')
