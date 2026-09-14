import re

arm64_so = r'c:\Users\Raysoo\Downloads\ROS_RE\03_lib\libclient_arm64.so'
with open(arm64_so, 'rb') as f:
    data = f.read()

# Look for PyMethodDef tables or strings related to BigWorld methods:
# Commonly: "connect", "disconnect", "logOn", "server", "createEntity", etc.
bw_methods = []
matches = re.findall(b'BigWorld\\.([a-zA-Z0-9_]+)', data)
for m in matches:
    name = m.decode('ascii')
    if name not in bw_methods:
        bw_methods.append(name)

print(f"BigWorld methods with 'BigWorld.<name>' string ({len(bw_methods)}):")
for name in sorted(bw_methods):
    print(f"  BigWorld.{name}")

# Also let's search for ServerConnection methods
sc_methods = []
matches_sc = re.findall(b'ServerConnection::([a-zA-Z0-9_]+)', data)
for m in matches_sc:
    name = m.decode('ascii')
    if name not in sc_methods:
        sc_methods.append(name)

print(f"\nServerConnection methods ({len(sc_methods)}):")
for name in sorted(sc_methods):
    print(f"  ServerConnection::{name}")
