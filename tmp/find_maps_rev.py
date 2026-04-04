import struct
import sys
import os

# Añadir el path para importar fomt_studio
sys.path.append("j:/Repositorios")
from Nucleos_de_Procesamiento.Nucleo_de_Datos.Utilidades.compression import is_lz77_block

def find_map_headers_by_layout(rom_path):
    with open(rom_path, 'rb') as f:
        data = f.read()
    
    # 1. Encontrar bloques LZ77 que parezcan layouts (tamaño ~1000-8000 bytes)
    layouts = []
    for i in range(0, len(data) - 4, 4):
        if is_lz77_block(data, i):
            size = struct.unpack('<I', data[i+1:i+4] + b'\x00')[0]
            if 1000 < size < 10000:
                layouts.append(i | 0x08000000)
    
    print(f"Encontrados {len(layouts)} posibles layouts LZ77.")
    
    # 2. Buscar tablas de punteros que apunten a estos layouts
    for layout_ptr in layouts[:10]: # Probar con los primeros
        le_ptr = struct.pack('<I', layout_ptr)
        idx = data.find(le_ptr)
        while idx != -1:
            # Si encontramos el puntero, veamos si es parte de una estructura de mapa (stride 32)
            # Probamos si idx-4 o idx-8 o idx+0 es el inicio de la tabla
            print(f"Puntero a layout 0x{layout_ptr:08X} encontrado en 0x{idx:06X}")
            idx = data.find(le_ptr, idx + 4)

if __name__ == "__main__":
    find_map_headers_by_layout(sys.argv[1])
