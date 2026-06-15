import struct
import json
import os

def export_map_table(rom_path, output_json):
    with open(rom_path, 'rb') as f:
        rom = f.read()

    start_offset = 0x105EDC
    current_offset = start_offset
    map_id = 0
    maps = []

    while True:
        data = rom[current_offset:current_offset+40]
        if len(data) < 40:
            break
            
        p_gfx = struct.unpack('<I', data[0:4])[0]
        p_pal1 = struct.unpack('<I', data[4:8])[0]
        p_pal2 = struct.unpack('<I', data[8:12])[0]
        p_bg1 = struct.unpack('<I', data[12:16])[0]
        p_bg2 = struct.unpack('<I', data[16:20])[0]
        p_col = struct.unpack('<I', data[20:24])[0]
        p_obj1 = struct.unpack('<I', data[24:28])[0]
        p_obj2 = struct.unpack('<I', data[28:32])[0]
        width_height = struct.unpack('<I', data[32:36])[0]
        
        width = width_height & 0xFFFF
        height = (width_height >> 16) & 0xFFFF

        # Validate that p_bg1 is a ROM pointer to ensure it's a valid map header
        if not (0x08000000 <= p_bg1 < 0x09000000):
            print(f'Terminado el parseo. Se encontró el final de la tabla en Map ID {map_id}.')
            break
            
        maps.append({
            'internal_id': map_id,
            'hex_id': f'{map_id:02X}',
            'width': width,
            'height': height,
            'pointers': {
                'p_gfx': f'0x{p_gfx:08X}',
                'p_pal1': f'0x{p_pal1:08X}',
                'p_pal2': f'0x{p_pal2:08X}',
                'p_bg1': f'0x{p_bg1:08X}',
                'p_bg2': f'0x{p_bg2:08X}',
                'p_col': f'0x{p_col:08X}',
                'p_obj1': f'0x{p_obj1:08X}',
                'p_obj2': f'0x{p_obj2:08X}'
            }
        })
        
        map_id += 1
        current_offset += 40

    with open(output_json, 'w') as f:
        json.dump(maps, f, indent=4)
    print(f'Exportados {len(maps)} mapas a {output_json}')

if __name__ == '__main__':
    rom_path = r'j:\scratch\Harvest Moon - Friends of Mineral Town.gba'
    output_path = r'j:\Repositorios\fomt_studio\Banco_de_Datos\Cilixes\fomt\fomt_map_table.json'
    export_map_table(rom_path, output_path)
