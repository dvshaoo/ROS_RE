import struct

data = open('02_dex/classes.dex', 'rb').read()
string_ids_size = struct.unpack_from('<I', data, 0x38)[0]
string_ids_off = struct.unpack_from('<I', data, 0x3c)[0]
method_ids_size = struct.unpack_from('<I', data, 0x58)[0]
method_ids_off = struct.unpack_from('<I', data, 0x5c)[0]

print(f"string_ids_size: {string_ids_size}")
print(f"method_ids_size: {method_ids_size}")

def get_str(idx):
    if idx >= string_ids_size: return f"<invalid_str_{idx}>"
    off = struct.unpack_from('<I', data, string_ids_off + idx * 4)[0]
    p = off
    ln = 0; sh = 0
    while True:
        b = data[p]; p += 1; ln |= (b & 0x7f) << sh
        if not (b & 0x80): break
        shift = 7
    return data[p:p+ln].decode('utf-8', errors='replace')

# Look at method 0 to 10
for i in range(10):
    ci, pi, ni = struct.unpack_from('<HHI', data, method_ids_off + i * 8)
    print(f"method #{i}: ci={ci}, pi={pi}, ni={ni} -> name={get_str(ni)}")
