import struct
import capstone

arm64_so = r'c:\Users\Raysoo\Downloads\ROS_RE\03_lib\libclient_arm64.so'
with open(arm64_so, 'rb') as f:
    elf_data = f.read()

# Let's find all occurrences of "entities\\loginapp.pubkey"
pubkey_str = b"entities\\loginapp.pubkey"
idx = elf_data.find(pubkey_str)
print(f"pubkey_str at {hex(idx)}")

# In ARM64, strings in .rodata are referenced via ADRP + ADD or ADRP + LDR
# Let's search for references to idx in the text section!
# Text section is from 0x7a3000 to 0x221ec80 approx
# Let's find references by searching ADRP to page (idx & ~0xfff) and ADD with (idx & 0xfff)
target_page = idx & ~0xfff
target_off = idx & 0xfff

print(f"Target page: {hex(target_page)}, target_off: {hex(target_off)}")

# Let's also check ARM32 libclient.so where literal pools are used (much easier to find pointer to string)
arm32_so = r'c:\Users\Raysoo\Downloads\ROS_RE\01_apk\base_decompiled\lib\armeabi-v7a\libclient.so'
with open(arm32_so, 'rb') as f:
    elf_data32 = f.read()

idx32 = elf_data32.find(pubkey_str)
print(f"pubkey_str in ARM32 at {hex(idx32)}")

# In ARM32, find all 4-byte occurrences of idx32 in the file:
ptr_bytes = struct.pack('<I', idx32)
pos = 0
found_ptrs = []
while True:
    p = elf_data32.find(ptr_bytes, pos)
    if p == -1:
        break
    found_ptrs.append(p)
    pos = p + 4
print(f"Pointers to pubkey_str in ARM32 ({len(found_ptrs)}): {[hex(p) for p in found_ptrs]}")

# For each pointer, let's see which function references it
for p in found_ptrs:
    print(f"\nDisassembling around pool pointer at {hex(p)}:")
    # Disassemble 100 bytes before the pool entry
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    start = max(0, p - 80)
    code = elf_data32[start:p]
    for ins in md.disasm(code, start):
        print(f"  {hex(ins.address)}: {ins.mnemonic} {ins.op_str}")
