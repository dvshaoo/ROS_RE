import sys, os, time, struct, subprocess

ADB = r'C:\LDPlayer\LDPlayer9\adb.exe'
DEVICE_SERIAL = 'emulator-5554'
LIBCLIENT_VTABLE_FILE_ADDR = 0x37dd3a0

def get_pid():
    res = subprocess.run([ADB, '-s', DEVICE_SERIAL, 'shell', 'pidof com.netease.chiji'], capture_output=True, text=True)
    out = res.stdout.strip()
    return out.split()[0] if out else None

def parse_sso_key(raw):
    if len(raw) < 1:
        return None
    ctrl = raw[0]
    if ctrl & 1:
        return None
    length = ctrl >> 1
    if length == 0 or length > 22 or len(raw) < 1 + length:
        return None
    return raw[1:1 + length].hex()

def check_range(pid, skip_mb, count_mb, pattern_escaped):
    check_cmd = (
        f"su 0 sh -c 'dd if=/proc/{pid}/mem bs=1048576 skip={skip_mb} count={count_mb} 2>/dev/null "
        f'| grep -qa -o "$(printf "{pattern_escaped}")"\''
    )
    res = subprocess.run([ADB, '-s', DEVICE_SERIAL, 'shell', check_cmd], capture_output=True, timeout=10)
    return res.returncode == 0

def binary_search_fast():
    t0 = time.time()
    pid = get_pid()
    if not pid:
        print("No PID found")
        return
    print(f"[{time.time()-t0:.2f}s] PID: {pid}")

    maps = subprocess.run([ADB, '-s', DEVICE_SERIAL, 'shell', 'su', '0', 'cat', f'/proc/{pid}/maps'], capture_output=True, text=True).stdout
    base_addr = None
    large_regions = []
    for line in maps.splitlines():
        if 'libclient.so' in line and base_addr is None:
            parts = line.split()
            if parts[2] == '00000000':
                base_addr = int(parts[0].split('-')[0], 16)
        if 'libc_malloc' in line or '[heap]' in line:
            parts = line.split()
            s, e = [int(x, 16) for x in parts[0].split('-')]
            sz = (e - s) // (1024 * 1024)
            if sz > 16:
                large_regions.append((s, e, sz))

    target_va = base_addr + LIBCLIENT_VTABLE_FILE_ADDR
    pattern = struct.pack('<Q', target_va)
    pattern_escaped = ''.join('\\x%02x' % b for b in pattern)
    print(f"[{time.time()-t0:.2f}s] Target VA: 0x{target_va:x} pattern: {pattern.hex()}")

    found_keys = []
    for s, e, sz in large_regions:
        aligned_start = (s // 1048576) * 1048576
        skip_mb = aligned_start // 1048576
        count_mb = -(-(e - aligned_start) // 1048576)

        t_check = time.time()
        if not check_range(pid, skip_mb, count_mb, pattern_escaped):
            print(f"[{time.time()-t0:.2f}s] Region 0x{s:x} ({sz} MB) no match ({time.time()-t_check:.2f}s)")
            continue

        print(f"[{time.time()-t0:.2f}s] Region 0x{s:x} ({sz} MB) MATCH! Starting binary search...")
        # Binary search down to 2 MB
        low = skip_mb
        high = skip_mb + count_mb
        while (high - low) > 2:
            mid = (low + high) // 2
            # Check left half [low, mid]
            # Add 1 MB overlap to avoid splitting pattern at boundary
            c_left = (mid - low) + 1
            if check_range(pid, low, c_left, pattern_escaped):
                high = mid + 1
            else:
                low = mid

        print(f"[{time.time()-t0:.2f}s] Narrowed down to MB range [{low}, {high}] (size: {high-low} MB)")
        t_dump = time.time()
        dump_cmd = f"su 0 dd if=/proc/{pid}/mem bs=1048576 skip={low} count={high-low} 2>/dev/null"
        data = subprocess.run([ADB, '-s', DEVICE_SERIAL, 'exec-out', dump_cmd], capture_output=True, timeout=10).stdout
        print(f"[{time.time()-t0:.2f}s] Dumped {len(data)/(1024*1024):.2f} MB in {time.time()-t_dump:.2f}s")

        idx = 0
        while True:
            idx = data.find(pattern, idx)
            if idx == -1:
                break
            raw = data[idx + 0x10:idx + 0x10 + 24]
            k = parse_sso_key(raw)
            if k:
                abs_va = low * 1048576 + idx
                found_keys.append((abs_va, k))
                print(f"[{time.time()-t0:.2f}s] Candidate at 0x{abs_va:x}: key={k}")
            idx += 1
        if found_keys:
            break

    print(f"[{time.time()-t0:.2f}s] TOTAL SCAN TIME: {time.time()-t0:.2f}s! Found: {found_keys}")

if __name__ == '__main__':
    binary_search_fast()
