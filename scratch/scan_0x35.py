
import struct
import os
import sys

# Añadir el directorio raíz al path
sys.path.append(os.getcwd())

from Nucleos_de_Procesamiento.Nucleo_de_Datos.proyecto import FoMTProject

def main():
    rom_path = "Modded_FoMT3.gba"
    project = FoMTProject()
    project.step_1_detect_rom(rom_path)
    project.step_2_scan_events()
    parser = project.event_parser
    
    print(f"Buscando llamadas a Opcode 0x35 en los primeros 1000 eventos...")
    
    found_any = False
    for i in range(1000):
        hint, offset = parser.get_event_name_and_offset(i)
        if offset is None: continue
        
        # Decompilar para ver si contiene la función
        try:
            text, stmts = parser.decompile_from_offset(offset, event_id=i)
            if "OpcodeUnknw_035" in text or "Tick_Overnight_Engine" in text:
                print(f"Evento {i} ({hint}) contiene la función 0x35.")
                # Extraer la línea de la función
                for line in text.splitlines():
                    if "OpcodeUnknw_035" in line or "Tick_Overnight_Engine" in line:
                        print(f"  Línea: {line.strip()}")
                        found_any = True
        except:
            pass
            
    if not found_any:
        print("No se encontraron más llamadas en los primeros 1000 eventos.")

if __name__ == "__main__":
    main()
