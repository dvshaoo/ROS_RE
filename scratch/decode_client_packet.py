import struct

# Decrypted packet from client:
# 5800 0861b200 0061b200 000c0900140006546869732064 00000000
raw = bytes.fromhex('58000861b2000061b200000c090014000654686973206400000000')
print('Total len:', len(raw))
flags = struct.unpack('<H', raw[0:2])[0]
print(f'Flags: {hex(flags)}')
# bit 3: FLAG_HAS_SEQUENCE_NUMBER (0x08)
# bit 4: FLAG_IS_RELIABLE (0x10)
# bit 6: FLAG_INDEXED_CHANNEL (0x40) or FLAG_HAS_ACKS?
# In ARM64:
# tbz w9, #2 -> bit 2 = 0x04 (FLAG_HAS_ACKS)
# tbz w8, #6 -> bit 6 = 0x40 (FLAG_INDEXED_CHANNEL)
# tbnz w8, #4 -> bit 4 = 0x10 (FLAG_IS_RELIABLE)
# tbz w8, #3 -> bit 3 = 0x08 (FLAG_HAS_SEQUENCE_NUMBER)
print('FLAG_HAS_ACKS (bit 2):', bool(flags & 4))
print('FLAG_HAS_SEQUENCE_NUMBER (bit 3):', bool(flags & 8))
print('FLAG_IS_RELIABLE (bit 4):', bool(flags & 0x10))
print('FLAG_INDEXED_CHANNEL (bit 6):', bool(flags & 0x40))

# Tail 4 bytes: sequence number
seq = struct.unpack('<I', raw[-4:])[0]
print('Sequence number (tail 4 bytes):', seq)

# If bit 6 is set (FLAG_INDEXED_CHANNEL):
# The 4 bytes preceding the sequence number are channelID!
channel_id = struct.unpack('<I', raw[-8:-4])[0]
print('Channel ID (or footer):', hex(channel_id), raw[-8:-4])

# Middle is bundle
bundle = raw[2:-8] if (flags & 0x40) else raw[2:-4]
print('Bundle bytes:', bundle.hex(), bundle)
