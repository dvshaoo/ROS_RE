# E2E-017 (2026-09-15): found the caller of `processFilteredPacket`
# (0x98fa30) -- and in the process, discovered a MAJOR alternate dispatch
# path that may fully explain the persistent BaseApp decrypt mystery.
#
# The caller is 0x98d38c (real prologue), args (this=Nub*, x1=some
# per-packet arg, x2=packet_obj). Its body:
#   1. Looks up the packet's SOURCE ADDRESS in a map at Nub+0x41f0 (via
#      0x9950d8, a find()-shaped call) against a map "end" sentinel at
#      Nub+0x41f8.
#   2. If FOUND (i.e. this source address has a REGISTERED/INDEXED
#      channel already) AND a flag byte at [channel_obj+0xf8] is set:
#      dispatches via a VIRTUAL CALL through the found channel object's
#      OWN vtable at +0x18 (`ldr x8,[x22]; ldr x8,[x8,#0x18]; blr x8`,
#      args this=channel_obj, Nub*, x2, packet_obj) -- see 0x98d4a0.
#   3. Only if NOT found (or the flag is clear) does it fall through to
#      the generic `processFilteredPacket` (0x98fa30) this project has
#      been analyzing since E2E-014/E2E-016.
#
# WHY THIS MATTERS: `BaseAppLoginRequest::initNetwork` (E2E-015) explicitly
# CONSTRUCTS a Channel object for the new BaseApp socket before the client
# even sends its first baseAppLogin packet. If that construction also
# REGISTERS the channel in this per-address map (not yet confirmed, but
# highly plausible given BigWorld's "indexed channel" terminology already
# seen in the vestigial-string set), then EVERY subsequent packet on the
# BaseApp channel -- including any reply this project sends -- would be
# dispatched via the CHANNEL-SPECIFIC virtual method at +0x18, NOT via
# the generic `processFilteredPacket`/`0x98924c` decrypt pair this
# project has been reverse-engineering. This would mean all of E2E-014
# through E2E-016's careful length/offset analysis, while correct for
# the GENERIC path, may simply not apply to the BaseApp channel at all
# once it becomes "indexed" -- a different code path with potentially
# different framing/length/decrypt semantics entirely.
#
# NOT YET FULLY TRACED (time budget): what class the Channel object at
# `Nub+0x41f0`'s map actually is, whether BaseAppLoginRequest::initNetwork
# really registers it there, and what the vtable+0x18 method
# (candidate address 0xd02fdc, unverified -- see below) actually does.
#
# See END_TO_END_TEST_LOG.md E2E-017 for the full writeup.
import sys
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\scratch')
from xref_lib import print_disasm

DISPATCHER_FUNC = 0x98d38c        # looks up indexed channel, branches to +0x18 or processFilteredPacket
INDEXED_CHANNEL_CALL_SITE = 0x98d4d4  # blr x8 -- the virtual dispatch, if channel found+flagged
GENERIC_FALLBACK_CALL = 0x98d49c  # b 0x98fa30 -- only reached if NOT an indexed channel
NUB_CHANNEL_MAP_OFFSET = 0x41f0   # Nub+0x41f0 : per-source-address channel map (find() via 0x9950d8)
NUB_CHANNEL_MAP_END_OFFSET = 0x41f8

if __name__ == '__main__':
    print('=== Dispatcher: indexed-channel lookup vs. generic processFilteredPacket fallback ===')
    print_disasm(DISPATCHER_FUNC, DISPATCHER_FUNC + 0x120)
