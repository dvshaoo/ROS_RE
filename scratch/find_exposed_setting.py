import xml.etree.ElementTree as ET

tree = ET.parse('05_entities/out/Athlete.def.xml')
root = tree.getroot()
base_methods = root.find('BaseMethods')

exposed_idx = 0
for m in base_methods:
    is_exp = m.find('Exposed') is not None
    if is_exp:
        print(f"[{exposed_idx}] {m.tag}")
        exposed_idx += 1
