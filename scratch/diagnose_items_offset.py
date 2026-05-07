
import os
import sys

# Añadir el directorio raíz al path
sys.path.append(os.getcwd())

from Nucleos_de_Procesamiento.Nucleo_de_Datos.super_lib import SuperLibrary

def main():
    lib = SuperLibrary(is_mfomt=False)
    lib.load_all()
    
    # Buscar Blessed Sickle y Animal Medicine
    print("--- Diagnóstico de ítems/herramientas ---")
    for idx, name in lib.item_map.items():
        if "Sickle" in name or "Medicine" in name or "Hammer" in name:
            print(f"ID: 0x{idx:02X} ({idx:3d}) -> {name}")
            
    print("\n--- Diagnóstico de herramientas específicas ---")
    for idx, name in lib.tool_map.items():
         print(f"ID: 0x{idx:02X} ({idx:3d}) -> {name}")

if __name__ == "__main__":
    main()
