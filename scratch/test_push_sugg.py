import sys, socket, struct, pickle, time
sys.path.insert(0, 'tools')
sys.path.insert(0, 'mitm')
import local_baseapp_capture as lbc

# The active client port:
dest = ('127.0.0.1', 63644)
key = '136e56f5'
print("Targeting ACTIVE client:", dest, "with key:", key)

goods = lbc._mall_runtime_goods()
# Filter goods for Suggested (TIME_APPEARANCE)
sugg = {k: v for k, v in goods.items() if v.get('IS_DISPLAY_IN_TIME_APPEARANCE')}
# Take 10 items
items = dict(list(sugg.items())[:10])

# Ensure each item has SECONDARY_DISPLAY_TYPE_ENUM set (1 for first 5, 2 for next 5)
for i, (gid, val) in enumerate(items.items()):
    val['SECONDARY_DISPLAY_TYPE_ENUM'] = 1 if i < 5 else 2
    val['ONLINE_TIME'] = '2018.1.1 00:00:00'
    val['OFFLINE_TIME'] = '2035.12.31 23:59:59'

blob = pickle.dumps(items, protocol=2)
py_arg = lbc._packed_int(len(blob)) + blob
print("Payload len:", len(py_arg))

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(('0.0.0.0', 25010))
    print("Bound to 25010 successfully!")
except Exception as e:
    print("Bind notice:", e)

# 1. Send method 450
print("Sending 450 (Appearance Mall)...")
lbc.send_entity_method(s, dest, key, 1, 450, py_arg, flags=0x0008, num_methods=1131)
time.sleep(0.05)

# 2. Send method 448
print("Sending 448 (General Mall)...")
lbc.send_entity_method(s, dest, key, 1, 448, py_arg, flags=0x0008, num_methods=1131)
time.sleep(0.05)

# 3. Send method 449 for type 16 (TIME_APPERANCE) and 0 (ALL)
for t in (16, 0):
    args = struct.pack('<I', t) + py_arg
    print("Sending 449 (type=%d)..." % t)
    lbc.send_entity_method(s, dest, key, 1, 449, args, flags=0x0008, num_methods=1131)
    time.sleep(0.05)

print("All unfragmented mall packets sent!")
s.close()
