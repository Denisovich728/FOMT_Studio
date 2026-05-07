import struct
with open('j:\\Repositorios\\fomt_studio\\Modded_FoMT.gba', 'rb') as f:
    rom = f.read()

off = 0x105EDC
for i in range(256):
    chunk = rom[off + i*32 : off + i*32 + 32]
    p = struct.unpack_from('<I', chunk, 0)[0]
    if not (0x08000000 <= p < 0x09FFFFFF):
        print(f"Map {i} broken! p = 0x{p:08X}")
        break
    #print(f"Map {i} OK")
