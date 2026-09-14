import struct, sys

def parse_npk_index(path):
    with open(path, 'rb') as f:
        data = f.read()
    
    print(f"File size: {len(data)}")
    print(f"Header: {' '.join(f'{b:02x}' for b in data[:32])}")
    
    magic = data[:4]
    version = struct.unpack_from('<I', data, 4)[0]
    print(f"Magic: {magic}, Version: {version}")
    
    # Try different header sizes to find the index
    # NXPK format typically: magic(4) + version(4) + reserved(8) + file_count(4) + ...
    # Or: magic(4) + version(4) + index_offset(4) + index_size(4) + ...
    
    # Try brute-forcing: look for the string "init" or "game" at various XOR-decrypted positions
    for key in range(256):
        # Try XOR decrypting a window around offset 32
        decrypted = bytes(b ^ key for b in data[32:4096])
        if b'init' in decrypted:
            idx = decrypted.find(b'init')
            # Check if it looks like a file path
            context = decrypted[max(0,idx-5):idx+20]
            if all(32 <= b < 127 or b == 0 for b in context):
                print(f"XOR key 0x{key:02x}: Found 'init' at relative offset {idx}")
                print(f"  Context: {context}")
    
    # Also try looking for it with different offsets
    for start in range(16, 128, 4):
        for key in range(256):
            decrypted = bytes(b ^ key for b in data[start:start+2048])
            if b'init' in decrypted:
                idx = decrypted.find(b'init')
                context = decrypted[max(0,idx-10):idx+30]
                if all(32 <= b < 127 or b == 0 for b in context):
                    print(f"Offset {start}, XOR 0x{key:02x}: Found 'init'")
                    print(f"  Context: {context}")
                    break

parse_npk_index(r'C:\Users\Raysoo\Downloads\ROS_RE\04_obb\extracted\script.npk')
