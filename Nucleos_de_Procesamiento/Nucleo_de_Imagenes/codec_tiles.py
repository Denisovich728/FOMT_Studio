# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.3.1)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
"""
codec_tiles.py — Adaptador de Compatibilidad v2.0
══════════════════════════════════════════════════
Reemplaza el codec antiguo. Ahora actúa como una capa delgada que redirige
toda la lógica real al motor BlueSpider en mapas.py.
Mantiene las funciones de conversión de color que siguen siendo útiles.
"""
import struct
from typing import List, Tuple
from PIL import Image

# ── Paleta / Color ──────────────────────────────────────────────────
def bgr555_to_rgb(color_16: int) -> Tuple[int, int, int]:
    """BGR555 → RGB888 (sin cambios, sigue siendo válida)."""
    r = (color_16 & 0x1F) << 3
    g = ((color_16 >> 5) & 0x1F) << 3
    b = ((color_16 >> 10) & 0x1F) << 3
    return (r, g, b)

def rgb_to_bgr555(r: int, g: int, b: int) -> int:
    """RGB888 → BGR555 para re-inserción en GBA."""
    return ((r >> 3) & 0x1F) | (((g >> 3) & 0x1F) << 5) | (((b >> 3) & 0x1F) << 10)

# ── GBATile — wrapper hacia el motor BlueSpider ────────────────────
def decode_4bpp_tile(data: bytes, offset: int = 0) -> List[int]:
    """
    Decodifica un tile 8×8 4bpp.
    Wrapper de compatibilidad con el motor BlueSpider (GBATile).
    Retorna 64 índices de color (0-15).
    """
    pixels = []
    for i in range(32):
        if offset + i >= len(data):
            pixels.extend([0, 0])
            continue
        byte = data[offset + i]
        pixels.append(byte & 0x0F)   # Low nibble = píxel izquierdo
        pixels.append(byte >> 4)     # High nibble = píxel derecho
    return pixels

def encode_4bpp_tile(pixels: List[int]) -> bytes:
    """64 índices → 32 bytes 4bpp lineal."""
    if len(pixels) != 64:
        raise ValueError("Se requieren 64 píxeles")
    data = bytearray()
    for i in range(0, 64, 2):
        data.append((pixels[i] & 0xF) | ((pixels[i+1] & 0xF) << 4))
    return bytes(data)

# ── Tabla de dimensiones OAM (copiada de mapas.py BlueSpider) ──────
OAM_DIM_TABLE = {
    (0,0):(8,8),   (0,1):(16,16), (0,2):(32,32), (0,3):(64,64),
    (1,0):(16,8),  (1,1):(32,8),  (1,2):(32,16), (1,3):(64,32),
    (2,0):(8,16),  (2,1):(8,32),  (2,2):(16,32), (2,3):(32,64),
}

def get_sprite_dimensions(shape: int, size: int) -> Tuple[int, int]:
    return OAM_DIM_TABLE.get((shape, size), (8, 8))

def decode_oam_attributes(data: bytes) -> dict:
    """
    Decodifica 6 bytes de OAM (Attr0 + Attr1 + Attr2).
    Compatible con el OAMEntry de mapas.py.
    """
    if len(data) < 6:
        return {}
    a0, a1, a2 = struct.unpack('<HHH', data[:6])
    shape = (a0 >> 14) & 3
    size  = (a1 >> 14) & 3
    w, h  = get_sprite_dimensions(shape, size)
    return {
        "x": a1 & 0x1FF,
        "y": a0 & 0xFF,
        "w": w, "h": h,
        "tile_id":     a2 & 0x3FF,
        "is_8bpp":     bool((a0 >> 13) & 1),
        "palette_bank": (a2 >> 12) & 0xF,
        "priority":    (a2 >> 10) & 3,
        "flip_h":      bool((a1 >> 12) & 1),
        "flip_v":      bool((a1 >> 13) & 1),
    }

def assemble_sprite(tileset_data: bytes, oam: dict) -> List[List[int]]:
    """
    Ensambla el sprite usando la lógica 1D-mapping (FoMT estándar).
    Retorna una matriz 2D de índices de color.
    """
    w, h = oam["w"], oam["h"]
    tile_size = 64 if oam.get("is_8bpp") else 32
    canvas = [[0]*w for _ in range(h)]
    tiles_x, tiles_y = w//8, h//8
    for ty in range(tiles_y):
        for tx in range(tiles_x):
            tid = oam["tile_id"] + ty * tiles_x + tx
            off = tid * tile_size
            if off + tile_size > len(tileset_data):
                continue
            if oam.get("is_8bpp"):
                pxs = list(tileset_data[off:off+64])
            else:
                pxs = decode_4bpp_tile(tileset_data, off)
            for py in range(8):
                for px in range(8):
                    canvas[ty*8+py][tx*8+px] = pxs[py*8+px]
    return canvas

# ── Render rápido a Pillow (para exportación) ───────────────────────
def render_tiles_to_pil(raw: bytes, palette_colors: List[Tuple[int,int,int]],
                        tiles_wide: int = 16, is_8bpp: bool = False) -> Image.Image:
    """
    Renderiza un banco de tiles a una imagen Pillow RGB.
    Substituye la lógica de _render_linear de tile_viewer.
    """
    tile_size = 64 if is_8bpp else 32
    num_tiles = len(raw) // tile_size
    if num_tiles == 0:
        return Image.new('RGB', (8, 8))

    tiles_x = tiles_wide
    tiles_y = (num_tiles + tiles_x - 1) // tiles_x
    img = Image.new('RGB', (tiles_x*8, tiles_y*8))
    px = img.load()

    for t in range(num_tiles):
        off  = t * tile_size
        base_x = (t % tiles_x) * 8
        base_y = (t // tiles_x) * 8
        if is_8bpp:
            pxs = list(raw[off:off+64])
        else:
            pxs = decode_4bpp_tile(raw, off)
        for py in range(8):
            for pxx in range(8):
                idx = pxs[py*8+pxx]
                color = palette_colors[idx] if idx < len(palette_colors) else (0,0,0)
                px[base_x+pxx, base_y+py] = color[:3]
    return img