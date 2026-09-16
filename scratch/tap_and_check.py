import subprocess
import time

ADB = r'C:\LDPlayer\LDPlayer9\adb.exe'

def run(cmd, timeout=10):
    p = subprocess.run([ADB, '-s', 'emulator-5554'] + cmd, capture_output=True, text=True, timeout=timeout)
    return p.stdout

print("Tapping at 955 795...")
run(['shell', 'input', 'tap', '955', '795'])
time.sleep(1)

log = run(['logcat', '-d', '-t', '50'])
for line in log.splitlines():
    if any(k in line for k in ['chiji', 'ServerConnection', 'LoginHandler', 'Mercury', 'Channel', 'Nub']):
        print(line)
