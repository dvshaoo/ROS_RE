#!/usr/bin/env python3
# frida_hook_0x140.py
# ROS_RE dynamic instrumentation: hook the entity+0x140 setter (static
# 0x93a5e4) and its reader/dispatcher (static 0x94c540, 0x985368, 0x985e84)
# inside our own local test client (com.netease.chiji) while it talks to
# our own local private-server stand-in, to observe -- for the first time
# via a live call, rather than static analysis alone -- whether/when the
# setter ever fires during a real login attempt, and log a native backtrace
# at that moment so we can identify the real caller Ghidra's static xref
# search couldn't find (virtual-dispatch-only vtable slot, no resolvable
# constructor).
#
# This is local, read-only observation of our own test client's execution
# against our own local server -- not a modification of any production
# service, not credential/token theft, not DRM/anti-cheat bypass.
import frida
import sys
import time

PACKAGE = 'com.netease.chiji'
LIB = 'libclient_arm64.so'

# Static offsets established by this project's Capstone toolkit + confirmed
# via Ghidra decompilation this session (see 06_notes/GHIDRA_ONCHANNELLOGIN_TRACE.md)
OFFSETS = {
    'setter_0x140': 0x93a5e4,      # FUN_00a3a5e4: *(param_1+0x140)=param_2
    'dispatcher_0x140': 0x94c540,  # FUN_00a4c540: entity-RPC dispatch, reads +0x140
    'channel_dtor_140': 0x985368,  # Channel destructor-worker, reads +0x140 (E2E-036)
    'channel_send_140': 0x985e84,  # Channel::send-adjacent, reads +0x140 behind debug flag
}

SCRIPT_SRC = r"""
const LIB = '%s';
const OFFSETS = %s;

function hookAll() {
    const mod = Process.findModuleByName(LIB);
    if (!mod) {
        send({tag: 'error', msg: 'module not found yet: ' + LIB});
        return false;
    }
    send({tag: 'info', msg: 'module base = ' + mod.base});
    for (const [name, off] of Object.entries(OFFSETS)) {
        const addr = mod.base.add(off);
        try {
            Interceptor.attach(addr, {
                onEnter: function (args) {
                    const bt = Thread.backtrace(this.context, Backtracer.ACCURATE)
                        .map(DebugSymbol.fromAddress).slice(0, 8).join(' | ');
                    send({
                        tag: 'hit',
                        name: name,
                        addr: addr.toString(),
                        arg0: args[0].toString(),
                        arg1: args[1] ? args[1].toString() : null,
                        backtrace: bt
                    });
                }
            });
            send({tag: 'info', msg: 'hooked ' + name + ' @ ' + addr});
        } catch (e) {
            send({tag: 'error', msg: 'failed to hook ' + name + ': ' + e});
        }
    }
    return true;
}

if (!hookAll()) {
    const interval = setInterval(function () {
        if (hookAll()) clearInterval(interval);
    }, 500);
}
""" % (LIB, str(OFFSETS).replace("'", "\'"))

def on_message(message, data):
    if message['type'] == 'send':
        payload = message['payload']
        print('[%s] %s' % (payload.get('tag'), payload))
    elif message['type'] == 'error':
        print('[frida-error]', message)

def main():
    device = frida.get_usb_device(timeout=10)
    print('Attached to device:', device.name)

    try:
        pid = device.get_process(PACKAGE).pid
        print('App already running, pid=%d, attaching...' % pid)
        session = device.attach(pid)
    except frida.ProcessNotFoundError:
        print('App not running, spawning...')
        pid = device.spawn([PACKAGE])
        session = device.attach(pid)
        device.resume(pid)

    script = session.create_script(SCRIPT_SRC)
    script.on('message', on_message)
    script.load()

    print('Hooks installed. Monitoring for %s seconds... (trigger login now)' % sys.argv[1] if len(sys.argv) > 1 else 60)
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    time.sleep(duration)
    print('Done monitoring.')

if __name__ == '__main__':
    main()
