import os
import re
import struct
import json

class SuperLibrary:
    """
    Base de conocimiento monolítica (La Super Librería) que absorbe la 
    magia de Carter NLP, StanHash y los topes lógicos documentados por Mary.
    """
    
    # Offsets y Tamaños
    FOMT_CONSTANTS = {
        "MASTER_TABLE_OFFSET": 0x0F89D4,
        "EVENT_LIMIT": 1329,
        "ITEMS_LIMIT": 101,
        "GFoodInfo_OFFSET": 0x08111B90,
        "GToolInfo_OFFSET": 0x081116A8,
    }
    
    MFOMT_CONSTANTS = {
        "MASTER_TABLE_OFFSET": 0x1014BC,
        "EVENT_LIMIT": 1416, 
        "ITEMS_LIMIT": 101,
        "GFoodInfo_OFFSET": 0x0813D8E8,
        "GToolInfo_OFFSET": 0x0813D3A8,
    }

    # NLP Keywords extraídos de Carter.py
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
        
        # Cargar mapeos externos (Editables por el usuario)
        self.custom_event_names = {}
        self.custom_map_names = {}
        self._load_custom_names()
        
        self._parse_mary_bible()

    def _load_custom_names(self):
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        
        mapas_path = os.path.join(data_dir, "mapas.json")
        if os.path.exists(mapas_path):
            with open(mapas_path, 'r', encoding='utf-8') as f:
                try: self.custom_map_names = json.load(f)
                except: pass
                
        eventos_path = os.path.join(data_dir, "eventos.json")
        if os.path.exists(eventos_path):
            with open(eventos_path, 'r', encoding='utf-8') as f:
                try: self.custom_event_names = json.load(f)
                except: pass

    def _parse_mary_bible(self):
        lib_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "lib_fomt.txt")
        if not os.path.exists(lib_path): return
            
        try:
            from fomt_studio.core.parsers.porpurri_engine.compiler.lexer import Lexer
            from fomt_studio.core.parsers.porpurri_engine.compiler.parser import Parser, ParseError
            from fomt_studio.core.parsers.porpurri_engine.compiler.emitter import ConstScope
            from fomt_studio.core.parsers.porpurri_engine.ast import NameRefFunc, NameRefProc
            from fomt_studio.core.parsers.porpurri_engine.ir import CallId, CallableShape, ValueType
        except ImportError: return
            
        scope = ConstScope()
        with open(lib_path, 'r', encoding='utf-8') as f:
            code = f.read()
            
        lexer = Lexer(code)
        parser = Parser(lexer)
        try:
            parser.parse_program(scope, allow_scripts=False)
        except ParseError: pass
            
        for name, ref in scope.names.items():
            if isinstance(ref, NameRefFunc) or isinstance(ref, NameRefProc):
                self.known_callables[ref.call_id] = (name, ref.shape)

    def scan_data_banks(self, rom_data: bytes):
        """
        Detección de Bancos de Datos (StanHash signature scanner).
        Escanea la ROM buscando bloques LZ77 y los valida estrictamente para eliminar ruido.
        """
        from Nucleos_de_Procesamiento.Nucleo_de_Datos.Utilidades.compression import is_lz77_block, decompress_lz77
        
        # Escaneo de FIRMAS (Heurística de Stan)
        # GBA assets están alineados a 4 bytes.
        for offset in range(0, len(rom_data) - 4, 4):
            if is_lz77_block(rom_data, offset):
                try:
                    # Leemos el tamaño esperado según el header
                    header = struct.unpack('<I', rom_data[offset:offset+4])[0]
                    size = header >> 8
                    
                    # Filtro de tamaño: Evitar bloques vacíos o absurdamente grandes (> 1MB)
                    if size < 32 or size > 0x100000: continue
                    
                    # VALIDACIÓN ESTRICTA: Intentar descompresión parcial
                    # El ratio de compresión LZ77 GBA rara vez supera 1:10
                    chunk_limit = min(size * 2 + 100, len(rom_data) - offset)
                    chunk = rom_data[offset : offset + chunk_limit]
                    
                    try:
                        data = decompress_lz77(chunk)
                        if len(data) != size: continue # Tamaño inconsistente
                        
                        # Pre-cachear colores si es una paleta para el explorador
                        if size == 512 or size == 32:
                            from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.codec_tiles import bgr555_to_rgb
                            colors = []
                            for i in range(0, len(data), 2):
                                c16 = int.from_bytes(data[i:i+2], 'little')
                                colors.append(bgr555_to_rgb(c16))
                            self.palette_cache[offset] = colors
                            
                        # Categorización Avanzada (Anti-Ruido)
                        bank_type = "UNKNOWN"
                        if size in [32, 512, 1024]:
                            bank_type = "PALETTE"
                        elif size % 32 == 0 and size >= 128:
                            # Heurística: El 99% de los tilesets de FoMT usan el índice 0 para transparencia.
                            # Si no hay ceros, o hay muy pocos ceros en datos de gran tamaño, es probable que no sea una imagen.
                            zero_count = data.count(0)
                            if zero_count > (size // 16): # Al menos 6% de transparencia
                                bank_type = "TILESET"
                            else:
                                bank_type = "DATA (CODE/STATIC)"
                        else:
                            bank_type = "LAYOUT/MAP/DATA"
                            
                        self.data_banks[offset] = {
                            "size": size,
                            "type": bank_type,
                            "name": f"{bank_type}_{offset:06X}"
                        }
                    except:
                        continue # Error en descompresión = Basura/Código
                except:
                    continue

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

    def get_baptized_name(self, event_id, script_content):
        """
        Versión simplificada: Prioriza eventos.json. Fallback: ID + Script.
        (Removido el análisis de palabras clave por petición del usuario).
        """
        ev_key = str(event_id)
        if ev_key in self.custom_event_names:
            return f"[{event_id:04d}] {self.custom_event_names[ev_key]}"
        
        # Fallback simple
        return f"[{event_id:04d}] Script {event_id:04d}"

    def get_event_name_hint(self, event_id):
        """
        Versión rápida para el Explorador (Heurística básica).
        """
        ev_key = str(event_id)
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
