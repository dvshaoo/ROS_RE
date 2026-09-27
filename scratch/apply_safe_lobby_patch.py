"""SAFE replacement for apply_clean_lobby_patch.py's risky Athlete.enterHall patch.

Root cause of the 2026-09-27 SIGSEGV crash: apply_clean_lobby_patch.py injected a
brand-new JUMP_FORWARD instruction at a hand-computed offset (85..88) inside
entities/Athlete.py's enterHall(), overwriting what was actually a
LOAD_GLOBAL/LOAD_ATTR pair (Globals.enterSelectModeFinished) that a later
POP_JUMP_IF_TRUE instruction depends on. This desynced the bytecode stream and
corrupted the interpreter stack, causing a native SIGSEGV in NeoXMain during
client bootstrap (confirmed live: scratch/loop_debug/logcat.txt, "Fatal signal
11 (SIGSEGV) ... in tid 5608 (NeoXMain)").

SAFE approach instead: enterHall()'s own existing logic already has a built-in
skip path --

     85  LOAD_GLOBAL   Globals
     88  LOAD_ATTR     enterSelectModeFinished
     91  POP_JUMP_IF_TRUE   103      <- if already finished once, skip UI
     94  LOAD_GLOBAL   switches
     97  LOAD_ATTR     PCEnableMode
    100  POP_JUMP_IF_FALSE  113      <- if NOT PC-enable-mode, show UISelectMode
    103  LOAD_FAST     _realEnterHall
    106  CALL_FUNCTION 0
    109  POP_TOP
    110  JUMP_FORWARD  64                (skips to RETURN)
    113  ... (enter_ui('UISelectMode', callback=_realEnterHall) branch)

Both instructions at 91 and 100 are POP_JUMP_IF_* -- they ALWAYS pop their
tested value off the stack regardless of whether the branch is taken, so
retargeting *where* they jump to is perfectly stack-safe: 103 is already a
valid, reachable instruction boundary from the other branch's fall-through.

This patch changes ONLY the 2-byte jump-target argument of the instruction at
byte offset 100 (POP_JUMP_IF_FALSE) from 113 to 103 -- a single-byte value
change (low byte 113->103), same opcode, same instruction, same stack effect.
No new instructions are inserted, no other byte in the function is touched.
"""
import sys, os, struct, shutil

sys.path.insert(0, r'C:\Users\Raysoo\Downloads\RulesOfSurvivalOld (2)\RulesOfSurvivalOld\tools\re')
import ros_script_decrypt as RS
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\scratch')
from npk_patch_lib import NPK_PATH, get_member_raw, member_pack
from npk_find_func_offset import OffsetTracker

TARGET_NPK = r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\script_patched_safe.npk'
SOURCE_NPK = r'C:\Users\Raysoo\Downloads\ROS_RE\04_obb\extracted\script.npk'  # pristine, NOT the crashed one


def find_span(n, target_name):
    if isinstance(n, dict):
        if n.get('name') == target_name.encode('ascii') and 'code_span' in n:
            return n['code_span']
        for k, v in n.items():
            if k != 'code_span':
                res = find_span(v, target_name)
                if res:
                    return res
    elif isinstance(n, list):
        for it in n:
            res = find_span(it, target_name)
            if res:
                return res
    return None


def main():
    print('Rebuilding from PRISTINE source npk (not the crashed patched one):', SOURCE_NPK)
    shutil.copyfile(SOURCE_NPK, TARGET_NPK)
    data = bytearray(open(TARGET_NPK, 'rb').read())

    # --- 1. UISelectCharacter.on_enter -> RETURN_CONST 0 (safe, already-proven pattern) ---
    sig_sc = 0x32d7c278
    raw_sc, off_sc, ln_sc, oln_sc, _ = get_member_raw(bytes(data), sig_sc)
    print('1. UISelectCharacter: off=0x%x ln=%d' % (off_sc, ln_sc))
    M_sc = bytearray(RS.member_marshal(raw_sc))
    p_sc = OffsetTracker(bytes(M_sc))
    tree_sc, _, _ = p_sc.load()
    span_sc = find_span(tree_sc, 'on_enter')
    assert span_sc, 'on_enter not found in UISelectCharacter'
    s_sc, e_sc = span_sc
    print('   on_enter span: (%d, %d)' % (s_sc, e_sc))
    plain_sc = bytearray(RS.deob(bytes(M_sc[s_sc:e_sc])))
    before = list(plain_sc[0:3])
    plain_sc[0:3] = bytes([94, 0, 0])  # RETURN_CONST 0 (None)
    print('   bytes[0:3]: %r -> %r' % (before, list(plain_sc[0:3])))
    M_sc[s_sc:e_sc] = RS.deob(bytes(plain_sc))
    new_raw_sc = member_pack(bytes(M_sc))
    print('   packed size: %d / %d' % (len(new_raw_sc), ln_sc))
    assert len(new_raw_sc) <= ln_sc, 'UISelectCharacter repacked size exceeded!'
    padded_sc = new_raw_sc + b'\x00' * (ln_sc - len(new_raw_sc))
    data[off_sc:off_sc + ln_sc] = padded_sc

    # --- 2. Athlete.enterHall: retarget ONE existing jump, byte-for-byte minimal ---
    sig_ath = 0xc7ef2b17
    raw_ath, off_ath, ln_ath, oln_ath, _ = get_member_raw(bytes(data), sig_ath)
    print('2. Athlete: off=0x%x ln=%d' % (off_ath, ln_ath))
    M_ath = bytearray(RS.member_marshal(raw_ath))
    p_ath = OffsetTracker(bytes(M_ath))
    tree_ath, _, _ = p_ath.load()
    span_ath = find_span(tree_ath, 'enterHall')
    assert span_ath, 'enterHall not found in Athlete'
    s_ath, e_ath = span_ath
    print('   enterHall span: (%d, %d)' % (s_ath, e_ath))
    plain_ath = bytearray(RS.deob(bytes(M_ath[s_ath:e_ath])))

    # Sanity check: verify byte 100..102 really is POP_JUMP_IF_FALSE with arg=113
    # before touching anything (opcode byte + 2-byte LE arg, per the disassembler's
    # own instruction-offset==byte-offset layout confirmed for this function).
    opcode_byte = plain_ath[100]
    arg_lo = plain_ath[101]
    arg_hi = plain_ath[102]
    print('   byte[100:103] before = [0x%02x, %d, %d] (opcode, arg_lo, arg_hi)' % (
        opcode_byte, arg_lo, arg_hi))
    assert arg_lo == 113 and arg_hi == 0, (
        'Unexpected bytes at offset 100 -- refusing to patch blind. '
        'Got arg=%d, expected 113. Re-verify with dump_module_funcs.py first.' % (
            arg_lo + (arg_hi << 8)))

    plain_ath[101] = 103  # retarget jump: 113 -> 103 (both already-valid landing points)
    print('   byte[100:103] after  = [0x%02x, %d, %d]' % (
        plain_ath[100], plain_ath[101], plain_ath[102]))

    M_ath[s_ath:e_ath] = RS.deob(bytes(plain_ath))
    new_raw_ath = member_pack(bytes(M_ath))
    print('   packed size: %d / %d' % (len(new_raw_ath), ln_ath))
    assert len(new_raw_ath) <= ln_ath, 'Athlete repacked size exceeded!'
    padded_ath = new_raw_ath + b'\x00' * (ln_ath - len(new_raw_ath))
    data[off_ath:off_ath + ln_ath] = padded_ath

    with open(TARGET_NPK, 'wb') as f:
        f.write(data)
    print('SUCCESS: safe patches written to', TARGET_NPK)


if __name__ == '__main__':
    main()
