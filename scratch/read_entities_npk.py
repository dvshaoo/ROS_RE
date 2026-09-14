import struct
import zlib

npk_path = r'c:\Users\Raysoo\Downloads\ROS_RE\05_entities\entities.npk'
with open(npk_path, 'rb') as f:
    header = f.read(16)
    print(f"NPK header: {header}")
    # NetEase NPK header is usually 'NXPK'
    if header[:4] == b'NXPK':
        count, table_offset = struct.unpack('<II', header[4:12])
        print(f"NXPK entry count: {count}, table offset: {hex(table_offset)}")
        f.seek(table_offset)
        # Read table
        table_data = f.read()
        print(f"Table data len: {len(table_data)}")
        # Check if table is compressed or raw entries
