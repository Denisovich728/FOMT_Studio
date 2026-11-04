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
        'lv2': {'summer': 2, 'winter': 3, 'x': 26, 'y': 3},
        'lv3': {'summer': 4, 'winter': 5, 'x': 26, 'y': 3},
    },
    'barn': {
        'lv1': {'summer': 6, 'winter': 7, 'x': 58, 'y': 2},
        'lv2': {'summer': 8, 'winter': 9, 'x': 58, 'y': 2},
    },
    'chicken_coop': {
        'lv1': {'summer': 10, 'winter': 11, 'x': 14, 'y': 52},
        'lv2': {'summer': 12, 'winter': 13, 'x': 14, 'y': 52},
    },
    'mailbox': {'summer': 46, 'winter': 46, 'x': 34, 'y': 6},
    # 'doghouse': Eliminado para evitar colisión de tiles glitcheados
    'town_cottage': {'summer': 38, 'winter': 39, 'x': 20, 'y': 15},
    'beach_cottage': {'summer': 40, 'winter': 41, 'x': 30, 'y': 26},
    'mountain_cottage': {'summer': 44, 'winter': 45, 'x': 23, 'y': 20},
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
            'town_cottage': True       # Villa de la ciudad (Mapas 04, 05, 06, 07)
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

    def _stamp_rom_structure(self, bg3, bg2, bg1, entry_idx, map_x, map_y):
        if not self.rom or entry_idx is None:
            return
        entry_off = ROM_BUILDINGS_TABLE + entry_idx * 24
        if entry_off + 24 > len(self.rom):
            return
        w, h = struct.unpack_from('<BB', self.rom, entry_off)
        p_bg3, p_bg2, p_bg1 = struct.unpack_from('<III', self.rom, entry_off + 4)

        for ptr, tmap in [(p_bg3, bg3), (p_bg2, bg2), (p_bg1, bg1)]:
            if ptr != 0 and tmap:
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
        array_bg3 = list(self.tilemap_bg3) if self.tilemap_bg3 else []
        array_bg2 = list(self.tilemap_bg2) if self.tilemap_bg2 else []
        array_bg1 = list(self.tilemap_bg1) if self.tilemap_bg1 else []

        map_id = getattr(self._map_header, 'map_id', 0) if self._map_header else 0
        is_winter = (map_id in (1, 3, 5, 7, 9, 11, 13, 15, 17) or bank == 2)
        season_key = 'winter' if is_winter else 'summer'
        dyn_cfg = getattr(self, 'dynamic_config', {})

        # Estampar estructuras dinámicas 100% nativas desde la tabla de la ROM
        if dyn_cfg.get('enabled', True):
            if map_id in (0, 1):
                # 1. Casa de Campo (Lv1, Lv2, Lv3)
                h_lvl = dyn_cfg.get('farmhouse', 'lv1')
                if h_lvl in BUILDING_ROM_ENTRIES['farmhouse']:
                    info = BUILDING_ROM_ENTRIES['farmhouse'][h_lvl]
                    self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, info[season_key], info['x'], info['y'])

                # 2. Granero (Lv1, Lv2)
                b_lvl = dyn_cfg.get('barn', 'lv1')
                if b_lvl in BUILDING_ROM_ENTRIES['barn']:
                    info = BUILDING_ROM_ENTRIES['barn'][b_lvl]
                    self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, info[season_key], info['x'], info['y'])

                # 3. Gallinero (Lv1, Lv2)
                c_lvl = dyn_cfg.get('chicken_coop', 'lv1')
                if c_lvl in BUILDING_ROM_ENTRIES['chicken_coop']:
                    info = BUILDING_ROM_ENTRIES['chicken_coop'][c_lvl]
                    self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, info[season_key], info['x'], info['y'])

                # 4. Extras de Granja (Buzón y Caseta de Perro)
                if dyn_cfg.get('extras', True):
                    mb = BUILDING_ROM_ENTRIES['mailbox']
                    self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, mb[season_key], mb['x'], mb['y'])
                    # Doghouse eliminada (ya existe nativa en el mapa base)

            elif map_id in (8, 9) and dyn_cfg.get('beach_cottage', True):
                # Villa de la Playa
                bc = BUILDING_ROM_ENTRIES['beach_cottage']
                self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, bc[season_key], bc['x'], bc['y'])

            elif map_id in (14, 15) and dyn_cfg.get('mountain_cottage', True):
                # Villa de la Montaña
                mc = BUILDING_ROM_ENTRIES['mountain_cottage']
                self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, mc[season_key], mc['x'], mc['y'])

            elif map_id in (4, 5, 6, 7) and dyn_cfg.get('town_cottage', True):
                # Villa de la Ciudad
                tc = BUILDING_ROM_ENTRIES['town_cottage']
                self._stamp_rom_structure(array_bg3, array_bg2, array_bg1, tc[season_key], tc['x'], tc['y'])

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

        if show_bottom and array_bottom:
            img = draw_layer(array_bottom, img, is_overlay=False)
            
        if show_bg2 and array_bg2:
            img = draw_layer(array_bg2, img, is_overlay=True)
            
        if show_top and array_top:
            img = draw_layer(array_top, img, is_overlay=True)

        # Malla Canónica de Cultivo (43x25 plots = 86x50 tiles, X=272, Y=176)
        if dyn_cfg.get('enabled', True) and map_id in (0, 1) and dyn_cfg.get('field_grid', False):
            from PIL import ImageDraw
            grid_overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
            gdraw = ImageDraw.Draw(grid_overlay)
            for pr in range(25):
                for pc in range(43):
                    px = 272 + pc * 16
                    py = 176 + pr * 16
                    gdraw.rectangle([px, py, px + 15, py + 15], outline=(255, 215, 0, 90), width=1)
            img.paste(grid_overlay, (0, 0), grid_overlay)

        # ── Capa de Colisiones ─────────────────────────────────────
        if show_col and self.collision_map:
            from PIL import ImageDraw
            overlay = Image.new('RGBA', (w * 8, h * 8), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            
            for row in range(h):
                for col in range(w):
                    idx = row * w + col
                    if idx >= len(self.collision_map):
                        break
                    val = self.collision_map[idx]
                    
                    if self.behavior_dict and val * 4 + 3 < len(self.behavior_dict):
                        behavior = struct.unpack_from('<H', self.behavior_dict, val * 4)[0]
                        script_id = struct.unpack_from('<H', self.behavior_dict, val * 4 + 2)[0]
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

            # Si las estructuras dinámicas están activadas, pintar sus huellas de colisión y triggers
            if dyn_cfg.get('enabled', True) and map_id in (0, 1):
                # Huella Casa Lv1/2/3: X=208..272, Y=24..112 (Sólido) con puerta en (232..248, 104..108)
                if dyn_cfg.get('farmhouse', 'lv1') != 'none':
                    draw.rectangle([208, 24, 271, 103], fill=(255, 0, 0, 120), outline=(255, 50, 50, 220))
                    draw.rectangle([232, 104, 247, 107], fill=(255, 215, 0, 180), outline=(255, 255, 0, 255))
                # Huella Granero: X=464..544, Y=16..112 (Sólido) con puerta en (496..512, 104..108)
                if dyn_cfg.get('barn', 'lv1') != 'none':
                    draw.rectangle([464, 16, 543, 103], fill=(255, 0, 0, 120), outline=(255, 50, 50, 220))
                    draw.rectangle([496, 104, 511, 107], fill=(255, 215, 0, 180), outline=(255, 255, 0, 255))
                # Huella Gallinero: X=112..184, Y=416..528 con puerta en (140..156, 504..508)
                if dyn_cfg.get('chicken_coop', 'lv1') != 'none':
                    draw.rectangle([112, 416, 183, 503], fill=(255, 0, 0, 120), outline=(255, 50, 50, 220))
                    draw.rectangle([140, 504, 155, 507], fill=(255, 215, 0, 180), outline=(255, 255, 0, 255))

            img.paste(overlay, (0, 0), overlay)

        return img

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
