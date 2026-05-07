import struct
with open('j:\\Repositorios\\fomt_studio\\Modded_FoMT.gba', 'rb') as f:
    rom = f.read()

off = 0x11776C
valid_maps = 0
for i in range(256):
    chunk = rom[off + i*24 : off + i*24 + 24]
    if len(chunk) < 24: break
    p = struct.unpack_from('<I', chunk, 0)[0]
    if not (0x08000000 <= p < 0x09FFFFFF):
        break
    valid_maps += 1
print(f"Total valid maps at 0x11776C (STRIDE=24): {valid_maps}")

valid_maps = 0
for i in range(256):
    chunk = rom[off + i*32 : off + i*32 + 32]
    if len(chunk) < 32: break
    p = struct.unpack_from('<I', chunk, 0)[0]
    if not (0x08000000 <= p < 0x09FFFFFF):
        break
    valid_maps += 1
print(f"Total valid maps at 0x11776C (STRIDE=32): {valid_maps}")
