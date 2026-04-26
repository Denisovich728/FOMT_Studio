import struct
import os

rom_path = r'd:\Repositorios\FOMT_Studio\Modded_FoMT.gba'
with open(rom_path, 'rb') as f:
    rom = f.read()

table_off = 0x0F89D4
count = 1329
for i in range(count):
    ptr_off = table_off + i*4
    ptr_val = struct.unpack('<I', rom[ptr_off:ptr_off+4])[0]
    ptr = ptr_val & 0x1FFFFFF
    if ptr == 0 or ptr > 0x800000: continue
    if rom[ptr:ptr+4] == b'RIFF':
        sz = struct.unpack('<I', rom[ptr+4:ptr+8])[0] + 8
        if 400 <= sz <= 415:
            print(f'Event {i} at 0x{ptr:06X} size {sz}')
