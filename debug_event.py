import sys
import os
import struct
sys.path.append(r'd:\Repositorios\FOMT_Studio')

from Nucleos_de_Procesamiento.Nucleo_de_Eventos.eventos import FoMTEventParser
from Nucleos_de_Procesamiento.Nucleo_de_Datos.proyecto import FoMTProject
from Nucleos_de_Procesamiento.Nucleo_de_Datos.super_lib import SuperLibrary
from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.bytecode.decoder import decode_script

project = FoMTProject()
project.step_1_detect_rom(r'd:\Repositorios\FOMT_Studio\Modded_FoMT.gba')
project.super_lib = SuperLibrary(is_mfomt=False)

# Event 98
loc_rom = project.super_lib.table_offset + (98 * 4)
ptr = struct.unpack('<I', project.read_rom(loc_rom, 4))[0] & 0x1FFFFFF
sz = struct.unpack('<I', project.read_rom(ptr+4, 4))[0] + 8
data = project.read_rom(ptr, sz)

ast_script = decode_script(data)
print(f"Number of instructions: {len(ast_script.instructions)}")
print(f"Number of strings:      {len(ast_script.strings)}")

for i, ins in enumerate(ast_script.instructions):
    print(f"  {i:3}: {ins}")

for i, s in enumerate(ast_script.strings):
    print(f"  Str {i}: {s}")
