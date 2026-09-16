import sys
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\scratch')
from xref_lib import DATA, MD

# Disassemble in_place_decrypt (0x98924c - 0x989350)
for insn in MD.disasm(DATA[0x98924c:0x989350], 0x98924c):
    print(f'{hex(insn.address)}: {insn.mnemonic} {insn.op_str}')
