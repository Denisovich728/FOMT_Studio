import struct
with open('j:\\Repositorios\\fomt_studio\\Modded_FoMT.gba', 'rb') as f:
    rom = f.read()

off = 0x0DBD58
chunk = rom[off:off+16]
print("Code at 0x0DBD58:")
print(chunk.hex())
