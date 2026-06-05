import sys, struct
sys.path.insert(0, r'j:\Repositorios\fomt_studio')

from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.mapas import MapParser, decompress_auto

class P:
    def __init__(self):
        with open(r'j:\scratch\Harvest Moon - Friends of Mineral Town.gba','rb') as f:
            self.base_rom_data = f.read()

proj = P()
rom = proj.base_rom_data
parser = MapParser(proj)
parser.scan_maps()

print("=== MAP POINTER TABLE (69 maps) ===")
print("ID    p_gfx        p_pal1       p_pal2       p_bg1        W    H")
for m in parser.maps:
    print(f"{m.map_id:3d}   0x{m.p_gfx:08X}   0x{m.p_pal1:08X}   0x{m.p_pal2:08X}   0x{m.p_bg1:08X}   {m.width:3d}  {m.height:3d}")

# Now test hypothesis: p_gfx = ALL tile data (no block split)
# If entire 32768 bytes = tiles => 1024 tiles
# tilemap entries = direct GBA BG tile refs (10-bit tile idx)
print("\n=== HYPOTHESIS TEST: Map 0 as direct tile refs ===")
m = parser.maps[0]
raw_gfx = decompress_auto(rom, m.p_gfx & 0x01FFFFFF)
print(f"p_gfx decompressed: {len(raw_gfx)} bytes = {len(raw_gfx)//32} tiles of 8x8")

raw_bg1 = decompress_auto(rom, m.p_bg1 & 0x01FFFFFF)
print(f"p_bg1 decompressed: {len(raw_bg1)} bytes = {len(raw_bg1)//2} cells")
print(f"Map dims: {m.width}x{m.height} = {m.width*m.height} cells")
print(f"  -> renders as: {m.width*8}x{m.height*8} pixels (8x8 tiles)")
print(f"  -> or renders as: {m.width*16}x{m.height*16} pixels (16x16 blocks)")

# What's the max tile index in the tilemap?
max_tile = 0
for i in range(len(raw_bg1)//2):
    val = struct.unpack_from('<H', raw_bg1, i*2)[0]
    idx = val & 0x3FF
    if idx > max_tile:
        max_tile = idx
print(f"\nMax tile index in tilemap: {max_tile}")
print(f"Total tiles available (32KB/32): {len(raw_gfx)//32}")
print(f"Fits? {max_tile < len(raw_gfx)//32}")
