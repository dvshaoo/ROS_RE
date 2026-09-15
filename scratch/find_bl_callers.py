import struct, sys
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\scratch')
from xref_lib import DATA, TEXT_START, TEXT_END

def find_bl_callers(target):
    hits = []
    for pc in range(TEXT_START, TEXT_END, 4):
        word = struct.unpack('<I', DATA[pc:pc+4])[0]
        if (word & 0xfc000000) == 0x94000000:  # BL
            imm26 = word & 0x3ffffff
            if imm26 & (1 << 25):
                imm26 -= (1 << 26)
            target_addr = pc + (imm26 << 2)
            if target_addr == target:
                hits.append(pc)
    return hits

for name, addr in [("addToStream(0x9d8014)", 0x9d8014), ("0x93c720", 0x93c720), ("readFromStream(0x9d838c)", 0x9d838c)]:
    hits = find_bl_callers(addr)
    print(name, "callers:", [hex(h) for h in hits])
