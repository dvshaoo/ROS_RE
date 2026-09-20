"""Scan every PYTHON property in the stream for its declared <Default> literal."""
import re, os, json, collections

ROOT = r'C:\Users\Raysoo\Downloads\ROS_RE'
XMLDIR = os.path.join(ROOT, '05_entities', 'out')

# name -> set of default literals declared across the XMLs
defaults = collections.defaultdict(set)
prop_re = re.compile(r'<(\w+)>\s*<Type>\s*([\w<>\s/]+?)\s*</Type>(.*?)</\1>', re.S)
for fn in os.listdir(XMLDIR):
    if not fn.endswith('.xml'):
        continue
    txt = open(os.path.join(XMLDIR, fn), encoding='utf-8', errors='replace').read()
    txt = re.sub(r'<!--.*?-->', '', txt, flags=re.S)
    for pblock in re.findall(r'<Properties>(.*?)</Properties>', txt, re.S):
        for name, typ, rest in prop_re.findall(pblock):
            m = re.search(r'<Default>(.*?)</Default>', rest, re.S)
            if m:
                defaults[name].add(' '.join(m.group(1).split()))

VT_PY = '0x6af7a28'
vt = {}
for line in open(os.path.join(ROOT, 'scratch', 'datatype_vtables.txt')):
    i, v = line.split()
    vt[int(i)] = v

rows = json.load(open(os.path.join(ROOT, 'scratch', 'athlete_prop_types.json'),
                      encoding='utf-8'))
inc = [r for r in rows if r['included']]

hist = collections.Counter()
examples = collections.defaultdict(list)
for o, r in enumerate(inc):
    if vt.get(r['idx']) != VT_PY:
        continue
    d = defaults.get(r['name'])
    key = 'NO_DEFAULT' if not d else ('AMBIGUOUS:' + '|'.join(sorted(d)) if len(d) > 1
                                      else next(iter(d)))
    hist[key] += 1
    if len(examples[key]) < 3:
        examples[key].append((o, r['name']))

print('PYTHON properties in stream, by declared default:')
for k, c in hist.most_common():
    print(f'  {k!r:30s} {c:3d}   e.g. {examples[k]}')
