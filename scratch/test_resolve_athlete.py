import os
import re
import glob

DEFS = r"c:\Users\Raysoo\Downloads\ROS_RE\05_entities\out"

def client_methods(xml_path):
    t = open(xml_path, encoding="utf-8", errors="replace").read()
    m = re.search(r"<ClientMethods>(.*?)</ClientMethods>", t, re.S)
    if not m:
        return []
    meths = re.findall(r"^[ \t]*<(\w+)>(?:[ \t]*<!--.*?-->)?\s*$", m.group(1), re.M)
    return [x for x in meths if x != "Arg"]

def implements(xml_path):
    t = open(xml_path, encoding="utf-8", errors="replace").read()
    m = re.search(r"<Implements>(.*?)</Implements>", t, re.S)
    if not m:
        return []
    return re.findall(r"<Interface>\s*(\w+)\s*</Interface>", m.group(1))

def find_def(name):
    # Try name.def.xml, name.xml
    for cand in [os.path.join(DEFS, f"{name}.def.xml"), os.path.join(DEFS, f"{name}.xml")]:
        if os.path.isfile(cand):
            return cand
    return None

def flattened(xml_path, _seen=None):
    _seen = _seen or set()
    out = []
    for iface in implements(xml_path):
        cand = find_def(iface)
        if cand and cand not in _seen:
            _seen.add(cand)
            out += flattened(cand, _seen)
        elif not cand:
            pass
    out += client_methods(xml_path)
    return out

athlete_file = find_def("Athlete")
print("Athlete file:", athlete_file)
order = flattened(athlete_file)
print(f"Total Athlete client methods: {len(order)}")
for i, m in enumerate(order):
    if "showSelect" in m or "Character" in m or "Role" in m or "Hall" in m:
        print(f"  {i:3d}  {m} (msgid {128+i})")
