import struct

def inspect_map_table():
    with open('j:\\Repositorios\\fomt_studio\\Modded_FoMT.gba', 'rb') as f:
        rom_data = f.read()
        
    table_offset = 0x105EDC
    
    print("=== MAP from 0x105EDC ===")
    chunk = rom_data[table_offset:table_offset+24]
    hex_chunk = ' '.join(f"{b:02X}" for b in chunk)
    print(f"Hex: {hex_chunk}")
    
    p_layout = struct.unpack_from('<I', chunk, 0)[0]
    p_tileset = struct.unpack_from('<I', chunk, 4)[0]
    p_objects = struct.unpack_from('<I', chunk, 8)[0]
    p_script = struct.unpack_from('<I', chunk, 12)[0]
    
    print(f"Layout: 0x{p_layout:08X}")
    print(f"Tileset: 0x{p_tileset:08X}")
    print(f"Objects: 0x{p_objects:08X}")
    print(f"Script: 0x{p_script:08X}")

if __name__ == '__main__':
    inspect_map_table()
