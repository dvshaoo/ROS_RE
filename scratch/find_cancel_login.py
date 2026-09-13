import struct

dex = open(r'02_dex\classes.dex', 'rb').read()
string_ids_off = 112
string_ids_size = struct.unpack_from('<I', dex, 56)[0]

def get_str(idx):
    off = struct.unpack_from('<I', dex, string_ids_off + idx * 4)[0]
    p = off
    while dex[p] & 0x80: p += 1
    p += 1
    end = dex.find(b'\x00', p)
    return dex[p:end].decode('latin1', errors='replace')

for i in range(string_ids_size):
    s = get_str(i)
    if 'cancel' in s.lower() and 'login' in s.lower():
        print(f'String #{i}: "{s}"')

# Also search for 1000 literal instructions (const/16 vx, 1000)
# const/16 has opcode 0x13, format: 13 AA BB BB
# 1000 is 0x03e8 -> BB BB = e8 03
print("\nSearching for const/16 vx, 1000 (0x03e8):")
for pos in range(0, len(dex)-4, 2):
    if dex[pos] == 0x13 and dex[pos+2:pos+4] == b'\xe8\x03':
        print(f'  const/16 at 0x{pos:x}')
