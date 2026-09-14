import os
import struct

def analyze_elf_symbols_and_dyn(so_path):
    print(f"\n==========================================")
    print(f"Analyzing {os.path.basename(so_path)}")
    print(f"==========================================")
    with open(so_path, 'rb') as f:
        elf_data = f.read()
        
    is_64 = (elf_data[4] == 2)
    endian = '<' if elf_data[5] == 1 else '>'
    
    # Read Section Headers
    if is_64:
        e_shoff = struct.unpack(endian + 'Q', elf_data[40:48])[0]
        e_shentsize = struct.unpack(endian + 'H', elf_data[58:60])[0]
        e_shnum = struct.unpack(endian + 'H', elf_data[60:62])[0]
        e_shstrndx = struct.unpack(endian + 'H', elf_data[62:64])[0]
    else:
        e_shoff = struct.unpack(endian + 'I', elf_data[32:36])[0]
        e_shentsize = struct.unpack(endian + 'H', elf_data[46:48])[0]
        e_shnum = struct.unpack(endian + 'H', elf_data[48:50])[0]
        e_shstrndx = struct.unpack(endian + 'H', elf_data[50:52])[0]

    print(f"Section headers offset: {hex(e_shoff)}, count: {e_shnum}, shstrndx: {e_shstrndx}")
    
    sections = []
    # If section headers exist
    if e_shoff > 0 and e_shnum > 0:
        # Get shstrtab
        shstr_entry = e_shoff + e_shstrndx * e_shentsize
        if is_64:
            shstr_offset = struct.unpack(endian + 'Q', elf_data[shstr_entry+24:shstr_entry+32])[0]
            shstr_size = struct.unpack(endian + 'Q', elf_data[shstr_entry+32:shstr_entry+40])[0]
        else:
            shstr_offset = struct.unpack(endian + 'I', elf_data[shstr_entry+16:shstr_entry+20])[0]
            shstr_size = struct.unpack(endian + 'I', elf_data[shstr_entry+20:shstr_entry+24])[0]
            
        shstrtab = elf_data[shstr_offset:shstr_offset+shstr_size]
        
        for i in range(e_shnum):
            entry = e_shoff + i * e_shentsize
            if is_64:
                sh_name_idx = struct.unpack(endian + 'I', elf_data[entry:entry+4])[0]
                sh_type = struct.unpack(endian + 'I', elf_data[entry+4:entry+8])[0]
                sh_flags = struct.unpack(endian + 'Q', elf_data[entry+8:entry+16])[0]
                sh_addr = struct.unpack(endian + 'Q', elf_data[entry+16:entry+24])[0]
                sh_offset = struct.unpack(endian + 'Q', elf_data[entry+24:entry+32])[0]
                sh_size = struct.unpack(endian + 'Q', elf_data[entry+32:entry+40])[0]
                sh_link = struct.unpack(endian + 'I', elf_data[entry+40:entry+44])[0]
                sh_info = struct.unpack(endian + 'I', elf_data[entry+44:entry+48])[0]
                sh_entsize = struct.unpack(endian + 'Q', elf_data[entry+56:entry+64])[0]
            else:
                sh_name_idx = struct.unpack(endian + 'I', elf_data[entry:entry+4])[0]
                sh_type = struct.unpack(endian + 'I', elf_data[entry+4:entry+8])[0]
                sh_flags = struct.unpack(endian + 'I', elf_data[entry+8:entry+12])[0]
                sh_addr = struct.unpack(endian + 'I', elf_data[entry+12:entry+16])[0]
                sh_offset = struct.unpack(endian + 'I', elf_data[entry+16:entry+20])[0]
                sh_size = struct.unpack(endian + 'I', elf_data[entry+20:entry+24])[0]
                sh_link = struct.unpack(endian + 'I', elf_data[entry+24:entry+28])[0]
                sh_info = struct.unpack(endian + 'I', elf_data[entry+28:entry+32])[0]
                sh_entsize = struct.unpack(endian + 'I', elf_data[entry+36:entry+40])[0]
                
            name_end = shstrtab.find(b'\x00', sh_name_idx)
            sname = shstrtab[sh_name_idx:name_end].decode('ascii', errors='ignore')
            sections.append({
                'name': sname,
                'type': sh_type,
                'addr': sh_addr,
                'offset': sh_offset,
                'size': sh_size,
                'link': sh_link,
                'info': sh_info,
                'entsize': sh_entsize
            })
            
    print("Sections found:")
    for s in sections:
        if s['name'] in ['.dynsym', '.dynstr', '.symtab', '.strtab', '.dynamic', '.rodata', '.text']:
            print(f"  {s['name']}: addr={hex(s['addr'])}, offset={hex(s['offset'])}, size={hex(s['size'])}")

    # Parse .dynamic
    dyn_sec = next((s for s in sections if s['name'] == '.dynamic'), None)
    dynstr_sec = next((s for s in sections if s['name'] == '.dynstr'), None)
    if dyn_sec and dynstr_sec:
        dynstr = elf_data[dynstr_sec['offset']:dynstr_sec['offset']+dynstr_sec['size']]
        d_size = 16 if is_64 else 8
        needed = []
        soname = None
        for off in range(dyn_sec['offset'], dyn_sec['offset'] + dyn_sec['size'], d_size):
            if is_64:
                d_tag = struct.unpack(endian + 'q', elf_data[off:off+8])[0]
                d_val = struct.unpack(endian + 'Q', elf_data[off+8:off+16])[0]
            else:
                d_tag = struct.unpack(endian + 'i', elf_data[off:off+4])[0]
                d_val = struct.unpack(endian + 'I', elf_data[off+4:off+8])[0]
            if d_tag == 0:
                break
            if d_tag == 1: # DT_NEEDED
                end = dynstr.find(b'\x00', d_val)
                needed.append(dynstr[d_val:end].decode('ascii', errors='ignore'))
            elif d_tag == 14: # DT_SONAME
                end = dynstr.find(b'\x00', d_val)
                soname = dynstr[d_val:end].decode('ascii', errors='ignore')
        print(f"SONAME: {soname}")
        print(f"DT_NEEDED ({len(needed)} libraries):")
        for lib in needed:
            print(f"  - {lib}")

    # Parse exported symbols in .dynsym
    dynsym_sec = next((s for s in sections if s['name'] == '.dynsym'), None)
    if dynsym_sec and dynstr_sec:
        dynstr = elf_data[dynstr_sec['offset']:dynstr_sec['offset']+dynstr_sec['size']]
        sym_entsize = 24 if is_64 else 16
        num_syms = dynsym_sec['size'] // sym_entsize
        print(f"\nTotal dynsym symbols: {num_syms}")
        jni_symbols = []
        bw_symbols = []
        for i in range(num_syms):
            soff = dynsym_sec['offset'] + i * sym_entsize
            if is_64:
                st_name = struct.unpack(endian + 'I', elf_data[soff:soff+4])[0]
                st_info = elf_data[soff+4]
                st_shndx = struct.unpack(endian + 'H', elf_data[soff+6:soff+8])[0]
                st_value = struct.unpack(endian + 'Q', elf_data[soff+8:soff+16])[0]
                st_size = struct.unpack(endian + 'Q', elf_data[soff+16:soff+24])[0]
            else:
                st_name = struct.unpack(endian + 'I', elf_data[soff:soff+4])[0]
                st_value = struct.unpack(endian + 'I', elf_data[soff+4:soff+8])[0]
                st_size = struct.unpack(endian + 'I', elf_data[soff+8:soff+12])[0]
                st_info = elf_data[soff+12]
                st_shndx = struct.unpack(endian + 'H', elf_data[soff+14:soff+16])[0]
                
            end = dynstr.find(b'\x00', st_name)
            sym_name = dynstr[st_name:end].decode('ascii', errors='ignore')
            if 'Java_' in sym_name or 'NativeInterface' in sym_name:
                jni_symbols.append((sym_name, hex(st_value), st_size, st_shndx))
            elif any(k in sym_name for k in ['bwclient', 'Mercury', 'logOn', 'ServerConnection', 'BaseApp', 'CellApp']):
                bw_symbols.append((sym_name, hex(st_value), st_size, st_shndx))
                
        print(f"Exported JNI symbols ({len(jni_symbols)}):")
        for sym in jni_symbols:
            print(f"  {sym[0]} -> value={sym[1]}, size={sym[2]}, shndx={sym[3]}")
        print(f"Exported BW/Mercury/Server symbols in dynsym ({len(bw_symbols)}):")
        for sym in bw_symbols[:20]:
            print(f"  {sym[0]} -> value={sym[1]}, size={sym[2]}")

analyze_elf_symbols_and_dyn(r'c:\Users\Raysoo\Downloads\ROS_RE\03_lib\libclient_arm64.so')
analyze_elf_symbols_and_dyn(r'c:\Users\Raysoo\Downloads\ROS_RE\01_apk\base_decompiled\lib\armeabi-v7a\libclient.so')
