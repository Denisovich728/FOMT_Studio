import struct
import sys

def scan_maps(rom_path):
    with open(rom_path, 'rb') as f:
        data = f.read()
    
    # Common map header offsets for FoMT (US)
    offsets = [0x11776C, 0x117770, 0x11ABAC, 0x10B45C] # Some known candidates
    
    for base in offsets:
        print(f"\nScanning candidate offset: 0x{base:06X}")
        try:
            for i in range(5): # Check first 5 entries
                off = base + i * 32
                if off + 32 > len(data): break
                struct_data = struct.unpack('<IIIIIIII', data[off:off+32])
                print(f"Entry {i:02d}: {['0x%08X'%x for x in struct_data]}")
        except:
            print("Failed to read at this offset.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        scan_maps(sys.argv[1])
    else:
        print("Usage: scan_maps.py <rom.gba>")
