import struct

payload = bytes.fromhex('0861b2000061b200000c0900140006546869732064')
print("Payload len:", len(payload))
print("Payload hex:", payload.hex())

# In Mercury bundles:
# Is it message-based?
# Let's inspect Nub::processPacket or Bundle unpacking in libclient.so
