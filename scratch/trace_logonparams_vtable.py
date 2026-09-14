import struct
import capstone

arm64_so = r'c:\Users\Raysoo\Downloads\ROS_RE\03_lib\libclient_arm64.so'
with open(arm64_so, 'rb') as f:
    elf_data = f.read()

# Find "N4neox8bwclient11LogOnParamsE"
s = b"N4neox8bwclient11LogOnParamsE"
idx = elf_data.find(s)
print(f"LogOnParams RTTI name at: {hex(idx)}")

# In ARM64, typeinfo struct starts with vtable pointer for typeinfo, then pointer to name string
# Search for pointer to idx
idx_bytes = struct.pack('<Q', idx)
pos = 0
found_ti = []
while True:
    p = elf_data.find(idx_bytes, pos)
    if p == -1:
        break
    found_ti.append(p)
    pos = p + 8
print(f"Typeinfo pointers to name ({len(found_ti)}): {[hex(p) for p in found_ti]}")

# For each typeinfo, find pointer to typeinfo (which is in vtable at index -1)
for ti in found_ti:
    ti_addr = ti - 8 # start of typeinfo
    print(f"Typeinfo at {hex(ti_addr)}")
    ti_bytes = struct.pack('<Q', ti_addr)
    pos = 0
    found_vt = []
    while True:
        p = elf_data.find(ti_bytes, pos)
        if p == -1:
            break
        found_vt.append(p)
        pos = p + 8
    print(f"  Vtable pointers to typeinfo ({len(found_vt)}): {[hex(p) for p in found_vt]}")
    for vt in found_vt:
        # Vtable methods start right after typeinfo pointer: vt + 8
        print(f"    Vtable methods at {hex(vt + 8)}:")
        for i in range(10):
            fn_ptr = struct.unpack('<Q', elf_data[vt + 8 + i*8 : vt + 8 + (i+1)*8])[0]
            print(f"      [{i}] {hex(fn_ptr)}")
