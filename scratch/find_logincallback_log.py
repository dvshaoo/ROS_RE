import struct

dex = open('02_dex/classes.dex', 'rb').read()
string_ids_off = struct.unpack_from('<I', dex, 0x3c)[0]
string_ids_size = struct.unpack_from('<I', dex, 0x38)[0]

def gs(i):
    off = struct.unpack_from('<I', dex, string_ids_off + i * 4)[0]
    p = off; ln = 0; sh = 0
    while True:
        b = dex[p]; p += 1; ln |= (b & 0x7f) << sh
        if not (b & 0x80): break
        sh += 7
    return dex[p:p+ln].decode('utf-8', errors='replace')

# Look for string "MpayLoginCallback.onFailure"
s_idx = None
for i in range(string_ids_size):
    s = gs(i)
    if 'MpayLoginCallback.onFailure' in s:
        print(f"Found MpayLoginCallback.onFailure string #{i}")
        s_idx = i

if s_idx:
    tb = struct.pack('<H', s_idx)
    for pos in range(0x300000, len(dex)-4, 2):
        if dex[pos] in (0x1a, 0x1b): # const-string
            if dex[pos+2:pos+4] == tb:
                print(f"  const-string at 0x{pos:x}")
