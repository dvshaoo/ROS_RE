import struct

with open(r'C:\Users\Raysoo\Downloads\ROS_RE\04_obb\extracted\script.npk', 'rb') as f:
    data = f.read()

idx_offset = struct.unpack_from('<I', data, 20)[0]
print(f'Index offset candidate: {idx_offset} (0x{idx_offset:08x})')
print(f'File size: {len(data)}')

if idx_offset < len(data):
    print(f'Bytes at index offset: {" ".join(f"{b:02x}" for b in data[idx_offset:idx_offset+64])}')
    
    file_count = struct.unpack_from('<I', data, idx_offset)[0]
    print(f'Possible file count: {file_count}')
    
    if file_count < 10000:
        region = data[idx_offset:idx_offset+50000]
        for name in [b'init', b'game', b'common', b'shader']:
            idx = region.find(name)
            if idx >= 0:
                print(f'Found {name} at relative offset {idx}')
                print(f'Context: {region[max(0,idx-20):idx+40]}')
