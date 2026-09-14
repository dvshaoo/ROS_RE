import capstone

arm64_so = r'c:\Users\Raysoo\Downloads\ROS_RE\03_lib\libclient_arm64.so'
with open(arm64_so, 'rb') as f:
    elf_data = f.read()

# Let's search for BL instructions targeting 0x94e22c
# In ARM64: BL instruction is 0x94000000 | (imm26 & 0x03ffffff)
# imm26 = (target - pc) >> 2
target = 0x94e22c
callers = []
for pc in range(0x7a3000, 0x221e000, 4):
    ins = elf_data[pc:pc+4]
    val = int.from_bytes(ins, 'little')
    if (val & 0xfc000000) == 0x94000000: # BL
        imm26 = val & 0x03ffffff
        if imm26 & (1 << 25):
            imm26 -= (1 << 26)
        dest = pc + (imm26 << 2)
        if dest == target:
            callers.append(pc)

print(f"Found {len(callers)} callers to 0x94e22c:")
md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
for c in callers:
    print(f"  Caller at {hex(c)}")
    # Disassemble 10 instructions before and after caller
    start = max(0x7a3000, c - 32)
    code = elf_data[start:c+36]
    for ins in md.disasm(code, start):
        prefix = "==>" if ins.address == c else "   "
        print(f"  {prefix} {hex(ins.address)}: {ins.mnemonic} {ins.op_str}")
