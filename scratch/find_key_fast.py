import os, sys, struct, subprocess

ADB = r'C:\LDPlayer\LDPlayer9\adb.exe'
DEVICE_SERIAL = 'emulator-5554'
LIBCLIENT_VTABLE_FILE_ADDR = 0x37ed3a0

def adb_cmd(cmd):
    return subprocess.run([ADB, '-s', DEVICE_SERIAL] + cmd, capture_output=True).stdout

pid = adb_cmd(['shell', 'pidof', 'com.netease.chiji']).decode().strip().split()[0]
print(f"PID: {pid}")

maps = adb_cmd(['shell', 'su', '0', 'cat', f'/proc/{pid}/maps']).decode('latin1')
base_addr = None
regions = []
for line in maps.splitlines():
    if 'libclient.so' in line and base_addr is None and ' 00000000 ' in line:
        base_addr = int(line.split()[0].split('-')[0], 16)
    if 'rw-p' in line and (line.strip().endswith('00:00 0') or '[heap]' in line or '[anon' in line):
        parts = line.split()[0].split('-')
        regions.append((int(parts[0], 16), int(parts[1], 16)))

print(f"Base: 0x{base_addr:x}, Heap regions: {len(regions)}")
target_va = base_addr + LIBCLIENT_VTABLE_FILE_ADDR
pattern = struct.pack('<Q', target_va)
print(f"Target VA: 0x{target_va:x}, Pattern: {pattern.hex()}")

def parse_sso_key(raw):
    if len(raw) < 1: return None
    ctrl = raw[0]
    if ctrl & 1: return None
    length = ctrl >> 1
    if length == 0 or length > 22 or len(raw) < 1 + length: return None
    return raw[1:1 + length].hex()

for s, e in regions:
    size = e - s
    # Only dump regions under 30MB
    if size > 30 * 1024 * 1024:
        continue
    skip_mb = s // 1048576
    count_mb = -(-(e - s) // 1048576)
    dump_cmd = f"su 0 dd if=/proc/{pid}/mem bs=1048576 skip={skip_mb} count={count_mb} 2>/dev/null"
    data = subprocess.run([ADB, '-s', DEVICE_SERIAL, 'exec-out', dump_cmd], capture_output=True).stdout
    idx = 0
    while True:
        idx = data.find(pattern, idx)
        if idx == -1:
            break
        raw = data[idx + 0x10 : idx + 0x10 + 24]
        k = parse_sso_key(raw)
        print(f"HIT at offset 0x{idx:x} in region 0x{s:x}-0x{e:x}! Key: {k}")
        idx += 1
