import os
import struct

def parse_elf(path):
    with open(path, 'rb') as f:
        data = f.read(64)
        if len(data) < 64 or data[:4] != b'\x7fELF':
            return None
        ei_class = data[4] # 1=32-bit, 2=64-bit
        ei_data = data[5] # 1=LE, 2=BE
        endian = '<' if ei_data == 1 else '>'
        e_type = struct.unpack(endian + 'H', data[16:18])[0]
        e_machine = struct.unpack(endian + 'H', data[18:20])[0]
        e_version = struct.unpack(endian + 'I', data[20:24])[0]
        
        machine_map = {
            3: 'x86',
            40: 'ARM (32-bit)',
            62: 'x86_64',
            183: 'AArch64 (ARM64)'
        }
        
        type_map = {
            1: 'ET_REL',
            2: 'ET_EXEC',
            3: 'ET_DYN (Shared Object)'
        }
        
        return {
            'class': '64-bit' if ei_class == 2 else '32-bit',
            'endian': 'Little-endian' if ei_data == 1 else 'Big-endian',
            'machine': machine_map.get(e_machine, f'Unknown ({e_machine})'),
            'type': type_map.get(e_type, f'Unknown ({e_type})'),
            'size': os.path.getsize(path)
        }

def find_needed_libs(path):
    # Quick scan for DT_NEEDED or SONAME in ELF dynamic section
    needed = []
    soname = None
    with open(path, 'rb') as f:
        header = f.read(64)
        if header[:4] != b'\x7fELF':
            return needed, soname
        ei_class = header[4]
        endian = '<' if header[5] == 1 else '>'
        
        if ei_class == 2: # 64-bit
            e_shoff = struct.unpack(endian + 'Q', header[40:48])[0]
            e_shentsize = struct.unpack(endian + 'H', header[58:60])[0]
            e_shnum = struct.unpack(endian + 'H', header[60:62])[0]
            e_shstrndx = struct.unpack(endian + 'H', header[62:64])[0]
        else:
            e_shoff = struct.unpack(endian + 'I', header[32:36])[0]
            e_shentsize = struct.unpack(endian + 'H', header[46:48])[0]
            e_shnum = struct.unpack(endian + 'H', header[48:50])[0]
            e_shstrndx = struct.unpack(endian + 'H', header[50:52])[0]
            
    return needed, soname

def check_string_in_file(path, search_str):
    search_bytes = search_str.encode('utf-8')
    with open(path, 'rb') as f:
        content = f.read()
        idx = content.find(search_bytes)
        count = content.count(search_bytes)
        return idx, count

if __name__ == '__main__':
    targets = [
        r'c:\Users\Raysoo\Downloads\ROS_RE\03_lib\libclient_arm64.so',
        r'c:\Users\Raysoo\Downloads\ROS_RE\01_apk\base_decompiled\lib\arm64-v8a\libclient.so',
        r'c:\Users\Raysoo\Downloads\ROS_RE\01_apk\base_decompiled\lib\armeabi-v7a\libclient.so',
    ]
    for t in targets:
        if os.path.exists(t):
            info = parse_elf(t)
            print(f"File: {t}")
            print(f"  Arch: {info['machine']} ({info['class']})")
            print(f"  Type: {info['type']}")
            print(f"  Size: {info['size']} bytes ({info['size'] / (1024*1024):.2f} MB)")
            
    print("\n--- Checking for loginapp.pubkey in libclient ---")
    for t in targets:
        if os.path.exists(t):
            idx, count = check_string_in_file(t, 'loginapp.pubkey')
            print(f"{os.path.basename(t)}: 'loginapp.pubkey' found at {hex(idx) if idx != -1 else 'NOT FOUND'} (count: {count})")
            idx_bw, count_bw = check_string_in_file(t, 'bwclient')
            print(f"{os.path.basename(t)}: 'bwclient' found at {hex(idx_bw) if idx_bw != -1 else 'NOT FOUND'} (count: {count_bw})")
            idx_merc, count_merc = check_string_in_file(t, 'Mercury')
            print(f"{os.path.basename(t)}: 'Mercury' found at {hex(idx_merc) if idx_merc != -1 else 'NOT FOUND'} (count: {count_merc})")
            idx_logon, count_logon = check_string_in_file(t, 'logOnBegin')
            print(f"{os.path.basename(t)}: 'logOnBegin' found at {hex(idx_logon) if idx_logon != -1 else 'NOT FOUND'} (count: {count_logon})")
