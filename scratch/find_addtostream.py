import re

arm64_so = r'c:\Users\Raysoo\Downloads\ROS_RE\03_lib\libclient_arm64.so'
with open(arm64_so, 'rb') as f:
    data = f.read()

matches = re.findall(b'[_a-zA-Z0-9]*addToStream[_a-zA-Z0-9]*', data)
for m in sorted(set(matches)):
    print(m.decode('ascii', errors='ignore'))
