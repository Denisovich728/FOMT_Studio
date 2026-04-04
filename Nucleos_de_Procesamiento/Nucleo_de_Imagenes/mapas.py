import struct
import os
from concurrent.futures import ThreadPoolExecutor

class MapHeader:
    def __init__(self, map_id, offset, data):
        self.map_id = map_id
        self.offset = offset
        
        # Estructura 24-byte (MFoMT/FoMT US)
        # 0: Layout Ptr (LZ77)
        # 4: Tileset Ptr (O Script ID en algunas versiones)
        # 8: Respawn/NPC/Warp Ptr
        # 12: Script Ptr 
        # 16: Width (byte)
        # 17: Height (byte)
        # 18: Tileset ID (byte)
        # 19: Name ID (byte)
        
        self.p_layout = struct.unpack('<I', data[0:4])[0]
        self.p_tileset = struct.unpack('<I', data[4:8])[0]
        self.p_npcs = struct.unpack('<I', data[8:12])[0]
        self.p_script = struct.unpack('<I', data[12:16])[0]
        
        self.width = data[16]
        self.height = data[17]
        self.tileset_id = data[18]
        self.name_id = data[19]
        
    @property
    def layout_offset(self): return self.p_layout & 0x01FFFFFF
    @property
    def script_offset(self): return self.p_script & 0x01FFFFFF
    @property
    def tileset_ptr(self): return self.p_tileset & 0x01FFFFFF

    def get_assets(self, project):
        """
        Lee el cabezal del tileset (16 bytes) para obtener punteros a paleta y gráficos.
        """
        if self.tileset_ptr == 0: return None, None
        
        try:
            ts_data = project.read_rom(self.tileset_ptr, 16)
            p_pal, p_gfx, p_col, p_anim = struct.unpack('<IIII', ts_data)
            
            pal_off = p_pal & 0x01FFFFFF
            gfx_off = p_gfx & 0x01FFFFFF
            
            return gfx_off, pal_off
        except:
            return None, None

class MapParser:
    """
    Extrae la lista completa de mapas de la ROM usando la tabla maestra de cabeceras.
    Soporta layouts LZ77 y datos Popuri (0x70).
    """
    def __init__(self, project):
        self.project = project
        self.maps = []
        self.stride = 24
        self._table_offset = None
        
    def _discover_table_offset(self):
        """Escanea la ROM buscando la tabla maestra de mapas por firma estructural."""
        rom_data = self.project.base_rom_data
        if not rom_data: return None
        
        # Primero intentamos offsets conocidos según versión (EU/US/JP/MFoMT)
        candidates = [0x11776C, 0x10FF2C, 0x10FF14, 0x127048, 0x117A00, 0x110200]
        for c in candidates:
            off = c & 0x01FFFFFF
            if off + 48 < len(rom_data):
                p_layout = struct.unpack('<I', rom_data[off:off+4])[0]
                if 0x08000000 <= p_layout < 0x09FFFFFF:
                    l_off = p_layout & 0x01FFFFFF
                    if l_off < len(rom_data) and rom_data[l_off] in [0x10, 0x70, 0x00]:
                        print(f"Map Discovery: Usando offset conocido 0x{off:X}")
                        return off

        # Escaneo profundo de punteros (Sólo si fallan los conocidos)
        print("Map Discovery: Iniciando escaneo profundo de firmas...")
        best_off = None
        max_count = 0
        
        # Empezamos a buscar después del primer 128KB (evitar offsets de boot)
        start_search = 0x020000 
        for i in range(start_search, len(rom_data) - 100, 4):
            p1 = struct.unpack('<I', rom_data[i:i+4])[0]
            if 0x08000000 <= p1 < 0x09FFFFFF:
                o1 = p1 & 0x01FFFFFF
                if o1 < len(rom_data) and rom_data[o1] in [0x10, 0x70]:
                    # Contamos cuántos registros válidos hay
                    valid_count = 0
                    for j in range(300):
                        curr_off = i + (j * self.stride)
                        if curr_off + 24 > len(rom_data): break
                        
                        # Validar Registro de 24 bytes
                        chunk = rom_data[curr_off : curr_off + 24]
                        p_layout = struct.unpack('<I', chunk[0:4])[0]
                        p_tileset = struct.unpack('<I', chunk[4:8])[0]
                        p_npcs = struct.unpack('<I', chunk[8:12])[0]
                        p_script = struct.unpack('<I', chunk[12:16])[0]
                        
                        w, h = chunk[16], chunk[17]
                        
                        # Heurística: Al menos 2 punteros válidos y dimensiones lógicas
                        valid_ptrs = 0
                        for p in [p_layout, p_npcs, p_script]:
                            if 0x08000000 <= p < 0x09FFFFFF: valid_ptrs += 1
                        
                        # Un mapa suele tener dimensiones entre 10 y 128 tiles
                        is_logical = (1 <= w <= 160) and (1 <= h <= 160)
                        
                        if valid_ptrs >= 2 and is_logical:
                            valid_count += 1
                        else:
                            if valid_count > 10: break # Fin de tabla probable
                            break
                    
                    if valid_count > max_count:
                        max_count = valid_count
                        best_off = i
                        if max_count > 60: break # Encontrada la tabla principal
        
        if best_off and max_count >= 20:
            print(f"Map Discovery: Mesa principal detectada en 0x{best_off:X} con {max_count} registros.")
            return best_off
            
        return None

    def scan_maps(self):
        self.maps = []
        rom_data = self.project.base_rom_data
        if not rom_data: return
        
        self._table_offset = self._discover_table_offset()
        if self._table_offset is None:
            print("MapParser Error: No se pudo localizar la tabla de mapas en esta ROM.")
            return

        # EXTRACCIÓN MULTI-HILO (Asíncrona)
        def _process_map(i):
            off = self._table_offset + (i * self.stride)
            if off + self.stride > len(rom_data): return None
            chunk = rom_data[off : off + self.stride]
            p_layout = struct.unpack('<I', chunk[0:4])[0]
            if not (0x08000000 <= p_layout < 0x09FFFFFF):
                if p_layout == 0 and i < 10: return "SKIP"
                return None
            return MapHeader(i, off, chunk)

        with ThreadPoolExecutor() as executor:
            # Procesamos hasta 256 posibles entradas en paralelo
            results = list(executor.map(_process_map, range(256)))
            
        for r in results:
            if r is None: break
            if r != "SKIP":
                self.maps.append(r)
            
        print(f"MapParser: Extraídos {len(self.maps)} mapas usando offset 0x{self._table_offset:X} (Tareas paralelas de GBA completadas).")

    # --- MÓDULO DE IMÁGENES: PAUSADO POR PETICIÓN DEL USUARIO ---
    # def decompress_image_assets(self):
    #     pass

    def get_layout(self, map_header):
        """Descomprime el layout del mapa usando el motor universal del proyecto."""
        try:
            return self.project.decompress(map_header.layout_offset)
        except Exception as e:
            print(f"Error decomprimiendo mapa {map_header.map_id}: {e}")
            return None
