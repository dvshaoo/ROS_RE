"""Generate the Athlete property stream for createBasePlayer (domain 0 / mask 0x0b).

Wire format, reversed from libclient.so this session:
  EntityType::newDictionary (FUN_00a2a58c) -> FUN_00acf8ac(entityType, stream, 0x0b, dict)
  -> FUN_00acf5ec walks the 832-entry property table at EntityType+0x58 (0x68 stride)
     and, for every property passing the three flag predicates, calls a visitor that
     reads that property's value SEQUENTIALLY off the stream.

  Inclusion (predicates FUN_00a9f2e0 / FUN_00aa0cec / FUN_00a9f2ec, all bit tests on
  the flag byte at descriptor +0x20):
      (flags & 0x10) == 0  and  (flags & 0x08) != 0  and  (flags & 0x06) != 0

  There is NO presence bitmask and NO per-property index tag, so every included
  property must be encoded, in table order, or the stream desynchronizes.

Goal: give `weekendPushRewardsHaveGotten` (table index 515, stream ordinal 258) a
real `[]` instead of the `None` it gets from the empty-stream path, which is what
makes iWeekendPush.tryActiveWeekendPushRedBadge raise
`TypeError: 'NoneType' object is not iterable` and abort the 143-interface
onCreate() chain.
"""
import json, os, re, struct, pickle, collections

ROOT = r'C:\Users\Raysoo\Downloads\ROS_RE'
XMLDIR = os.path.join(ROOT, '05_entities', 'out')
ROWS = os.path.join(ROOT, 'scratch', 'athlete_prop_types.json')
OUTBIN = os.path.join(ROOT, 'data', 'athlete_mobile_stream.bin')

TARGET = 'weekendPushRewardsHaveGotten'


def packed_int(n):
    """BigWorld length prefix: 1 byte, or 0xff + 3-byte LE (matches _packed_int
    in mitm/local_baseapp_capture.py)."""
    if n < 0xff:
        return bytes([n])
    return b'\xff' + struct.pack('<I', n)[:3]


def py(obj):
    # Protocol 0, not 2: the whole message must fit one Mercury packet. The client
    # rejected a 1751-byte createBasePlayer with
    #   "Bundle::iterator::unpack( createBasePlayer ): Not enough data on stream at 2
    #    for payload (1465 left, needed 1751)"
    # Protocol 0 encodes None as b'N.' (2 bytes) vs b'\x80\x02N.' (4), and there are
    # 143 PYTHON properties in the stream, so this saves ~286 bytes. Python 2 reads
    # protocol 0 natively.
    p = pickle.dumps(obj, protocol=0)
    return packed_int(len(p)) + p


# ---- FIXED_DICT field lists from the alias table ----
alias_txt = ''
for fn in os.listdir(XMLDIR):
    if fn.startswith('entities_types'):
        alias_txt += open(os.path.join(XMLDIR, fn), encoding='utf-8',
                          errors='replace').read()
alias_txt = re.sub(r'<!--.*?-->', '', alias_txt, flags=re.S)

fixed_dicts = {}
for m in re.finditer(r'<(\w+)>\s*FIXED_DICT(.*?)</\1>', alias_txt, re.S):
    name, body = m.group(1), m.group(2)
    pb = re.search(r'<Properties>(.*?)</Properties>', body, re.S)
    fields = []
    if pb:
        for fm in re.finditer(r'<(\w+)>\s*<Type>\s*([\w<>\s/]+?)\s*</Type>\s*</\1>',
                              pb.group(1), re.S):
            fields.append((fm.group(1), ' '.join(fm.group(2).split())))
    fixed_dicts[name] = fields

simple_alias = {}
for m in re.finditer(r'<(\w+)>\s*([\w\s<>/]+?)\s*</\1>', alias_txt):
    v = ' '.join(m.group(2).split())
    if v and '<' not in v:
        simple_alias[m.group(1)] = v


def encode(typ, depth=0):
    """Encode a harmless zero/empty value for a wire type."""
    if depth > 6 or typ is None:
        return None
    t = ' '.join(str(typ).split())
    if t.startswith('ARRAY'):
        return struct.pack('<I', 0)          # 4-byte LE count, confirmed @0x9a4b74
    if t.startswith('FIXED_DICT:'):
        name = t.split(':', 1)[1]
        out = b''
        for _fname, ftype in fixed_dicts.get(name, []):
            sub = encode(ftype, depth + 1)
            if sub is None:
                return None
            out += sub
        return out
    if t in fixed_dicts:
        return encode('FIXED_DICT:' + t, depth + 1)
    if t in simple_alias and simple_alias[t] != t:
        return encode(simple_alias[t], depth + 1)
    return {
        'BOOL':   b'\x00',
        'INT8':   b'\x00',
        'UINT8':  b'\x00',
        'INT16':  struct.pack('<h', 0),
        'UINT16': struct.pack('<H', 0),
        'INT32':  struct.pack('<i', 0),
        'UINT32': struct.pack('<I', 0),
        'INT64':  struct.pack('<q', 0),
        'UINT64': struct.pack('<Q', 0),
        'FLOAT':  struct.pack('<f', 0.0),
        'DOUBLE': struct.pack('<d', 0.0),
        'STRING': packed_int(0),
        'BLOB':   packed_int(0),
        'PYTHON': py(None),
        'PY_DICT': py({}),
    }.get(t)


rows = json.load(open(ROWS, encoding='utf-8'))
inc = [r for r in rows if r['included']]
print(f'included properties: {len(inc)}')

stream = b''
unhandled = []
layout = []
for ordinal, r in enumerate(inc):
    typ = r['type']
    # the two ARRAY-of-inline-FIXED_DICT decls whose nested <Properties> defeat the
    # simple type regex; an empty ARRAY is 4 zero bytes regardless of element type
    if typ is None and str(r['raw_type'] or '').startswith('ARRAY'):
        typ = 'ARRAY'
    if typ is None and r['name'] in ('childBaseClientPropertyList',
                                     'childClientPropertyList2'):
        typ = 'ARRAY'

    if r['name'] == TARGET:
        # b'(l.' is MARK/LIST/STOP -- a valid protocol-0 empty list, verified to
        # unpickle as []. pickle.dumps([], 0) would emit b'(lp0\n.' and waste 3 bytes
        # of a budget that has almost none left.
        blob = packed_int(3) + b'(l.'        # the whole point of this stream
    else:
        blob = encode(typ)

    if blob is None:
        unhandled.append((ordinal, r['idx'], r['name'], r['raw_type']))
        blob = py(None)                      # safest fallback: same as today's None
    layout.append((ordinal, r['idx'], r['name'], typ, len(blob), len(stream)))
    stream += blob

print(f'unhandled types (fell back to pickled None): {len(unhandled)}')
for u in unhandled[:10]:
    print('   ', u)

tgt = [l for l in layout if l[2] == TARGET][0]
print(f'\n{TARGET}: ordinal={tgt[0]} table_idx={tgt[1]} byte_offset={tgt[5]} len={tgt[4]}')
print(f'total stream: {len(stream)} bytes')

os.makedirs(os.path.dirname(OUTBIN), exist_ok=True)
with open(OUTBIN, 'wb') as f:
    f.write(stream)
print('wrote', OUTBIN)

with open(os.path.join(ROOT, 'scratch', 'athlete_stream_layout.txt'), 'w',
          encoding='utf-8') as f:
    for o, idx, name, typ, ln, off in layout:
        f.write(f'[ord {o:3d}] [idx {idx:3d}] off={off:6d} len={ln:3d} {typ:28s} {name}\n')
print('wrote scratch/athlete_stream_layout.txt')
