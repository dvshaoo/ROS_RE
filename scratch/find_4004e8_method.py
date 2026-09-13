import struct
from dexdis import *

target = 0x4004e8
cn, coff = struct.unpack_from('<II', data, 0x60)
for ci in range(cn):
    co = coff + ci * 32
    cidx = struct.unpack_from('<I', data, co)[0]
    cdo = struct.unpack_from('<I', data, co + 24)[0]
    if not cdo: continue
    pos = cdo
    nsf, pos = ruleb(pos); nif, pos = ruleb(pos); ndm, pos = ruleb(pos); nvm, pos = ruleb(pos)
    for _ in range(nsf + nif):
        _, pos = ruleb(pos); _, pos = ruleb(pos)
    last = 0
    for idx in range(ndm):
        d, pos = ruleb(pos); last += d; acc, pos = ruleb(pos); code, pos = ruleb(pos)
        if code:
            ins = struct.unpack_from('<I', data, code + 12)[0]
            start = code + 16
            if start <= target < start + ins * 2:
                print(f"Direct method #{idx}: {gm(last)} (Class {gt(cidx)}) at code 0x{code:x}")
    last = 0
    for idx in range(nvm):
        d, pos = ruleb(pos); last += d; acc, pos = ruleb(pos); code, pos = ruleb(pos)
        if code:
            ins = struct.unpack_from('<I', data, code + 12)[0]
            start = code + 16
            if start <= target < start + ins * 2:
                print(f"Virtual method #{idx}: {gm(last)} (Class {gt(cidx)}) at code 0x{code:x}")
