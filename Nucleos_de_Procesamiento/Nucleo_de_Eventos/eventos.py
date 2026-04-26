import struct
import os
from Perifericos.Traducciones.i18n import tr

# Intenta importar el núcleo copiado de SlipSpace_Engine (siendo ya una suite nativa y modular)
try:
    from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.bytecode.decoder import decode_script, disassemble, get_code_jumps
    from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.ir import *
    from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.decompiler.ins_decompiler import decompile_instructions
    from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.decompiler.formatter import format_script
    from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.decompiler.decorator import decorate_stmts_with_strings, decorate_stmts_with_items
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
        self.scanned_sizes = {} # event_id -> size
        self._lib_scope = None # Cache para la librería de opcodes

    def get_event_count(self):
        """Retorna la magnitud definida por la Super Librera basada en la ROM (FoMT/MFoMT)."""
        return self.super_lib.event_limit
        
    def get_event_name_and_offset(self, event_id):
        """Devuelve el Hint Name (stanhash / nlp) y el offset decodificado de la tabla."""
        loc_rom = self.super_lib.table_offset + (event_id * 4)
        
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
                if b == b'\x0B': break
            chunk_data = self.project.read_rom(script_off, raw_len)
            total_len = raw_len
            
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
                
            # Decorar Give_Item con nombres reales
            if self.project.item_parser:
                items = self.project.item_parser.scan_foods()
                item_map = {itm.index: itm.name_str.strip('\x00') for itm in items}
                decorate_stmts_with_items(stmts, item_map, known_callables)
                
            c_code = format_script(stmts)
            
            # Guardar tamaño TOTAL para limpieza posterior (Repunteo) e In-Place
            if event_id is not None:
                self.scanned_sizes[event_id] = total_len
            else:
                # Si no hay ID (ej. MapScript), usamos el offset como clave
                self.scanned_sizes[script_off] = total_len
            
            # El decorador ya inyectó los 'const CONST_MESSAGE_0xHEX' al AST como código activo.
            # Añadimos un comentario informativo al principio para el usuario.
            lib_name = "lib_mfomt.csv" if self.project.is_mfomt else "lib_fomt.csv"
            output = [
                f"#include \"{lib_name}\"\n",
            ]
            
            output.append(f"script {event_id if event_id is not None else 'ROM'} {hint or 'Script'} {{")
            
            for line in c_code.splitlines():
                output.append(f"    {line}")
            
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
            lib_name = "lib_mfomt.csv" if self.project.is_mfomt else "lib_fomt.csv"
            lib_path = os.path.join("Nucleos_de_Procesamiento", "data", lib_name)
            
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

        # 2. Obtener mapa de ítems para resolución
        item_map = {}
        if self.project.item_parser:
            items = self.project.item_parser.scan_foods()
            item_map = {itm.name_str.strip('\x00'): itm.index for itm in items}

        # 3. Compilar
        lexer = Lexer(text)
        parser = Parser(lexer)
        temp_scope = ConstScope()
        scripts = parser.parse_program(temp_scope, allow_scripts=True)
        
        if not scripts:
            raise ValueError("No se encontró ningún bloque 'script' para compilar.")
            
        # Tomamos el primer script (el IDE suele editar uno a la vez)
        sid, sname, script_obj = scripts[0]
        
        # El compilador de SlipSpace ya tiene el hook para item_resolver que añadimos
        compiled_script = compile_script(script_obj, self._lib_scope, item_map)
        
        # FIX: target_size debe ser la suma de riff_len + 8 para representar el archivo RIFF completo
        # scanned_sizes ya contiene el valor total si es RIFF, o raw_len si no lo es.
        return encode_script(compiled_script, target_size=old_size)

    def get_last_scanned_size(self, key):
        """Puede recibir un event_id o un offset directo (para MapScripts)."""
        return self.scanned_sizes.get(key, 0)
