"""Read/write helpers for script.npk (NeoX-encrypted Python-2.7-shaped bytecode
container). Builds on the read-only ros_script_decrypt.py by adding the inverse
operations: rotor encrypt, reverse_string inverse, and raw member repackaging.

Deliberately does NOT re-marshal whole code objects (P's unmarshaller is lossy
for int64/long/float constants -- see CLAUDE.md Checkpoint 28). Patches are
applied as raw byte overwrites within the decrypted-but-still-marshalled
member blob, at a fixed offset/length, so nothing else in the module is ever
re-encoded.
"""
import sys, struct, zlib, os
sys.path.insert(0, r'c:\Users\Raysoo\Downloads\RulesOfSurvivalOld (2)\RulesOfSurvivalOld\tools\re')
import ros_script_decrypt as RS

NPK_PATH = r'C:\Users\Raysoo\Downloads\ROS_RE\04_obb\extracted\script.npk'


class RotorCodec(RS.Rotor):
    """Adds encrypt() as the true inverse of RS.Rotor.decrypt(), derived from
    the class's own _init()/e/d tables: decrypt applies, per byte, stages
    i=R-1..0 as tc = pos[i] ^ d[i][tc]; since d[i] = e[i]^-1 (established by
    _init()'s shuffle loop), the per-stage inverse is tc = e[i][tc ^ pos[i]],
    and inverting the whole chain requires running stages in the opposite
    order (i=0..R-1). Position advance (_adv1) is independent of tc and must
    still be stepped once per byte, identically to decrypt(). Round-trip
    self-tested against RS.Rotor.decrypt() on random data before first use."""
    def encrypt(self, data):
        self._init()
        out = bytearray(len(data))
        R = self.rotors
        e = self.e
        pos = self.pos
        for n, c in enumerate(data):
            tc = c
            for i in range(R):
                tc = e[i * 256 + ((tc ^ pos[i]) % 256)]
            out[n] = tc
            self._adv1()
        return bytes(out)


def unreverse_string(b):
    """Inverse of RS.reverse_string: that function XORs indices [0,128) then
    reverses the whole buffer. Reversing is an involution, and XOR-by-const
    is an involution, but they don't commute over a shifted window, so the
    true inverse is: reverse first, THEN xor the (now-relocated) prefix."""
    l = bytearray(b)
    l.reverse()
    for i in range(min(128, len(l))):
        l[i] ^= 154
    return bytes(l)


def member_pack(M):
    """Inverse of RS.member_marshal: M -> reverse_string^-1 -> zlib.compress
    -> rotor.encrypt -> raw on-disk member bytes."""
    pre_zlib = unreverse_string(M)
    compressed = zlib.compress(pre_zlib, 9)
    raw = RotorCodec(RS.KEY, 6).encrypt(compressed)
    return raw


def npk_read_table(data):
    cnt = struct.unpack_from('<I', data, 4)[0]
    io = struct.unpack_from('<I', data, 0x14)[0]
    rows = []
    for i in range(cnt):
        b = io + i * 28
        sig, off, ln, oln = struct.unpack_from('<IIII', data, b)
        rows.append((sig, off, ln, oln, b))
    return rows


def get_member_raw(data, sig):
    for s, off, ln, oln, tabpos in npk_read_table(data):
        if s == sig:
            return data[off:off + ln], off, ln, oln, tabpos
    return None


if __name__ == '__main__':
    # Self-test: pack(unpack(raw)) must decrypt back to the exact same M via
    # the normal read path (RS.member_marshal), proving the whole pipeline is
    # internally consistent -- independent of whether our zlib settings match
    # the original encoder byte-for-byte (they need not; only OUR round trip
    # needs to hold, since we're the ones who will encrypt what we then also
    # decrypt on every subsequent read, including inside the game itself).
    data = open(NPK_PATH, 'rb').read()
    # ui/UILogin.py's signature, found earlier via tools/script_index.py's
    # cache (scratch/script_module_sigs.json key "ui\\UILogin.py").
    import json
    sigs = json.load(open(r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\script_module_sigs.json'))
    sig_hex = sigs['ui\\uilogin.py']
    sig = int(sig_hex, 16)

    found = get_member_raw(data, sig)
    if not found:
        print('FAILED: signature not found in npk table')
        sys.exit(1)
    raw, off, ln, oln, tabpos = found
    print('found ui/UILogin.py member: off=0x%x ln=%d oln=%d' % (off, ln, oln))

    M = RS.member_marshal(raw)
    print('decrypted M length:', len(M))

    raw2 = member_pack(M)
    print('re-packed raw length:', len(raw2), ' (original ln=%d)' % ln)

    M2 = RS.member_marshal(raw2)
    print('round-trip M matches original M:', M2 == M)
