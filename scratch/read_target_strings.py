arm64_so = r'c:\Users\Raysoo\Downloads\ROS_RE\03_lib\libclient_arm64.so'
with open(arm64_so, 'rb') as f:
    elf_data = f.read()

offsets = [0x3ee, 0x39e, 0x3b8, 0x475, 0x4c3, 0xbcb, 0xcd8, 0xd44, 0xd85, 0xdb0, 0xdf0, 0xe63, 0xe8e, 0xed7, 0xf28, 0xf5f, 0xfcf]
for off in offsets:
    addr = 0x2a49000 + off
    end = elf_data.find(b'\x00', addr)
    s = elf_data[addr:end].decode('ascii', errors='ignore')
    print(f"0x{addr:x}: {s}")
