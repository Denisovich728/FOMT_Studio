"""
Full regression test + Event 355 specific check.
"""
import sys, os, struct, csv, traceback
sys.path.insert(0, r"j:\Repositorios\fomt_studio")

from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.bytecode.decoder import decode_script
from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.ir import *
from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.decompiler.ins_decompiler import decompile_instructions
from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.decompiler.formatter import format_script

rom_path = r"j:\Repositorios\fomt_studio\Modded_FoMT.gba"
with open(rom_path, "rb") as f:
    rom_data = f.read()

TABLE_OFFSET = 0x0F89D8

known_callables = {}
lib_path = r"j:\Repositorios\fomt_studio\Nucleos_de_Procesamiento\data\lib_fomt.csv"
with open(lib_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        t = (row.get('Type') or '').strip()
        if t not in ('proc', 'func'): continue
        hex_id_str = (row.get('Hex_ID') or '').strip()
        name = (row.get('Name') or '').strip()
        args_str = (row.get('Arguments') or '').strip()
        try: call_id_val = int(hex_id_str, 16)
        except ValueError: continue
        args_count = 0 if not args_str else len([a for a in args_str.split(',') if a.strip()])
        param_types = [ValueType.integer() for _ in range(args_count)]
        shape = CallableShape.new_func(param_types) if t == 'func' else CallableShape.new_proc(param_types)
        known_callables[CallId(call_id_val)] = (name, shape)

# --- Event 355 specific test ---
EVENT_355 = 355
ptr_off = TABLE_OFFSET + (EVENT_355 * 4)
ptr_val = struct.unpack_from('<I', rom_data, ptr_off)[0]
script_off = ptr_val & 0x01FFFFFF
header = rom_data[script_off:script_off+4]

if header == b'RIFF':
    riff_len = struct.unpack_from('<I', rom_data, script_off + 4)[0]
    chunk_data = rom_data[script_off:script_off + riff_len + 8]
    script = decode_script(chunk_data)
    stmts = decompile_instructions(script.instructions, known_callables)
    code = format_script(stmts)
    if EVENT_355 == 355:
        print("RAW INSTRUCTIONS FOR EVENT 355:")
        for i, ins in enumerate(script.instructions):
            print(f"[{i:03}] {ins}")
    
    print("=" * 70)
    print("EVENT 355 DECOMPILED OUTPUT:")
    print("=" * 70)
    print(code)
    
    # Semantic checks
    lines = code.splitlines()
    
    # Check 1: No bare conditions (the original bug)
    bare = [l for l in lines if l.strip().startswith("((") and l.strip().endswith(");") and "Check_Flag" in l]
    
    # Check 2: Set_TV_Screen_Graphic should NOT be inside Init_Notice_Board_UI's else
    # Check 3: Init_Notice_Board_UI should NOT appear as if() condition at top level
    init_as_if = any("if (Init_Notice_Board_UI" in l for l in lines)
    
    # Check 4: Close_TV_Interface should exist at top level, not nested
    close_found = any("Close_TV_Interface" in l for l in lines)
    
    print("=" * 70)
    print("SEMANTIC CHECKS:")
    print(f"  Bare conditions: {len(bare)} (want 0)")
    print(f"  Init_Notice_Board_UI as if-condition: {init_as_if} (want True)")
    print(f"  Close_TV_Interface found: {close_found} (want True)")
    print("=" * 70)

# --- Full regression ---
print("\nRunning full regression...")
total = success = errors = bare_conds = has_if_else = 0

for event_id in range(1329):
    ptr_off = TABLE_OFFSET + (event_id * 4)
    if ptr_off + 4 > len(rom_data): continue
    ptr_val = struct.unpack_from('<I', rom_data, ptr_off)[0]
    if ptr_val < 0x08000000 or ptr_val >= 0x09000000: continue
    script_off = ptr_val & 0x01FFFFFF
    if script_off >= len(rom_data) - 4: continue
    header = rom_data[script_off:script_off+4]
    if header != b'RIFF': continue
    
    total += 1
    try:
        riff_len = struct.unpack_from('<I', rom_data, script_off + 4)[0]
        chunk_data = rom_data[script_off:script_off + riff_len + 8]
        script = decode_script(chunk_data)
        stmts = decompile_instructions(script.instructions, known_callables)
        code = format_script(stmts)
        
        for line in code.splitlines():
            stripped = line.strip()
            if stripped.startswith("((") and stripped.endswith(");") and "Check_Flag" in stripped:
                bare_conds += 1
                break
        if "else {" in code or "else\n{" in code: has_if_else += 1
        success += 1
    except Exception as e:
        errors += 1
        if errors <= 3: print(f"  ERROR event {event_id}: {e}")

print(f"\nREGRESSION: {success}/{total} OK, {errors} errors, {bare_conds} bare conds, {has_if_else} if/else")
