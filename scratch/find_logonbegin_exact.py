import struct
import capstone

arm64_so = r'c:\Users\Raysoo\Downloads\ROS_RE\03_lib\libclient_arm64.so'
with open(arm64_so, 'rb') as f:
    elf_data = f.read()

# Strings to find:
# 1. 0x2a492f2: "ServerConnection::logOnBegin ALREADY_ONLINE_LOCALLY" (offset 0x2f2)
# 2. 0x2a49326: "ServerConnection::logOnBegin: server:%s username:%s" (offset 0x326)
# 3. 0x2a49364: "ServerConnection::logOnBegin conneting to %s for loginAPP" (offset 0x364)
# 4. 0x2a4939e: "entities\\loginapp.pubkey" (offset 0x39e)
# 5. 0x2a493b8: "ServerConnection::logOnBegin PUBLIC_KEY_LOOKUP_FAILED" (offset 0x3b8)

# Let's search for ADRP to 0x2a49000 followed by ADD with offsets 0x2f2, 0x326, 0x364, 0x39e, 0x3b8
# In ARM64: ADD (immediate) is 0x11000000 | (imm12 << 10) | (Rn << 5) | Rd

def decode_add_imm(ins_bytes):
    val = struct.unpack('<I', ins_bytes)[0]
    if (val & 0xffc00000) in (0x91000000, 0x11000000): # 64-bit or 32-bit ADD imm
        rd = val & 0x1f
        rn = (val >> 5) & 0x1f
        imm12 = (val >> 10) & 0xfff
        sh = (val >> 22) & 1
        if sh:
            imm12 <<= 12
        return rd, rn, imm12
    return None, None, None

def decode_adrp(ins_bytes, pc):
    val = struct.unpack('<I', ins_bytes)[0]
    if (val & 0x9f000000) != 0x90000000:
        return None, None
    rd = val & 0x1f
    immlo = (val >> 29) & 0x3
    immhi = (val >> 5) & 0x7ffff
    imm = (immhi << 2) | immlo
    if imm & (1 << 20):
        imm -= (1 << 21)
    target_page = (pc & ~0xfff) + (imm << 12)
    return rd, target_page

md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)

print("Scanning for logOnBegin instructions...")
for pc in range(0x7a3000, 0x221e000, 4):
    rd_adrp, target = decode_adrp(elf_data[pc:pc+4], pc)
    if target == 0x2a49000:
        # Check next few instructions for ADD with rn == rd_adrp
        for next_pc in range(pc+4, pc+20, 4):
            rd_add, rn_add, imm12 = decode_add_imm(elf_data[next_pc:next_pc+4])
            if rn_add == rd_adrp and imm12 in (0x2f2, 0x30b, 0x326, 0x364, 0x39e, 0x3b8, 0x3ee, 0x429, 0x442, 0x464):
                print(f"Match at {hex(pc)}: imm12={hex(imm12)}")
                # Disassemble surrounding 40 instructions
                start_disas = max(0x7a3000, pc - 40)
                code = elf_data[start_disas:pc+100]
                for ins in md.disasm(code, start_disas):
                    print(f"  {hex(ins.address)}: {ins.mnemonic} {ins.op_str}")
                print("-" * 50)
