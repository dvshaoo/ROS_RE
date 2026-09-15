# E2E-014 (2026-09-15): confirms libclient_arm64.so embeds a standard,
# zlib-compatible CRC-32 (IEEE 802.3, reflected, polynomial 0xEDB88320)
# 256-entry lookup table at rodata 0x2be798c, and locates its update
# function (0x98fa30-region cluster, leaf function at 0x1cc3988) and its
# 4 known callers (0x1248fac, 0x127d950, 0x12a0270, 0x12a0524), all of
# which use the standard init=0xFFFFFFFF / finalize=~crc convention
# (byte-for-byte equivalent to Python's zlib.crc32()/binascii.crc32()).
#
# NOT CONFIRMED to be the Mercury packet checksum referenced by
# `Nub::processFilteredPacket(...): Packet (flags %hx, size %d) failed
# checksum (wanted %08x, got %08x)` -- the 4 known callers are all in a
# distant address range (~0x12xxxxx) consistent with an unrelated
# subsystem (most plausibly resource/asset-name hashing, a common CRC32
# use in game engines), not the Nub/Channel packet-validation cluster
# (~0x98fxxx-0x99xxxx). The checksum error string itself was NOT located
# via any of 5 independent static methods tried this pass (see
# END_TO_END_TEST_LOG.md E2E-014 for the full list) -- kept here as a
# concrete, reusable candidate algorithm for whoever continues this
# thread, not as a proven answer.
import struct

DATA = open(r'C:\Users\Raysoo\Downloads\ROS_RE\03_lib\libclient_arm64.so', 'rb').read()

CRC_TABLE_ADDR = 0x2be798c
CRC_UPDATE_FUNC = 0x1cc3988
KNOWN_CALLERS = [0x1248fac, 0x127d950, 0x12a0270, 0x12a0524]


def make_ieee_crc32_table():
    table = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (0xEDB88320 ^ (c >> 1)) if (c & 1) else (c >> 1)
        table.append(c)
    return table


if __name__ == '__main__':
    table_bytes = DATA[CRC_TABLE_ADDR:CRC_TABLE_ADDR + 1024]
    values = struct.unpack('<256I', table_bytes)
    std = make_ieee_crc32_table()
    match = sum(1 for a, b in zip(values, std) if a == b)
    print('CRC-32 table match: %d/256 entries' % match)
    print('Update function:', hex(CRC_UPDATE_FUNC))
    print('Known callers:', [hex(c) for c in KNOWN_CALLERS])
