import struct
from dexdis import *

code_off = 0x43886c
ins = struct.unpack_from('<I', data, code_off + 12)[0]
start = code_off + 16
u = 0
print(f"=== DISASSEMBLY OF Lcom/netease/ntunisdk/SdkNeteaseGlobal$LoginCallback;->onFailure at 0x{code_off:x} ===")
while u < ins:
    op = data[start + u * 2]
    wd = w(op)
    raw = data[start + u * 2:start + u * 2 + wd * 2]
    extra = ''
    try:
        if op == 0x1a:
            si = raw[2] | (raw[3] << 8); extra = 'STR ' + repr(gs(si))
        elif op == 0x1c:
            ti = raw[2] | (raw[3] << 8); extra = 'TYPE ' + gt(ti)
        elif 0x52 <= op <= 0x6d:
            fi = raw[2] | (raw[3] << 8)
            sec = 0x54 if op <= 0x5f else 0x50
            extra = 'FIELD ' + gf(fi, sec, 8)
        elif 0x6e <= op <= 0x78 and op != 0x73:
            mi = raw[2] | (raw[3] << 8); extra = 'METH ' + gm(mi)
        elif op == 0x1f:
            ti = struct.unpack('<H', raw[2:4])[0]; extra = 'TYPE ' + gt(ti)
        elif op in (0x38, 0x39):
            offset = struct.unpack('<h', raw[2:4])[0] * 2
            extra = f'target=0x{start + u*2 + offset:x}'
        elif op in (0x32, 0x33, 0x34, 0x35, 0x36, 0x37):
            offset = struct.unpack('<h', raw[2:4])[0] * 2
            extra = f'target=0x{start + u*2 + offset:x}'
        elif op == 0x28:
            offset = struct.unpack('<b', raw[1:2])[0] * 2
            extra = f'target=0x{start + u*2 + offset:x}'
    except Exception as e:
        extra = 'ERR ' + str(e)
    print('%5x (0x%04x) op=%02x %s %s' % (u * 2, start + u * 2, op, raw.hex(), extra))
    u += wd
