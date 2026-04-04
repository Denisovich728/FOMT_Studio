import struct
import sys

def seek_map_headers(rom_path):
    with open(rom_path, 'rb') as f:
        data = f.read()
    
    # 0x0813E994 was a previously mentioned MFoMT offset. Let's look there first.
    # Note: MFoMT US has the map table at 0x0811776C? No, let's scan.
    
    # We look for a pointer table (0x08XXXXXX) where each entry is 24-32 bytes.
    # Often, map headers are a table of STRUCTS, not pointers to structs.
    # Each struct starts with 3 pointers (Layout, Warps, NPCs).
    
    # Scan from 0x100000 to 0x160000 (usual table area)
    for i in range(0x100000, 0x160000, 4):
        if i + 16 > len(data): break
        p1, p2, p3, p4 = struct.unpack_from('<IIII', data, i)
        
        # Heuristics:
        # All 4 must be valid pointers to the 0x08 ROM space (0x08000000 - 0x08800000)
        # OR p1, p2, p3 are pointers and p4 is a small integer (width/height)
        
        is_ptr = lambda x: 0x08000000 <= x < 0x08800000
        
        if is_ptr(p1) and is_ptr(p2) and is_ptr(p3):
             # Check if p4 is also a ptr or a small value (< 100)
             if is_ptr(p4) or (0 < p4 < 100):
                 # Possible Map Header Table!
                 print(f"Found candidate at 0x{i:06X}: {p1:08X} {p2:08X} {p3:08X} {p4:08X}")
                 # Look at next entry to see if it follows
                 if i + 32 + 12 < len(data):
                     n1, n2, n3 = struct.unpack_from('<III', data, i + 32)
                     if is_ptr(n1) and is_ptr(n2) and is_ptr(n3):
                         print(f"  -> VALID TABLE DETECTED! (Stride=32)")
                         break

if __name__ == "__main__":
    seek_map_headers(sys.argv[1])
