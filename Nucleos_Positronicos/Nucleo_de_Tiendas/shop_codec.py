import os
import csv
import struct
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


@dataclass
class ShopItemEntry:
    slot_idx: int
    item_id: int
    price: int


@dataclass
class ShopDefinition:
    key: str
    name: str
    category: str  # "Tool", "FoodOrCrop", "MineralOrMisc"
    offset: int
    count: int
    entries: List[ShopItemEntry] = field(default_factory=list)


class ShopCodec:
    """
    Decodifica y parchea las tablas nativas de tiendas en FoMT y MFoMT.
    Cada entrada en ROM ocupa 8 bytes: <II (uint32 item_id, uint32 price).
    """

    SHOPS_FOMT = [
        ("supermarket_seeds", "Supermercado - Semillas (Jeff)", "Tool", 0x0FDDD8, 13, struct.pack("<IIII", 50, 120, 51, 150)),
        ("supermarket_food", "Supermercado - Alimentos (Jeff)", "FoodOrCrop", 0x0FDFA4, 7, struct.pack("<IIII", 63, 100, 64, 100)),
        ("clinic", "Clínica (Doctor)", "FoodOrCrop", 0x0FE050, 4, struct.pack("<IIII", 57, 500, 58, 1000)),
        ("won", "Tienda de Won", "Tool", 0x0FE484, 10, struct.pack("<IIII", 53, 100, 94, 5000)),
        ("winery", "Bodega Aja (Duke)", "FoodOrCrop", 0x0FE740, 2, struct.pack("<IIII", 61, 300, 62, 200)),
        ("van_records", "Tienda de Van / Discos", "MineralOrMisc", 0x0FE8FC, 14, struct.pack("<IIII", 64, 500, 65, 600)),
    ]

    SHOPS_MFOMT = [
        ("supermarket_seeds", "Supermercado - Semillas (Jeff)", "Tool", 0x106B04, 13, struct.pack("<IIII", 50, 120, 51, 150)),
        ("supermarket_food", "Supermercado - Alimentos (Jeff)", "FoodOrCrop", 0x106CD0, 7, struct.pack("<IIII", 63, 100, 64, 100)),
        ("clinic", "Clínica (Doctor)", "FoodOrCrop", 0x106D7C, 4, struct.pack("<IIII", 57, 500, 58, 1000)),
        ("winery", "Bodega Aja (Duke)", "FoodOrCrop", 0x10746C, 2, struct.pack("<IIII", 61, 300, 62, 200)),
        ("van_records", "Tienda de Van / Discos", "MineralOrMisc", 0x107628, 14, struct.pack("<IIII", 64, 500, 65, 600)),
    ]

    @staticmethod
    def load_item_catalog() -> Dict[str, Dict[int, str]]:
        """Carga items_master_table.csv agrupado por (category -> {index_in_category: nombre})."""
        catalog: Dict[str, Dict[int, str]] = {
            "Tool": {},
            "FoodOrCrop": {},
            "MineralOrMisc": {},
        }
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        csv_path = os.path.join(base_dir, "Banco_de_Datos", "Cilixes", "fomt", "items_master_table.csv")
        if not os.path.exists(csv_path):
            return catalog
        with open(csv_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                cat = row.get("category", "")
                if cat not in catalog:
                    catalog[cat] = {}
                try:
                    sub_idx = int(row.get("index_in_category", 0))
                except ValueError:
                    continue
                name = row.get("name_es") or row.get("name_en") or f"Item #{sub_idx}"
                catalog[cat][sub_idx] = name
        return catalog

    @classmethod
    def _get_rom_bytes(cls, project) -> Optional[bytes]:
        if getattr(project, "virtual_rom", None):
            return bytes(project.virtual_rom)
        if getattr(project, "base_rom_data", None):
            return bytes(project.base_rom_data)
        return None

    @classmethod
    def load_shops(cls, project) -> List[ShopDefinition]:
        rom = cls._get_rom_bytes(project)
        if not rom:
            return []

        is_mfomt = bool(getattr(project, "is_mfomt", False))
        defs = cls.SHOPS_MFOMT if is_mfomt else cls.SHOPS_FOMT
        shops: List[ShopDefinition] = []

        for key, name, cat, default_off, count, sig in defs:
            off = default_off
            if off + count * 8 > len(rom):
                idx = rom.find(sig)
                if idx == -1:
                    continue
                off = idx

            entries: List[ShopItemEntry] = []
            for i in range(count):
                item_id, price = struct.unpack_from("<II", rom, off + i * 8)
                entries.append(ShopItemEntry(slot_idx=i, item_id=item_id, price=price))

            shops.append(ShopDefinition(
                key=key,
                name=name,
                category=cat,
                offset=off,
                count=count,
                entries=entries,
            ))

        return shops

    @classmethod
    def save_shop(cls, project, shop: ShopDefinition) -> Tuple[bool, str]:
        if not project:
            return False, "No hay proyecto activo."
        if len(shop.entries) != shop.count:
            return False, f"Cantidad de slots inválida ({len(shop.entries)} != {shop.count})."

        buf = bytearray()
        for e in shop.entries:
            buf.extend(struct.pack("<II", max(0, int(e.item_id)), max(0, int(e.price))))

        project.write_patch(shop.offset, bytes(buf))
        if hasattr(project, "save") and getattr(project, "project_dir", None):
            try:
                project.save()
            except Exception:
                pass
        return True, f"Tienda '{shop.name}' actualizada en 0x{shop.offset:06X} ({len(buf)} bytes)."

