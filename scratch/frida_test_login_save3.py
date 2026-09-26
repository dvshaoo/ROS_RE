import frida, sys, time

device = frida.get_usb_device(timeout=10)
pid = int(sys.argv[1])
session = device.attach(pid)

src = r"""
Java.perform(function () {
    function dumpFields(obj, label) {
        try {
            if (obj === null) { send(label + " = null"); return; }
            var cls = obj.getClass();
            var fields = cls.getDeclaredFields();
            var out = label + " class=" + cls.getName() + "\n";
            for (var i = 0; i < fields.length; i++) {
                var f = fields[i];
                f.setAccessible(true);
                var name = f.getName();
                var val;
                try {
                    val = f.get(obj);
                    val = val === null ? "null" : val.toString();
                } catch (e2) { val = "ERR:" + e2; }
                out += "  " + name + " = " + val + "\n";
            }
            send(out);
        } catch (e) {
            send(label + " dump error: " + e);
        }
    }

    var gcCls = Java.use('com.netease.mpay.oversea.g.c');
    var jddCls = Java.use('com.netease.mpay.oversea.j.d.d');
    var jbCls = Java.use('com.netease.mpay.oversea.j.b');

    setTimeout(function () {
        Java.perform(function () {
            try {
                var gc = gcCls.b();
                var appId = gc.q();
                send("[GameConfig.q() appId] = '" + appId + "'");
            } catch (e) {
                send("[GameConfig error] " + e);
            }

            Java.choose('com.netease.chiji.EmailAuthActivity', {
                onMatch: function (instance) {
                    send("[found EmailAuthActivity instance] " + instance);
                    instance.onLoginSuccess("test-uid-777", "test-token-777", "TestNick3");
                    send("[called onLoginSuccess]");

                    setTimeout(function () {
                        Java.perform(function () {
                            try {
                                var gc = gcCls.b();
                                var appId = gc.q();
                                var jb = jbCls.$new(instance, appId);
                                var jdd = jb.a();
                                var loaded = jdd.g();
                                dumpFields(loaded, "[RELOAD via jdd.g() same appId='" + appId + "']");
                            } catch (e) {
                                send("[reload error] " + e);
                            }
                        });
                    }, 1000);
                },
                onComplete: function () { send("[choose onComplete]"); }
            });
        });
    }, 2000);

    send("[setup done]");
});
"""

script = session.create_script(src)
script.on("message", lambda msg, data: print(msg, flush=True))
script.load()
print("[attached pid=%d]" % pid, flush=True)
time.sleep(20)
