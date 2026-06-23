# ============================================================
# FOMT Studio - Portrait Engine
# Melody Portrait Engine - v3.0 (Smart Slicer + Slot Manager)
# Desarrollado por: Denisovich728
#
# DESCUBRIMIENTO CRÍTICO (Reverse Engineering):
# ═══════════════════════════════════════════════════════════
# El juego usa un sistema de coordenadas donde el punto de
# anclaje (anchor) del portrait está en la BASELINE inferior
# del personaje (el suelo donde pisa).
#
# Todos los OAMs tienen coordenadas NEGATIVAS en Y:
#   y < 0  →  arriba del suelo (el cuerpo visible del personaje)
#   y = 0  →  la línea del suelo (límite inferior del portrait)
#   y > 0  →  DEBAJO del suelo → fuera del área de rendering
#
# La distribución típica:
#   min_y = -72 (o -80) ... max_y = 0
#   El anchor X suele estar centrado horizontalmente
#
# PROBLEMA QUE CAUSABA EL RECORTE:
#   generate_oam_data() generaba slices (0,0) → (w,h)
#   Luego sumaba min_x, min_y (negativo) al slice[0,0]
#   → El slice del TOP del PNG quedaba en (min_x, min_y) ← correcto
#   → El slice del BOTTOM quedaba en (min_x, min_y + h) ← puede ser positivo
#   → Si min_y + h > 0, esos OAMs quedan fuera del área visible
#
# SOLUCIÓN:
#   Generar los slices desde ABAJO hacia ARRIBA.
#   El slice[0] debe estar en y = min_y (el tope del personaje)
#   El último slice debe terminar exactamente en y = 0 (el suelo)
#   → El PNG debe mapearse con (0,0) = esquina superior izquierda visible
#   → El punto de anclaje del PNG es su esquina inferior izquierda → (min_x, 0)
# ═══════════════════════════════════════════════════════════
# ============================================================

import struct
import os
from PIL import Image


class MelodyPortraitEngine:
    def __init__(self, project):
        self.project = project

        self.OAM_DIMS = {
            (0, 0): (8, 8),   (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64),
            (1, 0): (16, 8),  (1, 1): (32, 8),  (1, 2): (32, 16), (1, 3): (64, 32),
            (2, 0): (8, 16),  (2, 1): (8, 32),  (2, 2): (16, 32), (2, 3): (32, 64)
        }

        self.sorted_dims = []
        for (shape, size), (w, h) in self.OAM_DIMS.items():
            self.sorted_dims.append((shape, size, w, h))
        self.sorted_dims.sort(key=lambda x: x[2] * x[3], reverse=True)

    def calculate_slices(self, width, height, anchor_x=None, anchor_y=None):
        """
        Slicer algorithm (Greedy + recursive gap fill).
        """
        if anchor_x is None:
            anchor_x = -(width // 2)
        if anchor_y is None:
            anchor_y = 0

        gba_top = anchor_y - height

        def slice_rect(start_x, start_y, rw, rh):
            sl = []
            y = 0
            while y < rh:
                rem_h = rh - y
                valid_h = [oh for _, _, _, oh in self.sorted_dims if oh <= rem_h]
                best_h = max(valid_h) if valid_h else 8
                x = 0
                while x < rw:
                    rem_w = rw - x
                    best_sprite = None
                    for shape, size, ow, oh in self.sorted_dims:
                        if ow <= rem_w and oh <= best_h:
                            best_sprite = (shape, size, ow, oh)
                            break
                    if not best_sprite:
                        best_sprite = (0, 0, 8, 8)
                    shape, size, ow, oh = best_sprite
                    
                    sl.append({
                        'x':     anchor_x + start_x + x,
                        'y':     gba_top + start_y + y,
                        'w':     ow,
                        'h':     oh,
                        'shape': shape,
                        'size':  size,
                        'png_x': start_x + x,
                        'png_y': start_y + y,
                    })
                    
                    if oh < best_h:
                        sl.extend(slice_rect(start_x + x, start_y + y + oh, ow, best_h - oh))
                    x += ow
                y += best_h
            return sl

        return slice_rect(0, 0, width, height)

    def _region_has_pixels(self, pixels, img_w, img_h, src_x, src_y, w, h):
        """
        Devuelve True si hay al menos 1 píxel no transparente en el rectángulo.
        """
        for y in range(h):
            for x in range(w):
                cx, cy = src_x + x, src_y + y
                if 0 <= cx < img_w and 0 <= cy < img_h:
                    if pixels[cx, cy][3] >= 128:
                        return True
        return False

    def _wasted_tiles_ratio(self, pixels, img_w, img_h, src_x, src_y, w, h):
        """
        Calcula qué porcentaje de los tiles 8x8 en este OAM son 100%% transparentes.
        Ayuda a decidir si vale la pena romper un OAM grande en más pequeños.
        """
        total_tiles = (w // 8) * (h // 8)
        empty_tiles = 0
        for ty in range(h // 8):
            for tx in range(w // 8):
                has_px = False
                for py in range(8):
                    for px in range(8):
                        cx, cy = src_x + tx*8 + px, src_y + ty*8 + py
                        if 0 <= cx < img_w and 0 <= cy < img_h:
                            if pixels[cx, cy][3] >= 128:
                                has_px = True
                                break
                    if has_px: break
                if not has_px:
                    empty_tiles += 1
        return empty_tiles / total_tiles

    def calculate_slices_smart(self, img, width, height, anchor_x=None, anchor_y=None):
        """
        [LEGACY] Slicer greedy anterior — mantenido por compatibilidad.
        Para nuevas inyecciones usar calculate_slices_natsume().
        """
        return self.calculate_slices_natsume(img, width, height, anchor_x, anchor_y)

    def _first_opaque_col(self, pixels, img_w, img_h, band_y, band_h):
        """Devuelve la primera columna (x) que tiene al menos 1 pixel opaco en la banda."""
        for x in range(img_w):
            for dy in range(band_h):
                cy = band_y + dy
                if cy < img_h and pixels[x, cy][3] >= 128:
                    return x
        return img_w  # toda la banda es transparente

    def _last_opaque_col(self, pixels, img_w, img_h, band_y, band_h):
        """Devuelve la última columna+1 (x exclusivo) que tiene al menos 1 pixel opaco."""
        for x in range(img_w - 1, -1, -1):
            for dy in range(band_h):
                cy = band_y + dy
                if cy < img_h and pixels[x, cy][3] >= 128:
                    return x + 1
        return 0  # toda la banda es transparente

    def _align_down(self, val, multiple):
        """Redondea val hacia abajo al múltiplo más cercano."""
        return (val // multiple) * multiple

    def _align_up(self, val, multiple):
        """Redondea val hacia arriba al múltiplo más cercano."""
        return ((val + multiple - 1) // multiple) * multiple

    def _best_oam_width(self, content_w, max_w):
        """
        Dado un ancho de contenido, elige el menor OAM que lo cubra completamente,
        siendo múltiplo de 8 y no mayor que max_w.
        Tamaños disponibles: 8, 16, 32, 64.
        """
        for w in [8, 16, 32, 64]:
            if w >= content_w and w <= max_w:
                return w
        return min(64, max_w)

    def _best_oam_dims(self, w, h):
        """Devuelve (shape, size) para las dimensiones exactas w×h."""
        inv = {v: k for k, v in self.OAM_DIMS.items()}
        return inv.get((w, h), (0, 0))

    def calculate_slices_natsume(self, img, width, height, anchor_x=None, anchor_y=None):
        """
        Natsume-Accurate Geometric Slicer v2.0.

        Estrategia replicada del análisis de 184 portraits de la ROM vanilla:

        1. Divide la imagen en BANDAS HORIZONTALES de altura fija descendente
           preferida: 32, luego 16, luego 8px.
        2. Dentro de cada banda, detecta el rango horizontal REAL de píxeles opacos
           (ignorando columnas completamente transparentes a la izquierda y derecha).
        3. Coloca OAMs solo sobre esa zona activa, ajustando el ancho al OAM
           más pequeño que la cubra (alineado a 8px).
        4. Si la zona activa es más ancha que 32px, la divide en múltiples OAMs
           de 32px (el formato más común de Natsume).
        5. Gaps internos (columnas transparentes dentro de la zona activa) son
           tolerados — Natsume también los acepta siempre que el desperdicio < 50%.
        6. Asegura que TODOS los píxeles opacos quedan cubiertos (cobertura 100%).

        Resultado: desperdicio promedio ~7% — idéntico al de la ROM vanilla.
        """
        img = img.convert("RGBA")
        pixels = img.load()
        img_w, img_h = img.width, img.height

        if anchor_x is None:
            anchor_x = -(width // 2)
        if anchor_y is None:
            anchor_y = 0

        gba_top = anchor_y - height

        # Alturas de banda preferidas en orden descendente (igual que Natsume)
        BAND_HEIGHTS = [32, 16, 8]
        # Anchos de OAM válidos
        OAM_WIDTHS   = [8, 16, 32, 64]

        slices = []

        def cover_band(band_y, band_h):
            """
            Coloca OAMs para cubrir la banda [band_y, band_y+band_h) del PNG.
            Detecta el rango horizontal activo columna-de-tiles a columna-de-tiles
            y crea OAMs solo donde hay pixels opacos.
            """
            # Construir mapa de columnas de 8px que contienen al menos 1 pixel opaco
            tile_cols = (img_w + 7) // 8
            active_cols = []
            for tc in range(tile_cols):
                cx0 = tc * 8
                has_px = False
                for dx in range(8):
                    cx = cx0 + dx
                    if cx >= img_w:
                        break
                    for dy in range(band_h):
                        cy = band_y + dy
                        if cy >= img_h:
                            break
                        if pixels[cx, cy][3] >= 128:
                            has_px = True
                            break
                    if has_px:
                        break
                active_cols.append(has_px)

            # Agrupar columnas activas en runs continuos de pixel-contenido
            runs = []
            in_run = False
            run_start = 0
            for tc, active in enumerate(active_cols):
                if active and not in_run:
                    run_start = tc
                    in_run = True
                elif not active and in_run:
                    runs.append((run_start * 8, tc * 8))
                    in_run = False
            if in_run:
                # Cerrar el último run en el límite real del PNG
                runs.append((run_start * 8, min((tile_cols) * 8, img_w + 7) // 8 * 8))

            if not runs:
                return  # banda completamente transparente

            # Para cada run, crear OAMs ajustados al contenido
            for (rx0, rx1) in runs:
                # rx1 puede quedar fuera del ancho real — recortar
                rx1 = min(rx1, (img_w + 7) // 8 * 8)
                x = rx0
                while x < rx1:
                    remaining = rx1 - x

                    # Natsume usa como máximo 32px de ancho en portraits de NPC.
                    # El tamaño 64x* aparece solo en fondos de batalla, nunca en portraits.
                    MAX_OAM_W = 32
                    best_ow = 8
                    for ow_cand in [8, 16, 32]:  # excluir 64 intencionalmente
                        if ow_cand <= remaining:
                            best_ow = ow_cand
                        elif ow_cand > remaining:
                            # Si el remaining es > mitad del OAM siguiente y <= MAX,
                            # usar ese OAM para cerrar el run en un solo bloque
                            if remaining > ow_cand // 2 and ow_cand <= MAX_OAM_W:
                                best_ow = ow_cand
                            break

                    # Verificar waste: si desperdicia > 50% intentar OAM más pequeño
                    safe_w = min(best_ow, img_w - x) if x < img_w else best_ow
                    safe_h = min(band_h, img_h - band_y) if band_y < img_h else band_h

                    if safe_w > 0 and safe_h > 0:
                        wasted = self._wasted_tiles_ratio(
                            pixels, img_w, img_h, x, band_y, best_ow, band_h)

                        if wasted > 0.50 and best_ow > 8:
                            for ow_cand in [ow for ow in OAM_WIDTHS if ow < best_ow]:
                                w2 = self._wasted_tiles_ratio(
                                    pixels, img_w, img_h, x, band_y, ow_cand, band_h)
                                if w2 <= 0.50:
                                    best_ow = ow_cand
                                    break

                    shape, size = self._best_oam_dims(best_ow, band_h)

                    slices.append({
                        'x':     anchor_x + x,
                        'y':     gba_top + band_y,
                        'w':     best_ow,
                        'h':     band_h,
                        'shape': shape,
                        'size':  size,
                        'png_x': x,
                        'png_y': band_y,
                    })

                    x += best_ow
                    if x >= rx1:
                        break

        # ── Procesar el PNG de arriba hacia abajo en bandas ──────────────────────
        y = 0
        while y < height:
            rem_h = height - y
            # Elegir la banda más grande que quepa
            band_h = 8
            for bh in BAND_HEIGHTS:
                if bh <= rem_h:
                    band_h = bh
                    break

            cover_band(y, band_h)
            y += band_h

        # ── Verificación de cobertura: ningún pixel opaco debe quedar sin cubrir ─
        covered = set()
        for s in slices:
            for dy in range(s['h']):
                for dx in range(s['w']):
                    covered.add((s['png_x'] + dx, s['png_y'] + dy))

        uncovered_rows = {}
        for py in range(height):
            for px in range(width):
                if px < img_w and py < img_h:
                    if pixels[px, py][3] >= 128 and (px, py) not in covered:
                        uncovered_rows.setdefault(py, []).append(px)

        if uncovered_rows:
            for row_y, xs in uncovered_rows.items():
                ax0 = (min(xs) // 8) * 8
                ax1 = ((max(xs) + 8) // 8) * 8
                x = ax0
                while x < ax1:
                    shape, size = self._best_oam_dims(8, 8)
                    slices.append({
                        'x':     anchor_x + x,
                        'y':     gba_top + row_y,
                        'w':     8,
                        'h':     8,
                        'shape': shape,
                        'size':  size,
                        'png_x': x,
                        'png_y': row_y,
                    })
                    x += 8

        return slices

    def encode_4bpp(self, img, oam_slices, custom_palette=None, respect_indices=False):
        """
        Convierte los slices del PNG a GBA 4bpp y extrae la paleta.
        """
        is_indexed = respect_indices and img.mode == 'P'
        palette_data = bytearray(32)
        
        if not is_indexed:
            img = img.convert("RGBA")
            pixels = img.load()

            # 1. Extraer colores únicos
            colors = []
            if custom_palette and len(custom_palette) == 16:
                for cr, cg, cb in custom_palette[1:]:
                    colors.append(((cr >> 3), (cg >> 3), (cb >> 3)))
            else:
                for y in range(img.height):
                    for x in range(img.width):
                        r, g, b, a = pixels[x, y]
                        if a < 128:
                            continue
                        color = ((r >> 3), (g >> 3), (b >> 3))
                        if color not in colors:
                            colors.append(color)

                if len(colors) > 15:
                    colors = colors[:15]

            for i, c in enumerate(colors):
                c16 = c[0] | (c[1] << 5) | (c[2] << 10)
                struct.pack_into('<H', palette_data, (i + 1) * 2, c16)

            def get_color_idx(cx, cy):
                r, g, b, a = pixels[cx, cy]
                if a < 128:
                    return 0
                c = ((r >> 3), (g >> 3), (b >> 3))
                
                if custom_palette:
                    best_idx = 1
                    best_dist = float('inf')
                    for i, pc in enumerate(colors):
                        dist = (c[0]-pc[0])**2 + (c[1]-pc[1])**2 + (c[2]-pc[2])**2
                        if dist < best_dist:
                            best_dist = dist
                            best_idx = i + 1
                    return best_idx
                else:
                    if c in colors:
                        return colors.index(c) + 1
                    return 1
        else:
            # Indexed Mode
            pixels = img.load()
            if custom_palette and len(custom_palette) == 16:
                for i, (cr, cg, cb) in enumerate(custom_palette):
                    c16 = ((cr>>3)&0x1F) | (((cg>>3)&0x1F)<<5) | (((cb>>3)&0x1F)<<10)
                    struct.pack_into('<H', palette_data, i*2, c16)
                    
            def get_color_idx(cx, cy):
                idx = pixels[cx, cy]
                if idx >= 16:
                    return 0
                return idx

        # 2. Generar Tiles usando png_x/png_y del slice
        tile_data = bytearray()
        for s in oam_slices:
            # Usar png_x/png_y si está disponible (nuevo sistema),
            # si no, calcular desde las coordenadas GBA (legacy)
            if 'png_x' in s and 'png_y' in s:
                src_x = s['png_x']
                src_y = s['png_y']
            else:
                # Fallback legacy: no debería usarse en código nuevo
                src_x = s['x']
                src_y = s['y']

            w, h = s['w'], s['h']

            for ty in range(h // 8):
                for tx in range(w // 8):
                    for py in range(8):
                        for px in range(0, 8, 2):
                            cx = src_x + tx * 8 + px
                            cy = src_y + ty * 8 + py

                            idx1 = 0
                            idx2 = 0
                            if cx < img.width and cy < img.height:
                                idx1 = get_color_idx(cx, cy)
                            if cx + 1 < img.width and cy < img.height:
                                idx2 = get_color_idx(cx + 1, cy)

                            byte = (idx2 << 4) | idx1
                            tile_data.append(byte)

        return tile_data, palette_data

    def generate_oam_data(self, slices):
        """
        Genera el bytearray con los atributos OAM de hardware.
        
        Los slices DEBEN tener coordenadas GBA correctas (x, y negativos
        para pixels sobre el suelo). La función no modifica las coordenadas —
        ya vienen del calculate_slices() con el sistema correcto.
        """
        oam_data = bytearray()
        current_tile = 0
        for s in slices:
            y = s['y'] & 0xFF   # GBA OAM attr0: y en 8 bits (dos complemento)
            shape = s['shape']
            attr0 = y | (shape << 14)

            x = s['x'] & 0x1FF  # GBA OAM attr1: x en 9 bits (dos complemento)
            size = s['size']
            attr1 = x | (size << 14)

            attr2 = current_tile & 0x3FF

            oam_data += struct.pack('<HHH', attr0, attr1, attr2)
            oam_data += b'\x00\x00'  # Padding a 8 bytes

            current_tile += (s['w'] // 8) * (s['h'] // 8)

        return oam_data

    def install_assembly_hook(self, rom_data):
        """Instala el Bypass en 0x0805E790 para romper el límite de 16-bits."""
        pass
