import sys
import struct
import os
import binascii
sys.path.append(r'd:\Repositorios\FOMT_Studio')

from Nucleos_de_Procesamiento.Nucleo_de_Datos.proyecto import FoMTProject
from Nucleos_de_Procesamiento.Nucleo_de_Datos.super_lib import SuperLibrary

project = FoMTProject()
project.step_1_detect_rom(r'd:\Repositorios\FOMT_Studio\Modded_FoMT.gba')
project.super_lib = SuperLibrary(is_mfomt=False)

# Event 98
loc_rom = project.super_lib.table_offset + (98 * 4)
ptr = struct.unpack('<I', project.read_rom(loc_rom, 4))[0] & 0x1FFFFFF
header = project.read_rom(ptr, 12)
sz = struct.unpack('<I', header[4:8])[0] + 8
data = project.read_rom(ptr, sz)

offset = 12
while offset < sz:
    chunk_name = data[offset:offset+4].decode('ascii', errors='ignore')
    chunk_sz = struct.unpack('<I', data[offset+4:offset+8])[0]
    if chunk_name == "CODE":
        code_chunk = data[offset+8:offset+8+chunk_sz]
        print(f"CODE Chunk Size: {chunk_sz}")
        print(f"Full CODE Hex: {binascii.hexlify(code_chunk)}")
    offset += 8 + chunk_sz
