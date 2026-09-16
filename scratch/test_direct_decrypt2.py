from Crypto.Cipher import Blowfish

key = bytes.fromhex('fa490e60')
data2 = bytes.fromhex('9f4d43af58719b1c67fe0d5efe43c0dfe07fdc2f4965f2553cbead4ab2c9672b')

c = Blowfish.new(key, Blowfish.MODE_ECB)
blocks = [data2[i:i + 8] for i in range(0, len(data2), 8)]
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
print("Without wastage:", repr(out[:-out[-1]]))
