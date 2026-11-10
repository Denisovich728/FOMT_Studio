# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v4.0.0)
# "The Greatest Show - Final Release"
# Desarrollado por: Denisovich728
# ============================================================
import json
import os
import shutil
import binascii

from Banco_de_Datos.super_lib import SuperLibrary
from Nucleos_Positronicos.Nucleo_de_Scripts.eventos import FoMTEventParser
from Nucleos_Positronicos.Nucleo_de_Items.objetos import ItemParser
from Nucleos_Positronicos.Nucleo_de_Aldeanos.npcs import NpcParser
from Nucleos_Positronicos.Nucleo_de_Aldeanos.tiendas import ShopParser
from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.horarios import ScheduleParser
from Nucleos_Positronicos.Nucleo_de_Mapas.mapas import MapParser
from Nucleos_Positronicos.Nucleo_de_Sonido.motor_sappy import SappyParser
from Banco_de_Datos.gestor_memoria import MemoryManager

class FoMTProject:
    """
    Gestiona el estado completo de un proyecto modificado (Parches, Base ROM, y Configs).
    Garantiza la integridad de la ROM original, operando sobre un buffer virtual hasta la compilación final.
    Mantiene los cambios de forma persistente en los archivos de proyecto (.fsp).
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
            
        # Detección por Header (0xA0 - 0xAF)
        header_16 = self.base_rom_data[0xA0:0xB0]
        
        if header_16 == b"HARVESTMOGBAA4NE":
            self.game_version = "Harvest Moon FoMT"
            self.is_mfomt = False
            print(f"[*] Detectada ROM: {self.game_version} (A0-AF: {header_16.hex().upper()})")
        elif header_16 == b"HM MFOM USA\0BFGE":
            self.game_version = "Harvest Moon MFoMT"
            self.is_mfomt = True
            print(f"[*] Detectada ROM: {self.game_version} (A0-AF: {header_16.hex().upper()})")
        else:
            # Fallback por si hay ligeras variaciones (ej: versiones EU)
            game_name = header_16[:12]
            if b"HARVESTMOGBA" in game_name:
                self.game_version = "Harvest Moon FoMT (Legacy Detect)"
                self.is_mfomt = False
            elif b"HM MFOM USA" in game_name:
                self.game_version = "Harvest Moon MFoMT (Legacy Detect)"
                self.is_mfomt = True
            else:
                raise ValueError(f"La ROM no es compatible. Header detectado: {header_16.hex().upper()}")
            
        self.super_lib = SuperLibrary(self.is_mfomt)
        self.memory = MemoryManager(self)
        
        # Aplicar parches existentes (si estamos cargando un .fsp)
        for offset, data in self.patches.items():
            self.virtual_rom[offset : offset + len(data)] = data
            
        # Validación e Inyección Obligatoria del Splash (Control de Integridad)
        from Banco_de_Datos.parche_splash import validar_e_inyectar_splash, assert_rom_signed
        validar_e_inyectar_splash(self)
        assert_rom_signed(self, 'step_1_detect_rom')
            
        # Inicialización dinámica post-parches
        self.super_lib.dynamic_init(self.virtual_rom)
            
        return self.game_version

    def step_2_scan_events(self):
        from Banco_de_Datos.parche_splash import assert_rom_signed
        assert_rom_signed(self, 'step_2_scan_events')
        """Paso 2: Análisis de Mapas, NPCs y Eventos (Lógica)."""
        self.item_parser = ItemParser(self)
        self.event_parser = FoMTEventParser(self)
        self.npc_parser = NpcParser(self)
        self.shop_parser = ShopParser(self)
        self.schedule_parser = ScheduleParser(self)
        self.map_parser.scan_maps()
        return True

    def step_3_scan_graphics(self):
        from Banco_de_Datos.parche_splash import assert_rom_signed
        assert_rom_signed(self, 'step_3_scan_graphics')
        """Paso 3: Escaneo profundo de firmas StanHash (Pesado)."""
        if self.super_lib:
            self.super_lib.scan_data_banks(self.base_rom_data)
        return len(self.super_lib.data_banks)

    def step_4_scan_audio(self):
        from Banco_de_Datos.parche_splash import assert_rom_signed
        assert_rom_signed(self, 'step_4_scan_audio')
        """Paso 4: Indexación de música Sappy (Pesado)."""
        self.songs = self.sappy_engine.scan_songs()
        return len(self.songs)

    def open_rom_session(self, rom_path):
        """
        Crea un proyecto de sesión automático al abrir una ROM.
        Evita bloqueos de archivo y organiza las ediciones por fecha.
        Ruta resuelta dinámicamente mediante get_sessions_dir().
        """
        import datetime
        from Banco_de_Datos.Utilidades.rutas import get_sessions_dir
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Carpeta de sesión dinámica
        docs_dir = get_sessions_dir()
        proj_name = f"Session_{timestamp}"
        proj_dir = os.path.join(docs_dir, proj_name)
        
        os.makedirs(proj_dir, exist_ok=True)
            
        self.create_new(rom_path, proj_dir)
        return proj_dir

    def create_new(self, rom_path, proj_dir):
        """
        Inicialización de un nuevo proyecto con aislamiento.
        Crea una copia de la ROM (volcado) en la carpeta del proyecto.
        Cualquier cambio posterior se guarda en el .fsp (capa virtual).
        """
        if not os.path.exists(proj_dir):
            os.makedirs(proj_dir, exist_ok=True)
            
        self.name = os.path.basename(proj_dir)
        local_rom_name = "source.gba"
        local_rom_path = os.path.join(proj_dir, local_rom_name)
        
        # Resolver rom_path de forma robusta si es un directorio o ruta incompleta
        resolved_src = rom_path
        if os.path.isdir(resolved_src):
            for fname in ["source.gba", f"{self.name}.gba"]:
                c = os.path.join(resolved_src, fname)
                if os.path.isfile(c):
                    resolved_src = c
                    break
            else:
                try:
                    for f in os.listdir(resolved_src):
                        if f.lower().endswith(".gba"):
                            resolved_src = os.path.join(resolved_src, f)
                            break
                except Exception:
                    pass

        if not os.path.isfile(resolved_src):
            resolved_alt = self._resolve_base_rom_path()
            if resolved_alt and os.path.isfile(resolved_alt):
                resolved_src = resolved_alt
            else:
                raise FileNotFoundError(f"No se pudo localizar el binario ROM base: '{rom_path}'")
        
        # Copia binaria segura con streams sin depender de bloqueos o permisos de shutil
        with open(resolved_src, "rb") as f_in:
            rom_data = f_in.read()
        with open(local_rom_path, "wb") as f_out:
            f_out.write(rom_data)
        
        # 2. Configurar el proyecto para usar esta copia local
        self.project_dir = proj_dir
        self.base_rom_path = local_rom_path
        
        # 3. Identificación y carga inicial
        self.step_1_detect_rom(local_rom_path, proj_dir)
        
        # 4. Guardar archivo de proyecto inicial (.fsp)
        self.save()

    def _resolve_base_rom_path(self):
        """Resuelve dinámicamente la ruta a la ROM base sin fallar por rutas absolutas obsoletas o sesiones borradas."""
        candidates = []
        if getattr(self, 'base_rom_path', None):
            candidates.append(self.base_rom_path)
            if os.path.isdir(self.base_rom_path):
                candidates.append(os.path.join(self.base_rom_path, "source.gba"))
                try:
                    for f in os.listdir(self.base_rom_path):
                        if f.lower().endswith(".gba"):
                            candidates.append(os.path.join(self.base_rom_path, f))
                except Exception:
                    pass

        if getattr(self, 'project_dir', None):
            candidates.append(os.path.join(self.project_dir, "source.gba"))
            if getattr(self, 'name', None):
                candidates.append(os.path.join(self.project_dir, f"{self.name}.gba"))
            try:
                if os.path.isdir(self.project_dir):
                    for f in os.listdir(self.project_dir):
                        if f.lower().endswith(".gba"):
                            candidates.append(os.path.join(self.project_dir, f))
            except Exception:
                pass

        try:
            from Banco_de_Datos.Utilidades.rutas import get_sessions_dir, get_default_workspace_dir
            sess_dir = get_sessions_dir()
            ws_dir = get_default_workspace_dir()
            
            if getattr(self, 'name', None):
                candidates.append(os.path.join(sess_dir, self.name, "source.gba"))
                candidates.append(os.path.join(ws_dir, self.name, "source.gba"))
            
            candidates.append(os.path.join(ws_dir, "source.gba"))
            candidates.append(os.path.join(ws_dir, "fomt.gba"))
            candidates.append(os.path.join(ws_dir, "mfomt.gba"))
            
            # Buscar en sesiones recientes (de más nueva a más vieja) que tengan una source.gba válida
            if os.path.isdir(sess_dir):
                subdirs = sorted(
                    [os.path.join(sess_dir, d) for d in os.listdir(sess_dir) if d.startswith("Session_")],
                    key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0,
                    reverse=True
                )
                for s in subdirs[:15]:
                    cand = os.path.join(s, "source.gba")
                    if os.path.isfile(cand):
                        candidates.append(cand)
        except Exception:
            pass

        # Buscar en entorno local y directorios de laboratorio
        for root in [os.getcwd(), r"J:\Laboratorio", r"J:\Laboratorio\FOMT_Studio", r"J:\Laboratorio\FOMT-MATCH-ENGINE"]:
            if os.path.isdir(root):
                candidates.append(os.path.join(root, "source.gba"))
                candidates.append(os.path.join(root, "fomt virgen.gba"))
                candidates.append(os.path.join(root, "MFOMT VIRGEN.gba"))
                candidates.append(os.path.join(root, "fomt.gba"))

        for c in candidates:
            if c and os.path.isfile(c) and os.path.getsize(c) >= 0x400000:
                return os.path.abspath(c)
        return getattr(self, 'base_rom_path', "")

    def load(self, fsp_path):
        """Carga el proyecto desde un archivo .fsp o directorio de proyecto con resolución dinámica."""
        from Banco_de_Datos.Utilidades.rutas import resolve_project_fsp_path
        
        resolved_path = resolve_project_fsp_path(fsp_path)
        if not resolved_path or not os.path.isfile(resolved_path):
            raise FileNotFoundError(
                f"No se pudo localizar el archivo de proyecto (.fsp) para la ruta especificada: '{fsp_path}'. "
                "Verifica que el archivo exista o selecciona la carpeta de sesión correspondiente."
            )
        
        fsp_path = resolved_path
        with open(fsp_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        self.name = data.get("name", os.path.splitext(os.path.basename(fsp_path))[0])
        self.project_dir = os.path.dirname(fsp_path)
        
        # 1. Priorizamos la ROM local del proyecto si existe
        local_rom_path = os.path.join(self.project_dir, "source.gba")
        rel_rom = data.get("relative_rom", "")
        if rel_rom:
            cand_rel = os.path.join(self.project_dir, rel_rom)
            if os.path.isfile(cand_rel):
                local_rom_path = cand_rel

        if os.path.isfile(local_rom_path):
            self.base_rom_path = local_rom_path
        else:
            raw_base = data.get("base_rom", "")
            if raw_base and os.path.isfile(raw_base):
                self.base_rom_path = raw_base
            else:
                self.base_rom_path = raw_base
                resolved = self._resolve_base_rom_path()
                if resolved and os.path.isfile(resolved):
                    self.base_rom_path = resolved
                    try:
                        with open(resolved, "rb") as f_src:
                            b_data = f_src.read()
                        with open(local_rom_path, "wb") as f_dst:
                            f_dst.write(b_data)
                        self.base_rom_path = local_rom_path
                    except Exception:
                        pass
            
        self.game_version = data.get("version", "Unknown")
        self.is_mfomt = data.get("is_mfomt", False)
        
        saved_patches = data.get("patches", {})
        self.patches = {int(k): bytes.fromhex(v) for k,v in saved_patches.items()}
        self.next_free_space = data.get("next_free_space", 0x75C244)
        
        if not os.path.exists(self.base_rom_path) or not os.path.isfile(self.base_rom_path):
            resolved = self._resolve_base_rom_path()
            if resolved and os.path.isfile(resolved):
                self.base_rom_path = resolved
                try:
                    with open(resolved, "rb") as f_src:
                        b_data = f_src.read()
                    with open(local_rom_path, "wb") as f_dst:
                        f_dst.write(b_data)
                    self.base_rom_path = local_rom_path
                except Exception:
                    pass
            else:
                raise FileNotFoundError(
                    f"No se pudo localizar ninguna ROM base para el proyecto '{self.name}'. "
                    f"Ruta registrada en el proyecto: '{self.base_rom_path}'"
                )
            
        return self.step_1_detect_rom(self.base_rom_path, self.project_dir)

    def save(self):
        fsp_path = os.path.join(self.project_dir, f"{self.name}.fsp")
        
        # Convertir bytes a hex para el JSON
        serial_patches = {str(k): v.hex() for k, v in self.patches.items()}
        
        data = {
            "name": self.name,
            "base_rom": self.base_rom_path,
            "relative_rom": "source.gba" if os.path.exists(os.path.join(self.project_dir, "source.gba")) else "",
            "version": self.game_version,
            "is_mfomt": self.is_mfomt,
            "next_free_space": self.next_free_space,
            "patches": serial_patches
        }
        
        with open(fsp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            
    def read_rom(self, offset, size):
        """Lee directamente del buffer de memoria virtual (Base + Parches)."""
        if offset is not None and offset >= 0x08000000:
            offset &= 0x01FFFFFF
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
        # 3. Sincronizar base_rom_data si existe
        if getattr(self, 'base_rom_data', None):
            ba = bytearray(self.base_rom_data)
            ba[offset : offset + len(data)] = data
            self.base_rom_data = bytes(ba)

    def save_rom(self, target_path=None):
        from Banco_de_Datos.parche_splash import is_rom_signed, inyectar_splash_y_firmar, assert_rom_signed
        if not is_rom_signed(self):
            inyectar_splash_y_firmar(self)
        assert_rom_signed(self, "ROM Export/Save")
        from Banco_de_Datos.parche_splash import assert_rom_signed
        assert_rom_signed(self, 'save_rom')
        """
        Escribe directamente todos los cambios acumulados en el archivo físico ROM base (o target_path).
        Permite que emuladores como mGBA ejecuten inmediatamente las modificaciones.
        """
        out_path = target_path or self._resolve_base_rom_path()
        if not out_path or not os.path.exists(out_path):
            return False
        with open(out_path, "r+b") as f:
            for offset, patch_data in self.patches.items():
                f.seek(offset)
                f.write(patch_data)
        if hasattr(self, 'virtual_rom'):
            self.base_rom_data = bytes(self.virtual_rom)
        print(f"[*] ROM física guardada en {out_path} ({len(self.patches)} parches aplicados).")
        return True

    # write_bytes es el alias esperado por save_warps_to_rom y MapHeader
    def write_bytes(self, offset: int, data: bytes):
        self.write_patch(offset, data)

    def decompress(self, offset: int) -> bytes:
        """
        Descomprime desde la ROM usando el motor BlueSpider (LZ77/ArcanoMarvelous).
        Reemplaza al viejo descomprimir_rom que producía basura.
        """
        from Nucleos_Positronicos.Nucleo_de_Mapas.mapas import decompress_auto
        return decompress_auto(self.base_rom_data, offset)

    def compile_to_rom(self, export_path):
        from Banco_de_Datos.parche_splash import is_rom_signed, inyectar_splash_y_firmar, assert_rom_signed
        if not is_rom_signed(self):
            inyectar_splash_y_firmar(self)
        assert_rom_signed(self, "ROM Export/Save")
        from Banco_de_Datos.parche_splash import assert_rom_signed
        assert_rom_signed(self, 'compile_to_rom')
        """Aplica todos los parches virtuales a la ROM base y exporta un archivo GBA."""
        export_path = os.path.abspath(export_path)
        # Normalizar si export_path es una carpeta o carece de extensión .gba
        if os.path.isdir(export_path) or export_path.endswith(("\\", "/")):
            os.makedirs(export_path, exist_ok=True)
            export_path = os.path.join(export_path, f"{getattr(self, 'name', 'Modded')}.gba")
        elif not os.path.splitext(export_path)[1]:
            export_path = export_path + ".gba"
            os.makedirs(os.path.dirname(export_path), exist_ok=True)
        else:
            os.makedirs(os.path.dirname(export_path), exist_ok=True)

        # Evitar copiar sobre sí mismo si el usuario elige source.gba por error
        resolved_base = self._resolve_base_rom_path()
        if resolved_base and os.path.isfile(resolved_base) and os.path.abspath(resolved_base) == export_path:
            raise PermissionError("No puedes exportar sobre la ROM base del proyecto (source.gba). Elige otro nombre.")

        # Si tenemos virtual_rom en memoria, escribir directamente (inmune a rutas base rotas o relativas)
        if hasattr(self, 'virtual_rom') and self.virtual_rom:
            # Sincronizar todos los parches virtuales acumulados
            for offset, patch_data in self.patches.items():
                self.virtual_rom[offset : offset + len(patch_data)] = patch_data
            with open(export_path, "wb") as f:
                f.write(self.virtual_rom)
            return export_path
        else:
            if not resolved_base or not os.path.isfile(resolved_base):
                raise FileNotFoundError(f"No se pudo localizar ninguna ROM base para compilar: {self.base_rom_path}")
            with open(resolved_base, "rb") as f_in:
                rom_bytes = bytearray(f_in.read())
            for offset, patch_data in self.patches.items():
                rom_bytes[offset : offset + len(patch_data)] = patch_data
            with open(export_path, "wb") as f_out:
                f_out.write(rom_bytes)
            return export_path

    def export_ips(self, export_path):
        from Banco_de_Datos.parche_splash import is_rom_signed, inyectar_splash_y_firmar, assert_rom_signed
        if not is_rom_signed(self):
            inyectar_splash_y_firmar(self)
        assert_rom_signed(self, "ROM Export/Save")
        from Banco_de_Datos.parche_splash import assert_rom_signed
        assert_rom_signed(self, 'export_ips')
        """Exporta los parches acumulados en el formato estándar IPS."""
        import struct
        # Si self.patches está vacío, calcular automáticamente el diff binario
        active_rom = getattr(self, 'virtual_rom', None) or getattr(self, 'base_rom_data', None)
        patches_to_export = dict(self.patches)
        if not patches_to_export and active_rom:
            clean_path = self._resolve_base_rom_path()
            clean_data = None
            if clean_path and os.path.isfile(clean_path):
                try:
                    with open(clean_path, "rb") as fc:
                        clean_data = fc.read()
                except Exception:
                    clean_data = None
            if clean_data and len(clean_data) > 0 and clean_data != active_rom:
                min_len = min(len(clean_data), len(active_rom))
                i = 0
                while i < min_len:
                    if clean_data[i] != active_rom[i]:
                        start = i
                        while i < min_len and clean_data[i] != active_rom[i]:
                            i += 1
                        patches_to_export[start] = bytes(active_rom[start:i])
                    else:
                        i += 1
                if len(active_rom) > min_len:
                    patches_to_export[min_len] = bytes(active_rom[min_len:])

        with open(export_path, "wb") as f:
            f.write(b"PATCH")
            for offset, data in sorted(patches_to_export.items()):
                # IPS soporta máximo archivos de 16MB (Offset 24 bits)
                if offset >= 0x1000000:
                    print(f"[!] Offset fuera del límite IPS: 0x{offset:08X}. Ignorando.")
                    continue
                
                # Partir datos si superan los 65535 bytes (Límite de bloque IPS)
                data_length = len(data)
                chunk_offset = 0
                while chunk_offset < data_length:
                    chunk_size = min(0xFFFF, data_length - chunk_offset)
                    chunk_data = data[chunk_offset:chunk_offset + chunk_size]
                    
                    # Evitar tamaño 0x0000 (Usado en IPS para codificación RLE)
                    if chunk_size == 0:
                        break

                    current_offset = offset + chunk_offset
                    # Escribir Offset (3 bytes, Big-Endian)
                    f.write(struct.pack('>I', current_offset)[1:4])
                    # Escribir Tamaño (2 bytes, Big-Endian)
                    f.write(struct.pack('>H', chunk_size))
                    # Escribir Datos
                    f.write(chunk_data)
                    
                    chunk_offset += chunk_size
                    
            f.write(b"EOF")

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
        También actualiza el buffer en memoria y el registro de parches para consistencia.
        """
        data_bytes = bytes(data)

        # 0. Registrar siempre en el diccionario de parches del proyecto (.fsp / compile_to_rom / export_ips)
        self.patches[offset] = data_bytes

        # 1. Escribir en el archivo físico
        rom_path = self.base_rom_path or self._resolve_base_rom_path()
        if rom_path and os.path.exists(rom_path):
            self.base_rom_path = rom_path
            with open(rom_path, "r+b") as f:
                f.seek(0, os.SEEK_END)
                end_pos = f.tell()
                if offset > end_pos:
                    f.write(b'\xFF' * (offset - end_pos))
                f.seek(offset)
                f.write(data_bytes)
            
        # 2. Sincronizar buffer en memoria
        if self.base_rom_data:
            ba = bytearray(self.base_rom_data)
            req_len = offset + len(data_bytes)
            if req_len > len(ba):
                ba.extend(b'\xFF' * (req_len - len(ba)))
            ba[offset : offset + len(data_bytes)] = data_bytes
            self.base_rom_data = bytes(ba)
            
        if hasattr(self, 'virtual_rom') and self.virtual_rom is not None:
            req_len = offset + len(data_bytes)
            if req_len > len(self.virtual_rom):
                self.virtual_rom.extend(b'\xFF' * (req_len - len(self.virtual_rom)))
            self.virtual_rom[offset : offset + len(data_bytes)] = data_bytes
            
        print(f"Direct Overwrite: 0x{offset:08X} -> {len(data_bytes)} bytes escritos en la ROM base.")
