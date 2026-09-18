import subprocess, struct, time

ADB = r'C:\LDPlayer\LDPlayer9\adb.exe'
DEVICE_SERIAL = 'emulator-5554'

def adb(cmd, timeout=30):
    return subprocess.run([ADB, '-s', DEVICE_SERIAL] + cmd, capture_output=True, timeout=timeout)

def main():
    pid = adb(['shell', 'pidof', 'com.netease.chiji']).stdout.decode().strip().split()[0]
    print(f"PID: {pid}")

    maps = adb(['shell', 'su', '0', 'cat', f'/proc/{pid}/maps']).stdout.decode('latin1')
    base_addr = None
    malloc_regions = []
    for line in maps.splitlines():
        if 'libclient.so' in line and base_addr is None and ' 00000000 ' in line:
            base_addr = int(line.split()[0].split('-')[0], 16)
        if 'libc_malloc' in line:
            parts = line.split()[0].split('-')
            malloc_regions.append((int(parts[0], 16), int(parts[1], 16)))

    target_va = base_addr + 0x37dd3a0
    pattern = struct.pack('<Q', target_va)
    pat_esc = ''.join('\\x%02x' % b for b in pattern)
    print(f"Target VA: 0x{target_va:x}, Pattern: {pattern.hex()}")
    print(f"Total libc_malloc regions: {len(malloc_regions)}")

    sh_lines = ["#!/system/bin/sh", f"PAT=\"$(printf '{pat_esc}')\""]
    for s, e in malloc_regions:
        skip = s // 1048576
        count = -(-(e - s) // 1048576)
        if count <= 0: continue
        sh_lines.append(f"dd if=/proc/{pid}/mem bs=1048576 skip={skip} count={count} 2>/dev/null | grep -b -a -o \"$PAT\" | while read l; do echo \"{s}:$l\"; done")

    sh_content = "\n".join(sh_lines) + "\n"

    p = subprocess.Popen([ADB, '-s', DEVICE_SERIAL, 'shell', 'su 0 sh -c "cat > /data/local/tmp/scan_heap.sh && chmod +x /data/local/tmp/scan_heap.sh"'], stdin=subprocess.PIPE)
    p.communicate(sh_content.encode())

    print("Running scan on device...")
    t0 = time.time()
    res_bytes = adb(['shell', 'su 0 /data/local/tmp/scan_heap.sh'], timeout=30).stdout
    print(f"Scan finished in {time.time()-t0:.2f}s, bytes returned: {len(res_bytes)}")
    res_text = res_bytes.decode('latin1', errors='replace').strip()

    for line in res_text.splitlines():
        if ':' in line:
            parts = line.split(':')
            reg_s = int(parts[0])
            off_str = parts[1]
            try:
                byte_off = int(off_str)
            except ValueError:
                continue
            obj_va = reg_s + byte_off
            print(f"\nFOUND EncryptionFilter object at VA: 0x{obj_va:x}!")
            # Dump 64 bytes at obj_va
            raw_dump = adb(['shell', f'su 0 dd if=/proc/{pid}/mem bs=1 skip={obj_va} count=64 2>/dev/null | xxd']).stdout.decode('latin1', errors='replace')
            print("Hex dump:\n", raw_dump)

            # Dump bytes for key parsing
            raw_b64 = adb(['shell', f'su 0 dd if=/proc/{pid}/mem bs=1 skip={obj_va+16} count=24 2>/dev/null | base64']).stdout.decode().strip()
            import base64
            key_raw = base64.b64decode(raw_b64.replace('\n', '').replace('\r', ''))
            if len(key_raw) > 0:
                ctrl = key_raw[0]
                length = ctrl >> 1
                k = key_raw[1:1+length].hex()
                print(f"*** EXTRACTED KEY: {k} (ctrl=0x{ctrl:02x}, len={length}) ***")

if __name__ == '__main__':
    main()

