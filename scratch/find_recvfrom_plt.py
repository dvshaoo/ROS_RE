import struct

p = r'c:\Users\Raysoo\Downloads\ROS_RE\03_lib\libclient_arm64.so'
data = open(p, 'rb').read()

DYNSYM_OFF = 0x2e4d8
DYNSYM_SIZE = 0xb4d68
DYNSTR_OFF = 0xe3240
DYNSTR_SIZE = 0x2288f3
SYM_ENTSIZE = 24
RELA_PLT_OFF = 0x781530
RELA_PLT_SIZE = 0x51780
RELA_ENTSIZE = 24  # Elf64_Rela: r_offset(8), r_info(8), r_addend(8)
PLT_OFF = 0x7d2cb0
PLT_SIZE = 0x36520

num_syms = DYNSYM_SIZE // SYM_ENTSIZE

target_name = b'recvfrom'
sym_idx = None
for i in range(num_syms):
    off = DYNSYM_OFF + i * SYM_ENTSIZE
    st_name = struct.unpack_from('<I', data, off)[0]
    end = data.find(b'\x00', DYNSTR_OFF + st_name)
    name = data[DYNSTR_OFF + st_name:end]
    if name == target_name:
        sym_idx = i
        print(f'Found symbol index {i} for {target_name}')
        break

if sym_idx is None:
    print('symbol not found')
else:
    # find rela.plt entry with r_info's symbol index == sym_idx
    # r_info = (sym_idx << 32) | type
    num_rela = RELA_PLT_SIZE // RELA_ENTSIZE
    for i in range(num_rela):
        off = RELA_PLT_OFF + i * RELA_ENTSIZE
        r_offset, r_info, r_addend = struct.unpack_from('<QQq', data, off)
        this_sym = r_info >> 32
        if this_sym == sym_idx:
            print(f'rela.plt entry {i}: r_offset={hex(r_offset)} (GOT slot), r_info={hex(r_info)}')
            # PLT stub address: typically PLT[0] is special (16 bytes), then PLT[n] for n-th rela entry at PLT_OFF + 16 + i*16 (aarch64 standard .plt stub is 16 bytes each after the header)
            plt_addr_guess = PLT_OFF + 16 + i * 16
            print(f'  guessed PLT stub address: {hex(plt_addr_guess)}')
            break
