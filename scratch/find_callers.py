"""usage: python scratch/find_callers.py <name1,name2> [<file substr>] -- code objects whose NAMES contain any of the given names"""
import sys
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\tools')
import script_index as SI

want = set(sys.argv[1].split(','))
sub = sys.argv[2].lower().replace('/', chr(92)) if len(sys.argv) > 2 else None


def dec(x):
    return x.decode('latin1', 'replace') if isinstance(x, bytes) else x


for sig, co in SI.iter_modules():
    fn = dec(co.get('file'))
    if not isinstance(fn, str):
        continue
    if sub and sub not in fn.lower():
        continue

    def walk(c, path):
        nm = dec(c.get('name', b''))
        names = [dec(x) for x in c.get('names', [])] if isinstance(c.get('names'), (list, tuple)) else []
        hit = [n for n in names if n in want]
        if hit and nm != '<module>':
            print('##', fn, path + '.' + nm, hit, '| names:', names[:30])
        for x in c.get('consts', []) if isinstance(c.get('consts'), (list, tuple)) else []:
            if isinstance(x, dict) and 'code' in x:
                walk(x, path + '.' + nm)
    walk(co, '')
