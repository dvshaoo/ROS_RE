import sys, collections
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\tools')
import load_table as LT
d = LT.parse_table(open(r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\assets_dump\5081e268.bin', encoding='utf-8').read())
c = collections.Counter((r['value'].get('PROP_TYPE') or {}).get('type') for r in d.values())
print(c)
# pools of the firearm (id 15) and vehicle boxes
sup = LT.parse_table(open(r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\assets_dump\9e1c8652.bin', encoding='utf-8').read())
def show(sid):
    v = sup[sid]['value']
    pool = [g['value']['GUARANTEE_PROP_ID'] for g in v.get('GUARANTEE_LIST') or [] if 'value' in g] + [i['PROP_ID'] for i in v.get('SUPPLEMENT_LIST') or []]
    for pid in pool:
        r = d.get(pid)
        pt = (r or {}).get('value', {}).get('PROP_TYPE') if r else None
        print(sid, pid, 'NOTINTABLE' if r is None else (pt or {}).get('type'), (repr((pt or {}).get('value'))[:160] if pt else ''))
for s in (15, 9329):
    if s in sup: show(s)
