# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.6.5)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
# scan_vm_dispatch.py
# ────────────────────────────────────────────────────────────
# Escáner de la Tabla de Dispatch Nativa de la VM.
# Localiza la tabla de punteros a funciones ARM/THUMB que la
# VM del juego usa para resolver OPCODE_CALL (0x21).
#
# Cada Call ID (proc/func) se indexa en esta tabla para saltar
# a la rutina nativa correspondiente en el código ARM de la ROM.
# ============================================================
import struct
import sys
import os
import csv
from typing import List, Tuple, Optional, Dict


def read_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from('<I', data, offset)[0]


def is_code_pointer(ptr: int, rom_size: int) -> bool:
    """Verifica si un puntero apunta al área de código ARM/THUMB de la ROM."""
    # Los punteros ARM/THUMB tienen formato 0x08XXXXXX (o 0x08XXXXXX|1 para THUMB)
    clean = ptr & 0xFFFFFFFE  # Limpiar bit THUMB
    rom_offset = clean & 0x01FFFFFF
    return (0x08000000 <= clean < 0x09000000) and (rom_offset < rom_size)


def scan_vm_dispatch_table(rom_data: bytes, min_entries: int = 50, 
                           known_table_offsets: list = None) -> List[Tuple[int, int]]:
    """
    Busca la tabla de punteros de funciones nativas de la VM.
    
    La tabla es un array contiguo de punteros ARM/THUMB (0x08XXXXXX)
    al área de código de la ROM. Cada entrada corresponde a un Call ID.
    
    Args:
        rom_data: Datos crudos de la ROM GBA
        min_entries: Mínimo de entradas consecutivas para considerar un candidato
        known_table_offsets: Offsets de tablas ya conocidas (para excluirlas)
        
    Returns:
        Lista de (offset_tabla, num_entradas) candidatas
    """
    if known_table_offsets is None:
        known_table_offsets = []
    
    rom_size = len(rom_data)
    candidates = []
    
    # Escaneo alineado a 4 bytes
    i = 0
    while i < rom_size - min_entries * 4:
        # Verificar si esta dirección es una tabla conocida (scripts, etc.)
        if i in known_table_offsets:
            i += 4
            continue
        
        # Contar entradas consecutivas válidas de punteros a código
        count = 0
        null_streak = 0  # Tolerancia para entries nulas (opcode ID sin handler)
        
        j = i
        while j + 4 <= rom_size:
            ptr = read_u32(rom_data, j)
            
            if is_code_pointer(ptr, rom_size):
                count += 1
                null_streak = 0
                j += 4
            elif ptr == 0x00000000:
                # Algunos Call IDs pueden estar sin implementar (NULL)
                null_streak += 1
                if null_streak > 3:
                    break  # Demasiados NULLs consecutivos → fin de tabla
                count += 1
                j += 4
            else:
                break
        
        if count >= min_entries:
            # Verificar que NO sea la tabla de scripts (que tiene punteros a RIFF data)
            is_script_table = False
            sample_ptr = read_u32(rom_data, i) & 0x01FFFFFF
            if sample_ptr + 4 < rom_size:
                magic = rom_data[sample_ptr:sample_ptr + 4]
                if magic == b"RIFF":
                    is_script_table = True
            
            if not is_script_table:
                candidates.append((i, count))
                i = j  # Saltar al final de la tabla encontrada
                continue
        
        i += 4
    
    return candidates


def dump_dispatch_table(rom_data: bytes, table_offset: int, num_entries: int,
                        lib_path: str = None) -> str:
    """
    Genera un reporte de la tabla de dispatch con nombres de Fomt_Lib.csv.
    
    Args:
        rom_data: Datos de la ROM
        table_offset: Offset de inicio de la tabla en ROM
        num_entries: Cantidad de entradas a leer
        lib_path: Ruta al archivo Fomt_Lib.csv para mapear nombres
        
    Returns:
        String con el reporte formateado
    """
    # Cargar nombres de la librería si existe
    call_id_names: Dict[int, Tuple[str, str]] = {}
    if lib_path and os.path.exists(lib_path):
        try:
            with open(lib_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader)
                for row in reader:
                    if len(row) >= 4:
                        entry_type = row[0].strip()
                        hex_id = row[1].strip()
                        dec_id = int(row[2].strip())
                        name = row[3].strip()
                        args = row[4].strip() if len(row) > 4 else ""
                        call_id_names[dec_id] = (name, f"{entry_type}({args})")
        except Exception as e:
            pass  # Si falla, continuamos sin nombres
    
    lines = []
    lines.append("=" * 80)
    lines.append("  TABLA DE DISPATCH NATIVA DE LA VM")
    lines.append(f"  Offset ROM: 0x{table_offset:06X} (GBA: 0x{table_offset | 0x08000000:08X})")
    lines.append(f"  Entradas: {num_entries}")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"{'Call ID':<10} {'Hex ID':<10} {'Dirección ARM':<18} {'ROM Offset':<14} {'THUMB':<7} {'Nombre':<30} {'Firma'}")
    lines.append("-" * 120)
    
    for idx in range(num_entries):
        offset = table_offset + idx * 4
        if offset + 4 > len(rom_data):
            break
            
        ptr = read_u32(rom_data, offset)
        
        if ptr == 0:
            name_info = call_id_names.get(idx, ("(NULL)", ""))
            lines.append(f"{idx:<10} 0x{idx:03X}      {'(NULL)':<18} {'---':<14} {'---':<7} {name_info[0]:<30} {name_info[1]}")
            continue
        
        is_thumb = bool(ptr & 1)
        clean_ptr = ptr & 0xFFFFFFFE
        rom_off = clean_ptr & 0x01FFFFFF
        thumb_str = "THUMB" if is_thumb else "ARM"
        
        name_info = call_id_names.get(idx, (f"Unk_{idx:03X}", ""))
        
        lines.append(
            f"{idx:<10} 0x{idx:03X}      0x{ptr:08X}        "
            f"0x{rom_off:06X}      {thumb_str:<7} {name_info[0]:<30} {name_info[1]}"
        )
    
    return "\n".join(lines)


def dump_single_proc(rom_data: bytes, table_offset: int, call_id: int,
                     disasm_bytes: int = 128) -> str:
    """
    Extrae y muestra los bytes crudos de una rutina nativa específica.
    
    Args:
        rom_data: Datos de la ROM
        table_offset: Offset de la tabla de dispatch
        call_id: Call ID del proc/func a examinar
        disasm_bytes: Cantidad de bytes a extraer desde el entry point
        
    Returns:
        String con el dump hexadecimal de la función
    """
    ptr_offset = table_offset + call_id * 4
    if ptr_offset + 4 > len(rom_data):
        return f"Error: Call ID {call_id} (0x{call_id:03X}) fuera de rango de la tabla."
    
    ptr = read_u32(rom_data, ptr_offset)
    if ptr == 0:
        return f"Error: Call ID {call_id} (0x{call_id:03X}) no tiene handler (NULL)."
    
    is_thumb = bool(ptr & 1)
    clean_ptr = ptr & 0xFFFFFFFE
    rom_off = clean_ptr & 0x01FFFFFF
    mode = "THUMB" if is_thumb else "ARM"
    instr_size = 2 if is_thumb else 4
    
    lines = []
    lines.append("=" * 70)
    lines.append(f"  DUMP DE RUTINA NATIVA: Call ID {call_id} (0x{call_id:03X})")
    lines.append(f"  Dirección GBA: 0x{ptr:08X}")
    lines.append(f"  ROM Offset:    0x{rom_off:06X}")
    lines.append(f"  Modo:          {mode}")
    lines.append("=" * 70)
    lines.append("")
    
    # Extraer bytes
    end = min(rom_off + disasm_bytes, len(rom_data))
    func_bytes = rom_data[rom_off:end]
    
    # Hex dump con agrupación por instrucción
    lines.append(f"{'Offset':<12} {'GBA Addr':<14} {'Hex':<20} {'Instrucción (raw)'}")
    lines.append("-" * 65)
    
    pos = 0
    while pos < len(func_bytes):
        addr = (rom_off + pos) | 0x08000000
        
        if is_thumb:
            if pos + 2 <= len(func_bytes):
                word = struct.unpack_from('<H', func_bytes, pos)[0]
                hex_str = f"{func_bytes[pos]:02X} {func_bytes[pos+1]:02X}"
                
                # Detección básica de BX LR (retorno de función THUMB)
                comment = ""
                if word == 0x4770:
                    comment = " ; BX LR (return)"
                elif (word & 0xFF00) == 0xB500:
                    comment = f" ; PUSH {{LR, ...}}"
                elif (word & 0xFF00) == 0xBD00:
                    comment = f" ; POP {{PC, ...}}"
                elif (word & 0xF800) == 0x4800:
                    comment = f" ; LDR Rd, [PC, #imm]"
                elif (word & 0xF800) == 0xF000:
                    comment = " ; BL (high)"
                elif (word & 0xF800) == 0xF800:
                    comment = " ; BL (low)"
                    
                lines.append(f"0x{rom_off+pos:06X}   0x{addr:08X}   {hex_str:<20}{comment}")
                pos += 2
                
                # Si encontramos BX LR, marcar fin probable de función
                if word == 0x4770:
                    lines.append("  ---- Posible fin de funcion (BX LR) ----")
                    # Continuar un poco más por si hay datos de pool
            else:
                break
        else:
            # ARM mode
            if pos + 4 <= len(func_bytes):
                word = struct.unpack_from('<I', func_bytes, pos)[0]
                hex_str = " ".join(f"{func_bytes[pos+b]:02X}" for b in range(4))
                
                comment = ""
                # Detección básica de instrucciones ARM comunes
                if word == 0xE12FFF1E:
                    comment = " ; BX LR (return)"
                elif (word & 0x0FFF0000) == 0x092D0000:
                    comment = " ; STMFD SP!, {...} (push)"
                elif (word & 0x0FFF0000) == 0x08BD0000:
                    comment = " ; LDMFD SP!, {...} (pop)"
                    
                lines.append(f"0x{rom_off+pos:06X}   0x{addr:08X}   {hex_str:<20}{comment}")
                pos += 4
                
                if word == 0xE12FFF1E:
                    lines.append("  ---- Posible fin de funcion (BX LR) ----")
            else:
                break
    
    lines.append("")
    lines.append("NOTA: Para un desensamblado completo, carga la ROM en Ghidra")
    lines.append(f"      y navega a 0x{ptr:08X}. Configura como GBA ARM v4T Little Endian.")
    
    return "\n".join(lines)


def scan_and_report(rom_path: str, lib_path: str = None, 
                    target_call_id: int = None) -> str:
    """
    Función principal: escanea la ROM, encuentra la tabla de dispatch,
    y opcionalmente hace dump de un proc/func específico.
    
    Args:
        rom_path: Ruta al archivo .gba
        lib_path: Ruta al Fomt_Lib.csv (opcional)
        target_call_id: Call ID específico a examinar (opcional)
        
    Returns:
        Reporte completo como string
    """
    with open(rom_path, 'rb') as f:
        rom_data = f.read()
    
    # Detectar versión
    is_fomt = b"HARVESTMOGBA" in rom_data[0xA0:0xAC]
    is_mfomt = b"HM MFOM USA\0" in rom_data[0xA0:0xAC]
    
    # Tablas de scripts conocidas para excluir
    known_tables = []
    if is_fomt:
        known_tables = [0x0F89D4]
        version = "FoMT (USA)"
    elif is_mfomt:
        known_tables = [0x1014BC]
        version = "MFoMT (USA)"
    else:
        version = "Desconocida"
    
    report = []
    report.append("=" * 64)
    report.append("  SlipSpace VM Dispatch Scanner")
    report.append(f"  ROM: {os.path.basename(rom_path)}")
    report.append(f"  Version: {version}")
    report.append(f"  Size: {len(rom_data):,} bytes")
    report.append("=" * 64)
    report.append("")
    
    # Fase 1: Buscar tablas candidatas
    report.append("Fase 1: Escaneando tabla de dispatch de la VM...")
    candidates = scan_vm_dispatch_table(rom_data, min_entries=50, 
                                         known_table_offsets=known_tables)
    
    if not candidates:
        # Intentar con umbral más bajo
        report.append("  No se encontró con umbral 50. Reintentando con umbral 30...")
        candidates = scan_vm_dispatch_table(rom_data, min_entries=30,
                                             known_table_offsets=known_tables)
    
    if not candidates:
        report.append("  [!] No se encontraron candidatos a tabla de dispatch.")
        report.append("  Posibles causas:")
        report.append("    - La tabla usa un mecanismo de indirección diferente")
        report.append("    - Los punteros no están en formato estándar 0x08XXXXXX")
        report.append("    - La ROM está comprimida o encriptada en esa zona")
        return "\n".join(report)
    
    report.append(f"  [OK] Encontradas {len(candidates)} tablas candidatas:")
    for idx, (offset, count) in enumerate(candidates):
        report.append(f"    [{idx}] Offset: 0x{offset:06X} | Entradas: {count}")
    report.append("")
    
    # Fase 2: Analizar la tabla más probable
    # Heurística: la tabla de dispatch de la VM debería tener ~310+ entradas
    # (basado en el número de procs/funcs en Fomt_Lib.csv)
    best_candidate = max(candidates, key=lambda x: x[1])
    table_offset, table_count = best_candidate
    
    report.append(f"Fase 2: Analizando tabla principal en 0x{table_offset:06X} ({table_count} entradas)...")
    report.append("")
    report.append(dump_dispatch_table(rom_data, table_offset, table_count, lib_path))
    
    # Fase 3: Si se pidió un proc/func específico
    if target_call_id is not None:
        report.append("")
        report.append(f"Fase 3: Dump de Call ID {target_call_id} (0x{target_call_id:03X})...")
        report.append("")
        report.append(dump_single_proc(rom_data, table_offset, target_call_id))
    
    return "\n".join(report)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scan_vm_dispatch.py <rom.gba> [--lib Fomt_Lib.csv] [--proc 0x95]")
        print("")
        print("Opciones:")
        print("  --lib PATH    Ruta al archivo Fomt_Lib.csv para mapear nombres")
        print("  --proc ID     Call ID específico a examinar (hex con 0x o decimal)")
        sys.exit(1)
    
    rom_path = sys.argv[1]
    lib_path = None
    target_id = None
    
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--lib" and i + 1 < len(sys.argv):
            lib_path = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--proc" and i + 1 < len(sys.argv):
            val = sys.argv[i + 1]
            target_id = int(val, 0)  # Soporta 0x y decimal
            i += 2
        else:
            i += 1
    
    result = scan_and_report(rom_path, lib_path, target_id)
    print(result)
