"""Generate data/athlete_mobile_stream.bin from the LIVE runtime DataType tree.

Supersedes gen_stream_v2.py. v2 inferred wire types from XML regexes and vtable addresses and could not
see fixed-size arrays; it wrote a 4-byte count for childBaseClientPropertyList / childClientPropertyList2,
which the client reads as an inline 1-element FIXED_DICT (76 / 81 fields), desynchronising the stream from
ordinal 207 onward. v3 encodes straight from athlete_runtime_types.json (scratch/dump_runtime_types.py).

Env:
  ROS_STREAM_DEFAULTS = xml (default) | min
     min : zero for numbers/strings, and PYTHON collections take their declared []/{} default (the v2 "all"
           behaviour) -- isolates the desync fix from any default-value question.
     xml : every property honours its declared <Default> literal from the entity XML. (An earlier claim that this is
           REQUIRED for a clean Lobby was retracted: the same stream rendered both clean and messy -- see notes 20d.)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runtime_encoder as RE
import xmltypes as X

ROOT = RE.ROOT
OUTBIN = os.path.join(ROOT, 'data', 'athlete_mobile_stream.bin')
LAYOUT = os.path.join(ROOT, 'scratch', 'athlete_stream_layout.txt')
TARGET = 'weekendPushRewardsHaveGotten'
MODE = os.environ.get('ROS_STREAM_DEFAULTS', 'xml')
# Bisection aid: with ROS_XML_ONLY=name1,name2 only those properties honour their XML default and every
# other property behaves as in `min` mode. Used to isolate which defaults make the Lobby render correctly.
XML_ONLY = {n for n in os.environ.get('ROS_XML_ONLY', '').split(',') if n}


def elem_literal(e):
    """XML element -> python value: children -> dict, otherwise the literal in its text."""
    kids = list(e)
    if kids:
        return {k.tag: elem_literal(k) for k in kids}
    return RE.parse_literal(e.text or '')


rows, table = RE.load()
decls = X.load_all_property_decls()


def decl_defaults(name, node):
    """(property_default, element_default_dict) from the XML declaration best matching the runtime type."""
    cands = decls.get(name, [])
    if not cands:
        return None, None
    want_fixed = RE.resolve(node, table).get('fixed')
    pick = cands[0][1]
    for _fn, el in cands:
        sz = el.find('Type/size')
        if want_fixed and sz is not None and (sz.text or '').strip() == str(want_fixed):
            pick = el
            break
    d = pick.find('Default')
    prop_default = elem_literal(d) if d is not None else None
    of_default = pick.find('Type/of/Default')
    elem_default = elem_literal(of_default) if of_default is not None else None
    return prop_default, elem_default


class ModeEncoder(RE.Encoder):
    minmode = False

    def enc(self, node, default=None, path=''):
        n = RE.resolve(node, self.table)
        kind = RE.kind_of(n['cls'])[0]
        if MODE == 'min' or self.minmode:
            if kind in ('INT', 'FLOAT', 'STRING', 'BLOB'):
                default = None
            elif kind == 'PYTHON' and not (default == [] or default == {}):
                default = None
        if kind == 'ARRAY' and n.get('fixed', 0) > 0:
            # a fixed-size array carries the ELEMENT default (the <of><Default> block); pass it down
            return b''.join(self.enc(n['elem'], default if isinstance(default, dict) else None, path + '[]')
                            for _ in range(n['fixed']))
        return super().enc(node, default, path)


included = [r for r in rows if (r['flag'] & 0x10) == 0 and (r['flag'] & 0x08) and (r['flag'] & 0x06)]
print('included properties:', len(included), '| mode:', MODE, '| xml-only:', sorted(XML_ONLY) or '-')

stream, layout = b'', []
for ordinal, r in enumerate(included):
    prop_default, elem_default = decl_defaults(r['name'], r['type'])
    node = RE.resolve(r['type'], table)
    kind = RE.kind_of(node['cls'])[0]
    if r['name'] == TARGET:
        blob = RE.py_default_bytes([])          # the original TypeError fix
    else:
        default = elem_default if (kind == 'ARRAY' and node.get('fixed', 0) > 0) else prop_default
        e = ModeEncoder(table)
        e.minmode = bool(XML_ONLY) and r['name'] not in XML_ONLY
        blob = e.enc(r['type'], default, r['name'])
    layout.append((ordinal, r['idx'], len(stream), len(blob), kind, r['name']))
    stream += blob

t = [l for l in layout if l[5] == TARGET][0]
print('%s: ordinal=%d idx=%d offset=%d len=%d' % (TARGET, t[0], t[1], t[2], t[3]))
print('total stream: %d bytes' % len(stream))
for nm in ('childBaseClientPropertyList', 'childClientPropertyList2'):
    l = [x for x in layout if x[5] == nm][0]
    print('  %-30s ordinal=%d offset=%d len=%d' % (nm, l[0], l[2], l[3]))

os.makedirs(os.path.dirname(OUTBIN), exist_ok=True)
open(OUTBIN, 'wb').write(stream)
with open(LAYOUT, 'w', encoding='utf-8') as f:
    for o, idx, off, ln, ty, nm in layout:
        f.write(f'[ord {o:3d}] [idx {idx:3d}] off={off:6d} len={ln:3d} {ty:12s} {nm}\n')
print('wrote', OUTBIN, 'and', LAYOUT)
