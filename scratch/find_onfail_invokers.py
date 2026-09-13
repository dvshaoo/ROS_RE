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

# Find method_id for SdkNeteaseGlobal$LoginCallback->onFailure
method_ids_size = struct.unpack_from("<I", data, 0x58)[0]
method_ids_off = struct.unpack_from("<I", data, 0x5c)[0]

target_methods = []
for i in range(method_ids_size):
    cls_name, m_name = get_method(i)
    if "LoginCallback" in cls_name and "onFailure" in m_name:
        print(f"Target method id {i} (0x{i:04x}): {cls_name}->{m_name}")
        target_methods.append(i)
    elif "Mpay" in cls_name and "onFailure" in m_name:
        print(f"Target method id {i} (0x{i:04x}): {cls_name}->{m_name}")
        target_methods.append(i)

