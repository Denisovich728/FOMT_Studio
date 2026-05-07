import struct
with open('j:\\Repositorios\\fomt_studio\\Modded_FoMT.gba', 'rb') as f:
    rom = f.read()

off = 0x105EDC
print(f"Map Table at 0x{off:06X}:")
for i in range(5):
    p = struct.unpack_from('<I', rom, off + i*4)[0]
    print(f"  Map {i} Pointer: 0x{p:08X}")
    if 0x08000000 <= p < 0x09FFFFFF:
        lo = p & 0x01FFFFFF
        # read the map header at `lo`
        h0 = struct.unpack_from('<I', rom, lo)[0]
        h8 = struct.unpack_from('<I', rom, lo+8)[0]
        hC = struct.unpack_from('<I', rom, lo+12)[0]
        print(f"    Header at 0x{lo:06X}:")
        print(f"      Visual: 0x{h0:08X}")
        print(f"      Interac: 0x{h8:08X}")
        print(f"      Losa: 0x{hC:08X}")
