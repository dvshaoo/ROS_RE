// Test whether Mercury UDP I/O goes through Java's DatagramSocket rather
// than raw native libc calls (motivated by observing libart.so/libbinder.so/
// boot-framework.oat activity on the ServerConnection thread during login).
Java.perform(function () {
    try {
        var DatagramSocket = Java.use('java.net.DatagramSocket');
        DatagramSocket.send.overload('java.net.DatagramPacket').implementation = function (packet) {
            try {
                var addr = packet.getAddress() ? packet.getAddress().getHostAddress() : '?';
                var port = packet.getPort();
                var len = packet.getLength();
                var data = packet.getData();
                var bytes = [];
                for (var i = 0; i < Math.min(len, 300); i++) bytes.push(data[i] & 0xff);
                send('JAVA_DatagramSocket.send len=' + len + ' to=' + addr + ':' + port + ' hex=' + bytes.map(function(b){return ('0'+b.toString(16)).slice(-2);}).join(''));
            } catch (e) { send('send hook err: ' + e); }
            return this.send(packet);
        };
        DatagramSocket.receive.implementation = function (packet) {
            var ret = this.receive(packet);
            try {
                var addr = packet.getAddress() ? packet.getAddress().getHostAddress() : '?';
                var port = packet.getPort();
                var len = packet.getLength();
                var data = packet.getData();
                var bytes = [];
                for (var i = 0; i < Math.min(len, 300); i++) bytes.push(data[i] & 0xff);
                send('JAVA_DatagramSocket.receive len=' + len + ' from=' + addr + ':' + port + ' hex=' + bytes.map(function(b){return ('0'+b.toString(16)).slice(-2);}).join(''));
            } catch (e) { send('receive hook err: ' + e); }
            return ret;
        };
        send('DatagramSocket hooks installed OK');
    } catch (e) {
        send('DatagramSocket hook FAILED: ' + e);
    }

    try {
        var DatagramChannelImpl = Java.use('sun.nio.ch.DatagramChannelImpl');
        send('DatagramChannelImpl class found (not hooked, just confirming presence)');
    } catch (e) {
        send('DatagramChannelImpl not found: ' + e);
    }
});
send('java socket probe script loaded');
