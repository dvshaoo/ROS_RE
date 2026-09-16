import sys
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\scratch')
from decode_clientinterface_table import find_bl_callers, resolve, get_string_at

calls = find_bl_callers(0x98b30c)
prev = None
for i in range(min(22, len(calls))):
    pc = calls[i]
    x1, w2, w3 = resolve(pc, prev)
    s = get_string_at(x1) if x1 else b'???'
    print(i, hex(pc), s, "lenStyle=", w2, "lenParam=", w3)
    prev = pc
