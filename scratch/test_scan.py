import subprocess
import time
import struct
import base64

ADB = r'C:\LDPlayer\LDPlayer9\adb.exe'
pid = '18007'

# Calculate base
maps = subprocess.run([ADB, '-s', 'emulator-5554', 'shell', 'su', '0', 'cat', f'/proc/{pid}/maps'], capture_output=True).stdout.decode()
base = None
for l in maps.splitlines():
    if 'libclient.so' in l and '00000000' in l:
        base = int(l.split()[0].split('-')[0], 16)
        break

target_va = base + 0x37ed3a0
pattern = struct.pack('<Q', target_va)
pattern_escaped = ''.join('\\x%02x' % b for b in pattern)
print(f"PID: {pid}, base: 0x{base:x}, target_va: 0x{target_va:x}, pattern: {pattern.hex()}")

# Find the 420MB libc_malloc arena
arena_s, arena_e = None, None
for l in maps.splitlines():
    if 'rw-p' in l and ('00:00 0' in l or '[anon' in l):
        rng = l.split()[0]
        s, e = [int(x, 16) for x in rng.split('-')]
        if (e - s) > 100 * 1024 * 1024:
            arena_s, arena_e = s, e
            break

print(f"Arena: 0x{arena_s:x} - 0x{arena_e:x} ({(arena_e-arena_s)/1048576:.1f} MB)")

# Scan using busybox grep
skip_mb = arena_s // 1048576
count_mb = (arena_e - arena_s) // 1048576

cmd = f"su 0 sh -c 'busybox dd if=/proc/{pid}/mem bs=1M skip={skip_mb} count={count_mb} 2>/dev/null | busybox grep -b -a -o \"$(printf \"{pattern_escaped}\")\"'"
t0 = time.time()
res = subprocess.run([ADB, '-s', 'emulator-5554', 'shell', cmd], capture_output=True, timeout=25).stdout.decode().strip()
print(f"Scan finished in {time.time()-t0:.2f}s, hits:\n{res}")

for line in res.splitlines():
    if ':' in line:
        off = int(line.split(':')[0])
        obj_va = arena_s + off
        # Read 64 bytes at obj_va
        # read enclosing 1MB with skip_mb
        read_skip_mb = obj_va // 1048576
        local_off = obj_va - (read_skip_mb * 1048576)
        c = f"su 0 dd if=/proc/{pid}/mem bs=1048576 skip={read_skip_mb} count=1 2>/dev/null | busybox base64"
        b64_data = subprocess.run([ADB, '-s', 'emulator-5554', 'shell', c], capture_output=True, timeout=10).stdout.decode().strip()
        data = base64.b64decode(b64_data.replace('\n', '').replace('\r', ''))
        raw = data[local_off + 0x10 : local_off + 0x10 + 24]
        ctrl = raw[0]
        if not (ctrl & 1):
            sz = ctrl >> 1
            if 1 <= sz <= 22:
                key_hex = raw[1:1+sz].hex()
                print(f"FOUND BLOWFISH KEY: {key_hex} at 0x{obj_va:x}!")
