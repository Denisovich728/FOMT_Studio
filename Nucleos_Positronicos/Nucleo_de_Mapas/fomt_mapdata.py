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
    'double_bed': {'entry': 14, 'w': 4, 'h': 6, 'name': 'Cama Matrimonial'},
    'single_bed': {'entry': 15, 'w': 4, 'h': 6, 'name': 'Cama Individual'},
    'large_shelf': {'entry': 16, 'w': 4, 'h': 6, 'name': 'Anaquel Grande'},
    'small_shelf': {'entry': 17, 'w': 4, 'h': 6, 'name': 'Anaquel Chico'},
    'large_fridge': {'entry': 18, 'w': 4, 'h': 7, 'name': 'Refrigerador Grande'},
    'small_fridge': {'entry': 19, 'w': 4, 'h': 7, 'name': 'Refrigerador Chico'},
    'kitchen_base': {'entry': 20, 'w': 4, 'h': 3, 'name': 'Cocina (Base)'},
    'kitchen_cabinet': {'entry': 21, 'w': 4, 'h': 3, 'name': 'Alacena Cocina'},
    'kitchen_utensils': {'entry': 22, 'w': 4, 'h': 3, 'name': 'Cocina (Utensilios)'},
    'fireplace': {'entry': 23, 'w': 10, 'h': 15, 'name': 'Chimenea'},
    'bathroom_door': {'entry': 24, 'w': 6, 'h': 8, 'name': 'Baño (Acceso)'},
    'bathroom_tub': {'entry': 25, 'w': 6, 'h': 8, 'name': 'Baño (Tina)'},
    'carpet_dining': {'entry': 26, 'w': 3, 'h': 4, 'name': 'Comedor / Alfombra'},
    'clock_mirror': {'entry': 27, 'w': 2, 'h': 3, 'name': 'Reloj / Espejo'},
    'rug_mat': {'entry': 28, 'w': 3, 'h': 4, 'name': 'Alfombra'},
    'table_vase': {'entry': 29, 'w': 3, 'h': 6, 'name': 'Mesa / Florero'},
}

HOUSE_MAP_DEFAULTS = {
    41: {
        'bed': {'type': 'single_bed', 'x': 25, 'y': 15, 'name': 'Cama Individual'},
        'kitchen': {'type': 'kitchen_base', 'x': 1, 'y': 17, 'name': 'Cocina Base'},
        'clock_mirror': {'type': 'clock_mirror', 'x': 19, 'y': 6, 'name': 'Reloj / Espejo'},
        'rug_mat': {'type': 'rug_mat', 'x': 8, 'y': 2, 'name': 'Alfombra'},
    },
    42: {
        'bed': {'type': 'single_bed', 'x': 40, 'y': 15, 'name': 'Cama Individual'},
        'fireplace': {'type': 'fireplace', 'x': 2, 'y': 1, 'name': 'Chimenea'},
        'shelf': {'type': 'small_shelf', 'x': 11, 'y': 3, 'name': 'Anaquel Chico'},
        'fridge': {'type': 'small_fridge', 'x': 15, 'y': 2, 'name': 'Refrigerador Chico'},
        'kitchen': {'type': 'kitchen_base', 'x': 16, 'y': 17, 'name': 'Cocina Base'},
        'carpet_dining': {'type': 'carpet_dining', 'x': 23, 'y': 10, 'name': 'Comedor'},
        'clock_mirror': {'type': 'clock_mirror', 'x': 34, 'y': 6, 'name': 'Reloj / Espejo'},
        'rug_mat': {'type': 'rug_mat', 'x': 23, 'y': 2, 'name': 'Alfombra'},
        'table_vase': {'type': 'table_vase', 'x': 20, 'y': 3, 'name': 'Mesa Florero'},
    },
    43: {
        'bed': {'type': 'double_bed', 'x': 54, 'y': 15, 'name': 'Cama Matrimonial'},
        'fireplace': {'type': 'fireplace', 'x': 10, 'y': 1, 'name': 'Chimenea'},
        'bathroom_door': {'type': 'bathroom_door', 'x': 4, 'y': 1, 'name': 'Baño (Puerta)'},
        'bathroom_tub': {'type': 'bathroom_tub', 'x': 52, 'y': 5, 'name': 'Baño (Tina)'},
        'shelf': {'type': 'large_shelf', 'x': 19, 'y': 3, 'name': 'Anaquel Grande'},
        'fridge': {'type': 'large_fridge', 'x': 23, 'y': 2, 'name': 'Refrigerador Grande'},
        'kitchen': {'type': 'kitchen_utensils', 'x': 24, 'y': 17, 'name': 'Cocina Completa'},
        'carpet_dining': {'type': 'carpet_dining', 'x': 31, 'y': 10, 'name': 'Comedor'},
        'clock_mirror': {'type': 'clock_mirror', 'x': 42, 'y': 6, 'name': 'Reloj / Espejo'},
        'rug_mat': {'type': 'rug_mat', 'x': 31, 'y': 2, 'name': 'Alfombra'},
        'table_vase': {'type': 'table_vase', 'x': 28, 'y': 3, 'name': 'Mesa Florero'},
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

    def _stamp_rom_structure(self, bg_ground, bg_overlay, bg_fore, entry_idx, map_x, map_y, active_col=None, active_dict=None):
        if not self.rom or entry_idx is None:
            return
        entry_off = ROM_BUILDINGS_TABLE + entry_idx * 24
        if entry_off + 24 > len(self.rom):
            return
        w, h = struct.unpack_from('<BB', self.rom, entry_off)
        p_ground, p_overlay, p_fore, p_lut, p_map = struct.unpack_from('<IIIII', self.rom, entry_off + 4)

        # 1. Capas graficas de tiles 8x8 segun orden de visualizacion de FoMT:
        # +0x04 (p_ground): Suelo/despeje base -> bg_ground (array_bg3)
        # +0x08 (p_overlay): Estructura, paredes y techos -> bg_overlay (array_bg2)
        # +0x0C (p_fore): Detalles superiores/primer plano -> bg_fore (array_bg1)
        for ptr, tmap in [(p_ground, bg_ground), (p_overlay, bg_overlay), (p_fore, bg_fore)]:
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

                # Cama (Single o Double)
                bed_choice = house_cfg.get('bed', 'auto')
                if bed_choice == 'auto':
                    bed_type = 'double_bed' if map_id == 43 else 'single_bed'
                elif bed_choice == 'double':
                    bed_type = 'double_bed'
                elif bed_choice == 'single':
                    bed_type = 'single_bed'
                else:
                    bed_type = None

                if bed_type and bed_type in HOUSE_ROM_ENTRIES:
                    def_pos = defaults.get('bed', {'x': 25, 'y': 15})
                    bx, by = positions.get('bed', (def_pos['x'], def_pos['y']))
                    self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, HOUSE_ROM_ENTRIES[bed_type]['entry'], bx, by, active_col, active_dict)

                # Cocina
                k_choice = house_cfg.get('kitchen', 'auto')
                if k_choice == 'auto':
                    k_type = 'kitchen_utensils' if map_id == 43 else 'kitchen_base'
                elif k_choice == 'utensils':
                    k_type = 'kitchen_utensils'
                elif k_choice == 'base':
                    k_type = 'kitchen_base'
                else:
                    k_type = None

                if k_type and k_type in HOUSE_ROM_ENTRIES:
                    def_pos = defaults.get('kitchen', {'x': 1, 'y': 17})
                    kx, ky = positions.get('kitchen', (def_pos['x'], def_pos['y']))
                    self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, HOUSE_ROM_ENTRIES[k_type]['entry'], kx, ky, active_col, active_dict)

                # Refrigerador (Mapas 42 y 43)
                if map_id in (42, 43):
                    f_choice = house_cfg.get('fridge', 'auto')
                    if f_choice == 'auto':
                        f_type = 'large_fridge' if map_id == 43 else 'small_fridge'
                    elif f_choice == 'large':
                        f_type = 'large_fridge'
                    elif f_choice == 'small':
                        f_type = 'small_fridge'
                    else:
                        f_type = None

                    if f_type and f_type in HOUSE_ROM_ENTRIES:
                        def_pos = defaults.get('fridge', {'x': 15, 'y': 2})
                        fx, fy = positions.get('fridge', (def_pos['x'], def_pos['y']))
                        self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, HOUSE_ROM_ENTRIES[f_type]['entry'], fx, fy, active_col, active_dict)

                # Anaquel / Estante (Mapas 42 y 43)
                if map_id in (42, 43):
                    s_choice = house_cfg.get('shelf', 'auto')
                    if s_choice == 'auto':
                        s_type = 'large_shelf' if map_id == 43 else 'small_shelf'
                    elif s_choice == 'large':
                        s_type = 'large_shelf'
                    elif s_choice == 'small':
                        s_type = 'small_shelf'
                    else:
                        s_type = None

                    if s_type and s_type in HOUSE_ROM_ENTRIES:
                        def_pos = defaults.get('shelf', {'x': 11, 'y': 3})
                        sx, sy = positions.get('shelf', (def_pos['x'], def_pos['y']))
                        self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, HOUSE_ROM_ENTRIES[s_type]['entry'], sx, sy, active_col, active_dict)

                # Chimenea (Mapas 42 y 43)
                if map_id in (42, 43) and house_cfg.get('fireplace', True):
                    def_pos = defaults.get('fireplace', {'x': 2, 'y': 1})
                    px, py = positions.get('fireplace', (def_pos['x'], def_pos['y']))
                    self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, HOUSE_ROM_ENTRIES['fireplace']['entry'], px, py, active_col, active_dict)

                # Baño (Mapa 43)
                if map_id == 43 and house_cfg.get('bathroom', True):
                    def_pos_door = defaults.get('bathroom_door', {'x': 4, 'y': 1})
                    dx, dy = positions.get('bathroom_door', (def_pos_door['x'], def_pos_door['y']))
                    self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, HOUSE_ROM_ENTRIES['bathroom_door']['entry'], dx, dy, active_col, active_dict)

                    def_pos_tub = defaults.get('bathroom_tub', {'x': 52, 'y': 5})
                    tx, ty = positions.get('bathroom_tub', (def_pos_tub['x'], def_pos_tub['y']))
                    self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, HOUSE_ROM_ENTRIES['bathroom_tub']['entry'], tx, ty, active_col, active_dict)

                # Extras decorativos (Reloj/Espejo, Alfombra, Mesa/Florero, Comedor)
                if house_cfg.get('extras', True):
                    for extra_key in ['clock_mirror', 'rug_mat', 'table_vase', 'carpet_dining']:
                        if extra_key in defaults:
                            entry_type = defaults[extra_key]['type']
                            def_pos = defaults[extra_key]
                            ex, ey = positions.get(extra_key, (def_pos['x'], def_pos['y']))
                            self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, HOUSE_ROM_ENTRIES[entry_type]['entry'], ex, ey, active_col, active_dict)

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

            bed_choice = house_cfg.get('bed', 'auto')
            bed_type = ('double_bed' if map_id == 43 else 'single_bed') if bed_choice == 'auto' else ('double_bed' if bed_choice == 'double' else ('single_bed' if bed_choice == 'single' else None))
            if bed_type and bed_type in HOUSE_ROM_ENTRIES:
                def_pos = defaults.get('bed', {'x': 25, 'y': 15})
                bx, by = positions.get('bed', (def_pos['x'], def_pos['y']))
                e_info = HOUSE_ROM_ENTRIES[bed_type]
                results.append({'id': 'bed', 'name': e_info['name'], 'x': bx, 'y': by, 'w': e_info['w'], 'h': e_info['h'], 'entry': e_info['entry']})

            k_choice = house_cfg.get('kitchen', 'auto')
            k_type = ('kitchen_utensils' if map_id == 43 else 'kitchen_base') if k_choice == 'auto' else ('kitchen_utensils' if k_choice == 'utensils' else ('kitchen_base' if k_choice == 'base' else None))
            if k_type and k_type in HOUSE_ROM_ENTRIES:
                def_pos = defaults.get('kitchen', {'x': 1, 'y': 17})
                kx, ky = positions.get('kitchen', (def_pos['x'], def_pos['y']))
                e_info = HOUSE_ROM_ENTRIES[k_type]
                results.append({'id': 'kitchen', 'name': e_info['name'], 'x': kx, 'y': ky, 'w': e_info['w'], 'h': e_info['h'], 'entry': e_info['entry']})

            if map_id in (42, 43):
                f_choice = house_cfg.get('fridge', 'auto')
                f_type = ('large_fridge' if map_id == 43 else 'small_fridge') if f_choice == 'auto' else ('large_fridge' if f_choice == 'large' else ('small_fridge' if f_choice == 'small' else None))
                if f_type and f_type in HOUSE_ROM_ENTRIES:
                    def_pos = defaults.get('fridge', {'x': 15, 'y': 2})
                    fx, fy = positions.get('fridge', (def_pos['x'], def_pos['y']))
                    e_info = HOUSE_ROM_ENTRIES[f_type]
                    results.append({'id': 'fridge', 'name': e_info['name'], 'x': fx, 'y': fy, 'w': e_info['w'], 'h': e_info['h'], 'entry': e_info['entry']})

                s_choice = house_cfg.get('shelf', 'auto')
                s_type = ('large_shelf' if map_id == 43 else 'small_shelf') if s_choice == 'auto' else ('large_shelf' if s_choice == 'large' else ('small_shelf' if s_choice == 'small' else None))
                if s_type and s_type in HOUSE_ROM_ENTRIES:
                    def_pos = defaults.get('shelf', {'x': 11, 'y': 3})
                    sx, sy = positions.get('shelf', (def_pos['x'], def_pos['y']))
                    e_info = HOUSE_ROM_ENTRIES[s_type]
                    results.append({'id': 'shelf', 'name': e_info['name'], 'x': sx, 'y': sy, 'w': e_info['w'], 'h': e_info['h'], 'entry': e_info['entry']})

                if house_cfg.get('fireplace', True):
                    def_pos = defaults.get('fireplace', {'x': 2, 'y': 1})
                    px, py = positions.get('fireplace', (def_pos['x'], def_pos['y']))
                    e_info = HOUSE_ROM_ENTRIES['fireplace']
                    results.append({'id': 'fireplace', 'name': e_info['name'], 'x': px, 'y': py, 'w': e_info['w'], 'h': e_info['h'], 'entry': e_info['entry']})

            if map_id == 43 and house_cfg.get('bathroom', True):
                def_pos_door = defaults.get('bathroom_door', {'x': 4, 'y': 1})
                dx, dy = positions.get('bathroom_door', (def_pos_door['x'], def_pos_door['y']))
                e_info = HOUSE_ROM_ENTRIES['bathroom_door']
                results.append({'id': 'bathroom_door', 'name': e_info['name'], 'x': dx, 'y': dy, 'w': e_info['w'], 'h': e_info['h'], 'entry': e_info['entry']})

                def_pos_tub = defaults.get('bathroom_tub', {'x': 52, 'y': 5})
                tx, ty = positions.get('bathroom_tub', (def_pos_tub['x'], def_pos_tub['y']))
                e_info = HOUSE_ROM_ENTRIES['bathroom_tub']
                results.append({'id': 'bathroom_tub', 'name': e_info['name'], 'x': tx, 'y': ty, 'w': e_info['w'], 'h': e_info['h'], 'entry': e_info['entry']})

            if house_cfg.get('extras', True):
                for extra_key in ['clock_mirror', 'rug_mat', 'table_vase', 'carpet_dining']:
                    if extra_key in defaults:
                        def_pos = defaults[extra_key]
                        ex, ey = positions.get(extra_key, (def_pos['x'], def_pos['y']))
                        e_info = HOUSE_ROM_ENTRIES[def_pos['type']]
                        results.append({'id': extra_key, 'name': e_info['name'], 'x': ex, 'y': ey, 'w': e_info['w'], 'h': e_info['h'], 'entry': e_info['entry']})

        return results

    def _get_structure_dimensions(self, entry_index: int) -> tuple:
        table_offset = ROM_BUILDINGS_TABLE + (entry_index * 24)
        if table_offset + 24 <= len(self.rom):
            import struct
            chunk = self.rom[table_offset : table_offset + 24]
            flags = struct.unpack_from('<H', chunk, 0)[0]
            w = flags & 0xFF
            h = (flags >> 8) & 0xFF
            return (w, h)
        return (0, 0)
