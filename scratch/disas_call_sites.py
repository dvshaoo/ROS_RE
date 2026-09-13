import struct
from dexdis import *

call_sites = [0x3ff8b6, 0x3ff95c, 0x3ff9fa, 0x3ffc2a, 0x400348, 0x40063a]

for addr in call_sites:
    start = addr - 32
    end = addr + 16
    ins_slice = (end - start) // 2
    u = 0
    print(f"\n==================== Call site at 0x{addr:x} ====================")
    while start + u * 2 < end:
        curr = start + u * 2
        op = data[curr]
        wd = w(op)
        raw = data[curr:curr + wd * 2]
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
            elif op == 0x13:
                val = struct.unpack('<h', raw[2:4])[0]
                extra = f'CONST {val}'
        except Exception as e:
            extra = 'ERR ' + str(e)
        marker = '>>> ' if curr == addr else '    '
        print('%s0x%04x op=%02x %s %s' % (marker, curr, op, raw.hex(), extra))
        u += wd
