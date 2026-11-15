# ============================================================
# FOMT Studio - Gestor de Partidas Guardadas (.sav / SRAM)
# Soporta FoMT (AGB-A4N) y MFoMT (AGB-BFG)
# ============================================================

import os
import struct


class GestorSaves:
    """
    Lee y modifica archivos de guardado (.sav) de Harvest Moon FoMT y MFoMT.
    Mantiene compatibilidad con mapeo WRAM->SRAM y soporta selección de versión y slot.
    """

    VERSION_PROFILES = {
        "fomt": {
            "label": "Friends of Mineral Town (FoMT)",
            "slot_stride": 0x4000,
            "addrs": {
                "gold": 0x02004090,
                "stamina": 0x02004205,
                "fatigue": 0x02004206,
                "rucksack": 0x02004234,
                "house_size": 0x020027CC,
                "lumber": 0x020027D0,
                "year": 0x020025F8,
                "season": 0x020025FA,
                "day": 0x020025FB,
                "weather": 0x020025FC,
                "tool_exp_base": 0x02004210,
            },
        },
        "mfomt": {
            "label": "More Friends of Mineral Town (MFoMT)",
            "slot_stride": 0x4000,
            "addrs": {
                "gold": 0x02004090,
                "stamina": 0x02004205,
                "fatigue": 0x02004206,
                "rucksack": 0x02004234,
                "house_size": 0x020027CC,
                "lumber": 0x020027D0,
                "year": 0x020025F8,
                "season": 0x020025FA,
                "day": 0x020025FB,
                "weather": 0x020025FC,
                "tool_exp_base": 0x02004210,
            },
        },
    }

    TOOL_NAMES = [
        "Azada (Hoe)",
        "Hoz (Sickle)",
        "Hacha (Axe)",
        "Martillo (Hammer)",
        "Regadera (Watering Can)",
        "Caña (Fishing Rod)",
    ]

    def __init__(self, version: str = "fomt", slot: int = 0):
        self.save_data = bytearray()
        self.filepath = None
        self.version = "mfomt" if str(version).lower() == "mfomt" else "fomt"
        self.slot = max(0, min(1, int(slot)))

    def set_version(self, version: str):
        self.version = "mfomt" if str(version).lower() == "mfomt" else "fomt"

    def set_slot(self, slot: int):
        self.slot = max(0, min(1, int(slot)))

    def load_save(self, filepath: str) -> bool:
        if not filepath or not os.path.exists(filepath):
            return False
        with open(filepath, "rb") as f:
            self.save_data = bytearray(f.read())
        self.filepath = filepath
        return True

    def save_save(self, target_path: str = None) -> bool:
        out_path = target_path or self.filepath
        if not out_path or not self.save_data:
            return False
        with open(out_path, "wb") as f:
            f.write(self.save_data)
        self.filepath = out_path
        return True

    def get_sram_offset(self, ram_address: int) -> int:
        """Convierte la WRAM (0x02000000) a un offset lineal de SRAM con soporte de Slot."""
        base = ram_address - 0x02000000
        if self.slot == 1:
            stride = self.VERSION_PROFILES[self.version]["slot_stride"]
            if base + stride < len(self.save_data):
                return base + stride
        return base

    def _addr(self, key: str) -> int:
        return self.VERSION_PROFILES[self.version]["addrs"][key]

    def _read_uint8(self, offset: int) -> int:
        if 0 <= offset < len(self.save_data):
            return self.save_data[offset]
        return 0

    def _write_uint8(self, offset: int, val: int):
        if 0 <= offset < len(self.save_data):
            self.save_data[offset] = max(0, min(255, int(val)))

    def _read_uint16(self, offset: int) -> int:
        if 0 <= offset and offset + 2 <= len(self.save_data):
            return struct.unpack_from("<H", self.save_data, offset)[0]
        return 0

    def _write_uint16(self, offset: int, val: int):
        if 0 <= offset and offset + 2 <= len(self.save_data):
            struct.pack_into("<H", self.save_data, offset, max(0, min(65535, int(val))))

    def _read_uint32(self, offset: int) -> int:
        if 0 <= offset and offset + 4 <= len(self.save_data):
            return struct.unpack_from("<I", self.save_data, offset)[0]
        return 0

    def _write_uint32(self, offset: int, val: int):
        if 0 <= offset and offset + 4 <= len(self.save_data):
            struct.pack_into("<I", self.save_data, offset, max(0, min(0xFFFFFFFF, int(val))))

    # --- Propiedades del Jugador y Granja ---
    def get_player_gold(self) -> int:
        return self._read_uint32(self.get_sram_offset(self._addr("gold")))

    def set_player_gold(self, val: int):
        self._write_uint32(self.get_sram_offset(self._addr("gold")), val)

    def get_player_stamina(self) -> int:
        return self._read_uint8(self.get_sram_offset(self._addr("stamina")))

    def set_player_stamina(self, val: int):
        self._write_uint8(self.get_sram_offset(self._addr("stamina")), val)

    def get_player_fatigue(self) -> int:
        return self._read_uint8(self.get_sram_offset(self._addr("fatigue")))

    def set_player_fatigue(self, val: int):
        self._write_uint8(self.get_sram_offset(self._addr("fatigue")), val)

    def get_rucksack_level(self) -> int:
        return self._read_uint8(self.get_sram_offset(self._addr("rucksack")))

    def set_rucksack_level(self, val: int):
        self._write_uint8(self.get_sram_offset(self._addr("rucksack")), val)

    def get_house_size(self) -> int:
        return self._read_uint8(self.get_sram_offset(self._addr("house_size")))

    def set_house_size(self, val: int):
        self._write_uint8(self.get_sram_offset(self._addr("house_size")), val)

    def get_lumber(self) -> int:
        return self._read_uint16(self.get_sram_offset(self._addr("lumber")))

    def set_lumber(self, val: int):
        self._write_uint16(self.get_sram_offset(self._addr("lumber")), val)

    def get_year(self) -> int:
        return self._read_uint16(self.get_sram_offset(self._addr("year")))

    def set_year(self, val: int):
        self._write_uint16(self.get_sram_offset(self._addr("year")), val)

    def get_season(self) -> int:
        return self._read_uint8(self.get_sram_offset(self._addr("season")))

    def set_season(self, val: int):
        self._write_uint8(self.get_sram_offset(self._addr("season")), max(0, min(3, int(val))))

    def get_day(self) -> int:
        return self._read_uint8(self.get_sram_offset(self._addr("day")))

    def set_day(self, val: int):
        self._write_uint8(self.get_sram_offset(self._addr("day")), max(1, min(30, int(val))))

    def get_weather(self) -> int:
        return self._read_uint8(self.get_sram_offset(self._addr("weather")))

    def set_weather(self, val: int):
        self._write_uint8(self.get_sram_offset(self._addr("weather")), max(0, min(4, int(val))))

    def get_tool_exp(self, tool_idx: int) -> int:
        base = self._addr("tool_exp_base")
        return self._read_uint16(self.get_sram_offset(base + (tool_idx * 2)))

    def set_tool_exp(self, tool_idx: int, val: int):
        base = self._addr("tool_exp_base")
        self._write_uint16(self.get_sram_offset(base + (tool_idx * 2)), val)

    def get_summary(self) -> dict:
        return {
            "version": self.version,
            "slot": self.slot,
            "size_bytes": len(self.save_data),
            "gold": self.get_player_gold(),
            "stamina": self.get_player_stamina(),
            "fatigue": self.get_player_fatigue(),
            "rucksack": self.get_rucksack_level(),
            "house_size": self.get_house_size(),
            "lumber": self.get_lumber(),
            "year": self.get_year(),
            "season": self.get_season(),
            "day": self.get_day(),
            "weather": self.get_weather(),
        }
