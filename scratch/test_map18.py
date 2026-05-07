import struct
with open('j:\\Repositorios\\fomt_studio\\Modded_FoMT.gba', 'rb') as f:
    rom = f.read()

offsets = [0x0E5DB0, 0x105EDC, 0x106E74, 0x11776C, 0x10FF2C, 0x10FF14]

for off in offsets:
    for stride in [24, 32]:
        valid_maps = 0
        for i in range(256):
            chunk = rom[off + i*stride : off + i*stride + stride]
            if len(chunk) < stride: break
            p = struct.unpack_from('<I', chunk, 0)[0]
            if not (0x08000000 <= p < 0x09FFFFFF):
                break
            valid_maps += 1
        print(f"Offset 0x{off:06X} STRIDE={stride}: {valid_maps} maps")
