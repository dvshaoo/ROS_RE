r"""usage: python scratch/dump_module_funcs.py <script-file e.g. helpers/market_record_points.py> [name-regex]

Dumps the disassembly of every code object in a decrypted script.npk module
optionally filtered by a regex on the code object's name.  Faster than
tools/script_disas.py because it resolves the module through the sig cache
(scratch/script_module_sigs.json) instead of iterating/decrypting every module.

Read-only: this is a pure reader over the decrypted asset, no patching.
"""
import sys, os, json, re, importlib.util

LEGACY = r'C:\Users\Raysoo\Downloads\ROS_RE'
sys.path.insert(0, os.path.join(LEGACY, 'tools'))
import script_index as SI  # noqa: E402  (deferred import: tools/ is on sys.path)

spec = importlib.util.spec_from_file_location(
    'disas_mod', os.path.join(LEGACY, 'scratch', 'disassemble_targets.py'))
dm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dm)

CACHE_PATH = os.path.join(LEGACY, 'scratch', 'script_module_sigs.json')


def iter_code(co, depth=0):
    """Yield (depth, code_object) for every nested code object, in definition order."""
    if not isinstance(co, dict):
        return
    yield depth, co
    for c in co.get('consts', []) if isinstance(co.get('consts'), (list, tuple)) else []:
        if isinstance(c, dict) and 'code' in c:
            for item in iter_code(c, depth + 1):
                yield item


def resolve_sig(sub):
    sub_l = sub.lower().replace('/', '\\')
    cache = {}
    if os.path.exists(CACHE_PATH):
        try:
            cache = json.load(open(CACHE_PATH, encoding='utf-8'))
        except Exception:
            cache = {}
    if sub_l in cache:
        return int(cache[sub_l], 16)
    for sig, co in SI.iter_modules():          # slow fallback, only on cache miss
        fn = co.get('file')
        fn = fn.decode('latin1', 'ignore') if isinstance(fn, bytes) else str(fn)
        key = fn.lower()
        if key == sub_l:
            cache[key] = '0x%08x' % sig
            os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
            json.dump(cache, open(CACHE_PATH, 'w', encoding='utf-8'), indent=2, sort_keys=True)
            return sig
    return None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    sub = sys.argv[1]
    pat = re.compile(sys.argv[2]) if len(sys.argv) > 2 else None

    sig = resolve_sig(sub)
    if sig is None:
        print('module not found in script.npk: %s' % sub)
        return 2

    co = dm.find_mod(sig)
    if not co:
        print('module could not be decoded: %s (0x%08x)' % (sub, sig))
        return 3

    print('==== module %s  sig=0x%08x ====' % (sub, sig))
    for depth, c in iter_code(co):
        name = dm.nm(c.get('name'))
        if not name or name == '<module>':
            if pat is not None:
                continue
            label = '<module-body>'
        else:
            if pat is not None and not pat.search(name):
                continue
            label = name
        print()
        print('-------- %s%s (nlocals=%s stack=%s)' % (
            '  ' * depth, label, c.get('nlocals'), c.get('stacksize')))
        try:
            dm.disas(c)
        except Exception as e:
            print('   [disas error] %r' % (e,))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
