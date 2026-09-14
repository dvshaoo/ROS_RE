// Hook recvfrom/sendto in the NativeBridge-translated ARM64 libc.so by RAW
// ADDRESS (base from /proc/pid/maps + file offset from static analysis of
// the pulled /system/lib64/arm64/nb/libc.so), bypassing Frida's module
// enumeration entirely, since that ARM64 module is invisible to
// Process.enumerateModules() under NativeBridge.
var NB_LIBC_BASE = ptr('0x0b604000');
var RECVFROM_OFF = 0x6f95c;
var SENDTO_OFF = 0x6faf4;

var recvfromPtr = NB_LIBC_BASE.add(RECVFROM_OFF);
var sendtoPtr = NB_LIBC_BASE.add(SENDTO_OFF);
send('Attempting raw hook at recvfrom=' + recvfromPtr + ' sendto=' + sendtoPtr);

function sockaddrPort(buf) {
    try {
        var fam = buf.readU16();
        if (fam !== 2) return 'fam=' + fam;
        var portBytes = buf.add(2).readU16();
        var port = ((portBytes & 0xff) << 8) | ((portBytes >> 8) & 0xff);
        var addr = buf.add(4).readU32();
        var a = addr & 0xff, b = (addr >> 8) & 0xff, c = (addr >> 16) & 0xff, d = (addr >> 24) & 0xff;
        return a + '.' + b + '.' + c + '.' + d + ':' + port;
    } catch (e) { return 'err:' + e; }
}

try {
    Interceptor.attach(recvfromPtr, {
        onEnter: function (args) {
            this.buf = args[1];
            this.srcAddrPtr = args[4];
        },
        onLeave: function (retval) {
            var n = retval.toInt32();
            if (n <= 0) return;
            var addrStr = (this.srcAddrPtr && !this.srcAddrPtr.isNull()) ? sockaddrPort(this.srcAddrPtr) : '?';
            var bytes = Memory.readByteArray(this.buf, Math.min(n, 512));
            send('NB_RECVFROM n=' + n + ' from=' + addrStr, bytes);
        }
    });
    send('recvfrom hook installed OK');
} catch (e) {
    send('recvfrom hook FAILED: ' + e);
}

try {
    Interceptor.attach(sendtoPtr, {
        onEnter: function (args) {
            var buf = args[1];
            var len = args[2].toInt32();
            var dstAddrPtr = args[4];
            var addrStr = (dstAddrPtr && !dstAddrPtr.isNull()) ? sockaddrPort(dstAddrPtr) : '?';
            if (len > 0) {
                var bytes = Memory.readByteArray(buf, Math.min(len, 512));
                send('NB_SENDTO n=' + len + ' to=' + addrStr, bytes);
            }
        }
    });
    send('sendto hook installed OK');
} catch (e) {
    send('sendto hook FAILED: ' + e);
}
