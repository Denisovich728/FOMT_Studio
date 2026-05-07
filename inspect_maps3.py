import struct

def inspect_map_table():
    with open('j:\\Repositorios\\fomt_studio\\Modded_FoMT.gba', 'rb') as f:
        rom_data = f.read()
        
    table_offset = 0x0E5DB0
    
    for map_id in range(5):
        chunk = rom_data[table_offset + map_id * 0x20 : table_offset + map_id * 0x20 + 32]
        
        p_visual = struct.unpack_from('<I', chunk, 0)[0]
        p_04 = struct.unpack_from('<I', chunk, 4)[0]
        p_interaction = struct.unpack_from('<I', chunk, 8)[0]
        p_warp = struct.unpack_from('<I', chunk, 12)[0]
        
        print(f"=== MAP {map_id} ===")
        print(f"Visual (0x00): 0x{p_visual:08X}")
        print(f"Unknown (0x04): 0x{p_04:08X}")
        print(f"Interaction (0x08): 0x{p_interaction:08X}")
        print(f"Warp (0x0C): 0x{p_warp:08X}")
        print()

if __name__ == '__main__':
    inspect_map_table()
