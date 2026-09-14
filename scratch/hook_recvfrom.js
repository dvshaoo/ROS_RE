// Hook recvfrom/sendto in libc.so to observe the raw UDP path around Mercury
// LoginApp traffic (port 25000 range). libc.so is a normally-loaded module
// visible to Frida even though libclient.so (NativeBridge-translated) is not.
var libc = Process.getModuleByName('libc.so');
send('libc.so base=' + libc.base);

function sockaddrPort(buf) {
    try {
        // sockaddr_in: family(2, LE) port(2, BE) addr(4)
        var fam = buf.readU16();
        if (fam !== 2) return null; // AF_INET only
        var portBytes = buf.add(2).readU16();
        // port is stored big-endian in sockaddr
        var port = ((portBytes & 0xff) << 8) | ((portBytes >> 8) & 0xff);
        var addr = buf.add(4).readU32();
        var a = addr & 0xff, b = (addr >> 8) & 0xff, c = (addr >> 16) & 0xff, d = (addr >> 24) & 0xff;
        return a + '.' + b + '.' + c + '.' + d + ':' + port;
    } catch (e) { return null; }
}

var recvfromPtr = libc.getExportByName('recvfrom');
Interceptor.attach(recvfromPtr, {
    onEnter: function (args) {
        this.buf = args[1];
        this.len = args[2].toInt32();
        this.srcAddrPtr = args[4];
    },
    onLeave: function (retval) {
        var n = retval.toInt32();
        if (n <= 0) return;
        var addrStr = this.srcAddrPtr.isNull() ? '?' : sockaddrPort(this.srcAddrPtr);
        // Only log UDP-sized packets that look like our login traffic range
        if (n < 500) {
            var bytes = Memory.readByteArray(this.buf, Math.min(n, 512));
            send('RECVFROM n=' + n + ' from=' + addrStr, bytes);
        }
    }
});

var sendtoPtr = libc.getExportByName('sendto');
Interceptor.attach(sendtoPtr, {
    onEnter: function (args) {
        this.buf = args[1];
        this.len = args[2].toInt32();
        this.dstAddrPtr = args[4];
        var addrStr = this.dstAddrPtr.isNull() ? '?' : sockaddrPort(this.dstAddrPtr);
        if (this.len < 500) {
            var bytes = Memory.readByteArray(this.buf, Math.min(this.len, 512));
            send('SENDTO n=' + this.len + ' to=' + addrStr, bytes);
        }
    },
    onLeave: function (retval) {}
});

send('Hooks installed on recvfrom/sendto');
