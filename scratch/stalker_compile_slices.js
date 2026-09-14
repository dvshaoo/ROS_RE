// Time-sliced compile-event capture: count compiles per range-category per
// slice, without storing every raw event (keeps output bounded).
var counters = {};
var following = false;

function classify(addr) {
    var r = Process.findRangeByAddress(ptr(addr));
    if (!r) return 'unmapped';
    if (r.file && r.file.path.indexOf('libtcb.so') !== -1) return 'libtcb.so(static)';
    if (r.file && r.file.path.indexOf('libhoudini.so') !== -1) return 'libhoudini.so';
    if (!r.file && r.protection === 'rwx') return 'anon-rwx-jitheap';
    if (r.file) return r.file.path;
    return 'anon-' + r.protection;
}

rpc.exports = {
    reset: function () { counters = {}; },
    startFollow: function (tid) {
        Stalker.follow(tid, {
            events: { compile: true },
            onReceive: function (rawEvents) {
                var parsed = Stalker.parse(rawEvents, { annotate: true, stringify: true });
                for (var i = 0; i < parsed.length; i++) {
                    var start = parsed[i][1];
                    var cat = classify(start);
                    counters[cat] = (counters[cat] || 0) + 1;
                }
            }
        });
        following = true;
    },
    stopFollow: function (tid) {
        if (following) { Stalker.unfollow(tid); Stalker.flush(); following = false; }
        var snap = {};
        for (var k in counters) snap[k] = counters[k];
        return snap;
    }
};
send('slice-compile script loaded');
