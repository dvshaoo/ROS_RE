import sys, collections
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\tools')
import load_table as LT
D = r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\assets_dump\%s.bin'
for nm in ('c656e064', 'a2f095a2', '190f0c0a'):
    t = LT.parse_table(open(D % nm, encoding='utf-8').read())
    print(nm, collections.Counter((r['value'].get('PROP_TYPE') or {}).get('type') for r in t.values()).most_common(12))
t = LT.parse_table(open(D % 'c656e064', encoding='utf-8').read())
for k, r in t.items():
    pt = r['value'].get('PROP_TYPE') or {}
    if pt.get('type') not in ('CurrencyPropType', None) and any(s in pt.get('type', '') for s in ('Gift', 'Box', 'Random', 'Supply', 'Open')):
        print(k, pt.get('type'), repr(pt.get('value'))[:160]); break
