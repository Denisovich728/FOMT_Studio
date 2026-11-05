"""
fomt_mapdata.py — Adaptador FoMT para blue-spider
=======================================================
Traduce las estructuras de datos de Harvest Moon: FoMT
al formato interno de blue-spider para renderizado.

La filosofía: blue-spider es el motor, nosotros sólo
"desviamos los cables" para que lea FoMT en lugar de Pokémon.

Pipeline:
  FoMT MapHeader  →  FomtMapData  →  BlocksData (blue-spider)
                                   →  draw_map() (blue-spider)
"""

import struct
import sys
import os
from PIL import Image

# Añadir blue-spider al path para reutilizar sus clases directamente
_BLUESPIDER_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', 'blue-spider')
_BLUESPIDER_PATH = os.path.normpath(_BLUESPIDER_PATH)
if os.path.exists(_BLUESPIDER_PATH) and _BLUESPIDER_PATH not in sys.path:
    sys.path.insert(0, _BLUESPIDER_PATH)


_decomp_cache = {}

def _decompress(rom: bytes, offset: int) -> bytes:
    """Descomprime usando el motor nativo de FoMT Studio con caché para máxima fluidez."""
    key = (id(rom), offset)
    if key in _decomp_cache:
        return _decomp_cache[key]
    try:
        from Nucleos_Positronicos.Nucleo_de_Mapas.mapas import decompress_auto
    except ImportError:
        try:
            from mapas import decompress_auto
        except ImportError:
            from .mapas import decompress_auto
    res = decompress_auto(bytes(rom), offset)
    _decomp_cache[key] = res
    return res


def _apply_delta_4bpp(data: bytes) -> bytes:
    """Filtro delta nibble aplicado por FoMT al decodificar gráficos."""
    out = bytearray(len(data))
    r5 = 0
    for i in range(0, len(data) - 1, 2):
        r2 = struct.unpack_from('<H', data, i)[0]
        r1 = r2 >> 4
        r3 = r2 >> 12
        r4 = r2 >> 8
        r1 = (r1 + r5) & 0xFFFF
        r2 = (r2 + r1) & 0xFFFF
        r3 = (r3 + r2) & 0xFFFF
        r5 = (r4 + r3) & 0xFFFF
        out_r1 = r1 & 0xF
        out_r2 = r2 & 0xF
        out_r5 = r5 & 0xF
        out_r3 = r3 & 0xF
        out_word = out_r2 | (out_r1 << 4) | (out_r5 << 8) | (out_r3 << 12)
        struct.pack_into('<H', out, i, out_word)
    return bytes(out)


def _parse_palette(pal_raw: bytes) -> list:
    """
    Convierte datos de paleta GBA (BGR555) a lista de tuplas RGB.
    Igual que blue-spider's get_pal_colors pero acepta bytes ya descomprimidos.
    Returns: lista de 16 tuplas (R, G, B) por cada paleta de 32 bytes.
    """
    palettes = []
    n_pals = len(pal_raw) // 32
    for p in range(n_pals):
        colors = []
        for c in range(16):
            word = struct.unpack_from('<H', pal_raw, p * 32 + c * 2)[0]
            r = (word & 0x1F) << 3
            g = ((word >> 5) & 0x1F) << 3
            b = ((word >> 10) & 0x1F) << 3
            colors.append((r, g, b))
        palettes.append(colors)
    return palettes


def _decode_4bpp_tileset(raw_pixels: bytes, n_tiles: int) -> list:
    """
    Convierte datos raw 4bpp en lista de índices de pixel por tile (64 índices por tile).
    Sigue exactamente la lógica de blue-spider's build_imgdata.
    Returns: lista de listas, una por tile, cada una con 64 índices de paleta.
    """
    tiles = []
    for t in range(n_tiles):
        tile_data = raw_pixels[t * 32 : (t + 1) * 32]
        indices = []
        for byte in tile_data:
            indices.append(byte & 0xF)         # pixel izquierdo
            indices.append((byte >> 4) & 0xF)  # pixel derecho
        tiles.append(indices)
    return tiles


def _render_tile(tile_indices: list, palette: list,
                 h_flip: bool = False, v_flip: bool = False) -> Image.Image:
    """Renderiza un tile 8x8 como PIL Image RGBA."""
    img = Image.new('RGBA', (8, 8))
    pixels = []
    for i, idx in enumerate(tile_indices):
        r, g, b = palette[idx]
        a = 0 if idx == 0 else 255  # color 0 = transparente
        pixels.append((r, g, b, a))
    img.putdata(pixels)
    if h_flip:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    if v_flip:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
    return img


# ─────────────────────────────────────────────────────────────────────────────
#  La clase principal: FomtMapRenderer
#  Equivalente a blue-spider's MapData + BlocksData + draw_map() combined
# ─────────────────────────────────────────────────────────────────────────────

ROM_BUILDINGS_TABLE = 0x10692C

BUILDING_ROM_ENTRIES = {
    'farmhouse': {
        'lv1': {'summer': 0, 'winter': 1, 'x': 26, 'y': 3},
        'lv2': {'summer': 2, 'winter': 3, 'x': 18, 'y': 3},
        'lv3': {'summer': 4, 'winter': 5, 'x': 10, 'y': 2},
    },
    'barn': {
        'lv1': {'summer': 6, 'winter': 7, 'x': 58, 'y': 2},
        'lv2': {'summer': 8, 'winter': 9, 'x': 58, 'y': 2},
    },
    'chicken_coop': {
        'lv1': {'summer': 10, 'winter': 11, 'x': 14, 'y': 52},
        'lv2': {'summer': 12, 'winter': 13, 'x': 14, 'y': 52},
    },
    'mailbox': {'summer': 46, 'winter': 46, 'x': 33, 'y': 20},
    'town_cottage': {'summer': 38, 'winter': 39, 'x': 60, 'y': 0},
    'beach_cottage': {'summer': 40, 'winter': 41, 'x': 23, 'y': 52},
    'mountain_cottage': {'summer': 44, 'winter': 45, 'x': 36, 'y': 2},
}

HOUSE_ROM_ENTRIES = {
    # Caja de Herramientas (Toolbox) - 4x6 tiles
    'tool_box_closed': {'entry': 12, 'desc_off': 0x106A94, 'w': 4, 'h': 6, 'name': 'Caja de Herramientas (Cerrada)'},
    'tool_box_open': {'entry': 11, 'desc_off': 0x106A7C, 'w': 4, 'h': 6, 'name': 'Caja de Herramientas (Abierta)'},
    
    # Refrigerador (Fridge) - 4x6 tiles
    'fridge_closed': {'entry': 14, 'desc_off': 0x106AC4, 'w': 4, 'h': 6, 'name': 'Refrigerador (Cerrado)'},
    'fridge_open': {'entry': 13, 'desc_off': 0x106AAC, 'w': 4, 'h': 6, 'name': 'Refrigerador (Abierto)'},
    
    # Anaquel / Estante (Shelf) - 4x7 tiles
    'shelf_closed': {'entry': 16, 'desc_off': 0x106AF4, 'w': 4, 'h': 7, 'name': 'Anaquel (Cerrado)'},
    'shelf_open': {'entry': 15, 'desc_off': 0x106ADC, 'w': 4, 'h': 7, 'name': 'Anaquel (Abierto)'},
    
    # Mesa Tocadiscos (Record Player) - 4x3 tiles
    'record_player_base': {'entry': 17, 'desc_off': 0x106B0C, 'w': 4, 'h': 3, 'name': 'Mesa Tocadiscos (Base)'},
    'record_player_discs': {'entry': 18, 'desc_off': 0x106B24, 'w': 4, 'h': 3, 'name': 'Mesa Tocadiscos (Con Discos)'},
    'record_player_active': {'entry': 19, 'desc_off': 0x106B3C, 'w': 4, 'h': 3, 'name': 'Mesa Tocadiscos (Reproduciendo)'},
    
    # Mueble de Cocina (Kitchen Counter) - 10x15 tiles
    'kitchen_counter': {'entry': 20, 'desc_off': 0x106B54, 'w': 10, 'h': 15, 'name': 'Mueble de Cocina'},
    
    # Chimenea (Fireplace) - 6x8 tiles
    'fireplace': {'entry': 21, 'desc_off': 0x106B6C, 'w': 6, 'h': 8, 'name': 'Chimenea'},
    
    # Cama Matrimonial (Double Bed) - 6x8 tiles
    'double_bed': {'entry': 22, 'desc_off': 0x106B84, 'w': 6, 'h': 8, 'name': 'Cama Matrimonial'},
    
    # Comedor / Alfombra Grande (Dining Carpet & Table) - 12x10 tiles
    'carpet_dining': {'entry': 23, 'desc_off': 0x106B9C, 'w': 12, 'h': 10, 'name': 'Comedor / Alfombra Grande'},
    
    # Extras individuales
    'table_vase': {'entry': 24, 'desc_off': 0x106BB4, 'w': 2, 'h': 3, 'name': 'Florero'},
    'mirror': {'entry': 25, 'desc_off': 0x106BCC, 'w': 3, 'h': 4, 'name': 'Espejo'},
    'clock': {'entry': 26, 'desc_off': 0x106BE4, 'w': 3, 'h': 6, 'name': 'Reloj'},
    
    # Puerta del Baño (Bathroom Door) - 3x5 tiles
    'bathroom_door_open': {'entry': 27, 'desc_off': 0x106BFC, 'w': 3, 'h': 5, 'name': 'Puerta del Baño (Abierta)'},
    'bathroom_door_closed': {'entry': 28, 'desc_off': 0x106C14, 'w': 3, 'h': 5, 'name': 'Puerta del Baño (Cerrada)'},
}

HOUSE_UTENSILS = [
    {'id': 'utensil_knife', 'name': 'Cuchillo', 'desc_off': 0x106E24, 'w': 3, 'h': 5, 'rel_x': 2, 'rel_y': 6},
    {'id': 'utensil_pan', 'name': 'Sartén', 'desc_off': 0x106E54, 'w': 3, 'h': 5, 'rel_x': 4, 'rel_y': 6},
    {'id': 'utensil_pot', 'name': 'Olla', 'desc_off': 0x106E84, 'w': 3, 'h': 5, 'rel_x': 6, 'rel_y': 6},
    {'id': 'utensil_mixer', 'name': 'Batidora', 'desc_off': 0x106EB4, 'w': 3, 'h': 5, 'rel_x': 1, 'rel_y': 9},
    {'id': 'utensil_whisk', 'name': 'Batidor', 'desc_off': 0x106EE4, 'w': 3, 'h': 5, 'rel_x': 3, 'rel_y': 9},
    {'id': 'utensil_rolling_pin', 'name': 'Rodillo', 'desc_off': 0x106F14, 'w': 3, 'h': 5, 'rel_x': 5, 'rel_y': 9},
    {'id': 'utensil_oven', 'name': 'Horno', 'desc_off': 0x106F44, 'w': 3, 'h': 5, 'rel_x': 7, 'rel_y': 9},
    {'id': 'utensil_seasoning', 'name': 'Juego de Condimentos', 'desc_off': 0x106F74, 'w': 3, 'h': 5, 'rel_x': 4, 'rel_y': 3},
]

HOUSE_MAP_DEFAULTS = {
    41: {
        'tool_box': {'type': 'tool_box_closed', 'x': 25, 'y': 15, 'name': 'Caja de Herramientas'},
        'record_player': {'type': 'record_player_base', 'x': 1, 'y': 17, 'name': 'Mesa Tocadiscos'},
        'mirror': {'type': 'mirror', 'x': 19, 'y': 6, 'name': 'Espejo'},
        'clock': {'type': 'clock', 'x': 8, 'y': 2, 'name': 'Reloj'},
    },
    42: {
        'tool_box': {'type': 'tool_box_closed', 'x': 40, 'y': 15, 'name': 'Caja de Herramientas'},
        'record_player': {'type': 'record_player_base', 'x': 16, 'y': 17, 'name': 'Mesa Tocadiscos'},
        'fridge': {'type': 'fridge_closed', 'x': 11, 'y': 3, 'name': 'Refrigerador'},
        'shelf': {'type': 'shelf_closed', 'x': 15, 'y': 2, 'name': 'Anaquel'},
        'kitchen_counter': {'type': 'kitchen_counter', 'x': 2, 'y': 1, 'name': 'Mueble de Cocina'},
        'fireplace': {'type': 'fireplace', 'x': 2, 'y': 1, 'name': 'Chimenea'},
        'carpet_dining': {'type': 'carpet_dining', 'x': 23, 'y': 10, 'name': 'Comedor'},
        'table_vase': {'type': 'table_vase', 'x': 20, 'y': 3, 'name': 'Florero'},
        'mirror': {'type': 'mirror', 'x': 34, 'y': 6, 'name': 'Espejo'},
        'clock': {'type': 'clock', 'x': 23, 'y': 2, 'name': 'Reloj'},
    },
    43: {
        'tool_box': {'type': 'tool_box_closed', 'x': 54, 'y': 15, 'name': 'Caja de Herramientas'},
        'record_player': {'type': 'record_player_active', 'x': 24, 'y': 17, 'name': 'Mesa Tocadiscos'},
        'fridge': {'type': 'fridge_closed', 'x': 19, 'y': 3, 'name': 'Refrigerador'},
        'shelf': {'type': 'shelf_closed', 'x': 23, 'y': 2, 'name': 'Anaquel'},
        'kitchen_counter': {'type': 'kitchen_counter', 'x': 10, 'y': 1, 'name': 'Mueble de Cocina'},
        'fireplace': {'type': 'fireplace', 'x': 4, 'y': 1, 'name': 'Chimenea'},
        'bathroom_door': {'type': 'bathroom_door_closed', 'x': 1, 'y': 2, 'name': 'Puerta del Baño'},
        'double_bed': {'type': 'double_bed', 'x': 52, 'y': 5, 'name': 'Cama Matrimonial'},
        'carpet_dining': {'type': 'carpet_dining', 'x': 31, 'y': 10, 'name': 'Comedor'},
        'table_vase': {'type': 'table_vase', 'x': 28, 'y': 3, 'name': 'Florero'},
        'mirror': {'type': 'mirror', 'x': 42, 'y': 6, 'name': 'Espejo'},
        'clock': {'type': 'clock', 'x': 31, 'y': 2, 'name': 'Reloj'},
    }
}
class FomtMapRenderer:
    """
    Motor de renderizado de mapas FoMT basado en la arquitectura de blue-spider.

    Uso:
        renderer = FomtMapRenderer(rom_bytes)
        renderer.load_map(map_header)
        img = renderer.render()
    """

    POSITIONS = [(0, 0), (8, 0), (0, 8), (8, 8)]  # sub-tiles dentro de un bloque

    def __init__(self, rom: bytes | bytearray):
        self.rom = bytearray(rom)
        self.tiles: list = []          # list[list[int]] — 64 índices por tile
        self.palettes_1: list = []     # list[list[(R,G,B)]]
        self.palettes_2: list = []     # list[list[(R,G,B)]]
        self.tilemap_bg3: list = []    # list[int] — raw 16-bit entries (Floor)
        self.tilemap_bg2: list = []
        self.tilemap_bg1: list = []    # Front/Overlay
        self.collision_map: bytes | None = None
        self.behavior_dict: bytes | None = None
        self.width = 0
        self.height = 0
        self._loaded = False
        self._map_header = None
        self._tile_cache = {}          # Caché acelerado de tiles renderizados
        self.dynamic_config = {
            'enabled': True,
            'farmhouse': 'lv1',        # 'none', 'lv1', 'lv2', 'lv3'
            'barn': 'lv1',             # 'none', 'lv1', 'lv2'
            'chicken_coop': 'lv1',     # 'none', 'lv1', 'lv2'
            'extras': True,            # Buzón, caseta de perro
            'field_grid': False,       # Malla canónica de cultivo 43x25 plots
            'beach_cottage': True,     # Villa de la playa (Mapas 08, 09)
            'mountain_cottage': True,  # Villa de la montaña (Mapas 14, 15)
            'town_cottage': True,      # Villa de la ciudad (Mapas 04, 05, 06, 07)
            'house': {
                'bed': 'auto',        # 'auto', 'single', 'double', 'none'
                'kitchen': 'auto',    # 'auto', 'base', 'utensils', 'none'
                'fridge': 'auto',     # 'auto', 'small', 'large', 'none'
                'shelf': 'auto',      # 'auto', 'small', 'large', 'none'
                'fireplace': True,    # True, False
                'bathroom': True,     # True, False
                'extras': True,       # Espejo, Alfombra, Mesa
            },
            'positions': {},          # Overrides: {'bed': (x, y), 'farmhouse': (x, y), ...}
        }

    def load_map(self, map_header) -> bool:
        """
        Carga un mapa desde un MapHeader de FoMT Studio.
        Equivale a blue-spider's MapData.load() + load_tilesets().
        """
        self._loaded = False
        self._map_header = map_header
        self._tile_cache.clear()
        rom = self.rom

        try:
            # 1. Paletas (p_pal1 + p_pal2)
            self._load_palettes(map_header)

            # 2. Tileset (p_gfx: 100% tiles 8x8)
            self._load_tileset(map_header)

            # 3. Tilemaps (p_bg1, p_bg2: entradas de 16-bit GBA)
            self._load_tilemaps(map_header)

            self.width = map_header.width
            self.height = map_header.height

            # 4. Collisions
            off_col = map_header.p_obj2 & 0x01FFFFFF
            if off_col and off_col < len(rom):
                size = self.width * self.height
                self.collision_map = rom[off_col : off_col + size]
            else:
                self.collision_map = None

            # 5. Behavior Dictionary (p_obj1)
            off_dict = map_header.p_obj1 & 0x01FFFFFF
            if off_dict and off_col and off_dict < off_col and off_col < len(rom):
                dict_size = off_col - off_dict
                self.behavior_dict = rom[off_dict : off_dict + dict_size]
            else:
                self.behavior_dict = None

            # 6. Mapeo dinámico de paleta por tile desde el mapa
            self._build_tile_palette_map()

            self._loaded = True
            return True

        except Exception as e:
            print(f"[FomtMapRenderer] Error cargando mapa {map_header.map_id}: {e}")
            import traceback; traceback.print_exc()
            return False

    def _load_palettes(self, mh):
        """
        Lee y decodifica las paletas desde p_pal1 y p_pal2 como bancos separados.
        """
        self.palettes_1 = []
        self.palettes_2 = []
        rom = self.rom

        off1 = mh.p_pal1 & 0x01FFFFFF
        if off1 and off1 < len(rom) and rom[off1] in (0x10, 0x70):
            try:
                pal1_raw = _decompress(rom, off1)
                self.palettes_1 = _parse_palette(pal1_raw)
            except Exception:
                pass

        off2 = mh.p_pal2 & 0x01FFFFFF
        if off2 and off2 < len(rom) and rom[off2] in (0x10, 0x70):
            try:
                pal2_raw = _decompress(rom, off2)
                self.palettes_2 = _parse_palette(pal2_raw)
            except Exception:
                pass

        # Insertar Paleta 0 (Global/Transparente) para desplazar las demás
        if len(self.palettes_1) == 15:
            self.palettes_1.insert(0, [(0, 0, 0)] * 16)
        if len(self.palettes_2) == 15:
            self.palettes_2.insert(0, [(0, 0, 0)] * 16)

        # Rellenar hasta 16 paletas mínimo
        while len(self.palettes_1) < 16:
            self.palettes_1.append([(0, 0, 0)] * 16)
        while len(self.palettes_2) < 16:
            self.palettes_2.append([(0, 0, 0)] * 16)

        # En casas (Mapas 42 y 43), inicializar la paleta 11 con la paleta de utensilios (Pal 10)
        # para que los utensilios de cocina se rendericen con sus colores auténticos y no en negro.
        if getattr(mh, 'map_id', 0) in (42, 43):
            if len(self.palettes_1) > 11 and len(self.palettes_1) > 10:
                self.palettes_1[11] = list(self.palettes_1[10])
            if len(self.palettes_2) > 11 and len(self.palettes_2) > 10:
                self.palettes_2[11] = list(self.palettes_2[10])
            
        print(f"[FomtMapRenderer] Paletas cargadas: Banco 1={len(self.palettes_1)}, Banco 2={len(self.palettes_2)}")


    def _load_tileset(self, mh):
        """
        Descomprime p_gfx. En FoMT TODO el p_gfx son tiles de 8x8 a 4bpp.
        No hay tabla de bloques de 16x16 como en Pokémon.
        """
        self.tiles = []
        rom = self.rom

        off = mh.p_gfx & 0x01FFFFFF
        if not off or off >= len(rom) or rom[off] not in (0x10, 0x70):
            print(f"[FomtMapRenderer] p_gfx inválido: 0x{off:06X}")
            return

        fmt = rom[off]
        raw_pixels = _decompress(rom, off)

        # En FoMT, el decompressor de 0x70 ya aplica el delta internamente.
        # Sólo debemos aplicarlo manualmente si el formato es 0x10 (LZ77 normal).
        if fmt == 0x10:
            raw_pixels = _apply_delta_4bpp(raw_pixels)

        n_tiles = len(raw_pixels) // 32  # 32 bytes = 8x8 px a 4bpp
        self.tiles = _decode_4bpp_tileset(raw_pixels, n_tiles)
        print(f"[FomtMapRenderer] {n_tiles} tiles de 8x8 cargados.")

    def _load_tilemaps(self, mh):
        """Descomprime p_bg1, p_bg2 y p_col y extrae los arrays de 16 bits."""
        self.tilemap_bg3 = []
        self.tilemap_bg2 = []
        self.tilemap_bg1 = []
        rom = self.rom

        for attr, tgt in [('p_bg3', self.tilemap_bg3), ('p_bg2', self.tilemap_bg2), ('p_bg1', self.tilemap_bg1)]:
            off = getattr(mh, attr, 0) & 0x01FFFFFF
            if not off or off >= len(rom) or rom[off] not in (0x10, 0x70):
                continue
            
            raw = _decompress(rom, off)
            n_cells = len(raw) // 2
            
            words = [struct.unpack_from('<H', raw, i * 2)[0] for i in range(n_cells)]
            
            # Detectar capas basura (0xAAAA, 0xFFFF, 0x5555, etc)
            if n_cells > 0:
                from collections import Counter
                c = Counter(words)
                most_common, count = c.most_common(1)[0]
                
                # Patrones conocidos de basura de GBA o capas no inicializadas
                if most_common in [0xaaaa, 0xffff, 0x5555, 0x1111, 0x9999, 0x3333, 0x8888, 0xcccc, 0x4444]:
                    if count > n_cells * 0.05: # Si este patrón domina, es casi seguro basura
                        print(f"[FomtMapRenderer] Ignorando {attr}: Detectada capa de basura (patrón {hex(most_common)})")
                        continue
                
                # Heurística para p_bg3 en casas (las famosas líneas diagonales como 0x51AA)
                if attr == 'p_bg3' and mh.attributes == 1:
                    # En la mayoría de las casas, el suelo no es plano.
                    # Reducimos la exigencia de la heurística para no borrar pisos válidos.
                    if c[1023] < n_cells * 0.1 and count > n_cells * 0.5:
                        print(f"[FomtMapRenderer] Ignorando {attr}: Detectada memoria sin inicializar en p_bg3")
                        continue

            for val in words:
                tgt.append(val)
            print(f"[FomtMapRenderer] {attr}: {n_cells} celdas (raw bytes: {len(raw)})")

    def _stamp_rom_structure(self, bg_ground, bg_overlay, bg_fore, entry_idx_or_desc, map_x, map_y, active_col=None, active_dict=None, force_ground=False):
        if not self.rom or entry_idx_or_desc is None:
            return
        if isinstance(entry_idx_or_desc, int) and entry_idx_or_desc < 100:
            desc_off = ROM_BUILDINGS_TABLE + entry_idx_or_desc * 24
        elif isinstance(entry_idx_or_desc, int):
            desc_off = entry_idx_or_desc
        else:
            return

        if desc_off + 24 > len(self.rom):
            return

        w, h = struct.unpack_from('<BB', self.rom, desc_off)
        p_bg1, p_bg2, p_bg3, p_lut, p_map = struct.unpack_from('<IIIII', self.rom, desc_off + 4)

        # 1. Capas graficas de tiles 8x8 segun orden de hardware GBA FoMT:
        # +0x04 (p_bg1): Frente/Detalles superiores -> bg_fore (array_bg1)
        # +0x08 (p_bg2): Estructura, paredes y techos -> bg_overlay (array_bg2)
        # +0x0C (p_bg3): Suelo/despeje base -> bg_ground (array_bg3)
        layers_to_stamp = [(p_bg3, bg_ground), (p_bg2, bg_ground), (p_bg1, bg_ground)] if force_ground else [(p_bg3, bg_ground), (p_bg2, bg_overlay), (p_bg1, bg_fore)]
        for ptr, tmap in layers_to_stamp:
            if ptr != 0 and tmap is not None:
                off = ptr & 0x01FFFFFF
                if off + w * h * 2 <= len(self.rom):
                    for y in range(h):
                        for x in range(w):
                            t_val = struct.unpack_from('<H', self.rom, off + (y * w + x) * 2)[0]
                            # 0x03FF y 0xFFFF corresponden a tiles transparentes en GBA FoMT
                            if t_val != 0x03FF and t_val != 0xFFFF:
                                dst_idx = (map_y + y) * self.width + (map_x + x)
                                if dst_idx < len(tmap):
                                    tmap[dst_idx] = t_val

        # 2. Malla de colision autentica de la estructura (reproduce func_08017180 / ApplyMapPatch_Blitter_080A5BD8)
        if p_lut != 0 and p_map != 0 and active_col is not None and active_dict is not None:
            lut_off = p_lut & 0x01FFFFFF
            map_off = p_map & 0x01FFFFFF
            if lut_off < len(self.rom) and map_off + w * h <= len(self.rom):
                for y in range(h):
                    for x in range(w):
                        lut_idx = self.rom[map_off + (y * w + x)]
                        attr = struct.unpack_from('<I', self.rom, lut_off + lut_idx * 4)[0]
                        if attr == 0:
                            # 0x00000000 es transitable/despejado sin trigger
                            continue
                        attr_bytes = struct.pack('<I', attr)
                        found_idx = -1
                        for di in range(len(active_dict) // 4):
                            if active_dict[di*4 : di*4+4] == attr_bytes:
                                found_idx = di
                                break
                        if found_idx == -1:
                            found_idx = len(active_dict) // 4
                            active_dict.extend(attr_bytes)
                        dst_idx = (map_y + y) * self.width + (map_x + x)
                        if dst_idx < len(active_col):
                            active_col[dst_idx] = found_idx

    def render(self, show_bg1=True, show_bg2=True, show_bg3=True, show_col=False, bank=1, invert_bg=False) -> Image.Image | None:
        """
        Renderiza el mapa completo usando mapeo directo 8x8 optimizado con caché y
        superposición opcional de estructuras dinámicas (Granja / Cabañas).
        """
        if not self._loaded:
            return None

        w, h = self.width, self.height
        palettes = self.palettes_1 if bank == 1 else self.palettes_2
        
        # Renderizado de capas de tiles 8x8 con caché instantáneo
        def draw_layer(tgt_list, base_img, is_overlay=False):
            if not tgt_list: return base_img
            for row in range(h):
                row_offset = row * w
                row_y = row * 8
                for col in range(w):
                    idx = row_offset + col
                    if idx >= len(tgt_list): continue
                    val = tgt_list[idx]
                    
                    t_idx  = val & 0x3FF
                    h_flip = bool((val >> 10) & 1)
                    v_flip = bool((val >> 11) & 1)
                    p_idx  = (val >> 12) & 0xF

                    if t_idx < len(self.tiles) and p_idx < len(palettes):
                        cache_key = (t_idx, p_idx, h_flip, v_flip, bank)
                        tile_img = self._tile_cache.get(cache_key)
                        if tile_img is None:
                            tile_img = _render_tile(self.tiles[t_idx], palettes[p_idx], h_flip, v_flip)
                            self._tile_cache[cache_key] = tile_img

                        col_x = col * 8
                        if is_overlay:
                            base_img.paste(tile_img, (col_x, row_y), tile_img)
                        else:
                            base_img.paste(tile_img, (col_x, row_y))
            return base_img
        
        # Capas de trabajo clonadas para no mutar destructivamente el mapa base en edición
        # Capas de trabajo clonadas para no mutar destructivamente el mapa base en edicion
        array_bg3 = list(self.tilemap_bg3) if self.tilemap_bg3 else []
        array_bg2 = list(self.tilemap_bg2) if self.tilemap_bg2 else []
        array_bg1 = list(self.tilemap_bg1) if self.tilemap_bg1 else []
        active_col = bytearray(self.collision_map) if self.collision_map else None
        active_dict = bytearray(self.behavior_dict) if self.behavior_dict else None

        map_id = getattr(self._map_header, 'map_id', 0) if self._map_header else 0
        is_winter = (map_id in (1, 3, 5, 7, 9, 11, 13, 15, 17) or bank == 2)
        season_key = 'winter' if is_winter else 'summer'
        dyn_cfg = getattr(self, 'dynamic_config', {})

        # Estampar estructuras dinamicas 100% nativas desde la tabla de la ROM
        # Orden: array_bg3 (suelo), array_bg2 (paredes/techo), array_bg1 (frente)
        if dyn_cfg.get('enabled', True):
            positions = dyn_cfg.get('positions', {})
            if map_id in (0, 1):
                # 1. Casa de Campo (Lv1, Lv2, Lv3)
                h_lvl = dyn_cfg.get('farmhouse', 'lv1')
                if h_lvl in BUILDING_ROM_ENTRIES['farmhouse']:
                    info = BUILDING_ROM_ENTRIES['farmhouse'][h_lvl]
                    pos_x, pos_y = positions.get('farmhouse', (info['x'], info['y']))
                    self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, info[season_key], pos_x, pos_y, active_col, active_dict)

                # 2. Granero (Lv1, Lv2)
                b_lvl = dyn_cfg.get('barn', 'lv1')
                if b_lvl in BUILDING_ROM_ENTRIES['barn']:
                    info = BUILDING_ROM_ENTRIES['barn'][b_lvl]
                    pos_x, pos_y = positions.get('barn', (info['x'], info['y']))
                    self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, info[season_key], pos_x, pos_y, active_col, active_dict)

                # 3. Gallinero (Lv1, Lv2)
                c_lvl = dyn_cfg.get('chicken_coop', 'lv1')
                if c_lvl in BUILDING_ROM_ENTRIES['chicken_coop']:
                    info = BUILDING_ROM_ENTRIES['chicken_coop'][c_lvl]
                    pos_x, pos_y = positions.get('chicken_coop', (info['x'], info['y']))
                    self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, info[season_key], pos_x, pos_y, active_col, active_dict)

                # 4. Extras de Granja (Buzon)
                if dyn_cfg.get('extras', True):
                    mb = BUILDING_ROM_ENTRIES['mailbox']
                    pos_x, pos_y = positions.get('mailbox', (mb['x'], mb['y']))
                    self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, mb[season_key], pos_x, pos_y, active_col, active_dict)

            elif map_id in (41, 42, 43):
                # Casa del Jugador (Lv1, Lv2, Lv3) - Estructuras interiores dinámicas
                defaults = HOUSE_MAP_DEFAULTS.get(map_id, {})
                house_cfg = dyn_cfg.get('house', {})

                # 1. Caja de Herramientas (Toolbox)
                tb_choice = house_cfg.get('tool_box', 'closed') # 'closed', 'open', 'none'
                if tb_choice in ('closed', 'open'):
                    tb_type = f'tool_box_{tb_choice}'
                    def_pos = defaults.get('tool_box', {'x': 25, 'y': 15})
                    tx, ty = positions.get('tool_box', (def_pos['x'], def_pos['y']))
                    self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, HOUSE_ROM_ENTRIES[tb_type]['entry'], tx, ty, active_col, active_dict)

                # 2. Mesa Tocadiscos (Record Player)
                rp_choice = house_cfg.get('record_player', 'base') # 'base', 'discs', 'active', 'none'
                if rp_choice in ('base', 'discs', 'active'):
                    rp_type = f'record_player_{rp_choice}'
                    def_pos = defaults.get('record_player', {'x': 1, 'y': 17})
                    rx, ry = positions.get('record_player', (def_pos['x'], def_pos['y']))
                    self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, HOUSE_ROM_ENTRIES[rp_type]['entry'], rx, ry, active_col, active_dict)

                # 3. Refrigerador (Mapas 42 y 43)
                if map_id in (42, 43):
                    f_choice = house_cfg.get('fridge', 'closed') # 'closed', 'open', 'none'
                    if f_choice in ('closed', 'open'):
                        f_type = f'fridge_{f_choice}'
                        def_pos = defaults.get('fridge', {'x': 11 if map_id == 42 else 19, 'y': 3})
                        fx, fy = positions.get('fridge', (def_pos['x'], def_pos['y']))
                        self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, HOUSE_ROM_ENTRIES[f_type]['entry'], fx, fy, active_col, active_dict)

                # 4. Anaquel / Estante (Mapas 42 y 43)
                if map_id in (42, 43):
                    s_choice = house_cfg.get('shelf', 'closed') # 'closed', 'open', 'none'
                    if s_choice in ('closed', 'open'):
                        s_type = f'shelf_{s_choice}'
                        def_pos = defaults.get('shelf', {'x': 15 if map_id == 42 else 23, 'y': 2})
                        sx, sy = positions.get('shelf', (def_pos['x'], def_pos['y']))
                        self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, HOUSE_ROM_ENTRIES[s_type]['entry'], sx, sy, active_col, active_dict)

                # 5. Mueble de Cocina (Mapas 42 y 43)
                if map_id in (42, 43) and house_cfg.get('kitchen_counter', True):
                    def_pos = defaults.get('kitchen_counter', {'x': 2 if map_id == 42 else 10, 'y': 1})
                    kx, ky = positions.get('kitchen_counter', (def_pos['x'], def_pos['y']))
                    self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, HOUSE_ROM_ENTRIES['kitchen_counter']['entry'], kx, ky, active_col, active_dict)

                    # 8 Utensilios de Cocina individuales
                    active_utensils = house_cfg.get('utensils', [True]*8)
                    for u_idx, u_info in enumerate(HOUSE_UTENSILS):
                        is_active = active_utensils[u_idx] if u_idx < len(active_utensils) else False
                        if is_active:
                            ux, uy = positions.get(u_info['id'], (kx + u_info['rel_x'], ky + u_info['rel_y']))
                            self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, u_info['desc_off'], ux, uy, active_col, active_dict)

                # 6. Chimenea (Mapas 42 y 43)
                if map_id in (42, 43) and house_cfg.get('fireplace', True):
                    def_pos = defaults.get('fireplace', {'x': 2 if map_id == 42 else 4, 'y': 1})
                    px, py = positions.get('fireplace', (def_pos['x'], def_pos['y']))
                    self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, HOUSE_ROM_ENTRIES['fireplace']['entry'], px, py, active_col, active_dict)

                # 7. Puerta del Baño (Mapa 43)
                if map_id == 43:
                    bd_choice = house_cfg.get('bathroom_door', 'closed') # 'closed', 'open', 'none'
                    if bd_choice in ('closed', 'open'):
                        bd_type = f'bathroom_door_{bd_choice}'
                        def_pos = defaults.get('bathroom_door', {'x': 1, 'y': 2})
                        dx, dy = positions.get('bathroom_door', (def_pos['x'], def_pos['y']))
                        self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, HOUSE_ROM_ENTRIES[bd_type]['entry'], dx, dy, active_col, active_dict)

                # 8. Cama Matrimonial (Mapa 43)
                if map_id == 43 and house_cfg.get('double_bed', True):
                    def_pos = defaults.get('double_bed', {'x': 52, 'y': 5})
                    bx, by = positions.get('double_bed', (def_pos['x'], def_pos['y']))
                    self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, HOUSE_ROM_ENTRIES['double_bed']['entry'], bx, by, active_col, active_dict)

                # 9. Comedor / Mesa Grande (Mapas 42 y 43)
                if map_id in (42, 43) and house_cfg.get('carpet_dining', True):
                    def_pos = defaults.get('carpet_dining', {'x': 23 if map_id == 42 else 31, 'y': 10})
                    cx, cy = positions.get('carpet_dining', (def_pos['x'], def_pos['y']))
                    # Force to floor (array_bg3) so it renders under the dining table without wiping it out
                    self._stamp_rom_structure(array_bg3, None, None, HOUSE_ROM_ENTRIES['carpet_dining']['entry'], cx, cy, active_col, active_dict, force_ground=True)

                # 10. Florero (Mapas 42 y 43)
                if map_id in (42, 43) and house_cfg.get('table_vase', True) and 'table_vase' in defaults:
                    def_pos = defaults['table_vase']
                    vx, vy = positions.get('table_vase', (def_pos['x'], def_pos['y']))
                    self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, HOUSE_ROM_ENTRIES['table_vase']['entry'], vx, vy, active_col, active_dict)

                # 11. Espejo (Mapas 41, 42, 43)
                if house_cfg.get('mirror', True) and 'mirror' in defaults:
                    def_pos = defaults['mirror']
                    mx, my = positions.get('mirror', (def_pos['x'], def_pos['y']))
                    self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, HOUSE_ROM_ENTRIES['mirror']['entry'], mx, my, active_col, active_dict)

                # 12. Reloj (Mapas 41, 42, 43)
                if house_cfg.get('clock', True) and 'clock' in defaults:
                    def_pos = defaults['clock']
                    cx, cy = positions.get('clock', (def_pos['x'], def_pos['y']))
                    self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, HOUSE_ROM_ENTRIES['clock']['entry'], cx, cy, active_col, active_dict)

            elif map_id in (8, 9) and dyn_cfg.get('beach_cottage', True):
                # Villa de la Playa
                bc = BUILDING_ROM_ENTRIES['beach_cottage']
                pos_x, pos_y = positions.get('beach_cottage', (bc['x'], bc['y']))
                self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, bc[season_key], pos_x, pos_y, active_col, active_dict)

            elif map_id in (14, 15) and dyn_cfg.get('mountain_cottage', True):
                # Villa de la Montana
                mc = BUILDING_ROM_ENTRIES['mountain_cottage']
                pos_x, pos_y = positions.get('mountain_cottage', (mc['x'], mc['y']))
                self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, mc[season_key], pos_x, pos_y, active_col, active_dict)

            elif map_id in (4, 5, 6, 7) and dyn_cfg.get('town_cottage', True):
                # Villa de la Ciudad
                tc = BUILDING_ROM_ENTRIES['town_cottage']
                pos_x, pos_y = positions.get('town_cottage', (tc['x'], tc['y']))
                self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, tc[season_key], pos_x, pos_y, active_col, active_dict)

        self.active_collision_map = bytes(active_col) if active_col else None
        self.active_behavior_dict = bytes(active_dict) if active_dict else None

        img = Image.new('RGBA', (w * 8, h * 8), (0, 0, 0, 0))

        # Determinar orden de capas
        array_bottom = array_bg3
        array_top = array_bg1
        show_bottom = show_bg3
        show_top = show_bg1

        if invert_bg:
            array_bottom = array_bg1
            array_top = array_bg3
            show_bottom = show_bg1
            show_top = show_bg3

        # Capa inferior (Normalmente BG3, el piso/terreno base)
        if show_bottom and array_bottom:
            img = draw_layer(array_bottom, img, is_overlay=False)

        # Capa intermedia (Normalmente BG2, estructuras, techos, caminos, objetos)
        if show_bg2 and array_bg2:
            img = draw_layer(array_bg2, img, is_overlay=True)

        # Capa superior (Normalmente BG1, paredes altas, copas de arboles, superposiciones)
        if show_top and array_top:
            img = draw_layer(array_top, img, is_overlay=True)

        # Malla visual de cultivo (Canonico FoMT: 43x25 plots de 16x16 px = 2x2 tiles, X=272, Y=176)
        if dyn_cfg.get('enabled', True) and map_id in (0, 1) and dyn_cfg.get('field_grid', False):
            from PIL import ImageDraw
            grid_overlay = Image.new('RGBA', (w * 8, h * 8), (0, 0, 0, 0))
            gdraw = ImageDraw.Draw(grid_overlay)
            for row in range(25):
                for col in range(43):
                    px = 272 + col * 16
                    py = 176 + row * 16
                    gdraw.rectangle([px, py, px + 15, py + 15], outline=(255, 215, 0, 110), width=1)
            img.paste(grid_overlay, (0, 0), grid_overlay)

        # Capa de Colisiones / Triggers autentica (renderizado pixel-perfect sin inventar figuras)
        if show_col and active_col:
            from PIL import ImageDraw
            overlay = Image.new('RGBA', (w * 8, h * 8), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            for row in range(h):
                for col in range(w):
                    idx = row * w + col
                    if idx >= len(active_col):
                        break
                    val = active_col[idx]

                    if active_dict and val * 4 + 3 < len(active_dict):
                        behavior = struct.unpack_from('<H', active_dict, val * 4)[0]
                        script_id = struct.unpack_from('<H', active_dict, val * 4 + 2)[0]
                    else:
                        behavior = 0
                        script_id = 0

                    is_solid = bool(behavior & 1)
                    has_script = (script_id > 0)

                    if val == 0:
                        r, g, b, a = 255, 255, 255, 0
                    elif val == 0x40:
                        # Terreno cultivable
                        r, g, b, a = 218, 165, 32, 80
                    elif is_solid and has_script:
                        r, g, b, a = 255, 215, 0, 120
                    elif is_solid:
                        r, g, b, a = 255, 0, 0, 100
                    elif has_script:
                        r, g, b, a = 0, 255, 0, 100
                    else:
                        r, g, b, a = 0, 150, 255, 90

                    if a > 0:
                        draw.rectangle([col*8, row*8, col*8+7, row*8+7], fill=(r, g, b, a), outline=(r, g, b, 200))

            img.paste(overlay, (0, 0), overlay)

        return img

    def get_effective_collision(self) -> tuple[bytes | None, bytes | None]:
        """Devuelve (collision_map, behavior_dict) con las estructuras dinamicas estampadas."""
        if hasattr(self, 'active_collision_map') and self.active_collision_map:
            return self.active_collision_map, self.active_behavior_dict
        return self.collision_map, self.behavior_dict

    def _build_tile_palette_map(self):
        """
        Determina qué paleta le corresponde a cada tile según su uso en el mapa.
        Prioridad: tilemap_bg3 (suelo/terreno principal), luego bg2, luego bg1.
        """
        from collections import Counter
        tile_pal_counts = {}
        total_pals = Counter()

        for layer in [self.tilemap_bg3, self.tilemap_bg2, self.tilemap_bg1]:
            if not layer:
                continue
            for val in layer:
                t = val & 0x3FF
                p = (val >> 12) & 0xF
                if t != 0x3FF and p > 0:
                    if t not in tile_pal_counts:
                        tile_pal_counts[t] = Counter()
                    tile_pal_counts[t][p] += 1
                    total_pals[p] += 1

        self.dominant_palette = total_pals.most_common(1)[0][0] if total_pals else 1
        self.tile_palette_map = {t: c.most_common(1)[0][0] for t, c in tile_pal_counts.items()}

    def get_tile_palette(self, tile_idx: int) -> int:
        """Retorna la paleta activa en el mapa para un tile dado, o la paleta dominante."""
        if hasattr(self, 'tile_palette_map') and tile_idx in self.tile_palette_map:
            return self.tile_palette_map[tile_idx]
        return getattr(self, 'dominant_palette', 1)

    def render_tileset(self, pal_idx: int | None = None, bank: int = 1) -> Image.Image | None:
        """
        Genera una imagen con todos los tiles de 8x8.
        Si pal_idx es None o pal_idx == 0:
            Modo Auto: Cada tile se dibuja con la paleta activa que le manda el mapa.
        Si pal_idx > 0:
            Fuerza esa paleta específica para todos los tiles del tileset.
        """
        if not self._loaded or not self.tiles:
            return None
        palettes = self.palettes_1 if bank == 1 else self.palettes_2
        if not palettes:
            return None

        cols = 32
        rows = (len(self.tiles) + cols - 1) // cols
        img = Image.new('RGB', (cols * 8, rows * 8), (0, 0, 0))

        use_auto = (pal_idx is None or pal_idx == 0)

        for i, tile_data in enumerate(self.tiles):
            c = i % cols
            r = i // cols
            if use_auto:
                p = self.get_tile_palette(i)
            else:
                p = pal_idx

            if p >= len(palettes):
                p = getattr(self, 'dominant_palette', 1)

            tile_img = _render_tile(tile_data, palettes[p], False, False)
            img.paste(tile_img.convert('RGB'), (c * 8, r * 8))

        return img

    def get_cell_val_at(self, layer: int, col: int, row: int) -> int:
        """Retorna el valor crudo GBA (16 bits) de la celda."""
        tgt = self.tilemap_bg3 if layer == 3 else self.tilemap_bg2 if layer == 2 else self.tilemap_bg1
        idx = row * self.width + col
        if 0 <= idx < len(tgt):
            return tgt[idx]
        return 0

    def set_cell_val_at(self, layer: int, col: int, row: int, val: int):
        tgt = self.tilemap_bg3 if layer == 3 else self.tilemap_bg2 if layer == 2 else self.tilemap_bg1
        idx = row * self.width + col
        if 0 <= idx < len(tgt):
            tgt[idx] = val & 0xFFFF
    def get_trigger(self, x: int, y: int, val: int) -> tuple[int, int, int] | None:
        """
        Devuelve (flags, script_id, rom_addr_of_script_id) para la celda dada.
        Maneja tanto comportamientos inmediatos como listas de eventos basadas en coordenadas.
        """
        if val == 0 or not self._map_header: return None
        
        off_obj1 = self._map_header.p_obj1 & 0x01FFFFFF
        header_word_addr = off_obj1 + val * 4
        if header_word_addr + 4 > len(self.rom): return None
        
        word = struct.unpack_from('<I', self.rom, header_word_addr)[0]
        
        if word > 0x00010000:
            # Comportamiento inmediato (Ej: 0x01340001 -> flags=1, script=0x0134)
            flags = word & 0xFFFF
            script = (word >> 16) & 0xFFFF
            return (flags, script, header_word_addr + 2)
        else:
            # Es un offset a un array de eventos (Ej: Warps o Scripts posicionales)
            if word == 0: return None
            array_addr = off_obj1 + word
            
            # Buscar heurísticamente en el array por la coordenada (X, Y)
            for i in range(0, 512, 4):
                if array_addr + i + 4 > len(self.rom): break
                bx = self.rom[array_addr + i]
                by = self.rom[array_addr + i + 1]
                if bx == x and by == y:
                    script = struct.unpack_from('<H', self.rom, array_addr + i + 2)[0]
                    return (0, script, array_addr + i + 2)
            
            return None

    def set_trigger(self, val: int, addr: int, new_flags: int, new_script: int):
        """
        Guarda el script modificado en la ROM.
        Si es un comportamiento inmediato, guarda también los flags.
        """
        if not self._map_header: return
        
        # Si la dirección apunta directamente al script, la guardamos
        struct.pack_into('<H', self.rom, addr, new_script)
        
        # Comprobamos si era un comportamiento inmediato (addr coincide con header_word_addr + 2)
        off_obj1 = self._map_header.p_obj1 & 0x01FFFFFF
        header_word_addr = off_obj1 + val * 4
        if addr == header_word_addr + 2:
            struct.pack_into('<H', self.rom, header_word_addr, new_flags)

    def get_active_dynamic_structures(self) -> list:
        """
        Retorna la lista de todas las estructuras dinámicas activas en el mapa actual
        con su identificador, nombre legible, posición (x, y) en tiles y dimensiones (w, h).
        """
        map_id = getattr(self._map_header, 'map_id', 0) if self._map_header else 0
        dyn_cfg = getattr(self, 'dynamic_config', {})
        if not dyn_cfg.get('enabled', True):
            return []

        positions = dyn_cfg.get('positions', {})
        results = []

        if map_id in (0, 1):
            # Granja
            h_lvl = dyn_cfg.get('farmhouse', 'lv1')
            if h_lvl in BUILDING_ROM_ENTRIES['farmhouse']:
                info = BUILDING_ROM_ENTRIES['farmhouse'][h_lvl]
                px, py = positions.get('farmhouse', (info['x'], info['y']))
                entry = info['summer']
                w, h = self._get_structure_dimensions(entry)
                results.append({'id': 'farmhouse', 'name': f'Casa de Campo ({h_lvl.upper()})', 'x': px, 'y': py, 'w': w, 'h': h, 'entry': entry})

            b_lvl = dyn_cfg.get('barn', 'lv1')
            if b_lvl in BUILDING_ROM_ENTRIES['barn']:
                info = BUILDING_ROM_ENTRIES['barn'][b_lvl]
                px, py = positions.get('barn', (info['x'], info['y']))
                entry = info['summer']
                w, h = self._get_structure_dimensions(entry)
                results.append({'id': 'barn', 'name': f'Establo ({b_lvl.upper()})', 'x': px, 'y': py, 'w': w, 'h': h, 'entry': entry})

            c_lvl = dyn_cfg.get('chicken_coop', 'lv1')
            if c_lvl in BUILDING_ROM_ENTRIES['chicken_coop']:
                info = BUILDING_ROM_ENTRIES['chicken_coop'][c_lvl]
                px, py = positions.get('chicken_coop', (info['x'], info['y']))
                entry = info['summer']
                w, h = self._get_structure_dimensions(entry)
                results.append({'id': 'chicken_coop', 'name': f'Gallinero ({c_lvl.upper()})', 'x': px, 'y': py, 'w': w, 'h': h, 'entry': entry})

            if dyn_cfg.get('extras', True):
                mb = BUILDING_ROM_ENTRIES['mailbox']
                px, py = positions.get('mailbox', (mb['x'], mb['y']))
                entry = mb['summer']
                w, h = self._get_structure_dimensions(entry)
                results.append({'id': 'mailbox', 'name': 'Buzón / Caseta', 'x': px, 'y': py, 'w': w, 'h': h, 'entry': entry})

        elif map_id in (41, 42, 43):
            # Casa del Jugador
            defaults = HOUSE_MAP_DEFAULTS.get(map_id, {})
            house_cfg = dyn_cfg.get('house', {})

            # 1. Caja de Herramientas
            tb_choice = house_cfg.get('tool_box', 'closed')
            if tb_choice in ('closed', 'open'):
                tb_type = f'tool_box_{tb_choice}'
                def_pos = defaults.get('tool_box', {'x': 25, 'y': 15})
                tx, ty = positions.get('tool_box', (def_pos['x'], def_pos['y']))
                e_info = HOUSE_ROM_ENTRIES[tb_type]
                results.append({'id': 'tool_box', 'name': e_info['name'], 'x': tx, 'y': ty, 'w': e_info['w'], 'h': e_info['h'], 'entry': e_info['entry']})

            # 2. Mesa Tocadiscos
            rp_choice = house_cfg.get('record_player', 'base')
            if rp_choice in ('base', 'discs', 'active'):
                rp_type = f'record_player_{rp_choice}'
                def_pos = defaults.get('record_player', {'x': 1, 'y': 17})
                rx, ry = positions.get('record_player', (def_pos['x'], def_pos['y']))
                e_info = HOUSE_ROM_ENTRIES[rp_type]
                results.append({'id': 'record_player', 'name': e_info['name'], 'x': rx, 'y': ry, 'w': e_info['w'], 'h': e_info['h'], 'entry': e_info['entry']})

            # 3. Refrigerador
            if map_id in (42, 43):
                f_choice = house_cfg.get('fridge', 'closed')
                if f_choice in ('closed', 'open'):
                    f_type = f'fridge_{f_choice}'
                    def_pos = defaults.get('fridge', {'x': 11 if map_id == 42 else 19, 'y': 3})
                    fx, fy = positions.get('fridge', (def_pos['x'], def_pos['y']))
                    e_info = HOUSE_ROM_ENTRIES[f_type]
                    results.append({'id': 'fridge', 'name': e_info['name'], 'x': fx, 'y': fy, 'w': e_info['w'], 'h': e_info['h'], 'entry': e_info['entry']})

            # 4. Anaquel
            if map_id in (42, 43):
                s_choice = house_cfg.get('shelf', 'closed')
                if s_choice in ('closed', 'open'):
                    s_type = f'shelf_{s_choice}'
                    def_pos = defaults.get('shelf', {'x': 15 if map_id == 42 else 23, 'y': 2})
                    sx, sy = positions.get('shelf', (def_pos['x'], def_pos['y']))
                    e_info = HOUSE_ROM_ENTRIES[s_type]
                    results.append({'id': 'shelf', 'name': e_info['name'], 'x': sx, 'y': sy, 'w': e_info['w'], 'h': e_info['h'], 'entry': e_info['entry']})

            # 5. Mueble de Cocina y Utensilios
            if map_id in (42, 43) and house_cfg.get('kitchen_counter', True):
                def_pos = defaults.get('kitchen_counter', {'x': 2 if map_id == 42 else 10, 'y': 1})
                kx, ky = positions.get('kitchen_counter', (def_pos['x'], def_pos['y']))
                e_info = HOUSE_ROM_ENTRIES['kitchen_counter']
                results.append({'id': 'kitchen_counter', 'name': e_info['name'], 'x': kx, 'y': ky, 'w': e_info['w'], 'h': e_info['h'], 'entry': e_info['entry']})

                active_utensils = house_cfg.get('utensils', [True]*8)
                for u_idx, u_info in enumerate(HOUSE_UTENSILS):
                    if u_idx < len(active_utensils) and active_utensils[u_idx]:
                        ux, uy = positions.get(u_info['id'], (kx + u_info['rel_x'], ky + u_info['rel_y']))
                        results.append({'id': u_info['id'], 'name': f"Utensilio: {u_info['name']}", 'x': ux, 'y': uy, 'w': u_info['w'], 'h': u_info['h'], 'entry': u_info['desc_off']})

            # 6. Chimenea
            if map_id in (42, 43) and house_cfg.get('fireplace', True):
                def_pos = defaults.get('fireplace', {'x': 2 if map_id == 42 else 4, 'y': 1})
                px, py = positions.get('fireplace', (def_pos['x'], def_pos['y']))
                e_info = HOUSE_ROM_ENTRIES['fireplace']
                results.append({'id': 'fireplace', 'name': e_info['name'], 'x': px, 'y': py, 'w': e_info['w'], 'h': e_info['h'], 'entry': e_info['entry']})

            # 7. Puerta del Baño
            if map_id == 43:
                bd_choice = house_cfg.get('bathroom_door', 'closed')
                if bd_choice in ('closed', 'open'):
                    bd_type = f'bathroom_door_{bd_choice}'
                    def_pos = defaults.get('bathroom_door', {'x': 1, 'y': 2})
                    dx, dy = positions.get('bathroom_door', (def_pos['x'], def_pos['y']))
                    e_info = HOUSE_ROM_ENTRIES[bd_type]
                    results.append({'id': 'bathroom_door', 'name': e_info['name'], 'x': dx, 'y': dy, 'w': e_info['w'], 'h': e_info['h'], 'entry': e_info['entry']})

            # 8. Cama Matrimonial
            if map_id == 43 and house_cfg.get('double_bed', True):
                def_pos = defaults.get('double_bed', {'x': 52, 'y': 5})
                bx, by = positions.get('double_bed', (def_pos['x'], def_pos['y']))
                e_info = HOUSE_ROM_ENTRIES['double_bed']
                results.append({'id': 'double_bed', 'name': e_info['name'], 'x': bx, 'y': by, 'w': e_info['w'], 'h': e_info['h'], 'entry': e_info['entry']})

            # 9. Comedor / Mesa Grande
            if map_id in (42, 43) and house_cfg.get('carpet_dining', True):
                def_pos = defaults.get('carpet_dining', {'x': 23 if map_id == 42 else 31, 'y': 10})
                cx, cy = positions.get('carpet_dining', (def_pos['x'], def_pos['y']))
                e_info = HOUSE_ROM_ENTRIES['carpet_dining']
                results.append({'id': 'carpet_dining', 'name': e_info['name'], 'x': cx, 'y': cy, 'w': e_info['w'], 'h': e_info['h'], 'entry': e_info['entry']})

            # 10. Florero
            if map_id in (42, 43) and house_cfg.get('table_vase', True) and 'table_vase' in defaults:
                def_pos = defaults['table_vase']
                ex, ey = positions.get('table_vase', (def_pos['x'], def_pos['y']))
                e_info = HOUSE_ROM_ENTRIES['table_vase']
                results.append({'id': 'table_vase', 'name': e_info['name'], 'x': ex, 'y': ey, 'w': e_info['w'], 'h': e_info['h'], 'entry': e_info['entry']})

            # 11. Espejo
            if house_cfg.get('mirror', True) and 'mirror' in defaults:
                def_pos = defaults['mirror']
                ex, ey = positions.get('mirror', (def_pos['x'], def_pos['y']))
                e_info = HOUSE_ROM_ENTRIES['mirror']
                results.append({'id': 'mirror', 'name': e_info['name'], 'x': ex, 'y': ey, 'w': e_info['w'], 'h': e_info['h'], 'entry': e_info['entry']})

            # 12. Reloj
            if house_cfg.get('clock', True) and 'clock' in defaults:
                def_pos = defaults['clock']
                ex, ey = positions.get('clock', (def_pos['x'], def_pos['y']))
                e_info = HOUSE_ROM_ENTRIES['clock']
                results.append({'id': 'clock', 'name': e_info['name'], 'x': ex, 'y': ey, 'w': e_info['w'], 'h': e_info['h'], 'entry': e_info['entry']})

        return results

    def _get_structure_dimensions(self, entry_or_desc: int) -> tuple:
        if isinstance(entry_or_desc, int) and entry_or_desc < 100:
            table_offset = ROM_BUILDINGS_TABLE + (entry_or_desc * 24)
        elif isinstance(entry_or_desc, int):
            table_offset = entry_or_desc
        else:
            return (0, 0)
        if table_offset + 2 <= len(self.rom):
            w = self.rom[table_offset]
            h = self.rom[table_offset + 1]
            return (w, h)
        return (0, 0)
