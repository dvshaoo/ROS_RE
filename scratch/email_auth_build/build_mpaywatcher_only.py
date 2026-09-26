import os
import sys
import glob
import shutil
import subprocess

REPO = r'C:\Users\Raysoo\Downloads\ROS_RE'
BUILD_DIR = os.path.join(REPO, 'scratch', 'email_auth_build')
ANDROID_JAR = r'C:\Users\Raysoo\AppData\Local\Android\Sdk\platforms\android-34\android.jar'
D8 = r'C:\Users\Raysoo\AppData\Local\Android\Sdk\build-tools\34.0.0\d8.bat'
APKTOOL = os.path.join(REPO, 'tools', 'apktool.jar')
DECOMPILED2_CHIJI = os.path.join(REPO, '.claude', 'worktrees', 'agent-a26a6b361cc71d3b5', 'scratch', 'apk_work', 'decompiled2', 'smali_classes4', 'com', 'netease', 'chiji')

out_dir = os.path.join(BUILD_DIR, 'out_watcher')
shutil.rmtree(out_dir, ignore_errors=True)
os.makedirs(out_dir, exist_ok=True)
java_files = [os.path.join(BUILD_DIR, 'src', 'MpayWatcherService.java')]
print('[1/5] Compiling Java source (MpayWatcherService only)...')
cmd = ['javac', '-source', '8', '-target', '8', '-cp', ANDROID_JAR, '-d', out_dir] + java_files
res = subprocess.run(cmd, capture_output=True, text=True)
print(res.stdout, res.stderr)
if res.returncode != 0:
    sys.exit(1)

driver_out = os.path.join(BUILD_DIR, 'driver_out')
os.makedirs(driver_out, exist_ok=True)
cmd = ['javac', '-cp', APKTOOL, '-d', driver_out, os.path.join(BUILD_DIR, 'BaksmaliDriver.java')]
res = subprocess.run(cmd, capture_output=True, text=True)
if res.returncode != 0:
    print(res.stdout, res.stderr)
    sys.exit(1)

print('[3/5] Dexing with d8...')
dex_out = os.path.join(BUILD_DIR, 'dex_out_watcher')
shutil.rmtree(dex_out, ignore_errors=True)
os.makedirs(dex_out, exist_ok=True)
class_files = []
for root, dirs, files in os.walk(out_dir):
    for f in files:
        if f.endswith('.class'):
            class_files.append(os.path.join(root, f))
cmd = [D8, '--output', dex_out] + class_files
res = subprocess.run(cmd, capture_output=True, text=True)
print(res.stdout, res.stderr)
if res.returncode != 0:
    sys.exit(1)

print('[4/5] Disassembling with BaksmaliDriver...')
smali_out = os.path.join(BUILD_DIR, 'smali_out_watcher')
shutil.rmtree(smali_out, ignore_errors=True)
os.makedirs(smali_out, exist_ok=True)
dex_file = os.path.join(dex_out, 'classes.dex')
cp = f"{driver_out};{APKTOOL}"
cmd = ['java', '-cp', cp, 'BaksmaliDriver', dex_file, smali_out]
res = subprocess.run(cmd, capture_output=True, text=True)
print(res.stdout, res.stderr)
if res.returncode != 0:
    sys.exit(1)

print('[5/5] Copying smali to decompiled2...')
gen_chiji = os.path.join(smali_out, 'com', 'netease', 'chiji')
os.makedirs(DECOMPILED2_CHIJI, exist_ok=True)
copied = 0
for f in os.listdir(gen_chiji):
    shutil.copy2(os.path.join(gen_chiji, f), os.path.join(DECOMPILED2_CHIJI, f))
    copied += 1
    print(f'  Copied {f}')
print(f'Done! Copied {copied} files.')
