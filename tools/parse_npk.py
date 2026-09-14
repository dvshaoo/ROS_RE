import struct, re, sys

def parse_npk(path):
    with open(path, 'rb') as f:
        data = f.read()
    
    magic = data[:4]
    assert magic == b'NXPK', f"Not NXPK: {magic}"
    
    version = struct.unpack_from('<I', data, 4)[0]
    print(f"Version: {version} (0x{version:04x})")
    
    # Find all readable strings of length > 5
    strings = re.findall(b'[\x20-\x7e]{6,}', data)
    print(f"Readable strings ({len(strings)} total):")
    for s in strings:
        print(f"  {s.decode('ascii')}")

for path in sys.argv[1:]:
    print(f"\n=== {path} ===")
    parse_npk(path)
