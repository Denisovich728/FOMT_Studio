"""
Check: do real if/else patterns still work? Find events that had them.
"""
import sys, struct, csv
sys.path.insert(0, r"j:\Repositorios\fomt_studio")

from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.bytecode.decoder import decode_script
from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.ir import *
from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.decompiler.ins_decompiler import decompile_instructions
from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.decompiler.formatter import format_script

rom_path = r"j:\Repositorios\fomt_studio\Modded_FoMT3.gba"
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

# Find events with if/else to check Pattern 3
found = 0
for event_id in range(1329):
    ptr_off = TABLE_OFFSET + (event_id * 4)
    if ptr_off + 4 > len(rom_data): continue
    ptr_val = struct.unpack_from('<I', rom_data, ptr_off)[0]
    if ptr_val < 0x08000000 or ptr_val >= 0x09000000: continue
    script_off = ptr_val & 0x01FFFFFF
    if script_off >= len(rom_data) - 4: continue
    if rom_data[script_off:script_off+4] != b'RIFF': continue

    try:
        riff_len = struct.unpack_from('<I', rom_data, script_off + 4)[0]
        chunk_data = rom_data[script_off:script_off + riff_len + 8]
        script = decode_script(chunk_data)
        stmts = decompile_instructions(script.instructions, known_callables)
        code = format_script(stmts)
        
        if "} else {" in code:
            found += 1
            if found <= 3:
                print(f"\n=== Event {event_id} (has if/else) ===")
                for line in code.splitlines():
                    if "else" in line or "if (" in line:
                        print(f"  {line}")
    except: pass

print(f"\nTotal events with if/else: {found}")
