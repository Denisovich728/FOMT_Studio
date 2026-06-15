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


def _decompress(rom: bytes, offset: int) -> bytes:
    """Descomprime usando el motor nativo de FoMT Studio."""
    from Nucleos_Positronicos.Nucleo_de_Mapas.mapas import decompress_auto
    return decompress_auto(bytes(rom), offset)


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

    def load_map(self, map_header) -> bool:
        """
        Carga un mapa desde un MapHeader de FoMT Studio.
        Equivale a blue-spider's MapData.load() + load_tilesets().
        """
        self._loaded = False
        self._map_header = map_header
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

    def render(self, show_bg1=True, show_bg2=True, show_bg3=True, show_col=False, bank=1, invert_bg=False) -> Image.Image | None:
        """
        Renderiza el mapa completo usando mapeo directo 8x8.
        Acepta flags para ocultar/mostrar capas, elegir banco de paletas e invertir BGs.
        """
        if not self._loaded:
            return None

        w, h = self.width, self.height
        palettes = self.palettes_1 if bank == 1 else self.palettes_2
        
        # Renderizar usando draw_layer
        def draw_layer(tgt_list, base_img, is_overlay=False):
            if not tgt_list: return base_img
            overlay = Image.new('RGBA', (w * 8, h * 8), (0, 0, 0, 0)) if is_overlay else base_img
            for row in range(h):
                for col in range(w):
                    idx = row * w + col
                    if idx >= len(tgt_list): continue
                    val = tgt_list[idx]
                    
                    t_idx  = val & 0x3FF
                    h_flip = bool((val >> 10) & 1)
                    v_flip = bool((val >> 11) & 1)
                    p_idx  = (val >> 12) & 0xF

                    if t_idx < len(self.tiles) and p_idx < len(palettes):
                        tile_img = _render_tile(self.tiles[t_idx], palettes[p_idx], h_flip, v_flip)
                        if is_overlay:
                            overlay.paste(tile_img, (col * 8, row * 8), tile_img)
                        else:
                            overlay.paste(tile_img, (col * 8, row * 8))
            
            if is_overlay:
                base_img.paste(overlay, (0, 0), overlay)
            return base_img
        
        img = Image.new('RGBA', (w * 8, h * 8), (0, 0, 0, 0))
        
        # Determinar qué arrays van al fondo y al frente
        array_bottom = self.tilemap_bg3  # p_bg3 es BG3 (Suelo)
        array_top = self.tilemap_bg1     # p_bg1 es BG1 (Frente)
        show_bottom = show_bg3
        show_top = show_bg1
        
        if invert_bg:
            array_bottom = self.tilemap_bg1
            array_top = self.tilemap_bg3
            show_bottom = show_bg1
            show_top = show_bg3

        # Dibujar en el orden correcto (Bottom -> Middle -> Top)
        if show_bottom and array_bottom:
            img = draw_layer(array_bottom, img, is_overlay=False)
            
        if show_bg2 and self.tilemap_bg2:
            img = draw_layer(self.tilemap_bg2, img, is_overlay=True)
            
        if show_top and array_top:
            img = draw_layer(array_top, img, is_overlay=True)

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

                    # Dynamic color mapping based on behavior instead of raw value
                    if val == 0:
                        # Caminable puro, sin colisión, sin nada.
                        r, g, b, a = 255, 255, 255, 0 # Transparente
                    elif is_solid and has_script:
                        # Solido con evento (Ej: Cartel o TV) -> Amarillo
                        r, g, b, a = 255, 215, 0, 120
                    elif is_solid:
                        # Sólido normal (Ej: Pared) -> Rojo
                        r, g, b, a = 255, 0, 0, 100
                    elif has_script:
                        # Caminable con evento (Ej: Warp o trigger) -> Verde
                        r, g, b, a = 0, 255, 0, 100
                    else:
                        # Caminable especial sin script (Ej: Agua, Ledge) -> Azul claro
                        r, g, b, a = 0, 150, 255, 90

                    if a > 0:
                        draw.rectangle([col*8, row*8, col*8+7, row*8+7], fill=(r, g, b, a), outline=(r, g, b, 200))
            img.paste(overlay, (0, 0), overlay)

        return img

    def render_tileset(self, pal_idx=0, bank=1) -> Image.Image | None:
        """Genera una imagen con todos los tiles usando la paleta especificada."""
        if not self._loaded or not self.tiles:
            return None
        palettes = self.palettes_1 if bank == 1 else self.palettes_2
        if pal_idx >= len(palettes):
            return None
            
        cols = 32
        rows = (len(self.tiles) + cols - 1) // cols
        img = Image.new('RGB', (cols * 8, rows * 8), (0, 0, 0))
        
        for i, tile_data in enumerate(self.tiles):
            c = i % cols
            r = i // cols
            tile_img = _render_tile(tile_data, palettes[pal_idx], False, False)
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
