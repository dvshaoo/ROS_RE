import struct, os

os.makedirs('06_notes/MPAY_AUTH_FLOW', exist_ok=True)
dex = open(r'02_dex\classes.dex', 'rb').read()

type_ids_off = 175856
string_ids_off = 112
class_defs_size = 5323
class_defs_off = 863488
method_ids_off = 558112
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

def get_method(idx):
    class_idx = struct.unpack_from('<H', dex, method_ids_off + idx * 8)[0]
    name_idx = struct.unpack_from('<I', dex, method_ids_off + idx * 8 + 4)[0]
    return f'{get_type(class_idx)}->{get_str(name_idx)}'

def get_field(idx):
    class_idx = struct.unpack_from('<H', dex, field_ids_off + idx * 8)[0]
    name_idx = struct.unpack_from('<I', dex, field_ids_off + idx * 8 + 4)[0]
    return f'{get_type(class_idx)}->{get_str(name_idx)}'

def read_uleb128(data, off):
    res = 0; shift = 0
    while True:
        b = data[off]; off += 1
        res |= (b & 0x7f) << shift
        if not (b & 0x80): break
        shift += 7
    return res, off

def disas_range(start, end):
    lines = []
    i = start
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
        lines.append(f'  [0x{i:04x}] {desc}')
        i += sz
    return '\n'.join(lines)

# Target key ranges
targets = {
    '01_login_response_parser_0x3c8f8c.txt': (0x3c8f8c+16, 0x3c8f8c+16+334*2),
    '02_post_login_branch_and_onLoginSuccess_0x3ff840.txt': (0x3ff840, 0x3ff9b0),
    '03_cancel_login_callback_1000_0x3ffbb4.txt': (0x3ffbb4, 0x3ffc68),
    '04_status_code_mapping_to_1000_0x400144.txt': (0x400144, 0x4001d6),
    '05_minor_status_query_handler_0x3ccee0.txt': (0x3ccee0, 0x3ccfe4),
    '06_sdk_token_login_v2_parser_0x3d34bc.txt': (0x3d34bc, 0x3d3500),
    '07_sdk_token_login_callback_0x3d4ce8.txt': (0x3d4ce8, 0x3d4d74),
}

for fname, (s, e) in targets.items():
    content = disas_range(s, e)
    with open(os.path.join('06_notes/MPAY_AUTH_FLOW', fname), 'w', encoding='utf-8') as f:
        f.write(content)
print("Dumped key auth flows successfully.")
