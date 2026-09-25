import sys, os, socket, struct, pickle, time

sys.path.insert(0, 'tools')
sys.path.insert(0, 'mitm')
import local_baseapp_capture as lbc

# 1. Bind to UDP 25010 with SO_REUSEADDR
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('0.0.0.0', 25010))

# 2. Sniff one incoming packet to get the exact current client port
s.settimeout(2.0)
try:
    data, addr = s.recvfrom(4096)
    print("Sniffed active client from:", addr, "data len:", len(data))
except Exception as e:
    addr = ('127.0.0.1', 54083)
    print("Sniff timeout, falling back to:", addr)

# 3. Get Blowfish key from running process
pid = lbc._get_pid()
key = lbc.fast_find_session_key(pid) or '3f730241'
print("Using Blowfish key:", key, "pid:", pid)

# 4. Build goods dict
goods = lbc._mall_runtime_goods()
print("Total goods to send:", len(goods))
blob = pickle.dumps(goods, protocol=0)
py_arg = lbc._packed_int(len(blob)) + blob

# 5. Send onQueryAvailableMallGoods (idx 448)
print("Sending onQueryAvailableMallGoods (idx 448)...")
lbc.send_entity_method(s, addr, key, 1, 448, py_arg, flags=0x0008, num_methods=1131)

# 6. Send onQueryAvailableMallGoodsForAppearanceMall (idx 450)
print("Sending onQueryAvailableMallGoodsForAppearanceMall (idx 450)...")
lbc.send_entity_method(s, addr, key, 1, 450, py_arg, flags=0x0008, num_methods=1131)

# 7. Send onQueryAvailableMallGoodsByType (idx 449) for type 0, 8, 128
for t in (0, 8, 128, 1024, 32, 512):
    args = struct.pack('<I', t) + py_arg
    print("Sending onQueryAvailableMallGoodsByType (idx 449, type=%d)..." % t)
    lbc.send_entity_method(s, addr, key, 1, 449, args, flags=0x0008, num_methods=1131)
    time.sleep(0.05)

print("All mall RPCs sent successfully!")
s.close()
