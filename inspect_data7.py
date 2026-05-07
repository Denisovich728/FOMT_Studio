import struct

def dump_function():
    with open('j:\\Repositorios\\fomt_studio\\Modded_FoMT.gba', 'rb') as f:
        rom_data = f.read()
    
    off = 0xDBE10
    chunk = rom_data[off:off+128]
    
    print("Code/Pools at 0xDBE10:")
    for i in range(0, len(chunk), 4):
        val = struct.unpack_from('<I', chunk, i)[0]
        hex_str = ' '.join(f"{b:02X}" for b in chunk[i:i+4])
        print(f"+0x{i:02X}: {hex_str}  (0x{val:08X})")

if __name__ == '__main__':
    dump_function()
