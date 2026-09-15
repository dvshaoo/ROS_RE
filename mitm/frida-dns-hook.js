// frida-dns-hook.js -- REPURPOSED this pass (2026-09-15) for the reply-ID
// correlation investigation. Original DNS-hook content superseded; this now
// hooks Mercury::Nub::handleMessage (file offset 0x991e38 in libclient.so,
// per 06_trace/MERCURY_REPLY_ID_TRACE.md ss3) IN-PROCESS via frida-gadget,
// avoiding the external ptrace/frida-server attach path that this session
// found blocked/crashing against this specific process.
try {
    send('=== frida-dns-hook.js (repurposed: Nub::handleMessage tracer) loading ===');
    var mod = Process.findModuleByName('libclient.so');
    if (!mod) {
        send('ERROR: libclient.so not found in this process');
    } else {
        send('libclient.so base = ' + mod.base + ' size=' + mod.size);
        var target = mod.base.add(0x991e38);
        send('hooking handleMessage at ' + target);
        Interceptor.attach(target, {
            onEnter: function (args) {
                try {
                    var nub = args[0];      // x0 = this (Nub*)
                    var bundleIter = args[1]; // x1 = arg2 = bundle iterator
                    var msgId = Memory.readU8(bundleIter);
                    send('handleMessage ENTER nub=' + nub + ' msgId=' + msgId);
                    if (msgId === 255) {
                        var bucketCount = Memory.readU64(nub.add(0x90));
                        var bucketArrayPtr = Memory.readPointer(nub.add(0x88));
                        send('  REPLY path: bucketCount=' + bucketCount + ' bucketArray=' + bucketArrayPtr);
                        if (bucketCount.toNumber() > 0 && bucketCount.toNumber() < 4096) {
                            var n = Math.min(bucketCount.toNumber(), 64);
                            for (var i = 0; i < n; i++) {
                                var head = Memory.readPointer(bucketArrayPtr.add(i * 8));
                                if (!head.isNull()) {
                                    var key64 = Memory.readU64(head.add(8));
                                    var key32 = Memory.readU32(head.add(0x10));
                                    send('  bucket[' + i + '] node=' + head + ' key64=0x' + key64.toString(16) + ' key32=0x' + key32.toString(16));
                                }
                            }
                        }
                    }
                } catch (e) {
                    send('  onEnter error: ' + e.message);
                }
            }
        });
        send('Hook installed successfully.');
    }
} catch (e) {
    send('FATAL: ' + e.message + '\n' + e.stack);
}
