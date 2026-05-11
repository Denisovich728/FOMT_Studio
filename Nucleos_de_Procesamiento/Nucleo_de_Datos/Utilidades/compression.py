# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.3.4)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
import struct

def decompress_lz10(data):
    """
    Descompresor Estándar BIOS LZ77 0x10 para GBA.
    Implementación segura contra desbordamientos y bucles infinitos.
    """
    if len(data) < 4 or data[0] != 0x10:
        return None
        
    decomp_size = struct.unpack("<I", data[0:4])[0] >> 8
    if decomp_size == 0: return b""
    
    output = bytearray()
    read_offs = 4
    
    try:
        while len(output) < decomp_size:
            # Si nos quedamos sin datos de origen, abortar
            if read_offs >= len(data): break
            
            flag = data[read_offs]
            read_offs += 1
            
            for i in range(8):
                if len(output) >= decomp_size:
                    break
                
                if flag & (0x80 >> i):
                    # Comprimido (2 bytes)
                    if read_offs + 2 > len(data): break
                    info = struct.unpack(">H", data[read_offs:read_offs+2])[0]
                    read_offs += 2
                    
                    count = (info >> 12) + 3
                    disp = (info & 0x0FFF) + 1
                    
                    start = len(output) - disp
                    # Seguridad: No leer antes del inicio del buffer
                    if start < 0: 
                        # Algunos encoders asumen ceros antes del buffer 
                        # pero BIOS oficial suele fallar. Tratamos como ceros.
                        for _ in range(count):
                            if len(output) < decomp_size:
                                output.append(0)
                        continue

                    for j in range(count):
                        if len(output) < decomp_size:
                            output.append(output[start + j])
                else:
                    # No Comprimido (1 byte)
                    if read_offs >= len(data): break
                    output.append(data[read_offs])
                    read_offs += 1
                    
    except Exception:
        pass # Retornar lo que se haya descompresado hasta el error
                
    return bytes(output)

def is_lz77_block(data, offset=0):
    """
    Heurística reforzada de StanHash para evitar falsos positivos masivos.
    """
    if len(data) < offset + 5: return False
    if data[offset] != 0x10: return False
    
    # Tamaño (3 bytes)
    size = data[offset+1] | (data[offset+2] << 8) | (data[offset+3] << 16)
    
    # Filtros de tamaño lógicos para FoMT (Tilesets y Sprites)
    if size < 32 or size > 0x80000: # Max 512KB para assets individuales
        return False
        
    # HEURÍSTICA DE ORO: El primer byte de banderas (offset + 4)
    # Casi siempre el primer bloque de un asset GBA empieza con un literal (bit 7 = 0)
    # Si el primer bit es 1 (comprimido), es 99% probable que sea código o basura.
    first_flag = data[offset + 4]
    if (first_flag & 0x80):
        return False
        
        
    return True

def compress_popuri(data: bytes) -> bytes:
    """
    Compresor RLE (0x70) para el motor Popuri (FoMT).
    Este algoritmo comprime los triggers y layouts del mapa.
    """
    size = len(data)
    out = bytearray()
    out.append(0x70)
    
    # 3 bytes para el tamaño descomprimido (Little Endian)
    out.extend(struct.pack('<I', size)[:3])
    
    pos = 0
    while pos < size:
        # Buscar repeticiones (RLE match)
        match_len = 1
        while pos + match_len < size and data[pos] == data[pos + match_len] and match_len < 128:
            match_len += 1
            
        if match_len >= 3:
            # Comprimir repetición: byte de control (0x80 | (count-1)) seguido del byte
            out.append(0x80 | (match_len - 1))
            out.append(data[pos])
            pos += match_len
        else:
            # Literal run
            lit_len = 0
            while pos + lit_len < size and lit_len < 128:
                # Si encontramos un match de al menos 3 caracteres, rompemos el literal run
                if pos + lit_len + 2 < size and data[pos + lit_len] == data[pos + lit_len + 1] == data[pos + lit_len + 2]:
                    break
                lit_len += 1
                
            out.append(lit_len - 1)
            out.extend(data[pos : pos + lit_len])
            pos += lit_len
            
    # Pad a múltiplo de 4
    while len(out) % 4 != 0:
        out.append(0)
        
    return bytes(out)

# Alias para compatibilidad con código legado (SuperLibrary)
decompress_lz77 = decompress_lz10

# Alias para compatibilidad con código legado (SuperLibrary)
decompress_lz77 = decompress_lz10
