
import sys
import os

# Añadir el directorio raíz al path
sys.path.append(os.getcwd())

from Nucleos_de_Procesamiento.Nucleo_de_Datos.proyecto import FoMTProject
from Nucleos_de_Procesamiento.Nucleo_de_Eventos.eventos import FoMTEventParser

def main():
    # Detectar ROM
    rom_path = "Modded_FoMT3.gba"
    
    if not os.path.exists(rom_path):
        print(f"No se encontró {rom_path}")
        return

    project = FoMTProject()
    project.step_1_detect_rom(rom_path)
    project.step_2_scan_events()
    parser = project.event_parser
    
    event_id = 988
    hint, offset = parser.get_event_name_and_offset(event_id)
    
    if offset is None:
        print(f"Evento {event_id} ({hint}) no tiene un offset válido.")
    else:
        print(f"Evento {event_id} ({hint}) Offset: 0x{offset:08X}")

if __name__ == "__main__":
    main()
