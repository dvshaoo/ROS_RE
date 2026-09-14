import capstone

arm64_so = r'c:\Users\Raysoo\Downloads\ROS_RE\03_lib\libclient_arm64.so'
with open(arm64_so, 'rb') as f:
    elf_data = f.read()

md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
code = elf_data[0x996f50:0x997000]
for ins in md.disasm(code, 0x996f50):
    print(f"  {hex(ins.address)}: {ins.mnemonic} {ins.op_str}")
