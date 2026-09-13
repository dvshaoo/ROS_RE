import struct

dex_path = r"c:\Users\Raysoo\Downloads\ROS_RE\02_dex\classes.dex"
data = open(dex_path, "rb").read()

# Dex header
string_ids_size, string_ids_off = struct.unpack_from("<II", data, 0x38)
print(f"string_ids: {string_ids_size} at {hex(string_ids_off)}")

target_str = b"-onFailure, code=%d, msg=%s, minor_status=%d"
target_idx = -1

for i in range(string_ids_size):
    str_off = struct.unpack_from("<I", data, string_ids_off + i * 4)[0]
    # parse uleb128 length
    # then bytes
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
    s = data[pos:pos+length]
    if target_str in s:
        target_idx = i
        print(f"Found target string at string_id {i}: {s}")
        break

if target_idx != -1:
    print(f"Searching for bytecode instructions referencing string_id {target_idx} (0x{target_idx:04x})...")
    # const-string is opcode 0x1a (16-bit idx), const-string/jumbo is 0x1b (32-bit idx)
    # Let's find occurrences of [1a, target_idx & 0xff, target_idx >> 8]
    op1 = bytes([0x1a, target_idx & 0xff, target_idx >> 8])
    for idx in range(0, len(data) - 3):
        if data[idx:idx+2] == bytes([0x1a, 0]) or data[idx] == 0x1a:
            # check opcode format: 1a AA BB BB (AA = reg, BBBB = string index)
            if data[idx] == 0x1a and data[idx+2] == (target_idx & 0xff) and data[idx+3] == (target_idx >> 8):
                print(f"Found const-string at {hex(idx)} (reg v{data[idx+1]})")
