# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.0.0)
# "The Imposibility Update"
# Desarrollado por: Denisovich728
# ============================================================
import os
import sys
import struct
import traceback
from typing import List, Tuple
from SlipSpace_Script_Engine.cli import build_library_scope

def _decompile_worker(args):
    i, script_data, known_callables, library_path, eventos_dir = args
    if not script_data:
        return i, True, None
        
    try:
        from SlipSpace_Script_Engine.cli import decode_script, decompile_instructions, format_script
        from SlipSpace_Script_Engine.decompiler.decorator import decorate_stmts_with_strings
        from SlipSpace_Script_Engine.decompiler.error import DecompileError
        
        # Decode binary
        script_ir = decode_script(script_data)
        
        # Decompile IR -> AST
        stmts = decompile_instructions(script_ir.instructions, known_callables)
        decorate_stmts_with_strings(stmts, script_ir.strings, known_callables)
        
        # AST -> Text
        out_code = format_script(stmts)
        
        # Save file
        file_path = os.path.join(eventos_dir, f"evento_{i:04d}.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"// Script {i}\n")
            if library_path:
                f.write(f'#include "{os.path.basename(library_path)}"\n\n')
            f.write(f"script {i} Event_{i:04d} {{\n")
            for line in out_code.splitlines():
                f.write("    " + line + "\n")
            f.write("}\n")
        return i, True, None
    except Exception as e:
        return i, False, str(e)


def extract_all_resources(rom_path: str, output_dir: str, library_path: str = None, update_callback=None):
    """
    Orchestrates the mass extraction of events and tables from the GBA ROM into the structured Recursos/ format.
    """
    import os
    import sys
    import struct
    import traceback
    from typing import List, Tuple
    from SlipSpace_Script_Engine.cli import build_library_scope
    
    # 1. Structure Folders
    recursos_dir = os.path.join(output_dir, "Recursos")
    eventos_dir = os.path.join(recursos_dir, "Eventos")
    tablas_dir = os.path.join(recursos_dir, "Tablas")
    
    os.makedirs(eventos_dir, exist_ok=True)
    os.makedirs(tablas_dir, exist_ok=True)
    
    # Read ROM
    try:
        with open(rom_path, 'rb') as f:
            rom_data = f.read()
    except Exception as e:
        if update_callback: update_callback(f"Error reading ROM: {e}")
        return False
        
    known_callables = {}
    if library_path and os.path.exists(library_path):
        try:
            scope = build_library_scope(library_path)
            from SlipSpace_Script_Engine.ast import NameRefFunc, NameRefProc
            for name, ref in scope.names.items():
                if isinstance(ref, NameRefFunc) or isinstance(ref, NameRefProc):
                    known_callables[ref.call_id] = (name, ref.shape)
            if update_callback: update_callback(f"Successfully loaded {len(known_callables)} library definitions.")
        except Exception as e:
            if update_callback: update_callback(f"Warning: Failed to load library {library_path}. Decompilation heuristic might suffer. ({e})")
            
    # --- Parche: Registro Dinámico de Opcodes ---
    from SlipSpace_Script_Engine.ir import CallId, CallableShape, ValueType
    if CallId(106) not in known_callables:
        known_callables[CallId(106)] = ("Func106", CallableShape.new_proc([]))
    if CallId(117) not in known_callables:
        known_callables[CallId(117)] = ("Func117", CallableShape.new_proc([ValueType.integer()]))
        
    # 2. Extract Event Scripts
    from SlipSpace_Script_Engine.cli import get_all_scripts
    
    if update_callback: update_callback(f"Buscando Scripts en ROM...")
    
    scripts = get_all_scripts(rom_data)
    
    if not scripts:
        if update_callback: update_callback("No se encontraron scripts. Revisa que sea un dump compatible.")
        return False
        
    import concurrent.futures
    import multiprocessing
    
    max_workers = multiprocessing.cpu_count()
    if update_callback: update_callback(f"Descompilando {len(scripts)} scripts usando MULTIPROCESSING ({max_workers} Núcleos). Por favor espera...")
    
    failed_scripts = []
    worker_args = [(i, s, known_callables, library_path, eventos_dir) for i, s in enumerate(scripts)]
    
    scripts_ready = 0
    try:
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            for i, success, error in executor.map(_decompile_worker, worker_args):
                if not success:
                    failed_scripts.append((i, error))
                else:
                    scripts_ready += 1
                    if scripts_ready % 200 == 0 and update_callback:
                        update_callback(f"Progreso paralelo: {scripts_ready}/{len(scripts)} scripts...")
    except Exception as e:
        if update_callback: update_callback(f"Multiprocessing falló ({e}). Usando modo seguro (secuencial)...")
        for args in worker_args:
            i, success, error = _decompile_worker(args)
            if not success:
                failed_scripts.append((i, error))
            else:
                scripts_ready += 1
                if scripts_ready % 200 == 0 and update_callback:
                    update_callback(f"Progreso modo seguro: {scripts_ready}/{len(scripts)} scripts...")
                    
    if update_callback: update_callback(f"Scripts listos. {len(scripts)-len(failed_scripts)} extraídos, {len(failed_scripts)} fallidos.")
            
    # Write the errors report for Bot tracking
    bot_report_path = os.path.join(recursos_dir, "scripts_huerfanos_bot.txt")
    with open(bot_report_path, "w", encoding="utf-8") as f:
        f.write("=== LOG DE SCRIPTS FALLIDOS / DINÁMICOS ===\n")
        f.write("Los siguientes eventos no pudieron ser descompilados estáticamente.\n")
        f.write("El Bot debe ejecutar el juego, transitar por estas zonas y mapear las posiciones de RAM que los instancían.\n\n")
        
        for failed_id, reason in failed_scripts:
            f.write(f"Evento [{failed_id:04d}]: FAILED -> {reason}\n")
            
    # 1. Write the pointer map list for repointing tools (Strict CSV)
    pointer_map_path = os.path.join(recursos_dir, "mapa_punteros_eventos.txt")
    
    event_bounds = [] # Used for phase 2
    
    with open(pointer_map_path, "w", encoding="utf-8") as f:
        f.write("ID evento, Ofset inicio, Ofset final\n")
        from SlipSpace_Script_Engine.cli import get_all_scripts
        raw_scripts = get_all_scripts(rom_data)
        
        # We need the table bounds to get pointers
        is_fomt = b"HARVESTMOGBA" in rom_data[0xA0:0xAC]
        table_offset = 0x0F89D4 if is_fomt else 0x1014BC
        
        for i, s in enumerate(raw_scripts):
            if not s: continue
            if i in [fail[0] for fail in failed_scripts]: continue
            
            ptr_raw = struct.unpack_from('<I', rom_data, table_offset + i * 4)[0]
            start_off = ptr_raw & 0x01FFFFFF
            size = len(s)
            end_off = start_off + size
            
            event_bounds.append((i, start_off, end_off))
            f.write(f"{i}, 0x{start_off:06X}, 0x{end_off:06X}\n")

    # 2. ------ Buscador de Aglomeraciones Reales (Fragmentadas) ------
    if update_callback: update_callback("Rastreando aglomeraciones de punteros en Little Endian...")
    
    valid_pointers = {}
    for ev_id, start_off, end_off in event_bounds:
        actual_ptr = start_off | 0x08000000
        # Guardamos el primer evento que apunte aquí para referencia rápida
        if actual_ptr not in valid_pointers:
            valid_pointers[actual_ptr] = ev_id
            
    # Para no iterar toda la ROM byte a byte, encontramos las semillas rápido con .find()
    semillas = set()
    for actual_ptr in valid_pointers.keys():
        le_bytes = struct.pack('<I', actual_ptr)
        idx = rom_data.find(le_bytes)
        while idx != -1:
            semillas.add(idx)
            idx = rom_data.find(le_bytes, idx + 4)
            
    semillas_ordenadas = sorted(list(semillas))
    
    pointer_tables = []
    visitados = set()
    
    for inicio_tabla in semillas_ordenadas:
        if inicio_tabla in visitados:
            continue
            
        current_table = []
        curr_loc = inicio_tabla
        
        # Caminar hacia adelante validando que cada 4 bytes siga habiendo una coincidencia
        while curr_loc + 4 <= len(rom_data):
            test_ptr = struct.unpack_from('<I', rom_data, curr_loc)[0]
            if test_ptr in valid_pointers:
                current_table.append((curr_loc, valid_pointers[test_ptr], test_ptr))
                visitados.add(curr_loc)
                curr_loc += 4
            else:
                break
                
        # Según la heurística, 2 punteros juntos ya son una tablita a considerar
        if len(current_table) >= 2:
            pointer_tables.append(current_table)

    # Escribir cada tabla en su propio archivo independiente
    punteros_dir = os.path.join(tablas_dir, "Punteros")
    os.makedirs(punteros_dir, exist_ok=True)
    
    for table in pointer_tables:
        t_start = table[0][0]
        t_end = table[-1][0] + 4 # El final del bloque
        filepath = os.path.join(punteros_dir, f"POINTABLA_{t_start}_{t_end}.txt")
        with open(filepath, "w", encoding="utf-8") as f:
            for i, (ptr_loc, ev_id, ptr_val) in enumerate(table):
                le_hex = " ".join([f"{b:02X}" for b in struct.pack('<I', ptr_val)])
                f.write(f"Puntero {i+1} Evento {ev_id:04d} | Locación ROM: 0x{ptr_loc:06X} -> Apunta a: 0x{ptr_val:08X} | Little-Endian: [{le_hex}]\n")
    
    # 3. Extract Tables
    if update_callback: update_callback("Extrayendo Tablas de Punteros...")
    from SlipSpace_Script_Engine.utility.scan_tables import scan_fomt_tables
    # Since scan_tables currently only prints to stdout, we'll pipe it internally or build an API in it later.
    # For now we'll capture its output.
    import io
    old_stdout = sys.stdout
    sys.stdout = capture = io.StringIO()
    try:
        scan_fomt_tables(rom_data)
    except Exception as e:
        sys.stdout = old_stdout
        if update_callback: update_callback(f"Error en tablas: {e}")
        return False
        
    sys.stdout = old_stdout
    tablas_dump = capture.getvalue()
    
    # Split the output by tables if the scanner supports it
    import re
    blocks = re.split(r"=== REPORTE TABLA (.+?) ===", tablas_dump)
    
    if len(blocks) > 1:
        # Standardize separate tables
        for i in range(1, len(blocks), 2):
            table_name = blocks[i].strip()
            table_content = blocks[i+1].strip()
            with open(os.path.join(tablas_dir, f"{table_name}.txt"), "w", encoding="utf-8") as f:
                f.write(table_content)
    else:
        with open(os.path.join(tablas_dir, "Tablas_Generales.txt"), "w", encoding="utf-8") as f:
            f.write(tablas_dump)
            
    # 4. Extract Player Static Parameters (Stamina, Money, Resistance)
    if update_callback: update_callback("Buscando Datos Base del Jugador en ROM...")
    player_dir = os.path.join(recursos_dir, "Player_datos")
    os.makedirs(player_dir, exist_ok=True)
    
    from SlipSpace_Script_Engine.utility.scan_player import scan_player_stats
    try:
        player_report = scan_player_stats(rom_data)
        with open(os.path.join(player_dir, "Datos_Base.txt"), "w", encoding="utf-8") as f:
            f.write(player_report)
    except Exception as e:
        if update_callback: update_callback(f"Error escaneando Jugador: {e}")
        
    if update_callback: update_callback(f"¡Extracción Completa! Revisa la carpeta '{recursos_dir}'.")
    return True
