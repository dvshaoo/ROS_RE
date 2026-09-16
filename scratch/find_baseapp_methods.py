# Look for message registration in ClientApp / ServerConnection / Nub
# In Mercury, Nub::registerHandler( id, pHandler, name )
# Let's search strings in libclient.so for method names or interfaces
lib_path = r'c:\Users\Raysoo\Downloads\ROS_RE\01_apk\base_decompiled\lib\arm64-v8a\libclient.so'
with open(lib_path, 'rb') as f:
    data = f.read()

# Search for BaseAppExtInterface or ServerConnection method strings
pos = 0
while True:
    idx = data.find(b'BaseAppExtInterface', pos)
    if idx == -1:
        break
    print("Found BaseAppExtInterface at 0x%x" % idx)
    pos = idx + 1

pos = 0
while True:
    idx = data.find(b'baseAppLogin', pos)
    if idx == -1:
        break
    print("Found baseAppLogin at 0x%x" % idx)
    pos = idx + 1
