# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.1.0)
# "The Imposibility Update"
# Desarrollado por: Denisovich728
# ============================================================
import struct
import os
import sys
from Nucleos_de_Procesamiento.Nucleo_de_Datos.Utilidades.rutas import get_data_path
from Perifericos.Traducciones.i18n import tr

# Intenta importar el núcleo copiado de SlipSpace_Engine (siendo ya una suite nativa y modular)
try:
    from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.bytecode.decoder import decode_script, disassemble, get_code_jumps
    from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.ir import *
    from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.decompiler.ins_decompiler import decompile_instructions
    from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.decompiler.formatter import format_script
    from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.decompiler.decorator import decorate_stmts_with_strings, decorate_stmts_with_items, decorate_stmts_with_characters, decorate_stmts_with_flags
except ImportError as e:
    # Fallback o Dummy temporal en caso de no correr en un módulo correctamente linkeado
    pass

class FoMTEventParser:
    """
    El orquestador definitivo.
    Usa el decodificador de `SlipSpace_Engine` y los diccionarios de la `SuperLibrary`
    para masticar los punteros maestros del GBA y mandarlos en texto al IDE, y viceversa.
    """
    def __init__(self, project):
        self.project = project
        self.super_lib = project.super_lib
        self.scanned_sizes = {}
        
        # Caché para optimizar escaneo masivo (ej: búsqueda global)
        self._cached_items = None
        self._cached_npcs = None
        self._lib_scope = None # Cache para la librería de opcodes

    def get_event_count(self):
        """Retorna la magnitud definida por la Super Librera basada en la ROM (FoMT/MFoMT)."""
        return self.super_lib.event_limit
        
    def get_event_name_and_offset(self, event_id):
        """Devuelve el Hint Name (stanhash / nlp) y el offset decodificado de la tabla."""
        # AJUSTE: El usuario indica que el primer evento es el ID 1, no el 0.
        loc_rom = self.super_lib.table_offset + ((event_id - 1) * 4)
        
        # Leemos el Master Pointer de 4 bytes
        ptr_data = self.project.read_rom(loc_rom, 4)
        ptr_val = struct.unpack('<I', ptr_data)[0]
        
        hint = self.super_lib.get_event_name_hint(event_id)
        
        # Punteros vacíos o desconocidos (no apuntan a la GBA real ~08000000)
        if ptr_val < 0x08000000 or ptr_val >= 0x09000000:
            return hint, None
            
        return hint, ptr_val & 0x01FFFFFF

    def decompile_to_ui(self, event_id):
        """Usa el ID para buscar el offset y descompilar."""
        hint, script_off = self.get_event_name_and_offset(event_id)
        return self.decompile_from_offset(script_off, event_id, hint)

    def decompile_from_offset(self, script_off, event_id=None, hint=None):
        """
        La piedra filosofal: Recibe un offset, lee el bloque (RIFF o Raw), lo pasa 
        al decodificador AST y lo transforma a texto.
        """
        if script_off is None or script_off == 0:
            return (f"// [ALERTA] Offset inválido o NULL.\n// No hay script para mostrar.", [])

        # Comprobamos la cabecera
        header = self.project.read_rom(script_off, 4)
        is_riff = (header == b'RIFF')
        
        chunk_data = b""
        if is_riff:
            riff_len_b = self.project.read_rom(script_off + 4, 4)
            riff_len = struct.unpack('<I', riff_len_b)[0]
            chunk_data = self.project.read_rom(script_off, riff_len + 8)
            total_len = riff_len + 8
        else:
            raw_len = 0
            while raw_len < 10000:
                b = self.project.read_rom(script_off + raw_len, 1)
                raw_len += 1
                if b == b'\x0B': 
                    # Escaneo de relleno posterior (00 o FF) para maximizar el espacio recuperable
                    while raw_len < 10000:
                        next_b = self.project.read_rom(script_off + raw_len, 1)
                        if next_b not in (b'\x00', b'\xFF'):
                            break
                        raw_len += 1
                    break
            chunk_data = self.project.read_rom(script_off, raw_len)
            total_len = raw_len
            
        # Guardar el tamaño detectado para el gestor de memoria (In-Place recompilation)
        key = event_id if event_id is not None else script_off
        self.scanned_sizes[key] = total_len
        
        try:
            if is_riff:
                ast_script = decode_script(chunk_data)
                instructions = ast_script.instructions
                strings = ast_script.strings
            else:
                jump_map = get_code_jumps(chunk_data)
                instructions = disassemble(chunk_data, jump_map, [])
                strings = []
                
            known_callables = self.super_lib.known_callables
            stmts = decompile_instructions(instructions, known_callables)
            
            if strings:
                decorate_stmts_with_strings(stmts, strings, known_callables)
            
            # Decorar ítems (Give_Item, Give_Food) - No dependen del bloque STR
            if self._cached_items is None and self.project.item_parser:
                self._cached_items = self.project.item_parser.scan_foods()
            
            if self._cached_items:
                item_map = {}
                food_map = {}
                tool_map = {}
                for itm in self._cached_items:
                    # Limpiar nombre igual que en el compilador para consistencia
                    name = itm.name_str.replace('\n', ' ').strip('\x00').strip()
                    if not name: name = f"Unknown_{itm.index}"
                    rom_addr = itm.base_offset + 0x08000000
                    if itm.category == "Artículo":
                        item_map[itm.index] = name
                    elif itm.category == "Consumible/Comida":
                        food_map[itm.index] = name
                    elif itm.category == "Herramienta":
                        tool_map[itm.index] = name
                decorate_stmts_with_items(stmts, item_map, food_map, tool_map, known_callables)
                
            # Decorar comandos de personajes con nombres reales (ID 1-based)
            if self.project.npc_parser:
                if self._cached_npcs is None:
                    self._cached_npcs = self.project.npc_parser.scan_npcs()
                
                if self._cached_npcs:
                    char_map = {npc.index + 1: npc.name_str.strip('\x00') for npc in self._cached_npcs}
                    candidate_map = {npc.index + 1: npc.name_str.strip('\x00') for npc in self._cached_npcs if npc.is_candidate}
                    
                    # Inversos de los mapas para el descompilador
                    portrait_map_inv = {v: k for k, v in self.super_lib.portrait_map.items()}
                    map_map_inv = {v: k for k, v in self.super_lib.map_map.items()}

                    # Cargar emotes y animaciones
                    mode = "mfomt" if self.project.is_mfomt else "fomt"
                    prefix = "MFomt_" if self.project.is_mfomt else "Fomt_"
                    emote_map = {}
                    emote_path = get_data_path(mode, f"{prefix}Emotes.csv")
                    if os.path.exists(emote_path):
                        with open(emote_path, 'r', encoding='utf-8') as f:
                            import csv
                            f.seek(0)
                            reader = csv.DictReader(f)
                            for row in reader:
                                emote_map[int(row['Emote_ID'], 16)] = row['Emote_Name']

                    anim_map = {v: k for k, v in self.super_lib.anim_map.items()}

                    decorate_stmts_with_characters(stmts, char_map, candidate_map, portrait_map_inv, map_map_inv, emote_map, anim_map, known_callables)

                # Decorar flags desde flags.csv
                flag_path = get_data_path(mode, f"{prefix}Flags.csv")
                if os.path.exists(flag_path):
                    with open(flag_path, 'r', encoding='utf-8') as f:
                        import csv
                        reader = csv.DictReader(f)
                        flag_map = {}
                        for row in reader:
                            f_id = row.get('flag_id')
                            f_name = row.get('Flag_name')
                            if f_id and f_name:
                                try:
                                    flag_map[int(f_id, 16)] = f_name
                                except: pass
                        if flag_map:
                            decorate_stmts_with_flags(stmts, flag_map, known_callables)
                
            c_code = format_script(stmts)
            
            # Guardar tamaño TOTAL para limpieza posterior (Repunteo) e In-Place
            if event_id is not None:
                self.scanned_sizes[event_id] = total_len
            else:
                # Si no hay ID (ej. MapScript), usamos el offset como clave
                self.scanned_sizes[script_off] = total_len
            
            # El decorador ya inyectó los 'const CONST_MESSAGE_0xHEX' al AST como código activo.
            # Añadimos un comentario informativo al principio para el usuario.
            lib_name = "MFomt_Lib.csv" if self.project.is_mfomt else "Fomt_Lib.csv"
            output = [
                f"#include \"{lib_name}\"\n",
            ]
            
            output.append(f"script {event_id if event_id is not None else 'ROM'} {hint or 'Script'} {{")
            
            for line in c_code.splitlines():
                output.append(line)
            
            output.append(f"}}")
            return ("\n".join(output), stmts)
            
        except Exception as e:
            import traceback
            return (f"// Error al descompilar: {e}\n{traceback.format_exc()}", [])

    def compile_text_to_bytecode(self, text, item_map=None, old_size=0):
        """
        Lee el texto del IDE y lo compila a un binario inyectable.
        """
        from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.compiler.lexer import Lexer
        from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.compiler.parser import Parser
        from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.compiler.emitter import compile_script
        from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.bytecode.encoder import encode_script
        from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.compiler.emitter import ConstScope

        # 1. Preparar librería de opcodes
        if not self._lib_scope:
            self._lib_scope = ConstScope()
            mode = "mfomt" if self.project.is_mfomt else "fomt"
            lib_name = "MFomt_Lib.csv" if self.project.is_mfomt else "Fomt_Lib.csv"
            
            # Usar la utilidad de rutas para encontrar el CSV
            lib_path = get_data_path(mode, lib_name)
            
            if os.path.exists(lib_path):
                # Leer la librería como un script de declaraciones (KW_FUNC/KW_PROC)
                with open(lib_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                import csv
                import io
                f_io = io.StringIO("".join(lines))
                reader = csv.reader(f_io)
                
                decl_code = ""
                for i, parts in enumerate(reader):
                    # Ignorar cabecera si existe
                    if i == 0 and any(h in parts for h in ["Type", "kind"]):
                        continue
                        
                    if len(parts) >= 4:
                        kind, h_id, d_id, name = parts[0:4]
                        if kind not in ["proc", "func"]: continue
                        
                        # Limpiar los argumentos (quitar comillas y espacios extras)
                        args_raw = parts[4] if len(parts) > 4 else ""
                        args = args_raw.strip('"').strip()
                        
                        decl_code += f"{kind} {h_id} {name}({args})\n"
                
                if decl_code:
                    lex = Lexer(decl_code)
                    par = Parser(lex)
                    par.parse_program(self._lib_scope, allow_scripts=False)

        # 2. Obtener mapa de ítems para resolución (Índice/Puntero/Dirección -> Nombre)
        item_map = {0: "ITEM_GIFT", 1: "FOOD_GIFT"} # Para etiquetas de contexto
        food_map = {0: "ITEM_GIFT", 1: "FOOD_GIFT"}
        tool_map = {}
        
        if self.project.item_parser:
            items = self.project.item_parser.scan_foods()
            for itm in items:
                name = itm.name_str.replace('\n', ' ').strip('\x00').strip()
                if not name: name = f"Unknown_{itm.index}"
                
                # Mapeamos por todas las posibles formas en que el juego referencia al item
                addr = itm.base_offset + 0x08000000
                
                if itm.category == "Artículo":
                    item_map[itm.index] = name
                    item_map[itm.name_ptr] = name
                    item_map[addr] = name
                    # Inverso para compilación
                    item_map[name] = itm.real_id
                elif itm.category == "Consumible/Comida":
                    food_map[itm.index] = name
                    food_map[itm.name_ptr] = name
                    food_map[addr] = name
                    food_map[name] = itm.real_id
                elif itm.category == "Herramienta":
                    tool_map[itm.index] = name
                    tool_map[itm.name_ptr] = name
                    tool_map[addr] = name
                    tool_map[itm.real_id] = name
                    tool_map[name] = itm.real_id
            
        char_map = {}
        candidate_map = {}
        if self.project.npc_parser:
            npcs = self.project.npc_parser.scan_npcs()
            # ID 1-based para personajes + Hardcode Player=0
            char_map["Player"] = 0
            char_map["PLAYER"] = 0
            for npc in npcs:
                name = npc.name_str.replace('\n', ' ').strip('\x00').strip()
                if not name: name = f"NPC_{npc.index + 1}"
                char_map[name] = npc.index + 1
                if npc.is_candidate:
                    candidate_map[name] = npc.index + 1

        # 3. Compilar
        lexer = Lexer(text)
        parser = Parser(lexer)
        temp_scope = ConstScope()
        scripts = parser.parse_program(temp_scope, allow_scripts=True)
        
        if not scripts:
            raise ValueError("No se encontró ningún bloque 'script' para compilar.")
            
        # Tomamos el primer script (el IDE suele editar uno a la vez)
        sid, sname, script_obj = scripts[0]
        
        # 3. Resolutores para el compilador (Nombre -> ID)
        mode = "mfomt" if self.project.is_mfomt else "fomt"
        prefix = "MFomt_" if self.project.is_mfomt else "Fomt_"
        emote_map_inv = {}
        emote_path = get_data_path(mode, f"{prefix}Emotes.csv")
        if os.path.exists(emote_path):
            with open(emote_path, 'r', encoding='utf-8') as f:
                import csv
                reader = csv.DictReader(f)
                for row in reader:
                    emote_map_inv[row['Emote_Name']] = int(row['Emote_ID'], 16)

        anim_map_inv = self.super_lib.anim_map

        compiled_script = compile_script(script_obj, self._lib_scope, item_map, food_map, tool_map, char_map, candidate_map, self.super_lib.portrait_map, self.super_lib.map_map, emote_map_inv, anim_map_inv)
        
        # FIX: target_size debe ser la suma de riff_len + 8 para representar el archivo RIFF completo
        # scanned_sizes ya contiene el valor total si es RIFF, o raw_len si no lo es.
        return encode_script(compiled_script)

    def get_last_scanned_size(self, key):
        """Puede recibir un event_id o un offset directo (para MapScripts)."""
        return self.scanned_sizes.get(key, 0)