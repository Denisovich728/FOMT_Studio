import struct
import os

def find_map_table(rom_path):
    with open(rom_path, 'rb') as f:
        data = f.read()

    results = []
    # Escaneamos saltando de 4 en 4
    for i in range(0, len(data) - 48, 4):
        # Miramos si hay al menos 2 registros consecutivos con punteros lógicos válidos
        try:
            p1, _, _, _, _, _ = struct.unpack('<IIIIII', data[i:i+24])
            p2, _, _, _, _, _ = struct.unpack('<IIIIII', data[i+24:i+48])
        except: continue

        # ¿Son punteros válidos a ROM?
        if 0x08000000 <= p1 < 0x08800000 and 0x08000000 <= p2 < 0x08800000:
            o1 = p1 & 0x01FFFFFF
            o2 = p2 & 0x01FFFFFF
            
            # ¿Apunta a una cabecera de compresión conocida (LZ77 o Popuri)?
            if o1 < len(data) and o2 < len(data):
                if data[o1] in [0x10, 0x70] and data[o2] in [0x10, 0x70]:
                    # Contamos cuántos registros consecutivos hay
                    count = 0
                    while i + (count * 24) + 24 <= len(data):
                        px = struct.unpack('<I', data[i + count*24 : i + count*24 + 4])[0]
                        if not (0x08000000 <= px < 0x08800000): break
                        ox = px & 0x01FFFFFF
                        if ox >= len(data) or data[ox] not in [0x10, 0x70]: break
                        count += 1
                    
                    if count >= 3:
                        results.append((i, count))
    
    return results

if __name__ == "__main__":
    rom = "J:/Matriz De Datos Principal/Proyectos De Programacion/Proyecto De Descompilacion GBA/HM_MFOMT.gba"
    found = find_map_table(rom)
    for addr, count in found:
        print(f"Posible Tabla en 0x{addr:06X} (Registros: {count})")
