import frida, sys, time

device = frida.get_usb_device(timeout=10)
pid = int(sys.argv[1])
session = device.attach(pid)

src = r"""
Java.perform(function () {
    var fa = Java.use('com.netease.mpay.oversea.j.a.f$a');
    var cls = fa.class;

    send("=== f$a fields ===");
    var fields = cls.getDeclaredFields();
    for (var i = 0; i < fields.length; i++) {
        send(fields[i].toString());
    }

    send("=== f$a constructors ===");
    var ctors = cls.getDeclaredConstructors();
    for (var i = 0; i < ctors.length; i++) {
        send(ctors[i].toString());
    }

    send("=== f$a methods (non-inherited) ===");
    var methods = cls.getDeclaredMethods();
    for (var i = 0; i < methods.length; i++) {
        send(methods[i].toString());
    }

    var f = Java.use('com.netease.mpay.oversea.j.a.f');
    var fcls = f.class;
    send("=== f fields ===");
    var ffields = fcls.getDeclaredFields();
    for (var i = 0; i < ffields.length; i++) {
        send(ffields[i].toString());
    }
    send("=== f constructors ===");
    var fctors = fcls.getDeclaredConstructors();
    for (var i = 0; i < fctors.length; i++) {
        send(fctors[i].toString());
    }
});
"""

script = session.create_script(src)
script.on("message", lambda msg, data: print(msg, flush=True))
script.load()
time.sleep(5)
