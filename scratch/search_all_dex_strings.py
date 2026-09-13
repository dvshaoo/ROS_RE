import struct, glob, os

dex_files = ['02_dex/classes.dex', '02_dex/classes2.dex', '02_dex/classes3.dex']

search_terms = [
    b'j/d/d',
    b'e/b/c',
    b'MpayActivity',
    b'MpayLoginCallback',
    b'onFailure',
    b'onLoginSuccess',
    b'loginDone',
    b'minor_status',
    b'has_minor',
    b'isFirstLogin',
    b'Cancel login',
    b'RESULT_CANCELED',
    b'RESULT_OK',
    b'setResult',
    b'finish',
    b'onActivityResult',
    b'startActivityForResult'
]

print("=== SEARCHING STRINGS ACROSS ALL 3 DEX FILES ===")
for dpath in dex_files:
    if not os.path.exists(dpath):
        print(f"File not found: {dpath}")
        continue
    data = open(dpath, 'rb').read()
    string_ids_off = struct.unpack_from('<I', data, 60)[0]
    string_ids_size = struct.unpack_from('<I', data, 56)[0]
    print(f"\n--- {dpath} (string_ids: {string_ids_size}) ---")
    
    # scan string table
    found = {term: [] for term in search_terms}
    for i in range(string_ids_size):
        off = struct.unpack_from('<I', data, string_ids_off + i * 4)[0]
        p = off
        while data[p] & 0x80: p += 1
        p += 1
        end = data.find(b'\x00', p)
        s = data[p:end]
        for term in search_terms:
            if term in s:
                found[term].append((i, s.decode('latin1', errors='replace')[:80]))
                
    for term, hits in found.items():
        if hits:
            print(f"  [{term.decode()}]: {len(hits)} hits")
            for idx, s in hits[:5]:
                print(f"    #{idx}: {s}")
