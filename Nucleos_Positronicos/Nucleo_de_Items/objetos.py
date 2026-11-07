# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v4.0.0)
# "The Greatest Show - Final Release"
# Desarrollado por: Denisovich728
# ============================================================
"""
objetos.py - Motor Canonico de Items, Estructuras de ROM y Extraccion de Iconos
Bases maestras verificadas en ROM limpia mediante ingenieria inversa del Port:
- TOOLS_ROM_OFFSET = 0x000EAB0C (80 items, 12 bytes por entrada)
- FOODS_ROM_OFFSET = 0x000EDCD8 (170 items, 16 bytes por entrada)
- MISC_ROM_OFFSET  = 0x000EFED4 (94 items, 12 bytes por entrada)
- Subsistema Grafico de Iconos GBA:
  - Base Maestra: 0x086678A0 (Offset fisico: 0x6678A0)
  - Array 1 (Graphic ID -> Script): 0x6678A4 (stride 4)
  - Array 2 (Frame Descriptors):    0x66805C (stride 16)
  - Array 4 (Tiles 4bpp):           0x66A2CC (stride 32)
  - Array 5 (Paletas BGR555):       0x676DD0 (stride 32)
  - Array 7 (Script -> Frame):      0x679898 (stride 4)
"""

import os
import csv
import struct
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image

from PyQt6.QtGui import QImage, QPixmap, QIcon

from Banco_de_Datos.Utilidades.rutas import get_data_path


# ============================================================
#  MOTOR DE EXTRACCION DE ICONOS CANONICOS EN TIEMPO DE EJECUCION
# ============================================================

class ItemIconEngine:
    ARR1_OFF = 0x6678A4
    ARR2_OFF = 0x66805C
    ARR4_OFF = 0x66A2CC
    ARR5_OFF = 0x676DD0
    ARR7_OFF = 0x679898

    def __init__(self, rom_data: bytes):
        self.rom = rom_data
        self._cache_pil: Dict[Tuple[int, int], Image.Image] = {}
        self._cache_pixmap: Dict[Tuple[int, int], QPixmap] = {}

    def extract_icon_pil(self, graphic_id: int, scale: int = 1) -> Optional[Image.Image]:
        cache_key = (graphic_id, scale)
        if cache_key in self._cache_pil:
            return self._cache_pil[cache_key]

        arr1_entry = self.ARR1_OFF + graphic_id * 4
        if arr1_entry + 4 > len(self.rom):
            return None

        w0, w1 = struct.unpack_from('<HH', self.rom, arr1_entry)
        arr7_entry = self.ARR7_OFF + w1 * 4
        if arr7_entry + 4 > len(self.rom):
            return None

        frame_idx, timer = struct.unpack_from('<HH', self.rom, arr7_entry)
        arr2_entry = self.ARR2_OFF + frame_idx * 16
        if arr2_entry + 16 > len(self.rom):
            return None

        oam_cnt, oam_id, tile_cnt, tile_id, pal_cnt, pal_id = struct.unpack_from('<HHHHHH', self.rom, arr2_entry)

        # Decodificar paleta BGR555 (16 colores)
        pal_off = self.ARR5_OFF + pal_id * 32
        palette = []
        for i in range(16):
            if pal_off + i * 2 + 2 <= len(self.rom):
                c = struct.unpack_from('<H', self.rom, pal_off + i * 2)[0]
                r = (c & 0x1F) << 3
                g = ((c >> 5) & 0x1F) << 3
                b = ((c >> 10) & 0x1F) << 3
                a = 255 if i > 0 else 0
                palette.append((r, g, b, a))
            else:
                palette.append((0, 0, 0, 0))

        # Decodificar 4 tiles 4bpp (grid 2x2 = 16x16)
        tile_base = self.ARR4_OFF + tile_id * 32
        img = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
        pixels = img.load()

        for ty in range(2):
            for tx in range(2):
                t_idx = ty * 2 + tx
                t_off = tile_base + t_idx * 32
                if t_off + 32 > len(self.rom):
                    continue
                for py in range(8):
                    for px in range(4):
                        b = self.rom[t_off + py * 4 + px]
                        p1 = b & 0x0F
                        p2 = (b >> 4) & 0x0F
                        pixels[tx * 8 + px * 2, ty * 8 + py] = palette[p1]
                        pixels[tx * 8 + px * 2 + 1, ty * 8 + py] = palette[p2]

        if scale > 1:
            img = img.resize((16 * scale, 16 * scale), Image.Resampling.NEAREST)

        self._cache_pil[cache_key] = img
        return img

    def extract_icon_pixmap(self, graphic_id: int, scale: int = 1) -> QPixmap:
        cache_key = (graphic_id, scale)
        if cache_key in self._cache_pixmap:
            return self._cache_pixmap[cache_key]

        pil_img = self.extract_icon_pil(graphic_id, scale)
        if not pil_img:
            pm = QPixmap()
            self._cache_pixmap[cache_key] = pm
            return pm

        if pil_img.mode != "RGBA":
            pil_img = pil_img.convert("RGBA")
        data = pil_img.tobytes("raw", "RGBA")
        qimg = QImage(data, pil_img.width, pil_img.height, QImage.Format.Format_RGBA8888)
        pix = QPixmap.fromImage(qimg)
        self._cache_pixmap[cache_key] = pix
        return pix

    def inject_icon_pil(self, graphic_id: int, pil_img: Image.Image, project=None) -> bool:
        """
        Inyecta un icono de 16x16 pixels cuantizado a 16 colores (paleta BGR555)
        y 4 tiles 4bpp directamente en la memoria virtual / ROM.
        """
        arr1_entry = self.ARR1_OFF + graphic_id * 4
        if arr1_entry + 4 > len(self.rom):
            return False

        w0, w1 = struct.unpack_from('<HH', self.rom, arr1_entry)
        arr7_entry = self.ARR7_OFF + w1 * 4
        if arr7_entry + 4 > len(self.rom):
            return False

        frame_idx, timer = struct.unpack_from('<HH', self.rom, arr7_entry)
        arr2_entry = self.ARR2_OFF + frame_idx * 16
        if arr2_entry + 16 > len(self.rom):
            return False

        oam_cnt, oam_id, tile_cnt, tile_id, pal_cnt, pal_id = struct.unpack_from('<HHHHHH', self.rom, arr2_entry)
        pal_off = self.ARR5_OFF + pal_id * 32
        tile_base = self.ARR4_OFF + tile_id * 32

        if pal_off + 32 > len(self.rom) or tile_base + 128 > len(self.rom):
            return False

        # Redimensionar si es necesario a 16x16 RGBA
        if pil_img.size != (16, 16):
            pil_img = pil_img.resize((16, 16), Image.Resampling.NEAREST)
        if pil_img.mode != "RGBA":
            pil_img = pil_img.convert("RGBA")

        def clean_rgba(rgba):
            if rgba[3] < 128:
                return (0, 0, 0, 0)
            r = ((rgba[0] >> 3) & 0x1F) << 3
            g = ((rgba[1] >> 3) & 0x1F) << 3
            b = ((rgba[2] >> 3) & 0x1F) << 3
            return (r, g, b, 255)

        palette_map = {(0, 0, 0, 0): 0}
        palette_list = [(0, 0, 0, 0)]

        for y in range(16):
            for x in range(16):
                rgba = clean_rgba(pil_img.getpixel((x, y)))
                if rgba not in palette_map:
                    if len(palette_list) < 16:
                        palette_map[rgba] = len(palette_list)
                        palette_list.append(rgba)
                    else:
                        best_idx = 1
                        best_dist = 99999999
                        for p_idx in range(1, len(palette_list)):
                            pr, pg, pb, pa = palette_list[p_idx]
                            d = (rgba[0]-pr)**2 + (rgba[1]-pg)**2 + (rgba[2]-pb)**2
                            if d < best_dist:
                                best_dist = d
                                best_idx = p_idx
                        palette_map[rgba] = best_idx

        # Construir buffer de paleta (32 bytes)
        pal_bytes = bytearray(32)
        for i in range(16):
            if i < len(palette_list):
                r, g, b, a = palette_list[i]
                bgr = ((r >> 3) & 0x1F) | (((g >> 3) & 0x1F) << 5) | (((b >> 3) & 0x1F) << 10)
            else:
                bgr = 0
            struct.pack_into('<H', pal_bytes, i * 2, bgr)

        # Construir buffer de 4 tiles 4bpp (128 bytes)
        tiles_bytes = bytearray(128)
        for ty in range(2):
            for tx in range(2):
                t_idx = ty * 2 + tx
                t_rel = t_idx * 32
                for py in range(8):
                    for px in range(4):
                        c1 = palette_map[clean_rgba(pil_img.getpixel((tx * 8 + px * 2, ty * 8 + py)))]
                        c2 = palette_map[clean_rgba(pil_img.getpixel((tx * 8 + px * 2 + 1, ty * 8 + py)))]
                        tiles_bytes[t_rel + py * 4 + px] = (c1 & 0x0F) | ((c2 & 0x0F) << 4)

        # Escribir en ROM
        if project:
            project.write_patch(pal_off, bytes(pal_bytes))
            project.write_patch(tile_base, bytes(tiles_bytes))
            self.rom = project.base_rom_data
        else:
            if isinstance(self.rom, bytearray):
                self.rom[pal_off:pal_off+32] = pal_bytes
                self.rom[tile_base:tile_base+128] = tiles_bytes
            else:
                rb = bytearray(self.rom)
                rb[pal_off:pal_off+32] = pal_bytes
                rb[tile_base:tile_base+128] = tiles_bytes
                self.rom = bytes(rb)

        # Invalidar caches
        for k in list(self._cache_pil.keys()):
            if k[0] == graphic_id:
                del self._cache_pil[k]
        for k in list(self._cache_pixmap.keys()):
            if k[0] == graphic_id:
                del self._cache_pixmap[k]

        return True


# ============================================================
#  MODELOS DE DATOS DE ITEMS EN ROM
# ============================================================

class BaseItem:
    def __init__(self, parser, index: int, offset: int, category: str):
        self.parser = parser
        self.index = index
        self.base_offset = offset
        self.category = category
        self.global_id = 0

        self.name_str = "Desconocido"
        self.desc_str = "Sin descripcion"
        self.name_ptr = 0
        self.desc_ptr = 0

        self.graphic_id = 0
        self.tier_or_flags = 0
        self.is_drink = False
        self.stamina = 0
        self.fatigue = 0

        self.price = 0          # Precio de venta (embarque)
        self.buy_price = 0      # Precio de compra
        self.is_shippable = False
        self.product_offset = None

    def get_icon_pixmap(self, scale: int = 1) -> QPixmap:
        if self.parser and self.parser.icon_engine:
            return self.parser.icon_engine.extract_icon_pixmap(self.graphic_id, scale)
        return QPixmap()

    def get_icon(self, scale: int = 2) -> QIcon:
        pix = self.get_icon_pixmap(scale)
        return QIcon(pix) if not pix.isNull() else QIcon()

    def save_name_in_place(self, new_name: str):
        if not hasattr(self, 'name_ptr') or self.name_ptr == 0:
            return

        encoded = self.parser.write_string(new_name)
        old_off = self.name_ptr & 0x01FFFFFF
        old_size = self.parser.get_string_size(self.name_ptr)

        new_offset = self.parser.project.memory._re_point_generic_script(
            encoded,
            old_off,
            old_size,
            lambda off: self.parser.project.write_patch(self.base_offset, struct.pack("<I", off | 0x08000000))
        )

        self.name_str = new_name
        self.name_ptr = new_offset | 0x08000000

    def save_desc_in_place(self, new_desc: str):
        if not hasattr(self, 'desc_ptr') or self.desc_ptr == 0:
            return

        encoded = self.parser.write_string(new_desc)
        old_off = self.desc_ptr & 0x01FFFFFF
        old_size = self.parser.get_string_size(self.desc_ptr)

        desc_ptr_offset = self.base_offset + (12 if self.category == "Consumible/Comida" else 8)

        new_offset = self.parser.project.memory._re_point_generic_script(
            encoded,
            old_off,
            old_size,
            lambda off: self.parser.project.write_patch(desc_ptr_offset, struct.pack("<I", off | 0x08000000))
        )

        self.desc_str = new_desc
        self.desc_ptr = new_offset | 0x08000000

    def save_graphic_id(self, new_gid: int):
        gid_offset = self.base_offset + (8 if self.category == "Consumible/Comida" else 4)
        self.parser.project.write_patch(gid_offset, struct.pack("<H", new_gid & 0xFFFF))
        self.graphic_id = new_gid

    def save_sell_price(self, new_price: int):
        self.price = new_price
        if self.product_offset:
            data = list(self.parser.project.read_rom(self.product_offset, 4))
            old_hword = struct.unpack('<H', bytes(data[0:2]))[0]
            kind_flag = old_hword & 0x8000
            new_hword = kind_flag | (new_price & 0x7FFF)
            data[0:2] = struct.pack('<H', new_hword)
            self.parser.project.write_patch(self.product_offset, bytes(data))

    def save_buy_price(self, new_price: int):
        self.buy_price = new_price
        if hasattr(self, 'shop_entry') and self.shop_entry:
            self.shop_entry.save_price(new_price)


class ToolItem(BaseItem):
    SIZE = 12

    def read_stats(self):
        data = self.parser.project.read_rom(self.base_offset, self.SIZE)
        if not data or len(data) < self.SIZE:
            return

        self.name_ptr, self.graphic_id, self.tier_or_flags, self.desc_ptr = struct.unpack_from('<IHHI', data, 0)
        self.name_str = self.parser.read_string(self.name_ptr)
        self.desc_str = self.parser.read_string(self.desc_ptr)

    def save_tier(self, new_tier: int):
        self.tier_or_flags = new_tier & 0xFFFF
        self.parser.project.write_patch(self.base_offset + 6, struct.pack("<H", self.tier_or_flags))


class FoodItem(BaseItem):
    SIZE = 16

    def read_stats(self):
        data = self.parser.project.read_rom(self.base_offset, self.SIZE)
        if not data or len(data) < self.SIZE:
            return

        self.name_ptr = struct.unpack_from('<I', data, 0)[0]
        flags = data[4]
        self.is_drink = bool(flags & 1)
        self.stamina = struct.unpack_from('<b', data, 5)[0]
        self.fatigue = struct.unpack_from('<b', data, 6)[0]
        self.graphic_id = struct.unpack_from('<H', data, 8)[0]
        self.desc_ptr = struct.unpack_from('<I', data, 12)[0]

        self.name_str = self.parser.read_string(self.name_ptr)
        self.desc_str = self.parser.read_string(self.desc_ptr)

    def save_food_stats(self, stamina: int, fatigue: int, is_drink: bool, graphic_id: int):
        self.stamina = stamina
        self.fatigue = fatigue
        self.is_drink = is_drink
        self.graphic_id = graphic_id

        # Leer bytes actuales de la entrada
        raw = bytearray(self.parser.project.read_rom(self.base_offset, self.SIZE))
        if len(raw) >= self.SIZE:
            raw[4] = (raw[4] & ~1) | (1 if is_drink else 0)
            raw[5] = struct.pack('<b', stamina)[0]
            raw[6] = struct.pack('<b', fatigue)[0]
            struct.pack_into('<H', raw, 8, graphic_id & 0xFFFF)
            self.parser.project.write_patch(self.base_offset, bytes(raw))


class MiscItem(BaseItem):
    SIZE = 12

    def read_stats(self):
        data = self.parser.project.read_rom(self.base_offset, self.SIZE)
        if not data or len(data) < self.SIZE:
            return

        self.name_ptr, self.graphic_id, self.tier_or_flags, self.desc_ptr = struct.unpack_from('<IHHI', data, 0)
        self.name_str = self.parser.read_string(self.name_ptr)
        self.desc_str = self.parser.read_string(self.desc_ptr)

    def save_flags(self, new_flags: int):
        self.tier_or_flags = new_flags & 0xFFFF
        self.parser.project.write_patch(self.base_offset + 6, struct.pack("<H", self.tier_or_flags))


# ============================================================
#  PARSER CANONICO DE ITEMS
# ============================================================

class ItemParser:
    TOOLS_OFFSET = 0x000EAB0C  # 80 items
    FOODS_OFFSET = 0x000EDCD8  # 170 items
    MISC_OFFSET  = 0x000EFED4  # 94 items

    def __init__(self, project):
        self.project = project
        self.items: List[BaseItem] = []
        self.icon_engine: Optional[ItemIconEngine] = None

        from Banco_de_Datos.parche_splash import require_rom_signature
        require_rom_signature(project, auto_sign=True, module_name='ItemParser')
        if project and project.base_rom_data:
            self.icon_engine = ItemIconEngine(project.base_rom_data)

        self.scan_items()

    def scan_items(self) -> List[BaseItem]:
        self.items.clear()
        if not self.project:
            return self.items

        # Cargar tabla suplementaria si existe
        master_info = self._load_master_table()

        # 1. Herramientas (80 items, 12 bytes stride)
        for i in range(80):
            off = self.TOOLS_OFFSET + i * 12
            item = ToolItem(self, i, off, "Herramienta")
            item.global_id = i
            item.read_stats()
            self._apply_master_info(item, master_info.get(item.global_id))
            self.items.append(item)

        # 2. Comidas y Cultivos (170 items, 16 bytes stride)
        for i in range(170):
            off = self.FOODS_OFFSET + i * 16
            item = FoodItem(self, i, off, "Consumible/Comida")
            item.global_id = 80 + i
            item.read_stats()
            self._apply_master_info(item, master_info.get(item.global_id))
            self.items.append(item)

        # 3. Minerales y Varios (94 items, 12 bytes stride)
        for i in range(94):
            off = self.MISC_OFFSET + i * 12
            item = MiscItem(self, i, off, "Artículo")
            item.global_id = 250 + i
            item.read_stats()
            self._apply_master_info(item, master_info.get(item.global_id))
            self.items.append(item)

        return self.items

    def scan_foods(self) -> List[BaseItem]:
        """Alias para compatibilidad con llamadas existentes."""
        return self.scan_items()

    def _load_master_table(self) -> Dict[int, Dict[str, Any]]:
        master = {}
        csv_candidates = [
            os.path.join(os.path.dirname(__file__), "..", "..", "Banco_de_Datos", "Cilixes", "fomt", "items_master_table.csv"),
            os.path.join(r"J:\Laboratorio\harvest_moon_fomt_port\assets\data", "items_master_table.csv")
        ]

        found_path = None
        for p in csv_candidates:
            if os.path.exists(p):
                found_path = p
                break

        if not found_path:
            return master

        try:
            with open(found_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        i_id = int(row.get("id", -1))
                        if i_id >= 0:
                            master[i_id] = {
                                "name_es": row.get("name_es", ""),
                                "name_en": row.get("name_en", ""),
                                "sell_price": int(row.get("sell_price", 0)),
                                "buy_price": int(row.get("buy_price", 0)),
                                "is_shippable": row.get("is_shippable", "False").lower() == "true",
                                "stamina": int(row.get("stamina_effect", 0)),
                                "fatigue": int(row.get("fatigue_effect", 0)),
                            }
                    except ValueError:
                        continue
        except Exception as e:
            print(f"[ItemParser] Error cargando items_master_table: {e}")

        return master

    def _apply_master_info(self, item: BaseItem, info: Optional[Dict[str, Any]]):
        if not info:
            return
        if info.get("sell_price", 0) > 0:
            item.price = info["sell_price"]
        if info.get("buy_price", 0) > 0:
            item.buy_price = info["buy_price"]
        item.is_shippable = info.get("is_shippable", False)

        # Si el item en ROM tenia stamina en 0 pero master tiene valor asignado
        if item.category == "Consumible/Comida" and item.stamina == 0 and info.get("stamina", 0) != 0:
            item.stamina = info["stamina"]
            item.fatigue = info["fatigue"]

    def read_string(self, gba_addr: int) -> str:
        """Lectura Robusta con soporte de N mapeada (B1/B2)."""
        offset = gba_addr & 0x1FFFFFF
        s = ""
        rom = self.project.virtual_rom if self.project and hasattr(self.project, 'virtual_rom') else self.project.base_rom_data
        if not rom:
            return s

        while offset < len(rom):
            b = rom[offset]
            if b == 0:
                break
            if b == 0xB1:
                s += "ñ"
            elif b == 0xB2:
                s += "Ñ"
            elif 32 <= b <= 126:
                s += chr(b)
            elif b == 10:
                s += "[n]"
            else:
                s += f"[{b:02x}]"
            offset += 1
        return s

    def write_string(self, text: str) -> bytes:
        """Convierte texto de la UI a bytes de ROM con soporte de N (B1/B2)."""
        import re
        text = text.replace("ñ", "[b1]").replace("Ñ", "[b2]")
        output = bytearray()
        tokens = re.split(r'(\[[0-9A-Fa-f]{2}\]|\[n\])', text)

        for token in tokens:
            if not token:
                continue
            if token == "[n]":
                output.append(0x0A)
            elif re.match(r'\[[0-9A-Fa-f]{2}\]', token):
                output.append(int(token[1:3], 16))
            else:
                output.extend(token.encode('windows-1252', errors='replace'))

        output.append(0x00)
        return bytes(output)

    def get_string_size(self, ptr: int) -> int:
        if ptr < 0x08000000 or ptr >= 0x09000000:
            return 0
        offset = ptr & 0x01FFFFFF
        size = 0
        while True:
            b = self.project.read_rom(offset + size, 1)
            size += 1
            if not b or b[0] == 0:
                break
        return size
