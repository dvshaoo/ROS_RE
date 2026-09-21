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
import json, os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runtime_encoder as RE
import xmltypes as X

ROOT = RE.ROOT
OUTBIN = os.path.join(ROOT, 'data', 'athlete_mobile_stream.bin')
LAYOUT = os.path.join(ROOT, 'scratch', 'athlete_stream_layout.txt')
MODE = os.environ.get('ROS_STREAM_DEFAULTS', 'xml')
# Bisection aid: with ROS_XML_ONLY=name1,name2 only those properties honour their XML default and every
# other property behaves as in `min` mode. Used to isolate which defaults make the Lobby render correctly.
# Per-property value overrides for INT properties, e.g. ROS_PROP_OVERRIDES=freeYuanbao=1000,payYuanbao=500
OVR = {}
# Dev balance shown in the hall top bar (gp = gold coin, sp = silver coin, freeYuanbao/payYuanbao = diamonds).
# Set ROS_PROP_OVERRIDES='-' to disable, or supply your own list.
_DEFAULT_OVR = 'gp=999999,sp=5000,freeYuanbao=999999,payYuanbao=0'
for _kv in os.environ.get('ROS_PROP_OVERRIDES', _DEFAULT_OVR).split(','):
    if '=' in _kv:
        _k, _v = _kv.split('=', 1)
        OVR[_k.strip()] = int(_v)
XML_ONLY = {n for n in os.environ.get('ROS_XML_ONLY', '').split(',') if n}

# Values that the private BaseApp must provide instead of the XML/default encoder's None.
# Keep these semantic server values in one table: every entry is encoded through the property's
# live runtime DataType, so adding an override does not bypass the verified v3 wire layout.
_inventory_path = os.path.join(ROOT, 'data', 'player_inventory.json')
try:
    with open(_inventory_path, encoding='utf-8') as _f:
        _inventory = json.load(_f).get('items', {})
except (OSError, ValueError, AttributeError):
    _inventory = {}

# Gender and equipped appearance are persisted separately from inventory.
# The same file is written by Depot and read here for the next fresh hall
# build, preventing a hard-coded creation gender from overriding Depot.
_state_path = os.path.join(ROOT, 'data', 'player_state.json')
try:
    with open(_state_path, encoding='utf-8') as _f:
        _player_state = json.load(_f)
except Exception:
    _player_state = {'gender': 1, 'lists': {}}
_gender = int(_player_state.get('gender', 1))
_gender_lists = _player_state.get('lists', {}).get(str(_gender), {'wear': [], 'body': []})

_appearance_items = []
for _item_id, _item in sorted(_inventory.items(), key=lambda kv: int(kv[0])):
    try:
        _appearance_items.append({
            'uuid': bytes.fromhex(_item['uuid']),
            'itemID': int(_item_id),
            'number': int(_item['number']),
            'info': dict(_item.get('info') or {'ex_tm': 0}),
        })
    except (KeyError, TypeError, ValueError):
        print('WARNING: ignoring malformed inventory item', _item_id)

PROPERTY_OVERRIDES = {
    # This is read during Athlete.onBecomePlayer, before the later Stage-4
    # updateBaseNickname RPC.  Leaving it empty makes the client take the
    # no-role bootstrap path (control-selection UI followed by a new BaseApp
    # connection) even though this LAN profile already exists.
    'baseNickname': os.environ.get('ROS_BASE_NICKNAME', 'Dev | Raysoo').encode('utf-8'),
    'weekendPushRewardsHaveGotten': [],
    # Athlete.onBecomePlayer passes this to extconfigs.getServiceAccessPoint(ap), which indexes
    # ap[0], ap[1] (and ap[2] for published iOS). Point all services at the LAN gateway only.
    'msHttpAP': ['172.16.1.2', 80, 443],
    # currencyList = ARRAY<CURRENCY_ITEM{id INT32, num INT64}> (dynamic array). iCurrency.getCurrencyAmount(id) reads it for every
    # currency except YUANBAO (that one is freeYuanbao+payYuanbao). ids are MallCurrencyType consts: GP=1, YUANBAO=2, SP=3
    # (first three only; later ids not verified). id 213 is the top-bar coin slot (UIMain.curExchangeCoin), live-verified by probe. Override with ROS_CURRENCY_LIST='1:100000,3:5000' ('-' = empty).
    'currencyList': [{'id': int(kv.split(':')[0]), 'num': int(kv.split(':')[1])}
                     for kv in os.environ.get('ROS_CURRENCY_LIST', '1:999999,3:5000,213:999999').split(',') if ':' in kv],
    # DTS_APPEARANCE_PACKAGE3 is a FIXED_DICT. Its itemList records are ITEM_DATA3
    # (uuid BLOB, itemID INT32, number INT32, info PY_DICT), verified from the live
    # runtime DataType tree and entity_0464 DEF. The JSON is updated after each draw.
    'dtsAppearancePackage': {
        'itemList': _appearance_items,
        'itemsList': [],
        'layoutInfo': {},
        '_packageCapacity': len(_appearance_items),
    },
    'dtsAppearanceGender': _gender,
    'baseCharacterType': 10002 if _gender == 1 else 10005,
    'dtsWearableAppearanceList': _gender_lists.get('wear', []),
    'dtsBodyAppearanceList': _gender_lists.get('body', []),
    'dtsShowWearableAppearanceList': _gender_lists.get('wear', []),
    'dtsShowBodyAppearanceList': _gender_lists.get('body', []),
}


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
    dynamic_arrays = False      # True only for PROPERTY_OVERRIDES: encode a non-empty list default into a count-prefixed array

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
        if kind == 'ARRAY' and n.get('fixed', 0) == 0 and self.dynamic_arrays and isinstance(default, list) and default:
            return struct.pack('<I', len(default)) + b''.join(
                self.enc(n['elem'], item, path + '[]') for item in default)
        return super().enc(node, default, path)


included = [r for r in rows if (r['flag'] & 0x10) == 0 and (r['flag'] & 0x08) and (r['flag'] & 0x06)]
print('included properties:', len(included), '| mode:', MODE, '| xml-only:', sorted(XML_ONLY) or '-')

stream, layout = b'', []
for ordinal, r in enumerate(included):
    prop_default, elem_default = decl_defaults(r['name'], r['type'])
    node = RE.resolve(r['type'], table)
    kind = RE.kind_of(node['cls'])[0]
    if r['name'] in PROPERTY_OVERRIDES:
        oe = ModeEncoder(table)
        oe.dynamic_arrays = True
        blob = oe.enc(r['type'], PROPERTY_OVERRIDES[r['name']], r['name'])
    else:
        default = elem_default if (kind == 'ARRAY' and node.get('fixed', 0) > 0) else prop_default
        if r['name'] in OVR and kind == 'INT':
            default = OVR[r['name']]
        e = ModeEncoder(table)
        e.minmode = bool(XML_ONLY) and r['name'] not in XML_ONLY
        blob = e.enc(r['type'], default, r['name'])
    layout.append((ordinal, r['idx'], len(stream), len(blob), kind, r['name']))
    stream += blob

for name in PROPERTY_OVERRIDES:
    t = [l for l in layout if l[5] == name][0]
    print('%s: ordinal=%d idx=%d offset=%d len=%d' % (name, t[0], t[1], t[2], t[3]))
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
