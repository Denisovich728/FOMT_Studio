import struct
import sys

def scan_map_table(rom_path):
    with open(rom_path, 'rb') as f:
        data = f.read()
    
    # Common map structure candidates for MFoMT (US)
    # 0x0813E994 is a common one for Map Header entries.
    offsets = [0x13E994, 0x11776C, 0x11ABAC, 0x10B45C]
    
    for base in offsets:
        print(f"\nScanning candidate offset: 0x{base:06X}")
        try:
            for i in range(10): # Check first 10 entries
                off = base + i * 32
                struct_data = struct.unpack('<IIIIIIII', data[off:off+32])
                # A valid entry should have pointers (0x08XXXXXX) or zero
                valid = all(x == 0 or (0x08000000 <= x < 0x09000000) for x in struct_data[:4])
                if valid:
                    print(f"Entry {i:02d}: {['0x%08X'%x for x in struct_data]}")
                else:
                    if i == 0: print("Doesn't look like pointers.")
                    break
        except:
            print("Failed to read.")

if __name__ == "__main__":
    scan_map_table(sys.argv[1])
