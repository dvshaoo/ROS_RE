import sys
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\tools')
import load_table as LT
t = open(r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\assets_dump\5081e268.bin', encoding='utf-8').read()
d = LT.parse_table(t)
print(len(d), 'records')
for pid in [int(x) for x in sys.argv[1:]]:
    r = d.get(pid)
    if not r:
        print(pid, 'NOT FOUND'); continue
    s = repr(r)
    print(pid, r.get('type'), s[:1500].encode('ascii', 'replace').decode())
