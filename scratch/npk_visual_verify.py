import sys
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\scratch')
import disassemble_targets as dt
import json

sigs = json.load(open(r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\script_module_sigs.json'))
sig = int(sigs['ui\\uilogin.py'], 16)

dt.npk_path = r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\script_patched.npk'
co = dt.find_mod(sig)


def walk(c):
    if isinstance(c, dict):
        if c.get('name') == b'showGuestAccountRemind':
            dt.disas(c)
            return True
        for cc in (c.get('consts') or []):
            if walk(cc):
                return True
    return False


walk(co)
