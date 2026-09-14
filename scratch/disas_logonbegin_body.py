import capstone

arm64_so = r'c:\Users\Raysoo\Downloads\ROS_RE\03_lib\libclient_arm64.so'
with open(arm64_so, 'rb') as f:
    elf_data = f.read()

# Let's search backward from 0x93c100 to find the function entry
# Functions typically start with:
# sub sp, sp, #imm
# stp x29, x30, [sp, #imm]
# add x29, sp, #imm

md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
# Let's disassemble from 0x93be00 to 0x93c400
code = elf_data[0x93be00:0x93c450]
insns = list(md.disasm(code, 0x93be00))

# Find the function entry point
entry = None
for ins in insns:
    # A common prologue in this file
    if ins.mnemonic == 'sub' and ins.op_str.startswith('sp, sp,'):
        entry = ins.address
    elif ins.mnemonic == 'stp' and 'x29, x30' in ins.op_str:
        if entry is None or ins.address - entry < 16:
            func_start = entry if entry else ins.address
            print(f"Candidate function start: {hex(func_start)}")

# Let's disassemble from 0x93bf00 to 0x93c200
print("\n--- Disassembly of logOnBegin main body ---")
for ins in insns:
    if 0x93bf90 <= ins.address <= 0x93c200:
        print(f"  {hex(ins.address)}: {ins.mnemonic} {ins.op_str}")
