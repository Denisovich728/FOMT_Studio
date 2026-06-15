# ============================================================
# FOMT Studio - Módulo de Cultivos
# Mapeado por ingeniería inversa directa (sin Ghidra)
# ============================================================
import struct

# ============================================================
# OFFSETS CONFIRMADOS POR ANÁLISIS DIRECTO DE LA ROM (USA)
# ============================================================
SEEDS_TABLE_BASE    = 0x0EAD58  # Stride 12: [name_ptr:4][buy_price:4][desc_ptr:4]
HARVEST_TABLE_BASE  = 0x0EDCD8  # Stride 16: [name_ptr:4][flags:4][sell_price:4][desc_ptr:4]
TOOLS_TABLE_BASE    = 0x0EAB0C  # Stride 12: Herramientas
ARTICLES_TABLE_BASE = 0x0EFED4  # Stride 12: Artículos varios

# Nombres de cultivos en orden de tabla (index = crop_id)
CROP_NAMES = [
    "Turnip", "Potato", "Cucumber", "Strawberry", "Cabbage",
    "Tomato", "Corn", "Onion", "Pumpkin", "Pineapple",
    "Eggplant", "Carrot", "Sweet Potato", "Spinach", "Green Pepper",
]

SEED_NAMES = [
    "Turnip Seeds", "Potato Seeds", "Cucumber Seeds", "Strawberry Seeds", "Cabbage Seeds",
    "Tomato Seeds", "Corn Seeds", "Onion Seeds", "Pumpkin Seeds", "Pineapple Seeds",
    "Eggplant Seeds", "Carrot Seeds", "Sweet Potato Seeds", "Spinach Seeds", "Green Pepper Seeds",
    "Grass Seeds", "Moon Drop Seeds", "Pink Cat Seeds", "Magic Seeds", "Toy Flower Seeds",
]

# Datos de crecimiento extraídos del texto de ayuda del juego (0x10A8D0 area)
# Format: [stage_days, ...], regen_to_stage (-1 = no regen), season_mask
# season_mask: bit0=spring, bit1=summer, bit2=fall, bit3=winter
CROP_GROWTH_DATA = {
    #  name            stages     regen  season (bitmask)  harvest_count
    "Turnip":         ([2, 2],       -1,   0b0001,          1),
    "Potato":         ([3, 4],       -1,   0b0001,          1),
    "Cucumber":       ([4, 3, 2, 2],  1,   0b0001,          3),  # Returns to stage 1 (X)
    "Strawberry":     ([3, 3, 2, 2],  2,   0b0001,          3),  # Returns to stage 2 (Y)
    "Cabbage":        ([4, 5, 5],    -1,   0b0001,          1),
    "Tomato":         ([2, 2, 2, 3],  2,   0b0010,          4),  # Returns to stage 2 (Z)
    "Corn":           ([3, 4, 4, 3],  2,   0b0010,          3),
    "Onion":          ([3, 3, 3],    -1,   0b0010,          1),
    "Pumpkin":        ([3, 3, 3, 3], -1,   0b0010,          1),
    "Pineapple":      ([5, 5, 5, 5],  3,   0b0010,          5),
    "Eggplant":       ([3, 3, 3],     1,   0b0100,          3),
    "Carrot":         ([3, 4],       -1,   0b0100,          1),
    "Sweet Potato":   ([3, 2],       -1,   0b0100,          1),
    "Spinach":        ([2, 3],       -1,   0b0100,          1),
    "Green Pepper":   ([2, 1, 2, 2],  1,   0b0100,          3),
}

SEASON_NAMES = {0b0001: "Spring", 0b0010: "Summer", 0b0100: "Fall", 0b1000: "Winter",
                0b0111: "Spring/Summer/Fall", 0b0011: "Spring/Summer"}


class SeedItem:
    """Ítem de semilla de la tabla SEEDS_TABLE_BASE."""
    STRIDE = 12

    def __init__(self, index, offset, name, buy_price, desc):
        self.index = index
        self.offset = offset
        self.name = name
        self.buy_price = buy_price
        self.desc = desc

    def __repr__(self):
        return f"SeedItem({self.index}, '{self.name}', {self.buy_price}G)"


class HarvestItem:
    """Ítem cosechado de la tabla HARVEST_TABLE_BASE."""
    STRIDE = 16

    def __init__(self, index, offset, name, flags, sell_price, desc):
        self.index = index
        self.offset = offset
        self.name = name
        self.flags = flags
        self.sell_price = sell_price
        self.desc = desc
        # Decode flags
        self.harvest_count = (flags >> 8) & 0xFF   # byte 1 = stages/count
        self.regen_flag = (flags >> 16) & 0xFF      # 0xFF = no regen, 0xFE = regen

    def __repr__(self):
        return f"HarvestItem({self.index}, '{self.name}', {self.sell_price}G)"


class CropData:
    """Datos de crecimiento de un cultivo (extraídos del texto de ayuda)."""
    def __init__(self, name):
        self.name = name
        data = CROP_GROWTH_DATA.get(name)
        if data:
            self.stage_days, self.regen_to, self.season_mask, self.harvest_count = data
        else:
            self.stage_days = []
            self.regen_to = -1
            self.season_mask = 0b1111
            self.harvest_count = 1

    @property
    def total_days(self):
        return sum(self.stage_days)

    @property
    def num_stages(self):
        return len(self.stage_days)

    @property
    def season_name(self):
        return SEASON_NAMES.get(self.season_mask, f"0b{self.season_mask:04b}")

    @property
    def regrows(self):
        return self.regen_to >= 0

    def __repr__(self):
        return f"CropData('{self.name}', days={self.stage_days}, season={self.season_name})"


class CropParser:
    """Parser completo de semillas y cultivos de FoMT."""

    def __init__(self, project):
        self.project = project
        self.seeds = []
        self.harvests = []
        self.crops = []
        self._scan()

    def _read_str(self, gba_addr):
        if not (0x08000000 <= gba_addr <= 0x09000000):
            return ""
        offset = gba_addr & 0x01FFFFFF
        s = ""
        while offset < len(self.project.virtual_rom):
            b = self.project.virtual_rom[offset]
            if b == 0:
                break
            elif 32 <= b <= 126:
                s += chr(b)
            elif b == 0x0A:
                s += "[n]"
            elif b == 0xB1:
                s += "ñ"
            elif b == 0xB2:
                s += "Ñ"
            else:
                s += f"[{b:02x}]"
            offset += 1
        return s

    def _scan(self):
        """Escanea y carga todas las semillas y cultivos."""
        self._scan_seeds()
        self._scan_harvests()
        self._build_crop_data()

    def _scan_seeds(self):
        """Lee la tabla de semillas (stride=12)."""
        self.seeds.clear()
        base = SEEDS_TABLE_BASE
        i = 0
        while True:
            off = base + i * SeedItem.STRIDE
            raw = self.project.read_rom(off, 12)
            if not raw or len(raw) < 12:
                break
            name_ptr, buy_price, desc_ptr = struct.unpack_from('<III', raw)
            if not (0x08000000 <= name_ptr <= 0x081FFFFF):
                break
            name = self._read_str(name_ptr)
            desc = self._read_str(desc_ptr)
            self.seeds.append(SeedItem(i, off, name, buy_price, desc))
            i += 1
            if i > 100:  # Safety limit
                break

    def _scan_harvests(self):
        """Lee la tabla de cosechas (stride=16)."""
        self.harvests.clear()
        base = HARVEST_TABLE_BASE
        i = 0
        while True:
            off = base + i * HarvestItem.STRIDE
            raw = self.project.read_rom(off, 16)
            if not raw or len(raw) < 16:
                break
            name_ptr, flags, sell_price, desc_ptr = struct.unpack_from('<IIII', raw)
            if not (0x08000000 <= name_ptr <= 0x081FFFFF):
                break
            name = self._read_str(name_ptr)
            desc = self._read_str(desc_ptr)
            self.harvests.append(HarvestItem(i, off, name, flags, sell_price, desc))
            i += 1
            if i > 150:
                break

    def _build_crop_data(self):
        """Construye la lista de cultivos cruzando seeds, harvests y datos de crecimiento."""
        self.crops.clear()
        for name in CROP_NAMES:
            crop = CropData(name)
            # Link seed
            crop.seed = next((s for s in self.seeds if name in s.name), None)
            # Link harvest
            crop.harvest = next((h for h in self.harvests if h.name == name), None)
            self.crops.append(crop)

    def get_crop_by_name(self, name):
        return next((c for c in self.crops if c.name == name), None)

    # ─── Escritura de parches ───────────────────────────────────────────────

    def save_seed_buy_price(self, seed: SeedItem, new_price: int):
        """Cambia el precio de compra de una semilla."""
        self.project.write_patch(seed.offset + 4, struct.pack('<I', new_price & 0xFFFFFFFF))
        seed.buy_price = new_price

    def save_harvest_sell_price(self, harvest: HarvestItem, new_price: int):
        """Cambia el precio de venta de un cultivo cosechado."""
        self.project.write_patch(harvest.offset + 8, struct.pack('<I', new_price & 0xFFFFFFFF))
        harvest.sell_price = new_price

    def save_harvest_count(self, harvest: HarvestItem, new_count: int):
        """Cambia la cantidad de cosechas (byte 1 del campo flags)."""
        flags = harvest.flags
        flags = (flags & 0xFFFF00FF) | ((new_count & 0xFF) << 8)
        self.project.write_patch(harvest.offset + 4, struct.pack('<I', flags))
        harvest.flags = flags
        harvest.harvest_count = new_count

    def get_all_for_display(self):
        """Retorna lista de dicts para mostrar en la UI."""
        rows = []
        for crop in self.crops:
            row = {
                "Cultivo": crop.name,
                "Estación": crop.season_name,
                "Etapas": str(crop.stage_days),
                "Días Totales": crop.total_days,
                "Renace": "Sí" if crop.regrows else "No",
                "Precio Semilla": crop.seed.buy_price if crop.seed else "?",
                "Precio Cosecha": crop.harvest.sell_price if crop.harvest else "?",
                "Cosechas": crop.harvest_count,
            }
            rows.append(row)
        return rows
