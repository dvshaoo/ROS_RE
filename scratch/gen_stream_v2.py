"""Generate the Athlete property stream using RUNTIME types (DataType vtables).

The XML <Type> is unreliable: the same property name is declared with different types
across interfaces, and the client's runtime DataType wins. Feeding it XML types
desynced the stream at ordinal 128 (`multipleOpenTimes`, declared PYTHON but actually
a sequence), which the client reported as:
    SequenceDataType::createFromStream: Invalid size on stream: 36589058

Each descriptor's DataType pointer is at +0x18; its vtable identifies the wire type.
Mapping established by correlating all 832 properties against their XML declarations.
"""
import json, os, re, struct, collections

ROOT = r'C:\Users\Raysoo\Downloads\ROS_RE'
XMLDIR = os.path.join(ROOT, '05_entities', 'out')
OUTBIN = os.path.join(ROOT, 'data', 'athlete_mobile_stream.bin')
TARGET = 'weekendPushRewardsHaveGotten'

VTABLE_TYPE = {
    '0x6af6c38': 'INT32',
    '0x6af7a28': 'PYTHON',
    '0x6af69d8': 'INT8',
    '0x6af6448': 'ARRAY',
    '0x6af6050': 'STRING',
    '0x6af7228': 'INT64',
    '0x6af7778': 'FLOAT',
    '0x6af5f90': 'FIXED_DICT',
    '0x6af7418': 'UINT64',
    '0x6af84f8': 'BLOB',
    '0x6af70f8': 'UINT32',
    '0x6af6778': 'UINT8',
    '0x6af6b08': 'INT16',
}


def packed_int(n):
    return bytes([n]) if n < 0xff else b'\xff' + struct.pack('<I', n)[:3]


PRIM = {
    'INT8': b'\x00', 'UINT8': b'\x00',
    'INT16': struct.pack('<h', 0), 'UINT16': struct.pack('<H', 0),
    'INT32': struct.pack('<i', 0), 'UINT32': struct.pack('<I', 0),
    'INT64': struct.pack('<q', 0), 'UINT64': struct.pack('<Q', 0),
    'FLOAT': struct.pack('<f', 0.0), 'DOUBLE': struct.pack('<d', 0.0),
    'STRING': packed_int(0), 'BLOB': packed_int(0),
    'PYTHON': packed_int(2) + b'N.',      # protocol-0 None, smallest legal pickle
    'ARRAY': struct.pack('<I', 0),        # 4-byte LE count, confirmed @0x9a4b74
}

# ---- FIXED_DICT field lists (for the 11 bare fixed dicts) ----
alias_txt = ''
for fn in os.listdir(XMLDIR):
    if fn.startswith('entities_types'):
        alias_txt += open(os.path.join(XMLDIR, fn), encoding='utf-8', errors='replace').read()
alias_txt = re.sub(r'<!--.*?-->', '', alias_txt, flags=re.S)

fixed_dicts = {}
for m in re.finditer(r'<(\w+)>\s*FIXED_DICT(.*?)</\1>', alias_txt, re.S):
    pb = re.search(r'<Properties>(.*?)</Properties>', m.group(2), re.S)
    fields = []
    if pb:
        for fm in re.finditer(r'<(\w+)>\s*<Type>\s*([\w<>\s/]+?)\s*</Type>\s*</\1>',
                              pb.group(1), re.S):
            fields.append(' '.join(fm.group(2).split()))
    fixed_dicts[m.group(1)] = fields

simple_alias = {}
for m in re.finditer(r'<(\w+)>\s*([\w\s<>/]+?)\s*</\1>', alias_txt):
    v = ' '.join(m.group(2).split())
    if v and '<' not in v:
        simple_alias[m.group(1)] = v


def enc_field(t, depth=0):
    """Encode a nested FIXED_DICT field (XML types are all we have for these)."""
    if depth > 5 or not t:
        return None
    t = ' '.join(t.split())
    if t.startswith('ARRAY'):
        return PRIM['ARRAY']
    if t in fixed_dicts:
        out = b''
        for ft in fixed_dicts[t]:
            sub = enc_field(ft, depth + 1)
            if sub is None:
                return None
            out += sub
        return out
    if t in PRIM:
        return PRIM[t]
    if t == 'BOOL':
        return b'\x00'
    if t in simple_alias and simple_alias[t] != t:
        return enc_field(simple_alias[t], depth + 1)
    return None


rows = json.load(open(os.path.join(ROOT, 'scratch', 'athlete_prop_types.json'),
                      encoding='utf-8'))
vt = {}
for line in open(os.path.join(ROOT, 'scratch', 'datatype_vtables.txt')):
    i, v = line.split()
    vt[int(i)] = v

inc = [r for r in rows if r['included']]
print(f'included: {len(inc)}')

stream, layout, unhandled = b'', [], []
for ordinal, r in enumerate(inc):
    rt = VTABLE_TYPE.get(vt.get(r['idx']))

    if r['name'] == TARGET:
        blob = packed_int(3) + b'(l.'          # protocol-0 [] -- the actual fix
    elif rt == 'FIXED_DICT':
        xml_t = str(r['type'] or '')
        blob = enc_field(xml_t.split(':', 1)[1]) if xml_t.startswith('FIXED_DICT:') else None
    else:
        blob = PRIM.get(rt)

    if blob is None:
        unhandled.append((ordinal, r['idx'], r['name'], rt, r['type']))
        blob = PRIM['PYTHON']
    layout.append((ordinal, r['idx'], len(stream), len(blob), rt, r['name']))
    stream += blob

print(f'unhandled: {len(unhandled)}')
for u in unhandled:
    print('   ', u)

t = [l for l in layout if l[5] == TARGET][0]
print(f'\n{TARGET}: ordinal={t[0]} idx={t[1]} offset={t[2]} len={t[3]}')
print(f'total stream: {len(stream)} bytes  (message = {len(stream) + 6}, budget 1465)')
print('type histogram:', collections.Counter(l[4] for l in layout).most_common())

os.makedirs(os.path.dirname(OUTBIN), exist_ok=True)
open(OUTBIN, 'wb').write(stream)
print('wrote', OUTBIN)
with open(os.path.join(ROOT, 'scratch', 'athlete_stream_layout.txt'), 'w',
          encoding='utf-8') as f:
    for o, idx, off, ln, ty, nm in layout:
        f.write(f'[ord {o:3d}] [idx {idx:3d}] off={off:6d} len={ln:3d} {str(ty):12s} {nm}\n')
