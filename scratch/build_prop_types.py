"""Join the live Athlete property table (names+flags, in wire order) with the
<Type> declared for each name in the extracted entity XMLs.

Live order is authoritative for the stream; the XMLs only supply types.
"""
import re, os, collections, json

ROOT = r'C:\Users\Raysoo\Downloads\ROS_RE'
XMLDIR = os.path.join(ROOT, '05_entities', 'out')
LIVE = os.path.join(ROOT, 'scratch', 'athlete_props_full.txt')

# --- live table: index -> (name, flagbyte) ---
live = []
for line in open(LIVE, encoding='utf-8'):
    m = re.match(r'\[\s*(\d+)\] (.{52}) f@0x20=(\w+)', line)
    if m:
        live.append((int(m.group(1)), m.group(2).strip(), int(m.group(3)[0:2], 16)))
print(f'live properties: {len(live)}')

# --- XML: name -> set of declared types (collisions matter, so keep a set) ---
name_types = collections.defaultdict(set)
prop_re = re.compile(
    r'<(\w+)>\s*<Type>\s*([\w<>\s/]+?)\s*</Type>(.*?)</\1>', re.S)
for fn in os.listdir(XMLDIR):
    if not fn.endswith('.xml'):
        continue
    txt = open(os.path.join(XMLDIR, fn), encoding='utf-8', errors='replace').read()
    # only look inside <Properties> so we don't pick up method arg blocks
    for pblock in re.findall(r'<Properties>(.*?)</Properties>', txt, re.S):
        for name, typ, rest in prop_re.findall(pblock):
            has_default = '<Default>' in rest
            name_types[name].add((typ.strip(), has_default))

print(f'distinct property names found in XMLs: {len(name_types)}')

rows = []
missing = []
ambiguous = []
for idx, name, flag in live:
    entry = name_types.get(name)
    if not entry:
        missing.append((idx, name))
        typ, dflt = None, None
    elif len({t for t, _ in entry}) > 1:
        ambiguous.append((idx, name, sorted(entry)))
        typ, dflt = sorted(entry)[0]
    else:
        typ, dflt = sorted(entry)[0]
    rows.append({'idx': idx, 'name': name, 'flag': flag, 'type': typ, 'has_default': dflt})

print(f'unresolved names: {len(missing)}')
print(f'ambiguous (same name, different types across XMLs): {len(ambiguous)}')
for a in ambiguous[:10]:
    print('   ', a)

included = [r for r in rows if (r['flag'] & 0x0c) == 0x0c]
print(f'\nBASE_AND_CLIENT included set: {len(included)}')
tcount = collections.Counter(r['type'] for r in included)
print('type histogram of included set:')
for t, c in tcount.most_common():
    print(f'   {str(t):24s} {c}')

unresolved_inc = [r for r in included if r['type'] is None]
print(f'\nincluded but type UNRESOLVED: {len(unresolved_inc)}')
for r in unresolved_inc[:15]:
    print('   ', r['idx'], r['name'])

tgt = [i for i, r in enumerate(included) if r['name'] == 'weekendPushRewardsHaveGotten']
print(f'\nordinal of weekendPushRewardsHaveGotten in included set: {tgt}')

out = os.path.join(ROOT, 'scratch', 'athlete_prop_types.json')
json.dump(rows, open(out, 'w', encoding='utf-8'), indent=1)
print('wrote', out)
