import sys, os
sys.path.insert(0, 'tools')
import script_index as SI

for s, c in SI.iter_modules():
    fn = str(c.get('file', ''))
    if 'uiselectcharacter' in fn.lower():
        print("Found file:", fn)
        for m in c.get('consts', []):
            if isinstance(m, dict) and 'code' in m:
                name = m.get('name', b'').decode('latin1', 'ignore')
                print("  method:", name)
