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

target_method_id = 23773 # Lcom/netease/mpay/oversea/MpayLoginCallback;->onFailure
# invoke-interface is 0x72 or invoke-interface/range is 0x78
# format: 72 BA CC CC ... where CCCC is method_id
# or invoke-virtual: 0x6e, 0x74
print(f"Target method: {get_method(target_method_id)}")

target_bytes_lo = target_method_id & 0xff
target_bytes_hi = target_method_id >> 8

callers = []
for i in range(len(data) - 4):
    op = data[i]
    if op in (0x6e, 0x6f, 0x70, 0x71, 0x72, 0x74, 0x75, 0x76, 0x77, 0x78):
        # 16-bit method index is at i+2, i+3
        if data[i+2] == target_bytes_lo and data[i+3] == target_bytes_hi:
            callers.append((hex(i), hex(op)))

print(f"Found {len(callers)} call sites: {callers}")

# Find which class/method contains each call site
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

class_defs_size, class_defs_off = struct.unpack_from("<II", data, 0x60)
for site_str, op_str in callers:
    site = int(site_str, 16)
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
        for _ in range(static_fields_size + instance_fields_size):
            _, pos = read_uleb128(pos)
            _, pos = read_uleb128(pos)
        last_m = 0
        for _ in range(direct_methods_size + virtual_methods_size):
            m_diff, pos = read_uleb128(pos)
            last_m += m_diff
            acc, pos = read_uleb128(pos)
            code_off, pos = read_uleb128(pos)
            if code_off > 0:
                insns_size = struct.unpack_from("<I", data, code_off + 12)[0]
                start = code_off + 16
                end = start + insns_size * 2
                if start <= site < end:
                    cls_name, m_name = get_method(last_m)
                    print(f"Site {site_str} inside {cls_name}->{m_name}")
