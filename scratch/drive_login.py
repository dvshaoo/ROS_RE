"""Drive the client from launch to a BaseApp login, retrying the taps until the
server actually reports a new createBasePlayer.

The Events popup appears at an unpredictable time after the title screen, so a fixed
tap schedule misses often. This polls the server log for a new
"loaded N bytes from athlete_mobile_stream.bin" line and keeps tapping until it lands.

Usage: python scratch/drive_login.py [logcat_out_path]
"""
import subprocess, sys, time, os, re

ADB = [r'C:\LDPlayer\LDPlayer9\adb.exe', '-s', 'emulator-5554']
ROOT = r'C:\Users\Raysoo\Downloads\ROS_RE'
SERVER_LOG = os.path.join(ROOT, 'scratch', 'server_stream_test2.out')
LOGCAT_OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'scratch', 'lc_drive.txt')

DISMISS_SLOW = (951, 701)     # "Slow connection" confirm
CLOSE_EVENTS = (1841, 108)    # Events popup X
PLAY = (900, 800)


def sh(*args, t=25):
    try:
        return subprocess.run(ADB + list(args), capture_output=True, text=True,
                              timeout=t).stdout
    except subprocess.TimeoutExpired:
        return ''


def tap(xy):
    sh('shell', 'input', 'tap', str(xy[0]), str(xy[1]))


def last_load():
    """Most recent stream-load line the server emitted."""
    try:
        with open(SERVER_LOG, 'r', errors='replace') as f:
            hits = [l for l in f if 'from athlete_mobile_stream.bin' in l]
        return hits[-1].strip() if hits else ''
    except OSError:
        return ''


baseline = last_load()
print('baseline:', baseline or '(none)')

sh('logcat', '-c')
sh('shell', 'am', 'force-stop', 'com.netease.chiji')
time.sleep(3)
sh('shell', 'monkey', '-p', 'com.netease.chiji', '1')

log = subprocess.Popen(ADB + ['logcat'], stdout=open(LOGCAT_OUT, 'w'),
                       stderr=subprocess.STDOUT)
print('launched; waiting for title screen...')
time.sleep(45)

deadline = time.time() + 150
attempt = 0
try:
    while time.time() < deadline:
        attempt += 1
        for xy in (DISMISS_SLOW, CLOSE_EVENTS, PLAY):
            tap(xy)
            time.sleep(2)
        time.sleep(6)
        cur = last_load()
        if cur and cur != baseline:
            print(f'LOGIN OK after {attempt} attempt(s): {cur}')
            time.sleep(30)          # let the entity lifecycle finish
            break
        print(f'  attempt {attempt}: no login yet')
    else:
        print('TIMED OUT without a login')
finally:
    time.sleep(2)
    log.terminate()
    try:
        log.wait(timeout=10)
    except Exception:
        log.kill()

print('logcat ->', LOGCAT_OUT, os.path.getsize(LOGCAT_OUT), 'bytes')
