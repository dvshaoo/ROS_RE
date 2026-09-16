with open(r'c:\Users\Raysoo\Downloads\ROS_RE\mitm\captures\BASEAPP_LOGIN_CAPTURE.txt', 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

for i, line in enumerate(lines[-200:]):
    if 'BASEAPP UDP RECV' in line or 'DECRYPTED' in line or 'HEX' in line:
        print(line.strip())
