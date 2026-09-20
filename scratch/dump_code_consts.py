"""usage: python scratch/dump_code_consts.py <file (ui/UISupplyPackage.py)> <func1,func2,...>  -- names/consts of matching code objects"""
import sys
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\tools')
import script_index as SI
BS = chr(92)
want = sys.argv[1].replace('/', BS)
funcs = set(sys.argv[2].split(','))
def dec(x): return x.decode('latin1', 'replace') if isinstance(x, bytes) else x
for sig, co in SI.iter_modules():
    if dec(co.get('file')) != want:
        continue
    def walk(c, path):
        nm = dec(c.get('name', b''))
        cs = c.get('consts') if isinstance(c.get('consts'), (list, tuple)) else []
        names = [dec(x) for x in c.get('names', [])] if isinstance(c.get('names'), (list, tuple)) else []
        if nm in funcs:
            print('##', path + '.' + nm)
            print('  varnames', [dec(x) for x in c.get('varnames', [])][:14])
            print('  names', names[:60])
            print('  consts', [x if not isinstance(x, bytes) else dec(x) for x in cs if not isinstance(x, dict)][:60])
        for x in cs:
            if isinstance(x, dict) and 'code' in x:
                walk(x, path + '.' + nm)
    walk(co, '')
