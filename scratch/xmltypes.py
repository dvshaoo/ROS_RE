"""Structured (ElementTree) access to the entity XML type declarations.

Why this exists: the earlier regex-based type extraction could not see past a nested
<Properties> block, so any ARRAY-of-FIXED_DICT property came back as type None and was
special-cased to "ARRAY, count 0" (4 bytes). Two of those (childBaseClientPropertyList,
childClientPropertyList2) are really `ARRAY <of> FIXED_DICT ... </of> <size> 1 </size>`:
a FIXED-size array, whose element count is NOT on the wire (decompiled
SequenceDataType::createFromStream reads the 4-byte count only when the type's fixed size
is 0), so the client consumed the entire dict body from the bytes that followed and the
whole stream desynchronized from ordinal 207 onward.
"""
import os, re
import xml.etree.ElementTree as ET

ROOT = r'C:\Users\Raysoo\Downloads\ROS_RE'
XMLDIR = os.path.join(ROOT, '05_entities', 'out')


def load_xml(path):
    txt = open(path, encoding='utf-8', errors='replace').read()
    txt = re.sub(r'<!--.*?-->', '', txt, flags=re.S)
    txt = txt.replace('&', '&amp;')          # bare ampersands appear in a few defaults
    return ET.fromstring(txt)


def head_word(elem):
    """First token of the element's own text, e.g. 'ARRAY' for `<Type> ARRAY <of>..`."""
    t = (elem.text or '').split()
    return t[0] if t else ''


def load_all_property_decls():
    """name -> list of (file, <name> element) for every entity property declaration."""
    decls = {}
    for fn in sorted(os.listdir(XMLDIR)):
        if not fn.endswith('.xml') or fn.startswith('entities_types') or fn == 'entities.xml':
            continue
        try:
            root = load_xml(os.path.join(XMLDIR, fn))
        except ET.ParseError:
            continue
        props = root.find('Properties')
        if props is None:
            continue
        for p in props:
            if p.find('Type') is not None:
                decls.setdefault(p.tag, []).append((fn, p))
    return decls


def load_aliases():
    """alias name -> element (either a plain-type alias or a FIXED_DICT definition)."""
    out = {}
    for fn in os.listdir(XMLDIR):
        if fn.startswith('entities_types'):
            root = load_xml(os.path.join(XMLDIR, fn))
            for e in root:
                out[e.tag] = e
    return out


if __name__ == '__main__':
    d = load_all_property_decls()
    a = load_aliases()
    print('property names with declarations:', len(d), '| aliases:', len(a))
