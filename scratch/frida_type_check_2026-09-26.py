import frida
import time

device = frida.get_usb_device(timeout=10)

src = r"""
Java.perform(function () {
    var l = Java.use('com.netease.mpay.oversea.ui.l');
    var jdd = Java.use('com.netease.mpay.oversea.j.d.d');

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

    l.b.overload('com.netease.mpay.oversea.thirdapi.g').implementation = function (g_arg) {
        dumpFields(this, "[ui.l.b ENTRY] this(l instance)");
        var result = this.b(g_arg);
        dumpFields(result, "[ui.l.b RESULT] b/c object");
        return result;
    };

    jdd.g.overload().implementation = function () {
        var result = this.g();
        try {
            if (result === null) {
                send("[j.d.d.g()] returned null (no saved session)");
            } else {
                var cls = result.getClass();
                var fields = cls.getDeclaredFields();
                var out = "[j.d.d.g()] LoginInfo class=" + cls.getName() + " fields:\n";
                for (var i = 0; i < fields.length; i++) {
                    var f = fields[i];
                    f.setAccessible(true);
                    var name = f.getName();
                    var val;
                    try {
                        val = f.get(result);
                        val = val === null ? "null" : val.toString();
                    } catch (e2) {
                        val = "ERR:" + e2;
                    }
                    out += "  " + name + " = " + val + "\n";
                }
                send(out);
            }
        } catch (e) {
            send("[j.d.d.g()] error reading result: " + e);
        }
        return result;
    };

    send("[hooks installed]");
});
"""

def on_message(msg, data):
    print(msg, flush=True)

import sys
pid = int(sys.argv[1])
session = device.attach(pid)
script = session.create_script(src)
script.on("message", on_message)
script.load()
print("[attached pid=%d, watching 60s]" % pid, flush=True)
time.sleep(60)
