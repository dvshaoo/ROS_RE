"""Deploys scratch/script_patched.npk into a COPY of patch.1117219.com.netease.chiji.obb.

script.npk is stored UNCOMPRESSED (compress_type=0) inside the patch OBB
zip, and our patched npk is byte-for-byte the same length as the original
(we padded it to match exactly) -- so this is a pure in-place overwrite of
that one zip entry's data region, no zip rebuild needed. Computes the exact
data offset from the local file header (header_offset + 30 + fn_len +
extra_len), verifies it against zipfile's own read before touching
anything, writes to a NEW output file, and re-verifies via zipfile afterward.
"""
import zipfile
import struct
import shutil
import zlib

SRC_OBB = r'C:\Users\Raysoo\Downloads\ROS_RE\04_obb\patch.1117219.com.netease.chiji.obb'
OUT_OBB = r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\patch_with_nag_fix.obb'
PATCHED_NPK = r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\script_patched.npk'
ENTRY_NAME = 'script.npk'

LOCAL_HEADER_FIXED_SIZE = 30  # signature(4)+version(2)+flags(2)+method(2)+time(2)+date(2)+crc(4)+csize(4)+usize(4)+fnlen(2)+extralen(2)


def main():
    z = zipfile.ZipFile(SRC_OBB)
    info = z.getinfo(ENTRY_NAME)
    assert info.compress_type == 0, 'expected STORED, not compressed'

    with open(SRC_OBB, 'rb') as f:
        f.seek(info.header_offset)
        header = f.read(LOCAL_HEADER_FIXED_SIZE)
        sig, ver, flags, method, mtime, mdate, crc, csize, usize, fnlen, extralen = struct.unpack('<IHHHHHIIIHH', header)
        assert sig == 0x04034b50, 'bad local file header signature'
        data_start = info.header_offset + LOCAL_HEADER_FIXED_SIZE + fnlen + extralen
        print('local header: fnlen=%d extralen=%d data_start=0x%x usize=%d' % (fnlen, extralen, data_start, usize))
        assert usize == info.file_size

        f.seek(data_start)
        existing = f.read(info.file_size)

    ref = z.read(ENTRY_NAME)
    assert existing == ref, 'computed data offset does not match zipfile read -- header parsing is wrong, aborting'
    print('data offset verified correct (matches zipfile read).')

    patched = open(PATCHED_NPK, 'rb').read()
    assert len(patched) == info.file_size, 'patched npk size (%d) != original entry size (%d), cannot do in-place overwrite' % (len(patched), info.file_size)
    new_crc = zlib.crc32(patched) & 0xffffffff
    print('original CRC32: 0x%08x   new CRC32: 0x%08x' % (crc, new_crc))

    # Central directory record for this entry: find it so its CRC32 field
    # (same layout offset as the local header's, but inside the central
    # directory entry) can also be corrected -- both copies must be right
    # for the zip to be valid by spec, even if this particular reader only
    # ever consults one of them.
    with open(SRC_OBB, 'rb') as f:
        cd_data = f.read()
    needle = ENTRY_NAME.encode('ascii')
    cd_local_header_off = struct.pack('<I', info.header_offset)
    cd_entry_pos = None
    search_from = 0
    while True:
        idx = cd_data.find(b'PK\x01\x02', search_from)
        if idx == -1:
            break
        # central directory file header: sig(4) then fields; local header
        # offset is at fixed offset 42 within the 46-byte fixed part.
        fn_len_cd, extra_len_cd, comment_len_cd = struct.unpack('<HHH', cd_data[idx + 28:idx + 34])
        lho = struct.unpack('<I', cd_data[idx + 42:idx + 46])[0]
        name_cd = cd_data[idx + 46:idx + 46 + fn_len_cd]
        if lho == info.header_offset and name_cd == needle:
            cd_entry_pos = idx
            break
        search_from = idx + 4
    assert cd_entry_pos is not None, 'could not locate central directory entry for script.npk'
    cd_crc_offset = cd_entry_pos + 16  # crc32 field is at +16 within a central directory file header
    existing_cd_crc = struct.unpack('<I', cd_data[cd_crc_offset:cd_crc_offset + 4])[0]
    assert existing_cd_crc == crc, 'central directory CRC does not match local header CRC (unexpected zip layout)'
    print('central directory entry found at 0x%x' % cd_entry_pos)

    local_crc_offset = info.header_offset + 14  # crc32 field is at +14 within a local file header

    shutil.copyfile(SRC_OBB, OUT_OBB)
    with open(OUT_OBB, 'r+b') as f:
        f.seek(data_start)
        f.write(patched)
        f.seek(local_crc_offset)
        f.write(struct.pack('<I', new_crc))
        f.seek(cd_crc_offset)
        f.write(struct.pack('<I', new_crc))
    print('Wrote patched OBB to', OUT_OBB, '(data + both CRC32 fields updated)')

    # Verify via zipfile that the new obb still reads correctly AND matches
    # our patched bytes exactly (also implicitly validates zip integrity,
    # since ZipFile.read() checks entry CRC).
    z2 = zipfile.ZipFile(OUT_OBB)
    readback = z2.read(ENTRY_NAME)
    assert readback == patched, 'read-back content does not match what we wrote'
    print('SUCCESS: zipfile.read() on the patched OBB returns our patched bytes with a valid CRC32.')


if __name__ == '__main__':
    main()
