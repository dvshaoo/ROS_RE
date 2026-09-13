import sys, os, struct, zlib
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\05_entities')
from neox_decrypt import scan_index
import zipfile

obb = zipfile.ZipFile(r'C:\Users\Raysoo\Downloads\ROS_RE\04_obb\patch.1117219.com.netease.chiji.obb')
script_npk = obb.read('script.npk')
obb.close()

entries = scan_index(script_npk, limit=4000)
for e in entries:
    if e.get('hash_hex','').endswith('4CC04A3F'):
        print('FOUND offset=0x%X comp=%d decomp=%d' % (e['offset'], e['comp_size'], e['decomp_size']))
        data = script_npk[e['offset']:e['offset']+e['comp_size']]
        print('Header: %s' % data[:8].hex())
        enc_data = data[4:]
        print('Encrypted payload: %d bytes' % len(enc_data))
        with open(r'C:\Users\Raysoo\Downloads\ROS_RE\05_entities\ResourcePatcher_enc.bin','wb') as f:
            f.write(enc_data)
        print('Saved to ResourcePatcher_enc.bin')
        break
