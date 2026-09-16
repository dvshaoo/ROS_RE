import subprocess

ADB = r'C:\LDPlayer\LDPlayer9\adb.exe'

def run(cmd):
    p = subprocess.run([ADB, '-s', 'emulator-5554'] + cmd, capture_output=True, text=True)
    return p.stdout.strip()

print("PID of com.netease.chiji:", run(['shell', 'pidof', 'com.netease.chiji']))
windows = run(['shell', 'dumpsys', 'window', 'windows'])
for line in windows.splitlines():
    if 'mCurrentFocus' in line or 'mFocusedApp' in line:
        print(line.strip())
