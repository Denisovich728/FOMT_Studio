import struct
with open('j:\\Repositorios\\fomt_studio\\Modded_FoMT.gba', 'rb') as f:
    rom = f.read()

off = 0x106E74
valid_maps = 0
for i in range(256):
    chunk = rom[off + i*24 : off + i*24 + 24]
    p = struct.unpack_from('<I', chunk, 0)[0]
    if not (0x08000000 <= p < 0x09FFFFFF):
        break
    valid_maps += 1
print(f"Total valid maps at 0x106E74: {valid_maps}")
