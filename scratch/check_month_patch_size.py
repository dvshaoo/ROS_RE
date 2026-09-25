"""Validate an in-place date-only assets.npk monthly-supply patch candidate."""
import os
import struct
import sys
import zlib

sys.path.insert(0, 'tools')
import load_table as tables

signature = 0x5c64e12a
path = tables.NPK
blob = open(path, 'rb').read()
index_offset = struct.unpack_from('<I', blob, 0x14)[0]
count = struct.unpack_from('<I', blob, 4)[0]
for i in range(count):
    entry = index_offset + i * 28
    sig, offset, length, original_length = struct.unpack_from('<IIII', blob, entry)
    if sig != signature:
        continue
    packed = blob[offset:offset + length]
    raw = zlib.decompress(packed) if packed[:2] == b'x\x9c' else packed
    replacement = (raw.replace(b'2018.11.14', b'2026.01.01')
                       .replace(b'2021.12.30', b'2026.12.30'))
    packed_replacement = zlib.compress(replacement)
    print('entry', i, 'offset', offset, 'packed', length, 'raw', len(raw),
          'declared_raw', original_length)
    print('replacement raw', len(replacement), 'packed', len(packed_replacement),
          'fits_in_place', len(packed_replacement) <= length)
    print('changed monthly dates', raw.count(b'2018.11.14'), raw.count(b'2021.12.30'))
    break
else:
    raise SystemExit('monthly table not found')
