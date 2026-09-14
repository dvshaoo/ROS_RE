import re
import struct

arm64_so = r'c:\Users\Raysoo\Downloads\ROS_RE\03_lib\libclient_arm64.so'
with open(arm64_so, 'rb') as f:
    data = f.read()

# Let's search for "connect" or "logOn" or "login" as Python module function names
candidates = [b'connect', b'disconnect', b'logOn', b'logOff', b'server', b'login', b'doLogin', b'loginServer']
for c in candidates:
    pos = 0
    while True:
        idx = data.find(c, pos)
        if idx == -1:
            break
        # Check if null-terminated
        if data[idx-1:idx] == b'\x00' and data[idx+len(c):idx+len(c)+1] == b'\x00':
            print(f"Candidate exact string '{c.decode()}' at {hex(idx)}")
        pos = idx + len(c)
