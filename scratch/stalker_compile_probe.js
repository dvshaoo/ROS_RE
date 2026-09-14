// Probe: what does a Stalker 'compile' event actually look like in this
// Frida 16.2.1 / NativeBridge environment? Do not assume the shape.
var events = [];
var following = false;

rpc.exports = {
    startFollow: function (tid) {
        events = [];
        Stalker.follow(tid, {
            events: { compile: true },
            onReceive: function (rawEvents) {
                var parsed = Stalker.parse(rawEvents, { annotate: true, stringify: false });
                for (var i = 0; i < parsed.length && events.length < 200; i++) {
                    events.push(parsed[i]);
                }
            }
        });
        following = true;
        send('following tid=' + tid + ' with events.compile=true');
    },
    stopFollow: function (tid) {
        if (following) {
            Stalker.unfollow(tid);
            Stalker.flush();
            following = false;
        }
        // stringify addresses for transport
        var out = events.map(function (e) {
            return e.map(function (x) {
                if (x && x.toString) return x.toString();
                return x;
            });
        });
        return { count: events.length, sample: out.slice(0, 50) };
    }
};
send('compile-probe script loaded, frida stalker available: ' + (typeof Stalker));
