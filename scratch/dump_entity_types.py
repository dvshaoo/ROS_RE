import subprocess
import struct

ADB = r'C:\LDPlayer\LDPlayer9\adb.exe'

def get_pid():
    out = subprocess.run([ADB, '-s', 'emulator-5554', 'shell', 'pidof', 'com.netease.chiji'], capture_output=True).stdout.decode().strip()
    return out.split()[0] if out else None

def main():
    pid = get_pid()
    if not pid:
        print("No PID found")
        return
    maps = subprocess.run([ADB, '-s', 'emulator-5554', 'shell', 'su', '0', 'cat', f'/proc/{pid}/maps'], capture_output=True).stdout.decode(errors='replace')
    base = None
    for l in maps.splitlines():
        if 'libclient.so' in l and '00000000' in l:
            base = int(l.split()[0].split('-')[0], 16)
            break
    print(f"libclient base: 0x{base:x}")
    vec_addr = base + 0x45785f0
    
    # Read vector
    cmd = f"su 0 dd if=/proc/{pid}/mem bs=1 count=24 skip={vec_addr} 2>/dev/null | base64"
    b64 = subprocess.run([ADB, '-s', 'emulator-5554', 'shell', cmd], capture_output=True).stdout.decode().strip()
    import base64
    vec_bytes = base64.b64decode(b64)
    begin, end, _ = struct.unpack('<QQQ', vec_bytes[:24])
    count = (end - begin) // 8
    print(f"Total entity types: {count}")
    
    # Read all pointers
    cmd = f"su 0 dd if=/proc/{pid}/mem bs=1 count={count*8} skip={begin} 2>/dev/null | base64"
    b64 = subprocess.run([ADB, '-s', 'emulator-5554', 'shell', cmd], capture_output=True).stdout.decode().strip()
    raw_ptrs = base64.b64decode(b64.replace('\n', '').replace('\r', ''))
    ptrs = struct.unpack(f'<{count}Q', raw_ptrs[:count*8])
    
    # Let's inspect where EntityType name is stored.
    # Disassembly of EntityType constructor or name() will show offset of name.
    # In BigWorld:
    # class EntityType {
    #     ...
    #     std::string name_;
    # }
    for i, p in enumerate(ptrs):
        cmd = f"su 0 dd if=/proc/{pid}/mem bs=1 count=64 skip={p} 2>/dev/null | base64"
        b64 = subprocess.run([ADB, '-s', 'emulator-5554', 'shell', cmd], capture_output=True).stdout.decode().strip()
        obj_bytes = base64.b64decode(b64.replace('\n', '').replace('\r', ''))
        
        # Check ASCII strings in obj_bytes
        # In libc++ std::string (SSO):
        # byte 0: size << 1
        # byte 1..: chars
        names = []
        for off in range(0, 48, 8):
            # check SSO string
            ctrl = obj_bytes[off]
            if not (ctrl & 1):
                sz = ctrl >> 1
                if 2 <= sz <= 32 and off + 1 + sz <= len(obj_bytes):
                    s = obj_bytes[off+1:off+1+sz]
                    if s.isalnum() or b'_' in s:
                        names.append((off, s.decode(errors='ignore')))
            # check pointer string
            if off + 8 <= len(obj_bytes):
                str_ptr = struct.unpack('<Q', obj_bytes[off:off+8])[0]
                if str_ptr > 0x100000:
                    pass
        print(f"Type {i:3d} (0x{i:02x}): ptr=0x{p:x} names={names}")

if __name__ == '__main__':
    main()
