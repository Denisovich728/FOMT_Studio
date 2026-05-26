# ============================================================
# FOMT Studio - Portrait Engine
# Melody Portrait Engine - v2.1 (Sistema de Coordenadas Corregido)
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
        Auto-Slicing Greedy Algorithm adaptado al sistema de coordenadas GBA.

        El sistema de coordenadas del juego tiene el anchor en la baseline
        inferior del portrait (el suelo). Los OAMs usan coordenadas negativas
        en Y para representar píxeles SOBRE el suelo.

        Parámetros:
            width, height: Dimensiones del PNG de entrada.
            anchor_x:      Posición X del anchor en el sistema de coordenadas GBA.
                           Por defecto: -width // 2 (centrado horizontalmente).
            anchor_y:      Posición Y del anchor en el sistema de coordenadas GBA.
                           Por defecto: 0 (baseline = borde inferior del PNG).
                           SIEMPRE debe ser 0 o negativo.

        El mapeo es:
            PNG (0, 0)        → GBA (anchor_x, anchor_y - height)   [esquina sup-izq]
            PNG (0, height)   → GBA (anchor_x, anchor_y)             [baseline/suelo]

        Todos los slices generados tienen y <= 0 para que sean visibles.
        """
        if anchor_x is None:
            anchor_x = -(width // 2)
        if anchor_y is None:
            anchor_y = 0  # baseline = borde inferior del PNG

        slices = []
        # Iterar de ARRIBA (y más negativo) hacia ABAJO (y=0)
        # El tope del PNG en coordenadas GBA es anchor_y - height
        gba_top = anchor_y - height

        y_png = 0  # posición en el PNG (de arriba hacia abajo)
        while y_png < height:
            rem_h = height - y_png
            gba_y = gba_top + y_png  # coordenada Y en sistema GBA

            valid_heights = [oh for _, _, _, oh in self.sorted_dims if oh <= rem_h]
            best_h = max(valid_heights) if valid_heights else 8

            x_png = 0
            while x_png < width:
                rem_w = width - x_png
                gba_x = anchor_x + x_png

                best_sprite = None
                for shape, size, ow, oh in self.sorted_dims:
                    if ow <= rem_w and oh <= best_h:
                        best_sprite = (shape, size, ow, oh)
                        break

                if not best_sprite:
                    best_sprite = (0, 0, 8, 8)

                shape, size, ow, oh = best_sprite
                slices.append({
                    'x': gba_x,          # Coordenada GBA (incluye anchor_x)
                    'y': gba_y,          # Coordenada GBA negativa (sobre el suelo)
                    'w': ow,
                    'h': oh,
                    'shape': shape,
                    'size': size,
                    # Posición en el PNG para el encodificador
                    'png_x': x_png,
                    'png_y': y_png,
                })
                x_png += ow
            y_png += best_h

        return slices

    def encode_4bpp(self, img, oam_slices):
        """
        Convierte los slices del PNG a GBA 4bpp y extrae la paleta.
        
        Ahora los slices incluyen 'png_x'/'png_y' para la posición exacta
        en el PNG fuente (independiente del sistema de coordenadas GBA).
        Si los slices no tienen png_x/png_y (compatibilidad con código viejo),
        usa la diferencia con el anchor implícito.
        """
        img = img.convert("RGBA")

        # 1. Extraer colores únicos
        colors = []
        pixels = img.load()
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

        palette_data = bytearray(32)
        for i, c in enumerate(colors):
            c16 = c[0] | (c[1] << 5) | (c[2] << 10)
            struct.pack_into('<H', palette_data, (i + 1) * 2, c16)

        def get_color_idx(r, g, b, a):
            if a < 128:
                return 0
            c = ((r >> 3), (g >> 3), (b >> 3))
            if c in colors:
                return colors.index(c) + 1
            return 1

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
                                r, g, b, a = pixels[cx, cy]
                                idx1 = get_color_idx(r, g, b, a)
                            if cx + 1 < img.width and cy < img.height:
                                r, g, b, a = pixels[cx + 1, cy]
                                idx2 = get_color_idx(r, g, b, a)

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
