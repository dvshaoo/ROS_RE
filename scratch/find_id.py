import sys, glob, re
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\tools')
import load_table as LT
ids = [int(x) for x in sys.argv[1:]]
for p in glob.glob(r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\assets_dump\*.bin'):
    b = open(p, 'rb').read()
    if b'data = ' not in b: continue
    txt = b.decode('utf-8', 'replace')
    if not any(re.search(r'^\s+%d\s*:' % i, txt, re.M) for i in ids): continue
    try: d = LT.parse_table(txt)
    except Exception: continue
    nm = re.search(r'^name = "(.*?)"', txt, re.M)
    for i in ids:
        if i in d:
            r = d[i]; pt = (r.get('value') or {}).get('PROP_TYPE') if isinstance(r.get('value'), dict) else None
            print(i, p.split(chr(92))[-1], (nm.group(1) if nm else '').encode('ascii', 'replace').decode(), r.get('type'), repr(pt or r)[:230].encode('ascii', 'replace').decode())
