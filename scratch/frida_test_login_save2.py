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
    var fCls = 'com.netease.mpay.oversea.j.a.f';

    jdd.b.overload(fCls).implementation = function (info) {
        send("[j.d.d.b(f) CALLED]");
        dumpFields(info, "  arg");
        var ret;
        try {
            ret = this.b(info);
            send("[j.d.d.b(f) returned normally]");
        } catch (e) {
            send("[j.d.d.b(f) THREW] " + e);
            throw e;
        }
        return ret;
    };

    jdd.a.overload(fCls).implementation = function (info) {
        send("[j.d.d.a(f) CALLED]");
        dumpFields(info, "  arg");
        var ret = this.a(info);
        send("[j.d.d.a(f) returned normally]");
        return ret;
    };

    jdd.c.overload(fCls).implementation = function (info) {
        send("[j.d.d.c(f) private CALLED]");
        dumpFields(info, "  arg");
        var ret = this.c(info);
        send("[j.d.d.c(f) returned normally]");
        return ret;
    };

    jdd.g.overload().implementation = function () {
        var result = this.g();
        dumpFields(result, "[j.d.d.g() RESULT]");
        return result;
    };

    send("[all hooks installed]");

    setTimeout(function () {
        Java.perform(function () {
            try {
                Java.choose('com.netease.chiji.EmailAuthActivity', {
                    onMatch: function (instance) {
                        send("[found EmailAuthActivity instance] " + instance);
                        instance.onLoginSuccess("test-uid-999", "test-token-xyz", "TestNick2");
                        send("[called onLoginSuccess]");
                    },
                    onComplete: function () { send("[choose onComplete]"); }
                });
            } catch (e) {
                send("[choose error] " + e);
            }
        });
    }, 2000);
});
"""

script = session.create_script(src)
script.on("message", lambda msg, data: print(msg, flush=True))
script.load()
print("[attached pid=%d]" % pid, flush=True)
time.sleep(25)
