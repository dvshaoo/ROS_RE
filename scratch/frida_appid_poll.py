import frida, sys, time

device = frida.get_usb_device(timeout=10)
pid = int(sys.argv[1])
session = device.attach(pid)

src = r"""
Java.perform(function () {
    var gcCls = Java.use('com.netease.mpay.oversea.g.c');
    var count = 0;
    var iv = setInterval(function () {
        Java.perform(function () {
            try {
                var gc = gcCls.b();
                var appId = gc.q();
                send("[t=" + (count) + "s] GameConfig.q() = '" + appId + "'");
            } catch (e) {
                send("[t=" + (count) + "s] error: " + e);
            }
        });
        count += 1;
        if (count > 20) clearInterval(iv);
    }, 1000);
});
"""

script = session.create_script(src)
script.on("message", lambda msg, data: print(msg, flush=True))
script.load()
print("[attached pid=%d]" % pid, flush=True)
time.sleep(22)
