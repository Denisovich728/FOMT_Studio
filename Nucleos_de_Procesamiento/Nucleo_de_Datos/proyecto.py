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
from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.descompresor import descomprimir_rom
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

    def create_new(self, rom_path, proj_dir):
        """Legacy wrapper - ahora redirige a los steps."""
        self.step_1_detect_rom(rom_path, proj_dir)
        self.step_2_scan_events()
        self.step_3_scan_graphics()
        self.step_4_scan_audio()
        self.save()

    def load(self, fsp_path):
        """Carga básica del proyecto sin escaneos pesados inmediatos."""
        import json
        with open(fsp_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        self.name = data.get("name", "UnknownPatch")
        self.base_rom_path = data.get("base_rom", "")
        self.project_dir = os.path.dirname(fsp_path)
        self.game_version = data.get("version", "Unknown")
        self.is_mfomt = data.get("is_mfomt", False)
        
        saved_patches = data.get("patches", {})
        self.patches = {int(k): bytes.fromhex(v) for k,v in saved_patches.items()}
        
        if not os.path.exists(self.base_rom_path):
            raise FileNotFoundError(f"No se encontró la ROM base original: {self.base_rom_path}")
            
        # El resto de la carga se hace vía steps para permitir barra de progreso
        return self.step_1_detect_rom(self.base_rom_path)

    def save(self):
        fsp_path = os.path.join(self.project_dir, f"{self.name}.fsp")
        
        # Convertir bytes a hex para el JSON
        serial_patches = {str(k): v.hex() for k, v in self.patches.items()}
        
        data = {
            "name": self.name,
            "base_rom": self.base_rom_path,
            "version": self.game_version,
            "is_mfomt": self.is_mfomt,
            "patches": serial_patches
        }
        
        with open(fsp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            
    def read_rom(self, offset, size):
        """
        Lee bytes del proyecto. Si hay un parche VIRTUAL allí, retorna el parche, 
        de lo contrario lee de la Base ROM.
        """
        # Para simplificar en esta v1, si alguna parte de [offset : offset+size] está cacheada,
        # ensamblamos la mezcla.
        with open(self.base_rom_path, "rb") as f:
            f.seek(offset)
            base_data = bytearray(f.read(size))
            
        # Overlap pathes
        for p_offset, p_bytes in self.patches.items():
            if p_offset >= offset and p_offset < offset + size:
                rel = p_offset - offset
                p_len = min(len(p_bytes), size - rel)
                base_data[rel : rel + p_len] = p_bytes[:p_len]
            elif p_offset < offset and p_offset + len(p_bytes) > offset:
                rel = offset - p_offset
                w_len = min(len(p_bytes) - rel, size)
                base_data[0 : w_len] = p_bytes[rel : rel + w_len]
                
        return bytes(base_data)

    def write_patch(self, offset, data: bytes):
        """Registra un cambio en la memoria virtual del proyecto .fsp."""
        # Se guarda entero en el diccionario, la compilacion lo volcará a la ROM.
        self.patches[offset] = data
        
    def decompress(self, offset):
        """Usa el nuevo Nucleo de Imagenes / Descompresor centralizado."""
        return descomprimir_rom(self, offset)

    def compile_to_rom(self, export_path):
        """Aplica todos los parches virtuales a la ROM base y exporta un nuevo archivo GBA"""
        shutil.copy2(self.base_rom_path, export_path)
        with open(export_path, "r+b") as f:
            for offset, patch_data in self.patches.items():
                f.seek(offset)
                f.write(patch_data)
