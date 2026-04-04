import sys
import os

# Añadir la carpeta j:\Repositorios al path para importar fomt_studio
sys.path.append("j:/Repositorios")

from Nucleos_de_Procesamiento.Nucleo_de_Datos.super_lib import SuperLibrary

def test_compression():
    # Usar la ROM detectada por antigravity
    rom_path = "J:/Matriz De Datos Principal/Proyectos De Programacion/Proyecto De Descompilacion GBA/HM_MFOMT.gba"
    if not os.path.exists(rom_path):
        print(f"Error: ROM no encontrada en {rom_path}")
        return

    print("--- Iniciando Brain Scan de Bancos de Datos ---")
    with open(rom_path, "rb") as f:
        rom_data = f.read()

    # MFoMT es True
    lib = SuperLibrary(is_mfomt=True)
    lib.scan_data_banks(rom_data)
    
    banks = lib.data_banks
    print(f"Total de bancos LZ77 detectados por StanHash: {len(banks)}")
    
    # Probar descompresión de los primeros 5 bancos detectados
    from Nucleos_de_Procesamiento.Nucleo_de_Datos.Utilidades.compression import decompress_lz77
    sample_offsets = sorted(banks.keys())[:5]
    for off in sample_offsets:
        size, name = banks[off]
        print(f"Probando Banco {name} (Offset: 0x{off:06X}, Size: {size} bytes)...")
        try:
            # Obtener 64KB de datos desde el offset para asegurar que tenemos todo el bloque comprimido
            raw_chunk = rom_data[off : off + 0xFFFF]
            data = decompress_lz77(raw_chunk)
            if len(data) == size:
                print(f"  -> OK: Descompresión exitosa ({len(data)} bytes).")
            else:
                print(f"  -> ERROR: Tamaño inconsistente (Got {len(data)}, Expected {size}).")
        except Exception as e:
            print(f"  -> ERROR en descompresión: {e}")

if __name__ == "__main__":
    test_compression()
