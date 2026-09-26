"""Patches ui/UILogin.py's showGuestAccountRemind to an immediate `return
None` (bytes [94,0,0], the NeoX-fused RETURN_CONST opcode + const-index-0,
which is already None in this function's own consts table -- verified by
inspection, no new const needed). Neutralizes the "Link Account" nag panel
at its one and only call site (Checkpoint 27/28) without touching anything
else in the module: everything after byte 3 of the original 259-byte
function body is left completely untouched (dead code, never reached once
the function returns on its first instruction).

Writes to a NEW file (scratch/script_patched.npk) -- never overwrites the
extracted reference copy or any on-device file directly. Verifies the patch
by fully round-tripping it back through the normal read path and asserting
the disassembly is now exactly the 3-byte return.
"""
import sys, json, shutil

sys.path.insert(0, r'C:\Users\Raysoo\Downloads\RulesOfSurvivalOld (2)\RulesOfSurvivalOld\tools\re')
import ros_script_decrypt as RS
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\scratch')
from npk_patch_lib import NPK_PATH, get_member_raw, member_pack
from npk_find_func_offset import find_function_code_span

OUT_PATH = r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\script_patched.npk'
PATCH = bytes([94, 0, 0])  # RETURN_CONST 0  (consts[0] == None, verified)


def main():
    sigs = json.load(open(r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\script_module_sigs.json'))
    sig = int(sigs['ui\\uilogin.py'], 16)

    data = bytearray(open(NPK_PATH, 'rb').read())
    raw, off, ln, oln, tabpos = get_member_raw(bytes(data), sig)
    print('member: off=0x%x ln=%d oln=%d' % (off, ln, oln))

    M = bytearray(RS.member_marshal(raw))
    s, e = find_function_code_span(bytes(M), 'showGuestAccountRemind')
    print('showGuestAccountRemind code span in M: (%d, %d) len=%d' % (s, e, e - s))

    raw_span = bytes(M[s:e])
    plain = bytearray(RS.deob(raw_span))
    print('before patch, first 6 bytes (plaintext):', plain[:6].hex())
    print('before patch, last 3 bytes (plaintext):', plain[-3:].hex())
    assert plain[-3:] == PATCH, 'sanity check failed: function does not already end in RETURN_CONST 0 as expected'

    plain[0:3] = PATCH
    new_raw_span = RS.deob(bytes(plain))  # deob is its own inverse (XOR), same call re-obfuscates
    M[s:e] = new_raw_span

    # Verify the M-level patch alone (before repacking) reads back correctly.
    check_raw = bytes(M[s:e])
    check_plain = RS.deob(check_raw)
    assert check_plain[:3] == PATCH, 'patch did not stick at the M level'
    print('M-level patch verified OK.')

    # Repack this one member and pad/verify it fits in the original slot.
    new_member_raw = member_pack(bytes(M))
    print('new packed member length:', len(new_member_raw), ' original ln:', ln)
    if len(new_member_raw) > ln:
        raise SystemExit('FATAL: patched member is LARGER than the original slot (%d > %d) -- '
                          'container restructuring would be needed, not implemented.' % (len(new_member_raw), ln))
    padded = new_member_raw + b'\x00' * (ln - len(new_member_raw))
    assert len(padded) == ln

    # Full round-trip verification through the NORMAL read path, using the
    # padded bytes exactly as they'll sit in the file (zlib.decompress must
    # tolerate the trailing zero padding -- confirmed by this assertion).
    M_check = RS.member_marshal(padded)
    assert bytes(M_check) == bytes(M), 'full round-trip through padded raw bytes does not match patched M!'
    print('Full round-trip through padded on-disk bytes verified OK.')

    # Write the patched npk as a NEW file: copy original, then overwrite only
    # this one member's byte range in place (same offset, same length -- no
    # table/header changes needed at all).
    shutil.copyfile(NPK_PATH, OUT_PATH)
    with open(OUT_PATH, 'r+b') as f:
        f.seek(off)
        f.write(padded)
    print('Wrote patched npk to', OUT_PATH)

    # Final end-to-end sanity check: re-open the OUTPUT file fresh, locate
    # the same member by signature, decrypt, and confirm the function now
    # disassembles as our 3-byte patch (using the project's own disas tool
    # for an independent verification path).
    out_data = open(OUT_PATH, 'rb').read()
    out_raw, out_off, out_ln, out_oln, _ = get_member_raw(out_data, sig)
    assert out_off == off and out_ln == ln, 'member table entry should be unchanged'
    out_M = RS.member_marshal(out_raw)
    out_s, out_e = find_function_code_span(out_M, 'showGuestAccountRemind')
    out_plain = RS.deob(out_M[out_s:out_e])
    print('FINAL VERIFY: patched function first 3 bytes =', out_plain[:3].hex(),
          '(expect 5e0000)')
    assert out_plain[:3] == PATCH
    print('SUCCESS: patched npk is internally consistent and verified.')


if __name__ == '__main__':
    main()
