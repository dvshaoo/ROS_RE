# E2E-015 (2026-09-15): CONFIRMS BY DISASSEMBLY (not just live memory-scan
# coincidence, per E2E-012) that the BaseApp Channel object is constructed
# with the LITERAL SAME EncryptionFilter pointer as LoginApp's
# ServerConnection+0x148 slot -- not a copy, not a coincidentally-equal key.
#
# Trace: BaseAppLoginRequest::initNetwork (0x9389dc, per
# 06_trace/BASEAPP_LOGIN_SERIALIZATION.md's own prologue address) reads
# ServerConnection+0x148 (line ~0x938b0c: `ldr x23, [x20, #0x148]` where
# x20=ServerConnection*) -- the EXACT SAME offset documented in
# 06_notes/FIRST_LOGINREPLY_BLOWFISH_KEY_TRACE.md as the LoginApp
# EncryptionFilter cache slot -- bumps its refcount twice (intrusive-ptr
# convention), then calls the Channel constructor at 0x984a54 with
# x4=&filter_ptr. Inside that constructor:
#   0x984aa0: ldr x8, [x4]          ; x8 = the SAME filter pointer
#   0x984aa8: str x8, [x19, #0x40]  ; new Channel object's +0x40 = filter ptr (STORED DIRECTLY)
#   0x984aac: cbz x8, #0x984ac4
#   0x984ab0-0x984ac0: refcount++ on that SAME object (no copy, no new key material)
#
# This means decrypt() for BOTH the LoginApp reply AND any BaseApp channel
# message dispatches through the IDENTICAL object's IDENTICAL vtable slot
# -- i.e. there is NO separate/distinct decrypt code path or chaining mode
# to find for BaseApp specifically; it is provably the same code by
# construction, not by coincidence. See END_TO_END_TEST_LOG.md E2E-015 for
# the full writeup and what remains unexplained despite this.
import sys
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\scratch')
from xref_lib import print_disasm

INITNETWORK_FILTER_READ = 0x938b0c   # ldr x23, [x20, #0x148]
CHANNEL_CTOR = 0x984a54              # constructs the new BaseApp Channel object
CHANNEL_CTOR_FILTER_STORE = 0x984aa8  # str x8, [x19, #0x40] -- stores the SAME pointer

if __name__ == '__main__':
    print('=== ServerConnection+0x148 filter read, inside BaseAppLoginRequest::initNetwork ===')
    print_disasm(INITNETWORK_FILTER_READ - 8, INITNETWORK_FILTER_READ + 0x50)
    print()
    print('=== Channel constructor storing the SAME filter pointer at +0x40 ===')
    print_disasm(CHANNEL_CTOR_FILTER_STORE - 0x10, CHANNEL_CTOR_FILTER_STORE + 0x20)
