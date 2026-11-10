# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa
# Mapeo Canónico de Nombres y Gráficos de Mapas de FoMT
# ============================================================
"""
fomt_map_names.py
══════════════════════════════════════════════════════════════
Mapeo canónico entre IDs de mapas de rutinas (GBA Action Struct),
nombres de áreas de Mineral Town de Fomt_Mapas.csv y cabeceras
del motor gráfico MapParser (BlueSpider / FoMT Map Header Table).
"""

from typing import Optional, Tuple, Dict, Any

# Mapeo de IDs base de mapa (base_map_id = map_id & 0xFF) a nombres verificados
CANONICAL_MAP_INFO: Dict[int, Dict[str, Any]] = {
    0x00: {
        "key": "Mothers_Hill_Middle",
        "name_es": "Colina Madre (Zona Media)",
        "name_en": "Mother's Hill (Middle)",
        "header_id": 14,
        "is_outdoor": True
    },
    0x01: {
        "key": "Mineral_Beach",
        "name_es": "Playa Mineral",
        "name_en": "Mineral Beach",
        "header_id": 8,
        "is_outdoor": True
    },
    0x02: {
        "key": "Farm",
        "name_es": "Granja del Jugador",
        "name_en": "Player's Farm",
        "header_id": 0,
        "is_outdoor": True
    },
    0x03: {
        "key": "Forest",
        "name_es": "Bosque de Gotz",
        "name_en": "Gotz's Forest",
        "header_id": 12,
        "is_outdoor": True
    },
    0x04: {
        "key": "Behind_Church",
        "name_es": "Jardín Trasero de la Iglesia",
        "name_en": "Behind Church",
        "header_id": 10,
        "is_outdoor": True
    },
    0x05: {
        "key": "North_Side_Town",
        "name_es": "Pueblo Norte",
        "name_en": "North Side Town",
        "header_id": 4,
        "is_outdoor": True
    },
    0x06: {
        "key": "Rose_Square",
        "name_es": "Plaza Rosa",
        "name_en": "Rose Square",
        "header_id": 2,
        "is_outdoor": True
    },
    0x07: {
        "key": "South_Side_Town",
        "name_es": "Pueblo Sur",
        "name_en": "South Side Town",
        "header_id": 6,
        "is_outdoor": True
    },
    0x08: {
        "key": "Mothers_Hill_Top",
        "name_es": "Cima de la Colina Madre",
        "name_en": "Mother's Hill (Peak)",
        "header_id": 16,
        "is_outdoor": True
    },
    0x09: {
        "key": "Horse_House",
        "name_es": "Establo del Caballo",
        "name_en": "Horse Stable",
        "header_id": 40,
        "is_outdoor": False
    },
    0x0A: {
        "key": "Poultry_Farm_House_Floor_01",
        "name_es": "Granja Avícola (Planta Baja / Tienda de Lillia)",
        "name_en": "Poultry Farm (Floor 1)",
        "header_id": 44,
        "is_outdoor": False
    },
    0x0B: {
        "key": "Poultry_Farm_House_Floor_02",
        "name_es": "Granja Avícola (Planta Alta / Habitaciones)",
        "name_en": "Poultry Farm (Floor 2)",
        "header_id": 45,
        "is_outdoor": False
    },
    0x0C: {
        "key": "Church",
        "name_es": "Iglesia de Carter",
        "name_en": "Carter's Church",
        "header_id": 31,
        "is_outdoor": False
    },
    0x0D: {
        "key": "Zack_House",
        "name_es": "Casa de Zack (Playa)",
        "name_en": "Zack's House",
        "header_id": 28,
        "is_outdoor": False
    },
    0x0E: {
        "key": "Ellen_House",
        "name_es": "Casa de Ellen y Stu",
        "name_en": "Ellen's House",
        "header_id": 51,
        "is_outdoor": False
    },
    0x0F: {
        "key": "Jeff_Shop",
        "name_es": "Supermercado de Jeff",
        "name_en": "Jeff's Supermarket",
        "header_id": 25,
        "is_outdoor": False
    },
    0x10: {
        "key": "Jeff_Shop_Back_Room",
        "name_es": "Supermercado (Trastienda y Sala)",
        "name_en": "Supermarket (Back Room)",
        "header_id": 26,
        "is_outdoor": False
    },
    0x11: {
        "key": "Chicken_House_1",
        "name_es": "Gallinero de la Granja",
        "name_en": "Chicken Coop",
        "header_id": 36,
        "is_outdoor": False
    },
    0x12: {
        "key": "Mountain_House",
        "name_es": "Cabaña de la Montaña (Refugio)",
        "name_en": "Mountain Cottage",
        "header_id": 53,
        "is_outdoor": False
    },
    0x13: {
        "key": "Mineral_Clinic_Floor_01",
        "name_es": "Clínica Mineral (Planta Baja / Consulta)",
        "name_en": "Mineral Clinic (Floor 1)",
        "header_id": 29,
        "is_outdoor": False
    },
    0x14: {
        "key": "Mineral_Clinic_Floor_02",
        "name_es": "Clínica Mineral (Planta Alta / Cuartos)",
        "name_en": "Mineral Clinic (Floor 2)",
        "header_id": 30,
        "is_outdoor": False
    },
    0x15: {
        "key": "Doug_Inn_Floor_01",
        "name_es": "Posada de Doug (Taberna / Planta Baja)",
        "name_en": "Doug's Inn (Floor 1)",
        "header_id": 22,
        "is_outdoor": False
    },
    0x16: {
        "key": "Doug_Inn_Back_Room",
        "name_es": "Posada de Doug (Cocina)",
        "name_en": "Doug's Inn (Kitchen)",
        "header_id": 23,
        "is_outdoor": False
    },
    0x17: {
        "key": "Doug_Inn_Floor_02",
        "name_es": "Posada de Doug (Habitaciones / Planta Alta)",
        "name_en": "Doug's Inn (Floor 2)",
        "header_id": 24,
        "is_outdoor": False
    },
    0x18: {
        "key": "Mary_Library_Floor_01",
        "name_es": "Biblioteca de Mary (Planta Baja)",
        "name_en": "Mary's Library (Floor 1)",
        "header_id": 32,
        "is_outdoor": False
    },
    0x19: {
        "key": "Mary_Library_Floor_02",
        "name_es": "Biblioteca de Mary (Planta Alta)",
        "name_en": "Mary's Library (Floor 2)",
        "header_id": 33,
        "is_outdoor": False
    },
    0x1A: {
        "key": "Basil_House_Floor_01",
        "name_es": "Casa de Basil (Planta Baja)",
        "name_en": "Basil's House (Floor 1)",
        "header_id": 34,
        "is_outdoor": False
    },
    0x1B: {
        "key": "Basil_House_Floor_02",
        "name_es": "Casa de Basil (Planta Alta / Estudio)",
        "name_en": "Basil's House (Floor 2)",
        "header_id": 35,
        "is_outdoor": False
    },
    0x1C: {
        "key": "Harvest_Sprites_House",
        "name_es": "Cabaña de los Duendes de la Cosecha",
        "name_en": "Harvest Sprites' Hut",
        "header_id": 52,
        "is_outdoor": False
    },
    0x1D: {
        "key": "Farm_House_3",
        "name_es": "Casa Grande de la Granja (Vivienda del Jugador / Casada)",
        "name_en": "Player's Farm House (LV3 / Married)",
        "header_id": 43,
        "is_outdoor": False
    },
    0x1E: {
        "key": "Thomas_House",
        "name_es": "Casa del Alcalde Thomas",
        "name_en": "Mayor Thomas' House",
        "header_id": 50,
        "is_outdoor": False
    },
    0x1F: {
        "key": "Aja_Winery_Floor_01",
        "name_es": "Bodega Aja (Mostrador / Tienda de Vino)",
        "name_en": "Aja Winery (Floor 1)",
        "header_id": 18,
        "is_outdoor": False
    },
    0x20: {
        "key": "Aja_Winery_Floor_02",
        "name_es": "Bodega Aja (Planta Alta / Vivienda)",
        "name_en": "Aja Winery (Floor 2)",
        "header_id": 19,
        "is_outdoor": False
    },
    0x21: {
        "key": "Aja_Winery_Storage_Floor_01",
        "name_es": "Bodega Aja (Almacén de Barricas)",
        "name_en": "Aja Winery Storage",
        "header_id": 20,
        "is_outdoor": False
    },
    0x22: {
        "key": "Aja_Winery_Storage_Floor_00",
        "name_es": "Bodega Aja (Sótano / Cava de Envejecimiento)",
        "name_en": "Aja Winery Cellar",
        "header_id": 21,
        "is_outdoor": False
    },
    0x23: {
        "key": "Beach_House",
        "name_es": "Caseta de la Playa (Casa de Vacaciones)",
        "name_en": "Beach House",
        "header_id": 54,
        "is_outdoor": False
    },
    0x24: {
        "key": "Kai_Restaurant",
        "name_es": "Chiringuito de Kai (Playa)",
        "name_en": "Kai's Beach Shack",
        "header_id": 27,
        "is_outdoor": False
    },
    0x25: {
        "key": "Barn_01",
        "name_es": "Establo de Animales (Granja)",
        "name_en": "Barn",
        "header_id": 38,
        "is_outdoor": False
    },
    0x26: {
        "key": "Saibara_House",
        "name_es": "Herrería de Saibara",
        "name_en": "Saibara's Blacksmith",
        "header_id": 48,
        "is_outdoor": False
    },
    0x27: {
        "key": "Town_House",
        "name_es": "Casa de Campo del Pueblo",
        "name_en": "Town Cottage",
        "header_id": 55,
        "is_outdoor": False
    },
    0x28: {
        "key": "Gotz_House",
        "name_es": "Cabaña de Gotz (Carpintero)",
        "name_en": "Gotz's House",
        "header_id": 49,
        "is_outdoor": False
    },
    0x29: {
        "key": "Barley_House_Floor_01",
        "name_es": "Granja Yodel (Casa de Barley / P1)",
        "name_en": "Yodel Ranch House (Floor 1)",
        "header_id": 46,
        "is_outdoor": False
    },
    0x2A: {
        "key": "Barley_House_Floor_02",
        "name_es": "Granja Yodel (Habitaciones / P2)",
        "name_en": "Yodel Ranch House (Floor 2)",
        "header_id": 47,
        "is_outdoor": False
    },
    0x2B: {
        "key": "Mine_Lake",
        "name_es": "Mina del Lago (Cenote / Isla)",
        "name_en": "Lake Mine (Cenote)",
        "header_id": 60,
        "is_outdoor": False
    },
    0x2C: {
        "key": "Mothers_Hill_Top_2",
        "name_es": "Cima de la Colina Madre (Verano)",
        "name_en": "Mother's Hill (Peak Summer)",
        "header_id": 16,
        "is_outdoor": True
    },
    0x2D: {
        "key": "Mothers_Hill_Top_Rain",
        "name_es": "Cima de la Colina Madre (Lluvia)",
        "name_en": "Mother's Hill (Peak Rain)",
        "header_id": 16,
        "is_outdoor": True
    },
    0x2E: {
        "key": "Mothers_Hill_Top_Snow",
        "name_es": "Cima de la Colina Madre (Invierno)",
        "name_en": "Mother's Hill (Peak Snow)",
        "header_id": 17,
        "is_outdoor": True
    },
    0x2F: {
        "key": "Tutorial_Field",
        "name_es": "Campo de Tutorial",
        "name_en": "Tutorial Field",
        "header_id": 62,
        "is_outdoor": True
    },
    0x30: {
        "key": "Tutorial_Animals_Field",
        "name_es": "Pasto de Animales (Tutorial)",
        "name_en": "Tutorial Animal Field",
        "header_id": 63,
        "is_outdoor": True
    },
    0x31: {
        "key": "Tutorial_Chicken_House",
        "name_es": "Gallinero (Tutorial)",
        "name_en": "Tutorial Chicken Coop",
        "header_id": 65,
        "is_outdoor": False
    },
    0x32: {
        "key": "Tutorial_Barn",
        "name_es": "Establo (Tutorial)",
        "name_en": "Tutorial Barn",
        "header_id": 64,
        "is_outdoor": False
    },
    0x33: {
        "key": "Mine_Entrance",
        "name_es": "Entrada a la Mina de Primavera",
        "name_en": "Spring Mine Entrance",
        "header_id": 56,
        "is_outdoor": False
    },
    0x34: {
        "key": "Mine_Floor_1",
        "name_es": "Mina de Primavera (Piso 1)",
        "name_en": "Spring Mine (Floor 1)",
        "header_id": 57,
        "is_outdoor": False
    },
    0x35: {
        "key": "Mine_Floor_2",
        "name_es": "Mina (Piso 2)",
        "name_en": "Mine (Floor 2)",
        "header_id": 58,
        "is_outdoor": False
    },
    0x36: {
        "key": "Mine_Floor_3",
        "name_es": "Mina (Piso 3)",
        "name_en": "Mine (Floor 3)",
        "header_id": 59,
        "is_outdoor": False
    }
}

# Prefijos estacionales del byte alto
SEASON_NAMES = {
    0x00: "Primavera",
    0x04: "Verano",
    0x08: "Otoño",
    0x0C: "Invierno",
    0x10: "Interior / Todo el año"
}

SEASON_NAMES_I18N = {
    "es": {0x00: "Primavera", 0x04: "Verano", 0x08: "Otoño", 0x0C: "Invierno", 0x10: "Interior / Todo el año"},
    "en": {0x00: "Spring", 0x04: "Summer", 0x08: "Autumn", 0x0C: "Winter", 0x10: "Indoor / All Year"},
    "jp": {0x00: "春", 0x04: "夏", 0x08: "秋", 0x0C: "冬", 0x10: "室内 / 通年"},
    "de": {0x00: "Frühling", 0x04: "Sommer", 0x08: "Herbst", 0x0C: "Winter", 0x10: "Innen / Ganzjährig"},
    "ru": {0x00: "Весна", 0x04: "Лето", 0x08: "Осень", 0x0C: "Зима", 0x10: "Интерьер / Круглый год"},
    "zh": {0x00: "春季", 0x04: "夏季", 0x08: "秋季", 0x0C: "冬季", 0x10: "室内 / 全年"},
    "pt": {0x00: "Primavera", 0x04: "Verão", 0x08: "Outono", 0x0C: "Inverno", 0x10: "Interior / Ano todo"},
    "hi": {0x00: "वसंत", 0x04: "गर्मी", 0x08: "शरद", 0x0C: "सर्दी", 0x10: "भीतर / पूरे वर्ष"}
}

OFF_MAP_I18N = {
    "es": "Fuera de Mapa (Despawn / Limbo)",
    "en": "Off-Map (Despawn / Limbo)",
    "jp": "マップ外 (デスポーン / リンボ)",
    "de": "Außerhalb der Karte (Despawn / Limbo)",
    "ru": "Вне карты (Деспавн / Лимбо)",
    "zh": "地图外 (消失 / 虚空)",
    "pt": "Fora do Mapa (Despawn / Limbo)",
    "hi": "मानचित्र से बाहर (डिसपॉन / अधर)"
}

MINE_FLOOR_I18N = {
    "es": "Mina (Piso {floor})",
    "en": "Mine (Floor {floor})",
    "jp": "鉱山 (地下{floor}階)",
    "de": "Mine (Ebene {floor})",
    "ru": "Шахта (Этаж {floor})",
    "zh": "矿洞 (第{floor}层)",
    "pt": "Mina (Andar {floor})",
    "hi": "खदान (तल {floor})"
}

MAP_GENERIC_I18N = {
    "es": "Mapa 0x{base_id:02X}",
    "en": "Map 0x{base_id:02X}",
    "jp": "マップ 0x{base_id:02X}",
    "de": "Karte 0x{base_id:02X}",
    "ru": "Карта 0x{base_id:02X}",
    "zh": "地图 0x{base_id:02X}",
    "pt": "Mapa 0x{base_id:02X}",
    "hi": "मानचित्र 0x{base_id:02X}"
}


def unpack_fomt_map_id(map_id: int) -> Tuple[int, int]:
    """
    Desempaqueta un map_id de GBA (uint16) en (base_map_id, season_code).
    Ejemplo: 0x1007 -> (0x07, 0x10) [Pueblo Sur, Interior/Global]
             0x0C0B -> (0x0B, 0x0C) [Granja Avícola P2, Invierno]
    """
    raw_id = int(map_id) & 0xFFFF
    base_id = raw_id & 0xFF
    season_code = (raw_id >> 8) & 0xFF
    return base_id, season_code


def get_map_display_name(map_id: int, include_season: bool = False, lang: str = "es") -> str:
    """
    Retorna el nombre formal, exacto y amigable para el usuario según el idioma solicitado.
    Ejemplo: "[07] Pueblo Sur" o "[07] South Side Town"
    """
    raw_id = int(map_id) & 0xFFFF
    base_id, season_code = unpack_fomt_map_id(map_id)
    lang_key = lang.lower() if lang else "es"

    # Detección de estado Despawn / Fuera de Mapa (bit 9 o valor canónico 0x0234 / 0x0634)
    if (raw_id & 0x200) or (base_id == 0x34 and raw_id in (0x0234, 0x0634)):
        off_text = OFF_MAP_I18N.get(lang_key, OFF_MAP_I18N.get("en", OFF_MAP_I18N["es"]))
        return f"[{base_id:02X}] {off_text}"

    info = CANONICAL_MAP_INFO.get(base_id)
    
    if info:
        name = info.get(f"name_{lang_key}") or info.get("name_en") or info.get("name_es", f"Map 0x{base_id:02X}")
    elif 0x34 <= base_id <= 0x62:
        floor_num = base_id - 0x34 + 1
        floor_tmpl = MINE_FLOOR_I18N.get(lang_key, MINE_FLOOR_I18N.get("en", MINE_FLOOR_I18N["es"]))
        name = floor_tmpl.format(floor=floor_num)
    else:
        map_tmpl = MAP_GENERIC_I18N.get(lang_key, MAP_GENERIC_I18N.get("en", MAP_GENERIC_I18N["es"]))
        name = map_tmpl.format(base_id=base_id)

    seasons_dict = SEASON_NAMES_I18N.get(lang_key, SEASON_NAMES_I18N.get("en", SEASON_NAMES_I18N["es"]))
    if include_season and season_code != 0x10 and season_code in seasons_dict:
        return f"[{base_id:02X}] {name} ({seasons_dict[season_code]})"

    return f"[{base_id:02X}] {name}"


def get_map_header_id_for_event_map(map_id: int) -> Optional[int]:
    """
    Retorna el índice del MapHeader en MapParser que corresponde
    a este mapa de evento para renderizado visual de tiles.
    """
    base_id, season_code = unpack_fomt_map_id(map_id)
    info = CANONICAL_MAP_INFO.get(base_id)
    if not info:
        # Pisos de mina repetitivos (0x34 a 0x62) usan tipos de cabecera 57, 58, 59
        if 0x34 <= base_id <= 0x62:
            return 57 + ((base_id - 0x34) % 3)
        return None

    h_id = info.get("header_id")
    # Para mapas exteriores en invierno, MapParser tiene la versión de invierno en h_id + 1
    if info.get("is_outdoor") and season_code == 0x0C and h_id is not None:
        return h_id + 1

    return h_id
