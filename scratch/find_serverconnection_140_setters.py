"""
Wider, smarter re-check for the REAL success-path setter of
ServerConnection+0x140 (per the coordinator's E2E-032 follow-up request):
instead of filtering by a narrow address range (which may have missed
the real store if it lives outside 0x900000-0x970000), filter by OBJECT
SHAPE -- find every `str ..., [reg, #0x140]` anywhere in .text, then
check whether the SAME base register is ALSO used for a `+0x138` access
(load or store) within the same function (a generous +/-0x300 byte
window around the store), matching the already-established
"ServerConnection+0x138 == Nub*" shape confirmed in E2E-015/017/018 and
live-verified in E2E-031.
"""
import sys, struct
sys.path.insert(0, 'scratch')
from xref_lib import DATA, MD, TEXT_START, TEXT_END


def reg_of_base(op_str):
    """Extract the base register name from an operand string like
    'x8, [x19, #0x140]' -> 'x19'."""
    if '[' not in op_str:
        return None
    inside = op_str.split('[', 1)[1].split(']')[0]
    base = inside.split(',')[0].strip()
    return base


def main():
    # Step 1: find all str-to-+0x140 sites across the WHOLE .text section.
    candidates = []
    for pc in range(TEXT_START, TEXT_END, 4):
        word = DATA[pc:pc+4]
        for ins in MD.disasm(word, pc):
            if ins.mnemonic == 'str' and ins.op_str.endswith('#0x140]'):
                base = reg_of_base(ins.op_str)
                if base and not base.startswith('sp'):
                    candidates.append((pc, base, ins.op_str))

    print(f"Total non-sp str-to-+0x140 sites in whole .text: {len(candidates)}")

    # Step 2: for each candidate, scan a window around it for a
    # +0x138 access (ldr or str) using the SAME base register.
    matches = []
    WINDOW = 0x300
    for pc, base, opstr in candidates:
        found_138 = False
        lo = max(TEXT_START, pc - WINDOW)
        hi = min(TEXT_END, pc + WINDOW)
        for pc2 in range(lo, hi, 4):
            code2 = DATA[pc2:pc2+4]
            for ins2 in MD.disasm(code2, pc2):
                if ins2.mnemonic in ('ldr', 'str') and ins2.op_str.endswith('#0x138]'):
                    b2 = reg_of_base(ins2.op_str)
                    if b2 == base:
                        found_138 = True
                        break
            if found_138:
                break
        if found_138:
            matches.append((pc, base, opstr))

    print(f"Candidates ALSO touching +0x138 on the same base register within +/-{hex(WINDOW)}: {len(matches)}")
    for pc, base, opstr in matches:
        print(f"  {hex(pc)}  base={base}  {opstr}")


if __name__ == '__main__':
    main()
