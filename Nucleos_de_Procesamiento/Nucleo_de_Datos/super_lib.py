# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.3.4)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
import os
import sys
from Nucleos_de_Procesamiento.Nucleo_de_Datos.Utilidades.rutas import get_data_path, get_resource_path
import re
import struct
import json
import multiprocessing
import concurrent.futures

def _scan_chunk_worker_wrapper(args):
    rom_data, start_idx, end_idx = args
    from Nucleos_de_Procesamiento.Nucleo_de_Datos.Utilidades.compression import is_lz77_block, decompress_lz77
    from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.codec_tiles import bgr555_to_rgb
    
    local_banks = {}
    local_palette_cache = {}
    
    for offset in range(start_idx, end_idx, 4):
        # 1. DETECCIÓN LZ77
        if is_lz77_block(rom_data, offset):
            try:
                header = struct.unpack('<I', rom_data[offset:offset+4])[0]
                size = header >> 8
                if size < 32 or size > 0x100000: continue
                
                # Validación estricta con descompresión parcial
                data_decomp = decompress_lz77(rom_data[offset : offset + min(size*2+100, len(rom_data)-offset)])
                if len(data_decomp) != size: continue
                
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
            except: continue

        # 2. DETECCIÓN OAM
        if offset % 8 == 0:
            chunk = rom_data[offset:offset+6]
            if len(chunk) == 6:
                a0, a1, a2 = struct.unpack('<HHH', chunk)
                if (a0 & 0xFF) < 160 and (a1 & 0x1FF) < 240 and (a2 & 0x3FF) < 1024:
                    next_chunk = rom_data[offset+8:offset+14]
                    if len(next_chunk) == 6:
                        na0, na1, na2 = struct.unpack('<HHH', next_chunk)
                        if (na0 & 0xFF) < 160 and (na1 & 0x1FF) < 240:
                            if offset not in local_banks:
                                local_banks[offset] = {
                                    "size": 8,
                                    "type": "OAM_ENTRY",
                                    "name": f"SPRITE_PART_{offset:06X}"
                                }
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
            from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.ir import CallId, CallableShape, ValueType
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
        Detección de Bancos de Datos (StanHash signature scanner).
        Escanea la ROM buscando bloques LZ77, tablas OAM y secuencias de animación.
        ¡Ahora usando Multi-Processing para reducir tiempos astronómicos!
        """
        total_len = len(rom_data) - 8
        if total_len <= 0: return

        from Nucleos_de_Procesamiento.Nucleo_de_Datos.Utilidades.sistema import get_safe_worker_count
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
        except Exception as e:
            print(f"Alerta: Multiprocessing falló ({e}). Usando escaneo secuencial de respaldo...")
            # Fallback secuencial
            for chunk in chunks:
                local_banks, local_palette_cache = _scan_chunk_worker_wrapper(chunk)
                self.data_banks.update(local_banks)
                self.palette_cache.update(local_palette_cache)

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

    def get_baptized_name(self, event_id, script_content):
        """
        Retorna el nombre del evento para la UI (Formato: ID - Nombre).
        """
        ev_key = str(event_id).strip()
        if ev_key in self.custom_event_names:
            return f"{event_id:04d} - {self.custom_event_names[ev_key]}"
        
        return f"{event_id:04d} - Script {event_id:04d}"

    def get_event_name_hint(self, event_id):
        """
        Retorna solo el nombre o un genérico (usado en el IDE y punteros).
        """
        ev_key = str(event_id).strip()
        if ev_key in self.custom_event_names:
            return self.custom_event_names[ev_key]
        return f"Unknown_Event_{event_id:04d}"

    def get_map_name_hint(self, map_id):
        """Mapeo de nombres para los mapas (ID + Nombre personalizado)."""
        m_key = str(map_id)
        if m_key in self.custom_map_names:
            return f"[{map_id:03d}] {self.custom_map_names[m_key]}"
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
