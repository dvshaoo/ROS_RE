import struct

def decode_axml(data):
    RES_XML_START_NAMESPACE_TYPE = 0x00100100
    RES_XML_END_NAMESPACE_TYPE = 0x00100101
    RES_XML_START_ELEMENT_TYPE = 0x00100102
    RES_XML_END_ELEMENT_TYPE = 0x00100103
    RES_XML_CDATA_TYPE = 0x00100104

    magic, file_size = struct.unpack_from('<II', data, 0)
    pos = 8
    
    # Read string pool
    chunk_type, chunk_size = struct.unpack_from('<II', data, pos)
    string_count, style_count, flags, strings_start, styles_start = struct.unpack_from('<IIIII', data, pos + 8)
    is_utf8 = bool(flags & (1 << 8))
    offsets = struct.unpack_from(f'<{string_count}I', data, pos + 28)
    pool_base = pos + strings_start
    
    strings = []
    for off in offsets:
        p = pool_base + off
        if is_utf8:
            b1 = data[p]
            p += 1
            if b1 & 0x80:
                b1 = ((b1 & 0x7f) << 8) | data[p]
                p += 1
            b2 = data[p]
            p += 1
            if b2 & 0x80:
                b2 = ((b2 & 0x7f) << 8) | data[p]
                p += 1
            s = data[p:p+b2].decode('utf-8', errors='ignore')
        else:
            u16len = struct.unpack_from('<H', data, p)[0]
            p += 2
            if u16len & 0x8000:
                u16len = ((u16len & 0x7fff) << 16) | struct.unpack_from('<H', data, p)[0]
                p += 2
            s = data[p:p + u16len*2].decode('utf-16le', errors='ignore')
        strings.append(s)
        
    pos += chunk_size
    
    # Read resource ID map if present
    if pos < file_size:
        chunk_type, chunk_size = struct.unpack_from('<II', data, pos)
        if chunk_type == 0x00080180:
            pos += chunk_size
            
    # Now parse nodes
    indent = 0
    xml_out = []
    while pos < file_size:
        chunk_type, chunk_size = struct.unpack_from('<II', data, pos)
        if chunk_type == RES_XML_START_ELEMENT_TYPE:
            line_num, comment_idx, ns_idx, name_idx, attr_start, attr_size, attr_count, id_idx, class_idx, style_idx = struct.unpack_from('<IIIIHHHHHH', data, pos + 8)
            elem_name = strings[name_idx] if name_idx < len(strings) else f'unk_{name_idx}'
            attrs = []
            attr_offset = pos + 8 + attr_start
            for i in range(attr_count):
                a_ns_idx, a_name_idx, a_val_str_idx, a_type_data, a_data = struct.unpack_from('<IIIIhI', data, attr_offset + i * 20)[:5]
                a_name = strings[a_name_idx] if a_name_idx < len(strings) else f'unk_{a_name_idx}'
                a_val = strings[a_val_str_idx] if (a_val_str_idx != 0xFFFFFFFF and a_val_str_idx < len(strings)) else str(a_data)
                attrs.append(f'{a_name}="{a_val}"')
            attr_str = (' ' + ' '.join(attrs)) if attrs else ''
            xml_out.append('  ' * indent + f'<{elem_name}{attr_str}>')
            indent += 1
        elif chunk_type == RES_XML_END_ELEMENT_TYPE:
            indent = max(0, indent - 1)
            line_num, comment_idx, ns_idx, name_idx = struct.unpack_from('<IIII', data, pos + 8)
            elem_name = strings[name_idx] if name_idx < len(strings) else f'unk_{name_idx}'
            xml_out.append('  ' * indent + f'</{elem_name}>')
        elif chunk_type == RES_XML_START_NAMESPACE_TYPE or chunk_type == RES_XML_END_NAMESPACE_TYPE:
            pass
        pos += chunk_size
    return '\n'.join(xml_out)

with open(r'01_apk\base_decompiled\AndroidManifest.xml', 'rb') as f:
    text = decode_axml(f.read())

with open(r'scratch\manifest_decoded.xml', 'w', encoding='utf-8') as f:
    f.write(text)

print('Saved scratch/manifest_decoded.xml, lines:', len(text.splitlines()))
