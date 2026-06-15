import struct
from PIL import Image
from typing import List, Tuple, Optional

from Nucleos_Positronicos.Nucleo_de_Sprites.sprite_decoder import SpriteRenderer
from Nucleos_Positronicos.Nucleo_de_Mapas.codec_tiles import bgr555_to_rgb

# Mapeo estándar OAM para tamaño y forma
OAM_DIMS = {
    (0,0):(8,8),   (0,1):(16,16), (0,2):(32,32), (0,3):(64,64),
    (1,0):(16,8),  (1,1):(32,8),  (1,2):(32,16), (1,3):(64,32),
    (2,0):(8,16),  (2,1):(8,32),  (2,2):(16,32), (2,3):(32,64),
}

class MetaspritePiece:
    """
    Representa una pieza del metasprite (Sprite Batching).
    Estructura asumida: [TileID, OffsetX, OffsetY, Atributos] -> 8 bytes
    """
    def __init__(self, data: bytes):
        if len(data) < 8:
            self.tile_id = self.x = self.y = self.attr = 0
            return
            
        self.tile_id = struct.unpack_from('<H', data, 0)[0]
        self.x = struct.unpack_from('<h', data, 2)[0]
        self.y = struct.unpack_from('<h', data, 4)[0]
        self.attr = struct.unpack_from('<H', data, 6)[0]

    def to_bytes(self) -> bytes:
        return struct.pack('<HhhH', self.tile_id, self.x, self.y, self.attr)

    def render(self, tile_data: bytes, palette: List[Tuple[int,int,int]]) -> Optional[Image.Image]:
        # Suponemos que los atributos definen forma y tamaño similar al OAM
        # Si no funciona perfectamente, se puede adaptar luego.
        shape = (self.attr >> 14) & 3
        size = (self.attr >> 12) & 3 # Hipótesis
        w, h = OAM_DIMS.get((shape, size), (32, 32)) # Default 32x32 para retratos
        
        # O forzamos a 32x32 si el juego usa siempre piezas de 32x32 para retratos
        if w > 64 or h > 64:
            w = h = 32
            
        tiles_x = w // 8
        tiles_y = h // 8
        
        return SpriteRenderer.render_single_frame(
            tile_data, palette, tiles_x, tiles_y, self.tile_id
        )

class PortraitCompiler:
    """
    Parser y Compilador de Metasprites.
    """
    def __init__(self, rom_data: bytes):
        self.rom_data = bytearray(rom_data)
        
    def parse_assembly_map(self, offset: int, count: int = 16) -> List[MetaspritePiece]:
        """
        Lee una lista de piezas desde el offset.
        """
        pieces = []
        for i in range(count):
            start = offset + i * 8
            if start + 8 > len(self.rom_data):
                break
            chunk = self.rom_data[start:start+8]
            
            # Detectar fin de lista
            if chunk == b'\x00'*8 or chunk == b'\xFF'*8:
                break
                
            pieces.append(MetaspritePiece(chunk))
        return pieces

    def compile_assembly_map(self, offset: int, pieces: List[MetaspritePiece]):
        """
        Sobrescribe la ROM con las nuevas coordenadas y piezas.
        """
        for i, p in enumerate(pieces):
            start = offset + i * 8
            if start + 8 <= len(self.rom_data):
                self.rom_data[start:start+8] = p.to_bytes()

    def get_palette(self, offset: int) -> List[Tuple[int,int,int]]:
        """Lee la paleta BGR555 desde el offset."""
        if offset + 32 > len(self.rom_data):
            return SpriteRenderer.DEFAULT_PALETTE
            
        pal_data = self.rom_data[offset:offset+32]
        return [bgr555_to_rgb(struct.unpack_from('<H', pal_data, i*2)[0]) for i in range(16)]

