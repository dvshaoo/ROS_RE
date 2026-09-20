"""usage: python scratch/module_lists.py <file> <name1,name2> -- dump list constants (with the code-object NAMES) of functions/module that mention any of the names"""
import sys, json, importlib.util
BS = chr(92)
want = sys.argv[1].replace('/', BS).lower(); names_w = set(sys.argv[2].split(','))
spec = importlib.util.spec_from_file_location('disas_mod', r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\disassemble_targets.py')
dm = importlib.util.module_from_spec(spec); spec.loader.exec_module(dm)
cache = json.load(open(r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\script_module_sigs.json', encoding='utf-8'))
if want not in cache:
    sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\tools')
    import script_index as SI
    for sig, c in SI.iter_modules():
        f = c.get('file'); f = f.decode('latin1') if isinstance(f, bytes) else str(f)
        if f.lower() == want:
            cache[want] = '0x%08x' % sig
            json.dump(cache, open(r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\script_module_sigs.json', 'w', encoding='utf-8'), indent=2, sort_keys=True)
            break
co = dm.find_mod(int(cache[want], 16))
def dec(x): return x.decode('latin1', 'replace') if isinstance(x, bytes) else x
def walk(c, path):
    nm = dec(c.get('name', b''))
    names = [dec(x) for x in c.get('names', [])] if isinstance(c.get('names'), (list, tuple)) else []
    if names_w & set(names):
        print('##', path + '.' + nm, sorted(names_w & set(names)))
        for k in c.get('consts', []):
            if isinstance(k, (list, tuple)) and len(k) > 1:
                print('   LIST', len(k), [dec(x) for x in k][:80])
    for k in c.get('consts', []) if isinstance(c.get('consts'), (list, tuple)) else []:
        if isinstance(k, dict) and 'code' in k:
            walk(k, path + '.' + nm)
walk(co, '')
