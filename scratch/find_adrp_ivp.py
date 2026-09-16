import struct
# Search for adrp/add pointing to 0x2a4a379
target = 0x2a4a379
page = target & ~0xfff

lib_path = r'c:\Users\Raysoo\Downloads\ROS_RE\01_apk\base_decompiled\lib\arm64-v8a\libclient.so'
with open(lib_path, 'rb') as f:
    data = f.read()

# Scan code section for references to page 0x2a4a000
for i in range(0x500000, 0x1500000, 4):
    insn = struct.unpack('<I', data[i:i+4])[0]
    # Check if ADRP
    if (insn & 0x9f000000) == 0x90000000:
        immlo = (insn >> 29) & 3
        immhi = (insn >> 5) & 0x7ffff
        imm = (immhi << 2) | immlo
        if imm & (1 << 20):
            imm -= (1 << 21)
        pc_page = (i) & ~0xfff
        dest_page = pc_page + (imm << 12)
        if dest_page == page:
            # Check next instruction for ADD with low 12 bits
            next_insn = struct.unpack('<I', data[i+4:i+8])[0]
            if (next_insn & 0xffc00000) == 0x91000000: # ADD immediate
                imm12 = (next_insn >> 10) & 0xfff
                if (dest_page + imm12) == target:
                    print("Found ref to identifyVersionPoint at 0x%x" % i)
