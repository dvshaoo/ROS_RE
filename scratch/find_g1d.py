import struct

dex = open(r'02_dex\classes.dex', 'rb').read()
type_ids_off = 175856
string_ids_off = 112
field_ids_off = 307664

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

def get_field(idx):
    class_idx = struct.unpack_from('<H', dex, field_ids_off + idx * 8)[0]
    name_idx = struct.unpack_from('<I', dex, field_ids_off + idx * 8 + 4)[0]
    return f'{get_type(class_idx)}->{get_str(name_idx)}'

field_ids_size = struct.unpack_from('<I', dex, 72)[0]
target_f_idx = None
for i in range(field_ids_size):
    f_str = get_field(i)
    if 'Lcom/netease/mpay/oversea/ui/g$1;->d' in f_str:
        print(f'Found field #{i}: {f_str}')
        target_f_idx = i

if target_f_idx is not None:
    tb = struct.pack('<H', target_f_idx)
    for pos in range(0, len(dex)-4, 2):
        if dex[pos] in (0x59, 0x5c): # iput-boolean
            if dex[pos+2:pos+4] == tb:
                print(f'  iput at 0x{pos:x}')
