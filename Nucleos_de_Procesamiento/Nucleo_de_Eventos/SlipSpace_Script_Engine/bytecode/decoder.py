# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.3.1)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
import struct
from io import BytesIO
from typing import List, Dict, Tuple, Optional
from functools import cmp_to_key
from ..ir import *
from .opcodes import *

class DecodeError(Exception):
    pass

def read_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from('<I', data, offset)[0]

def read_u16(data: bytes, offset: int) -> int:
    return struct.unpack_from('<H', data, offset)[0]

def operand_size(opcode: int) -> int:
    sizes = {
        OPCODE_PUSHV: 4, OPCODE_POPV: 4, OPCODE_PUSH32: 4, OPCODE_PUSH16: 2, OPCODE_PUSH8: 1,
        OPCODE_JMP: 4, OPCODE_BLT: 4, OPCODE_BLE: 4, OPCODE_BEQ: 4, OPCODE_BNE: 4,
        OPCODE_BGE: 4, OPCODE_BGT: 4, OPCODE_CALL: 4, OPCODE_SWITCH: 4,
    }
    return sizes.get(opcode, 0)

@dataclass
class JumpInfo:
    source_offset: int
    target_offset: int
    jump_id: JumpId

def get_code_jumps(code_data: bytes) -> List[JumpInfo]:
    offset = 0
    jump_id_counter = 0
    extended_jump_map = []
    
    while offset < len(code_data):
        opcode = code_data[offset]
        offset += 1
        
        if opcode in (OPCODE_JMP, OPCODE_BEQ, OPCODE_BNE, OPCODE_BLE, OPCODE_BLT, OPCODE_BGE, OPCODE_BGT):
            jump_id = JumpId(jump_id_counter)
            target_offset = read_u32(code_data, offset)
            disp = target_offset - offset
            info = JumpInfo(offset - 1, target_offset, jump_id)
            extended_jump_map.append((info, disp))
            jump_id_counter += 1
            
        offset += operand_size(opcode)
        
    def cmp_jumps(a, b):
        ai, adisp = a
        bi, bdisp = b
        if ai.target_offset == bi.target_offset:
            if (adisp < 0 and bdisp < 0) or (adisp > 0 and bdisp > 0):
                return (adisp > bdisp) - (adisp < bdisp)
            else:
                return (bdisp > adisp) - (bdisp < adisp)
        return (ai.target_offset > bi.target_offset) - (ai.target_offset < bi.target_offset)

    extended_jump_map.sort(key=cmp_to_key(cmp_jumps))
    return [info for info, _ in extended_jump_map]

@dataclass
class CaseTable:
    entries: List[Tuple[CaseEnum, int]]

@dataclass
class DecodedJumpChunk:
    case_tables: List[CaseTable]

def decode_jump_chunk(data: bytes) -> DecodedJumpChunk:
    if not data:
        return DecodedJumpChunk([])
    ent_count = read_u32(data, 0)
    offset = 4
    
    offs = []
    for _ in range(ent_count):
        off = read_u32(data, offset)
        offset += 4
        offs.append(off)
        if off % 4 != 0:
            raise DecodeError(f"Misaligned jump table offset: {off:02X}")
            
    case_tables = []
    for _ in range(ent_count):
        entries = read_u32(data, offset)
        default_val = read_u32(data, offset + 4)
        offset += 8
        
        table = []
        if (default_val & 0x80000000) == 0:
            table.append((CaseDefault(), default_val))
            
        for _ in range(entries):
            compare = struct.unpack_from('<i', data, offset)[0]
            target = read_u32(data, offset + 4)
            offset += 8
            table.append((CaseVal(compare), target))
            
        case_tables.append(CaseTable(table))
        
    return DecodedJumpChunk(case_tables)

def build_case_map(jump_chunk: DecodedJumpChunk) -> List[Tuple[int, SwitchId, CaseEnum]]:
    case_map = []
    for i, table in enumerate(jump_chunk.case_tables):
        switch_id = SwitchId(i)
        for case_enum, code_offset in table.entries:
            case_map.append((code_offset, switch_id, case_enum))
            
    case_map.sort(key=lambda x: x[0])
    return case_map

def decode_code_chunk(code_data: bytes) -> bytes:
    head_size = read_u32(code_data, 0)
    # No recortamos por OPCODE_END porque puede haber datos o múltiples exits.
    # El desensamblador leerá hasta el final del tamaño indicado por la cabecera del chunk.
    return code_data[4:]

def disassemble(code_data: bytes, jump_targets: List[JumpInfo], case_map: List[Tuple[int, SwitchId, CaseEnum]]) -> List[Ins]:
    result = []
    offset = 0
    current_case_target_idx = 0
    current_jump_target_idx = 0
    
    jump_source_map = {jump.source_offset: jump.jump_id for jump in jump_targets}
    
    while offset < len(code_data):
        while current_jump_target_idx < len(jump_targets):
            head = jump_targets[current_jump_target_idx]
            if head.target_offset > offset:
                break
            result.append(Label(head.jump_id))
            current_jump_target_idx += 1
            
        while current_case_target_idx < len(case_map):
            target_offset, switch_id, case_id = case_map[current_case_target_idx]
            if target_offset > offset:
                break
            result.append(Case(switch_id, case_id))
            current_case_target_idx += 1
            
        pc = offset
        opcode = code_data[offset]
        offset += 1
        
        op_size = operand_size(opcode)
        operand = 0
        if op_size == 1:
            operand = code_data[offset]
            offset += 1
        elif op_size == 2:
            operand = read_u16(code_data, offset)
            offset += 2
        elif op_size == 4:
            operand = read_u32(code_data, offset)
            offset += 4
            
        if opcode == OPCODE_NOP: pass
        elif opcode == OPCODE_EQU: result.append(Assign())
        elif opcode == OPCODE_ADDEQU: result.append(AssignAdd())
        elif opcode == OPCODE_SUBEQU: result.append(AssignSub())
        elif opcode == OPCODE_MULEQU: result.append(AssignMul())
        elif opcode == OPCODE_DIVEQU: result.append(AssignDiv())
        elif opcode == OPCODE_MODEQU: result.append(AssignMod())
        elif opcode == OPCODE_ADD: result.append(Add())
        elif opcode == OPCODE_SUB: result.append(Sub())
        elif opcode == OPCODE_MUL: result.append(Mul())
        elif opcode == OPCODE_DIV: result.append(Div())
        elif opcode == OPCODE_MOD: result.append(Mod())
        elif opcode == OPCODE_AND: result.append(LogicalAnd())
        elif opcode == OPCODE_OR: result.append(LogicalOr())
        elif opcode == OPCODE_INC: result.append(Inc())
        elif opcode == OPCODE_DEC: result.append(Dec())
        elif opcode == OPCODE_NEG: result.append(Neg())
        elif opcode == OPCODE_NOT: result.append(LogicalNot())
        elif opcode == OPCODE_CMP: result.append(Cmp())
        elif opcode == OPCODE_PUSHV: result.append(PushVar(VarId(operand)))
        elif opcode == OPCODE_POPV: result.append(PopVar(VarId(operand)))
        elif opcode == OPCODE_DUP: result.append(Dupe())
        elif opcode == OPCODE_DISC: result.append(Discard())
        elif opcode in (OPCODE_PUSH32, OPCODE_PUSH16, OPCODE_PUSH8):
            signed_operand = operand
            if op_size == 1 and operand >= 0x80: signed_operand -= 0x100
            elif op_size == 2 and operand >= 0x8000: signed_operand -= 0x10000
            elif op_size == 4 and operand >= 0x80000000: signed_operand -= 0x100000000
            if op_size == 4:
                signed_operand = struct.unpack('<i', struct.pack('<I', operand & 0xFFFFFFFF))[0]
            result.append(PushInt(signed_operand))
        elif opcode == OPCODE_JMP: result.append(Jmp(jump_source_map[pc]))
        elif opcode == OPCODE_BLT: result.append(Blt(jump_source_map[pc]))
        elif opcode == OPCODE_BLE: result.append(Ble(jump_source_map[pc]))
        elif opcode == OPCODE_BEQ: result.append(Beq(jump_source_map[pc]))
        elif opcode == OPCODE_BNE: result.append(Bne(jump_source_map[pc]))
        elif opcode == OPCODE_BGE: result.append(Bge(jump_source_map[pc]))
        elif opcode == OPCODE_BGT: result.append(Bgt(jump_source_map[pc]))
        elif opcode == OPCODE_END: result.append(Exit())
        elif opcode == OPCODE_CALL: result.append(Call(CallId(operand)))
        elif opcode == OPCODE_SWITCH: result.append(Switch(SwitchId(operand)))
        else:
            raise DecodeError(f"Bad opcode: {opcode:02X}")
            
    while current_jump_target_idx < len(jump_targets):
        head = jump_targets[current_jump_target_idx]
        result.append(Label(head.jump_id))
        current_jump_target_idx += 1
        
    return result

def decode_string_chunk(strings_data: bytes) -> List[bytes]:
    if not strings_data:
        return []
    string_count = read_u32(strings_data, 0)
    pool_offset = 4 + 4 * string_count
    
    if pool_offset > len(strings_data):
        raise DecodeError("BadStrChunk")
        
    string_table = []
    for i in range(string_count):
        offset = read_u32(strings_data, 4 + i * 4)
        if offset > len(strings_data):
            raise DecodeError("BadStrChunk")
            
        end = pool_offset + offset
        while end < len(strings_data) and strings_data[end] != 0:
            end += 1
            
        string_table.append(strings_data[pool_offset + offset:end])
        
    return string_table

def read_riff_chunks(data: bytes, riff_size: int) -> Dict[str, bytes]:
    chunks = {}
    offset = 12
    
    while offset < riff_size and offset < len(data):
        chunk_name = data[offset:offset+4].decode('utf-8', errors='replace')
        chunk_size = read_u32(data, offset+4)
        chunk_data = data[offset+8:offset+8+chunk_size]
        chunks[chunk_name] = chunk_data
        offset += 8 + chunk_size
        
    return chunks

def decode_script(data: bytes) -> Script:
    riff_head = data[0:4]
    riff_size = read_u32(data, 4)
    riff_name = data[8:12]
    
    if riff_head != b'RIFF' or riff_name != b'SCR ':
        raise DecodeError("Not a valid FoMT script binary (invalid magics)")
        
    chunks = read_riff_chunks(data, min(riff_size, len(data)))
    
    if "CODE" not in chunks:
        raise DecodeError("MissingCodeChunk")
        
    code_data = decode_code_chunk(chunks["CODE"])
    jump_map = get_code_jumps(code_data)
    
    jumps_data = chunks.get("JUMP", b"")
    if jumps_data:
        jumps = decode_jump_chunk(jumps_data)
    else:
        jumps = DecodedJumpChunk([])
        
    case_map = build_case_map(jumps)
    
    instructions = disassemble(code_data, jump_map, case_map)
    strings = decode_string_chunk(chunks.get("STR ", b""))
    
    return Script(instructions, strings)