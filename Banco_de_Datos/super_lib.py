# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v4.0.0)
# "The Greatest Show - Final Release"
# Desarrollado por: Denisovich728
# ============================================================
import os
import sys
from Banco_de_Datos.Utilidades.rutas import get_data_path, get_resource_path
import re
import struct
import json
import multiprocessing
import concurrent.futures

def _scan_chunk_worker_wrapper(args):
    rom_data, start_idx, end_idx = args
    from Banco_de_Datos.Utilidades.compression import decompress_lz77
    from Nucleos_Positronicos.Nucleo_de_Mapas.codec_tiles import bgr555_to_rgb
    
    local_banks = {}
    local_palette_cache = {}
    
    # Los assets de FoMT residen a partir de 0x130000 (despues del codigo ejecutable)
    actual_start = max(start_idx, 0x130000)
    if actual_start >= end_idx:
        return local_banks, local_palette_cache
    
    for offset in range(actual_start, end_idx, 4):
        # 1. Pre-check ultra rapido: Byte magico LZ77 (0x10)
        if rom_data[offset] != 0x10:
            continue

        # Filtro de cabecera LZ77 (tamano maximo estandar en VRAM/FoMT: 64KB)
        size = rom_data[offset+1] | (rom_data[offset+2] << 8) | (rom_data[offset+3] << 16)
        if size < 32 or size > 0x10000:
            continue

        # Primer byte de banderas: el bit 7 debe ser 0 (primer bloque literal)
        if rom_data[offset+4] & 0x80:
            continue

        try:
            # Validacion estricta con descompresion acotada
            data_decomp = decompress_lz77(rom_data[offset : offset + min(size*2+100, len(rom_data)-offset)])
            if len(data_decomp) != size:
                continue
            
            # Pre-cachear paletas
            if size in [32, 512]:
                colors = []
                for i in range(0, len(data_decomp), 2):
                    c16 = int.from_bytes(data_decomp[i:i+2], 'little')
                    colors.append(bgr555_to_rgb(c16))
                local_palette_cache[offset] = colors

            bank_type = "PALETTE" if size in [32, 512] else "TILESET" if size % 32 == 0 else "LAYOUT/DATA"
            local_banks[offset] = {
                "size": size,
                "type": bank_type,
                "name": f"{bank_type}_{offset:06X}"
            }
        except Exception:
            continue

    return local_banks, local_palette_cache

class SuperLibrary:
    """
    Base de conocimiento centralizada que gestiona los offsets, constantes y 
    mapeos de recursos para las diferentes versiones de la ROM.
    """
    
    # Offsets y Tamaños
    FOMT_CONSTANTS = {
        "MASTER_TABLE_OFFSET": 0x0F89D4,
        "EVENT_LIMIT": 1329,
        "ITEMS_LIMIT": 101,
        "NPC_TABLE_OFFSET": 0x104260,
        "NPC_LIMIT": 42,
        "GFoodInfo_OFFSET": 0x08111B90,
        "GToolInfo_OFFSET": 0x081116A8,
        "TOOLS_TABLE": (0x0, 0x0), # (start, end)
        "FOODS_TABLE": (0x0, 0x0),
        "MISC_TABLE": (0x0, 0x0),
    }
    
    MFOMT_CONSTANTS = {
        "MASTER_TABLE_OFFSET": 0x1014BC,
        "EVENT_LIMIT": 1416, 
        "ITEMS_LIMIT": 101,
        "NPC_TABLE_OFFSET": 0x104260 + 0x2BD58,
        "NPC_LIMIT": 42,
        "GFoodInfo_OFFSET": 0x0813D8E8,
        "GToolInfo_OFFSET": 0x0813D3A8,
        "TOOLS_TABLE": (0x0, 0x0),
        "FOODS_TABLE": (0x0, 0x0),
        "MISC_TABLE": (0x0, 0x0),
    }

    # Palabras clave extraídas para la identificación de personajes.
    CHARACTER_KEYWORDS = {
        "Ann": ["Ann", "Doug"],
        "Elli": ["Elli", "Ellen", "Stu", "Doctor"],
        "Karen": ["Karen", "Sasha", "Jeff"],
        "Mary": ["Mary", "Basil", "Anna"],
        "Popuri": ["Popuri", "Lillia", "Rick"],
        "Goddess": ["Harvest Goddess", "Goddess"],
        "Rivals": ["Cliff", "Gray", "Kai", "Doctor", "Rick"],
        "Townsfolk": ["Thomas", "Zack", "Won", "Barley", "May", "Manna", "Duke", "Carter", "Saibara", "Gotz", "Harris"],
        "Harvest Sprites": ["Chef", "Nappy", "Hoggy", "Bold", "Staid", "Aqua", "Timmid"]
    }

    def __init__(self, is_mfomt):
        self.is_mfomt = is_mfomt
        self.cfg = self.MFOMT_CONSTANTS if is_mfomt else self.FOMT_CONSTANTS
        self.known_callables = {}
        self.data_banks = {} # {Offset: (DecompSize, Name_Hint)}
        self.palette_cache = {} # {Offset: List[Tuple(r,g,b)]} para Previsualización Rápida
        self.portrait_map = {} # {Nombre: ID}
        self.map_map = {} # {Nombre: ID}
        self.anim_map = {} # {Nombre: ID}
        
        # Cargar mapeos externos (Editables por el usuario)
        self.custom_event_names = {}
        self.custom_map_names = {}
        self._load_extraction_pointers()
        self._load_custom_names()
        self._load_portraits()
        self._load_maps()
        self._load_animations()
        
        self._load_opcode_library()

    def dynamic_init(self, rom_data: bytes):
        """
        Escanea la ROM (o ROM virtual) para detectar dinámicamente la tabla maestra de eventos.
        Si la tabla ha sido reubicada, actualiza los offsets internos.
        También detecta el límite real de eventos según la tabla en la ROM.
        """
        if not self.is_mfomt:
            # Puntero maestro del motor FOMT a la tabla de eventos
            engine_ptr_offset = 0x03F89C
            
            # 1. Leer el puntero que usa el motor
            if engine_ptr_offset + 4 <= len(rom_data):
                ptr_val = struct.unpack_from('<I', rom_data, engine_ptr_offset)[0]
                
                # 2. Validar que sea un puntero ROM (0x08XXXXXX)
                if ptr_val >= 0x08000000 and ptr_val < 0x09000000:
                    # El puntero apunta a la "Base Fantasma" (offset - 4). 
                    # El espacio real de los eventos (Event 1) empieza +4 bytes adelante.
                    real_table_offset = (ptr_val & 0x01FFFFFF) + 4
                    self.cfg["MASTER_TABLE_OFFSET"] = real_table_offset
                    
                    # 3. Escanear el límite de eventos (hasta encontrar un puntero inválido)
                    idx = 0
                    max_events = 5000  # Límite de seguridad
                    while idx < max_events:
                        entry_ptr = real_table_offset + (idx * 4)
                        if entry_ptr + 4 > len(rom_data):
                            break
                            
                        val = struct.unpack_from('<I', rom_data, entry_ptr)[0]
                        # Validar si es un puntero razonable para GBA (o nulo)
                        if val != 0 and (val < 0x08000000 or val >= 0x09000000):
                            # Fin de la tabla (no es un puntero ROM)
                            break
                        idx += 1
                        
                    # 4. Actualizar el límite de eventos detectado
                    if idx > 0:
                        self.cfg["EVENT_LIMIT"] = idx
                        print(f"[*] SuperLibrary: Tabla de Eventos dinámicamente detectada en 0x{real_table_offset:06X} con {idx} eventos.")

    def _load_extraction_pointers(self):
        import csv
        mode = "mfomt" if self.is_mfomt else "fomt"
        prefix = "MFomt_" if self.is_mfomt else "Fomt_"
        csv_path = get_data_path(mode, f"{prefix}Punteros de extraccion.csv")
        
        if os.path.exists(csv_path):
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    t = row.get('type')
                    if t == 'PunterosScript':
                        base_offset = int(row['ofsetini'], 16)
                        end_offset = int(row['ofsetfin'], 16)
                        delta = 0x2BD58 if self.is_mfomt else 0
                        self.cfg["MASTER_TABLE_OFFSET"] = base_offset + delta
                        self.cfg["EVENT_LIMIT"] = ((end_offset - base_offset) // 4) + 1
                    elif t == 'npcs':
                        base_offset = int(row['ofsetini'], 16)
                        end_offset = int(row['ofsetfin'], 16)
                        delta = 0x2BD58 if self.is_mfomt else 0
                        self.cfg["NPC_TABLE_OFFSET"] = base_offset + delta
                        # Cada entrada NPC ocupa 8 bytes (puntero + script/flags)
                        self.cfg["NPC_LIMIT"] = ((end_offset - base_offset + 1) // 8)
                    elif t == 'Herramientas':
                        self.cfg["TOOLS_TABLE"] = (int(row['ofsetini'], 16), int(row['ofsetfin'], 16))
                    elif t == 'Comestibles':
                        self.cfg["FOODS_TABLE"] = (int(row['ofsetini'], 16), int(row['ofsetfin'], 16))
                    elif t == 'Variados':
                        self.cfg["MISC_TABLE"] = (int(row['ofsetini'], 16), int(row['ofsetfin'], 16))

    def _load_portraits(self):
        import csv
        mode = "mfomt" if self.is_mfomt else "fomt"
        prefix = "MFomt_" if self.is_mfomt else "Fomt_"
        csv_path = get_data_path(mode, f"{prefix}Portraits.csv")
        if os.path.exists(csv_path):
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row.get('id_portrait')
                    hex_val = row.get('hex_name')
                    if name and hex_val:
                        try:
                            self.portrait_map[name] = int(hex_val, 16)
                        except: pass

    def _load_maps(self):
        import csv
        mode = "mfomt" if self.is_mfomt else "fomt"
        prefix = "MFomt_" if self.is_mfomt else "Fomt_"
        csv_path = get_data_path(mode, f"{prefix}Mapas.csv")
        if os.path.exists(csv_path):
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, skipinitialspace=True)
                for row in reader:
                    name = row.get('Map_Name')
                    hex_val = row.get('Map_ID')
                    if name and hex_val:
                        try:
                            # Quitar espacios y manejar hex
                            self.map_map[name.strip()] = int(hex_val.strip(), 16)
                        except: pass

        # Cargar nombres canónicos traducidos a map_map para alias y autocompletado multilingüe
        try:
            from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.fomt_map_names import CANONICAL_MAP_INFO
            for mid, minfo in CANONICAL_MAP_INFO.items():
                for k, v in minfo.items():
                    if k.startswith("name_") and isinstance(v, str):
                        clean_v = v.strip()
                        if clean_v not in self.map_map:
                            self.map_map[clean_v] = mid
        except Exception:
            pass

    def _load_animations(self):
        import csv
        mode = "mfomt" if self.is_mfomt else "fomt"
        prefix = "MFomt_" if self.is_mfomt else "Fomt_"
        csv_path = get_data_path(mode, f"{prefix}Animations.csv")
        if os.path.exists(csv_path):
            with open(csv_path, 'r', encoding='utf-8') as f:
                # El formato es Nombre,ID (ej: Player_Stop_Down,0x000)
                reader = csv.reader(f)
                for row in reader:
                    if len(row) < 2: continue
                    name, hex_val = row[0].strip(), row[1].strip()
                    if name and hex_val:
                        try:
                            self.anim_map[name] = int(hex_val.replace("0x", ""), 16)
                        except: pass

    def _load_custom_names(self):
        mode = "mfomt" if self.is_mfomt else "fomt"
        prefix = "MFomt_" if self.is_mfomt else "Fomt_"
        mapas_path = get_data_path(mode, f"{prefix}Mapas.json")
        if os.path.exists(mapas_path):
            with open(mapas_path, 'r', encoding='utf-8') as f:
                try: self.custom_map_names = json.load(f)
                except: pass
                
        eventos_path = get_data_path(mode, f"{prefix}Eventos.json")
        if os.path.exists(eventos_path):
            with open(eventos_path, 'r', encoding='utf-8') as f:
                try: self.custom_event_names = json.load(f)
                except: pass

        # Cargar nombres de eventos canonicos por defecto desde CSV
        csv_filename = f"{prefix}Events_Listname.csv"
        self.load_event_names_from_csv(csv_filename)

    def load_event_names_from_csv(self, filename):
        """Carga nombres de eventos desde un archivo CSV (Formato: Event_Name,ID)."""
        import csv
        mode = "mfomt" if self.is_mfomt else "fomt"
        path = get_data_path(mode, filename)
        if not os.path.exists(path):
            print(f"Alerta: No se encontró el archivo {filename} en {path}.")
            return False
            
        try:
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                new_names = {}
                for row in reader:
                    name = row.get('Event_Name')
                    id_val = row.get('ID')
                    if name and id_val:
                        # Limpiar y guardar
                        new_names[str(id_val).strip()] = name.strip()
                
                if new_names:
                    self.custom_event_names.update(new_names)
                    print(f"Éxito: Se cargaron {len(new_names)} nombres de eventos desde {filename}.")
                    return True
            return False
        except Exception as e:
            print(f"Error cargando nombres de eventos desde CSV ({filename}): {e}")
            return False

    def _load_opcode_library(self):
        import csv
        mode = "mfomt" if self.is_mfomt else "fomt"
        filename = "MFomt_Lib.csv" if self.is_mfomt else "Fomt_Lib.csv"
        
        # Intentar en data y en docs
        lib_path = get_data_path(mode, filename)
        if not os.path.exists(lib_path):
            lib_path = get_resource_path(os.path.join("docs", filename))
            
        if not os.path.exists(lib_path): 
            print(f"Alerta: No se encontró la librería {filename} en data ni en docs.")
            return
            
        try:
            from Nucleos_Positronicos.Nucleo_de_Scripts.SlipSpace_Script_Engine.ir import CallId, CallableShape, ValueType
        except ImportError as e:
            print(f"Error de importación en SuperLibrary: {e}")
            return
            
        with open(lib_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                t = (row.get('Type') or '').strip()
                if t not in ('proc', 'func'):
                    continue
                
                hex_id_str = (row.get('Hex_ID') or '').strip()
                name = (row.get('Name') or '').strip()
                args_str = (row.get('Arguments') or '').strip()
                
                try:
                    call_id_val = int(hex_id_str, 16)
                except ValueError:
                    continue
                
                # Para SlipSpace_Engine, determinamos la forma
                args_count = 0 if not args_str else len([a for a in args_str.split(',') if a.strip()])
                param_types = [ValueType.integer() for _ in range(args_count)]
                
                if t == 'func':
                    shape = CallableShape.new_func(param_types)
                else:
                    shape = CallableShape.new_proc(param_types)
                    
                call_id = CallId(call_id_val)
                self.known_callables[call_id] = (name, shape)

    def scan_data_banks(self, rom_data: bytes):
        """
        Deteccion de Bancos de Datos (StanHash signature scanner).
        Escanea la ROM buscando bloques LZ77 y paletas graficas.
        Implementa cache persistente en disco por hash para carga ultra-veloz (<15ms).
        """
        total_len = len(rom_data) - 8
        if total_len <= 0: return

        # 1. Intento de carga desde cache persistente
        import hashlib
        import json
        rom_sig = hashlib.sha256(rom_data[:2048] + rom_data[-2048:] + len(rom_data).to_bytes(8, 'little')).hexdigest()[:16]
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
        cache_file = os.path.join(cache_dir, f"data_banks_{rom_sig}.json")

        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                self.data_banks = {int(k): v for k, v in cache_data.get("banks", {}).items()}
                self.palette_cache = {int(k): [tuple(c) for c in v] for k, v in cache_data.get("palettes", {}).items()}
                return
            except Exception:
                pass

        from Banco_de_Datos.Utilidades.sistema import get_safe_worker_count
        num_cores = get_safe_worker_count()
        chunk_size = (total_len // num_cores)
        chunk_size = (chunk_size // 4) * 4 # Alinear a 4 bytes

        chunks = []
        for i in range(num_cores):
            start = i * chunk_size
            end = start + chunk_size if i < num_cores - 1 else total_len
            chunks.append((rom_data, start, end))

        try:
            with concurrent.futures.ProcessPoolExecutor(max_workers=num_cores) as executor:
                for local_banks, local_palette_cache in executor.map(_scan_chunk_worker_wrapper, chunks):
                    self.data_banks.update(local_banks)
                    self.palette_cache.update(local_palette_cache)
        except Exception:
            for chunk in chunks:
                local_banks, local_palette_cache = _scan_chunk_worker_wrapper(chunk)
                self.data_banks.update(local_banks)
                self.palette_cache.update(local_palette_cache)

        # 2. Guardar en cache persistente para inicios instantaneos posteriores
        try:
            os.makedirs(cache_dir, exist_ok=True)
            cache_payload = {
                "banks": {str(k): v for k, v in self.data_banks.items()},
                "palettes": {str(k): v for k, v in self.palette_cache.items()}
            }
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_payload, f)
        except Exception:
            pass

    def find_references(self, rom_data: bytes, target_offset: int) -> list:
        """
        Busca todos los punteros en la ROM que apunten al offset especificado.
        Útil para saber qué mapas o tablas usan un gráfico.
        """
        target_ptr = target_offset | 0x08000000
        ptr_bytes = struct.pack('<I', target_ptr)
        
        references = []
        # Buscar en toda la ROM alineada a 4 bytes
        for i in range(0, len(rom_data) - 4, 4):
            if rom_data[i : i+4] == ptr_bytes:
                references.append(i)
        return references

    def get_portrait_data(self, portrait_id: int):
        """
        Calcula el offset del retrato basado en ID.
        Los retratos en FoMT suelen ser bloques LZ77 de 64x64 tiles.
        """
        # Offsets aproximados según versión
        p_table = 0x08112000 if not self.is_mfomt else 0x0813E000 # Offsets base para tablas de retratos
        # Cada entrada es un puntero (4 bytes)
        return p_table + (portrait_id * 4)

    def get_animation_sequence(self, anim_id: int) -> list:
        """
        Lee la secuencia de frames (IDs de OAM) para una animación específica.
        Implementación de la lógica detectada en animPool.
        """
        # Estructura simplificada para la v1.3.0
        # En la ROM real buscaríamos la tabla maestra de animaciones.
        return [{"oam_id": anim_id, "delay": 8}] # Placeholder 1-frame

    def get_translated_event_name(self, raw_name: str, lang: str = "es") -> str:
        """Traduce el nombre técnico de un evento al idioma solicitado para visualización en la UI."""
        if not raw_name:
            return ""
        lang_key = (lang or "es").lower()

        # Nombres de eventos conocidos del motor FoMT
        EVENT_TRANSLATIONS = {
            "Golden_Lumber_Retribition": {
                "es": "Retribución de Madera Dorada", "en": "Golden Lumber Retribution",
                "jp": "黄金の資材の制裁", "de": "Goldholz-Vergeltung", "ru": "Возмездие за золотой лесоматериал",
                "zh": "黄金木材惩罚", "pt": "Retribuição da Madeira Dourada", "hi": "गोल्डन लंबर प्रतिशोध"
            },
            "Mine_Descend_Level": {
                "es": "Descenso de Nivel en Mina", "en": "Mine Level Descent",
                "jp": "鉱山階層下降", "de": "Minen-Ebenenabstieg", "ru": "Спуск на этаж шахты",
                "zh": "矿洞下楼", "pt": "Descida de Nível na Mina", "hi": "खदान स्तर अवरोहण"
            },
            "Sleep_SUper_Engine": {
                "es": "Motor Nocturno (Dormir)", "en": "Sleep Engine (Bedtime)",
                "jp": "就寝エンジン", "de": "Schlafroutine-Engine", "ru": "Ночной движок (Сон)",
                "zh": "就寝引擎", "pt": "Motor Noturno (Dormir)", "hi": "नींद इंजन"
            },
            "Morning_Engine": {
                "es": "Motor Matutino (Despertar)", "en": "Morning Engine (Wakeup)",
                "jp": "朝のエンジン", "de": "Morgenroutine-Engine", "ru": "Утренний движок",
                "zh": "早晨引擎", "pt": "Motor Matinal (Acordar)", "hi": "सुबह का इंजन"
            },
            "Global_Events_Engine": {
                "es": "Motor de Eventos Globales", "en": "Global Events Engine",
                "jp": "グローバルイベントエンジン", "de": "Globale Event-Engine", "ru": "Движок глобальных событий",
                "zh": "全局事件引擎", "pt": "Motor de Eventos Globais", "hi": "वैश्विक इवेंट इंजन"
            },
            "Debug_Menu": {
                "es": "Menú de Depuración (Debug)", "en": "Debug Menu",
                "jp": "デバッグメニュー", "de": "Debug-Menü", "ru": "Меню отладки",
                "zh": "调试菜单", "pt": "Menu de Depuração", "hi": "डीबग मेनू"
            },
            "Shopping_Channel_TV": {
                "es": "Canal de Compras (TV)", "en": "Shopping Channel (TV)",
                "jp": "ショッピングチャンネル (TV)", "de": "Shopping-Kanal (TV)", "ru": "Телемагазин",
                "zh": "电视购物频道", "pt": "Canal de Compras (TV)", "hi": "शॉपिंग चैनल (TV)"
            },
            "Weather_TV": {
                "es": "Pronóstico del Tiempo (TV)", "en": "Weather Forecast (TV)",
                "jp": "天気予報 (TV)", "de": "Wetterbericht (TV)", "ru": "Прогноз погоды (ТВ)",
                "zh": "天气预报 (TV)", "pt": "Previsão do Tempo (TV)", "hi": "मौसम पूर्वानुमान (TV)"
            },
            "Weather_Disasters_TV": {
                "es": "Aviso de Desastres Meteorológicos (TV)", "en": "Weather Disaster Warnings (TV)",
                "jp": "気象災害警報 (TV)", "de": "Katastrophenwarnung (TV)", "ru": "Предупреждения о бурях (ТВ)",
                "zh": "气象灾害警报 (TV)", "pt": "Aviso de Desastres Meteorológicos (TV)", "hi": "मौसम आपदा चेतावनी (TV)"
            }
        }

        if raw_name in EVENT_TRANSLATIONS:
            trans = EVENT_TRANSLATIONS[raw_name]
            return trans.get(lang_key, trans.get("en", raw_name))

        # Rutinas de personalidad de aldeanos: [Name]_Personality
        if "_Personality" in raw_name or "_Personaliti" in raw_name:
            char_name = raw_name.replace("_Personality", "").replace("_Personaliti", "")
            # Normalización de typos en nombres del juego original
            char_fix = {
                "Lilia": "Lillia", "CLiff": "Cliff", "Cheff": "Chef", "Loun": "Lou"
            }.get(char_name, char_name)

            if lang_key == "es":
                return f"Personalidad de {char_fix}"
            elif lang_key == "jp":
                return f"{char_fix}の日常・性格"
            elif lang_key == "de":
                return f"{char_fix} Persönlichkeit"
            elif lang_key == "ru":
                return f"Личность {char_fix}"
            elif lang_key == "zh":
                return f"{char_fix}日常性格"
            elif lang_key == "pt":
                return f"Personalidade de {char_fix}"
            elif lang_key == "hi":
                return f"{char_fix} व्यक्तित्व"
            else:
                return f"{char_fix} Personality"

        # Programas de televisión (_TV o _Tv)
        if raw_name.endswith("_TV") or raw_name.endswith("_Tv") or "_TV" in raw_name:
            clean_tv = raw_name.replace("_TV", "").replace("_Tv", "").replace("_", " ")
            if lang_key == "es":
                return f"Programa de TV: {clean_tv}"
            elif lang_key == "jp":
                return f"テレビ番組: {clean_tv}"
            elif lang_key == "de":
                return f"TV-Sendung: {clean_tv}"
            elif lang_key == "ru":
                return f"ТВ-программа: {clean_tv}"
            elif lang_key == "zh":
                return f"电视节目: {clean_tv}"
            elif lang_key == "pt":
                return f"Programa de TV: {clean_tv}"
            elif lang_key == "hi":
                return f"टीवी शो: {clean_tv}"
            else:
                return f"TV Show: {clean_tv}"

        # Eventos no identificados
        if raw_name.startswith("Unknow_Event_") or raw_name.startswith("Unknown_Event_"):
            num_part = raw_name.split("_")[-1]
            if lang_key == "es":
                return f"Evento Desconocido {num_part}"
            elif lang_key == "jp":
                return f"未知のイベント {num_part}"
            elif lang_key == "de":
                return f"Unbekanntes Event {num_part}"
            elif lang_key == "ru":
                return f"Неизвестное событие {num_part}"
            elif lang_key == "zh":
                return f"未知事件 {num_part}"
            elif lang_key == "pt":
                return f"Evento Desconhecido {num_part}"
            elif lang_key == "hi":
                return f"अज्ञात इवेंट {num_part}"
            else:
                return f"Unknown Event {num_part}"

        return raw_name.replace("_", " ")

    def get_baptized_name(self, event_id, script_content=None, lang: str = "es"):
        """
        Retorna el nombre del evento para la UI (Formato: ID - Nombre) traducido según el idioma activo.
        """
        ev_key = str(event_id).strip()
        if ev_key in self.custom_event_names:
            raw_name = self.custom_event_names[ev_key]
            trans_name = self.get_translated_event_name(raw_name, lang=lang)
            return f"{event_id:04d} - {trans_name}"
        
        script_word = "Script"
        if lang == "es": script_word = "Guión"
        elif lang == "jp": script_word = "スクリプト"
        elif lang == "de": script_word = "Skript"
        elif lang == "ru": script_word = "Скрипт"
        elif lang == "zh": script_word = "脚本"
        return f"{event_id:04d} - {script_word} {event_id:04d}"

    def get_event_name_hint(self, event_id, lang: str = "es"):
        """
        Retorna solo el nombre o un genérico (usado en el IDE y punteros) en el idioma seleccionado.
        """
        ev_key = str(event_id).strip()
        if ev_key in self.custom_event_names:
            raw_name = self.custom_event_names[ev_key]
            return self.get_translated_event_name(raw_name, lang=lang)
        
        prefix = "Unknown_Event_"
        if lang == "es": prefix = "Evento_Desconocido_"
        elif lang == "jp": prefix = "未知イベント_"
        elif lang == "de": prefix = "Unbekanntes_Event_"
        elif lang == "ru": prefix = "Неизвестное_событие_"
        elif lang == "zh": prefix = "未知事件_"
        return f"{prefix}{event_id:04d}"

    def get_map_name_hint(self, map_id, lang: str = "es"):
        """Mapeo de nombres para los mapas (ID + Nombre personalizado o canónico en el idioma activo)."""
        m_key = str(map_id)
        if m_key in self.custom_map_names:
            return f"[{map_id:03d}] {self.custom_map_names[m_key]}"
        try:
            from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.fomt_map_names import get_map_display_name
            disp = get_map_display_name(map_id, include_season=False, lang=lang)
            if disp and not disp.startswith("Mapa 0x") and not disp.startswith("Map 0x"):
                return f"[{map_id:03d}] {disp}"
        except Exception:
            pass
        return f"[{map_id:03d}] Map {map_id:03d}"

    @property
    def table_offset(self): return self.cfg["MASTER_TABLE_OFFSET"]
    @property
    def event_limit(self): return self.cfg["EVENT_LIMIT"]
    @property
    def item_limit(self): return self.cfg["ITEMS_LIMIT"]
    @property
    def npc_table_offset(self): return self.cfg["NPC_TABLE_OFFSET"]
    @property
    def npc_limit(self): return self.cfg["NPC_LIMIT"]
