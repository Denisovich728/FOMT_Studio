import struct
import os

# Mocking enough IR to run the decoder
class VarId:
    def __init__(self, id): self.id = id
class CallId:
    def __init__(self, id): self.id = id
class JumpId:
    def __init__(self, id): self.id = id
class SwitchId:
    def __init__(self, id): self.id = id
class CaseEnum: pass
class CaseVal(CaseEnum):
    def __init__(self, val): self.val = val
class CaseDefault(CaseEnum): pass

OPCODE_SWITCH = 0x24 # Guessing from the dump: ... 18 c6 00 00 00 24 00 00 00 00 ...

def read_u32(data, off): return struct.unpack_from('<I', data, off)[0]

def analyze_1011():
    rom_path = 'j:/Repositorios/fomt_studio/Modded_FoMT3.gba'
    with open(rom_path, 'rb') as f:
        rom = f.read()
    
    idx_off = 0x0F89D8
    event_ptr = struct.unpack('<I', rom[idx_off + 1011*4 : idx_off + 1011*4 + 4])[0]
    event_off = event_ptr & 0x1ffffff
    
    print(f"Evento 1011 en {hex(event_off)}")
    riff_size = read_u32(rom, event_off + 4)
    data = rom[event_off : event_off + riff_size + 8]
    
    # Encontrar el chunk CODE
    code_idx = data.find(b'CODE')
    code_size = read_u32(data, code_idx + 4)
    code_data = data[code_idx + 12 : code_idx + 8 + code_size]
    
    # Encontrar el chunk JUMP
    jump_idx = data.find(b'JUMP')
    jump_size = read_u32(data, jump_idx + 4)
    jump_data = data[jump_idx + 8 : jump_idx + 8 + jump_size]
    
    print(f"CODE size: {code_size}, JUMP size: {jump_size}")
    
    if jump_data:
        ent_count = read_u32(jump_data, 0)
        print(f"Switch count: {ent_count}")
        off = 4 + ent_count * 4
        for s in range(ent_count):
            entries = read_u32(jump_data, off)
            default = read_u32(jump_data, off + 4)
            print(f"Switch {s}: {entries} entries, default {hex(default)}")
            off += 8
            for e in range(entries):
                val = struct.unpack_from('<i', jump_data, off)[0]
                target = read_u32(jump_data, off + 4)
                print(f"  Case {hex(val & 0xFFFFFFFF)} -> {hex(target)}")
                off += 8

analyze_1011()
