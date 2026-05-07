
import struct
import os
import sys

# Añadir el directorio raíz al path
sys.path.append(os.getcwd())

from Nucleos_de_Procesamiento.Nucleo_de_Datos.proyecto import FoMTProject
from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.objetos import ItemParser

def main():
    rom_path = "Modded_FoMT3.gba"
    if not os.path.exists(rom_path):
        print(f"ROM no encontrada: {rom_path}")
        return

    project = FoMTProject()
    project.step_1_detect_rom(rom_path)
    
    parser = ItemParser(project)
    items = parser.scan_foods()
    
    print("--- REPORTE DE HERRAMIENTAS REALES (ROM) ---")
    for it in items:
        if it.category == "Herramienta":
            # Formatear como hex para comparar con el script
            print(f"Index 0x{it.index:02X} ({it.index:3d}) -> {it.name_str}")

if __name__ == "__main__":
    main()
