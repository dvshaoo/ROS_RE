import struct

arm32_so = r'c:\Users\Raysoo\Downloads\ROS_RE\01_apk\base_decompiled\lib\armeabi-v7a\libclient.so'
with open(arm32_so, 'rb') as f:
    elf_data = f.read()

# Let's calculate the global variable address at 0x13777f2
# PC at 0x13777f8 is 0x13777f8 + 4 = 0x13777fc
# In Thumb mode: PC is current instruction address + 4
pc = 0x13777f2 + 4
# offset at pc + 0xb4
offset_location = (0x13777f2 & ~3) + 4 + 0xb4 # thumb PC relative load is typically ((PC & ~3) + imm)
# Let's check the exact bytes around 0x13777f2 + 0xb4 + 4
target_ptr = struct.unpack('<I', elf_data[0x13777f2 + 4 + 0xb4 : 0x13777f2 + 4 + 0xb4 + 4])[0]
print(f"Target ptr in pool: {hex(target_ptr)}")

# Add PC (0x13777f8 + 4 = 0x13777fc)
global_var_addr = (0x13777f8 + 4) + target_ptr
print(f"Global var addr: {hex(global_var_addr)}")

# In ELF, let's see which section global_var_addr falls into, and read its value if static or BSS
print(f"Searching for string references to 'ntOnLogin' or 'on_login' or 'OnLogin' across the whole binary...")
for s in [b'ntOnLogin', b'onLogin', b'on_login', b'channelLogin', b'ntOnInitSdk', b'ntOnLogout']:
    pos = 0
    while True:
        idx = elf_data.find(s, pos)
        if idx == -1:
            break
        print(f"  Found '{s.decode()}' at {hex(idx)}")
        pos = idx + len(s)
