import frida, time, json

PID = 16332
TARGET_TID = 16424

dev = frida.get_device_manager().add_remote_device('127.0.0.1:27042')
sess = dev.attach(PID)
src = open('stalker_compile_probe.js').read()
script = sess.create_script(src)
script.on('message', lambda msg, data: print('MSG:', msg))
script.load()

print('Starting compile-event follow for 3s (idle, no tap)...')
script.exports_sync.start_follow(TARGET_TID)
time.sleep(3)
report = script.exports_sync.stop_follow(TARGET_TID)
print('count=', report['count'])
for row in report['sample'][:30]:
    print(row)
with open('compile_probe_report.json', 'w') as f:
    json.dump(report, f, indent=2)
