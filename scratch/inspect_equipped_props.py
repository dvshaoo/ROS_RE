import sys,json
sys.path.insert(0,'mitm')
import local_baseapp_capture as l
items=[1111326,1112326,1110326,1110324,120014,120920,1112325,1111325,1110325]
t=l._prop_tables().get(0xa2f095a2,{})
for x in items:
 r=t.get(x,{})
 print(x,json.dumps(r.get('value',{}),ensure_ascii=False,sort_keys=True)[:2000])
