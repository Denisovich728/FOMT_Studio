import struct
import json

def inspect_map_table():
    with open('j:\\Repositorios\\fomt_studio\\Modded_FoMT.gba', 'rb') as f:
        rom_data = f.read()
        
    table_offset = 0x0E5DB0
    
    print("=== MAP 0 ===")
    chunk = rom_data[table_offset:table_offset+32]
    hex_chunk = ' '.join(f"{b:02X}" for b in chunk)
    print(f"Hex: {hex_chunk}")
    
    p_visual = struct.unpack_from('<I', chunk, 0)[0]
    p_unk = struct.unpack_from('<I', chunk, 4)[0]
    p_interaction = struct.unpack_from('<I', chunk, 8)[0]
    p_warp = struct.unpack_from('<I', chunk, 12)[0]
    
    print(f"Visual: 0x{p_visual:08X}")
    print(f"Unknown (+04): 0x{p_unk:08X}")
    print(f"Interaction: 0x{p_interaction:08X}")
    print(f"Warp: 0x{p_warp:08X}")
    
    if 0x08000000 <= p_visual < 0x09000000:
        v_off = p_visual & 0x01FFFFFF
        v_chunk = rom_data[v_off:v_off+32]
        print(f"\nVisual Header at 0x{v_off:06X}:")
        print(' '.join(f"{b:02X}" for b in v_chunk))

if __name__ == '__main__':
    inspect_map_table()
