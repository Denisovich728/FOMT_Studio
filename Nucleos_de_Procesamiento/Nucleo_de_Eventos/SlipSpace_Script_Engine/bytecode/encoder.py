import struct
from typing import List, Dict, Tuple
from ..ir import *
from .opcodes import *

class EncoderHelper:
    def __init__(self):
        self.data = bytearray()
        
    def push_u8(self, val: int):
        self.data.append(val & 0xFF)
        
    def push_u16(self, val: int):
        self.data.extend(struct.pack('<H', val & 0xFFFF))
        
    def push_u32(self, val: int):
        self.data.extend(struct.pack('<I', val & 0xFFFFFFFF))
        
    def write_u32_at(self, offset: int, val: int):
        struct.pack_into('<I', self.data, offset, val & 0xFFFFFFFF)

def write_push(vec: EncoderHelper, val: int):
    val = val & 0xFFFFFFFF
    if val < 0x80:
        vec.push_u8(OPCODE_PUSH8)
        vec.push_u8(val)
    elif val < 0x8000:
        vec.push_u8(OPCODE_PUSH16)
        vec.push_u16(val)
    else:
        vec.push_u8(OPCODE_PUSH32)
        vec.push_u32(val)

@dataclass
class JumpTables:
    tables: List[List[Tuple[CaseEnum, int]]]

def encode_instructions(vec: EncoderHelper, instructions: List[Ins]) -> JumpTables:
    label_map = {}
    jump_map = {}
    
    switch_id_max = 0
    for ins in instructions:
        if isinstance(ins, Switch):
            switch_id_max = max(switch_id_max, ins.switch_id.id + 1)
            
    switches = [[] for _ in range(switch_id_max)]
    
    vec.push_u32(0) # placeholder for code size
    begin = len(vec.data)
    
    for ins in instructions:
        if isinstance(ins, Assign): vec.push_u8(OPCODE_EQU)
        elif isinstance(ins, AssignAdd): vec.push_u8(OPCODE_ADDEQU)
        elif isinstance(ins, AssignSub): vec.push_u8(OPCODE_SUBEQU)
        elif isinstance(ins, AssignMul): vec.push_u8(OPCODE_MULEQU)
        elif isinstance(ins, AssignDiv): vec.push_u8(OPCODE_DIVEQU)
        elif isinstance(ins, AssignMod): vec.push_u8(OPCODE_MODEQU)
        elif isinstance(ins, Add): vec.push_u8(OPCODE_ADD)
        elif isinstance(ins, Sub): vec.push_u8(OPCODE_SUB)
        elif isinstance(ins, Mul): vec.push_u8(OPCODE_MUL)
        elif isinstance(ins, Div): vec.push_u8(OPCODE_DIV)
        elif isinstance(ins, Mod): vec.push_u8(OPCODE_MOD)
        elif isinstance(ins, LogicalAnd): vec.push_u8(OPCODE_AND)
        elif isinstance(ins, LogicalOr): vec.push_u8(OPCODE_OR)
        elif isinstance(ins, Inc): vec.push_u8(OPCODE_INC)
        elif isinstance(ins, Dec): vec.push_u8(OPCODE_DEC)
        elif isinstance(ins, Neg): vec.push_u8(OPCODE_NEG)
        elif isinstance(ins, LogicalNot): vec.push_u8(OPCODE_NOT)
        elif isinstance(ins, Cmp): vec.push_u8(OPCODE_CMP)
        elif isinstance(ins, PushVar):
            vec.push_u8(OPCODE_PUSHV)
            vec.push_u32(ins.var_id.id)
        elif isinstance(ins, PopVar):
            vec.push_u8(OPCODE_POPV)
            vec.push_u32(ins.var_id.id)
        elif isinstance(ins, Dupe): vec.push_u8(OPCODE_DUP)
        elif isinstance(ins, Discard): vec.push_u8(OPCODE_DISC)
        elif isinstance(ins, PushInt):
            write_push(vec, ins.value)
        elif isinstance(ins, Jmp):
            vec.push_u8(OPCODE_JMP)
            jump_map[len(vec.data)] = ins.jump_id
            vec.push_u32(0)
        elif isinstance(ins, Blt):
            vec.push_u8(OPCODE_BLT)
            jump_map[len(vec.data)] = ins.jump_id
            vec.push_u32(0)
        elif isinstance(ins, Ble):
            vec.push_u8(OPCODE_BLE)
            jump_map[len(vec.data)] = ins.jump_id
            vec.push_u32(0)
        elif isinstance(ins, Beq):
            vec.push_u8(OPCODE_BEQ)
            jump_map[len(vec.data)] = ins.jump_id
            vec.push_u32(0)
        elif isinstance(ins, Bne):
            vec.push_u8(OPCODE_BNE)
            jump_map[len(vec.data)] = ins.jump_id
            vec.push_u32(0)
        elif isinstance(ins, Bge):
            vec.push_u8(OPCODE_BGE)
            jump_map[len(vec.data)] = ins.jump_id
            vec.push_u32(0)
        elif isinstance(ins, Bgt):
            vec.push_u8(OPCODE_BGT)
            jump_map[len(vec.data)] = ins.jump_id
            vec.push_u32(0)
        elif isinstance(ins, Call):
            vec.push_u8(OPCODE_CALL)
            vec.push_u32(ins.call_id.id)
        elif isinstance(ins, Switch):
            vec.push_u8(OPCODE_SWITCH)
            vec.push_u32(ins.switch_id.id)
        elif isinstance(ins, Exit):
            vec.push_u8(OPCODE_END)
        elif isinstance(ins, Case):
            switches[ins.switch_id.id].append((ins.case_enum, len(vec.data) - begin))
        elif isinstance(ins, Label):
            label_map[ins.jump_id] = len(vec.data) - begin
            
    for off, target in jump_map.items():
        if target in label_map:
            vec.write_u32_at(off, label_map[target])
            
    # Solo añadir END si el último byte generado NO fue ya un END (0x20)
    # Esto previene que el script crezca 1 byte en cada guardado.
    if len(vec.data) > begin and vec.data[-1] != OPCODE_END:
        vec.push_u8(OPCODE_END)
    elif len(vec.data) == begin: # Script vacío
        vec.push_u8(OPCODE_END)
    
    len_aligned = (len(vec.data) - begin + 3) & ~3
    while len(vec.data) - begin < len_aligned:
        vec.push_u8(OPCODE_NOP)
        
    vec.write_u32_at(begin - 4, len_aligned)
    return JumpTables(switches)

def encode_jump(vec: EncoderHelper, jump_tables: JumpTables):
    tables = jump_tables.tables
    vec.push_u32(len(tables))
    data_begin = len(vec.data)
    
    table_begin = len(vec.data)
    for _ in range(len(tables)): vec.push_u32(0)
    
    for i, jt in enumerate(tables):
        off = len(vec.data) - data_begin
        vec.write_u32_at(table_begin + 4 * i, off)
        
        default_off = None
        for e, off in jt:
            if isinstance(e, CaseDefault):
                default_off = off
                break
                
        if default_off is not None:
            vec.push_u32(len(jt) - 1)
            vec.push_u32(default_off)
        else:
            vec.push_u32(len(jt))
            vec.push_u32(0xFFFFFFFF)
            
        values = []
        for e, off in jt:
            if isinstance(e, CaseVal):
                values.append((e.val, off))
                
        values.sort()
        for val, off in values:
            vec.push_u32(val)
            vec.push_u32(off)
            
def encode_str(vec: EncoderHelper, str_tab: List[bytes]):
    vec.push_u32(len(str_tab))
    table_begin = len(vec.data)
    for _ in range(len(str_tab)): vec.push_u32(0)
    data_begin = len(vec.data)
    
    for i, s in enumerate(str_tab):
        off = len(vec.data) - data_begin
        vec.write_u32_at(table_begin + 4 * i, off)
        vec.data.extend(s)
        vec.push_u8(0)

def encode_script(script: Script, target_size: int = 0) -> bytes:
    vec = EncoderHelper()
    vec.data.extend(b"RIFF")
    vec.push_u32(0)
    vec.data.extend(b"SCR ")
    
    chunk_hook = len(vec.data)
    vec.data.extend(b"CODE")
    vec.push_u32(0)
    
    jump_tables = encode_instructions(vec, script.instructions)
    chunk_len = len(vec.data) - chunk_hook - 8
    vec.write_u32_at(chunk_hook + 4, chunk_len)
    
    if len(jump_tables.tables) > 0:
        chunk_hook = len(vec.data)
        vec.data.extend(b"JUMP")
        vec.push_u32(0)
        encode_jump(vec, jump_tables)
        chunk_len = len(vec.data) - chunk_hook - 8
        vec.write_u32_at(chunk_hook + 4, chunk_len)
        
    if script.strings:
        chunk_hook = len(vec.data)
        vec.data.extend(b"STR ")
        vec.push_u32(0)
        encode_str(vec, script.strings)
        chunk_len = len(vec.data) - chunk_hook - 8
        vec.write_u32_at(chunk_hook + 4, chunk_len)
    
    # FIX: Recalcular total_len para que el RIFF header sea exacto
    total_len = len(vec.data)
    vec.write_u32_at(4, total_len - 8) # RIFF size is total - 8
    
    return bytes(vec.data)
