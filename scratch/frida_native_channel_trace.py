import frida, sys, time

device = frida.get_usb_device(timeout=10)
pid = int(sys.argv[1])
session = device.attach(pid)

# Offsets found via Ghidra static analysis of libclient_arm64.so (Checkpoint 26):
#   get_auth_type      @ 0x00973ffc  (native PyMethodDef "get_auth_type")
#   get_auth_type_name @ 0x00974020
#   guest_bind         @ 0x009740f8
src = r"""
function waitForModuleAndHook() {
    var base = Module.findBaseAddress('libclient.so');
    if (base === null) {
        send('[waiting for libclient.so to load...]');
        setTimeout(waitForModuleAndHook, 300);
        return;
    }
    send('[libclient.so base] ' + base);
    installHooks(base);
}

function installHooks(base) {
var offsets = {
    'get_auth_type': 0x973ffc,
    'get_auth_type_name': 0x974020,
    'guest_bind': 0x9740f8
};

for (var name in offsets) {
    (function (name, off) {
        var addr = base.add(off);
        try {
            Interceptor.attach(addr, {
                onEnter: function (args) {
                    var param1 = args[0];
                    var vtablePtrAt0x10 = "?";
                    try {
                        var innerPtr = Memory.readPointer(param1.add(0x10));
                        vtablePtrAt0x10 = innerPtr.isNull() ? "NULL" : innerPtr.toString();
                    } catch (e) {
                        vtablePtrAt0x10 = "READ_ERR:" + e;
                    }
                    send('[' + name + ' ENTER] t=' + Date.now() + ' param1=' + param1 + ' *(param1+0x10)=' + vtablePtrAt0x10);
                },
                onLeave: function (retval) {
                    send('[' + name + ' LEAVE] t=' + Date.now() + ' retval=' + retval);
                }
            });
            send('[hooked] ' + name + ' @ ' + addr);
        } catch (e) {
            send('[hook FAILED] ' + name + ': ' + e);
        }
    })(name, offsets[name]);
}
}

waitForModuleAndHook();
"""

script = session.create_script(src)
script.on("message", lambda msg, data: print(msg, flush=True))
script.load()
print("[attached pid=%d, watching 90s]" % pid, flush=True)
time.sleep(90)
