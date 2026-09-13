import struct
from dexdis import *

cdo = class_cdo('Lcom/netease/mpay/oversea/MpayActivity;')
pos = cdo
nsf, pos = ruleb(pos); nif, pos = ruleb(pos); ndm, pos = ruleb(pos); nvm, pos = ruleb(pos)
for _ in range(nsf + nif):
    _, pos = ruleb(pos); _, pos = ruleb(pos)
last = 0
for idx in range(ndm + nvm):
    d, pos = ruleb(pos); last += d; acc, pos = ruleb(pos); code, pos = ruleb(pos)
    name = gm(last)
    if code:
        ins = struct.unpack_from('<I', data, code + 12)[0]
        start = code + 16
        print(f"MpayActivity Method #{idx}: {name} code_off=0x{code:x} [0x{start:x} - 0x{start+ins*2:x}]")
