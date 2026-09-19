"""Resolve a concrete wire type for every property in Athlete's live table.

Sources, in priority order:
  1. Athlete.def.xml          (the entity's own properties)
  2. all other entity XMLs    (interface properties)
  3. entities_types_*.xml     (alias table: KEY_NAME -> BLOB, SCORE -> UINT64, ...)

Live table order is authoritative for the wire stream; XMLs only supply types.

Inclusion rule, verified from libclient.so (FUN_00acf5ec + its three predicates):
    (flags & 0x10) == 0  and  (flags & 0x08) != 0  and  (flags & 0x06) != 0
"""
import re, os, collections, json

ROOT = r'C:\Users\Raysoo\Downloads\ROS_RE'
XMLDIR = os.path.join(ROOT, '05_entities', 'out')
LIVE = os.path.join(ROOT, 'scratch', 'athlete_props_full.txt')


def included(flag):
    return (flag & 0x10) == 0 and (flag & 0x08) != 0 and (flag & 0x06) != 0


# ---- live table ----
live = []
for line in open(LIVE, encoding='utf-8'):
    m = re.match(r'\[\s*(\d+)\] (.{52}) f@0x20=(\w+)', line)
    if m:
        live.append((int(m.group(1)), m.group(2).strip(), int(m.group(3)[0:2], 16)))

# ---- alias table ----
aliases = {}
alias_fixed_dict = set()
for fn in os.listdir(XMLDIR):
    if not fn.startswith('entities_types'):
        continue
    txt = open(os.path.join(XMLDIR, fn), encoding='utf-8', errors='replace').read()
    for name, body in re.findall(r'<(\w+)>\s*([^<]*?)\s*</\1>', txt):
        b = body.strip()
        if b and re.fullmatch(r'[\w\s<>/]+', b):
            aliases[name] = b
    for name in re.findall(r'<(\w+)>\s*FIXED_DICT', txt):
        alias_fixed_dict.add(name)

# ---- property -> declared type ----
prop_re = re.compile(r'<(\w+)>\s*<Type>\s*([\w<>\s/]+?)\s*</Type>(.*?)</\1>', re.S)
own, iface = {}, collections.defaultdict(set)
for fn in os.listdir(XMLDIR):
    if not fn.endswith('.xml'):
        continue
    txt = open(os.path.join(XMLDIR, fn), encoding='utf-8', errors='replace').read()
    # Many declarations carry an inline comment between the tag and <Type>
    # (e.g. `<playerUUID><!--@..-->`), which would otherwise break the match.
    txt = re.sub(r'<!--.*?-->', '', txt, flags=re.S)
    for pblock in re.findall(r'<Properties>(.*?)</Properties>', txt, re.S):
        for name, typ, _rest in prop_re.findall(pblock):
            t = ' '.join(typ.split())
            if fn == 'Athlete.def.xml':
                own[name] = t
            else:
                iface[name].add(t)


def resolve(t, depth=0):
    """Collapse aliases down to a primitive / ARRAY / FIXED_DICT marker."""
    if t is None or depth > 6:
        return t
    t = ' '.join(t.split())
    if t.startswith('ARRAY'):
        return 'ARRAY'
    if t in alias_fixed_dict:
        return 'FIXED_DICT:' + t
    if t in aliases:
        return resolve(aliases[t], depth + 1)
    return t


rows = []
for idx, name, flag in live:
    raw = own.get(name)
    if raw is None:
        cands = iface.get(name)
        if cands:
            # prefer a non-PYTHON concrete declaration when the name collides
            raw = sorted(cands, key=lambda x: (x == 'PYTHON', x))[0]
    rows.append({'idx': idx, 'name': name, 'flag': flag,
                 'raw_type': raw, 'type': resolve(raw),
                 'included': included(flag)})

inc = [r for r in rows if r['included']]
print(f'live={len(rows)}  included={len(inc)}')
hist = collections.Counter(r['type'] for r in inc)
print('resolved type histogram (included set):')
for t, c in hist.most_common():
    print(f'   {str(t):28s} {c}')

unres = [r for r in inc if r['type'] is None]
print(f'\nSTILL UNRESOLVED in included set: {len(unres)}')
for r in unres[:20]:
    print('   ', r['idx'], r['name'])

tgt = [i for i, r in enumerate(inc) if r['name'] == 'weekendPushRewardsHaveGotten']
print(f"\nweekendPushRewardsHaveGotten ordinal in stream: {tgt}")

json.dump(rows, open(os.path.join(ROOT, 'scratch', 'athlete_prop_types.json'), 'w',
                     encoding='utf-8'), indent=1)
print('wrote scratch/athlete_prop_types.json')
