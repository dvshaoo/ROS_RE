"""Encode an all-default Athlete property stream from the LIVE runtime DataType tree.

Input: scratch/athlete_runtime_types.json (produced by scratch/dump_runtime_types.py). That tree comes
straight from the client's own DataType objects, so it is exactly what SequenceDataType /
FixedDictDataType / IntegerDataType ... will read -- including fixed-size arrays (no wire count) that
the XML regexes could not see.

Wire rules (each one verified against the client's own behaviour or a decompile):
  integers/floats  little-endian natural width
  STRING / BLOB    packed_int(len) + bytes            (empty = 1 byte)
  PYTHON           packed_int(len) + protocol-0 pickle (FUN_00ac38c8)
  ARRAY            fixed>0: exactly `fixed` elements, NO count;  fixed==0: uint32 count + elements
                   (FUN_00aa4b14: the count is read from the wire only when +0x30 == 0)
  FIXED_DICT       concatenation of its fields in table order
"""
import json, os, re, struct, pickle, ast

ROOT = r'C:\Users\Raysoo\Downloads\ROS_RE'
TYPES_JSON = os.path.join(ROOT, 'scratch', 'athlete_runtime_types.json')

# RTTI class -> (kind, byte width, signed)   (Itanium-mangled template arg: c/h char, s short, i int,
# j unsigned int, x long long, y unsigned long long, f float)
INT_CLASSES = {
    'IntegerDataTypeIcEE': (1, True), 'IntegerDataTypeIhEE': (1, False),
    'IntegerDataTypeIsEE': (2, True), 'IntegerDataTypeItEE': (2, False),
    'IntegerDataTypeIiEE': (4, True), 'IntegerDataTypeIjEE': (4, False),
    'LongIntegerDataTypeIjEE': (4, False), 'LongIntegerDataTypeIiEE': (4, True),
    'LongIntegerDataTypeIxEE': (8, True), 'LongIntegerDataTypeIyEE': (8, False),
}


def packed_int(n):
    return bytes([n]) if n < 0xff else b'\xff' + struct.pack('<I', n)[:3]


def kind_of(cls):
    """Return (kind, extra) for an RTTI class name."""
    c = cls.split('bwclient')[-1]
    c = re.sub(r'^\d+', '', c)
    if c.startswith('FixedDictDataType'):
        return 'FIXED_DICT', None
    if c.startswith('ArrayDataType') or c.startswith('SequenceDataType'):
        return 'ARRAY', None
    if c.startswith('PythonDataType'):
        return 'PYTHON', None
    if c.startswith('StringDataType'):
        return 'STRING', None
    if c.startswith('BlobDataType'):
        return 'BLOB', None
    if c.startswith('FloatDataType'):
        return 'FLOAT', 4
    if c.startswith('MailBoxDataType'):
        return 'MAILBOX', None
    for k, (w, sg) in INT_CLASSES.items():
        if c.startswith(k[:-2]) and c.endswith(k[-4:-2] + 'EE') or c == k:
            return 'INT', (w, sg)
    return 'UNKNOWN', cls


def load():
    rows = json.load(open(TYPES_JSON, encoding='utf-8'))
    table = {}

    def collect(n):
        if not n or 'ref' in n:
            return
        table[n['ptr']] = n
        if n.get('elem'):
            collect(n['elem'])
        for f in n.get('fields', []):
            collect(f['type'])

    for r in rows:
        collect(r['type'])
    return rows, table


def resolve(n, table):
    return table[n['ref']] if n and 'ref' in n else n


def py_default_bytes(value):
    """Protocol-0 pickle of a literal default, length-prefixed. [] / {} use the shortest forms that the
    client's Python-2 cPickle is known to accept."""
    if value is None:
        p = b'N.'
    elif value == [] and isinstance(value, list):
        p = b'(l.'
    elif value == {} and isinstance(value, dict):
        p = b'(d.'
    else:
        p = pickle.dumps(value, protocol=0)
    return packed_int(len(p)) + p


def parse_literal(text):
    try:
        return ast.literal_eval(' '.join(text.split()))
    except Exception:
        return None


class Encoder:
    def __init__(self, table, defaults=None):
        self.table = table
        self.defaults = defaults or {}     # field-name -> python literal, for the CURRENT property
        self.unknown = {}

    def enc(self, node, default=None, path=''):
        n = resolve(node, self.table)
        kind, extra = kind_of(n['cls'])
        if kind == 'INT':
            w, signed = extra
            v = int(default) if isinstance(default, (int, bool)) else 0
            lo, hi = ((-(1 << (8 * w - 1)), (1 << (8 * w - 1)) - 1) if signed else (0, (1 << (8 * w)) - 1))
            v = v if lo <= v <= hi else 0
            return v.to_bytes(w, 'little', signed=signed)
        if kind == 'FLOAT':
            return struct.pack('<f', float(default) if isinstance(default, (int, float)) else 0.0)
        if kind in ('STRING', 'BLOB'):
            s = default.encode('utf-8') if isinstance(default, str) else (default if isinstance(default, bytes) else b'')
            return packed_int(len(s)) + s
        if kind == 'PYTHON':
            return py_default_bytes(default)
        if kind == 'ARRAY':
            fixed = n.get('fixed', 0)
            if fixed > 0:
                return b''.join(self.enc(n['elem'], None, path + '[]') for _ in range(fixed))
            return struct.pack('<I', 0)
        if kind == 'FIXED_DICT':
            out = b''
            dd = default if isinstance(default, dict) else {}
            for f in n.get('fields', []):
                out += self.enc(f['type'], dd.get(f['name'], self.defaults.get(f['name'])), path + '.' + f['name'])
            return out
        self.unknown[n['cls']] = self.unknown.get(n['cls'], 0) + 1
        raise NotImplementedError('wire form of %s (%s) at %s is not established' % (kind, n['cls'], path))


def inventory(rows, table):
    """Where each non-trivial class is used, and the encoded size of every included property."""
    included = [r for r in rows if (r['flag'] & 0x10) == 0 and (r['flag'] & 0x08) and (r['flag'] & 0x06)]
    uses = {}
    sizes = []
    for r in included:
        enc = Encoder(table)
        try:
            b = enc.enc(r['type'], None, r['name'])
            sizes.append((r['idx'], r['name'], len(b)))
        except NotImplementedError as e:
            uses.setdefault(str(e).split(' at ')[0], []).append(r['name'])
            sizes.append((r['idx'], r['name'], None))
    return included, sizes, uses


if __name__ == '__main__':
    rows, table = load()
    included, sizes, uses = inventory(rows, table)
    print('included properties:', len(included))
    ok = [s for s in sizes if s[2] is not None]
    print('encodable:', len(ok), '| blocked:', len(sizes) - len(ok))
    for k, v in uses.items():
        print('  BLOCKED by', k, '->', v[:8], '...' if len(v) > 8 else '')
    print('total bytes of encodable properties:', sum(s[2] for s in ok))
    big = sorted(ok, key=lambda s: -s[2])[:6]
    print('largest:', [(n, b) for _, n, b in big])
    # also: MailBox usage anywhere in the tree (nested)
    def walk(n, path, hits):
        n = resolve(n, table)
        if kind_of(n['cls'])[0] == 'MAILBOX':
            hits.append(path)
        if n.get('elem'):
            walk(n['elem'], path + '[]', hits)
        for f in n.get('fields', []):
            walk(f['type'], path + '.' + f['name'], hits)
    hits = []
    for r in included:
        walk(r['type'], r['name'], hits)
    print('MailBox usages inside the included set:', hits[:10], len(hits))
