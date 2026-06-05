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
        Natsume-Style Smart Slicer (con gap fill recursivo y optimización agresiva).
        Omite rectángulos 100%% transparentes. Además, si un OAM desperdicia muchos
        tiles en zonas transparentes, lo rechaza para forzar OAMs más pequeños
        y ahorrar VRAM.
        """
        img = img.convert("RGBA")
        pixels = img.load()
        img_w, img_h = img.width, img.height

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
                    
                    # Buscar el sprite más grande, pero penalizar si desperdicia mucha memoria
                    for shape, size, ow, oh in self.sorted_dims:
                        if ow <= rem_w and oh <= best_h:
                            if not self._region_has_pixels(pixels, img_w, img_h, start_x + x, start_y + y, ow, oh):
                                # 100% transparente, es un candidato perfecto (costo 0 tiles)
                                best_sprite = (shape, size, ow, oh)
                                break
                            
                            # Si no es transparente, ver cuánto desperdicia
                            wasted = self._wasted_tiles_ratio(pixels, img_w, img_h, start_x + x, start_y + y, ow, oh)
                            # Si desperdicia más del 30% de sus tiles, intentamos usar un OAM más pequeño
                            if wasted > 0.30 and (ow > 16 or oh > 16):
                                continue
                                
                            best_sprite = (shape, size, ow, oh)
                            break
                            
                    if not best_sprite:
                        # Fallback al sprite más pequeño posible que quepa (o 8x8)
                        for shape, size, ow, oh in reversed(self.sorted_dims):
                            if ow <= rem_w and oh <= best_h:
                                best_sprite = (shape, size, ow, oh)
                                break
                        if not best_sprite:
                            best_sprite = (0, 0, 8, 8)
                            
                    shape, size, ow, oh = best_sprite

                    if self._region_has_pixels(pixels, img_w, img_h, start_x + x, start_y + y, ow, oh):
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
