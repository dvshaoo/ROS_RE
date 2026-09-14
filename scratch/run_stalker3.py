import frida, time, json, subprocess

ADB = r'C:\LDPlayer\LDPlayer9\adb.exe'
PID = 16332
TARGET_TID = 16424

dev = frida.get_device_manager().add_remote_device('127.0.0.1:27042')
sess = dev.attach(PID)
src = open('stalker_login.js').read()
script = sess.create_script(src)
script.on('message', lambda msg, data: None)
script.load()

baseline = json.load(open('stalker_baseline.json'))
baseline_addrs = set(a for a, c in baseline['top'])

subprocess.run([ADB, '-s', 'emulator-5554', 'shell', 'logcat', '-c'])

slices = []
NUM_SLICES = 13
t0 = time.time()
script.exports_sync.start_follow(TARGET_TID)
time.sleep(0.3)
print('Tapping PLAY at t=', time.time() - t0)
subprocess.run([ADB, '-s', 'emulator-5554', 'shell', 'input', 'tap', '960', '795'])

for i in range(NUM_SLICES):
    time.sleep(1.0)
    rep = script.exports_sync.stop_follow()
    elapsed = time.time() - t0
    new_addrs = [(a, c) for a, c in rep['top'] if a not in baseline_addrs]
    slices.append({'slice': i, 't': elapsed, 'totalCalls': rep['totalCalls'], 'newAddrCount': len(new_addrs), 'newTop': sorted(new_addrs, key=lambda x: -x[1])[:8]})
    print(f"slice {i} t={elapsed:.2f} totalCalls={rep['totalCalls']} newAddrs={len(new_addrs)} top={slices[-1]['newTop'][:3]}")
    script.exports_sync.start_follow(TARGET_TID)

script.exports_sync.stop_follow()

logcat = subprocess.run([ADB, '-s', 'emulator-5554', 'logcat', '-d'], capture_output=True, text=True).stdout
with open('stalker_slices.json', 'w') as f:
    json.dump(slices, f, indent=2)
with open('stalker_slices_logcat.txt', 'w', encoding='utf-8') as f:
    f.write(logcat)

for line in logcat.splitlines():
    if 'logOnBegin' in line or 'logOnComplete' in line:
        print('LOGCAT:', line)
