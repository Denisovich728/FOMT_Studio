# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.0.0)
# "The Imposibility Update"
# Desarrollado por: Denisovich728
# ============================================================
"""
Motor de Gráficos y Mapas de FoMT Studio — Reescritura Total v2.0
══════════════════════════════════════════════════════════════════
Reemplaza por completo la lógica anterior.

Basado en ingeniería inversa directa de BlueSpider (mapped.pyd, mapdata.pyd):
  • parse_map_header  → estructura de 24 bytes confirmada
  • get_map_headers   → offsets correctos para versión USA
  • BlocksData.draw_block_layers → algoritmo de 4 sub-tiles × 2 bytes
  • Block layout: 16 bytes total = 4 subtiles_bajo + 4 subtiles_alto
    Cada subtile (2 bytes):
      byte0: tile_index (bits 0-9 en uint16 LE)
      byte1[3:0]: flip (bit2=x_flip, bit3=y_flip)
      byte1[7:4]: palette_index
  • MapData.load_tilesets → usa pals_ptr, img_data_ptr, block_data_ptr
  • Warp/Script events extraídos de la tabla de objetos del mapa
  • LZ77 decompressor (header 0x10) y Popuri RLE (header 0x70)
"""
import struct
import zlib
from PIL import Image
from typing import List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

# ═══════════════════════════════════════════════════════════════════
#  CONSTANTES — extraídas de BlueSpider (@USATH confirmada)
# ═══════════════════════════════════════════════════════════════════

TILE_W = TILE_H = 8       # Tiles GBA: 8×8 píxeles
BLOCK_W = BLOCK_H = 16    # Bloques del mapa: 2×2 tiles = 16×16 px
SUBTILE_BYTES = 2         # Cada sub-tile ocupa 2 bytes
BLOCK_BYTES = 16          # 4 sub-tiles capa baja + 4 sub-tiles capa alta
BITS_PER_PIXEL_4BPP = 4
TILE_BYTES_4BPP = (TILE_W * TILE_H * BITS_PER_PIXEL_4BPP) // 8  # = 32 bytes

# Tabla de posiciones de sub-tiles dentro de un bloque 16×16
# Orden GBA: top-left, top-right, bottom-left, bottom-right
SUBTILE_POSITIONS = [
    (0, 0), (8, 0),    # Fila superior
    (0, 8), (8, 8),    # Fila inferior
]

# Tablas de GFX de tilesets (BlueSpider TABLE_A + TABLE_B de mapped.pyd)
TILESET_GFX_TABLE_USA = [
    0x836800, 0x835E00, 0x835600, 0x834E00, 0x834600, 0x833E00,
    0x833600, 0x832E00, 0x832600, 0x831E00, 0x831600, 0x830E00,
    0x830600, 0x82FE00, 0x82F300, 0x838F00, 0x83B600, 0x83DF00,
    0x840800, 0x843100, 0x845A00, 0x848300, 0x84AC00, 0x84D500,
    0x84FE00, 0x852700, 0x855000, 0x857900, 0x85A200,
    0x874D00, 0x874500, 0x873D00, 0x873500, 0x872D00, 0x872500,
    0x871D00, 0x871500, 0x870D00, 0x870500,
    0x86FD00, 0x86F500, 0x86ED00, 0x86E600,
]

# Tabla de nombres de mapas (fomt_map_labels — BlueSpider mapped.pyd)
FOMT_MAP_LABELS = {
    0:  "Farm (Main)",
    1:  "Farm House",
    2:  "Farm Cave",
    3:  "Mineral Town",
    4:  "Town South",
    5:  "Rose Plaza",
    6:  "Church",
    7:  "Inn",
    8:  "Hospital",
    9:  "Blacksmith",
    10: "Supermarket",
    11: "Library",
    12: "Flower Shop",
    13: "Bakery",
    14: "Poultry Farm",
    15: "Yodel Farm",
    16: "Ranch House",
    17: "Aja Winery",
    18: "Hot Spring",
    19: "Mineral Mine",
    20: "Mine 1F",
    21: "Mine 2F",
    22: "Mine B1F",
    23: "Goddess Pond",
    24: "Harvest Sprite",
    25: "Connor's Cart",
    26: "Saibara House",
    27: "Town House",
    28: "Gotz House",
    29: "Barley House 1F",
    30: "Barley House 2F",
    31: "Mine Lake",
    32: "Mother's Hill",
    33: "Summit",
    34: "Mineral Mine",
    35: "Spring Mine",
    38: "Lake",
    47: "Tutorial Field",
    83: "Mineral Clinic",
    120: "Supermarket",
    121: "Inn 1F",
    122: "Inn 2F",
    123: "Library 1F",
    124: "Library 2F",
}

# Tabla de permisos de movimiento (behaviour_data_ptr)
# Valores estándar GBA — confirmados en BlueSpider
MOVEMENT_LABEL  = {
    0x00: "0", # Libre
    0x01: "1", # Bloqueado
    0x02: "1", # Bloqueado (NPC?)
    0x04: "~", # Agua
    0x08: "^", # Salto/Borde
    0x10: "S", # Silla/Sentarse
    0x20: "M", # Mostrador
    0x40: "H", # Hierba/Cultivo
}
MOVEMENT_LABELS = MOVEMENT_LABEL
MOVEMENT_BLOCKED = {0x01, 0x02, 0x20}


# ═══════════════════════════════════════════════════════════════════
#  DESCOMPRESOR LZ77 (estándar GBA, header 0x10)
# ═══════════════════════════════════════════════════════════════════
def decompress_lz77(data: bytes, offset: int = 0) -> bytes:
    """
    Descompresor LZ77 estándar de GBA.
    Header: 1 byte tipo (0x10) + 3 bytes tamaño decomprimido (LE 24-bit).
    """
    if offset >= len(data):
        return b''
    header = data[offset]
    if header != 0x10:
        raise ValueError(f"LZ77: header inválido 0x{header:02X} en 0x{offset:06X}")
    
    decomp_size = struct.unpack_from('<I', data, offset)[0] >> 8
    out = bytearray(decomp_size)
    out_pos = 0
    in_pos = offset + 4

    while out_pos < decomp_size and in_pos < len(data):
        flags = data[in_pos]; in_pos += 1
        for bit in range(7, -1, -1):
            if out_pos >= decomp_size:
                break
            if (flags >> bit) & 1:
                # Referencia hacia atrás
                b0 = data[in_pos]; b1 = data[in_pos+1]; in_pos += 2
                length = ((b0 >> 4) & 0xF) + 3
                disp   = (((b0 & 0xF) << 8) | b1) + 1
                src = out_pos - disp
                for _ in range(length):
                    if out_pos >= decomp_size: break
                    out[out_pos] = out[src % len(out)]
                    out_pos += 1; src += 1
            else:
                out[out_pos] = data[in_pos]; in_pos += 1; out_pos += 1
    return bytes(out)


def decompress_popuri(data: bytes, offset: int = 0) -> bytes:
    """
    Descompresor Popuri RLE (header 0x70) — usado en FoMT para mapas.
    """
    if offset >= len(data):
        return b''
    header = data[offset]
    if header != 0x70:
        raise ValueError(f"Popuri: header inválido 0x{header:02X} en 0x{offset:06X}")
    
    decomp_size = struct.unpack_from('<I', data, offset)[0] >> 8
    out = bytearray(decomp_size)
    out_pos = 0
    in_pos = offset + 4

    while out_pos < decomp_size and in_pos < len(data):
        b = data[in_pos]; in_pos += 1
        if b & 0x80:
            # RLE: repite (b & 0x7F)+1 veces el siguiente byte
            count = (b & 0x7F) + 1
            val = data[in_pos]; in_pos += 1
            for _ in range(count):
                if out_pos < decomp_size:
                    out[out_pos] = val; out_pos += 1
        else:
            # Literal: copia los siguientes b+1 bytes
            count = b + 1
            for _ in range(count):
                if out_pos < decomp_size and in_pos < len(data):
                    out[out_pos] = data[in_pos]; out_pos += 1; in_pos += 1
    return bytes(out)


def decompress_auto(data: bytes, offset: int) -> bytes:
    """Detecta automáticamente LZ77 o Popuri y descomprime."""
    if offset >= len(data):
        return b''
    header = data[offset]
    if header == 0x10:
        return decompress_lz77(data, offset)
    elif header == 0x70:
        return decompress_popuri(data, offset)
    elif header == 0x00:
        # Sin compresión — datos crudos (rare pero válido en FoMT)
        if offset + 4 > len(data): return b""
        size = struct.unpack_from('<I', data, offset)[0] >> 8
        if offset + 4 + size > len(data): size = len(data) - (offset + 4)
        return data[offset+4:offset+4+size]
    else:
        raise ValueError(f"Formato desconocido 0x{header:02X} en 0x{offset:06X}")


# ═══════════════════════════════════════════════════════════════════
#  PALETA GBA (16 colores × 2 bytes cada uno, formato BGR555)
# ═══════════════════════════════════════════════════════════════════
class GBAPalette:
    """
    Paleta de 16 colores en formato BGR555.
    Compatible con MapData.get_palettes de BlueSpider.
    """
    def __init__(self, raw: bytes):
        self.colors: List[Tuple[int,int,int,int]] = []  # RGBA
        for i in range(min(16, len(raw)//2)):
            bgr = struct.unpack_from('<H', raw, i*2)[0]
            r = ((bgr >> 0)  & 0x1F) << 3
            g = ((bgr >> 5)  & 0x1F) << 3
            b = ((bgr >> 10) & 0x1F) << 3
            alpha = 0 if i == 0 else 255  # color 0 = transparente
            self.colors.append((r, g, b, alpha))

    def get(self, idx: int) -> Tuple[int,int,int,int]:
        if 0 <= idx < len(self.colors):
            return self.colors[idx]
        return (0, 0, 0, 0)


# ═══════════════════════════════════════════════════════════════════
#  TILE GBA (8×8 píxeles, 4bpp)
# ═══════════════════════════════════════════════════════════════════
class GBATile:
    """Un tile de 8×8 en formato 4bpp (32 bytes)."""
    BYTES = TILE_BYTES_4BPP  # 32

    def __init__(self, raw: bytes):
        # Asegurar que tenemos al menos 32 bytes, rellenando con ceros si es necesario
        if len(raw) < self.BYTES:
            self._data = raw.ljust(self.BYTES, b'\x00')
        else:
            self._data = raw[:self.BYTES]

    def get_pixel(self, x: int, y: int) -> int:
        """Retorna el índice de color (0-15) del píxel en (x, y)."""
        idx = y * 4 + x // 2
        byte = self._data[idx]
        return (byte >> 4) if (x & 1) else (byte & 0xF)

    def render(self, palette: GBAPalette,
               h_flip: bool = False,
               v_flip: bool = False) -> Image.Image:
        """Renderiza el tile como imagen RGBA de 8×8."""
        img = Image.new('RGBA', (TILE_W, TILE_H))
        px = img.load()
        for y in range(TILE_H):
            for x in range(TILE_W):
                sy = (TILE_H-1-y) if v_flip else y
                sx = (TILE_W-1-x) if h_flip else x
                color_idx = self.get_pixel(sx, sy)
                px[x, y] = palette.get(color_idx)
        return img


# ═══════════════════════════════════════════════════════════════════
#  SUBTILE y BLOQUE (BlueSpider BlocksData algorithm)
# ═══════════════════════════════════════════════════════════════════
class SubTile:
    """
    2 bytes que describen un sub-tile dentro de un bloque 16×16.
    Algoritmo extraído directamente del código comentado en mapdata.pyd:
      uint16 LE:
        bits 0-9:  tile_index en el tileset
        bit 10:    H-flip (x flip)
        bit 11:    V-flip (y flip)
        bits 12-15: palette_index (0-15)
    """
    def __init__(self, raw2: bytes):
        val = struct.unpack_from('<H', raw2)[0]
        self.tile_idx    = val & 0x3FF          # bits 0-9
        self.h_flip      = bool((val >> 10) & 1) # bit 10
        self.v_flip      = bool((val >> 11) & 1) # bit 11
        self.palette_idx = (val >> 12) & 0xF    # bits 12-15


class Block:
    """
    Bloque de mapa de 16×16 píxeles.
    16 bytes total:
      bytes  0-7:  4 sub-tiles de la capa BAJA  (suelo)
      bytes 8-15:  4 sub-tiles de la capa ALTA  (decoración/objetos)
    """
    BYTES = BLOCK_BYTES  # 16

    def __init__(self, raw: bytes):
        assert len(raw) >= self.BYTES
        self.lower = [SubTile(raw[i*2:i*2+2]) for i in range(4)]
        self.upper = [SubTile(raw[8+i*2:8+i*2+2] ) for i in range(4)]

    def draw(self, tiles: List[GBATile],
             palettes: List[GBAPalette],
             layer: int = 0) -> Image.Image:
        """
        Dibuja el bloque en la capa especificada (0=baja, 1=alta).
        Retorna imagen RGBA de 16×16.
        """
        img = Image.new('RGBA', (BLOCK_W, BLOCK_H), (0,0,0,0))
        subtiles = self.lower if layer == 0 else self.upper
        for i, st in enumerate(subtiles):
            ox, oy = SUBTILE_POSITIONS[i]
            if st.tile_idx >= len(tiles):
                continue
            pal = palettes[st.palette_idx] if st.palette_idx < len(palettes) else palettes[0]
            tile_img = tiles[st.tile_idx].render(pal, st.h_flip, st.v_flip)
            img.paste(tile_img, (ox, oy))
        return img


# ═══════════════════════════════════════════════════════════════════
#  WARP y SCRIPT TRIGGERS
# ═══════════════════════════════════════════════════════════════════
class Warp:
    """
    Punto de teletransporte o Losa (Trigger). Estructura de 8 bytes:
    [X:1][Y:1][ScriptID:2][Metadata:4]
    """
    STRIDE = 8
    def __init__(self, data: bytes, warp_id: int, rom_offset: int = 0):
        self.id = warp_id
        self.rom_offset = rom_offset
        if len(data) >= 8:
            self.x          = data[0]
            self.y          = data[1]
            self.script_id  = struct.unpack_from('<H', data, 2)[0]
            self.metadata   = data[4:8]
        else:
            self.x = self.y = self.script_id = 0
            self.metadata = b'\x00\x00\x00\x00'

    def to_bytes(self) -> bytes:
        return struct.pack('<BBH', self.x, self.y, self.script_id) + self.metadata

    def get_label(self) -> str:
        # En FoMT un Warp dispara un Script (que a su vez hace Warp_Player)
        return f"Script_0x{self.script_id:04X}"

    def __repr__(self):
        return f"Warp#{self.id}({self.x},{self.y})→{self.get_label()}"


class ScriptTrigger:
    """
    Trigger de Interacción en el mapa (Carteles, NPCs).
    Estructura de 8 bytes:
      [X:1][Y:1][ScriptID:2][Metadata:4]
    """
    STRIDE = 8

    def __init__(self, data: bytes, tid: int, rom_offset: int = 0):
        self.id = tid
        self.rom_offset = rom_offset
        if len(data) >= 8:
            self.x         = data[0]
            self.y         = data[1]
            self.script_id = struct.unpack_from('<H', data, 2)[0]
            self.metadata  = data[4:8]
        else:
            self.x = self.y = self.script_id = 0
            self.metadata = b'\x00\x00\x00\x00'

    def to_bytes(self) -> bytes:
        return struct.pack('<BBH', self.x, self.y, self.script_id) + self.metadata

    def __repr__(self):
        return f"Script#{self.id}({self.x},{self.y}) → 0x{self.script_id:04X}"


# ═══════════════════════════════════════════════════════════════════
#  CABECERA DE MAPA (parse_map_header — BlueSpider)
# ═══════════════════════════════════════════════════════════════════
class MapHeader:
    """
    Estructura de 24 bytes — parse_map_header de BlueSpider.
    """
    STRIDE = 24

    def __init__(self, map_id: int, offset: int, data: bytes):
        self.map_id     = map_id
        self.offset     = offset
        self.p_layout   = struct.unpack_from('<I', data, 0)[0]
        self.p_tileset  = struct.unpack_from('<I', data, 4)[0]
        self.p_objects  = struct.unpack_from('<I', data, 8)[0]
        self.p_script   = struct.unpack_from('<I', data, 12)[0]
        self.width      = data[16]
        self.height     = data[17]
        self.tileset_id = data[18]
        self.name_id    = data[19]

        # Datos cargados con load_data()
        self.tiles      : List[GBATile]       = []
        self.palettes   : List[GBAPalette]    = []
        self.blocks     : List[Block]         = []
        self.collision  : Optional[bytes]     = None
        self.tilemap_lo : Optional[bytes]     = None  # BG1 lower layer
        self.tilemap_hi : Optional[bytes]     = None  # BG2 upper layer
        self.warps      : List[Warp]          = []
        self.scripts    : List[ScriptTrigger] = []
        self._loaded    = False

    @property
    def layout_offset(self) -> int:  return self.p_layout  & 0x01FFFFFF
    @property
    def tileset_offset(self) -> int: return self.p_tileset & 0x01FFFFFF
    @property
    def objects_offset(self) -> int: return self.p_objects & 0x01FFFFFF
    @property
    def script_offset(self) -> int:  return self.p_script  & 0x01FFFFFF

    def get_name(self) -> str:
        return FOMT_MAP_LABELS.get(self.map_id, f"Map {self.map_id:03d}")

    # ── Carga completa de assets (MapData.load en BlueSpider) ────────
    def load_data(self, rom: bytes) -> bool:
        """
        Carga paletas, tiles, bloques, colisiones, tilemap y eventos.
        Equivale a MapData.load() + BlocksData.load() de BlueSpider.
        """
        try:
            self._load_tileset(rom)
            self._load_tilemap(rom)
            self._load_objects(rom)
            self._loaded = True
            return True
        except Exception as e:
            print(f"[MapHeader] Map {self.map_id} load error: {e}")
            return False

    def _load_tileset(self, rom: bytes):
        """
        Lee el header del tileset (16 bytes) y carga:
          pals_ptr    → paletas BGR555
          img_data_ptr → GFX de tiles (LZ77)
          block_data_ptr → datos de bloques (16 bytes c/u)
          behaviour_data_ptr → datos de colisión (1 byte / tile)
        """
        if not self.tileset_offset:
            return
        # Header del tileset: 4 punteros × 4 bytes = 16 bytes
        hdr = rom[self.tileset_offset: self.tileset_offset + 16]
        if len(hdr) < 16:
            return

        pals_ptr        = struct.unpack_from('<I', hdr, 0)[0] & 0x01FFFFFF
        img_data_ptr    = struct.unpack_from('<I', hdr, 4)[0] & 0x01FFFFFF
        block_data_ptr  = struct.unpack_from('<I', hdr, 8)[0] & 0x01FFFFFF
        behav_data_ptr  = struct.unpack_from('<I', hdr, 12)[0] & 0x01FFFFFF

        # 1. Paletas (num_of_pals paletas, cada una 32 bytes = 16 colores × 2 bytes)
        self.palettes = []
        if pals_ptr:
            raw_pal = rom[pals_ptr: pals_ptr + 32 * 16]  # hasta 16 paletas
            for i in range(16):
                chunk = raw_pal[i*32 : i*32+32]
                if len(chunk) < 32:
                    break
                self.palettes.append(GBAPalette(chunk))

        # 2. Tiles GFX (LZ77 comprimido)
        self.tiles = []
        
        # Tiles 0-639 vienen del Tileset Global (Map 0)
        # Tiles 640+ vienen del Tileset Local
        base_tiles_ptr = 0x836800
        if len(rom) > base_tiles_ptr and rom[base_tiles_ptr] == 0x10:
            raw_base = decompress_lz77(rom, base_tiles_ptr)
            n_base = len(raw_base) // GBATile.BYTES
            for i in range(n_base):
                self.tiles.append(GBATile(raw_base[i*GBATile.BYTES : (i+1)*GBATile.BYTES]))

        if img_data_ptr and rom[img_data_ptr] == 0x10:
            raw_tiles = decompress_lz77(rom, img_data_ptr)
            n_tiles = len(raw_tiles) // GBATile.BYTES
            # Si ya cargamos base, los locales empiezan después (offset 640 aprox)
            # Para simplificar, los añadimos al final. El motor GBA maneja el offset.
            for i in range(n_tiles):
                self.tiles.append(GBATile(raw_tiles[i*GBATile.BYTES : (i+1)*GBATile.BYTES]))

        # 3. Bloques (block_data_ptr: datos crudos, 16 bytes cada uno)
        self.blocks = []
        if block_data_ptr:
            # Los bloques son datos crudos (no comprimidos)
            # Heurística: leer hasta encontrar un bloque vacío o llegar a un límite
            i = block_data_ptr
            max_blocks = 1024 # Aumentado de 512
            for _ in range(max_blocks):
                if i + Block.BYTES > len(rom):
                    break
                raw_block = rom[i:i+Block.BYTES]
                # Si encontramos 8 bloques seguidos de solo ceros, probablemente terminó la tabla
                # Pero en FoMT el bloque 0 es legítimamente transparente.
                self.blocks.append(Block(raw_block))
                i += Block.BYTES

        # 4. Colisiones (behaviour_data_ptr: 1 byte por tile del mapa)
        self.collision = None
        if behav_data_ptr:
            col_size = self.width * self.height
            if col_size > 0 and behav_data_ptr + col_size <= len(rom):
                self.collision = rom[behav_data_ptr: behav_data_ptr + col_size]

    def _load_tilemap(self, rom: bytes):
        """
        Descomprime el layout del mapa (tilemap_bg1 + tilemap_bg2).
        BlueSpider guarda ambas capas concatenadas bajo el mismo puntero.
        Cada entrada del tilemap es un uint16 LE = índice de bloque.
        """
        if not self.layout_offset or self.layout_offset >= len(rom):
            return
        header_byte = rom[self.layout_offset]
        if header_byte not in (0x10, 0x70, 0x00):
            return

        raw = decompress_auto(rom, self.layout_offset)
        if not raw: return
        n_tiles = self.width * self.height
        # Cada índice = 2 bytes → total = n_tiles * 2 para c/capa
        lo_size = n_tiles * 2
        self.tilemap_lo = raw[:lo_size]
        self.tilemap_hi = raw[lo_size:lo_size+lo_size] if len(raw) >= lo_size*2 else None

    def _load_objects(self, rom: bytes):
        """
        Parsea la tabla de objetos (warps + scripts) usando el nuevo protocolo.
        El bloque puede estar comprimido con Popuri (0x70).
        """
        self.warps   = []
        self.scripts = []
        if not self.objects_offset or self.objects_offset >= len(rom):
            return
            
        header_byte = rom[self.objects_offset]
        if header_byte == 0x70:
            data = decompress_auto(rom, self.objects_offset)
        elif header_byte == 0x10:
            data = decompress_auto(rom, self.objects_offset)
        else:
            # Si no está comprimido, asumimos un bloque de tamaño fijo o leemos hasta llenar un buffer
            data = rom[self.objects_offset : self.objects_offset + 1024]
            
        if not data or len(data) < 4:
            return

        n_warps   = data[0]
        n_scripts = data[1]
        base = 4

        for i in range(n_warps):
            off = base + i * Warp.STRIDE
            if off + Warp.STRIDE > len(data):
                break
            self.warps.append(Warp(data[off:off+Warp.STRIDE], i, self.objects_offset))
        base += n_warps * Warp.STRIDE

        for i in range(n_scripts):
            off = base + i * ScriptTrigger.STRIDE
            if off + ScriptTrigger.STRIDE > len(data):
                break
            self.scripts.append(ScriptTrigger(data[off:off+ScriptTrigger.STRIDE], i, self.objects_offset))

    # ── Warp CRUD ────────────────────────────────────────────────────
    def add_warp(self, x, y, target_map, tx, ty, face=0) -> Warp:
        raw = struct.pack('<HHBBBB', x, y, target_map, tx, ty, face)
        w = Warp(raw, len(self.warps))
        self.warps.append(w)
        return w

    def remove_warp(self, warp_id: int):
        self.warps = [w for w in self.warps if w.id != warp_id]
        for i, w in enumerate(self.warps):
            w.id = i

    def save_warps_to_rom(self, project) -> bool:
        if not self.objects_offset:
            return False
        try:
            buf = bytearray()
            buf += bytes([len(self.warps), len(self.scripts), 0, 0])
            for w in self.warps:
                buf += w.to_bytes()
            for s in self.scripts:
                buf += s.to_bytes()
                
            from Nucleos_de_Procesamiento.Nucleo_de_Datos.Utilidades.compression import compress_popuri
            compressed_buf = compress_popuri(bytes(buf))
            project.write_patch(self.objects_offset, compressed_buf)
            return True
        except Exception as e:
            print(f"[MapHeader] save_warps: {e}")
            return False

    def save_layout_to_rom(self, project) -> bool:
        """Comprime y guarda el layout (tilemap) de vuelta a la ROM."""
        if not self.layout_offset or self.tilemap_lo is None:
            return False
        try:
            buf = bytearray(self.tilemap_lo)
            if self.tilemap_hi:
                buf += self.tilemap_hi
            
            # En FoMT el layout suele usar Popuri (0x70) o LZ77 (0x10)
            from Nucleos_de_Procesamiento.Nucleo_de_Datos.Utilidades.compression import compress_popuri
            compressed_buf = compress_popuri(bytes(buf))
            project.write_patch(self.layout_offset, compressed_buf)
            return True
        except Exception as e:
            print(f"[MapHeader] save_layout: {e}")
            return False

    # ── Renderizado (BlocksData.draw_block_layers de BlueSpider) ────
    def render_layer(self, layer: int = 0) -> Optional[Image.Image]:
        """
        Genera la imagen completa de una capa del mapa.
        layer=0 → capa baja (suelo)
        layer=1 → capa alta (decoraciones/objetos)
        """
        if not self._loaded or not self.blocks:
            return None
        tilemap = self.tilemap_lo if layer == 0 else self.tilemap_hi
        if not tilemap:
            return None
        if not self.palettes:
            return None

        img = Image.new('RGBA', (self.width * BLOCK_W, self.height * BLOCK_H))
        n = self.width * self.height

        for i in range(n):
            if i*2+2 > len(tilemap):
                break
            block_idx = struct.unpack_from('<H', tilemap, i*2)[0] & 0x7FFF
            if block_idx >= len(self.blocks):
                continue

            blk_img = self.blocks[block_idx].draw(
                self.tiles, self.palettes, layer
            )
            tx = (i % self.width) * BLOCK_W
            ty = (i // self.width) * BLOCK_H
            img.paste(blk_img, (tx, ty), blk_img)

        return img

    def render_map(self) -> Optional[Image.Image]:
        """Renderiza el mapa completo (capa baja + capa alta compuestas)."""
        lo = self.render_layer(0)
        hi = self.render_layer(1)
        if lo is None:
            return None
        if hi is not None:
            lo.paste(hi, (0, 0), hi)
        return lo


# ═══════════════════════════════════════════════════════════════════
#  PARSER DE MAPAS (get_map_headers de BlueSpider)
# ═══════════════════════════════════════════════════════════════════
class MapParser:
    """
    Extrae la lista de mapas desde la ROM.
    Implementa el algoritmo get_map_headers de BlueSpider.
    """
    # Offsets verificados de la tabla maestra USA (@USATH confirmado)
    KNOWN_OFFSETS_USA   = [0x0E5DB0, 0x105EDC, 0x106E74, 0x11776C, 0x10FF2C, 0x10FF14]
    KNOWN_OFFSETS_EUR   = [0x127048, 0x117A00, 0x110200]
    KNOWN_OFFSETS_MFOMT = [0x0E5DB0, 0x10FF14, 0x110200]

    STRIDE = MapHeader.STRIDE

    def __init__(self, project):
        self.project = project
        self.maps: List[MapHeader] = []
        self._table_offset: Optional[int] = None

    def scan_maps(self):
        self.maps = []
        rom = self.project.base_rom_data
        if not rom:
            return

        self._table_offset = self._find_table(rom)
        if not self._table_offset:
            print("MapParser: No se encontró la tabla de mapas.")
            return

        def _parse(i):
            off = self._table_offset + i * self.STRIDE
            if off + self.STRIDE > len(rom):
                return None
            chunk = rom[off:off+self.STRIDE]
            p_layout = struct.unpack_from('<I', chunk, 0)[0]
            if not (0x08000000 <= p_layout < 0x09FFFFFF):
                return None
            return MapHeader(i, off, chunk)

        with ThreadPoolExecutor() as ex:
            results = list(ex.map(_parse, range(512)))

        for r in results:
            if r is None:
                continue
            # Intentar obtener nombre bautizado desde la SuperLibrary
            if hasattr(self.project, 'super_lib'):
                name_hint = self.project.super_lib.get_map_name_hint(r.map_id)
                # Si el nombre es genérico "[ID] Map ID", intentar buscar en el CSV cargado en map_map
                if "Map " in name_hint and r.map_id in self.project.super_lib.map_map.values():
                    # Buscar el nombre por ID
                    for name, mid in self.project.super_lib.map_map.items():
                        if mid == r.map_id:
                            name_hint = f"[{mid:03d}] {name}"
                            break
            self.maps.append(r)

        print(f"MapParser: {len(self.maps)} mapas desde 0x{self._table_offset:X}")

    def _find_table(self, rom: bytes) -> Optional[int]:
        """Busca la tabla maestra — get_map_headers de BlueSpider."""
        all_candidates = (self.KNOWN_OFFSETS_USA +
                          self.KNOWN_OFFSETS_EUR +
                          self.KNOWN_OFFSETS_MFOMT)
        for c in all_candidates:
            off = c & 0x01FFFFFF
            if off + 48 >= len(rom):
                continue
            p = struct.unpack_from('<I', rom, off)[0]
            if 0x08000000 <= p < 0x09FFFFFF:
                lo = p & 0x01FFFFFF
                if lo < len(rom) and rom[lo] in (0x10, 0x70, 0x00):
                    print(f"Map Discovery: Offset conocido 0x{off:X}")
                    return off

        # Escaneo profundo
        print("Map Discovery: Escaneo profundo...")
        best, best_n = None, 0
        for i in range(0x020000, len(rom)-100, 4):
            p = struct.unpack_from('<I', rom, i)[0]
            if not (0x08000000 <= p < 0x09FFFFFF):
                continue
            lo = p & 0x01FFFFFF
            if lo >= len(rom) or rom[lo] not in (0x10, 0x70):
                continue
            n = self._count_valid(rom, i)
            if n > best_n:
                best_n = n; best = i
                if best_n > 60:
                    break
        if best and best_n >= 20:
            print(f"Map Discovery: Mesa en 0x{best:X} ({best_n} mapas)")
            return best
        return None

    def _count_valid(self, rom: bytes, start: int) -> int:
        count = 0
        for j in range(300):
            off = start + j * self.STRIDE
            if off + 24 > len(rom):
                break
            chunk = rom[off:off+24]
            pl = struct.unpack_from('<I', chunk, 0)[0]
            pt = struct.unpack_from('<I', chunk, 4)[0]
            po = struct.unpack_from('<I', chunk, 8)[0]
            w, h = chunk[16], chunk[17]
            valid_ptrs = sum(1 for p in (pl, pt, po) if 0x08000000 <= p < 0x09FFFFFF)
            if valid_ptrs >= 2 and 1 <= w <= 160 and 1 <= h <= 160:
                count += 1
            else:
                if count > 10:
                    break
                break
        return count

    def get_map_by_id(self, map_id: int) -> Optional[MapHeader]:
        for m in self.maps:
            if m.map_id == map_id:
                return m
        return None

    def load_map_data(self, map_header: MapHeader) -> bool:
        """Carga los assets del mapa desde la ROM."""
        return map_header.load_data(self.project.base_rom_data)


# ═══════════════════════════════════════════════════════════════════
#  SPRITE ENGINE (extract_sprite_frame.pyd — FOMTSpriteData)
# ═══════════════════════════════════════════════════════════════════
# Los GBA OAM usan:
#  Attr0: bits 8-9 = Shape (0=square, 1=wide, 2=tall)
#  Attr1: bits 14-15 = Size
#  Dimensiones:
OAM_DIMS = {
    (0,0):(8,8),   (0,1):(16,16), (0,2):(32,32), (0,3):(64,64),
    (1,0):(16,8),  (1,1):(32,8),  (1,2):(32,16), (1,3):(64,32),
    (2,0):(8,16),  (2,1):(8,32),  (2,2):(16,32), (2,3):(32,64),
}

class OAMEntry:
    """Una entrada OAM de 6 bytes (3 atributos × 2 bytes)."""
    def __init__(self, data: bytes):
        a0 = struct.unpack_from('<H', data, 0)[0]
        a1 = struct.unpack_from('<H', data, 2)[0]
        a2 = struct.unpack_from('<H', data, 4)[0]
        self.y      = a0 & 0xFF
        self.shape  = (a0 >> 14) & 3
        self.x      = a1 & 0x1FF
        self.h_flip = bool((a1 >> 12) & 1)
        self.v_flip = bool((a1 >> 13) & 1)
        self.size   = (a1 >> 14) & 3
        self.tile   = a2 & 0x3FF
        self.pal    = (a2 >> 12) & 0xF
        self.w, self.h = OAM_DIMS.get((self.shape, self.size), (8, 8))
