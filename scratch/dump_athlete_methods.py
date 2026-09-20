"""Dump the FULL Athlete client-method name table (EntityType[51]+0x1e8, vector<std::string>) from the live client.
The old dump left every name longer than 22 chars blank: libc++ std::string is 24 bytes; names <=22 chars are inline (SSO),
longer ones store [cap|1][size][ptr] and must be dereferenced. Output: scratch/athlete_methods_full.txt ('[idx] name')."""
import struct, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dump_runtime_types as D
D.ADB[0] = os.environ.get('ADB_PATH', D.ADB[0])
D.PID = D.pid_of()
maps = D.sh(f"su 0 grep libclient.so /proc/{D.PID}/maps | head -1")
base = int(maps.split('-')[0], 16)
vb, ve = struct.unpack('<QQ', D.rd(base + 0x45785f0, 16))
athlete = D.u64(D.rd(vb + 51 * 8, 8), 0)
b, e = struct.unpack('<QQ', D.rd(athlete + 0x1e8, 16))
n = (e - b) // 24
print('pid', D.PID, 'athlete', hex(athlete), 'methods', n)
raw = D.rd(b, n * 24)
out = []
for i in range(n):
    o = i * 24
    if raw[o] & 1 == 0:
        name = raw[o + 1:o + 1 + (raw[o] >> 1)].decode('latin1')
    else:
        ln, ptr = struct.unpack_from('<QQ', raw, o + 8)
        name = D.rd(ptr, ln).decode('latin1') if 0 < ln < 200 else '?'
    out.append(name)
with open(r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\athlete_methods_full.txt', 'w', encoding='utf-8') as f:
    for i, nm in enumerate(out):
        f.write('[%4d] %s\n' % (i, nm))
print('blank/?:', sum(1 for x in out if not x or x == '?'))
for i, nm in enumerate(out):
    if nm in ('onGetAnniversaryAirShipRank', 'syncMonthPayRebateSpecialAwardInfo', 'onPersonalRecommendStateUpdated',
              'onSPUpdated', 'onGPUpdated', 'onYBUpdated', 'onUpdateLuckyCarnivalData', 'gmsyncRedPoints'):
        print(i, nm)
