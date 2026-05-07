
import struct
from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.decoder import decode_script

ROM_PATH = "Nucleos_de_Procesamiento/data/rom.gba"
TABLE_OFFSET = 0x3D740
EVENT_ID = 355

with open(ROM_PATH, "rb") as f:
    rom_data = f.read()

ptr_off = TABLE_OFFSET + (EVENT_ID * 4)
ptr_val = struct.unpack_from('<I', rom_data, ptr_off)[0]
script_off = ptr_val & 0x01FFFFFF

# Leer un bloque generoso
chunk_data = rom_data[script_off:script_off + 2048]
script = decode_script(chunk_data)

print(f"BYTECODE ANALYSIS FOR EVENT {EVENT_ID} (Offset: {hex(script_off)}):")
for i, ins in enumerate(script.instructions):
    # Buscar la zona de Init_Notice_Board_UI (opcode Call con ID que termina en algo específico)
    # o simplemente imprimir los primeros 100
    if i < 150:
        print(f"[{i:03}] {ins}")
