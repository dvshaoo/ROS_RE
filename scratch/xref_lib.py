import struct
import capstone

SO_PATH = r'c:\Users\Raysoo\Downloads\ROS_RE\03_lib\libclient_arm64.so'
DATA = open(SO_PATH, 'rb').read()
TEXT_START = 0x809200
TEXT_END = 0x809200 + 0x222f464
MD = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)

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

def xrefs(target_addr, max_off=20):
    """find adrp Xd,#page ... add Xd,Xd,#off  OR  ldr Xd,[Xd,#off] within max_off bytes"""
    target_page = target_addr & ~0xfff
    target_off = target_addr & 0xfff
    hits = []
    for pc in range(TEXT_START, TEXT_END, 4):
        word = struct.unpack('<I', DATA[pc:pc+4])[0]
        rd, page = decode_adrp(word, pc)
        if page != target_page:
            continue
        for off in range(4, max_off, 4):
            w2 = struct.unpack('<I', DATA[pc+off:pc+off+4])[0]
            if (w2 & 0xffc00000) == 0x91000000:  # ADD imm 64-bit
                rd2 = w2 & 0x1f
                rn2 = (w2 >> 5) & 0x1f
                imm12 = (w2 >> 10) & 0xfff
                if rn2 == rd and imm12 == target_off:
                    hits.append(pc)
                    break
    return hits

def find_str(s):
    idx = DATA.find(s)
    return idx

def disasm_range(start, end, mark=None):
    out = []
    for ins in MD.disasm(DATA[start:end], start):
        marker = " <==" if mark is not None and ins.address == mark else ""
        out.append(f"{hex(ins.address)}: {ins.mnemonic} {ins.op_str}{marker}")
    return out

def print_disasm(start, end, mark=None):
    for line in disasm_range(start, end, mark):
        print(line)

def find_prologue_before(addr, window=0x3000):
    """scan backward for stp x29,x30,[sp,#imm] (non pre-indexed) pattern"""
    hits = []
    for pc in range(addr, max(TEXT_START, addr - window), -4):
        code = DATA[pc:pc+4]
        for ins in MD.disasm(code, pc):
            if ins.mnemonic == 'stp' and ins.op_str.startswith('x29, x30, [sp'):
                hits.append(pc)
    return hits
