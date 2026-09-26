r"""usage: python scratch/dump_module_consts.py <script-file e.g. helpers/market_record_points.py> [code-object-name-regex]

Prints, for a decrypted script.npk module, the module body's and every nested
code object's VARNAMES / NAMES / CONSTS (recursively, non-mutating) so literal
data like INIT_MARKET_RECORD_POINT can be read even when the NeoX opcode
permutation is only partially known.

Read-only: pure reader over the decrypted asset.
"""
import sys, os, re, importlib.util

LEGACY = r'C:\Users\Raysoo\Downloads\ROS_RE'
sys.path.insert(0, os.path.join(LEGACY, 'tools'))

spec = importlib.util.spec_from_file_location(
    'disas_mod', os.path.join(LEGACY, 'scratch', 'disassemble_targets.py'))
dm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dm)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dump_module_funcs import resolve_sig, iter_code  # noqa: E402


def show(x, depth=0):
    if isinstance(x, dict) and 'code' in x:
        return '<code %s>' % dm.nm(x.get('name'))
    if isinstance(x, bytes):
        try:
            return repr(x.decode('utf-8'))
        except Exception:
            return repr(x)
    return repr(x)


def main():
    sig = resolve_sig(sys.argv[1])
    if sig is None:
        print('module not found: %s' % sys.argv[1])
        return 2
    co = dm.find_mod(sig)
    pat = re.compile(sys.argv[2]) if len(sys.argv) > 2 else None

    for depth, c in iter_code(co):
        name = dm.nm(c.get('name')) or '<module-body>'
        if pat is not None and not pat.search(name):
            continue
        print('=' * 70)
        print('%s%s' % ('  ' * depth, name))
        print('  varnames:', [dm.nm(v) for v in c.get('varnames', []) or []])
        print('  names   :', [dm.nm(v) for v in c.get('names', []) or []])
        cs = c.get('consts') if isinstance(c.get('consts'), (list, tuple)) else []
        for i, v in enumerate(cs):
            print('  consts[%d] = %s' % (i, show(v)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
