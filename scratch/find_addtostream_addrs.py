import re

arm64_so = r'c:\Users\Raysoo\Downloads\ROS_RE\03_lib\libclient_arm64.so'
with open(arm64_so, 'rb') as f:
    data = f.read()

for target in [b'addToStream', b'addToStreamCustom']:
    pos = 0
    while True:
        idx = data.find(target, pos)
        if idx == -1:
            break
        print(f"'{target.decode()}' at {hex(idx)}")
        pos = idx + len(target)
