import capstone
import struct

arm64_so = r'c:\Users\Raysoo\Downloads\ROS_RE\03_lib\libclient_arm64.so'
with open(arm64_so, 'rb') as f:
    elf_data = f.read()

# In ARM64:
# "ServerConnection::logOnBegin conneting to %s for loginAPP" is at 0x2a49364
# "entities\\loginapp.pubkey" is at 0x2a4939e
# "ServerConnection::logOnBegin PUBLIC_KEY_LOOKUP_FAILED" is at 0x2a493b8

# Let's search all ADRP instructions that target 0x2a49000
# In ARM64: ADRP instruction encoding:
# bits [31]: 1
# bits [30:29]: immlo
# bits [28:24]: 10000 (0x10)
# bits [23:5]: immhi
# bits [4:0]: Rd

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

print("Scanning ARM64 text section for ADRP targeting 0x2a49000...")
# text section is around 0x7a3000 to 0x221e000
matches = []
for pc in range(0x7a3000, 0x221e000, 4):
    rd, target = decode_adrp(elf_data[pc:pc+4], pc)
    if target == 0x2a49000:
        matches.append((pc, rd))

print(f"Found {len(matches)} ADRP targeting 0x2a49000:")
md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
for pc, rd in matches:
    # Disassemble 12 instructions starting at pc
    code = elf_data[pc:pc+48]
    print(f"\n--- At {hex(pc)} (Rd=x{rd}) ---")
    for ins in md.disasm(code, pc):
        print(f"  {hex(ins.address)}: {ins.mnemonic} {ins.op_str}")
