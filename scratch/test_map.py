import struct
with open('j:\\Repositorios\\fomt_studio\\Modded_FoMT.gba', 'rb') as f:
    rom = f.read()

off = 0x0E5DB0
p = struct.unpack_from('<I', rom, off)[0]
print(f"p = {p:08X}")
if 0x08000000 <= p < 0x09FFFFFF:
    lo = p & 0x01FFFFFF
    print(f"lo = {lo:08X}, rom[lo] = {rom[lo]:02X}")
    if rom[lo] in (0x10, 0x70, 0x00):
        print("MATCHED!")
    else:
        print("Header not matched")
else:
    print("Not a valid pointer")
