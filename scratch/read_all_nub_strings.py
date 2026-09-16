lib_path = r'c:\Users\Raysoo\Downloads\ROS_RE\01_apk\base_decompiled\lib\arm64-v8a\libclient.so'
with open(lib_path, 'rb') as f:
    f.seek(0x2a5d000)
    data = f.read(0x1000)
    for part in data.split(b'\x00'):
        if b'Nub::processFilteredPacket' in part or b'Packet' in part or b'Channel' in part or b'FLAG' in part:
            print(part.decode('utf-8', errors='replace').strip())
