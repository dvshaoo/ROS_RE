import capstone

cs = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)

lib_path = r'c:\Users\Raysoo\Downloads\ROS_RE\01_apk\base_decompiled\lib\arm64-v8a\libclient.so'
with open(lib_path, 'rb') as f:
    data = f.read()

target = 0x938e04
for i in range(0x800000, 0xa00000, 4):
    insn_bytes = data[i:i+4]
    for ins in cs.disasm(insn_bytes, i):
        if ins.mnemonic == 'bl' and hex(target) in ins.op_str:
            print("Found call to 0x938e04 at 0x%x: %s %s" % (ins.address, ins.mnemonic, ins.op_str))
