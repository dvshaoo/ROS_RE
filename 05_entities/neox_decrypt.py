#!/usr/bin/env python3
"""
neox_decrypt.py — NXPK entity def extractor & index scanner for ROS v1117219
Usage:
    python neox_decrypt.py <input.npk> [output_dir]
    python neox_decrypt.py 05_entities/entities.npk 05_entities/out/
    python neox_decrypt.py --index-scan <input.npk> [limit]
    python neox_decrypt.py --obb <patch.obb> <inner_npk> --index-scan [limit]

Features:
- Full NXPK index table parsing (28-byte entries at table_offset)
- Safe collision handling: appends _0x<offset> on name collisions
- Fallback linear zlib stream scanning if index table is unavailable
- Index-only inspection mode for large packages (e.g. script.npk)
"""
import sys
import os
import zlib
import struct
import re
import zipfile

NXPK_HEADER_SIZE = 24
ENTRY_STRUCT_SIZE = 28


def parse_nxpk_header(data: bytes) -> tuple[int, int]:
    """Parse 24-byte NXPK header.
    Returns (entry_count, table_offset).
    """
    if len(data) < NXPK_HEADER_SIZE:
        raise ValueError(f"File too small for NXPK header ({len(data)}B)")
    magic = data[0:4]
    if magic != b'NXPK':
        raise ValueError(f"Not an NXPK file (magic={magic!r})")

    entry_count = struct.unpack_from('<I', data, 0x04)[0]
    table_offset = struct.unpack_from('<I', data, 0x14)[0]
    return entry_count, table_offset


def scan_index(npk_bytes: bytes, limit: int = 20) -> list[dict]:
    """Scan and return entries from the NXPK index table."""
    entry_count, table_offset = parse_nxpk_header(npk_bytes)
    total_table_size = entry_count * ENTRY_STRUCT_SIZE

    print(f"[*] NXPK Header: entry_count={entry_count}, table_offset=0x{table_offset:X} ({table_offset})")
    print(f"[*] Table size: {total_table_size} bytes ({entry_count} entries * {ENTRY_STRUCT_SIZE}B)")

    if table_offset + total_table_size > len(npk_bytes):
        raise ValueError(f"Table offset out of bounds: 0x{table_offset:X} + {total_table_size} > {len(npk_bytes)}")

    entries = []
    print(f"\n[*] Index Census (showing first {min(limit, entry_count)} of {entry_count} entries):")
    print(f"{'Idx':>5} | {'Hash':>10} | {'Offset':>10} | {'CompSz':>8} | {'DecompSz':>8} | {'Flags':>5}")
    print("-" * 56)

    for i in range(entry_count):
        entry_raw = npk_bytes[table_offset + i * ENTRY_STRUCT_SIZE : table_offset + (i + 1) * ENTRY_STRUCT_SIZE]
        h, off, csz, dsz, f4, f5, f6 = struct.unpack('<IIIIIII', entry_raw)
        entry_dict = {
            'index': i,
            'hash': h,
            'offset': off,
            'comp_size': csz,
            'decomp_size': dsz,
            'f4': f4,
            'f5': f5,
            'flags': f6,
        }
        entries.append(entry_dict)
        if i < limit:
            print(f"{i:5d} | 0x{h:08X} | 0x{off:08X} | {csz:8d} | {dsz:8d} | {f6:5d}")

    if entry_count > limit:
        print(f"    ... [{entry_count - limit} entries truncated]")
    return entries


def extract_npk(npk_path: str, out_dir: str) -> list[str]:
    """Extract files from an NXPK archive, using table index with collision resolution."""
    with open(npk_path, 'rb') as f:
        data = f.read()

    os.makedirs(out_dir, exist_ok=True)
    entry_count, table_offset = parse_nxpk_header(data)
    total_table_size = entry_count * ENTRY_STRUCT_SIZE

    print(f"[*] Extracting NXPK: {os.path.basename(npk_path)} ({len(data)}B)")
    print(f"[*] Header: entry_count={entry_count}, table_offset=0x{table_offset:X}")

    entries = []
    use_table = False

    if table_offset + total_table_size <= len(data):
        try:
            for i in range(entry_count):
                entry_raw = data[table_offset + i * ENTRY_STRUCT_SIZE : table_offset + (i + 1) * ENTRY_STRUCT_SIZE]
                h, off, csz, dsz, f4, f5, f6 = struct.unpack('<IIIIIII', entry_raw)
                entries.append((h, off, csz, dsz, f6))
            use_table = True
            print(f"[*] Successfully parsed {len(entries)} index table entries")
        except Exception as e:
            print(f"[!] Index table parse error ({e}), falling back to linear scan")
            use_table = False

    extracted = []
    seen_names: dict[str, list[int]] = {}

    if use_table:
        for idx, (h, off, csz, dsz, f6) in enumerate(entries):
            blob = data[off : off + csz]
            try:
                dec = zlib.decompress(blob)
            except Exception:
                dec = blob  # uncompressed or raw

            name = _guess_name(dec, idx, off)
            base_name, ext = os.path.splitext(name)
            if ext == '.xml' and base_name.endswith('.def'):
                base_stem = base_name[:-4]
                full_ext = '.def.xml'
            else:
                base_stem = base_name
                full_ext = ext

            # Check collision
            if name in seen_names:
                # Collision detected: append offset to make unique
                seen_names[name].append(off)
                unique_name = f"{base_stem}_0x{off:X}{full_ext}"
                print(f"  [!] COLLISION for {name} -> saved as {unique_name}")
            else:
                seen_names[name] = [off]
                unique_name = name

            out_path = os.path.join(out_dir, unique_name)
            with open(out_path, 'wb') as out_file:
                out_file.write(dec)
            extracted.append(out_path)

        # Special case: if entities.xml had collisions, also ensure the master
        # entities file at 0xDE8 has its explicit entities_0xDE8.xml copy
        for orig_name, offsets in seen_names.items():
            if len(offsets) > 1:
                first_off = offsets[0]
                first_entry = [e for e in entries if e[1] == first_off][0]
                first_dec = zlib.decompress(data[first_off : first_off + first_entry[2]])
                explicit_name = f"{os.path.splitext(orig_name)[0]}_0x{first_off:X}.xml"
                exp_path = os.path.join(out_dir, explicit_name)
                with open(exp_path, 'wb') as out_file:
                    out_file.write(first_dec)
                extracted.append(exp_path)
                print(f"  [+] Collision master preserved: {explicit_name} ({len(first_dec)}B)")

    else:
        # Fallback linear scan with collision resolution
        extracted = _extract_npk_linear_scan(data, out_dir)

    print(f"[*] Done: {len(extracted)} files written to {out_dir}")
    return extracted


def _extract_npk_linear_scan(data: bytes, out_dir: str) -> list[str]:
    """Fallback: scan for zlib streams if index is absent."""
    ZLIB_MAGIC = {b'\x78\x9c', b'\x78\xda', b'\x78\x01'}
    extracted = []
    seen_names: dict[str, list[int]] = {}
    i = 0x18
    xml_count = 0

    while i < len(data) - 1:
        if data[i:i+2] in ZLIB_MAGIC:
            try:
                dec = zlib.decompress(data[i:])
                if len(dec) < 20:
                    i += 1
                    continue

                name = _guess_name(dec, xml_count, i)
                base_stem, ext = os.path.splitext(name)

                if name in seen_names:
                    seen_names[name].append(i)
                    unique_name = f"{base_stem}_0x{i:X}{ext}"
                else:
                    seen_names[name] = [i]
                    unique_name = name

                out_path = os.path.join(out_dir, unique_name)
                with open(out_path, 'wb') as out_f:
                    out_f.write(dec)

                extracted.append(out_path)
                xml_count += 1

                recomp = zlib.compress(dec)
                i += max(len(recomp), 4)
                continue
            except zlib.error:
                pass
        i += 1
    return extracted


def _guess_name(dec: bytes, index: int, offset: int = 0) -> str:
    """Try to determine appropriate filename from decompressed payload content."""
    text = dec.decode('utf-8', errors='replace')

    # 1. Check for <ClientName> entity definition
    m = re.search(r'<ClientName>\s*(\S+)', text)
    if m:
        return f"{m.group(1).strip()}.def.xml"

    # 2. Check for BigWorld master entities list
    if 'BigWorld engine' in text or 'entities available for use' in text:
        return "entities.xml"

    # 3. Check for type definitions / aliases
    if '<BOOL>' in text and '<LONG>' in text and '<DWORD>' in text:
        return f"entities_types_0x{offset:X}.xml" if offset else "entities_types.xml"

    # 4. Content mentions entities or entity groups
    if '<entity' in text.lower() or 'entitygroup' in text.lower():
        return f"entities_0x{offset:X}.xml" if offset else f"entity_{index:04d}.xml"

    return f"entity_{index:04d}.xml"


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == '--index-scan':
        npk = sys.argv[2]
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 20
        with open(npk, 'rb') as f:
            data = f.read()
        scan_index(data, limit)

    elif sys.argv[1] == '--obb':
        obb_path = sys.argv[2]
        inner_npk = sys.argv[3]
        limit = int(sys.argv[5]) if len(sys.argv) > 5 else 20
        print(f"[*] Opening OBB {obb_path} -> {inner_npk}")
        with zipfile.ZipFile(obb_path, 'r') as z:
            with z.open(inner_npk) as f:
                data = f.read()
        scan_index(data, limit)

    else:
        npk = sys.argv[1]
        out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(npk), 'out')
        extract_npk(npk, out)
