import struct

data = open('02_dex/classes.dex', 'rb').read()
string_ids_size = struct.unpack_from('<I', data, 0x38)[0]
string_ids_off = struct.unpack_from('<I', data, 0x3c)[0]
type_ids_size = struct.unpack_from('<I', data, 0x40)[0]
type_ids_off = struct.unpack_from('<I', data, 0x44)[0]
method_ids_size = struct.unpack_from('<I', data, 0x58)[0]
method_ids_off = struct.unpack_from('<I', data, 0x5c)[0]
class_defs_size = struct.unpack_from('<I', data, 0x60)[0]
class_defs_off = struct.unpack_from('<I', data, 0x64)[0]

def gs(idx):
    if idx >= string_ids_size: return f"<invalid_str_{idx}>"
    off = struct.unpack_from('<I', data, string_ids_off + idx * 4)[0]
    p = off; ln = 0; sh = 0
    while True:
        b = data[p]; p += 1; ln |= (b & 0x7f) << sh
        if not (b & 0x80): break
        sh += 7
    return data[p:p+ln].decode('utf-8', errors='replace')

def gt(idx):
    if idx >= type_ids_size: return f"<invalid_type_{idx}>"
    return gs(struct.unpack_from('<I', data, type_ids_off + idx * 4)[0])

def gm(idx):
    if idx >= method_ids_size: return f"<invalid_method_{idx}>"
    ci, pi, ni = struct.unpack_from('<HHI', data, method_ids_off + idx * 8)
    return f"{gt(ci)}->{gs(ni)}"

def ruleb(pos):
    v = 0; sh = 0
    while True:
        b = data[pos]; pos += 1; v |= (b & 0x7f) << sh
        if not (b & 0x80): break
        sh += 7
    return v, pos

# Find MpayActivity class
for ci in range(class_defs_size):
    co = class_defs_off + ci * 32
    class_idx = struct.unpack_from('<I', data, co)[0]
    cname = gt(class_idx)
    if cname == 'Lcom/netease/mpay/oversea/MpayActivity;':
        cdo = struct.unpack_from('<I', data, co + 24)[0]
        pos = cdo
        nsf, pos = ruleb(pos); nif, pos = ruleb(pos); ndm, pos = ruleb(pos); nvm, pos = ruleb(pos)
        for _ in range(nsf + nif):
            _, pos = ruleb(pos); _, pos = ruleb(pos)
        last = 0
        for idx in range(ndm):
            d, pos = ruleb(pos); last += d; acc, pos = ruleb(pos); code, pos = ruleb(pos)
            print(f"Direct #{idx}: {gm(last)} at code=0x{code:x}")
        last = 0
        for idx in range(nvm):
            d, pos = ruleb(pos); last += d; acc, pos = ruleb(pos); code, pos = ruleb(pos)
            print(f"Virtual #{idx}: {gm(last)} at code=0x{code:x}")
