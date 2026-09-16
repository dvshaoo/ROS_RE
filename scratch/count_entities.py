import xml.etree.ElementTree as ET

tree = ET.parse(r'c:\Users\Raysoo\Downloads\ROS_RE\05_entities\out\entities.xml')
root = tree.getroot()

for idx, child in enumerate(root):
    if child.tag in ['Account', 'BattleAccount', 'Athlete', 'LoginProxy']:
        print(f"Index {idx}: {child.tag}")
