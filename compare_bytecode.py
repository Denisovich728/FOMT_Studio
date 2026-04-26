import sys
import os
import struct
import binascii
sys.path.append(r'd:\Repositorios\FOMT_Studio')

from Nucleos_de_Procesamiento.Nucleo_de_Eventos.eventos import FoMTEventParser
from Nucleos_de_Procesamiento.Nucleo_de_Datos.proyecto import FoMTProject
from Nucleos_de_Procesamiento.Nucleo_de_Datos.super_lib import SuperLibrary

project = FoMTProject()
project.step_1_detect_rom(r'd:\Repositorios\FOMT_Studio\Modded_FoMT.gba')
project.super_lib = SuperLibrary(is_mfomt=False)
project.event_parser = FoMTEventParser(project)

# Event 98 offset is 0x2C5540
off = 0x2C5540
header = project.read_rom(off, 16)
print(f"Header at 0x{off:06X}: {binascii.hexlify(header)}")

code, stmts = project.event_parser.decompile_to_ui(98)
orig_size = project.event_parser.get_last_scanned_size(98)
print(f"Original size from parser: {orig_size}")

bytecode = project.event_parser.compile_text_to_bytecode(code)
print(f"New bytecode size: {len(bytecode)}")
print(f"New bytecode hex: {binascii.hexlify(bytecode[:64])}")
