
import struct
import os
import sys

# Añadir el directorio raíz al path
sys.path.append(os.getcwd())

from Nucleos_de_Procesamiento.Nucleo_de_Datos.proyecto import FoMTProject
from Nucleos_de_Procesamiento.Nucleo_de_Eventos.eventos import FoMTEventParser

def main():
    rom_path = "Modded_FoMT3.gba"
    project = FoMTProject()
    project.step_1_detect_rom(rom_path)
    
    # Evento 97 (Manejador de diálogos comunes)
    # Buscamos su offset
    parser = FoMTEventParser(project)
    name, offset = parser.get_event_name_and_offset(97)
    print(f"Evento 97: {name} at 0x{offset:08X}")
    
    # Descompilar
    try:
        text, stmts = parser.decompile_to_ui(1011)
        print(text)
    except Exception as e:
        print(f"Error descompilando 97: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
