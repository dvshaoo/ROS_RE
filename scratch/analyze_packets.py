import struct

buf1 = bytes.fromhex('08000c120014000f5468697320646f63756d656e742073')
print('=== BUF 1 (len=%d) ===' % len(buf1))
flags1 = struct.unpack('<H', buf1[0:2])[0]
print('flags: 0x%04x' % flags1)
print('FLAG_HAS_REQUESTS: %s' % bool(flags1 & 0x1))
print('FLAG_HAS_PINGS: %s' % bool(flags1 & 0x2))
print('FLAG_HAS_ACKS: %s' % bool(flags1 & 0x4))
print('FLAG_HAS_SEQUENCE_NUMBER: %s' % bool(flags1 & 0x8))
print('FLAG_HAS_PIGGYBACKS: %s' % bool(flags1 & 0x10))
print('FLAG_PACKET_RESENT: %s' % bool(flags1 & 0x20))
print('FLAG_IS_RELIABLE: %s' % bool(flags1 & 0x40))
print('FLAG_IS_FRAGMENT: %s' % bool(flags1 & 0x80))

buf2 = bytes.fromhex('58000861b2000061b200000c090014000654686973206400000000')
print('\n=== BUF 2 (len=%d) ===' % len(buf2))
flags2 = struct.unpack('<H', buf2[0:2])[0]
print('flags: 0x%04x' % flags2)
print('FLAG_HAS_REQUESTS: %s' % bool(flags2 & 0x1))
print('FLAG_HAS_PINGS: %s' % bool(flags2 & 0x2))
print('FLAG_HAS_ACKS: %s' % bool(flags2 & 0x4))
print('FLAG_HAS_SEQUENCE_NUMBER: %s' % bool(flags2 & 0x8))
print('FLAG_HAS_PIGGYBACKS: %s' % bool(flags2 & 0x10))
print('FLAG_PACKET_RESENT: %s' % bool(flags2 & 0x20))
print('FLAG_IS_RELIABLE: %s' % bool(flags2 & 0x40))
print('FLAG_IS_FRAGMENT: %s' % bool(flags2 & 0x80))
