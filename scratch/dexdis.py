import struct, sys
DEX = r'C:\Users\Raysoo\Downloads\ROS_RE\02_dex\classes.dex'
data = open(DEX, 'rb').read()
NS = struct.unpack_from('<I', data, 0x38)[0]
def gs(i):
    if i < 0 or i >= NS: return '?str%d?' % i
    off = struct.unpack_from('<I', data, struct.unpack_from('<I', data, 0x3c)[0] + i * 4)[0]
    p = off; ln = 0; sh = 0
    while True:
        b = data[p]; p += 1; ln |= (b & 0x7f) << sh
        if not (b & 0x80): break
        sh += 7
    return data[p:p + ln].decode('utf-8', errors='replace')
def gt(i):
    return gs(struct.unpack_from('<I', data, struct.unpack_from('<I', data, 0x44)[0] + i * 4)[0])
MN = struct.unpack_from('<I', data, 0x58)[0]; MOFF = struct.unpack_from('<I', data, 0x5c)[0]
def gm(i):
    ci, pi, ni = struct.unpack_from('<HHI', data, MOFF + i * 8)
    return gt(ci) + '->' + gs(ni)
def gf(i, sec, sz):
    noff = struct.unpack_from('<I', data, sec)[0]
    ci, ti, ni = struct.unpack_from('<HHI', data, noff + i * sz)
    return gt(ci) + '::' + gs(ni) + ' : ' + gt(ti)
WIDTH = {0x1a: 2, 0x1b: 3, 0x1c: 2, 0x1f: 3, 0x16: 2, 0x17: 3, 0x18: 5, 0x19: 3,
         0x13: 2, 0x14: 3, 0x24: 3, 0x25: 3, 0x26: 3, 0x27: 1}
def w(op):
    if op in WIDTH: return WIDTH[op]
    if 0x6e <= op <= 0x72 or 0x74 <= op <= 0x78: return 3
    if op == 0x28: return 1
    if op == 0x29: return 2
    if op == 0x2a: return 3
    if 0x60 <= op <= 0x6d or 0x52 <= op <= 0x5f or 0x44 <= op <= 0x51 or 0x20 <= op <= 0x23: return 2
    if 0x32 <= op <= 0x3d: return 2
    if 0x2b <= op <= 0x2d: return 3
    if op in (0x1d, 0x1e): return 2
    return 1
def ruleb(pos):
    v = 0; sh = 0
    while True:
        b = data[pos]; pos += 1; v |= (b & 0x7f) << sh
        if not (b & 0x80): break
        sh += 7
    return v, pos
def class_cdo(tname):
    tn = struct.unpack_from('<I', data, 0x40)[0]; toff = struct.unpack_from('<I', data, 0x44)[0]
    ti = None
    for i in range(tn):
        if gs(struct.unpack_from('<I', data, toff + i * 4)[0]) == tname:
            ti = i; break
    if ti is None: print('NO-TYPE', tname); return None
    cn, coff = struct.unpack_from('<II', data, 0x60)
    for ci in range(cn):
        co = coff + ci * 32
        cidx = struct.unpack_from('<I', data, co)[0]
        if cidx == ti:
            return struct.unpack_from('<I', data, co + 24)[0]
    print('NO-CLASS', tname); return None
def dump(tname, only=None):
    cdo = class_cdo(tname)
    if cdo is None: return
    pos = cdo
    nsf, pos = ruleb(pos); nif, pos = ruleb(pos); ndm, pos = ruleb(pos); nvm, pos = ruleb(pos)
    print('CLASS', tname, 'sfields', nsf, 'ifields', nif, 'dmethods', ndm, 'vmethods', nvm)
    for _ in range(nsf + nif):
        _, pos = ruleb(pos); _, pos = ruleb(pos)
    last = 0
    for _ in range(ndm + nvm):
        d, pos = ruleb(pos); last += d; acc, pos = ruleb(pos); code, pos = ruleb(pos)
        name = gm(last)
        short = name.split('->')[-1]
        if only and short not in only: continue
        print('=' * 100); print('METHOD', name, 'code', hex(code) if code else 0)
        if not code: continue
        ins = struct.unpack_from('<I', data, code + 12)[0]
        start = code + 16; u = 0
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
                elif op == 0x14:
                    extra = 'CONST ' + repr(gs(raw[2] | (raw[3] << 8)))
            except Exception as e:
                extra = 'ERR ' + str(e)
            print('%5x op=%02x %s %s' % (u * 2, op, raw.hex(), extra))
            u += wd
if __name__ == '__main__':
    dump(sys.argv[1], sys.argv[2:])
