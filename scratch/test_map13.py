import struct
with open('j:\\Repositorios\\fomt_studio\\Modded_FoMT.gba', 'rb') as f:
    rom = f.read()

off = 0x106E74
for i in range(2):
    chunk = rom[off + i*24 : off + i*24 + 24]
    p0 = struct.unpack_from('<I', chunk, 0)[0]
    p4 = struct.unpack_from('<I', chunk, 4)[0]
    p8 = struct.unpack_from('<I', chunk, 8)[0]
    p12 = struct.unpack_from('<I', chunk, 12)[0]
    b16 = chunk[16]
    b17 = chunk[17]
    print(f"Map {i}:")
    print(f"  +0x00: {p0:08X}")
    print(f"  +0x04: {p4:08X}")
    print(f"  +0x08: {p8:08X}")
    print(f"  +0x0C: {p12:08X}")
    print(f"  +0x10: {b16}x{b17}")
