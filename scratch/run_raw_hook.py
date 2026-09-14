import frida, time, binascii

dev = frida.get_device_manager().add_remote_device('127.0.0.1:27042')
sess = dev.attach(16332)
src = open('hook_recvfrom_raw.js').read()
script = sess.create_script(src)

def onmsg(msg, data):
    if msg.get('type') == 'send':
        payload = msg.get('payload')
        hexed = binascii.hexlify(data).decode() if data else ''
        print(payload, '| hex:', hexed[:600])
    else:
        print('ERR', msg)

script.on('message', onmsg)
script.load()
print('HOOK_READY')
import sys
sys.stdout.flush()
time.sleep(20)
print('DONE')
