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

class_defs_size, class_defs_off = struct.unpack_from("<II", data, 0x60)
for c_i in range(class_defs_size):
    c_off = class_defs_off + c_i * 32
    class_idx, access_flags, superclass_idx, interfaces_off, source_file_idx, annotations_off, class_data_off, static_values_off = struct.unpack_from("<IIIIIIII", data, c_off)
    cls_name = get_type(class_idx)
    if "SdkNeteaseGlobal$LoginCallback" in cls_name:
        super_name = get_type(superclass_idx) if superclass_idx != 0xffffffff else "None"
        interfaces = []
        if interfaces_off > 0:
            size = struct.unpack_from("<I", data, interfaces_off)[0]
            for j in range(size):
                t_idx = struct.unpack_from("<H", data, interfaces_off + 4 + j * 2)[0]
                interfaces.append(get_type(t_idx))
        print(f"Class: {cls_name}")
        print(f"Super: {super_name}")
        print(f"Interfaces: {interfaces}")

