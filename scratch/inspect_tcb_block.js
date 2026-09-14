// Inspect raw bytes around a known libtcb.so translated block to look for
// Houdini metadata (e.g. a stored original ARM64 address) before/after the
// block boundaries reported by Stalker's compile event.
rpc.exports = {
    dump: function (addrHex, beforeLen, afterLen) {
        var addr = ptr(addrHex);
        var out = {};
        try {
            out.before = Memory.readByteArray(addr.sub(beforeLen), beforeLen);
        } catch (e) { out.beforeErr = '' + e; }
        try {
            out.at = Memory.readByteArray(addr, 32);
        } catch (e) { out.atErr = '' + e; }
        // scan a window of 8-byte-aligned qwords around the block for values that look
        // like a valid ARM64 libclient.so address (0x03200000 - 0x07000000 range,
        // per the confirmed mapping found in earlier sessions).
        var candidates = [];
        var base = addr.sub(256);
        for (var off = 0; off < 512; off += 8) {
            try {
                var val = Memory.readU64(base.add(off));
                var v = val.toNumber ? val.toNumber() : Number(val);
                if (v >= 0x03200000 && v <= 0x07000000) {
                    candidates.push({ offsetFromBlockMinus256: off, value: '0x' + v.toString(16) });
                }
            } catch (e) { /* skip unreadable */ }
        }
        out.candidates = candidates;
        return out;
    },
    findModule: function (addrHex) {
        var addr = ptr(addrHex);
        var r = Process.findRangeByAddress(addr);
        return r ? { base: r.base.toString(), size: r.size, prot: r.protection, file: r.file ? r.file.path : null } : null;
    }
};
send('inspect script loaded');
