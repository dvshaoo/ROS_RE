"""
Walk the interface-method registration block sequentially, symbolically
tracking every X-register's "known string pointer" value (via ADRP+ADD
patterns and simple MOV-copy propagation, invalidating on any other write),
and record the resolved string name for EVERY `bl 0x98b30c` call site in
strict program order (looking at whatever register holds the call's x1 arg
value at that point).

This recovers the exact 0-indexed registration order (== numeric Mercury
msgID, since 0x98b30c is confirmed to be a std::vector<MethodDescription>
push_back that assigns each entry's ID as the vector's size at push time)
for BOTH LoginInterface/BaseAppExtInterface and ClientInterface, without
hand-counting any strings, and resolves the createBasePlayer-msgID-5
"off-by-one" question as a side effect.

v2: the naive "track x1 only" version produced duplicate/stale entries
(e.g. "baseAppLogin" appearing twice) because the compiler interleaves
loop iterations -- some calls' x1 value is pre-computed several
instructions ahead into a DIFFERENT register (x19/x20/x21...) and only
MOV'd into x1 right before the call. This version tracks all registers
and invalidates on any write it doesn't explicitly understand, so stale
values can't leak through a register the compiler actually reused for
something else in between.
"""
import sys, struct, re
sys.path.insert(0, 'scratch')
from xref_lib import DATA, MD, decode_adrp, TEXT_START, TEXT_END

BLOCK_START = 0x80c600
BLOCK_END = 0x80e800

XREG = re.compile(r'^[xw](\d+)$')


def reg_num(tok):
    tok = tok.strip().rstrip(',')
    m = XREG.match(tok)
    if m:
        n = int(m.group(1))
        if 0 <= n <= 30:
            return n
    return None


def cstr(addr):
    if addr is None:
        return None
    end = DATA.find(b'\x00', addr)
    if end < 0 or end - addr > 200:
        return None
    try:
        return DATA[addr:end].decode('ascii')
    except UnicodeDecodeError:
        return None


def main():
    reg_val = {}       # reg_num -> resolved absolute address (string ptr)
    pending_adrp = {}   # reg_num -> page (waiting for matching ADD)

    results = []

    pc = BLOCK_START
    while pc < BLOCK_END:
        code = DATA[pc:pc + 4]
        word = struct.unpack('<I', code)[0]
        decoded = list(MD.disasm(code, pc))
        if not decoded:
            pc += 4
            continue
        ins = decoded[0]
        mnem = ins.mnemonic
        ops = [o.strip() for o in ins.op_str.split(',')] if ins.op_str else []

        rd, page = decode_adrp(word, pc)
        handled = False
        if page is not None:
            pending_adrp[rd] = page
            reg_val.pop(rd, None)
            handled = True
        elif mnem == 'add' and len(ops) == 3 and ops[1] == ops[0]:
            d = reg_num(ops[0])
            imm_tok = ops[2]
            if d is not None and imm_tok.startswith('#'):
                try:
                    imm = int(imm_tok[1:], 0)
                except ValueError:
                    imm = None
                if imm is not None and d in pending_adrp:
                    reg_val[d] = pending_adrp[d] + imm
                    handled = True
        elif mnem == 'mov' and len(ops) == 2:
            d = reg_num(ops[0])
            s = reg_num(ops[1])
            if d is not None and s is not None:
                if s in reg_val:
                    reg_val[d] = reg_val[s]
                else:
                    reg_val.pop(d, None)
                handled = True
        elif mnem == 'bl' and ins.op_str == '#0x98b30c':
            x1 = reg_val.get(1)
            name = cstr(x1)
            results.append(('method', pc, x1, name))
            handled = True
        elif mnem == 'bl' and ins.op_str == '#0x98b294':
            # Interface object placement-constructor: x1 = interface name.
            # Marks an epoch boundary -- 0x98b30c's push_back index resets
            # per-interface (each interface object has its OWN vector).
            x1 = reg_val.get(1)
            name = cstr(x1)
            results.append(('interface', pc, x1, name))
            handled = True

        if not handled:
            # Invalidate any destination register this instruction writes,
            # to prevent stale values leaking through reused registers.
            if ops:
                d = reg_num(ops[0])
                if d is not None and mnem not in ('cmp', 'cmn', 'tst', 'b', 'bl', 'ret',
                                                    'str', 'strb', 'strh', 'stur', 'sturb',
                                                    'stp', 'sturh', 'cbz', 'cbnz', 'tbz', 'tbnz'):
                    reg_val.pop(d, None)
                    pending_adrp.pop(d, None)

        pc += 4

    n_methods = sum(1 for r in results if r[0] == 'method')
    n_ifaces = sum(1 for r in results if r[0] == 'interface')
    print(f"Total bl 0x98b30c (method) call sites: {n_methods}")
    print(f"Total bl 0x98b294 (interface ctor) call sites: {n_ifaces}")
    print()

    current_iface = None
    per_iface_idx = 0
    for kind, call_addr, str_addr, name in results:
        s = name if name is not None else '<UNRESOLVED>'
        if kind == 'interface':
            current_iface = s
            per_iface_idx = 0
            print(f"\n=== INTERFACE: \"{s}\" (constructed at {hex(call_addr)}) ===")
        else:
            print(f"  msgID {per_iface_idx:3d}  {hex(call_addr)}  x1={hex(str_addr) if str_addr else None}  \"{s}\"  [interface={current_iface}]")
            per_iface_idx += 1


if __name__ == '__main__':
    main()
