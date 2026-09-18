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

    print(f"Base: 0x{base_addr:x}, Regions: {len(regions)}")
    target_va = base_addr + 0x37ed3a0
    pattern = struct.pack('<Q', target_va)
    pat_esc = ''.join('\\x%02x' % b for b in pattern)
    print(f"Target VA: 0x{target_va:x}, Pattern: {pattern.hex()} ({pat_esc})")

    # Let's check regions under 16MB in batches of 50
    small_regions = [(s, e) for (s, e) in regions if (e - s) <= 16 * 1024 * 1024]
    print(f"Small regions (<= 16MB): {len(small_regions)}")

    # Search in batches of 100
    for b_idx in range(0, len(small_regions), 100):
        batch = small_regions[b_idx:b_idx+100]
        items = " ".join(f"{s}:{e}" for s, e in batch)
        sh_script = f"""
for r in {items}; do
    s=${{r%%:*}}
    e=${{r##*:}}
    aligned=$(( (s / 1048576) * 1048576 ))
    skip=$(( aligned / 1048576 ))
    count=$(( (e - aligned + 1048575) / 1048576 ))
    if [ $count -gt 0 ]; then
        if dd if=/proc/{pid}/mem bs=1048576 skip=$skip count=$count 2>/dev/null | grep -qa -o "$(printf "{pat_esc}")"; then
            echo "HIT: $s-$e skip=$skip count=$count"
        fi
    fi
done
"""
        res = adb(['shell', f"su 0 sh -c '{sh_script}'"], timeout=60)
        out = res.stdout.decode('latin1').strip()
        if out:
            print(f"Batch {b_idx}: {out}")


if __name__ == '__main__':
    main()
