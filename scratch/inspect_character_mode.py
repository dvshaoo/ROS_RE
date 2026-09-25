import sys, importlib.util
sys.path.insert(0, 'tools')
spec = importlib.util.spec_from_file_location('disas_mod', r'scratch/disassemble_targets.py')
dm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dm)

with open('scratch/selectmode_trace.txt', 'w', encoding='utf-8') as out:
    def inspect_co(co, prefix=""):
        name = co.get('name', b'').decode('latin1', 'ignore')
        consts = co.get('consts', [])
        names = [n.decode('latin1', 'ignore') if isinstance(n, bytes) else str(n) for n in co.get('names', [])]
        
        has_sm = False
        for c in consts:
            if isinstance(c, (str, bytes)) and 'selectmode' in str(c).lower():
                has_sm = True
        for n in names:
            if 'selectmode' in n.lower():
                has_sm = True
                
        if has_sm:
            out.write(f"\n[MATCH] {prefix}{name} mentions SelectMode!\n")
            out.write(f"   names: {names}\n")
            out.write(f"   consts: {[c for c in consts if not isinstance(c, dict)][:15]}\n")
            # redirect stdout to out for disas
            old_stdout = sys.stdout
            sys.stdout = out
            try:
                dm.disas(co)
            finally:
                sys.stdout = old_stdout
            out.write("\n" + "="*60 + "\n")
            
        for c in consts:
            if isinstance(c, dict) and 'code' in c:
                inspect_co(c, prefix + name + " -> ")

    out.write("--- Searching in UISelectCharacter (0x32d7c278) ---\n")
    co = dm.find_mod(0x32d7c278)
    inspect_co(co)

    out.write("\n--- Searching in Athlete (0xc7ef2b17) ---\n")
    co_ath = dm.find_mod(0xc7ef2b17)
    inspect_co(co_ath)

print("Done! Written to scratch/selectmode_trace.txt")
