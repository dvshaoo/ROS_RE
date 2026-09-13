import struct

dex = open(r'02_dex\classes.dex', 'rb').read()
type_ids_off = 175856
string_ids_off = 112
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
    return get_str(struct.unpack_from('<I', dex, type_ids_off + idx * 4)[0])

target = 'Lcom/netease/mpay/oversea/h/a/b;'
for i in range(struct.unpack_from('<I', dex, 64)[0]): # type_ids_size
    if get_type(i) == target:
        print(f'Found type {target} at type_idx={i}')
        # Find usages
        target_bytes = struct.pack('<H', i)
        for pos in range(0, len(dex)-4, 2):
            if dex[pos] in (0x1c, 0x1f, 0x22): # const-class, check-cast, new-instance
                if dex[pos+2:pos+4] == target_bytes:
                    print(f'  Instantiated/referenced at 0x{pos:x}')
