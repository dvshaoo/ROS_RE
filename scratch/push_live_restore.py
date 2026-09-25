import sys, os, socket, struct, pickle, time

sys.path.insert(0, 'tools')
sys.path.insert(0, 'mitm')
import local_baseapp_capture as lbc

# Client destination from latest log
addr = ('127.0.0.1', 58678)
key = '136e56f5'

# Bind with SO_REUSEADDR on 25010
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(('0.0.0.0', 25010))
    print("Bound to 25010 with SO_REUSEADDR")
except Exception as e:
    print("Could not bind 25010 directly:", e)

# 1. Update Currency:
print("Sending currency updates to", addr, "key:", key)
# onGPUpdated(INT64 gp, INT32 src) idx 202
lbc.send_entity_method(s, addr, key, 1, 202, struct.pack('<qi', 999999, 0), flags=0x0008, num_methods=1131)
# onSPUpdated(INT64 sp, INT32 src) idx 201
lbc.send_entity_method(s, addr, key, 1, 201, struct.pack('<qi', 50000, 0), flags=0x0008, num_methods=1131)
# onYBUpdated(INT64 freeYuanbao, INT64 payYuanbao, INT32 src) idx 203
lbc.send_entity_method(s, addr, key, 1, 203, struct.pack('<qqi', 999999, 0, 0), flags=0x0008, num_methods=1131)
# onCurrencyUpdated(INT32 id, INT64 val, INT32 src) idx 204
for cid in (1, 2, 3, 9, 91, 202, 213, 214):
    lbc.send_entity_method(s, addr, key, 1, 204, struct.pack('<iqi', cid, 999999, 0), flags=0x0008, num_methods=1131)

# 2. Update Clothes: Cowboy outfit [112689, 105688, 111689, 110212]
wear = [112689, 105688, 111689, 110212]
print("Sending clothes update:", wear)
lbc.send_entity_method(s, addr, key, 1, 355, struct.pack('<i', 1), flags=0x0008, num_methods=1131)
lbc.send_entity_method(s, addr, key, 1, 344, lbc._int_array(wear), flags=0x0008, num_methods=1131)
lbc.send_entity_method(s, addr, key, 1, 359, lbc._int_array(wear), flags=0x0008, num_methods=1131)
for item_id in wear:
    lbc.send_entity_method(s, addr, key, 1, 356, struct.pack('<i', item_id), flags=0x0008, num_methods=1131)

s.close()
print("Live restore pushed successfully!")
