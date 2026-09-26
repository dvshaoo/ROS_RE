import sys, json
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\RulesOfSurvivalOld (2)\RulesOfSurvivalOld\tools\re')
import ros_script_decrypt as RS
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\scratch')
from npk_patch_lib import NPK_PATH, get_member_raw
from npk_find_func_offset import find_function_code_span

sigs = json.load(open(r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\script_module_sigs.json'))
sig = int(sigs['ui\\uilogin.py'], 16)
data = open(NPK_PATH, 'rb').read()
raw, off, ln, oln, tabpos = get_member_raw(data, sig)
M = RS.member_marshal(raw)

s, e = find_function_code_span(M, 'showGuestAccountRemind')
raw_bytes = M[s:e]
plain = RS.deob(raw_bytes)
print('plain len', len(plain))
print('plain first 10 bytes:', plain[:10].hex())
print('plain last 10 bytes:', plain[-10:].hex())
