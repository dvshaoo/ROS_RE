import sys, os, pickle, collections
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\mitm'); sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\tools')
os.chdir(r'C:\Users\Raysoo\Downloads\ROS_RE\mitm')
import re
src = open(r'C:\Users\Raysoo\Downloads\ROS_RE\mitm\local_baseapp_capture.py', encoding='utf-8').read()
a = src.index('def _supplement_runtime_record'); b = src.index('_SUPPLEMENT_CACHE = {}')
ns = {}
exec(src[a:src.index('def supplement_avail_payload')], ns)
import load_table as LT
data = LT.parse_table(LT.read_member(0x9e1c8652).decode('utf-8'))
KEYS = ['NAME','CURRENCY_ID','BUY_TIMES_PRICE','NEXT_BUY_TIMES_PRICE','BUY_MULTIPLE_TIMES_PRICE','CURRENT_DISCOUNT','KIND','IS_PREVIOUS_BOX','SORT_KEY','PURCHASE_LIMIT_NUM','CONTINUE_LOTTERY_TIMES']
def slim(rec, keys):
    v = ns['_supplement_runtime_record'](rec)
    return {k: v[k] for k in keys if k in v}
for keys in (KEYS, KEYS[:7]):
    out = {sid: slim(r, keys) for sid, r in data.items()}
    print(len(keys), 'keys ->', len(out), 'records', len(pickle.dumps(out, protocol=0)), 'B (proto0),', len(pickle.dumps(out, protocol=2)), 'B (proto2)')
one = slim(data[15], KEYS); print(one)
