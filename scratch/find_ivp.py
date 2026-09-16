lib_path = r'c:\Users\Raysoo\Downloads\ROS_RE\01_apk\base_decompiled\lib\arm64-v8a\libclient.so'
with open(lib_path, 'rb') as f:
    data = f.read()

# Search for xrefs to string "identifyVersionPoint"
str_off = 0x2a4a350 # or wherever identifyVersionPoint is
str_bytes = b'identifyVersionPoint'
pos = data.find(str_bytes)
print("String at 0x%x" % pos)

# Find references to this string in .rodata / .data / code
import struct
pattern = struct.pack('<Q', pos)
for i in range(0, len(data) - 8, 4):
    if data[i:i+8] == pattern:
        print("Pointer at 0x%x" % i)
