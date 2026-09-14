import frida, time, json, subprocess

ADB = r'C:\LDPlayer\LDPlayer9\adb.exe'
PID = 16332
TARGET_TID = 16424

dev = frida.get_device_manager().add_remote_device('127.0.0.1:27042')
sess = dev.attach(PID)
src = open('stalker_compile_slices.js').read()
script = sess.create_script(src)
script.on('message', lambda msg, data: None)
script.load()

subprocess.run([ADB, '-s', 'emulator-5554', 'shell', 'logcat', '-c'])

slices = []
t0 = time.time()
script.exports_sync.reset()
script.exports_sync.start_follow(TARGET_TID)
time.sleep(0.3)
print('Tapping PLAY at t=', time.time() - t0)
subprocess.run([ADB, '-s', 'emulator-5554', 'shell', 'input', 'tap', '960', '795'])

for i in range(11):
    time.sleep(1.0)
    snap = script.exports_sync.stop_follow(TARGET_TID)
    elapsed = time.time() - t0
    slices.append({'slice': i, 't': round(elapsed, 2), 'counts': snap})
    print(f"slice {i} t={elapsed:.2f}", snap)
    script.exports_sync.reset()
    script.exports_sync.start_follow(TARGET_TID)

script.exports_sync.stop_follow(TARGET_TID)

logcat = subprocess.run([ADB, '-s', 'emulator-5554', 'logcat', '-d'], capture_output=True, text=True).stdout
with open('compile_slices.json', 'w') as f:
    json.dump(slices, f, indent=2)
for line in logcat.splitlines():
    if 'logOnBegin' in line or 'logOnComplete' in line:
        print('LOGCAT:', line)
