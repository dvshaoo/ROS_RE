import capstone
import struct

p = r'c:\Users\Raysoo\Downloads\ROS_RE\03_lib\libclient_arm64.so'
data = open(p, 'rb').read()

TEXT_START = 0x809200
TEXT_END = 0x809200 + 0x222f464

def decode_adrp(word, pc):
    if (word & 0x9f000000) != 0x90000000:
        return None, None
    rd = word & 0x1f
    immlo = (word >> 29) & 0x3
    immhi = (word >> 5) & 0x7ffff
    imm = (immhi << 2) | immlo
    if imm & (1 << 20):
        imm -= (1 << 21)
    page = (pc & ~0xfff) + (imm << 12)
    return rd, page

def find_xrefs(target_addr, label):
    target_page = target_addr & ~0xfff
    target_off = target_addr & 0xfff
    hits = []
    for pc in range(TEXT_START, TEXT_END, 4):
        word = struct.unpack('<I', data[pc:pc+4])[0]
        rd, page = decode_adrp(word, pc)
        if page != target_page:
            continue
        # check next few instructions for add xN, xN, #imm12 matching target_off, with same reg
        for off in (4,):
            w2 = struct.unpack('<I', data[pc+off:pc+off+4])[0]
            if (w2 & 0xffc00000) == 0x91000000:  # ADD (immediate) 64-bit
                rd2 = w2 & 0x1f
                rn2 = (w2 >> 5) & 0x1f
                imm12 = (w2 >> 10) & 0xfff
                if rn2 == rd and imm12 == target_off:
                    hits.append(pc)
    print(f"{label}: {len(hits)} xrefs")
    for h in hits:
        print(f"  {hex(h)}")
    return hits

hits1 = find_xrefs(0x2a62d6a, "LogOnParams::addToStream publicEncrypt failed")
hits2 = find_xrefs(0x2a62d9a, "LogOnParams::readFromStream privateDecrypt failed")

md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
for h in hits1 + hits2:
    print(f"\n--- context around {hex(h)} ---")
    lo = h - 200
    code = data[lo:h+40]
    for ins in md.disasm(code, lo):
        marker = " <==" if ins.address == h else ""
        print(f"  {hex(ins.address)}: {ins.mnemonic} {ins.op_str}{marker}")
