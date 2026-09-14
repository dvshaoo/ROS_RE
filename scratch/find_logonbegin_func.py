import capstone

arm64_so = r'c:\Users\Raysoo\Downloads\ROS_RE\03_lib\libclient_arm64.so'
with open(arm64_so, 'rb') as f:
    elf_data = f.read()

# Let's search backward from 0x94e2bc for a standard ARM64 function prologue
# like `stp x29, x30, [sp, ...]` or `sub sp, sp, ...`
start = 0x94e2bc
while start > 0x94d000:
    # Check for STP x29, x30 or sub sp, sp
    ins = elf_data[start:start+4]
    # STP x29, x30, [sp, ...] is commonly 0xa9b... or 0xa9a...
    # Let's disassemble backwards
    start -= 4

md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
# Let's disassemble from 0x94d500 to 0x94e500
code = elf_data[0x94d800:0x94e600]
insns = list(md.disasm(code, 0x94d800))

print(f"Disassembled {len(insns)} instructions around 0x94e2bc:")
# Print instructions around 0x94e2bc
for ins in insns:
    if 0x94e200 <= ins.address <= 0x94e350:
        print(f"  {hex(ins.address)}: {ins.mnemonic} {ins.op_str}")
