import os
import struct
import capstone

def disas_arm64(so_path, func_offset, size):
    print(f"\nDisassembling ARM64 {hex(func_offset)} (size {size}) in {os.path.basename(so_path)}")
    with open(so_path, 'rb') as f:
        f.seek(func_offset)
        code = f.read(size)
        
    md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
    md.detail = True
    
    for ins in md.disasm(code, func_offset):
        print(f"  {hex(ins.address)}: {ins.mnemonic} {ins.op_str}")

def disas_arm32(so_path, func_offset, size):
    print(f"\nDisassembling ARM32 {hex(func_offset)} (size {size}) in {os.path.basename(so_path)}")
    with open(so_path, 'rb') as f:
        # Check if thumb (lowest bit of symbol was 1)
        is_thumb = (func_offset % 2 != 0)
        offset = func_offset & ~1
        f.seek(offset)
        code = f.read(size)
        
    mode = capstone.CS_MODE_THUMB if is_thumb else capstone.CS_MODE_ARM
    md = capstone.Cs(capstone.CS_ARCH_ARM, mode)
    md.detail = True
    
    for ins in md.disasm(code, offset):
        print(f"  {hex(ins.address)}: {ins.mnemonic} {ins.op_str}")

if __name__ == '__main__':
    arm64_so = r'c:\Users\Raysoo\Downloads\ROS_RE\03_lib\libclient_arm64.so'
    arm32_so = r'c:\Users\Raysoo\Downloads\ROS_RE\01_apk\base_decompiled\lib\armeabi-v7a\libclient.so'
    
    # ARM64: 0x1bfe890 (size 348)
    disas_arm64(arm64_so, 0x1bfe890, 348)
    
    # ARM32: 0x13777e9 (Thumb, size 204)
    disas_arm32(arm32_so, 0x13777e9, 204)
