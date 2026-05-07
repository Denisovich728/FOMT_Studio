import struct
with open('j:\\Repositorios\\fomt_studio\\Modded_FoMT.gba', 'rb') as f:
    rom = f.read()

off = 0x105EDC
for i in range(2):
    chunk = rom[off + i*32 : off + i*32 + 32]
    print(f"Map {i} Block at 0x{off + i*32:06X}:")
    for j in range(0, 32, 4):
        p = struct.unpack_from('<I', chunk, j)[0]
        print(f"  +0x{j:02X} : 0x{p:08X} (bytes: {chunk[j:j+4].hex()})")
