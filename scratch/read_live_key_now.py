import subprocess

ADB = r'C:\LDPlayer\LDPlayer9\adb.exe'
obj_va = 0x763838200000 + 308950128
skip_mb = obj_va // 1048576
local_off = obj_va % 1048576

import base64

cmd = [ADB, '-s', 'emulator-5554', 'shell', f'su 0 sh -c "dd if=/proc/18007/mem bs=1048576 skip={skip_mb} count=1 2>/dev/null | base64"']
b64_str = subprocess.run(cmd, capture_output=True).stdout.decode('ascii', errors='ignore')
data = base64.b64decode(b64_str.replace('\n', '').replace('\r', '').strip())

print('Downloaded bytes:', len(data))
pattern = bytes.fromhex('a093a90600000000')
idx = data.find(pattern)
print(f'data.find(pattern) = {idx} (expected local_off={local_off})')
if idx != -1:
    chunk = data[idx : idx + 64]
    print('Vtable at obj:', chunk[:8].hex())
    print('Raw 64 bytes:', chunk.hex())
    ctrl = chunk[0x10]
    length = ctrl >> 1
    key = chunk[0x11 : 0x11 + length]
    print(f'*** LIVE BLOWFISH KEY: {key.hex()} (ctrl=0x{ctrl:02x}, len={length}) ***')
else:
    print('Pattern not in this 1MB block, let us look nearby or find where it was!')

