lib_path = r'c:\Users\Raysoo\Downloads\ROS_RE\01_apk\base_decompiled\lib\arm64-v8a\libclient.so'
with open(lib_path, 'rb') as f:
    # adrp 0x2a5d000
    offsets = [
        0x23d, 0x286, 0x2d1, 0x319, 0x3cd, 0x5ae, 0x69c, 0x702, 0x75a, 0x7a2, 0x843, 0x884, 0x8e2
    ]
    for off in offsets:
        f.seek(0x2a5d000 + off)
        s = f.read(120).split(b'\x00')[0].decode('utf-8', errors='replace')
        print("0x%x: %s" % (0x2a5d000 + off, s))
