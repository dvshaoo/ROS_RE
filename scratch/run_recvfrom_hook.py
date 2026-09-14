import frida, time, sys, binascii

dev = frida.get_device_manager().add_remote_device('127.0.0.1:27042')
sess = dev.attach(16332)
src = open('hook_recvfrom.js').read()
script = sess.create_script(src)

def onmsg(msg, data):
    if msg.get('type') == 'send':
        payload = msg.get('payload')
        if data:
            print(payload, '| hex:', binascii.hexlify(data).decode())
        else:
            print(payload)
    else:
        print('ERR', msg)

script.on('message', onmsg)
script.load()
print('loaded, watching for 25s...')
time.sleep(25)
