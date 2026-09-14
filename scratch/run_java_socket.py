import frida, time, subprocess

ADB = r'C:\LDPlayer\LDPlayer9\adb.exe'
PID = 16332

dev = frida.get_device_manager().add_remote_device('127.0.0.1:27042')
sess = dev.attach(PID)
src = open('hook_java_socket.js').read()
script = sess.create_script(src)
script.on('message', lambda msg, data: print('MSG:', msg))
script.load()

time.sleep(1)
print('Tapping PLAY...')
subprocess.run([ADB, '-s', 'emulator-5554', 'shell', 'input', 'tap', '960', '795'])
print('Waiting 12s...')
time.sleep(12)
print('done')
