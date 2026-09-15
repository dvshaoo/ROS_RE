import subprocess
import time
import os
import sys

ADB = r"C:\LDPlayer\LDPlayer9\adb.exe"
PY = sys.executable
REPO = r"C:\Users\Raysoo\Downloads\ROS_RE"
CAPTURE_LOG = os.path.join(REPO, "mitm", "captures", "BASEAPP_LOGIN_CAPTURE.txt")

print("=== STARTING LOCAL_BASEAPP_CAPTURE TEST ===")
env = os.environ.copy()
env['BFKEY_HEX'] = 'b2525a3c'
env['BF_MODE'] = 'pc_variant'
env['ATTEMPT_I'] = '1'

# Truncate capture log
os.makedirs(os.path.dirname(CAPTURE_LOG), exist_ok=True)
with open(CAPTURE_LOG, 'w', encoding='utf-8') as f:
    f.write('=== TEST RUN START ===\n')

server = subprocess.Popen(
    [PY, os.path.join(REPO, "mitm", "local_baseapp_capture.py")],
    cwd=REPO,
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)

time.sleep(2)
print("Server launched (PID %d). Tapping PLAY (952, 800)..." % server.pid)

# Tap PLAY
subprocess.run([ADB, "-s", "emulator-5554", "shell", "input", "tap", "952", "800"], check=True)

print("Waiting 6 seconds for login flow...")
time.sleep(6)

# Read logcat
print("Fetching logcat...")
res = subprocess.run([ADB, "-s", "emulator-5554", "logcat", "-d", "-t", "100"], capture_output=True, text=True, errors='replace')
logcat_lines = res.stdout.splitlines()

print("\n--- RELEVANT LOGCAT LINES ---")
for line in logcat_lines:
    if any(k in line for k in ["checkScriptBaseAppAddr", "onLoginReply", "baseApp", "LoginHandler", "EncryptionFilter", "Mercury"]):
        print(line)

print("\n--- BASEAPP_LOGIN_CAPTURE.txt ---")
if os.path.exists(CAPTURE_LOG):
    with open(CAPTURE_LOG, 'r', encoding='utf-8', errors='replace') as f:
        print(f.read())

# Clean up
server.terminate()
try:
    server.wait(timeout=2)
except Exception:
    server.kill()

print("=== TEST FINISHED ===")
