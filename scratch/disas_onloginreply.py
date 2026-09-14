import capstone
import struct

arm64_so = r'c:\Users\Raysoo\Downloads\ROS_RE\03_lib\libclient_arm64.so'
with open(arm64_so, 'rb') as f:
    elf_data = f.read()

# Let's find "LoginHandler::onLoginReply: change baseAddr from %s to %s"
# at 0x2a49000 + 0x113 (or nearby)
s = b"LoginHandler::onLoginReply: change baseAddr"
idx = elf_data.find(s)
print(f"onLoginReply string at {hex(idx)}")

target_page = idx & ~0xfff
target_off = idx & 0xfff

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

for pc in range(0x7a3000, 0x221e000, 4):
    rd, target = decode_adrp(elf_data[pc:pc+4], pc)
    if target == target_page:
        add_bytes = elf_data[pc+4:pc+8]
        val = struct.unpack('<I', add_bytes)[0]
        if (val & 0xffc00000) in (0x91000000, 0x11000000):
            imm12 = (val >> 10) & 0xfff
            if imm12 == target_off:
                print(f"Found onLoginReply ref at {hex(pc)}")
                code = elf_data[pc-60:pc+140]
                for ins in md.disasm(code, pc-60):
                    print(f"  {hex(ins.address)}: {ins.mnemonic} {ins.op_str}")
