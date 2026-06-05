import sys, struct
sys.path.insert(0, r'j:\Repositorios\fomt_studio')

from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.mapas import MapParser, decompress_auto
from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.fomt_mapdata import _apply_delta_4bpp, _parse_palette, _decode_4bpp_tileset, _render_tile
from PIL import Image

class P:
    def __init__(self):
        with open(r'j:\scratch\Harvest Moon - Friends of Mineral Town.gba','rb') as f:
            self.base_rom_data = f.read()

proj = P()
rom = proj.base_rom_data
parser = MapParser(proj)
parser.scan_maps()

mh = parser.maps[0]

# 1. Load Palettes
pal2_raw = decompress_auto(rom, mh.p_pal2 & 0x01FFFFFF)
palettes = _parse_palette(pal2_raw)
while len(palettes) < 16: palettes.append([(0,0,0)]*16)

# 2. Load Tiles (ALL of p_gfx)
gfx_raw = decompress_auto(rom, mh.p_gfx & 0x01FFFFFF)
gfx_raw = _apply_delta_4bpp(gfx_raw)
tiles = _decode_4bpp_tileset(gfx_raw, len(gfx_raw) // 32)

# 3. Load Tilemap (Direct 8x8 mapping)
bg1_raw = decompress_auto(rom, mh.p_bg1 & 0x01FFFFFF)
w, h = mh.width, mh.height

img = Image.new('RGB', (w * 8, h * 8), (20, 20, 40))

for row in range(h):
    for col in range(w):
        idx = (row * w + col) * 2
        if idx + 2 > len(bg1_raw): break
        
        val = struct.unpack_from('<H', bg1_raw, idx)[0]
        t_idx = val & 0x3FF
        h_flip = bool((val >> 10) & 1)
        v_flip = bool((val >> 11) & 1)
        p_idx = (val >> 12) & 0xF
        
        if t_idx < len(tiles):
            tile_img = _render_tile(tiles[t_idx], palettes[p_idx], h_flip, v_flip)
            img.paste(tile_img.convert('RGB'), (col * 8, row * 8))

out = r'C:\Users\Denis\.gemini\antigravity-ide\brain\c5e367b5-58c5-4d66-9173-0df464e12e3b\farm_8x8_test.png'
img.save(out)
print(f"Saved: {out}")
