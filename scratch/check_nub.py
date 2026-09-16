import sys
sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\scratch')
from xref_lib import DATA, MD

# Disassemble 0x9900f0 - 0x990180
for insn in MD.disasm(DATA[0x9900f0:0x990180], 0x9900f0):
    print(f'{hex(insn.address)}: {insn.mnemonic} {insn.op_str}')
