import sys, zipfile, struct
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, 'C:/tools/re')
import ros_dump_module as R

target = b'g_UseSDKChannel'

def check_one(item):
    sig, raw = item
    try:
        m = R.member_marshal(raw)
        if target in m:
            co = R.P(m).load()
            return (hex(sig), R._name(co.filename))
    except:
        pass
    return None

def main():
    obb = r'c:\Users\Raysoo\Downloads\ROS_RE\04_obb\patch.1117219.com.netease.chiji.obb'
    with zipfile.ZipFile(obb, 'r') as z:
        with z.open('script.npk') as f:
            data = f.read()

    cnt = struct.unpack_from('<I', data, 4)[0]
    io_off = struct.unpack_from('<I', data, 0x14)[0]
    items = []
    for i in range(cnt):
        b = io_off + i * 28
        sig, off, ln, oln = struct.unpack_from('<IIII', data, b)
        items.append((sig, data[off:off+ln]))

    with ProcessPoolExecutor(max_workers=14) as ex:
        for res in ex.map(check_one, items, chunksize=50):
            if res:
                print('FOUND:', res)

if __name__ == '__main__':
    main()
