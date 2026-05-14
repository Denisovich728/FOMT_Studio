# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.4.4)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
import argparse
import sys
import os
import struct
from .compiler.lexer import Lexer
from .compiler.parser import Parser
from .compiler.emitter import compile_script, ConstScope, eval_expr
from .bytecode.encoder import encode_script
from .bytecode.decoder import decode_script, DecodeError
from .decompiler.ins_decompiler import decompile_instructions
from .decompiler.formatter import format_script
from .ast import *

# Event Tracking and Table Discovery features
def get_all_scripts(rom_data: bytes) -> list[bytes]:
    try:
        if rom_data[0xA0:0xAC] == b"HARVESTMOGBA":
            table_offset = 0x0F89D4
            size = 1329
        elif rom_data[0xA0:0xAC] == b"HM MFOM USA\0":
            table_offset = 0x1014BC
            size = 1416
        else:
            print("Unknown ROM type. Falling back to default FoMT bounds.")
            table_offset = 0x0F89D4
            size = 1329
            
        scripts = []
        for i in range(size):
            ptr = struct.unpack_from('<I', rom_data, table_offset + i * 4)[0]
            if ptr < 0x08000000 or ptr >= 0x09000000:
                scripts.append(None)
                continue
                
            script_off = ptr & 0x01FFFFFF
            if script_off + 12 <= len(rom_data):
                riff = rom_data[script_off:script_off + 4]
                if riff == b"RIFF":
                    riff_len = struct.unpack_from('<I', rom_data, script_off + 4)[0]
                    name = rom_data[script_off + 8:script_off + 12]
                    if name == b"SCR " and script_off + riff_len + 8 <= len(rom_data):
                        scripts.append(rom_data[script_off:script_off + riff_len + 8])
                        continue
            scripts.append(None)
        return scripts
    except Exception as e:
        print(f"Error accessing script table: {e}")
        return []

def scan_for_pointers(rom_data: bytes, target_offset: int) -> list[int]:
    """Scans the ROM for any 32-bit pointers that point to the target_offset."""
    target_ptr = target_offset | 0x08000000
    found_at = []
    
    # 4-byte aligned search
    for i in range(0, len(rom_data) - 4, 4):
        ptr = struct.unpack_from('<I', rom_data, i)[0]
        if ptr == target_ptr:
            found_at.append(i)
            
    return found_at

def build_library_scope(lib_path: str) -> ConstScope:
    scope = ConstScope()
    if not os.path.exists(lib_path):
        return scope
        
    with open(lib_path, 'r', encoding='utf-8') as f:
        code = f.read()
        
    lexer = Lexer(code)
    parser = Parser(lexer)
    
    from .compiler.parser import ParseError
    try:
        parser.parse_program(scope, allow_scripts=False)
    except ParseError as e:
        print(f"Library parse error: {e}")
                
    return scope

def cmd_compile(args):
    code = ""
    if args.input:
        with open(args.input, 'r', encoding='utf-8') as f:
            code = f.read()
    else:
        code = sys.stdin.read()
        
    lexer = Lexer(code)
    parser = Parser(lexer)
    scope = ConstScope()
    
    from .compiler.parser import ParseError
    try:
        scripts = parser.parse_program(scope, allow_scripts=True)
        
        if args.binary:
            if len(scripts) != 1:
                print("Error: In binary output mode, exactly one script must be defined.")
                sys.exit(1)
                
            script_id, script_name, script_obj = scripts[0]
            bytecode = encode_script(script_obj)
            
            output = sys.stdout.buffer
            if args.output:
                output = open(args.output, 'wb')
            output.write(bytecode)
            if args.output:
                output.close()
        else:
            print("C-style compilation not yet implemented in Python port.")
            
    except ParseError as e:
        print(f"Compilation error: {e}")
        sys.exit(1)

def cmd_decompile(args):
    with open(args.input_binary, 'rb') as f:
        rom = f.read()
        
    script_data = None
    event_name = "YourEventScriptNameHere"
    event_id = 0
    rom_offset = 0
    
    if args.script_id is not None:
        scripts = get_all_scripts(rom)
        if args.script_id - 1 < len(scripts):
            script_data = scripts[args.script_id - 1]
            event_id = args.script_id
            event_name = f"EventScript_{args.script_id}"
            
            # Find the ROM offset for tracking
            ptr_table_offset = 0x15340C + (args.script_id - 1) * 4
            rom_offset = struct.unpack_from('<I', rom, ptr_table_offset)[0] & 0x01FFFFFF
    elif args.offset is not None:
        rom_offset = args.offset & 0x01FFFFFF
        script_data = rom[rom_offset:]
        event_name = f"EventScript_{rom_offset | 0x08000000:08X}"
    else:
        script_data = rom
        
    if not script_data:
        print("Error: Could not locate script data.")
        sys.exit(1)
        
    # Analyze caller scripts (Father scripts) using pointer scanner
    callers = scan_for_pointers(rom, rom_offset)
    
    try:
        script = decode_script(script_data)
        
        known_callables = {}
        if args.input_library:
            for name, ref in library_scope.names.items():
                from .ast import NameRefFunc, NameRefProc
                if isinstance(ref, NameRefFunc) or isinstance(ref, NameRefProc):
                    known_callables[ref.call_id] = (name, ref.shape)
                    
        # --- Parche: Registro Dinámico de Opcodes (RAWDynamic RAM args) ---
        from .ir import CallId, CallableShape, ValueType
        # Func106() -> 0 params
        if CallId(106) not in known_callables:
            known_callables[CallId(106)] = ("Func106", CallableShape.new_proc([]))
        # Func117(var_0) -> 1 param
        if CallId(117) not in known_callables:
            known_callables[CallId(117)] = ("Func117", CallableShape.new_proc([ValueType.integer()]))
            
        stmts = decompile_instructions(script.instructions, known_callables)
        from .decompiler.decorator import decorate_stmts_with_strings
        decorate_stmts_with_strings(stmts, script.strings, known_callables)
        
        out_code = format_script(stmts)
        
        output = sys.stdout
        if args.output:
            output = open(args.output, 'w', encoding='utf-8')
            
        output.write(f"// ==========================================\n")
        output.write(f"// SlipSpace_Engine Extended Decompiler\n")
        output.write(f"// ==========================================\n")
        output.write(f"// Event Offset: 0x{rom_offset:06X} (GBA: 0x{rom_offset | 0x08000000:08X})\n")
        if callers:
            output.write(f"// Father/Caller Events pointing here at: " + ", ".join([f"0x{c:06X}" for c in callers]) + "\n")
        else:
            output.write(f"// Father/Caller Events pointing here: None Found\n")
        output.write(f"// Script Length: {len(stmts)} statements\n")
        output.write(f"// ==========================================\n\n")
        
        if args.input_library:
            output.write(f'#include "{args.input_library}"\n\n')
            
        output.write(f"script {event_id} {event_name} {{\n")
        
        # Ident formatting manually applied here
        for line in out_code.splitlines():
            output.write("    " + line + "\n")
            
        output.write("}\n")
        
        if args.output:
            output.close()
            
    except DecodeError as e:
        print(f"Decode Error: {e}")
    except Exception as e:
        print(f"Decompile Error: {e}")

def main():
    parser = argparse.ArgumentParser(description="SlipSpace_Engine (GBA Script Tool) - Implementación Python")
    subparsers = parser.add_subparsers(dest="command")
    
    # Compile
    comp = subparsers.add_parser("compile", help="Compile a script")
    comp.add_argument("input", nargs="?", help="Input script to compile")
    comp.add_argument("-o", "--output", help="Output binary file")
    comp.add_argument("--binary", action="store_true", help="Output as raw RIFF script binary")
    
    # Decompile
    dec = subparsers.add_parser("decompile", help="Decompile a binary into script")
    dec.add_argument("input_binary", help="Input ROM or Script Binary")
    dec.add_argument("input_library", nargs="?", help="Input library definitions script")
    dec.add_argument("-o", "--output", help="Output script file")
    dec.add_argument("--script-id", type=int, help="Event Script ID to decompile from ROM")
    dec.add_argument("--offset", type=lambda x: int(x, 0), help="ROM offset to decompile from (hex supported: 0x...)")
    dec.add_argument("--print-ir", action="store_true", help="Include IR trace in comments")
    
    # Table Scanner
    t_scan = subparsers.add_parser("scan-tables", help="Scan ROM for pointer tables like Characters and Items")
    t_scan.add_argument("rom_file", help="Path to FoMT ROM .gba file")
    
    args = parser.parse_args()
    
    if args.command == "compile":
        cmd_compile(args)
    elif args.command == "decompile":
        cmd_decompile(args)
    elif args.command == "scan-tables":
        with open(args.rom_file, 'rb') as f:
            from .utility.scan_tables import scan_fomt_tables
            scan_fomt_tables(f.read())
    else:
        # Launch GUI if no command is specified
        from .ui import launch_gui
        launch_gui()

if __name__ == "__main__":
    main()
