import sys
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\scratch')
from xref_lib import DATA, xrefs

# Search for "Account" as entity name in DATA
targets = [b'Account\x00', b'Avatar\x00', b'Login\x00', b'EntityDef\x00']
for t in targets:
    pos = 0
    while True:
        idx = DATA.find(t, pos)
        if idx == -1:
            break
        print(f'Found {t} at {hex(idx)}')
        pos = idx + len(t)
        # check xrefs
        h = xrefs(idx)
        if h:
            print(f'  xrefs: {[hex(x) for x in h]}')
        if pos > 0x3000000: # don't loop forever
            break
