"""Byte-offset-tracking mirror of ros_script_decrypt.P.load(), used to locate
the exact (offset, length) of a named function's co_code string within the
raw decrypted-but-still-marshalled module bytes (M), WITHOUT re-encoding
anything -- avoids the lossy int64/long/float round-trip entirely (see
CLAUDE.md Checkpoint 28) by only ever reading, never rebuilding, the format.
"""
import struct


class OffsetTracker:
    """Same grammar as ros_script_decrypt.P, but returns (value, start, end)
    for every load() so callers can find exact byte spans."""
    def __init__(self, b):
        self.b = b
        self.i = 0
        self.refs = []

    def i32(self):
        v = struct.unpack_from('<i', self.b, self.i)[0]
        self.i += 4
        return v

    def load(self):
        start = self.i
        t = self.b[self.i] & 0x7f
        self.i += 1
        c = chr(t)
        if c == 'c':
            for _ in range(4):
                self.i32()
            code = self.load()
            consts = self.load()
            names = self.load()
            varnames = self.load()
            free = self.load()
            cell = self.load()
            fn = self.load()
            nm = self.load()
            self.i32()
            ln = self.load()
            end = self.i
            return ({'code': code[0], 'consts': consts[0], 'names': names[0],
                     'varnames': varnames[0], 'file': fn[0], 'name': nm[0],
                     'code_span': (code[1], code[2])},
                    start, end)
        if c in ('s', 't', 'u'):
            n = self.i32()
            content_start = self.i
            raw = self.b[self.i:self.i + n]
            self.i += n
            end = self.i
            v = bytes((ch ^ ((n - 1 - k) & 0xff)) for k, ch in enumerate(raw))
            if c == 't':
                self.refs.append(v)
            # value, (content_start, content_end) -- the span of the ACTUAL
            # string bytes (post length-prefix), which is what we patch.
            return (v, content_start, end)
        if c == 'R':
            idx = self.i32()
            end = self.i
            return (self.refs[idx] if 0 <= idx < len(self.refs) else b'', start, end)
        if c in ('(', '[', '<', '>'):
            n = self.i32()
            items = [self.load() for _ in range(n)]
            end = self.i
            return ([it[0] for it in items], start, end)
        if c == 'N':
            return (None, start, self.i)
        if c in ('T', 'F', '.'):
            return (c, start, self.i)
        if c == 'i':
            v = self.i32()
            return (v, start, self.i)
        if c == 'I':
            self.i += 8
            return (0, start, self.i)
        if c == 'l':
            n = self.i32()
            for _ in range(abs(n)):
                self.i += 2
            return (0, start, self.i)
        if c == 'g':
            self.i += 8
            return (0.0, start, self.i)
        if c == 'f':
            n = self.b[self.i]
            self.i += 1
            self.i += n
            return (0.0, start, self.i)
        return (None, start, self.i)


def find_function_code_span(M, func_name):
    """Depth-first search through the module's code-object tree (via consts)
    for a code object whose 'name' equals func_name, returning the (start,
    end) byte span of its co_code STRING CONTENT (i.e. where the raw
    instruction bytes live, ready to overwrite in place)."""
    tracker = OffsetTracker(M)
    top, _, _ = tracker.load()

    def walk(co):
        if not isinstance(co, dict):
            return None
        name = co.get('name')
        name_s = name.decode('latin1') if isinstance(name, bytes) else name
        if name_s == func_name:
            return co['code_span']
        consts = co.get('consts')
        if isinstance(consts, list):
            for c in consts:
                if isinstance(c, dict) and 'code' in c:
                    r = walk(c)
                    if r is not None:
                        return r
                elif isinstance(c, list):
                    for cc in c:
                        if isinstance(cc, dict) and 'code' in cc:
                            r = walk(cc)
                            if r is not None:
                                return r
        return None

    return walk(top)


if __name__ == '__main__':
    import sys, json
    sys.path.insert(0, r'c:\Users\Raysoo\Downloads\RulesOfSurvivalOld (2)\RulesOfSurvivalOld\tools\re')
    import ros_script_decrypt as RS
    sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\scratch')
    from npk_patch_lib import NPK_PATH, get_member_raw

    sigs = json.load(open(r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\script_module_sigs.json'))
    sig = int(sigs['ui\\uilogin.py'], 16)
    data = open(NPK_PATH, 'rb').read()
    raw, off, ln, oln, tabpos = get_member_raw(data, sig)
    M = RS.member_marshal(raw)

    span = find_function_code_span(M, 'showGuestAccountRemind')
    print('showGuestAccountRemind code_span in M:', span)
    if span:
        s, e = span
        print('length:', e - s)
        print('first bytes (should match known disas start: 0,0x2c? etc.):', M[s:s+8].hex())
        print('last bytes (should end ...RETURN_CONST-equivalent 94,0,0):', M[e-8:e].hex())
