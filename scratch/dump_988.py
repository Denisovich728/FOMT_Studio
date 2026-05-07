
import struct
import os
import sys

# Añadir el directorio raíz al path
sys.path.append(os.getcwd())

from Nucleos_de_Procesamiento.Nucleo_de_Datos.proyecto import FoMTProject
from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.bytecode.decoder import decode_script

def main():
    rom_path = "Modded_FoMT3.gba"
    project = FoMTProject()
    project.step_1_detect_rom(rom_path)
    
    # Evento 988
    # Offset: 0x003944D0
    offset = 0x003944D0
    
    # Leer un trozo de la ROM
    data = project.read_rom(offset, 256)
    
    # Decodificar instrucciones
    script = decode_script(data)
    
    print("--- BYTECODE EVENTO 988 ---")
    for ins in script.instructions:
        print(ins)
    print("---------------------------")

if __name__ == "__main__":
    main()
