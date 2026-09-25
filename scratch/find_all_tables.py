import sys, re, os
sys.path.insert(0, 'tools')
import load_table as LT

results = []
for sig, raw in LT.members():
    if b'data =' in raw:
        txt = raw[:600].decode('utf-8', errors='replace')
        if any(w in txt for w in ('商城', '商店', 'MallGoodItem', 'types_mall_item')):
            m = re.search(r'name\s*=\s*["\']([^"\']+)["\']', txt)
            name = m.group(1) if m else 'no-name'
            results.append((sig, name, len(raw)))

print(f"Total matching tables: {len(results)}")
for sig, name, sz in sorted(results, key=lambda x: -x[2]):
    print(f"{hex(sig)}: {name} ({sz} bytes)")
