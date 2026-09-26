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

    var jdd = Java.use('com.netease.mpay.oversea.j.d.d');
    jdd.g.overload().implementation = function () {
        var result = this.g();
        dumpFields(result, "[j.d.d.g() SILENT-RELOGIN LOAD]");
        return result;
    };

    Java.choose('com.netease.chiji.EmailAuthActivity', {
        onMatch: function (instance) {
            send("[found EmailAuthActivity] " + instance);
            instance.onLoginSuccess("verify-uid", "verify-token-final", "VerifyNick");
            send("[called onLoginSuccess -- watching for Launcher's own j.d.d.g() call]");
        },
        onComplete: function () { send("[choose onComplete]"); }
    });
});
"""

script = session.create_script(src)
script.on("message", lambda msg, data: print(msg, flush=True))
script.load()
print("[attached pid=%d]" % pid, flush=True)
time.sleep(30)
