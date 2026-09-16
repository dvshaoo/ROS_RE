import capstone

cs = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)

lib_path = r'c:\Users\Raysoo\Downloads\ROS_RE\01_apk\base_decompiled\lib\arm64-v8a\libclient.so'
with open(lib_path, 'rb') as f:
    data = f.read()

# Search for any store to [..., #0x140] in 0x900000 to 0x9a0000
for i in range(0x900000, 0x9a0000, 4):
    insn_bytes = data[i:i+4]
    for ins in cs.disasm(insn_bytes, i):
        if '0x140' in ins.op_str and ins.mnemonic.startswith('st'):
            print("0x%x: %s %s" % (ins.address, ins.mnemonic, ins.op_str))
