"""Load a client data table (a plain-text Python literal stored in APK assets.npk) by its member signature.

assets.npk = NXPK, zlib-compressed members, index at header +0x14 (28-byte entries: sig, off, len, orig_len). Tables look like
    imports = [...]; name = "..."; types = \\ {...schema...}; data = \\ {id: {'type': ..., 'value': {...}}}
`_g89na_trans('<md5>')` (translated strings) is replaced by the plain md5 key string.
Dump everything with `python tools/load_table.py --dump` (writes scratch/assets_dump/<sig>.bin)."""
import ast, os, re, struct, sys, zlib

ROOT = r'C:\Users\Raysoo\Downloads\ROS_RE'
NPK = os.path.join(ROOT, '01_apk', 'h45na_extract2', 'assets.npk')
BS = chr(92)


def members():
    d = open(NPK, 'rb').read()
    cnt = struct.unpack_from('<I', d, 4)[0]
    io = struct.unpack_from('<I', d, 0x14)[0]
    for i in range(cnt):
        sig, off, ln, _ = struct.unpack_from('<IIII', d, io + i * 28)
        raw = d[off:off + ln]
        try:
            raw = zlib.decompress(raw) if raw[:2] == b'x\x9c' else raw
        except Exception:
            pass
        yield sig, raw


def read_member(sig):
    for s, raw in members():
        if s == sig:
            return raw
    raise KeyError(hex(sig))


def parse_table(text):
    """Return the `data` dict of a table source text."""
    text = text.replace('\r', '')
    marker = '\ndata = ' + BS
    i = text.index(marker) + len(marker)
    body = re.sub(r"_g89na_trans\('([0-9a-f]+)'\)", r"'\1'", text[i:])
    return ast.literal_eval(body.strip())


def load(sig):
    return parse_table(read_member(sig).decode('utf-8'))


if __name__ == '__main__':
    if '--dump' in sys.argv:
        os.makedirs(os.path.join(ROOT, 'scratch', 'assets_dump'), exist_ok=True)
        n = 0
        for sig, raw in members():
            open(os.path.join(ROOT, 'scratch', 'assets_dump', '%08x.bin' % sig), 'wb').write(raw)
            n += 1
        print('wrote', n)
    else:
        sig = int(sys.argv[1], 16)
        data = load(sig)
        print(len(data), 'records; first keys', sorted(data)[:20])
