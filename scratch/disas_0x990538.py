import capstone

cs = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)

lib_path = r'c:\Users\Raysoo\Downloads\ROS_RE\01_apk\base_decompiled\lib\arm64-v8a\libclient.so'
with open(lib_path, 'rb') as f:
    f.seek(0x990538)
    code = f.read(0x60)

for insn in cs.disasm(code, 0x990538):
    print("0x%x: %s %s" % (insn.address, insn.mnemonic, insn.op_str))
