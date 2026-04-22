import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/..'))

from Nucleos_de_Procesamiento.Nucleo_de_Datos.super_lib import SuperLibrary

def test():
    import time
    rom_path = r"D:\Matriz De Datos Principal\Proyectos De Programacion\Proyecto De Descompilacion GBA\Harvest Moon - Friends of Mineral Town (USA).gba"
    
    if not os.path.exists(rom_path):
        print("ROM no encontrada para el test.")
        return
        
    with open(rom_path, "rb") as f:
        rom_data = f.read()
        
    print("Iniciando escaneo de firmas de manera multiproceso...")
    lib = SuperLibrary(False)
    
    t0 = time.time()
    lib.scan_data_banks(rom_data)
    
    print(f"Completado en {time.time() - t0:.2f} segundos!")
    print(f"Bancos de datos encontrados: {len(lib.data_banks)}")

if __name__ == '__main__':
    test()
