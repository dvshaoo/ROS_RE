import sys, collections
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\tools')
import load_table as LT
D = r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\assets_dump\%s.bin'
tabs = {}
for nm in ('a2f095a2', 'c656e064', '190f0c0a', 'd99267c9', '502032c7'):
    try:
        tabs[nm] = LT.parse_table(open(D % nm, encoding='utf-8').read())
    except Exception as e:
        print(nm, 'parse fail', str(e)[:80]); continue
    print(nm, len(tabs[nm]), collections.Counter(r.get('type') for r in tabs[nm].values()).most_common(6))
for pid in (291401, 291211, 291733, 121223, 1110322, 142058, 103982, 310000, 2104):
    for nm, t in tabs.items():
        if pid in t:
            r = t[pid]; print(pid, nm, r.get('type'), repr(r['value'])[:200].encode('ascii', 'replace').decode()); break
    else:
        print(pid, 'not in any')
