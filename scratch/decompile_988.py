
import sys
import os

# Añadir el directorio raíz al path
sys.path.append(os.getcwd())

from Nucleos_de_Procesamiento.Nucleo_de_Datos.proyecto import FoMTProject

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
    # Decompilar
    text, stmts = parser.decompile_from_offset(0x003944D0, event_id=event_id)
    
    print("--- DECOMPILACION EVENTO 988 ---")
    print(text)
    print("--------------------------------")

if __name__ == "__main__":
    main()
