import struct

def dump_food():
    rom_path = 'j:/Repositorios/fomt_studio/Modded_FoMT3.gba'
    with open(rom_path, 'rb') as f:
        rom = f.read()
    
    start = 0xedcd8
    end = 0xee787
    
    print(f"Dumping from {hex(start)} to {hex(end)} (Step 16)")
    for i in range((end - start + 1) // 16):
        base = start + (i * 16)
        ptr = struct.unpack('<I', rom[base:base+4])[0]
        if ptr < 0x08000000 or ptr >= 0x09000000:
            print(f"{i}: Invalid Ptr {hex(ptr)} at {hex(base)}")
            continue
        off = ptr & 0x1ffffff
        name = rom[off:off+30].split(b'\0')[0].decode('windows-1252', errors='ignore')
        print(f"{i}: {name} ({hex(ptr)}) at {hex(base)}")

dump_food()
