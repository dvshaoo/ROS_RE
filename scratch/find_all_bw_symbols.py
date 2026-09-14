import re

arm64_so = r'c:\Users\Raysoo\Downloads\ROS_RE\03_lib\libclient_arm64.so'
with open(arm64_so, 'rb') as f:
    data = f.read()

# Search for mangled names starting with _Z or N4neox or ZN4neox
mangled = re.findall(b'[_a-zA-Z0-9]{10,}', data)

bw_mangled = []
for m in mangled:
    if b'neox8bwclient' in m or b'Mercury' in m or b'ServerConnection' in m or b'BaseApp' in m or b'LoginHandler' in m:
        if m not in bw_mangled:
            bw_mangled.append(m)

print(f"Total relevant symbols found: {len(bw_mangled)}")
for m in bw_mangled[:60]:
    try:
        print(" ", m.decode('ascii'))
    except:
        pass
