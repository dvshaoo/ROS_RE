"""One-command live probe: build a stream variant, log in, wait for the Lobby, screenshot, summarise.

Usage: python scratch/lobby_probe.py <label> [comma,separated,xml-only,property,names]
  - no names        -> full XML defaults
  - names           -> XML defaults for those properties only (everything else as `min`)
  - the word 'MIN'  -> ROS_STREAM_DEFAULTS=min
Writes scratch/probe_<label>.png, scratch/probe_<label>_logcat.txt and prints an error summary.
Needs the private server already running (it re-reads data/athlete_mobile_stream.bin on every login).
"""
import os, re, subprocess, sys, time

ROOT = r'C:\Users\Raysoo\Downloads\ROS_RE'
PY = r'C:\Python314\python.exe'
ADB = [r'C:\Users\Raysoo\AppData\Local\Android\Sdk\platform-tools\adb.exe', '-s', 'emulator-5554']
label = sys.argv[1]
arg = sys.argv[2] if len(sys.argv) > 2 else ''

env = dict(os.environ)
env.pop('ROS_XML_ONLY', None)
if arg == 'MIN':
    env['ROS_STREAM_DEFAULTS'] = 'min'
elif arg:
    env['ROS_STREAM_DEFAULTS'] = 'xml'
    env['ROS_XML_ONLY'] = arg
else:
    env['ROS_STREAM_DEFAULTS'] = 'xml'

g = subprocess.run([PY, os.path.join(ROOT, 'scratch', 'gen_stream_v3.py')], env=env, capture_output=True, text=True)
print(g.stdout.strip().splitlines()[0], '|', [l for l in g.stdout.splitlines() if l.startswith('total')][0])

lc = os.path.join(ROOT, 'scratch', f'probe_{label}_logcat.txt')
d = subprocess.run([PY, os.path.join(ROOT, 'scratch', 'drive_login.py'), lc], capture_output=True, text=True)
print([l for l in d.stdout.splitlines() if l.startswith(('LOGIN OK', 'TIMED OUT'))])

# PROBE_DELAYS="70,60,60" -> screenshots after 70 s, then 60 s later, then 60 s later (default: one at 70 s).
# Several shots show whether a messy hall repairs itself over time WITHOUT any interaction.
delays = [int(x) for x in os.environ.get('PROBE_DELAYS', '70').split(',') if x]
shot = None
for k, dly in enumerate(delays):
    time.sleep(dly)
    shot = os.path.join(ROOT, 'scratch', f'probe_{label}' + (f'_t{k}' if len(delays) > 1 else '') + '.png')
    subprocess.run(ADB + ['shell', 'screencap -p /data/local/tmp/probe.png'], capture_output=True)
    subprocess.run(ADB + ['pull', '/data/local/tmp/probe.png', shot], capture_output=True)
    print('screenshot @+%ds:' % sum(delays[:k + 1]), shot, os.path.getsize(shot) if os.path.exists(shot) else 'MISSING')

t = open(lc, encoding='utf-8', errors='replace').read()
errs = {k: t.count(k) for k in ('SequenceDataType', 'PythonDataType', 'Could not create', 'still',
                                'Traceback', 'AttributeError', 'TypeError', 'Dropping packet')}
print('createBasePlayer lines:', t.count('createBasePlayer: id'), '| error counters:', {k: v for k, v in errs.items() if v})
