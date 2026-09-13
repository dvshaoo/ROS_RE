import struct
from dexdis import *

# Find method index of 0x400464
cdo = class_cdo('Lcom/netease/mpay/oversea/ui/g;')
pos = cdo
nsf, pos = ruleb(pos); nif, pos = ruleb(pos); ndm, pos = ruleb(pos); nvm, pos = ruleb(pos)
for _ in range(nsf + nif):
    _, pos = ruleb(pos); _, pos = ruleb(pos)
last = 0
target_midx = None
for idx in range(ndm):
    d, pos = ruleb(pos); last += d; acc, pos = ruleb(pos); code, pos = ruleb(pos)
    if code == 0x400464:
        print(f"Direct method #{idx}: {gm(last)} is target! midx={last}")
        target_midx = last
        break

if target_midx:
    tb = struct.pack('<H', target_midx)
    for p in range(0x300000, len(data)-6, 2):
        if data[p] in (0x6e, 0x6f, 0x70, 0x71, 0x72):
            if data[p+2:p+4] == tb:
                print(f"  Called at 0x{p:x}")
