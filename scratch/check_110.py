import sys
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\scratch')
from xref_lib import DATA, MD

# Disassemble 0x92a58c - 0x92a650
for insn in MD.disasm(DATA[0x92a58c:0x92a650], 0x92a58c):
    print(f'{hex(insn.address)}: {insn.mnemonic} {insn.op_str}')
