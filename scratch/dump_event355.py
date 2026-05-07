"""
Raw bytecode dump for Event 355 - Showing every instruction, its offset,
and jump target addresses to understand the real control flow.
"""
import sys, struct, csv
sys.path.insert(0, r"j:\Repositorios\fomt_studio")

from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.bytecode.opcodes import *
from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.bytecode.decoder import (
    decode_script, read_u32, read_u16, operand_size, read_riff_chunks, 
    decode_code_chunk, get_code_jumps, decode_jump_chunk, build_case_map,
    decode_string_chunk, disassemble
)
from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine.ir import *

rom_path = r"j:\Repositorios\fomt_studio\Modded_FoMT3.gba"
with open(rom_path, "rb") as f:
    rom_data = f.read()

# Real table offset from Punteros de extraccion.csv
TABLE_OFFSET = 0x0F89D8
EVENT_ID = 355

ptr_off = TABLE_OFFSET + (EVENT_ID * 4)
ptr_val = struct.unpack_from('<I', rom_data, ptr_off)[0]
script_off = ptr_val & 0x01FFFFFF

print(f"Event {EVENT_ID} (0x{EVENT_ID:03X})")
print(f"  Pointer at ROM 0x{ptr_off:06X}: 0x{ptr_val:08X}")
print(f"  Script ROM Offset: 0x{script_off:06X}")

header = rom_data[script_off:script_off+4]
print(f"  Header: {header}")

if header != b'RIFF':
    print("NOT RIFF - aborting")
    sys.exit(1)

riff_len = struct.unpack_from('<I', rom_data, script_off + 4)[0]
chunk_data = rom_data[script_off:script_off + riff_len + 8]
print(f"  RIFF Length: {riff_len} (0x{riff_len:X})")

# Parse RIFF chunks
chunks = read_riff_chunks(chunk_data, riff_len)
print(f"  Chunks: {list(chunks.keys())}")

# Get CODE data
code_raw = chunks["CODE"]
code_size = read_u32(code_raw, 0)
code_data = code_raw[4:]
print(f"  CODE chunk: {len(code_raw)} bytes, code_size={code_size}")

# Opcode names
OPCODE_NAMES = {
    0x00: "NOP", 0x01: "EQU", 0x02: "ADDEQU", 0x03: "SUBEQU",
    0x04: "MULEQU", 0x05: "DIVEQU", 0x06: "MODEQU",
    0x07: "ADD", 0x08: "SUB", 0x09: "MUL", 0x0A: "DIV", 0x0B: "MOD",
    0x0C: "AND", 0x0D: "OR", 0x0E: "INC", 0x0F: "DEC",
    0x10: "NEG", 0x11: "NOT", 0x12: "CMP",
    0x13: "PUSHV", 0x14: "POPV", 0x15: "DUP", 0x16: "DISC",
    0x17: "PUSH32", 0x18: "JMP", 0x19: "BLT", 0x1A: "BLE",
    0x1B: "BEQ", 0x1C: "BNE", 0x1D: "BGE", 0x1E: "BGT",
    0x1F: "JPI", 0x20: "END", 0x21: "CALL", 0x22: "PUSH16", 0x23: "PUSH8",
    0x24: "SWITCH",
}

# Load callables for CALL resolution
known_callables = {}
lib_path = r"j:\Repositorios\fomt_studio\Nucleos_de_Procesamiento\data\lib_fomt.csv"
with open(lib_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        t = (row.get('Type') or '').strip()
        if t not in ('proc', 'func'): continue
        hex_id_str = (row.get('Hex_ID') or '').strip()
        name = (row.get('Name') or '').strip()
        try:
            call_id_val = int(hex_id_str, 16)
            known_callables[call_id_val] = name
        except ValueError:
            continue

# Get jump targets for annotation
jump_infos = get_code_jumps(code_data)
jump_targets = {}  # offset -> list of jump_ids that land here
for ji in jump_infos:
    if ji.target_offset not in jump_targets:
        jump_targets[ji.target_offset] = []
    jump_targets[ji.target_offset].append(f"from 0x{ji.source_offset:03X}")

# Disassemble with raw offsets
print(f"\n{'='*80}")
print(f"RAW BYTECODE DISASSEMBLY (CODE chunk, {len(code_data)} bytes)")
print(f"{'='*80}")

offset = 0
while offset < len(code_data):
    # Check if this offset is a jump target
    if offset in jump_targets:
        sources = ", ".join(jump_targets[offset])
        print(f"  ---- TARGET @ 0x{offset:03X} (jumped to by: {sources}) ----")
    
    pc = offset
    opcode = code_data[offset]
    offset += 1
    
    op_size = operand_size(opcode)
    operand = 0
    raw_bytes = f"{opcode:02X}"
    
    if op_size == 1:
        operand = code_data[offset]
        raw_bytes += f" {operand:02X}"
        offset += 1
    elif op_size == 2:
        operand = read_u16(code_data, offset)
        raw_bytes += f" {code_data[offset]:02X} {code_data[offset+1]:02X}"
        offset += 2
    elif op_size == 4:
        operand = read_u32(code_data, offset)
        raw_bytes += f" {code_data[offset]:02X} {code_data[offset+1]:02X} {code_data[offset+2]:02X} {code_data[offset+3]:02X}"
        offset += 4
    
    name = OPCODE_NAMES.get(opcode, f"UNK_{opcode:02X}")
    
    # Build annotation
    annotation = ""
    if opcode in (OPCODE_JMP, OPCODE_BEQ, OPCODE_BNE, OPCODE_BLT, OPCODE_BLE, OPCODE_BGE, OPCODE_BGT):
        annotation = f"  -> target 0x{operand:03X}"
    elif opcode == OPCODE_CALL:
        call_name = known_callables.get(operand, f"???_{operand:03X}")
        annotation = f"  [{call_name}]"
    elif opcode in (OPCODE_PUSH32, OPCODE_PUSH16, OPCODE_PUSH8):
        # Sign extend for display
        if op_size == 1 and operand >= 0x80: signed = operand - 0x100
        elif op_size == 2 and operand >= 0x8000: signed = operand - 0x10000
        elif op_size == 4 and operand >= 0x80000000: signed = operand - 0x100000000
        else: signed = operand
        annotation = f"  (={signed}, 0x{operand:X})"
    elif opcode == OPCODE_PUSHV:
        annotation = f"  [var_{operand}]"
    elif opcode == OPCODE_POPV:
        annotation = f"  [var_{operand}]"
    
    print(f"  0x{pc:03X}: {raw_bytes:<20s} {name:<10s}{annotation}")

# Also show strings
if "STR " in chunks:
    strings = decode_string_chunk(chunks["STR "])
    print(f"\n{'='*80}")
    print(f"STRINGS ({len(strings)} entries)")
    print(f"{'='*80}")
    for i, s in enumerate(strings):
        preview = s[:80].decode('ascii', errors='replace')
        print(f"  [{i}] {preview}...")

# Also show JUMP chunk (switch tables)
if "JUMP" in chunks:
    jc = decode_jump_chunk(chunks["JUMP"])
    print(f"\n{'='*80}")
    print(f"SWITCH TABLES ({len(jc.case_tables)} tables)")
    print(f"{'='*80}")
    for i, table in enumerate(jc.case_tables):
        print(f"  Table {i}:")
        for case_enum, target in table.entries:
            if isinstance(case_enum, CaseDefault):
                print(f"    default -> 0x{target:03X}")
            else:
                print(f"    case {case_enum.val} -> 0x{target:03X}")
