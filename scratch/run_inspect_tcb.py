import frida, binascii

PID = 16332
dev = frida.get_device_manager().add_remote_device('127.0.0.1:27042')
sess = dev.attach(PID)
src = open('inspect_tcb_block.js').read()
script = sess.create_script(src)
script.on('message', lambda msg, data: print('MSG:', msg))
script.load()

# a libtcb.so block addr observed from the compile probe
addrs = ['0xd26ebca', '0xd2f2394', '0xdd1923d', '0xe85e0c0']
for a in addrs:
    mod = script.exports_sync.find_module(a)
    print(a, '->', mod)

print()
report = script.exports_sync.dump('0xd26ebca', 256, 32)
print('candidates (looks-like-ARM64-libclient-address, within +-256 bytes):')
for c in report.get('candidates', []):
    print(' ', c)
