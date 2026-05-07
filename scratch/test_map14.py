import struct
with open('j:\\Repositorios\\fomt_studio\\Modded_FoMT.gba', 'rb') as f:
    rom = f.read()

off = 0x0E5DB0
for i in range(5):
    chunk = rom[off + i*32 : off + i*32 + 32]
    p0 = struct.unpack_from('<I', chunk, 0)[0]
    p4 = struct.unpack_from('<I', chunk, 4)[0]
    p8 = struct.unpack_from('<I', chunk, 8)[0]
    p12 = struct.unpack_from('<I', chunk, 12)[0]
    print(f"Map {i} Block at 0x{off + i*32:06X}:")
    print(f"  +0x00: {p0:08X} (ROM={hex(p0 & 0x1FFFFFF)})")
    print(f"  +0x04: {p4:08X}")
    print(f"  +0x08: {p8:08X}")
    print(f"  +0x0C: {p12:08X}")
