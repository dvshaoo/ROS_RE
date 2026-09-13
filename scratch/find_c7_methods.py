import struct

dex = open(r'02_dex\classes.dex', 'rb').read()
string_ids_off = 112
type_ids_off = 175856
field_ids_off = 307664
method_ids_off = 558112
class_defs_size = 5323
class_defs_off = 863488

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

def get_field(idx):
    class_idx = struct.unpack_from('<H', dex, field_ids_off + idx * 8)[0]
    name_idx = struct.unpack_from('<I', dex, field_ids_off + idx * 8 + 4)[0]
    return f'{get_type(class_idx)}->{get_str(name_idx)}'

def read_uleb128(data, off):
    res = 0; shift = 0
    while True:
        b = data[off]; off += 1
        res |= (b & 0x7f) << shift
        if not (b & 0x80): break
        shift += 7
    return res, off

# Find Lcom/netease/mpay/oversea/h/c/c$7; methods
for c_i in range(class_defs_size):
    c_off = class_defs_off + c_i * 32
    class_idx = struct.unpack_from('<I', dex, c_off)[0]
    if get_type(class_idx) == 'Lcom/netease/mpay/oversea/h/c/c$7;':
        class_data_off = struct.unpack_from('<I', dex, c_off + 24)[0]
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
            m_name = get_method(m_idx)
            print(f'Method {m_name} at code_off=0x{code_off:x}')
