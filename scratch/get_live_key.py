import os
import sys
import struct
import subprocess

ADB = r'C:\LDPlayer\LDPlayer9\adb.exe'
DEVICE_SERIAL = 'emulator-5554'
LIBCLIENT_VTABLE_FILE_ADDR = 0x37ed3a0

def adb(args, timeout=20):
    cmd = [ADB, '-s', DEVICE_SERIAL] + args
    return subprocess.run(cmd, capture_output=True, timeout=timeout).stdout

def get_pid():
    out = adb(['shell', 'pidof', 'com.netease.chiji']).decode(errors='replace').strip()
    return out.split()[0] if out else None

def get_libclient_base_and_regions(pid):
    maps = adb(['shell', 'su', '0', 'cat', f'/proc/{pid}/maps']).decode(errors='replace')
    base_addr = None
    regions = []
    for line in maps.splitlines():
        if 'libclient.so' in line and base_addr is None:
            rng = line.split()[0]
            start_hex, _ = rng.split('-')
            parts = line.split()
            if parts[2] == '00000000':
                base_addr = int(start_hex, 16)
        if 'rw-p' in line and (line.strip().endswith('00:00 0') or '[heap]' in line or '[anon' in line):
            rng = line.split()[0]
            s, e = rng.split('-')
            regions.append((int(s, 16), int(e, 16)))
    return base_addr, regions

def parse_sso_key(raw):
    if len(raw) < 1:
        return None
    ctrl = raw[0]
    if ctrl & 1:
        return None
    length = ctrl >> 1
    if length == 0 or length > 22 or len(raw) < 1 + length:
        return None
    key_bytes = raw[1:1 + length]
    return key_bytes.hex()

def main():
    pid = get_pid()
    print(f"PID: {pid}")
    if not pid:
        return
    base_addr, regions = get_libclient_base_and_regions(pid)
    print(f"Base: 0x{base_addr:x}, Regions: {len(regions)}")
    target_va = base_addr + LIBCLIENT_VTABLE_FILE_ADDR
    pattern = struct.pack('<Q', target_va)
    pattern_escaped = ''.join('\\x%02x' % b for b in pattern)
    print(f"Target vtable VA: 0x{target_va:x}, pattern: {pattern.hex()}")

    found_keys = []
    for s, e in regions:
        # Sort small regions first
        size = e - s
        if size < 4096:
            continue
        # Use dd + grep -b on device to find byte offsets quickly
        check_cmd = f"su 0 sh -c 'dd if=/proc/{pid}/mem bs=65536 skip={s // 65536} count={(e - s) // 65536} 2>/dev/null | grep -b -a -o \"$(printf \"{pattern_escaped}\")\"'"
        res = subprocess.run([ADB, '-s', DEVICE_SERIAL, 'shell', check_cmd], capture_output=True, timeout=6).stdout.decode(errors='ignore').strip()
        if res:
            for line in res.splitlines():
                if ':' in line:
                    off_in_region = int(line.split(':')[0])
                    obj_va = (s // 65536) * 65536 + off_in_region
                    # Read 64 bytes at obj_va
                    dump_cmd = f"su 0 dd if=/proc/{pid}/mem bs=1 skip={obj_va} count=64 2>/dev/null | base64"
                    import base64
                    b64 = subprocess.run([ADB, '-s', DEVICE_SERIAL, 'shell', dump_cmd], capture_output=True, timeout=5).stdout.decode().strip()
                    raw = base64.b64decode(b64.replace('\n', '').replace('\r', ''))
                    if len(raw) >= 0x10 + 8:
                        k = parse_sso_key(raw[0x10:0x10+24])
                        if k:
                            print(f"FOUND KEY: {k} at 0x{obj_va:x}")
                            found_keys.append(k)
    print(f"All distinct keys: {sorted(set(found_keys))}")

if __name__ == '__main__':
    main()
