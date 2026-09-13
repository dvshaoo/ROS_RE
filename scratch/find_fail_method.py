import struct

dex_path = r"c:\Users\Raysoo\Downloads\ROS_RE\02_dex\classes.dex"
data = open(dex_path, "rb").read()

def get_string(idx):
    string_ids_off = struct.unpack_from("<I", data, 0x3c)[0]
    str_off = struct.unpack_from("<I", data, string_ids_off + idx * 4)[0]
    pos = str_off
    length = 0
    shift = 0
    while True:
        b = data[pos]
        pos += 1
        length |= (b & 0x7f) << shift
        if not (b & 0x80):
            break
        shift += 7
    return data[pos:pos+length].decode('utf-8', errors='replace')

def get_type(idx):
    type_ids_off = struct.unpack_from("<I", data, 0x44)[0]
    str_idx = struct.unpack_from("<I", data, type_ids_off + idx * 4)[0]
    return get_string(str_idx)

def get_method(idx):
    method_ids_off = struct.unpack_from("<I", data, 0x5c)[0]
    class_idx, proto_idx, name_idx = struct.unpack_from("<HHI", data, method_ids_off + idx * 8)
    return get_type(class_idx), get_string(name_idx)

class_defs_size, class_defs_off = struct.unpack_from("<II", data, 0x60)
print(f"class_defs: {class_defs_size}")

target_pc = 0x4388a4

# In dex, code items are in data section. A code item has:
# ushort registers_size
# ushort ins_size
# ushort outs_size
# ushort tries_size
# uint debug_info_off
# uint insns_size
# ushort insns[insns_size]

# Let's find which class_def has class_data_item with a direct/virtual method whose code_off contains target_pc
def read_uleb128(pos):
    val = 0
    shift = 0
    while True:
        b = data[pos]
        pos += 1
        val |= (b & 0x7f) << shift
        if not (b & 0x80):
            break
        shift += 7
    return val, pos

found = False
for c_i in range(class_defs_size):
    c_off = class_defs_off + c_i * 32
    class_idx, access_flags, superclass_idx, interfaces_off, source_file_idx, annotations_off, class_data_off, static_values_off = struct.unpack_from("<IIIIIIII", data, c_off)
    if class_data_off == 0:
        continue
    pos = class_data_off
    static_fields_size, pos = read_uleb128(pos)
    instance_fields_size, pos = read_uleb128(pos)
    direct_methods_size, pos = read_uleb128(pos)
    virtual_methods_size, pos = read_uleb128(pos)
    
    # skip fields
    for _ in range(static_fields_size):
        _, pos = read_uleb128(pos)
        _, pos = read_uleb128(pos)
    for _ in range(instance_fields_size):
        _, pos = read_uleb128(pos)
        _, pos = read_uleb128(pos)
        
    # direct methods
    last_m_idx = 0
    for _ in range(direct_methods_size):
        m_diff, pos = read_uleb128(pos)
        last_m_idx += m_diff
        acc, pos = read_uleb128(pos)
        code_off, pos = read_uleb128(pos)
        if code_off > 0:
            insns_size = struct.unpack_from("<I", data, code_off + 12)[0]
            start = code_off + 16
            end = start + insns_size * 2
            if start <= target_pc < end:
                cls_name, m_name = get_method(last_m_idx)
                print(f"FOUND in direct method: {cls_name}->{m_name}, code range [{hex(start)}, {hex(end)}]")
                found = True
                break
    if found:
        break
        
    last_m_idx = 0
    for _ in range(virtual_methods_size):
        m_diff, pos = read_uleb128(pos)
        last_m_idx += m_diff
        acc, pos = read_uleb128(pos)
        code_off, pos = read_uleb128(pos)
        if code_off > 0:
            insns_size = struct.unpack_from("<I", data, code_off + 12)[0]
            start = code_off + 16
            end = start + insns_size * 2
            if start <= target_pc < end:
                cls_name, m_name = get_method(last_m_idx)
                print(f"FOUND in virtual method: {cls_name}->{m_name}, code range [{hex(start)}, {hex(end)}]")
                found = True
                break
    if found:
        break
