import struct
with open('j:\\Repositorios\\fomt_studio\\Modded_FoMT.gba', 'rb') as f:
    rom = f.read()

off = 0x0E5DB0
chunk = rom[off:off+32]
print(f"Map 0 Block at 0x{off:06X}:")
for i in range(0, 32, 4):
    p = struct.unpack_from('<I', chunk, i)[0]
    print(f"  +0x{i:02X} : 0x{p:08X} (bytes: {chunk[i:i+4].hex()})")
