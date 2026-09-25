import sys, importlib.util
sys.path.insert(0, 'tools')
spec = importlib.util.spec_from_file_location('disas_mod', r'scratch/disassemble_targets.py')
dm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dm)

co = dm.find_mod(0x32d7c278)

def search_co(co, prefix=""):
    name = co.get('name', b'').decode('latin1', 'ignore')
    consts = co.get('consts', [])
    for c in consts:
        if isinstance(c, dict) and 'code' in c:
            mname = c.get('name', b'').decode('latin1', 'ignore')
            print("UISelectCharacter method:", mname)
            search_co(c, prefix + mname + " -> ")

search_co(co)
