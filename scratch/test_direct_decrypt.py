from Crypto.Cipher import Blowfish

key = bytes.fromhex('fa490e60')
data = bytes.fromhex('1fab6492e3a49d8f36fef23710c26e3719f4e3b99d31ff0f')

# pc_variant decrypt
c = Blowfish.new(key, Blowfish.MODE_ECB)
blocks = [data[i:i + 8] for i in range(0, len(data), 8)]
prev = b'\x00' * 8
out = b''
for blk in blocks:
    dec = c.decrypt(blk)
    plain = bytes(a ^ b for a, b in zip(dec, prev))
    out += plain
    prev = plain

print("Decrypted len:", len(out))
print("Decrypted hex:", out.hex())
print("Decrypted repr:", repr(out))
print("Wastage byte:", out[-1])
