import struct
from dexdis import *

# Find type index of Lcom/netease/mpay/oversea/ui/g$2;
tn = struct.unpack_from('<I', data, 0x40)[0]; toff = struct.unpack_from('<I', data, 0x44)[0]
ti = None
target_name = 'Lcom/netease/mpay/oversea/ui/g$2;'
for i in range(tn):
    if gs(struct.unpack_from('<I', data, toff + i * 4)[0]) == target_name:
        ti = i; break

print(f"Type index of {target_name}: {ti}")
target_bytes = struct.pack('<H', ti)
for pos in range(0x300000, len(data)-4, 2):
    if data[pos] == 0x22: # new-instance
        if data[pos+2:pos+4] == target_bytes:
            print(f"  new-instance at 0x{pos:x}")
