import subprocess, struct, time

ADB = r'C:\LDPlayer\LDPlayer9\adb.exe'
DEVICE_SERIAL = 'emulator-5554'

def adb(cmd, timeout=30):
    return subprocess.run([ADB, '-s', DEVICE_SERIAL] + cmd, capture_output=True, timeout=timeout)

def main():
    pid_out = adb(['shell', 'pidof', 'com.netease.chiji']).stdout.decode().strip()
    if not pid_out:
        print("No PID found")
        return
    pid = pid_out.split()[0]
    print(f"PID: {pid}")

    maps = adb(['shell', 'su', '0', 'cat', f'/proc/{pid}/maps']).stdout.decode('latin1')
    base_addr = None
    regions = []
    for line in maps.splitlines():
        if 'libclient.so' in line and base_addr is None and ' 00000000 ' in line:
            base_addr = int(line.split()[0].split('-')[0], 16)
        if 'rw-p' in line and (line.strip().endswith('00:00 0') or '[heap]' in line or '[anon' in line):
            parts = line.split()[0].split('-')
            regions.append((int(parts[0], 16), int(parts[1], 16)))

    print(f"Base: 0x{base_addr:x}, Total heap/anon regions: {len(regions)}")
    target_va = base_addr + 0x37ed3a0
    pattern = struct.pack('<Q', target_va)
    print(f"Target VA: 0x{target_va:x}, Pattern: {pattern.hex()}")

    # Sort regions by size descending or search regions under 32MB
    candidate_regions = [(s, e) for (s, e) in regions if (e - s) <= 32 * 1024 * 1024]
    print(f"Candidate regions (<= 32MB): {len(candidate_regions)}")

    found = []
    for s, e in candidate_regions:
        aligned_s = (s // 1048576) * 1048576
        skip_mb = aligned_s // 1048576
        count_mb = -(-(e - aligned_s) // 1048576)
        if count_mb <= 0:
            continue
        # Pull region to host using exec-out (binary safe)
        dump_cmd = f"su 0 dd if=/proc/{pid}/mem bs=1048576 skip={skip_mb} count={count_mb} 2>/dev/null"
        raw_data = adb(['exec-out', dump_cmd], timeout=10).stdout
        idx = 0
        while True:
            idx = raw_data.find(pattern, idx)
            if idx == -1:
                break
            # Found pattern!
            obj_va = aligned_s + idx
            key_raw = raw_data[idx + 0x10 : idx + 0x10 + 24]
            print(f"HIT at VA 0x{obj_va:x}! Raw at +0x10: {key_raw[:12].hex()}")
            if len(key_raw) >= 1:
                ctrl = key_raw[0]
                if not (ctrl & 1):
                    length = ctrl >> 1
                    if 0 < length <= 22 and len(key_raw) >= 1 + length:
                        k = key_raw[1:1+length].hex()
                        print(f"*** EXTRACTED KEY: {k} (length={length}) ***")
                        found.append(k)
            idx += 1
        if found:
            break

    print("Result keys:", set(found))

if __name__ == '__main__':
    main()
