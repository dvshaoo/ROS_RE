import struct, glob

terms = [
    b'createRole',
    b'createCharacter',
    b'create_role',
    b'create_character',
    b'roleList',
    b'role_list',
    b'enterHall',
    b'enter_hall',
    b'offline',
    b'loginapp',
    b'baseapp'
]

dex_files = ['02_dex/classes.dex', '02_dex/classes2.dex', '02_dex/classes3.dex']

for dpath in dex_files:
    data = open(dpath, 'rb').read()
    string_ids_off = struct.unpack_from('<I', data, 0x3c)[0]
    string_ids_size = struct.unpack_from('<I', data, 0x38)[0]
    print(f"\n--- {dpath} ---")
    for i in range(string_ids_size):
        off = struct.unpack_from('<I', data, string_ids_off + i * 4)[0]
        p = off; ln = 0; sh = 0
        while True:
            b = data[p]; p += 1; ln |= (b & 0x7f) << sh
            if not (b & 0x80): break
            sh += 7
        s = data[p:p+ln]
        for t in terms:
            if t.lower() in s.lower():
                print(f"  hit '{t.decode()}': string #{i}: {s.decode('latin1', errors='replace')}")
