import struct
import sys
import os

def find_map_table(rom_path):
    with open(rom_path, 'rb') as f:
        data = f.read()
    
    # Event table range for MFoMT (USA)
    # Start: 0x1014BC, Count: 1416
    event_table_start = 0x081014BC
    event_table_end = event_table_start + 1416 * 4

    def is_ptr(p):
        return 0x08000000 <= p < 0x08800000
    
    def is_event_ptr(p):
        # Many map scripts are NOT in the main event table, 
        # but they are often in the same range or nearby.
        return 0x08100000 <= p < 0x08800000

    print(f"Scanning for Map Header Table in {os.path.basename(rom_path)}...")
    
    for i in range(0, len(data) - 128, 4):
        # Check first entry of a potential table
        p_layout, p_props, p_npcs, p_script, p_tileset = struct.unpack_from('<IIIII', data, i)
        
        if is_ptr(p_layout) and is_ptr(p_npcs) and is_ptr(p_script) and is_ptr(p_tileset):
            # Verify p_layout points to an LZ77 block
            layout_off = p_layout & 0x01FFFFFF
            if layout_off < len(data) and data[layout_off] == 0x10:
                # Potential match! Check next 2 entries to confirm stride of 32
                off2 = i + 32
                off3 = i + 64
                if off3 + 16 < len(data):
                    l2 = struct.unpack_from('<I', data, off2)[0]
                    l3 = struct.unpack_from('<I', data, off3)[0]
                    if is_ptr(l2) and (l2 & 0x1FFFFFF) < len(data) and data[l2 & 0x1FFFFFF] == 0x10:
                        if is_ptr(l3) and (l3 & 0x1FFFFFF) < len(data) and data[l3 & 0x1FFFFFF] == 0x10:
                            print(f"!!! FOUND MAP TABLE AT 0x{i:06X} !!!")
                            return i

if __name__ == "__main__":
    find_map_table(sys.argv[1])
