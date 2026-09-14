import frida, time, json, sys, subprocess

ADB = r'C:\LDPlayer\LDPlayer9\adb.exe'
PID = 16332
TARGET_TID = 16424

dev = frida.get_device_manager().add_remote_device('127.0.0.1:27042')
sess = dev.attach(PID)
src = open('stalker_login.js').read()
script = sess.create_script(src)
script.on('message', lambda msg, data: None)
script.load()

print('=== Capturing BASELINE (idle, 3s) ===')
script.exports_sync.start_follow(TARGET_TID)
time.sleep(3)
baseline = script.exports_sync.stop_follow()
with open('stalker_baseline.json', 'w') as f:
    json.dump(baseline, f, indent=2)
print('baseline totalCalls=', baseline['totalCalls'], 'uniqueTargets=', baseline['uniqueTargets'])

time.sleep(1)

print('=== Capturing ACTIVE (tap PLAY, 12s) ===')
script.exports_sync.start_follow(TARGET_TID)
subprocess.run([ADB, '-s', 'emulator-5554', 'shell', 'input', 'tap', '960', '795'])
time.sleep(12)
active = script.exports_sync.stop_follow()
with open('stalker_active.json', 'w') as f:
    json.dump(active, f, indent=2)
print('active totalCalls=', active['totalCalls'], 'uniqueTargets=', active['uniqueTargets'])

baseline_addrs = set(a for a, c in baseline['top'])
# baseline['top'] only has top 60; need full set - let's also dump full summary by re-requesting
# (top list is truncated at 60, so we approximate: any active addr not seen at all in baseline's full set)
print('Note: comparing against baseline top-60 only (approximation)')
active_sorted = active['top']
new_only = [(a, c) for a, c in active_sorted if a not in baseline_addrs]
print('Active top targets NOT in baseline top-60 (candidate login-specific addresses):')
for a, c in new_only[:40]:
    print(' ', a, c)
