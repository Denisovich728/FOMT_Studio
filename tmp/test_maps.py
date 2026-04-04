import sys
import os

# Añadir j:\Repositorios al path
sys.path.append("j:/Repositorios")

from Nucleos_de_Procesamiento.Nucleo_de_Datos.proyecto import FoMTProject

def test_map_extraction():
    rom_path = "J:/Matriz De Datos Principal/Proyectos De Programacion/Proyecto De Descompilacion GBA/HM_MFOMT.gba"
    if not os.path.exists(rom_path):
        print("ROM no encontrada.")
        return

    proj = FoMTProject()
    # Simular carga mínima
    proj.is_mfomt = True
    with open(rom_path, 'rb') as f:
        proj.base_rom_data = f.read()
    proj.base_rom_path = rom_path
    
    from Nucleos_de_Procesamiento.Nucleo_de_Datos.super_lib import SuperLibrary
    proj.super_lib = SuperLibrary(proj.is_mfomt)
    
    from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.mapas import MapParser
    proj.map_parser = MapParser(proj)
    
    print("Iniciando escaneo de mapas...")
    proj.map_parser.scan_maps()
    
    maps = proj.map_parser.maps
    print(f"Total de mapas extraídos: {len(maps)}")
    
    if len(maps) > 0:
        m0 = maps[0]
        print(f"Mapa 0: Layout=0x{m0.layout_offset:X}, Script=0x{m0.script_offset:X}, Dim={m0.width}x{m0.height}")
        name = proj.super_lib.get_map_name_hint(0)
        print(f"Nombre bautizado: {name}")

if __name__ == "__main__":
    test_map_extraction()
