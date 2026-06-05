from unicorn import *
from unicorn.arm_const import *
import struct

def find_jt():
    with open(r'j:\scratch\Harvest Moon - Friends of Mineral Town.gba', 'rb') as f:
        rom = f.read()

    mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    
    # Map memory
    ROM_BASE = 0x08000000
    mu.mem_map(ROM_BASE, 0x1000000)
    mu.mem_write(ROM_BASE, rom)

    # Set up PC to execute exactly the literal load
    mu.reg_write(UC_ARM_REG_PC, 0x080D1D18 | 1)
    
    # We only want to execute one instruction: ldr r0, [pc, #0x17c]
    mu.emu_start(0x080D1D18 | 1, 0x080D1D1A | 1, count=1)
    
    r0 = mu.reg_read(UC_ARM_REG_R0)
    print(f"Jump Table Base loaded in r0: 0x{r0:08X}")

if __name__ == "__main__":
    find_jt()
