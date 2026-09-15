# E2E-011 (2026-09-15): decodes the full BaseAppExtInterface + ClientInterface
# method registration table by finding every BL caller of the shared
# registrar function 0x98b30c and resolving each call site's own x1 (name
# string pointer), w2 (lengthStyle), w3 (lengthParam) arguments from the
# register-writes strictly between it and the PREVIOUS registrar call (not a
# fixed-size lookback window, which produced stale-value artifacts on an
# earlier attempt this pass -- e.g. misattributing "disconnectClient" twice).
# This is how createBasePlayer's exact wire framing (VARIABLE_LENGTH_MESSAGE,
# u16 length prefix) and its message-ID-by-registration-order (index 4 within
# ClientInterface: bandwidthNotification=0, updateFrequencyNotification=1,
# setGameTime=2, resetEntities=3, createBasePlayer=4) were established this
# pass. See END_TO_END_TEST_LOG.md E2E-011 for the full writeup.
import sys, struct
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\scratch')
from xref_lib import DATA, TEXT_START, TEXT_END, decode_adrp


def find_bl_callers(target):
    hits = []
    for pc in range(TEXT_START, TEXT_END, 4):
        word = struct.unpack('<I', DATA[pc:pc + 4])[0]
        if (word & 0xfc000000) == 0x94000000:
            imm26 = word & 0x3ffffff
            if imm26 & (1 << 25):
                imm26 -= (1 << 26)
            target_addr = pc + (imm26 << 2)
            if target_addr == target:
                hits.append(pc)
    return hits


def get_string_at(addr, n=35):
    return DATA[addr:addr + n].split(b'\x00')[0]


def resolve(bl_pc, prev_bl_pc):
    adrp_page = {}
    val = {}
    w2 = None
    w3 = None
    start = prev_bl_pc + 4 if prev_bl_pc else bl_pc - 200
    for pc in range(start, bl_pc, 4):
        word = struct.unpack('<I', DATA[pc:pc + 4])[0]
        rd, page = decode_adrp(word, pc)
        if page is not None:
            adrp_page[rd] = page
            continue
        if (word & 0xffc00000) == 0x91000000:  # ADD (imm), 64-bit
            rd2 = word & 0x1f
            rn2 = (word >> 5) & 0x1f
            imm12 = (word >> 10) & 0xfff
            if rn2 in adrp_page:
                val[rd2] = adrp_page[rn2] + imm12
        if (word & 0x7f800000) == 0x52800000:  # MOVZ wN, #imm
            rd2 = word & 0x1f
            imm16 = (word >> 5) & 0xffff
            if rd2 == 2:
                w2 = imm16
            elif rd2 == 3:
                w3 = imm16
        if word == 0x2a1f03e2:  # mov w2, wzr
            w2 = 0
        if word == 0x2a1f03e3:  # mov w3, wzr
            w3 = 0
    return val.get(1), w2, w3


if __name__ == '__main__':
    calls = find_bl_callers(0x98b30c)
    prev = None
    for i, pc in enumerate(calls):
        x1, w2, w3 = resolve(pc, prev)
        s = get_string_at(x1) if x1 else b'???'
        print(i, hex(pc), s, "lenStyle=", w2, "lenParam=", w3)
        prev = pc
