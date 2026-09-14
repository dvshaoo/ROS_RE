# -*- coding: utf-8 -*-
# frida_run.py -- attach to running game, load JS, log messages to file. Usage:
#   python frida_run.py <pid> <script.js> <outfile>
import sys, time
import frida

pid = int(sys.argv[1])
js = sys.argv[2]
out = sys.argv[3]
f = open(out, 'a', encoding='utf-8', errors='replace')

def on_msg(msg, data):
    try:
        if msg.get('type') == 'send':
            line = str(msg.get('payload'))[:300]
        else:
            line = 'META: %s' % str(msg)[:300]
        print(line, flush=True)
        f.write(line + '\n')
        f.flush()
    except Exception as e:
        print('LOG-ERR %s' % e, flush=True)

dev = frida.get_device_manager().get_device('emulator-5554')
proc = dev.attach(pid)
src = open(js, encoding='utf-8', errors='replace').read()
script = proc.create_script(src)
script.on('message', on_msg)
script.load()
print('HOOK-LOADED pid=%d js=%s' % (pid, js), flush=True)
try:
    time.sleep(int(sys.argv[4]) if len(sys.argv) > 4 else 60)
except KeyboardInterrupt:
    pass
print('HOOK-DONE', flush=True)
