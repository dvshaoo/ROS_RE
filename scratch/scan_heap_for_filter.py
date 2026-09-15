import os, struct

HEAP_DIR = r"C:\Users\Raysoo\Downloads\ROS_RE\scratch\heap_dump"
LIBCLIENT_BASE = 0x03310000  # from /proc/9754/maps, first libclient.so segment (file offset 0)
VTABLE_FILE_ADDR = 0x37dd3a0  # EncryptionFilter vtable, per FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md
TARGET_VA = LIBCLIENT_BASE + VTABLE_FILE_ADDR
print("Target EncryptionFilter vtable VA: 0x%x" % TARGET_VA)
pattern = struct.pack('<Q', TARGET_VA)
print("8-byte LE pattern:", pattern.hex())

results = []
for fn in sorted(os.listdir(HEAP_DIR)):
    if not fn.startswith('region_') or not fn.endswith('.bin'):
        continue
    region_base = int(fn[len('region_'):-len('.bin')], 16)
    path = os.path.join(HEAP_DIR, fn)
    with open(path, 'rb') as f:
        data = f.read()
    idx = 0
    while True:
        idx = data.find(pattern, idx)
        if idx == -1:
            break
        obj_va = region_base + idx
        results.append((obj_va, path, idx))
        idx += 1

print("Found %d candidate EncryptionFilter objects" % len(results))
for obj_va, path, off in results:
    print("  candidate object VA=0x%x  file=%s offset=0x%x" % (obj_va, path, off))
