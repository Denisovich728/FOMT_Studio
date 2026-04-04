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

# Alias para compatibilidad con código legado (SuperLibrary)
decompress_lz77 = decompress_lz10

# Alias para compatibilidad con código legado (SuperLibrary)
decompress_lz77 = decompress_lz10
