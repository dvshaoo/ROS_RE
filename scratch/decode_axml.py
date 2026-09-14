import struct

with open(r'01_apk\base_decompiled\AndroidManifest.xml', 'rb') as f:
    data = f.read()

# Check AXML header
magic, size = struct.unpack_from('<II', data, 0)
print(f'Magic: {hex(magic)}, Size: {size}')

# String pool starts at offset 8
chunk_type, chunk_size = struct.unpack_from('<II', data, 8)
print(f'String pool type: {hex(chunk_type)}, size: {chunk_size}')
string_count, style_count, flags, strings_start, styles_start = struct.unpack_from('<IIIII', data, 16)
print(f'Strings: {string_count}, flags: {hex(flags)}')

is_utf8 = bool(flags & (1 << 8))
offsets = struct.unpack_from(f'<{string_count}I', data, 36)

strings = []
pool_base = 8 + strings_start
for off in offsets:
    pos = pool_base + off
    if is_utf8:
        # UTF-8: length prefix then null-terminated
        # First 1 or 2 bytes = char count, next 1 or 2 bytes = byte count
        b1 = data[pos]
        pos += 1
        if b1 & 0x80:
            b1 = ((b1 & 0x7f) << 8) | data[pos]
            pos += 1
        b2 = data[pos]
        pos += 1
        if b2 & 0x80:
            b2 = ((b2 & 0x7f) << 8) | data[pos]
            pos += 1
        s = data[pos:pos+b2].decode('utf-8', errors='ignore')
    else:
        # UTF-16LE
        u16len = struct.unpack_from('<H', data, pos)[0]
        pos += 2
        if u16len & 0x8000:
            u16len = ((u16len & 0x7fff) << 16) | struct.unpack_from('<H', data, pos)[0]
            pos += 2
        s = data[pos:pos + u16len*2].decode('utf-16le', errors='ignore')
    strings.append(s)

print(f'Decoded {len(strings)} strings.')
for s in strings:
    if 'Activity' in s or 'com.netease' in s or 'main' in s.lower() or 'launch' in s.lower() or 'action' in s.lower():
        print(' ', s)
