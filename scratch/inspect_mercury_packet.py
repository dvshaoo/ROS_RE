import struct

buf1 = bytes.fromhex('08000c120014000f5468697320646f63756d656e742073')
print('=== BUF 1 (len=%d) ===' % len(buf1))
flags1 = struct.unpack('<H', buf1[0:2])[0]
print('flags: 0x%04x' % flags1)
# When FLAG_HAS_SEQUENCE_NUMBER is set, where is the sequence number?
# In Mercury, footers are at the END of the packet!
# Let's check the last 4 bytes:
seq1 = struct.unpack('<I', buf1[-4:])[0]
print('last 4 bytes as uint32: 0x%08x (%d)' % (seq1, seq1))
print('first 8 bytes:', buf1[:8].hex(), [b for b in buf1[:8]])
print('tail 8 bytes:', buf1[-8:].hex(), [b for b in buf1[-8:]])
print('full hex:', buf1.hex())
print('full ascii repr:', repr(buf1))

buf2 = bytes.fromhex('58000861b2000061b200000c090014000654686973206400000000')
print('\n=== BUF 2 (len=%d) ===' % len(buf2))
flags2 = struct.unpack('<H', buf2[0:2])[0]
print('flags: 0x%04x' % flags2)
print('last 4 bytes as uint32: 0x%08x (%d)' % (struct.unpack('<I', buf2[-4:])[0], struct.unpack('<I', buf2[-4:])[0]))
print('full hex:', buf2.hex())
print('full ascii repr:', repr(buf2))
