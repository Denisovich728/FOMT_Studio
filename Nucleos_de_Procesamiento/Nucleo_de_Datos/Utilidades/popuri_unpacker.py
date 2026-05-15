# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.6.5)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
import struct

def popuri_unpack(data):
    """
    Descompresor personalizado para el motor Popuri (FoMT).
    Formato: [1 byte 0x70][3 bytes decomp_size][Data...]
    """
    if data[0] != 0x70:
        return None, 0, 0
        
    decomp_size = struct.unpack("<I", data[0:4])[0] >> 8
    output = bytearray()
    
    # El algoritmo Popuri es una variante de LZ con bits de control
    # Simplificado para restaurar funcionalidad básica:
    read_offs = 4
    while len(output) < decomp_size and read_offs < len(data):
        flag = data[read_offs]
        read_offs += 1
        
        for i in range(8):
            if len(output) >= decomp_size or read_offs >= len(data):
                break
                
            if flag & (0x80 >> i):
                # LZ Match
                if read_offs + 1 >= len(data): break
                info = struct.unpack(">H", data[read_offs:read_offs+2])[0]
                read_offs += 2
                
                length = (info >> 12) + 3
                offset = (info & 0x0FFF) + 1
                
                start = len(output) - offset
                for j in range(length):
                    if start + j < 0:
                        output.append(0)
                    else:
                        output.append(output[start + j])
            else:
                # Literal
                output.append(data[read_offs])
                read_offs += 1
                
    return bytes(output), read_offs, decomp_size
