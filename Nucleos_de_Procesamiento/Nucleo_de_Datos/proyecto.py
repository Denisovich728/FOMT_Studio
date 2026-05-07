import json
import os
import shutil
import binascii

from Nucleos_de_Procesamiento.Nucleo_de_Datos.super_lib import SuperLibrary
from Nucleos_de_Procesamiento.Nucleo_de_Eventos.eventos import FoMTEventParser
from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.objetos import ItemParser
from Nucleos_de_Procesamiento.Nucleo_de_Eventos.npcs import NpcParser
from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.tiendas import ShopParser
from Nucleos_de_Procesamiento.Nucleo_de_Eventos.horarios import ScheduleParser
from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.mapas import MapParser
from Nucleos_de_Procesamiento.Nucleo_de_Sonido.motor_sappy import SappyParser
from Nucleos_de_Procesamiento.Nucleo_de_Datos.gestor_memoria import MemoryManager

class FoMTProject:
    """
    Gestiona el estado completo de un proyecto modificado (Parches, Base ROM, y Configs).
    Aprende de los errores anteriores: nunca altera la ROM base hasta que le das a 'Compilar'.
    Mantiene los cambios virtualmente en Project_Data.json (como AdvanceMap).
    """
    def __init__(self):
        self.name = "My_Patch"
        self.base_rom_path = ""
        self.project_dir = ""
        self.game_version = "Unknown"
        self.is_mfomt = False
        self.base_rom_data = None
        
        # Virtual Memory Patches: keys are ROM addresses, values are bytes
        self.patches = {}
        self.next_free_space = 0x75C254 # Inicio del espacio libre verificado en FoMT (Después de Thomas)
        
        self.super_lib = None
        self.memory = MemoryManager(self) 
        self.item_parser = None
        self.event_parser = None
        self.npc_parser = None
        self.shop_parser = None
        self.schedule_parser = None
        self.map_parser = MapParser(self)
        self.sappy_engine = SappyParser(self)
        self.songs = []

    def step_1_detect_rom(self, rom_path, proj_dir=None):
        """Paso 1: Identificación básica y carga de binario."""
        self.base_rom_path = rom_path
        if proj_dir:
            self.project_dir = proj_dir
            self.name = os.path.basename(proj_dir)
            
        with open(self.base_rom_path, "rb") as f:
            self.base_rom_data = f.read()
            # Memoria Virtual: Un buffer que contiene la ROM + parches aplicados
            self.virtual_rom = bytearray(self.base_rom_data)
            
        header = self.base_rom_data[0:0xC0]
        game_name = header[0xA0:0xAC]
        if b"HARVESTMOGBA" in game_name:
            self.game_version = "Harvest Moon FoMT"
            self.is_mfomt = False
        elif b"HM MFOM USA\0" in game_name:
            self.game_version = "Harvest Moon MFoMT"
            self.is_mfomt = True
        else:
            raise ValueError("La ROM no es compatible con el FoMT Studio System.")
            
        self.super_lib = SuperLibrary(self.is_mfomt)
        self.memory = MemoryManager(self)
        
        # Aplicar parches existentes (si estamos cargando un .fsp)
        for offset, data in self.patches.items():
            self.virtual_rom[offset : offset + len(data)] = data
            
        # Inicialización dinámica post-parches
        self.super_lib.dynamic_init(self.virtual_rom)
            
        return self.game_version

    def step_2_scan_events(self):
        """Paso 2: Análisis de Mapas, NPCs y Eventos (Lógica)."""
        self.item_parser = ItemParser(self)
        self.event_parser = FoMTEventParser(self)
        self.npc_parser = NpcParser(self)
        self.shop_parser = ShopParser(self)
        self.schedule_parser = ScheduleParser(self)
        self.map_parser.scan_maps()
        return True

    def step_3_scan_graphics(self):
        """Paso 3: Escaneo profundo de firmas StanHash (Pesado)."""
        if self.super_lib:
            self.super_lib.scan_data_banks(self.base_rom_data)
        return len(self.super_lib.data_banks)

    def step_4_scan_audio(self):
        """Paso 4: Indexación de música Sappy (Pesado)."""
        self.songs = self.sappy_engine.scan_songs()
        return len(self.songs)

    def open_rom_session(self, rom_path):
        """
        Crea un proyecto de sesión automático al abrir una ROM.
        Evita bloqueos de archivo y organiza las ediciones por fecha.
        """
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Carpeta de sesión en Documentos
        docs_dir = os.path.join(os.path.expanduser("~"), "Documents", "FoMTStudio", "Sessions")
        proj_name = f"Session_{timestamp}"
        proj_dir = os.path.join(docs_dir, proj_name)
        
        if not os.path.exists(proj_dir):
            os.makedirs(proj_dir)
            
        self.create_new(rom_path, proj_dir)
        return proj_dir

    def create_new(self, rom_path, proj_dir):
        """
        Inicialización de un nuevo proyecto con aislamiento.
        Crea una copia de la ROM (volcado) en la carpeta del proyecto.
        Cualquier cambio posterior se guarda en el .fsp (capa virtual).
        """
        if not os.path.exists(proj_dir):
            os.makedirs(proj_dir)
            
        # 1. Volcado entero del hex (Copia de seguridad local)
        self.name = os.path.basename(proj_dir)
        local_rom_name = "source.gba"
        local_rom_path = os.path.join(proj_dir, local_rom_name)
        
        # IMPORTANTE: Cerrar cualquier handle si existiera (aunque aquí es nuevo)
        shutil.copy2(rom_path, local_rom_path)
        
        # 2. Configurar el proyecto para usar esta copia local
        self.project_dir = proj_dir
        self.base_rom_path = local_rom_path
        
        # 3. Identificación y carga inicial
        self.step_1_detect_rom(local_rom_path, proj_dir)
        
        # 4. Guardar archivo de proyecto inicial (.fsp)
        self.save()

    def load(self, fsp_path):
        """Carga el proyecto desde un archivo .fsp."""
        with open(fsp_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        self.name = data.get("name", "UnknownPatch")
        # Priorizamos la ROM local si existe
        self.project_dir = os.path.dirname(fsp_path)
        local_rom_path = os.path.join(self.project_dir, "source.gba")
        
        if os.path.exists(local_rom_path):
            self.base_rom_path = local_rom_path
        else:
            self.base_rom_path = data.get("base_rom", "")
            
        self.game_version = data.get("version", "Unknown")
        self.is_mfomt = data.get("is_mfomt", False)
        
        saved_patches = data.get("patches", {})
        self.patches = {int(k): bytes.fromhex(v) for k,v in saved_patches.items()}
        self.next_free_space = data.get("next_free_space", 0x75C244)
        
        if not os.path.exists(self.base_rom_path):
            raise FileNotFoundError(f"No se encontró la ROM base del proyecto: {self.base_rom_path}")
            
        return self.step_1_detect_rom(self.base_rom_path, self.project_dir)

    def save(self):
        fsp_path = os.path.join(self.project_dir, f"{self.name}.fsp")
        
        # Convertir bytes a hex para el JSON
        serial_patches = {str(k): v.hex() for k, v in self.patches.items()}
        
        data = {
            "name": self.name,
            "base_rom": self.base_rom_path,
            "version": self.game_version,
            "is_mfomt": self.is_mfomt,
            "next_free_space": self.next_free_space,
            "patches": serial_patches
        }
        
        with open(fsp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            
    def read_rom(self, offset, size):
        """Lee directamente del buffer de memoria virtual (Base + Parches)."""
        if not hasattr(self, 'virtual_rom'):
            return self.base_rom_data[offset : offset + size]
        return bytes(self.virtual_rom[offset : offset + size])

    def write_patch(self, offset, data: bytes):
        """Registra un cambio en la memoria virtual del proyecto."""
        # 1. Guardar en la lista de parches (para el JSON del .fsp)
        self.patches[offset] = data
        # 2. Sincronizar el buffer de memoria virtual para lecturas inmediatas
        if hasattr(self, 'virtual_rom'):
            self.virtual_rom[offset : offset + len(data)] = data

    # write_bytes es el alias esperado por save_warps_to_rom y MapHeader
    def write_bytes(self, offset: int, data: bytes):
        self.write_patch(offset, data)

    def decompress(self, offset: int) -> bytes:
        """
        Descomprime desde la ROM usando el motor BlueSpider (LZ77/Popuri).
        Reemplaza al viejo descomprimir_rom que producía basura.
        """
        from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.mapas import decompress_auto
        return decompress_auto(self.base_rom_data, offset)

    def compile_to_rom(self, export_path):
        """Aplica todos los parches virtuales a la ROM base y exporta un archivo GBA."""
        # Evitar copiar sobre sí mismo si el usuario elige source.gba por error
        if os.path.abspath(self.base_rom_path) == os.path.abspath(export_path):
            # No necesitamos copiar, solo escribir los parches (aunque es peligroso)
            # Pero para seguridad del usuario, lanzamos error
            raise PermissionError("No puedes exportar sobre la ROM base del proyecto (source.gba). Elige otro nombre.")
            
        shutil.copy2(self.base_rom_path, export_path)
        with open(export_path, "r+b") as f:
            for offset, patch_data in self.patches.items():
                f.seek(offset)
                f.write(patch_data)

    def allocate_free_space(self, size):
        """
        Asigna un bloque de memoria alineado a 4 bytes.
        Retorna el offset de inicio alineado.
        """
        # Asegurar que el inicio esté alineado a 4 bytes (multiplo de 4)
        start_offset = (self.next_free_space + 3) & ~3
        # El puntero del proyecto se mueve al final del bloque asignado, también alineado
        self.next_free_space = start_offset + ((size + 3) & ~3)
        return start_offset

    def overwrite_rom_directly(self, offset: int, data: bytes):
        """
        ¡PELIGRO!: Escribe directamente en el archivo ROM base.
        Útil para pruebas rápidas cuando el juego no está comprimido.
        También actualiza el buffer en memoria para consistencia.
        """
        # 1. Escribir en el archivo físico
        with open(self.base_rom_path, "r+b") as f:
            f.seek(offset)
            f.write(data)
            
        # 2. Sincronizar buffer en memoria
        if self.base_rom_data:
            # Los bytes en Python son inmutables, reconstruimos el buffer
            ba = bytearray(self.base_rom_data)
            ba[offset : offset + len(data)] = data
            self.base_rom_data = bytes(ba)
            
        print(f"Direct Overwrite: 0x{offset:08X} -> {len(data)} bytes escritos en la ROM base.")
