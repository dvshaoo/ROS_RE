r"""usage: python tools/script_disas.py <script path e.g. ui/UIMain.py> <func name> [<func name> ...]
Disassembles the named functions/methods of a mobile script (decrypted from script.npk) via scratch/disassemble_targets.disas."""
import sys, importlib.util, json, os
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\tools')
import script_index as SI
spec = importlib.util.spec_from_file_location('disas_mod', r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\disassemble_targets.py')
dm = importlib.util.module_from_spec(spec); spec.loader.exec_module(dm)
sub = sys.argv[1].lower().replace('/', chr(92)); wanted = {n.encode() for n in sys.argv[2:]}
CACHE_PATH = r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\script_module_sigs.json'

def walk(co):
    if not isinstance(co, dict):
        return
    if co.get('name', b'') in wanted:
        dm.disas(co)
    for c in co.get('consts', []) if isinstance(co.get('consts'), (list, tuple)) else []:
        if isinstance(c, dict) and 'code' in c:
            walk(c)

cache = {}
if os.path.exists(CACHE_PATH):
    try:
        cache = json.load(open(CACHE_PATH, encoding='utf-8'))
    except Exception:
        cache = {}

if sub in cache:
    co = dm.find_mod(int(cache[sub], 16))
    if co:
        walk(co)
        raise SystemExit(0)

for sig, co in SI.iter_modules():
    fn = co.get('file'); fn = fn.decode('latin1', 'ignore') if isinstance(fn, bytes) else str(fn)
    key = fn.lower()
    if key == sub:
        cache[key] = '0x%08x' % sig
        with open(CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, sort_keys=True)
        walk(co)
        break
