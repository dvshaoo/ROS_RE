"""
Scan the ~170 "ClientMessageHandler::handleMessage...did not consume all
data" per-entity-method dispatch stub functions (E2E-025/E2E-026 lead) and
extract each one's argument-read signature: the sequence of `mov w1, #N`
immediates that precede each `blr` call reading N raw bytes from the
incoming arg stream, in order. A method like Account.onChannelLogin
(UINT8 status, PYTHON accountData) should show a DISTINCTIVE signature:
one 1-byte fixed read, followed by a variable/blob-shaped read (a
different call target than the generic fixed-size stream reader), rather
than a second fixed 'mov w1,#N' read.

This does NOT require script.npk or the entity-defs binary -- it only
needs the already-known error-string xref addresses (pure static
disassembly of libclient_arm64.so).
"""
import sys, struct
sys.path.insert(0, 'scratch')
from xref_lib import DATA, MD, find_prologue_before, find_str

STRING_ADDR = 0x2a4b1f3  # "ClientMessageHandler::handleMessage..."

def xrefs_wide(target_addr, max_off=80):
    from xref_lib import decode_adrp
    target_page = target_addr & ~0xfff
    target_off = target_addr & 0xfff
    hits = []
    for pc in range(0x809200, 0x2a38664, 4):
        word = struct.unpack('<I', DATA[pc:pc+4])[0]
        rd, page = decode_adrp(word, pc)
        if page != target_page:
            continue
        for off in range(4, max_off, 4):
            w2 = struct.unpack('<I', DATA[pc+off:pc+off+4])[0]
            if (w2 & 0xffc00000) == 0x91000000:
                rn2 = (w2 >> 5) & 0x1f
                imm12 = (w2 >> 10) & 0xfff
                if rn2 == rd and imm12 == target_off:
                    hits.append(pc)
                    break
    return hits


def disasm_window(start, end):
    return list(MD.disasm(DATA[start:end], start))


def analyze_stub(err_call_addr):
    # Function entry is a `sub sp, sp, #0x80` a bounded distance before the
    # error-string call site. Search backward up to 0x200 bytes.
    entry = None
    for back in range(4, 0x200, 4):
        pc = err_call_addr - back
        code = DATA[pc:pc+4]
        ins = list(MD.disasm(code, pc))
        if ins and ins[0].mnemonic == 'sub' and ins[0].op_str.startswith('sp, sp, #0x'):
            entry = pc
            # keep scanning further back in case of an even earlier one;
            # but stubs are short, so the FIRST one found scanning backward
            # from the error site should be correct -- stop here.
            break
    if entry is None:
        return None
    ins_list = disasm_window(entry, err_call_addr + 0x10)
    reads = []  # list of ('fixed', N) or ('call', target_addr) for each blr
    pending_w1 = None
    for ins in ins_list:
        if ins.mnemonic == 'mov' and ins.op_str.startswith('w1, #'):
            try:
                pending_w1 = int(ins.op_str.split('#')[1], 0)
            except ValueError:
                pending_w1 = None
        elif ins.mnemonic == 'bl':
            # a direct call -- could be a PYTHON/pickle-unpack helper etc.
            try:
                target = int(ins.op_str.lstrip('#'), 16)
            except ValueError:
                target = None
            if target is not None and target not in (0x1cad7ac, 0x7e1c90, 0x97bfa8, 0x97c0d8):
                reads.append(('bl', hex(target)))
        elif ins.mnemonic == 'blr':
            if pending_w1 is not None:
                reads.append(('fixed', pending_w1))
                pending_w1 = None
            else:
                reads.append(('blr', None))
    return entry, reads


def main():
    hits = xrefs_wide(STRING_ADDR, max_off=80)
    print(f"Found {len(hits)} error-string xref sites")
    results = []
    for h in hits:
        r = analyze_stub(h)
        if r is None:
            print(hex(h), 'ENTRY NOT FOUND')
            continue
        entry, reads = r
        results.append((entry, h, reads))

    print()
    for entry, h, reads in results:
        print(f"{hex(entry)} (err@{hex(h)}): {reads}")

    # Flag candidates matching a UINT8-then-something-else shape:
    # exactly 2 reads, first is ('fixed', 1), second is NOT another simple
    # small fixed read (i.e. anything except ('fixed', 1/2/4/8)) --
    # consistent with (UINT8, PYTHON) or similar (u8, variable-blob) shape.
    print()
    print("=== Candidates matching (fixed 1-byte, then non-trivial-fixed) ===")
    for entry, h, reads in results:
        if len(reads) >= 2 and reads[0] == ('fixed', 1):
            second = reads[1]
            if not (second[0] == 'fixed' and second[1] in (1, 2, 4, 8)):
                print(f"{hex(entry)}: {reads}")


if __name__ == '__main__':
    main()
