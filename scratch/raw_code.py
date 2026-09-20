"""usage: python scratch/raw_code.py <file> <func> [start end] -- hex of co_code (uses cached module sig)"""
import sys, json, importlib.util
BS = chr(92)
want = sys.argv[1].replace('/', BS).lower(); fn = sys.argv[2]
spec = importlib.util.spec_from_file_location('disas_mod', r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\disassemble_targets.py')
dm = importlib.util.module_from_spec(spec); spec.loader.exec_module(dm)
cache = json.load(open(r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\script_module_sigs.json', encoding='utf-8'))
co = dm.find_mod(int(cache[want], 16))
def dec(x): return x.decode('latin1', 'replace') if isinstance(x, bytes) else x
def walk(c):
    if dec(c.get('name', b'')) == fn and 'code' in c:
        code = c['code']
        a = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        b = int(sys.argv[4]) if len(sys.argv) > 4 else len(code)
        print('len', len(code), 'keys', [k for k in c.keys()][:20])
        print(code[a:b].hex(' '))
        return True
    for k in c.get('consts', []) if isinstance(c.get('consts'), (list, tuple)) else []:
        if isinstance(k, dict) and 'code' in k and walk(k):
            return True
walk(co)
