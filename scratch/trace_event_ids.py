import struct
import capstone

arm32_so = r'c:\Users\Raysoo\Downloads\ROS_RE\01_apk\base_decompiled\lib\armeabi-v7a\libclient.so'
with open(arm32_so, 'rb') as f:
    elf_data = f.read()

# Let's inspect JNI methods in ARM32:
methods = [
    ("NativeOnInitSdk", 0x1377651),
    ("NativeOnLeaveSdk", 0x137771d),
    ("NativeOnLogin", 0x13777e9),
    ("NativeOnLogout", 0x13778b5),
]

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
for name, addr in methods:
    code = elf_data[addr & ~1 : (addr & ~1) + 80]
    print(f"\n--- {name} at {hex(addr)} ---")
    for ins in md.disasm(code, addr & ~1):
        print(f"  {hex(ins.address)}: {ins.mnemonic} {ins.op_str}")
        if ins.mnemonic == 'blx' and ins.op_str == 'r6':
            break
