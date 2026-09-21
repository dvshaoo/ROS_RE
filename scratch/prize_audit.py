import sys, os, collections, glob, re
os.chdir(r'C:\Users\Raysoo\Downloads\ROS_RE\mitm'); sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\tools')
src = open('local_baseapp_capture.py', encoding='utf-8').read()
ns = {'sys': sys, 'os': os, '__file__': os.path.abspath('local_baseapp_capture.py'), 'time': __import__('time'), 'pickle': __import__('pickle'), 'struct': __import__('struct'), 'log': print}
a = src.index('_SUPPLEMENT_CACHE = {}'); b = src.index('def _packed_int(n):')
exec(src[a:b], ns)
import load_table as LT
# index every data table by id -> (table name, prop type)
idx = {}
for p in glob.glob(r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\assets_dump\*.bin'):
    t = open(p, 'rb').read().decode('utf-8', 'replace')
    if 'data = ' not in t or 'types_' not in t[:600] and 'imports' not in t[:600]: continue
    try: d = LT.parse_table(t)
    except Exception: continue
    for k, r in d.items():
        pt = (r.get('value') or {}).get('PROP_TYPE') if isinstance(r.get('value'), dict) else None
        if isinstance(k, int) and pt: idx.setdefault(k, set()).add((os.path.basename(p)[:8], pt.get('type')))
cnt = collections.Counter()
for sid in [int(x) for x in sys.argv[1:]]:
    for _ in range(60):
        for i in ns['supplement_pick_prizes'](sid, 10):
            for tab, typ in idx.get(i, {('NONE', 'NONE')}):
                cnt[(sid, typ)] += 1
for k, v in sorted(cnt.items()): print(k, v)
