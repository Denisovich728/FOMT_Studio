import struct
with open('j:\\Repositorios\\fomt_studio\\Modded_FoMT.gba', 'rb') as f:
    rom = f.read()

lo = 0x086EB014 & 0x1FFFFFF
print(f"Data at 0x{lo:06X}: {rom[lo]:02X}")
