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
    ci, pi, ni = struct.unpack_from('<HHI', data, MOFF + last * 8)
    mname = gs(ni)
    if code:
        print(f"MpayActivity #{idx}: {mname} at 0x{code:x}")
