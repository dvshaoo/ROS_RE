import struct, collections

path = r"C:\Users\Raysoo\Downloads\ROS_RE\04_obb\extracted\script.npk"
with open(path, 'rb') as f:
    data = f.read()

entry_count = struct.unpack_from('<I', data, 0x04)[0]
table_offset = struct.unpack_from('<I', data, 0x14)[0]
print("entries:", entry_count, "table_off:", hex(table_offset))

entries = []
for i in range(entry_count):
    off = table_offset + i * 28
    h, o, csz, dsz, f4, f5, f6 = struct.unpack_from('<IIIIIII', data, off)
    entries.append((h, o, csz, dsz, f4, f5, f6))

# look at first-4-byte signatures across all entries
sigs = collections.Counter()
for h, o, csz, dsz, f4, f5, f6 in entries:
    sigs[data[o:o+4]] += 1

print("\ntop 10 leading-4-byte signatures across all", entry_count, "entries:")
for s, c in sigs.most_common(10):
    print("  ", s.hex(), repr(s), "->", c)

print("\nflag field distributions:")
print("  f4:", collections.Counter(e[4] for e in entries).most_common(5))
print("  f5:", collections.Counter(e[5] for e in entries).most_common(5))
print("  f6:", collections.Counter(e[6] for e in entries).most_common(5))

print("\nfirst 3 entries, first 64 bytes:")
for h, o, csz, dsz, f4, f5, f6 in entries[:3]:
    blob = data[o:o+64]
    print(f"  off=0x{o:x} csz={csz}")
    print("   hex:", blob[:48].hex())
    print("   asc:", ''.join(chr(b) if 32 <= b < 127 else '.' for b in blob[:48]))
