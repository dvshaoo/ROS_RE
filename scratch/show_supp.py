import sys, json
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\tools')
import load_table as LT
data = LT.parse_table(open(r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\assets_dump\9e1c8652.bin', encoding='utf-8').read())
sid = int(sys.argv[1]); r = data[sid]; v = r['value']
print(sid, r['type'], 'keys', sorted(v.keys()))
def brief(x, d=0):
    s = repr(x)
    return s if len(s) < 350 else s[:350] + '...'
for k in ('KIND', 'SUPPLEMENT_LIST', 'GUARANTEE_LIST', 'CURRENCY_OPTION', 'PURCHASE_LIMIT_NUM', 'CONTINUE_LOTTERY_TIMES', 'ExtraGiftParam', 'CURRENT_DISCOUNT'):
    print(k, '=', brief(v.get(k)))
sl = v.get('SUPPLEMENT_LIST') or []
print('SUPPLEMENT_LIST n =', len(sl)); print(brief(sl[0]) if sl else '')
gl = v.get('GUARANTEE_LIST') or []
print('GUARANTEE_LIST n =', len(gl)); print(brief(gl[0]) if gl else '')
