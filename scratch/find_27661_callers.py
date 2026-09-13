import struct

dex = open(r'02_dex\classes.dex', 'rb').read()
target = struct.pack('<H', 27661)

print('Callers of method 27661 (Lcom/netease/mpay/oversea/ui/g;->a(I)I):')
for pos in range(0, len(dex)-6, 2):
    if dex[pos] in (0x6e, 0x71): # invoke-virtual, invoke-static
        if dex[pos+2:pos+4] == target:
            print(f'  invoke at 0x{pos:x}')
