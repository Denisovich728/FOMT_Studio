# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.7.0)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
"""
Motor de Gráficos y Mapas de FoMT Studio — Reescritura Total v2.0
══════════════════════════════════════════════════════════════════
Reemplaza por completo la lógica anterior.

Basado en ingeniería inversa directa de BlueSpider (mapped.pyd, mapdata.pyd):
  • parse_map_header  → estructura de 24 bytes confirmada
  • get_map_headers   → offsets correctos para versión USA
  • BlocksData.draw_block_layers → algoritmo de 4 sub-tiles × 2 bytes
  • Block layout: 16 bytes total = 4 subtiles_bajo + 4 subtiles_alto
    Cada subtile (2 bytes):
      byte0: tile_index (bits 0-9 en uint16 LE)
      byte1[3:0]: flip (bit2=x_flip, bit3=y_flip)
      byte1[7:4]: palette_index
  • MapData.load_tilesets → usa pals_ptr, img_data_ptr, block_data_ptr
  • Warp/Script events extraídos de la tabla de objetos del mapa
  • LZ77 decompressor (header 0x10) y Popuri RLE (header 0x70)
"""
import struct
import zlib
from PIL import Image
from typing import List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
try:
    import unicorn
    from unicorn.arm_const import *
    HAS_UNICORN = True
except ImportError:
    HAS_UNICORN = False

# ═══════════════════════════════════════════════════════════════════
#  CONSTANTES — extraídas de BlueSpider (@USATH confirmada)
# ═══════════════════════════════════════════════════════════════════

TILE_W = TILE_H = 8       # Tiles GBA: 8×8 píxeles
BLOCK_W = BLOCK_H = 16    # Bloques del mapa: 2×2 tiles = 16×16 px
SUBTILE_BYTES = 2         # Cada sub-tile ocupa 2 bytes
BLOCK_BYTES = 16          # 4 sub-tiles capa baja + 4 sub-tiles capa alta
BITS_PER_PIXEL_4BPP = 4
TILE_BYTES_4BPP = (TILE_W * TILE_H * BITS_PER_PIXEL_4BPP) // 8  # = 32 bytes

# Tabla de posiciones de sub-tiles dentro de un bloque 16×16
# Orden GBA: top-left, top-right, bottom-left, bottom-right
SUBTILE_POSITIONS = [
    (0, 0), (8, 0),    # Fila superior
    (0, 8), (8, 8),    # Fila inferior
]

# Tablas de GFX de tilesets (BlueSpider TABLE_A + TABLE_B de mapped.pyd)
TILESET_GFX_TABLE_USA = [
    0x836800, 0x835E00, 0x835600, 0x834E00, 0x834600, 0x833E00,
    0x833600, 0x832E00, 0x832600, 0x831E00, 0x831600, 0x830E00,
    0x830600, 0x82FE00, 0x82F300, 0x838F00, 0x83B600, 0x83DF00,
    0x840800, 0x843100, 0x845A00, 0x848300, 0x84AC00, 0x84D500,
    0x84FE00, 0x852700, 0x855000, 0x857900, 0x85A200,
    0x874D00, 0x874500, 0x873D00, 0x873500, 0x872D00, 0x872500,
    0x871D00, 0x871500, 0x870D00, 0x870500,
    0x86FD00, 0x86F500, 0x86ED00, 0x86E600,
]

# Tabla de nombres de mapas (fomt_map_labels — BlueSpider mapped.pyd)
FOMT_MAP_LABELS = {
    0:  "Farm Normal",
    1:  "Farm Winter",
    2:  "Rose Square",
    3:  "Rose Square Winter",
    4:  "Town North",
    5:  "Town North Winter",
    6:  "Town South",
    7:  "Town South Winter",
    8:  "Beach",
    9:  "Beach Winter",
    10: "Church Back",
    11: "Church Back Winter",
    12: "Forest",
    13: "Forest Winter",
    14: "Mothers Hill Middle",
    15: "Mothers Hill Middle Winter",
    16: "Mothers Hill Top",
    17: "Mothers Hill Top Winter",
    18: "Aja Winery 1ST Floor",
    19: "Aja Winery 2ND Floor",
    20: "Aja Storage",
    21: "Aja Basement",
    22: "Doug Inn 1ST Floor",
    23: "Doug Room",
    24: "Doug Inn 2ND Floor",
    25: "Jeff Shop",
    26: "Jeff Room",
    27: "Kai Shop",
    28: "Zack House",
    29: "Hospital 1ST Floor",
    30: "Hospital 2ND Floor",
    31: "Church",
    32: "Mary Library 1ST Floor",
    33: "Mary Library 2ND Floor",
    34: "Basil House 1ST Floor",
    35: "Basil House 2ND Floor",
    36: "Chicken Coop 1",
    37: "Chicken Coop 2",
    38: "Barn 1",
    39: "Barn 2",
    40: "Horse Stable",
    41: "House LV1",
    42: "House LV2",
    43: "House LV3",
    44: "Lilia House 1ST Floor",
    45: "Lilia House 2ND Floor",
    46: "Barley House 1ST Floor",
    47: "Barley House 2ND Floor",
    48: "Saibara House",
    49: "Gotz House",
    50: "Thomas House",
    51: "Ellen House",
    52: "Harvest Sprites House",
    53: "Mountain House",
    54: "Beach House",
    55: "Town House",
    56: "Mine Entrance",
    57: "Mine Floor Type 1",
    58: "Mine Floor Type 2",
    59: "Mine Floor Type 3",
    60: "Mine Cenote",
    61: "Mine Cenote Entrance",
    62: "Tutorial Field",
    63: "Tutorial Barn Outside",
    64: "Tutorial Barn",
    65: "Tutorial Chicken Cop",
}

# Tabla de permisos de movimiento (behaviour_data_ptr)
MOVEMENT_LABEL  = {
    0x00: "0", # Libre
    0x01: "1", # Bloqueado
    0x02: "1", # Bloqueado (NPC?)
    0x04: "~", # Agua
    0x08: "^", # Salto/Borde
    0x10: "S", # Silla/Sentarse
    0x20: "M", # Mostrador
    0x40: "H", # Hierba/Cultivo
    0x79: "?", # Descubierto en Ptr 5
}
MOVEMENT_LABELS = MOVEMENT_LABEL
MOVEMENT_BLOCKED = {0x01, 0x02, 0x20}


# ═══════════════════════════════════════════════════════════════════
#  DESCOMPRESOR LZ77 (estándar GBA, header 0x10)
# ═══════════════════════════════════════════════════════════════════
def decompress_lz77(data: bytes, offset: int = 0) -> bytes:
    """
    Descompresor LZ77 estándar de GBA.
    Header: 1 byte tipo (0x10) + 3 bytes tamaño decomprimido (LE 24-bit).
    """
    if offset >= len(data):
        return b''
    header = data[offset]
    if header != 0x10:
        raise ValueError(f"LZ77: header inválido 0x{header:02X} en 0x{offset:06X}")
    
    decomp_size = struct.unpack_from('<I', data, offset)[0] >> 8
    out = bytearray(decomp_size)
    out_pos = 0
    in_pos = offset + 4

    while out_pos < decomp_size and in_pos < len(data):
        flags = data[in_pos]; in_pos += 1
        for bit in range(7, -1, -1):
            if out_pos >= decomp_size:
                break
            if (flags >> bit) & 1:
                # Referencia hacia atrás
                b0 = data[in_pos]; b1 = data[in_pos+1]; in_pos += 2
                length = ((b0 >> 4) & 0xF) + 3
                disp   = (((b0 & 0xF) << 8) | b1) + 1
                src = out_pos - disp
                for _ in range(length):
                    if out_pos >= decomp_size: break
                    out[out_pos] = out[src % len(out)]
                    out_pos += 1; src += 1
            else:
                out[out_pos] = data[in_pos]; in_pos += 1; out_pos += 1
    return bytes(out)


class BitReader:
    def __init__(self, data, offset):
        self.data = data
        self.pos = offset
        self.readBuff = 0
        self.readBits = 0

    def rshift(self, val, n):
        return (val >> (n & 0x1F)) & 0xFFFFFFFF

    def lshift(self, val, n):
        return (val << (n & 0x1F)) & 0xFFFFFFFF

    def read_bits(self, count):
        data = self.rshift(self.readBuff, 32 - count)
        self.readBits -= count
        if self.readBits < 0:
            if self.pos + 4 <= len(self.data):
                newRead = struct.unpack_from('<I', self.data, self.pos)[0]
            else:
                newRead = 0
            self.pos += 4
            self.readBuff = self.lshift(newRead, -self.readBits)
            self.readBits += 32
            return data | self.rshift(newRead, self.readBits)
        self.readBuff = self.lshift(self.readBuff, count)
        return data

    def read_bit(self):
        return self.read_bits(1)


_SHARED_LZ_LADDER = []

class HuffLZDecompressor:
    """
    Descompresor nativo de BlueSpider: HuffLZ + DeltaNibble.
    Reemplaza la necesidad de emular la ROM con Unicorn.
    """
    def __init__(self, data, offset):
        self.reader = BitReader(data, offset)
        self.out = bytearray()
        self.huffman = {}
        
    def decompress(self):
        global _SHARED_LZ_LADDER
        header32 = self.reader.read_bits(32)
        targetSize = header32 >> 8
        typeByte = self.reader.read_bits(8)
        
        compType = typeByte & 0x7
        huffType = (typeByte >> 3) & 0x3
        filtType = (typeByte >> 5) & 0x7
        
        # 1. Huffman pass
        if huffType == 0:
            def read_byte(): return self.reader.read_bits(8)
            self.read_byte = read_byte
        elif huffType == 2:
            self.read_huffman_tree(8)
            def read_byte(): return self.read_byte_huff8()
            self.read_byte = read_byte
        else:
            raise NotImplementedError(f"Unsupported huffType {huffType}")
            
        # 2. Decomp pass
        if compType == 3:
            self.read_lz_lookup_ladder(3)
            while len(self.out) < targetSize:
                if self.reader.read_bit() == 0:
                    self.out.append(self.read_byte())
                    self.out.append(self.read_byte())
                else:
                    i = self.reader.read_bits(2)
                    if i < 3:
                        offset = _SHARED_LZ_LADDER[i]['offset']
                        bits = _SHARED_LZ_LADDER[i]['bits']
                        distance = offset + self.reader.read_bits(bits)
                        size = self.reader.read_bits(3) + 2
                        self.apply_lz_2bytes(distance, size)
                    elif i == 3:
                        count = 0
                        value = 0
                        while True:
                            value = self.reader.read_bits(3)
                            count = (count << 2) | (value >> 1)
                            if (value & 1) == 0: break
                        if self.reader.read_bit() == 0:
                            for _ in range(count + 1):
                                self.out.append(self.read_byte())
                                self.out.append(self.read_byte())
                        else:
                            j = self.reader.read_bits(2)
                            offset = _SHARED_LZ_LADDER[j]['offset']
                            bits = _SHARED_LZ_LADDER[j]['bits']
                            distance = offset + self.reader.read_bits(bits)
                            size = self.reader.read_bits(3) + (count << 3) + 2
                            self.apply_lz_2bytes(distance, size)
        elif compType == 1:
            self.read_lz_lookup_ladder(4)
            while len(self.out) < targetSize:
                if self.reader.read_bit() == 0:
                    self.out.append(self.read_byte())
                else:
                    i = self.reader.read_bits(2)
                    offset = _SHARED_LZ_LADDER[i]['offset']
                    bits = _SHARED_LZ_LADDER[i]['bits']
                    distance = offset + self.reader.read_bits(bits)
                    size = self.reader.read_bits(4) + 3
                    self.apply_lz_bytes(distance, size)
        elif compType == 0:
            self.read_lz_lookup_ladder(2)
            while len(self.out) < targetSize:
                i = self.reader.read_bits(2)
                if i < 2:
                    offset = _SHARED_LZ_LADDER[i]['offset']
                    bits = _SHARED_LZ_LADDER[i]['bits']
                    distance = offset + self.reader.read_bits(bits)
                    size = self.reader.read_bits(6) + 3
                    self.apply_lz_bytes(distance, size)
                elif i == 2:
                    count = self.reader.read_bits(6) + 1
                    for _ in range(count):
                        self.out.append(self.read_byte())
                elif i == 3:
                    size = self.reader.read_bits(6) + 1
                    self.out.append(self.reader.read_bits(8))
                    self.apply_lz_bytes(1, size)
        elif compType == 4:
            while len(self.out) < targetSize:
                self.out.append(self.read_byte())
        else:
            raise NotImplementedError(f"Unsupported compType {compType}")
            
        # 3. Filter pass
        if filtType == 0:
            pass
        elif filtType == 1:
            acc = 0
            for i in range(len(self.out)):
                val = self.out[i]
                a = val & 0xF
                b = (val >> 4) & 0xF
                b = (b + acc) & 0xF
                acc = b
                a = (a + acc) & 0xF
                acc = a
                self.out[i] = a | (b << 4)
        elif filtType == 2:
            pass # No implementado en Lua original, asumimos 0
        elif filtType == 3:
            acc = 0
            for i in range(len(self.out)):
                val = self.out[i]
                a = val & 0xF
                b = (val >> 4) & 0xF
                a = (a + acc) & 0xF
                b = (b + a) & 0xF
                acc = b
                self.out[i] = a | (b << 4)
        elif filtType == 4:
            acc = 0
            for i in range(len(self.out)):
                val = self.out[i]
                acc = (acc + val) & 0xFF
                self.out[i] = acc
                
        return bytes(self.out)

    def read_lz_lookup_ladder(self, count):
        global _SHARED_LZ_LADDER
        nextOffset = 1
        for i in range(count):
            bits = self.reader.read_bits(4) + 1
            if i < len(_SHARED_LZ_LADDER):
                _SHARED_LZ_LADDER[i] = {'bits': bits, 'offset': nextOffset}
            else:
                _SHARED_LZ_LADDER.append({'bits': bits, 'offset': nextOffset})
            nextOffset += (1 << bits)
            
    def apply_lz_bytes(self, distance, length):
        viewOffset = len(self.out) - distance
        for _ in range(length):
            self.out.append(self.out[viewOffset])
            viewOffset += 1

    def apply_lz_2bytes(self, distance, length):
        viewOffset = len(self.out) - (distance * 2)
        for _ in range(length):
            self.out.append(self.out[viewOffset])
            self.out.append(self.out[viewOffset+1])
            viewOffset += 2

    def read_huffman_tree(self, bits):
        self.huffman = {}
        currentNodePath = 0
        for i in range(bits * 2): 
            count = self.reader.read_bits(bits)
            currentNodePath <<= 1
            for _ in range(count):
                node = self.huffman
                for j in range(i, 0, -1):
                    huffBit = (currentNodePath >> j) & 1
                    if huffBit not in node:
                        node[huffBit] = {}
                    node = node[huffBit]
                node[currentNodePath & 1] = {'value': self.reader.read_bits(bits)}
                currentNodePath += 1

    def read_byte_huff8(self):
        node = self.huffman
        while 'value' not in node:
            t = self.reader.read_bit()
            node = node[t]
        return node['value']


def apply_delta_4bpp(data: bytes) -> bytes:
    """Aplica la transformación in-place Delta-Nibble que FoMT realiza en VRAM tras descomprimir (usado para LZ77 puro)."""
    out = bytearray(len(data))
    r5 = 0
    for i in range(0, len(data)-1, 2):
        r2 = struct.unpack_from('<H', data, i)[0]
        r1 = r2 >> 4
        r3 = r2 >> 12
        r4 = r2 >> 8

        r1 = (r1 + r5) & 0xFFFF
        r2 = (r2 + r1) & 0xFFFF
        r3 = (r3 + r2) & 0xFFFF
        r5 = (r4 + r3) & 0xFFFF

        r6 = 0xF
        out_r1 = r1 & r6
        out_r2 = r2 & r6
        out_r5 = r5 & r6
        out_r3 = r3 & r6

        out_word = out_r2 | (out_r1 << 4) | (out_r5 << 8) | (out_r3 << 12)
        struct.pack_into('<H', out, i, out_word)
    return bytes(out)


def decompress_unicorn(data, offset):
    import struct
    from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_PROT_ALL, UC_PROT_READ, UC_PROT_EXEC, UC_HOOK_CODE
    from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
    
    ROM_BASE = 0x08000000
    RAM_BASE = 0x02000000
    STACK_BASE = 0x03000000
    
    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    
    # Map memory
    uc.mem_map(ROM_BASE, 32 * 1024 * 1024, UC_PROT_READ | UC_PROT_EXEC)
    uc.mem_write(ROM_BASE, data)
    
    uc.mem_map(RAM_BASE, 16 * 1024 * 1024, UC_PROT_ALL)
    uc.mem_map(STACK_BASE, 1 * 1024 * 1024, UC_PROT_ALL)
    
    uc.reg_write(UC_ARM_REG_R0, ROM_BASE + offset)
    uc.reg_write(UC_ARM_REG_R1, RAM_BASE)
    uc.reg_write(UC_ARM_REG_SP, STACK_BASE + 0x10000)
    uc.reg_write(UC_ARM_REG_LR, 0x08111111)
    
    targetSize = struct.unpack_from('<I', data, offset)[0] >> 8
    if targetSize == 0:
        return bytearray()
        
    # Search for the true Popuri Decompressor routine (push {r4-r7, lr}; mov r4, r8; mov r5, sb...)
    routine_bytes = bytes.fromhex('f0b544464d4656465f46f0b4634a')
    routine_offset = data.find(routine_bytes)
    
    if routine_offset == -1:
        routine_offset = 0xD102C
        
    # GBA (ARMv4T) doesn't switch to ARM mode on 'pop {pc}' if the address is even, 
    # but Unicorn defaults to ARMv5T interworking behavior and crashes. We hook it to fix it.
    def hook_code(uc, address, size, user_data):
        if (address & 1) == 0:
            val = struct.unpack_from('<H', data, (address - ROM_BASE) & 0x1FFFFFF)[0]
            if (val & 0xFF00) == 0xBD00:  # pop {Rlist, pc}
                rlist = val & 0xFF
                sp = uc.reg_read(UC_ARM_REG_SP)
                mem_offset = 0
                for i in range(8):
                    if (rlist & (1 << i)):
                        r_val = struct.unpack_from('<I', uc.mem_read(sp + mem_offset, 4))[0]
                        reg = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, 
                               UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7][i]
                        uc.reg_write(reg, r_val)
                        mem_offset += 4
                pc_val = struct.unpack_from('<I', uc.mem_read(sp + mem_offset, 4))[0]
                mem_offset += 4
                uc.reg_write(UC_ARM_REG_SP, sp + mem_offset)
                uc.reg_write(UC_ARM_REG_PC, pc_val | 1) # Force Thumb mode
                
    uc.hook_add(UC_HOOK_CODE, hook_code)
        
    try:
        uc.emu_start(ROM_BASE + routine_offset | 1, 0x08111110)
    except Exception:
        pass
        
    return bytearray(uc.mem_read(RAM_BASE, targetSize))

def decompress_popuri(data: bytes, offset: int) -> bytearray:
    """
    Descomprime datos comprimidos con el algoritmo "Popuri" (0x70).
    Usamos el motor Unicorn para garantizar extracción byte-perfect.
    """
    return decompress_unicorn(data, offset)

def decompress_auto(data: bytes, offset: int) -> bytes:
    """Detecta automáticamente LZ77 o Popuri y descomprime."""
    if offset >= len(data):
        return b''
    header = data[offset]
    if header == 0x10:
        return decompress_lz77(data, offset)
    elif header == 0x70:
        return decompress_popuri(data, offset)
    elif header == 0x00:
        # Sin compresión — datos crudos (rare pero válido en FoMT)
        if offset + 4 > len(data): return b""
        size = struct.unpack_from('<I', data, offset)[0] >> 8
        if offset + 4 + size > len(data): size = len(data) - (offset + 4)
        return data[offset+4:offset+4+size]
    else:
        raise ValueError(f"Formato desconocido 0x{header:02X} en 0x{offset:06X}")

class BitWriter:
    def __init__(self):
        self.out_words = []
        self.current_word = 0
        self.bits_in_word = 0

    def write_bits(self, value, count):
        while count > 0:
            space = 32 - self.bits_in_word
            if count <= space:
                self.current_word |= (value & ((1 << count) - 1)) << (space - count)
                self.bits_in_word += count
                count = 0
                if self.bits_in_word == 32:
                    self.out_words.append(self.current_word)
                    self.current_word = 0
                    self.bits_in_word = 0
            else:
                top_bits = (value >> (count - space)) & ((1 << space) - 1)
                self.current_word |= top_bits
                self.out_words.append(self.current_word)
                self.current_word = 0
                self.bits_in_word = 0
                count -= space

    def flush(self):
        if self.bits_in_word > 0:
            self.out_words.append(self.current_word)
            self.current_word = 0
            self.bits_in_word = 0

    def get_bytes(self):
        self.flush()
        out = bytearray()
        import struct
        for w in self.out_words:
            out.extend(struct.pack('<I', w))
        return bytes(out)

def compress_popuri(data: bytes) -> bytes:
    """
    Compresor nativo 100% auténtico para FoMT (0x70) con soporte LZ completo.
    Codifica un flujo bit-perfect usando el compType = 0 soportado
    directamente por la ROM (secuencias de literales crudos mezclados con LZ).
    Garantiza una compresión óptima sin exceder el tamaño original en la ROM.
    """
    size = len(data)
    bw = BitWriter()
    
    # 1. header32 (32 bits)
    bw.write_bits((size << 8) | 0x70, 32)
    # 2. typeByte (8 bits). compType=0, huffType=0, filtType=0 -> 0
    bw.write_bits(0, 8)
    # 3. lz lookup ladder (2 elementos, 4 bits c/u).
    # ladder 0 usará 12 bits para distancias (hasta 4096), ladder 1 sin usar
    bw.write_bits(11, 4) # 12 bits = 11 + 1
    bw.write_bits(0, 4)  # no usado

    # 4. Secuencias de compresión (LZ + Literales)
    pos = 0
    while pos < size:
        best_len = 0
        best_dist = 0
        max_dist = min(pos, 4096)
        max_len = min(66, size - pos)
        
        # Búsqueda inversa para coincidencia LZ
        if max_len >= 3 and max_dist >= 1:
            for d in range(1, max_dist + 1):
                match_len = 0
                while match_len < max_len and data[pos - d + match_len] == data[pos + match_len]:
                    match_len += 1
                if match_len > best_len:
                    best_len = match_len
                    best_dist = d
                    if best_len == max_len:
                        break
                        
        if best_len >= 3:
            # Codificar referencia LZ usando ladder 0 (i = 0)
            bw.write_bits(0, 2)
            bw.write_bits(best_dist - 1, 12)
            bw.write_bits(best_len - 3, 6)
            pos += best_len
        else:
            # Racha de literales (hasta 64) hasta la próxima buena coincidencia
            lit_len = 1
            while lit_len < min(64, size - pos):
                next_pos = pos + lit_len
                next_max_dist = min(next_pos, 4096)
                next_max_len = min(66, size - next_pos)
                found_match = False
                if next_max_len >= 3 and next_max_dist >= 1:
                    # Lookahead rápido
                    for d in range(1, min(next_max_dist, 256) + 1):
                        if data[next_pos - d] == data[next_pos] and data[next_pos - d + 1] == data[next_pos + 1] and data[next_pos - d + 2] == data[next_pos + 2]:
                            found_match = True
                            break
                if found_match:
                    break
                lit_len += 1
                
            bw.write_bits(2, 2)              # i = 2 (indicador de secuencia literal)
            bw.write_bits(lit_len - 1, 6)    # contador de literales (6 bits)
            for b in data[pos : pos + lit_len]:
                bw.write_bits(b, 8)
            pos += lit_len

    return bw.get_bytes()

def compress_lz77(data: bytes) -> bytes:
    """Compresor LZ77 GBA estándar (0x10). Implementación acelerada."""
    out = bytearray()
    size = len(data)
    out.append(0x10)
    out.append(size & 0xFF)
    out.append((size >> 8) & 0xFF)
    out.append((size >> 16) & 0xFF)
    
    # Pre-calcular posiciones para acelerar la búsqueda
    positions = {}
    for i in range(size - 2):
        triplet = tuple(data[i:i+3])
        if triplet not in positions:
            positions[triplet] = []
        positions[triplet].append(i)
        
    i = 0
    while i < size:
        flags_pos = len(out)
        out.append(0)
        flags = 0
        
        for bit in range(7, -1, -1):
            if i >= size:
                break
                
            best_len = 2
            best_disp = 0
            
            triplet = tuple(data[i:i+3]) if i + 3 <= size else None
            if triplet in positions:
                for j in reversed(positions[triplet]):
                    if j >= i: continue
                    disp = i - j
                    if disp > 4096: break # Fuera de la ventana
                    
                    match_len = 3
                    while match_len < 18 and i + match_len < size and data[j + match_len] == data[i + match_len]:
                        match_len += 1
                        
                    if match_len > best_len:
                        best_len = match_len
                        best_disp = disp
                        if best_len == 18:
                            break
                            
            if best_len >= 3:
                flags |= (1 << bit)
                b0 = (((best_len - 3) & 0xF) << 4) | (((best_disp - 1) >> 8) & 0xF)
                b1 = (best_disp - 1) & 0xFF
                out.append(b0)
                out.append(b1)
                i += best_len
            else:
                out.append(data[i])
                i += 1
                
        out[flags_pos] = flags
        
    while len(out) % 4 != 0:
        out.append(0)
    return bytes(out)


# ═══════════════════════════════════════════════════════════════════
#  PALETA GBA (16 colores × 2 bytes cada uno, formato BGR555)
# ═══════════════════════════════════════════════════════════════════
class GBAPalette:
    """
    Paleta de 16 colores en formato BGR555.
    Compatible con MapData.get_palettes de BlueSpider.
    """
    def __init__(self, raw: bytes):
        self.colors: List[Tuple[int,int,int,int]] = []  # RGBA
        for i in range(min(16, len(raw)//2)):
            bgr = struct.unpack_from('<H', raw, i*2)[0]
            r = ((bgr >> 0)  & 0x1F) << 3
            g = ((bgr >> 5)  & 0x1F) << 3
            b = ((bgr >> 10) & 0x1F) << 3
            alpha = 0 if i == 0 else 255  # color 0 = transparente
            self.colors.append((r, g, b, alpha))

    def get(self, idx: int) -> Tuple[int,int,int,int]:
        if 0 <= idx < len(self.colors):
            return self.colors[idx]
        return (0, 0, 0, 0)


# ═══════════════════════════════════════════════════════════════════
#  TILE GBA (8×8 píxeles, 4bpp)
# ═══════════════════════════════════════════════════════════════════
class GBATile:
    """Un tile de 8×8 en formato 4bpp (32 bytes)."""
    BYTES = TILE_BYTES_4BPP  # 32

    def __init__(self, raw: bytes):
        # Asegurar que tenemos al menos 32 bytes, rellenando con ceros si es necesario
        if len(raw) < self.BYTES:
            self._data = raw.ljust(self.BYTES, b'\x00')
        else:
            self._data = raw[:self.BYTES]

    def get_pixel(self, x: int, y: int) -> int:
        """Retorna el índice de color (0-15) del píxel en (x, y)."""
        idx = y * 4 + x // 2
        byte = self._data[idx]
        return (byte >> 4) if (x & 1) else (byte & 0xF)

    def render(self, palette: GBAPalette,
               h_flip: bool = False,
               v_flip: bool = False) -> Image.Image:
        """Renderiza el tile como imagen RGBA de 8×8."""
        img = Image.new('RGBA', (TILE_W, TILE_H))
        px = img.load()
        for y in range(TILE_H):
            for x in range(TILE_W):
                sy = (TILE_H-1-y) if v_flip else y
                sx = (TILE_W-1-x) if h_flip else x
                color_idx = self.get_pixel(sx, sy)
                px[x, y] = palette.get(color_idx)
        return img


# ═══════════════════════════════════════════════════════════════════
#  GBA TILEMAP ENTRY
# ═══════════════════════════════════════════════════════════════════
class TilemapEntry:
    """
    2 bytes que describen un tile en el tilemap GBA.
      uint16 LE:
        bits 0-9:  tile_index en el tileset
        bit 10:    H-flip (x flip)
        bit 11:    V-flip (y flip)
        bits 12-15: palette_index (0-15)
    """
    __slots__ = ['tile_idx', 'h_flip', 'v_flip', 'palette_idx']
    def __init__(self, raw2: bytes):
        val = struct.unpack_from('<H', raw2)[0]
        self.tile_idx    = val & 0x3FF
        self.h_flip      = bool((val >> 10) & 1)
        self.v_flip      = bool((val >> 11) & 1)
        self.palette_idx = (val >> 12) & 0xF




# ═══════════════════════════════════════════════════════════════════
#  WARP y SCRIPT TRIGGERS
# ═══════════════════════════════════════════════════════════════════
class Warp:
    """
    Punto de teletransporte o Losa (Trigger). Estructura de 8 bytes:
    [X:1][Y:1][ScriptID:2][Metadata:4]
    """
    STRIDE = 8
    def __init__(self, data: bytes, warp_id: int, rom_offset: int = 0):
        self.id = warp_id
        self.rom_offset = rom_offset
        if len(data) >= 8:
            self.x          = data[0]
            self.y          = data[1]
            self.script_id  = struct.unpack_from('<H', data, 2)[0]
            self.metadata   = data[4:8]
        else:
            self.x = self.y = self.script_id = 0
            self.metadata = b'\x00\x00\x00\x00'

    def to_bytes(self) -> bytes:
        return struct.pack('<BBH', self.x, self.y, self.script_id) + self.metadata

    def get_label(self) -> str:
        # En FoMT un Warp dispara un Script (que a su vez hace Warp_Player)
        return f"Script_0x{self.script_id:04X}"

    def __repr__(self):
        return f"Warp#{self.id}({self.x},{self.y})→{self.get_label()}"


class ScriptTrigger:
    """
    Trigger de Interacción en el mapa (Carteles, NPCs).
    Estructura de 8 bytes:
      [X:1][Y:1][ScriptID:2][Metadata:4]
    """
    STRIDE = 8

    def __init__(self, data: bytes, tid: int, rom_offset: int = 0):
        self.id = tid
        self.rom_offset = rom_offset
        if len(data) >= 8:
            self.x         = data[0]
            self.y         = data[1]
            self.script_id = struct.unpack_from('<H', data, 2)[0]
            self.metadata  = data[4:8]
        else:
            self.x = self.y = self.script_id = 0
            self.metadata = b'\x00\x00\x00\x00'

    def to_bytes(self) -> bytes:
        return struct.pack('<BBH', self.x, self.y, self.script_id) + self.metadata

    def __repr__(self):
        return f"Script#{self.id}({self.x},{self.y}) → 0x{self.script_id:04X}"


# ═══════════════════════════════════════════════════════════════════
#  CABECERA DE MAPA (O(1) Array of Structs)
# ═══════════════════════════════════════════════════════════════════
class MapHeader:
    """
    Estructura de 40 bytes (<8I2HI).
    Ptr 0: GFX Tileset
    Ptr 1: Palettes
    Ptr 3: BG1 Tilemap
    Ptr 4: BG2 Tilemap
    Ptr 5: Collision
    Ptr 6, 7: Objects/Scripts
    """
    STRIDE = 40

    def __init__(self, map_id: int, offset: int, data: bytes):
        self.map_id     = map_id
        self.offset     = offset
        
        unpacked = struct.unpack('<8I2HI', data)
        self.p_gfx      = unpacked[0]
        self.p_pal1     = unpacked[1]
        self.p_pal2     = unpacked[2]
        self.p_bg3      = unpacked[3]
        self.p_bg2      = unpacked[4]
        self.p_bg1      = unpacked[5]
        self.p_obj1     = unpacked[6]
        self.p_obj2     = unpacked[7]
        
        self.width      = unpacked[8]
        self.height     = unpacked[9]
        self.attributes = unpacked[10]
        self.tileset_id = 0 # No longer used
        self.name_id    = 0

        # Datos cargados con load_data()
        self.tiles      : List[GBATile]       = []
        self.blocks_data: bytes               = b''
        self.palettes   : List[GBAPalette]    = []
        self.collision  : Optional[bytes]     = None
        self.tilemap_bg3: Optional[bytes]     = None
        self.tilemap_bg2: Optional[bytes]     = None
        self.tilemap_bg1: Optional[bytes]     = None
        self.warps      : List[Warp]          = []
        self.scripts    : List[ScriptTrigger] = []
        self._loaded    = False

    @property
    def layout_bg3_offset(self) -> int: return self.p_bg3 & 0x01FFFFFF
    @property
    def layout_bg2_offset(self) -> int: return self.p_bg2 & 0x01FFFFFF
    @property
    def layout_bg1_offset(self) -> int: return self.p_bg1 & 0x01FFFFFF
    @property
    def objects_offset(self) -> int: return self.p_obj1 & 0x01FFFFFF

    def get_name(self) -> str:
        return FOMT_MAP_LABELS.get(self.map_id, f"Map {self.map_id:03d}")

    def load_data(self, rom: bytes) -> bool:
        try:
            self._load_palettes(rom)
            self._load_tileset(rom)
            self._load_tilemap(rom)
            # Cargar colisiones (crudo, ancho x alto)
            off_col = self.p_obj2 & 0x01FFFFFF
            if off_col and off_col < len(rom):
                size = self.width * self.height
                self.collision = rom[off_col : off_col + size]
            
            self._load_objects(rom)
            self._loaded = True
            return True
        except Exception as e:
            print(f"[MapHeader] Map {self.map_id} load error: {e}")
            return False

    def _load_palettes(self, rom: bytes):
        self.palettes = []
        off1 = self.p_pal1 & 0x01FFFFFF
        off2 = self.p_pal2 & 0x01FFFFFF
        
        pal1_raw = b''
        pal2_raw = b''
        
        if off1 and off1 < len(rom):
            pal1_raw = decompress_auto(rom, off1)
        if off2 and off2 < len(rom):
            pal2_raw = decompress_auto(rom, off2)
            
        merged = []
        for i in range(15):
            chunk1 = pal1_raw[i*32 : i*32+32] if i*32+32 <= len(pal1_raw) else b'\x00'*32
            chunk2 = pal2_raw[i*32 : i*32+32] if i*32+32 <= len(pal2_raw) else b'\x00'*32
            
            if len(set(chunk1)) <= 2:
                merged.append(chunk2)
            else:
                merged.append(chunk1)
                
        for chunk in merged:
            self.palettes.append(GBAPalette(chunk))
            
        while len(self.palettes) < 16:
            self.palettes.append(GBAPalette(b'\x00' * 32))

    def _load_tileset(self, rom: bytes):
        """
        Carga el tileset y los bloques desde p_gfx.
        Arquitectura FoMT: p_gfx contiene tiles (primeros 16384 bytes) + tabla de bloques (resto).
        Luego pre-renderiza todas las imágenes de bloque (16x16) siguiendo la arquitectura
        de blue-spider (BlocksData.load), para poder usarlas directamente en render_map.
        """
        self.tiles = []
        self.blocks_data = b''
        self.block_images: list = []  # Lista de PIL Image 16x16, una por bloque
        off = self.p_gfx & 0x01FFFFFF

        if off and off < len(rom) and rom[off] in (0x10, 0x70):
            raw_gfx = decompress_auto(rom, off)

            raw_tiles = raw_gfx[:16384]
            self.blocks_data = raw_gfx[16384:]

            # FoMT 0x70 (HuffLZ) ya incluye el filtro delta internamente.
            # Para LZ77 (0x10) aplicamos delta manual.
            if rom[off] != 0x70:
                raw_tiles = apply_delta_4bpp(raw_tiles)

            n_tiles = len(raw_tiles) // GBATile.BYTES
            for i in range(n_tiles):
                self.tiles.append(GBATile(raw_tiles[i*GBATile.BYTES : (i+1)*GBATile.BYTES]))

        # Pre-renderizar bloques siguiendo la arquitectura de blue-spider: BlocksData.load()
        # Cada bloque = 16 bytes: 8 bytes layer1 (4 sub-tiles × 2 bytes) + 8 bytes layer2
        self._build_block_images()

    def _build_block_images(self):
        """
        Pre-renderiza TODOS los bloques del mapa como imágenes PIL de 16x16.
        Equivale exactamente a blue-spider's BlocksData.load().
        El resultado queda en self.block_images[block_idx].
        """
        self.block_images = []
        if not self.blocks_data or not self.tiles or not self.palettes:
            return

        TRANSPARENT = Image.new('RGBA', (8, 8), (0, 0, 0, 0))
        BASE_IMG    = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
        # Posiciones de los 4 sub-tiles dentro del bloque de 16x16
        POSITIONS = [(0, 0), (8, 0), (0, 8), (8, 8)]

        n_blocks = len(self.blocks_data) // 16
        for b in range(n_blocks):
            block_img = BASE_IMG.copy()

            # Layer 1 (ground/floor) — bytes 0-7
            for j in range(4):
                entry = struct.unpack_from('<H', self.blocks_data, b * 16 + j * 2)[0]
                t_idx  = entry & 0x3FF
                h_flip = bool((entry >> 10) & 1)
                v_flip = bool((entry >> 11) & 1)
                p_idx  = (entry >> 12) & 0xF

                if t_idx == 0 or t_idx >= len(self.tiles):
                    part = TRANSPARENT
                elif p_idx < len(self.palettes):
                    part = self.tiles[t_idx].render(self.palettes[p_idx], h_flip, v_flip)
                else:
                    part = TRANSPARENT

                px, py = POSITIONS[j]
                block_img.paste(part, (px, py))  # Layer 1: opaco sobre fondo negro

            # Layer 2 (roofs/overlay) — bytes 8-15, con transparencia del color 0
            for j in range(4):
                entry = struct.unpack_from('<H', self.blocks_data, b * 16 + 8 + j * 2)[0]
                t_idx  = entry & 0x3FF
                h_flip = bool((entry >> 10) & 1)
                v_flip = bool((entry >> 11) & 1)
                p_idx  = (entry >> 12) & 0xF

                if t_idx == 0 or t_idx >= len(self.tiles):
                    continue  # Transparent: skip
                if p_idx >= len(self.palettes):
                    continue

                part = self.tiles[t_idx].render(self.palettes[p_idx], h_flip, v_flip)
                px, py = POSITIONS[j]
                # Pegar con máscara de alpha (color 0 de la paleta = transparente)
                block_img.paste(part, (px, py), part)

            self.block_images.append(block_img)

    def _load_tilemap(self, rom: bytes):
        off3 = self.p_bg3 & 0x01FFFFFF
        if off3 and off3 < len(rom):
            self.tilemap_bg3 = decompress_auto(rom, off3)
            
        off2 = self.p_bg2 & 0x01FFFFFF
        if off2 and off2 < len(rom):
            self.tilemap_bg2 = decompress_auto(rom, off2)
            
        off1 = self.p_bg1 & 0x01FFFFFF
        if off1 and off1 < len(rom):
            self.tilemap_bg1 = decompress_auto(rom, off1)

    def _load_objects(self, rom: bytes):
        self.warps = []
        self.scripts = []
        # TODO: Reverse engineer Ptr 6 and Ptr 7 lists.
        # For now, we clear the list so the UI doesn't crash trying to read garbage.

    def add_warp(self, x, y, target_map, tx, ty, face=0) -> Warp:
        return Warp(b'\x00'*8, 0)

    def remove_warp(self, warp_id: int):
        pass

    def save_warps_to_rom(self, project) -> bool:
        return False

    def save_layout_to_rom(self, project) -> bool:
        return False

    def render_map(self) -> Optional[Image.Image]:
        """
        Renderiza el mapa completo.
        BG1 (p_bg1) es la capa de suelo/base.
        BG2 (p_bg2) es la capa superior (árboles, techos, superposiciones).
        Cada celda de 2 bytes es un índice de bloque 16x16.
        """
        if not self._loaded or not self.block_images or not self.tilemap_bg1:
            return None

        w = self.width
        h = self.height
        img = Image.new('RGBA', (w * 16, h * 16), (0, 0, 30, 255))  # Fondo azul oscuro

        # Dibujar BG1 (Base)
        for row in range(h):
            for col in range(w):
                raw_idx = (row * w + col) * 2
                if raw_idx + 2 > len(self.tilemap_bg1):
                    continue
                block_val = struct.unpack_from('<H', self.tilemap_bg1, raw_idx)[0]
                block_idx = block_val & 0x3FF

                if block_idx < len(self.block_images) and block_idx != 0:
                    img.paste(self.block_images[block_idx], (col * 16, row * 16), self.block_images[block_idx])

        # Dibujar BG2 (Superposiciones / Techos) encima
        if self.tilemap_bg2:
            for row in range(h):
                for col in range(w):
                    raw_idx = (row * w + col) * 2
                    if raw_idx + 2 > len(self.tilemap_bg2):
                        continue
                    block_val = struct.unpack_from('<H', self.tilemap_bg2, raw_idx)[0]
                    block_idx = block_val & 0x3FF

                    if block_idx < len(self.block_images) and block_idx != 0:
                        img.paste(self.block_images[block_idx], (col * 16, row * 16), self.block_images[block_idx])

        return img


# ═══════════════════════════════════════════════════════════════════
#  PARSER DE MAPAS (get_map_headers de BlueSpider)
# ═══════════════════════════════════════════════════════════════════
class MapParser:
    """
    Extrae la lista de mapas desde la ROM.
    Implementa el algoritmo get_map_headers de BlueSpider.
    """
    # Offsets verificados de la tabla maestra USA (@USATH confirmado)
    KNOWN_OFFSETS_USA   = [0x105EDC]
    KNOWN_OFFSETS_EUR   = [0x127048, 0x117A00, 0x110200]
    KNOWN_OFFSETS_MFOMT = [0x0E5DB0, 0x10FF14, 0x110200]

    LITERAL_POOLS_MAP_TABLE = [0x0A46A8]

    STRIDE = MapHeader.STRIDE

    def __init__(self, project):
        self.project = project
        self.maps: List[MapHeader] = []
        self._table_offset: Optional[int] = None
        self._literal_pool_addr: Optional[int] = None

    def scan_maps(self):
        self.maps = []
        rom = self.project.base_rom_data
        if not rom:
            return

        self._table_offset = self._find_table(rom)
        if not self._table_offset:
            print("MapParser: No se encontró la tabla de mapas.")
            return

        i = 0
        while True:
            off = self._table_offset + i * self.STRIDE
            if off + self.STRIDE > len(rom):
                break
            chunk = rom[off:off+self.STRIDE]
            
            # Validación heurística estricta para evitar leer basura
            unpacked = struct.unpack('<8I2HI', chunk)
            valid_ptrs = sum(1 for p in unpacked[:6] if 0x08000000 <= p < 0x09FFFFFF)
            w, h = unpacked[8], unpacked[9]
            
            if valid_ptrs < 3 or not (1 <= w <= 256) or not (1 <= h <= 256):
                break
                
            m = MapHeader(i, off, chunk)
            
            # Nombre de SuperLibrary
            if hasattr(self.project, 'super_lib'):
                name_hint = self.project.super_lib.get_map_name_hint(m.map_id)
                if "Map " in name_hint and m.map_id in self.project.super_lib.map_map.values():
                    for name, mid in self.project.super_lib.map_map.items():
                        if mid == m.map_id:
                            name_hint = f"[{mid:03d}] {name}"
                            break
            
            self.maps.append(m)
            i += 1

        print(f"MapParser: Cargados {len(self.maps)} mapas exactos desde 0x{self._table_offset:X}")

    def _find_table(self, rom: bytes) -> Optional[int]:
        """Busca la tabla maestra dinámicamente mediante el Literal Pool (reapuntable)."""
        self._literal_pool_addr = None
        # Firma de la función que calcula: Address = Base + (MapID * 40)
        signature = bytes.fromhex('011C88004018C000014940187047')
        idx = rom.find(signature)
        if idx != -1:
            # ldr r1, [pc, #4] está a idx + 8
            # Y el literal pool está en (idx + 8 + 4) + 4 = idx + 16 (con PC aligned)
            pc_val = (idx + 8 + 4) & ~3
            pool_addr = pc_val + 4
            
            if pool_addr + 4 <= len(rom):
                p = struct.unpack_from('<I', rom, pool_addr)[0]
                if 0x08000000 <= p < 0x09FFFFFF:
                    off = p & 0x01FFFFFF
                    self._literal_pool_addr = pool_addr
                    print(f"Map Discovery: Offset detectado por Literal Pool en 0x{off:X} (Literal en 0x{pool_addr:X})")
                    return off

        # Fallback a los offsets conocidos si falló la búsqueda de la firma
        all_candidates = (self.KNOWN_OFFSETS_USA +
                          self.KNOWN_OFFSETS_EUR +
                          self.KNOWN_OFFSETS_MFOMT)
        for c in all_candidates:
            off = c & 0x01FFFFFF
            if off + 48 >= len(rom):
                continue
            p = struct.unpack_from('<I', rom, off)[0]
            if 0x08000000 <= p < 0x09FFFFFF:
                lo = p & 0x01FFFFFF
                if lo < len(rom) and rom[lo] in (0x10, 0x70, 0x00):
                    print(f"Map Discovery: Offset conocido 0x{off:X}")
                    return off

        print("Map Discovery: Falló la búsqueda dinámica. Escaneo profundo...")
        best, best_n = None, 0
        for i in range(0x020000, len(rom)-100, 4):
            n = self._count_valid(rom, i)
            if n > best_n:
                best_n = n; best = i
                if best_n > 60:
                    break
        if best and best_n >= 20:
            print(f"Map Discovery: Mesa en 0x{best:X} ({best_n} mapas)")
            return best
        return None

    def _count_valid(self, rom: bytes, start: int) -> int:
        count = 0
        for j in range(300):
            off = start + j * self.STRIDE
            if off + self.STRIDE > len(rom):
                break
            chunk = rom[off:off+self.STRIDE]
            unpacked = struct.unpack('<8I2HI', chunk)
            w, h = unpacked[8], unpacked[9]
            
            valid_ptrs = sum(1 for p in unpacked[:6] if 0x08000000 <= p < 0x09FFFFFF)
            if valid_ptrs >= 3 and 1 <= w <= 256 and 1 <= h <= 256:
                count += 1
            else:
                if count > 10:
                    break
                break
        return count

    def get_map_by_id(self, map_id: int) -> Optional[MapHeader]:
        for m in self.maps:
            if m.map_id == map_id:
                return m
        return None

    def load_map_data(self, map_header: MapHeader) -> bool:
        """Carga los assets del mapa desde la ROM."""
        return map_header.load_data(self.project.base_rom_data)

    def find_free_space(self, size: int, start_offset: int = 0x800000) -> int:
        search_bytes = b'\xFF' * size
        idx = self.project.base_rom_data.find(search_bytes, start_offset)
        if idx != -1:
            if idx % 4 != 0:
                idx += 4 - (idx % 4)
            return idx
        return -1

    def create_new_map(self, width: int, height: int) -> int:
        """
        Crea un nuevo mapa repunteando toda la tabla maestra.
        Devuelve el ID del nuevo mapa creado.
        """
        if self._table_offset is None or self._literal_pool_addr is None:
            raise Exception("No se encontró la tabla de mapas o el Literal Pool no está disponible para repuntear.")
            
        rom = self.project.base_rom_data
        num_maps = len(self.maps)
        
        # Tamaño de la tabla actual + 1 nueva entrada
        old_table_size = num_maps * self.STRIDE
        new_table_size = old_table_size + self.STRIDE
        
        # 1. Buscar espacio libre para la nueva tabla
        new_table_offset = self.find_free_space(new_table_size)
        if new_table_offset == -1:
            new_table_offset = len(rom)
            if new_table_offset % 4 != 0:
                new_table_offset += 4 - (new_table_offset % 4)
                
        # 2. Copiar la tabla vieja al nuevo espacio
        old_table_data = rom[self._table_offset : self._table_offset + old_table_size]
        self.project.overwrite_rom_directly(new_table_offset, old_table_data)
        
        # 3. Crear la nueva entrada de mapa (vacía/referencias a mapa 0 para evitar crash)
        new_map_id = num_maps
        base_map = self.maps[0] # Clonar assets básicos del mapa 0
        new_entry = struct.pack('<8I2HI',
            base_map.p_gfx,
            base_map.p_pal1,
            base_map.p_pal2,
            0, # bg3
            0, # bg2
            0, # bg1
            0, # obj1
            0, # obj2
            width,
            height,
            0  # attributes
        )
        self.project.overwrite_rom_directly(new_table_offset + old_table_size, new_entry)
        
        # 4. Actualizar el Literal Pool
        new_table_ptr = new_table_offset | 0x08000000
        ptr_data = struct.pack('<I', new_table_ptr)
        
        for pool_addr in self.LITERAL_POOLS_MAP_TABLE:
            self.project.overwrite_rom_directly(pool_addr, ptr_data)
            
        # Optional: still update the one found dynamically if it wasn't in the list
        if self._literal_pool_addr and self._literal_pool_addr not in self.LITERAL_POOLS_MAP_TABLE:
            self.project.overwrite_rom_directly(self._literal_pool_addr, ptr_data)
        
        # Actualizar estado interno
        self._table_offset = new_table_offset
        print(f"Tabla de mapas repunteada a 0x{new_table_offset:X}. Nuevo mapa ID: {new_map_id}")
        
        return new_map_id

    def save_map(self, map_index: int, renderer) -> bool:
        import struct

        mh = self.maps[map_index]
        
        # 1. Empaquetar tilemaps (16-bit array -> bytes)
        bg3_raw = struct.pack(f'<{len(renderer.tilemap_bg3)}H', *renderer.tilemap_bg3)
        bg2_raw = struct.pack(f'<{len(renderer.tilemap_bg2)}H', *renderer.tilemap_bg2)
        bg1_raw = struct.pack(f'<{len(renderer.tilemap_bg1)}H', *renderer.tilemap_bg1)
        
        # 2. Comprimir con el algoritmo nativo de FoMT (Popuri RLE - 0x70)
        bg3_comp = compress_popuri(bg3_raw)
        bg2_comp = compress_popuri(bg2_raw)
        bg1_comp = compress_popuri(bg1_raw)
        
        # 3. Inyectar tilemaps al final de la ROM
        total_size = len(bg3_comp) + len(bg2_comp) + len(bg1_comp)
        
        # Expandir la ROM si no hay espacio
        rom_len = len(self.project.base_rom_data)
        free_space = self.find_free_space(total_size)
        
        if free_space == -1:
            free_space = rom_len
            # Alinear a 4 bytes
            if free_space % 4 != 0:
                free_space += 4 - (free_space % 4)
                
        # 5. Escribir datos a través de overwrite_rom_directly para asegurar que persista en el archivo
        offset = free_space
        
        new_bg3_ptr = offset | 0x08000000
        self.project.overwrite_rom_directly(offset, bg3_comp)
        offset += len(bg3_comp)
        
        new_bg2_ptr = offset | 0x08000000
        self.project.overwrite_rom_directly(offset, bg2_comp)
        offset += len(bg2_comp)
        
        new_bg1_ptr = offset | 0x08000000
        self.project.overwrite_rom_directly(offset, bg1_comp)
        offset += len(bg1_comp)
        
        # 6. Guardar Collision Map
        obj2_off = mh.p_obj2 & 0x01FFFFFF
        if obj2_off > 0 and renderer.collision_map and len(renderer.collision_map) == mh.width * mh.height:
            self.project.overwrite_rom_directly(obj2_off, bytes(renderer.collision_map))
            
        # 7. Actualizar Map Header
        if self._table_offset is None:
            self._table_offset = 0x105EDC
        header_off = self._table_offset + (map_index * 40)
        
        # Ptr 3, 4, 5 (bg3, bg2, bg1)
        pointers_data = struct.pack('<3I', new_bg3_ptr, new_bg2_ptr, new_bg1_ptr)
        self.project.overwrite_rom_directly(header_off + 12, pointers_data)
        
        mh.p_bg3 = new_bg3_ptr
        mh.p_bg2 = new_bg2_ptr
        mh.p_bg1 = new_bg1_ptr
        
        print(f"Mapa {map_index} guardado en {hex(free_space)}. Tamaño: {total_size} bytes.")
        return True

    def export_map_to_tiled(self, map_header: MapHeader, out_dir: str):
        """Exporta un mapa al formato .tmx de Tiled."""
        import os
        from PIL import Image
        import struct
        
        os.makedirs(out_dir, exist_ok=True)
        
        if not map_header._loaded:
            self.load_map_data(map_header)
            
        # 1. Export Tileset PNG
        tiles = map_header.tiles
        palettes = map_header.palettes
        img_w = 1024 * 8
        img_h = 16 * 8 # 16 palettes

        img = Image.new('RGBA', (img_w, img_h), color=(0,0,0,0))
        for p_idx in range(16):
            if p_idx < len(palettes):
                pal = palettes[p_idx]
                for t_idx in range(1024):
                    if t_idx < len(tiles):
                        tile = tiles[t_idx]
                        tile_img = tile.render(pal)
                        img.paste(tile_img, (t_idx * 8, p_idx * 8))

        img.save(os.path.join(out_dir, 'tileset.png'))

        # 2. Generate TMX Map
        blocks_data = map_header.blocks_data
        bg3_decomp = map_header.tilemap_bg3
        w, h = map_header.width, map_header.height

        tiled_w = w * 2
        tiled_h = h * 2

        def get_tiled_gid(raw_val):
            if raw_val == 0: return 0
            t_idx = raw_val & 0x3FF
            h_flip = (raw_val >> 10) & 1
            v_flip = (raw_val >> 11) & 1
            p_idx = (raw_val >> 12) & 0xF
            
            gid = (p_idx * 1024) + t_idx + 1
            if h_flip: gid |= 0x80000000
            if v_flip: gid |= 0x40000000
            return gid

        l1_data = []
        l2_data = []

        for ty in range(tiled_h):
            for tx in range(tiled_w):
                bx = tx // 2
                by = ty // 2
                b_idx = by * w + bx
                
                if bg3_decomp and b_idx * 2 + 2 <= len(bg3_decomp):
                    block_id = struct.unpack_from('<H', bg3_decomp, b_idx * 2)[0] & 0x3FF
                    if block_id < 1024:
                        l1_raw = struct.unpack_from('<4H', blocks_data, block_id * 16)
                        l2_raw = struct.unpack_from('<4H', blocks_data, block_id * 16 + 8)
                        
                        sub_x = tx % 2
                        sub_y = ty % 2
                        sub_idx = sub_y * 2 + sub_x
                        
                        l1_data.append(str(get_tiled_gid(l1_raw[sub_idx])))
                        l2_data.append(str(get_tiled_gid(l2_raw[sub_idx])))
                    else:
                        l1_data.append('0')
                        l2_data.append('0')
                else:
                    l1_data.append('0')
                    l2_data.append('0')

        tmx_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<map version="1.10" tiledversion="1.10.2" orientation="orthogonal" renderorder="right-down" width="{tiled_w}" height="{tiled_h}" tilewidth="8" tileheight="8" infinite="0" nextlayerid="3" nextobjectid="1">
 <tileset firstgid="1" name="{map_header.get_name().replace(' ', '_')}_tileset" tilewidth="8" tileheight="8" tilecount="16384" columns="1024">
  <image source="tileset.png" width="8192" height="128"/>
 </tileset>
 <layer id="1" name="Capa 1 (Suelo)" width="{tiled_w}" height="{tiled_h}">
  <data encoding="csv">
{','.join(l1_data)}
  </data>
 </layer>
 <layer id="2" name="Capa 2 (Techos)" width="{tiled_w}" height="{tiled_h}">
  <data encoding="csv">
{','.join(l2_data)}
  </data>
 </layer>
</map>'''

        with open(os.path.join(out_dir, f'map_{map_header.map_id}.tmx'), 'w') as f:
            f.write(tmx_content)
        
        return True


# ═══════════════════════════════════════════════════════════════════
#  SPRITE ENGINE (extract_sprite_frame.pyd — FOMTSpriteData)
# ═══════════════════════════════════════════════════════════════════
# Los GBA OAM usan:
#  Attr0: bits 8-9 = Shape (0=square, 1=wide, 2=tall)
#  Attr1: bits 14-15 = Size
#  Dimensiones:
OAM_DIMS = {
    (0,0):(8,8),   (0,1):(16,16), (0,2):(32,32), (0,3):(64,64),
    (1,0):(16,8),  (1,1):(32,8),  (1,2):(32,16), (1,3):(64,32),
    (2,0):(8,16),  (2,1):(8,32),  (2,2):(16,32), (2,3):(32,64),
}

class OAMEntry:
    """Una entrada OAM de 6 bytes (3 atributos × 2 bytes)."""
    def __init__(self, data: bytes):
        a0 = struct.unpack_from('<H', data, 0)[0]
        a1 = struct.unpack_from('<H', data, 2)[0]
        a2 = struct.unpack_from('<H', data, 4)[0]
        self.y      = a0 & 0xFF
        self.shape  = (a0 >> 14) & 3
        self.x      = a1 & 0x1FF
        self.h_flip = bool((a1 >> 12) & 1)
        self.v_flip = bool((a1 >> 13) & 1)
        self.size   = (a1 >> 14) & 3
        self.tile   = a2 & 0x3FF
        self.pal    = (a2 >> 12) & 0xF
        self.w, self.h = OAM_DIMS.get((self.shape, self.size), (8, 8))
