# E2E-016 (2026-09-15): locates the REAL generic EncryptionFilter decrypt
# function (0x98924c), distinct from the onLoginReply-specific helper
# (0x989600) this project had been treating as authoritative for BaseApp
# testing too. Found by first recovering EncryptionFilter's TRUE vtable
# contents via .rela.dyn (the raw file bytes at the vtable address are
# R_AARCH64_RELATIVE relocation targets, NOT literal function pointers --
# a bug in an earlier naive read this same pass), then disassembling the
# neighboring already-known addresses (0x98924c, 0x989600, 0x98938c) that
# 06_notes/FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md had listed together as
# "the three known encrypt/decrypt call targets" without fully
# characterizing which was which.
#
# KEY FINDING: 0x98924c is the generic recv-path decrypt function (checks
# the +0x2c "enabled" bool, computes length from packet_obj+0x1a plus
# packet_obj+0x1c, then runs the same pc_variant IV=0 XOR-chain loop
# starting at packet_obj+0x60 -- CONFIRMED as wire offset 0, the flags
# field, per 06_trace/MERCURY_REPLY_DISPATCH_TRACE.md's own "bad flags"
# trace). This means: (a) decrypt always starts at the true beginning of
# the wire packet (consistent with this project's working assumption),
# but (b) the LENGTH is not simply "however many bytes we sent" -- it is
# read back out of two 16-bit fields the receive path itself populates
# BEFORE calling decrypt, and reclassified (moved between the two fields,
# sum unchanged) when certain Mercury footer flags (sequence number, etc.)
# are set. The "base case" population of these two fields was not fully
# traced to its origin this pass (time budget) -- also found, as an
# unplanned side discovery, what appears to be an INLINE SIMD (NEON)
# checksum/hash computation directly inside `processFilteredPacket`
# itself (around 0x98fce0-0x98fd10) -- likely the true implementation
# behind the "failed checksum" error this project searched for via
# function-call methods and could not find, because it isn't a separate
# callable function at all. NOT further characterized this pass.
#
# See END_TO_END_TEST_LOG.md E2E-016 and
# 06_notes/BASEAPP_CRYPTO_BLOCKER_SUMMARY.md for the full writeup.
import sys
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\scratch')
from xref_lib import print_disasm

GENERIC_DECRYPT_FUNC = 0x98924c   # the real recv-path decrypt (NOT 0x989600)
LOGINREPLY_ONLY_DECRYPT_FUNC = 0x989600  # onLoginReply's own hardcoded-length helper
FLAGS_FIELD_LENGTH_A = 0x1a       # packet_obj+0x1a -- summed with...
FLAGS_FIELD_LENGTH_B = 0x1c       # ...packet_obj+0x1c to get total decrypt length
WIRE_DATA_START = 0x60            # packet_obj+0x60 == wire byte 0 (the flags field)
INLINE_CHECKSUM_REGION = 0x98fce0  # unplanned discovery: SIMD checksum/hash, not yet characterized

if __name__ == '__main__':
    print('=== Generic decrypt (0x98924c) -- length computation + decrypt loop start ===')
    print_disasm(GENERIC_DECRYPT_FUNC, GENERIC_DECRYPT_FUNC + 0x100)
