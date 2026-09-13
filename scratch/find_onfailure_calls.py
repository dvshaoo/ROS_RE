import struct

dex = open(r'02_dex\classes.dex', 'rb').read()
type_ids_off = 175856
string_ids_off = 112
method_ids_off = 558112

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

def get_method(idx):
    class_idx = struct.unpack_from('<H', dex, method_ids_off + idx * 8)[0]
    name_idx = struct.unpack_from('<I', dex, method_ids_off + idx * 8 + 4)[0]
    return f'{get_type(class_idx)}->{get_str(name_idx)}'

method_ids_size = struct.unpack_from('<I', dex, 88)[0]
target_methods = []
for i in range(method_ids_size):
    m = get_method(i)
    if 'MpayLoginCallback;->onFailure' in m:
        print(f'Method #{i}: {m}')
        target_methods.append(i)

for m_idx in target_methods:
    tb = struct.pack('<H', m_idx)
    for pos in range(0x300000, len(dex)-6, 2):
        if dex[pos] in (0x6e, 0x6f, 0x70, 0x71, 0x72): # invoke-*
            if dex[pos+2:pos+4] == tb:
                print(f'  Invoked at 0x{pos:x} (op 0x{dex[pos]:02x})')
