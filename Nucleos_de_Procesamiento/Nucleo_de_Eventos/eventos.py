import struct
from Perifericos.Traducciones.i18n import tr

# Intenta importar el núcleo copiado de porpurri (siendo ya una suite nativa y modular)
try:
    from Nucleos_de_Procesamiento.Nucleo_de_Eventos.porpurri_engine.bytecode.decoder import decode_script, disassemble, get_code_jumps
    from Nucleos_de_Procesamiento.Nucleo_de_Eventos.porpurri_engine.ir import *
    from Nucleos_de_Procesamiento.Nucleo_de_Eventos.porpurri_engine.decompiler.ins_decompiler import decompile_instructions
    from Nucleos_de_Procesamiento.Nucleo_de_Eventos.porpurri_engine.decompiler.formatter import format_script
    from Nucleos_de_Procesamiento.Nucleo_de_Eventos.porpurri_engine.decompiler.decorator import decorate_stmts_with_strings
except ImportError as e:
    # Fallback o Dummy temporal en caso de no correr en un módulo correctamente linkeado
    pass

class FoMTEventParser:
    """
    El orquestador definitivo.
    Usa el decodificador de `porpurri` y los diccionarios de la `SuperLibrary`
    para masticar los punteros maestros del GBA y mandarlos en texto al IDE, y viceversa.
    """
    def __init__(self, project):
        self.project = project
        self.super_lib = project.super_lib
        self.scanned_sizes = {} # event_id -> size

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
        else:
            raw_len = 0
            while raw_len < 10000:
                b = self.project.read_rom(script_off + raw_len, 1)
                raw_len += 1
                if b == b'\x0B': break
            chunk_data = self.project.read_rom(script_off, raw_len)
            riff_len = raw_len
            
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
                
            c_code = format_script(stmts)
            
            if event_id is not None:
                self.scanned_sizes[event_id] = riff_len
            
            lib_name = "lib_mfomt.txt" if self.project.is_mfomt else "lib_fomt.txt"
            output = [
                f"// Porpurri Core Decompiler Output",
                f"// Offset: 0x{script_off:08X} | Hint: {hint or 'Unknown'}",
                f"// =========================================\n",
                f"#include \"{lib_name}\"\n",
                f"script {event_id if event_id is not None else 'ROM'} {hint or 'Script'} {{"
            ]
            
            for line in c_code.splitlines():
                output.append(f"    {line}")
                    
            output.append(f"}}")
            return ("\n".join(output), stmts)
            
        except Exception as e:
            return (f"// Fallo catastrófico al descompilar: {e}\n// Offset 0x{script_off:X}", [])

    def get_last_scanned_size(self, event_id):
        return self.scanned_sizes.get(event_id, 0)

