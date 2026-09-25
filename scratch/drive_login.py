"""Drive the client from launch to a BaseApp login, retrying the taps until the
server actually reports a new createBasePlayer.

The Events popup appears at an unpredictable time after the title screen, so a fixed
tap schedule misses often. This polls the server log for a new
"loaded N bytes from athlete_mobile_stream.bin" line and keeps tapping until it lands.

Usage: python scratch/drive_login.py [logcat_out_path]
"""
import subprocess, sys, time, os, re

ADB = [os.environ.get('ADB_PATH', r'C:\Users\Raysoo\AppData\Local\Android\Sdk\platform-tools\adb.exe'),
       '-s', os.environ.get('DEVICE_SERIAL', 'emulator-5554')]
ROOT = r'C:\Users\Raysoo\Downloads\ROS_RE'
SERVER_LOG = os.environ.get('ROS_SERVER_LOG', os.path.join(ROOT, 'scratch', 'server_cell_stream_test.out'))
LOGCAT_OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'scratch', 'live_logcat_stream1585.txt')

DISMISS_SLOW = (951, 701)     # "Slow connection" confirm
CLOSE_EVENTS = (1845, 105)    # Events popup X (exact measured)
PLAY = (960, 740)             # PLAY center
PLAY_ALT = (900, 800)         # PLAY alternate


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
        # The log is UTF-16LE when the server was started with Windows PowerShell 5.1's
        # `>` redirection and UTF-8 otherwise; decoding it with the wrong one finds no
        # matches, so the driver kept re-tapping after a login had already succeeded.
        with open(SERVER_LOG, 'rb') as f:
            raw = f.read()
        text = raw.decode('utf-16le' if b'\x00' in raw[:400] else 'utf-8', errors='replace')
        hits = [l for l in text.splitlines() if 'from athlete_mobile_stream.bin' in l]
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
        for xy in (DISMISS_SLOW, CLOSE_EVENTS, PLAY, PLAY_ALT):
            tap(xy)
            time.sleep(1.5)
        time.sleep(5)
        cur = last_load()
        if cur and cur != baseline:
            print(f'LOGIN OK after {attempt} attempt(s): {cur}')
            print('Waiting 25s for entity lifecycle & lobby load...')
            time.sleep(25)
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

# Save final screenshot
try:
    data = subprocess.run(ADB + ['exec-out', 'screencap', '-p'], capture_output=True, timeout=10).stdout
    if data:
        with open(os.path.join(ROOT, 'scratch', 'current_screen.png'), 'wb') as f:
            f.write(data)
        print('Saved screenshot scratch/current_screen.png (%d bytes)' % len(data))
except Exception as e:
    print('Error saving screencap:', e)

print('logcat ->', LOGCAT_OUT, os.path.getsize(LOGCAT_OUT), 'bytes')

# Analyze logcat
try:
    lines = open(LOGCAT_OUT, 'r', encoding='utf-8', errors='replace').readlines()
    keywords = ['createBasePlayer', 'createCellPlayer', 'iWeekendPush', 'weekendPush',
                'newYearGoal', 'childBaseClientProperty', 'SequenceDataType',
                'Invalid size', 'Traceback', 'TypeError', 'AttributeError',
                'showSelectCharacter', 'enterHall', 'athleteEnterHall',
                'Login Succ', 'remain', 'MemoryIStream', 'onRoleCreateSuc']
    print('\n=== KEY LOGCAT EVENTS ===')
    for line in lines:
        if any(k in line for k in keywords):
            print(line.strip()[:140])
except Exception as e:
    print('Error reading logcat:', e)
