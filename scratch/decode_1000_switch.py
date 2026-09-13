import struct

dex = open(r'02_dex\classes.dex', 'rb').read()

# at 0x40017a: packed-switch vX, table_offset
# opcode 0x2b, vX = dex[0x40017b], table_offset = int32 at 0x40017c
offset = struct.unpack_from('<i', dex, 0x40017c)[0] * 2
table_addr = 0x40017a + offset
ident = struct.unpack_from('<H', dex, table_addr)[0]
size = struct.unpack_from('<H', dex, table_addr + 2)[0]
first_key = struct.unpack_from('<i', dex, table_addr + 4)[0]

print(f'packed-switch table at 0x{table_addr:x}: ident=0x{ident:x}, size={size}, first_key={first_key}')
for k in range(size):
    target_off = struct.unpack_from('<i', dex, table_addr + 8 + k * 4)[0] * 2
    target_addr = 0x40017a + target_off
    print(f'  key {first_key + k} -> target 0x{target_addr:x}')
