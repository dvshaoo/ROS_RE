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

    var faBuilder = Java.use('com.netease.mpay.oversea.j.a.f$a');
    faBuilder.a.overload().implementation = function () {
        var result = this.a();
        dumpFields(result, "[f$a.a() BUILD RESULT]");
        return result;
    };

    var jdd = Java.use('com.netease.mpay.oversea.j.d.d');
    var jddMethods = jdd.class.getDeclaredMethods();
    var names = [];
    for (var i = 0; i < jddMethods.length; i++) names.push(jddMethods[i].toString());
    send("[j.d.d methods]\n" + names.join("\n"));

    setTimeout(function () {
        Java.perform(function () {
            try {
                Java.choose('com.netease.chiji.EmailAuthActivity', {
                    onMatch: function (instance) {
                        send("[found EmailAuthActivity instance] " + instance);
                        instance.onLoginSuccess("test-uid-123", "test-token-abc", "TestNick");
                        send("[called onLoginSuccess with test values]");
                    },
                    onComplete: function () {
                        send("[Java.choose onComplete]");
                    }
                });
            } catch (e) {
                send("[Java.choose error] " + e);
            }
        });
    }, 3000);
});
"""

script = session.create_script(src)
script.on("message", lambda msg, data: print(msg, flush=True))
script.load()
print("[attached pid=%d]" % pid, flush=True)
time.sleep(20)
