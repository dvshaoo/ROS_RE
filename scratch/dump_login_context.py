def dump_context(data, offset, radius=200):
    start = max(0, offset - radius)
    end = min(len(data), offset + radius)
    chunk = data[start:end]
    # Replace non-printable bytes with . or null with \0
    clean = ""
    for b in chunk:
        if 32 <= b <= 126:
            clean += chr(b)
        elif b == 0:
            clean += "\\0\n"
        else:
            clean += "."
    return clean

arm32_so = r'c:\Users\Raysoo\Downloads\ROS_RE\01_apk\base_decompiled\lib\armeabi-v7a\libclient.so'
with open(arm32_so, 'rb') as f:
    data32 = f.read()

print("--- ARM32 context at 0x59bcfa ---")
print(dump_context(data32, 0x59bcfa, 300))

print("--- ARM32 context at 0x21ff091 ---")
print(dump_context(data32, 0x21ff091, 300))

print("--- ARM32 context at 0x21ff24f (loginapp.pubkey) ---")
print(dump_context(data32, 0x21ff24f, 300))

arm64_so = r'c:\Users\Raysoo\Downloads\ROS_RE\03_lib\libclient_arm64.so'
with open(arm64_so, 'rb') as f:
    data64 = f.read()

print("--- ARM64 context at 0x2a493a7 (loginapp.pubkey) ---")
print(dump_context(data64, 0x2a493a7, 300))
