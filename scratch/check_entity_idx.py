import xml.etree.ElementTree as ET

tree = ET.parse(r'c:\Users\Raysoo\Downloads\ROS_RE\05_entities\out\entities.xml')
root = tree.getroot()

entities = []
for i, child in enumerate(root):
    # skip comments
    if not isinstance(child.tag, str):
        continue
    entities.append((len(entities), child.tag))
    if child.tag == 'Account':
        print(f'Account found at 0-based index {len(entities)-1}, total entities before: {len(entities)-1}')

print(f'Total entities declared: {len(entities)}')
for idx, tag in entities:
    if 'Account' in tag or 'Avatar' in tag or idx < 10:
        print(f'{idx}: {tag}')
