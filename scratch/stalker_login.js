// Frida Stalker experiment: observe actual runtime execution during one
// ROS login attempt, using call-summary mode to keep output bounded
// (task explicitly warns against a raw instruction dump).
var TARGET_TID = parseInt(Memory.allocUtf8String ? '0' : '0'); // placeholder, set via rpc
var summary = {};
var callCount = 0;
var following = false;
var rangesSeen = {};

function classifyAddr(addrStr) {
    try {
        var addr = ptr(addrStr);
        var range = Process.findRangeByAddress(addr);
        if (!range) return 'unmapped';
        var key = range.base + '-' + range.base.add(range.size) + ' prot=' + range.protection + (range.file ? ' file=' + range.file.path : ' anon');
        rangesSeen[key] = (rangesSeen[key] || 0) + 1;
        return key;
    } catch (e) {
        return 'err:' + e;
    }
}

rpc.exports = {
    startFollow: function (tid) {
        TARGET_TID = tid;
        summary = {};
        callCount = 0;
        rangesSeen = {};
        Stalker.follow(tid, {
            events: { call: true },
            onCallSummary: function (sum) {
                for (var addr in sum) {
                    summary[addr] = (summary[addr] || 0) + sum[addr];
                    callCount += sum[addr];
                    classifyAddr(addr);
                }
            }
        });
        following = true;
        send('Stalker following tid=' + tid);
    },
    stopFollow: function () {
        if (following) {
            Stalker.unfollow(TARGET_TID);
            Stalker.flush();
            following = false;
        }
        // build a compact report: top call targets by count, and distinct ranges touched
        var entries = [];
        for (var addr in summary) entries.push([addr, summary[addr]]);
        entries.sort(function (a, b) { return b[1] - a[1]; });
        var rangesReport = [];
        for (var k in rangesSeen) rangesReport.push(k + ' (hit ' + rangesSeen[k] + 'x)');
        send('TOTAL_CALLS=' + callCount + ' UNIQUE_TARGETS=' + entries.length);
        return { top: entries, ranges: rangesReport, totalCalls: callCount, uniqueTargets: entries.length };
    },
    listThreads: function () {
        return Process.enumerateThreads().map(function (t) { return { id: t.id, state: t.state }; });
    }
};
send('script loaded');
