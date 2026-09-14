arm64_so = r'c:\Users\Raysoo\Downloads\ROS_RE\03_lib\libclient_arm64.so'
with open(arm64_so, 'rb') as f:
    f.seek(0x2a47000)
    data = f.read(0x1000)

for s in data.split(b'\x00'):
    if len(s) > 1 and all(32 <= b <= 126 for b in s):
        print(s.decode('ascii'))
