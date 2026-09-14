import re

arm64_so = r'c:\Users\Raysoo\Downloads\ROS_RE\03_lib\libclient_arm64.so'
with open(arm64_so, 'rb') as f:
    f.seek(0x2a46000)
    chunk = f.read(0x6000)

strings = re.findall(b'[\x20-\x7e]{4,}', chunk)
print(f"Total strings found in 0x2a46000 - 0x2a4c000: {len(strings)}")
for s in strings:
    s_dec = s.decode('ascii', errors='ignore')
    if any(k in s_dec for k in ['ServerConnection', 'Login', 'Mercury', 'BaseApp', 'CellApp', 'Entity', 'pubkey', 'Stream', 'Packet', 'logOn', 'Nub', 'Channel', 'Session', 'Account', 'Avatar']):
        print(f"  {s_dec}")
