import struct
from typing import List, Tuple

def bgr555_to_rgb(color_16: int) -> Tuple[int, int, int]:
    """Convierte un color de 16 bits BGR555 a una tupla RGB888 (0-255)."""
    # GBA BGR555: 0BBBBBGGGGGRRRRR
    r = (color_16 & 0x1F) << 3
    g = ((color_16 >> 5) & 0x1F) << 3
    b = ((color_16 >> 10) & 0x1F) << 3
    return (r, g, b)

def rgb_to_bgr555(r: int, g: int, b: int) -> int:
    """Convierte una tupla RGB888 a un color de 16 bits BGR555 para GBA."""
    r5 = (r >> 3) & 0x1F
    g5 = (g >> 3) & 0x1F
    b5 = (b >> 3) & 0x1F
    return r5 | (g5 << 5) | (b5 << 10)

def decode_4bpp_tile(data: bytes, offset: int = 0) -> List[int]:
    """
    Decodifica un tile de 8x8 píxeles en formato 4bpp lineal (GBA style).
    Retorna una lista de 64 índices de color (0-15).
    """
    pixels = []
    # Un tile de 8x8 en 4bpp ocupa 32 bytes (64 píxeles * 0.5 bytes/pixel)
    for i in range(32):
        byte = data[offset + i]
        # Píxel 1: Low nibble, Píxel 2: High nibble (GBA Reverse Order)
        p1 = byte & 0x0F
        p2 = byte >> 4
        pixels.append(p1)
        pixels.append(p2)
    return pixels

def encode_4bpp_tile(pixels: List[int]) -> bytes:
    """
    Encodifica una lista de 64 índices de color en un tile de 32 bytes 4bpp lineal.
    """
    if len(pixels) != 64:
        raise ValueError("Se requieren exactamente 64 índices de píxel para un tile de 8x8")
    
    data = bytearray()
    for i in range(0, 64, 2):
        p1 = pixels[i] & 0x0F
        p2 = pixels[i+1] & 0x0F
        byte = p1 | (p2 << 4)
        data.append(byte)
    return bytes(data)

def render_tile_to_rgb(pixels: List[int], palette: List[Tuple[int, int, int]]) -> List[Tuple[int, int, int]]:
    """Aplica una paleta a los índices de píxel para obtener colores RGB."""
    return [palette[idx] if idx < len(palette) else (0,0,0) for idx in pixels]
