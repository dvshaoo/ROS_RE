import frida, time, json, sys, subprocess, os

ADB = r'C:\LDPlayer\LDPlayer9\adb.exe'

PID = 16332
TARGET_TID = 16424

dev = frida.get_device_manager().add_remote_device('127.0.0.1:27042')
sess = dev.attach(PID)
src = open('stalker_login.js').read()
script = sess.create_script(src)
script.on('message', lambda msg, data: print('MSG:', msg))
script.load()

threads = script.exports_sync.list_threads()
print('thread count:', len(threads))
match = [t for t in threads if t['id'] == TARGET_TID]
print('target tid present:', bool(match), match)

if not match:
    print('TARGET_TID NOT FOUND, aborting')
    sys.exit(1)

print('Starting Stalker follow on tid', TARGET_TID)
script.exports_sync.start_follow(TARGET_TID)

time.sleep(2)
print('Tapping PLAY now...')
subprocess.run([ADB, '-s', 'emulator-5554', 'shell', 'input', 'tap', '960', '795'])

print('Waiting through login+timeout window (12s)...')
time.sleep(12)

print('Stopping follow, collecting report...')
report = script.exports_sync.stop_follow()
with open('stalker_report.json', 'w') as f:
    json.dump(report, f, indent=2)
print('totalCalls=', report['totalCalls'], 'uniqueTargets=', report['uniqueTargets'])
print('Top targets (first 30):')
for addr, cnt in report['top'][:30]:
    print(' ', addr, cnt)
print('Ranges touched:')
for r in report['ranges']:
    print(' ', r)
