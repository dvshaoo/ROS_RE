lib_path = r'c:\Users\Raysoo\Downloads\ROS_RE\01_apk\base_decompiled\lib\arm64-v8a\libclient.so'
with open(lib_path, 'rb') as f:
    f.seek(0x2a4a280)
    chunk = f.read(0x600)
    for s in chunk.split(b'\x00'):
        if s:
            print(s.decode('utf-8', errors='replace'))
