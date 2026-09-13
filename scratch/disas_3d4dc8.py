import struct

dex = open(r'02_dex\classes.dex', 'rb').read()
string_ids_off = 112
type_ids_off = 175856
field_ids_off = 307664
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

def get_field(idx):
    class_idx = struct.unpack_from('<H', dex, field_ids_off + idx * 8)[0]
    name_idx = struct.unpack_from('<I', dex, field_ids_off + idx * 8 + 4)[0]
    return f'{get_type(class_idx)}->{get_str(name_idx)}'

i = 0x3d4dc8 + 16
end = i + 80
while i < end:
    op = dex[i]
    sz = 2
    desc = f'op 0x{op:02x}'
    if op == 0x0e: desc = 'return-void'
    elif op == 0x11: desc = f'return-object v{dex[i+1]}'
    elif op == 0x1a:
        s_idx = struct.unpack_from('<H', dex, i+2)[0]
        desc = f'const-string v{dex[i+1]}, "{get_str(s_idx)}"'
        sz = 4
    elif op in (0x52, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5b, 0x5c):
        f_idx = struct.unpack_from('<H', dex, i+2)[0]
        desc = f'i-op 0x{op:x} {get_field(f_idx)}'
        sz = 4
    elif op in (0x6e, 0x6f, 0x70, 0x71, 0x72):
        m_idx = struct.unpack_from('<H', dex, i+2)[0]
        desc = f'invoke 0x{op:x} {get_method(m_idx)}'
        sz = 6
    print(f'  [0x{i:04x}] {desc}')
    i += sz
