"""usage: python scratch/find_list_const.py <file> -- print every list/tuple/set constant of the module (fast: uses the cached module signature)."""
import sys, json, os, importlib.util
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\tools')
BS = chr(92)
want = sys.argv[1].replace('/', BS).lower()
spec = importlib.util.spec_from_file_location('disas_mod', r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\disassemble_targets.py')
dm = importlib.util.module_from_spec(spec); spec.loader.exec_module(dm)
cache = json.load(open(r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\script_module_sigs.json', encoding='utf-8'))
co = dm.find_mod(int(cache[want], 16))


def dec(x):
    return x.decode('latin1', 'replace') if isinstance(x, bytes) else x


names = [dec(x) for x in co.get('names', [])]
for n in ('g_import_py_list_client_skip', 'normalLoad', 'MODULE_PREFIXES', 'MODULE_EXTENSIONS'):
    print(n, 'in names' if n in names else 'NOT in names')
for c in co.get('consts', []):
    if isinstance(c, (list, tuple, set, frozenset)) and len(c) >= 1 and not (len(c) and isinstance(next(iter(c)), dict)):
        print(len(c), [dec(x) for x in list(c)[:60]])
