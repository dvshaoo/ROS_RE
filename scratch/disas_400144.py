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

code_off = 0x400144
insns_size = struct.unpack_from('<I', dex, code_off + 12)[0]
insns_start = code_off + 16
i = insns_start
end = insns_start + insns_size * 2
print(f'Disassembling 0x{code_off:x}, size {insns_size} words:')
while i < end:
    op = dex[i]
    sz = 2
    desc = f'op 0x{op:02x}'
    if op == 0x0e: desc = 'return-void'
    elif op == 0x0f: desc = f'return v{dex[i+1]}'
    elif op == 0x11: desc = f'return-object v{dex[i+1]}'
    elif op == 0x12: desc = f'const/4 v{dex[i+1]&0xf}, {dex[i+1]>>4}'
    elif op == 0x13:
        val = struct.unpack_from('<h', dex, i+2)[0]
        desc = f'const/16 v{dex[i+1]}, {val}'
        sz = 4
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
    elif op in (0x38, 0x39):
        offset = struct.unpack_from('<h', dex, i+2)[0] * 2
        desc = f'if-testz 0x{op:x} v{dex[i+1]}, target=0x{i+offset:x}'
        sz = 4
    elif op in (0x32, 0x33, 0x34, 0x35, 0x36, 0x37):
        offset = struct.unpack_from('<h', dex, i+2)[0] * 2
        desc = f'if-test 0x{op:x} target=0x{i+offset:x}'
        sz = 4
    elif op == 0x28:
        offset = struct.unpack_from('<b', dex, i+1)[0] * 2
        desc = f'goto target=0x{i+offset:x}'
    print(f'  [0x{i:04x}] {desc}')
    i += sz
