import os
import sys
import struct
from collections import Counter

# Añadir el directorio raíz al path para poder importar los módulos del proyecto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Nucleos_de_Procesamiento.Nucleo_de_Datos.proyecto import FoMTProject
from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.ast import (
    StmtCall, StmtExpr, ExprCall, StmtIf, StmtIfElse, StmtSwitch, StmtDoWhile, SwitchCaseCase, SwitchCaseDefault
)

def check_stmts_for_unknowns(stmt, counter, usage_map, event_id):
    """Escanea buscando opcodes desconocidos o genéricos (Proc/Func)."""
    name = None
    if isinstance(stmt, StmtCall):
        name = stmt.invoke.func
    elif isinstance(stmt, StmtExpr) and isinstance(stmt.expr, ExprCall):
        name = stmt.expr.invoke.func
    
    if name:
        # Detectar OpcodeUnknw_XXX, ProcXXX o FuncXXX
        is_unknw = name.startswith("OpcodeUnknw_")
        is_generic = (name.startswith("Proc") or name.startswith("Func")) and any(c.isdigit() for c in name)
        
        if is_unknw or is_generic:
            if name not in usage_map:
                usage_map[name] = []
            counter[name] += 1
            if event_id not in usage_map[name]:
                usage_map[name].append(event_id)

    # Recursión para bloques
    if isinstance(stmt, StmtIf):
        for s in stmt.stmts: check_stmts_for_unknowns(s, counter, usage_map, event_id)
    elif isinstance(stmt, StmtIfElse):
        for s in stmt.true_stmts: check_stmts_for_unknowns(s, counter, usage_map, event_id)
        for s in stmt.false_stmts: check_stmts_for_unknowns(s, counter, usage_map, event_id)
    elif isinstance(stmt, StmtSwitch):
        for case in stmt.cases:
            for s in case.stmts: check_stmts_for_unknowns(s, counter, usage_map, event_id)
    elif isinstance(stmt, StmtDoWhile):
        for s in stmt.body: check_stmts_for_unknowns(s, counter, usage_map, event_id)

def main():
    print("=== FOMT MIRROR DUMP SYSTEM v2.1 (FIXED) ===")
    
    rom_path = r"j:\Repositorios\fomt_studio\Modded_FoMT.gba"
    project = FoMTProject()
    project.step_1_detect_rom(rom_path)
    project.step_2_scan_events()

    event_parser = project.event_parser
    limit = event_parser.get_event_count()
    output_dir = r"j:\Repositorios\fomt_studio\scratch\event_dump"
    
    unknown_opcodes = Counter()
    usage_map = {} 
    total_events = 0

    print(f"Analizando {limit} eventos...")

    for event_id in range(1, limit + 1):
        try:
            script_text, stmts = event_parser.decompile_to_ui(event_id)
            
            with open(os.path.join(output_dir, f"event_{event_id:04d}.txt"), "w", encoding="utf-8") as f:
                f.write(script_text)
            
            for stmt in stmts:
                check_stmts_for_unknowns(stmt, unknown_opcodes, usage_map, event_id)
                
            total_events += 1
            if event_id % 200 == 0:
                print(f"Progreso: {event_id}/{limit}...")
        except Exception as e:
            # Ahora sí imprimimos si hay error real
            if event_id == 988: print(f"Error en 988: {e}")
            continue

    # Generar Reporte de Mapeo
    report_path = os.path.join(output_dir, "!!_CANDIDATOS_A_MAPEO.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=== REPORTE DE CANDIDATOS A MAPEARE ===\n")
        f.write("Opcodes genéricos o desconocidos detectados en la ROM.\n\n")
        
        # Ordenar por frecuencia
        for op, count in unknown_opcodes.most_common():
            events = usage_map.get(op, [])
            # Mostrar los primeros 10 eventos donde aparece
            ev_list = ", ".join([str(e) for e in events[:10]])
            if len(events) > 10: ev_list += "..."
            
            f.write(f"[{op}]\n")
            f.write(f"  Frecuencia: {count}\n")
            f.write(f"  Eventos: {ev_list}\n\n")

    print(f"\n¡Listo! Reporte generado en: {report_path}")

if __name__ == "__main__":
    main()
