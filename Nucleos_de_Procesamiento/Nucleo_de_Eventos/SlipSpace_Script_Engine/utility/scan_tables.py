# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.6.5)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
import sys
import struct

def scan_fomt_tables(rom_data: bytes):
    print("SlipSpace_Engine Table Scanner - Harvest Moon: FoMT/MFoMT")
    # GBA ROM memory starts mapped at 0x08000000
    # Items and Character strings usually reside in pointer tables.
    
    # Let's locate the main Script event table first to anchor version
    is_fomt = b"HARVESTMOGBA" in rom_data[0xA0:0xAC]
    is_mfomt = b"HM MFOM USA\0" in rom_data[0xA0:0xAC]
    
    if is_fomt:
        print("Detected: Harvest Moon: Friends of Mineral Town (USA)")
    elif is_mfomt:
        print("Detected: More Friends of Mineral Town (USA)")
    else:
        print("Could not identify ROM header as US FoMT/MFoMT.")
        
    categories = {
        "Personajes": [b"Popuri\0", b"Karen\0", b"Mary\0", b"Elli\0", b"Ann\0", b"Rick\0", b"Cliff\0"],
        "Duendes": [b"Chef\0", b"Nappy\0", b"Hoggy\0", b"Timid\0", b"Aqua\0", b"Bold\0", b"Staid\0"],
        "Items": [b"Turnip\0", b"Potato\0", b"Cucumber\0", b"Strawberry\0", b"Cabbage\0", b"Tomato\0"]
    }
    
    for cat_name, search_terms in categories.items():
        locations = {}
        for term in search_terms:
            idx = rom_data.find(term)
            if idx != -1:
                locations[term] = idx
                
        if not locations:
            continue
            
        table_candidates = []
        for t, l in locations.items():
            ptr = l | 0x08000000
            ptr_bytes = struct.pack('<I', ptr)
            ptr_loc = rom_data.find(ptr_bytes)
            if ptr_loc != -1:
                table_candidates.append(ptr_loc)
                
        if not table_candidates:
            continue

        table_candidates.sort()
        
        # Determine the stride (size of each entity struct)
        if len(table_candidates) >= 2:
            diffs = []
            for i in range(len(table_candidates)-1):
                diff = table_candidates[i+1] - table_candidates[i]
                if diff > 0 and diff % 4 == 0:
                    diffs.append(diff)
            stride = min(diffs) if diffs else 4
        else:
            stride = 4

        def is_valid_string_ptr(p: int) -> bool:
            if not (0x08000000 <= p < 0x09000000):
                return False
            rom_off = p & 0x01FFFFFF
            if rom_off >= len(rom_data): 
                return False
            # Check if first few characters look like ascii/printable
            valid_chars = 0
            curr = rom_off
            while curr < len(rom_data) and curr < rom_off + 5:
                b = rom_data[curr]
                if b == 0: break
                if 0x20 <= b <= 0x7E: valid_chars += 1
                curr += 1
            return valid_chars > 0

        allowance = 65 # Tolerancia masiva a ítems vacíos (Null/Pad)
        
        ranges = []
        for anchor in table_candidates:
            start_table = anchor
            misses_back = 0
            while start_table >= stride:
                test_ptr = struct.unpack_from('<I', rom_data, start_table - stride)[0]
                if is_valid_string_ptr(test_ptr):
                    start_table -= stride
                    misses_back = 0
                else:
                    if misses_back < allowance:
                        misses_back += 1
                        start_table -= stride
                    else:
                        start_table += (allowance * stride)
                        break
                    
            # Move forwards
            end_table = anchor
            misses_fwd = 0
            
            while end_table + stride <= len(rom_data):
                test_ptr = struct.unpack_from('<I', rom_data, end_table + stride)[0]
                if is_valid_string_ptr(test_ptr):
                    end_table += stride
                    misses_fwd = 0
                else:
                    if misses_fwd < allowance:
                        misses_fwd += 1
                        end_table += stride
                    else:
                        end_table -= (allowance * stride)
                        break
                        
            ranges.append((start_table, end_table))
            
        # Merge overlapping/adjacent ranges
        ranges.sort()
        merged_ranges = []
        for r in ranges:
            if not merged_ranges:
                merged_ranges.append(r)
            else:
                last_r = merged_ranges[-1]
                # If they overlap or are perfectly adjacent, merge them
                if r[0] <= last_r[1] + stride:
                    merged_ranges[-1] = (last_r[0], max(last_r[1], r[1]))
                else:
                    merged_ranges.append(r)
                    
        for block_idx, (start_table, end_table) in enumerate(merged_ranges):
            table_size = ((end_table - start_table) // stride) + 1
            
            print(f"=== REPORTE TABLA {cat_name} (Bloque {block_idx+1}) ===")
            print(f"Rastreo Heurístico Completado.")
            print(f"Dirección de memoria inicial: 0x{start_table:06X}")
            print(f"Dirección de memoria final:   0x{end_table:06X}")
            print(f"Cantidad de índices extraídos: {table_size}")
            print(f"----------------------------------------")
            
            for i in range(table_size):
                struct_start = start_table + i * stride
                ptr = struct.unpack_from('<I', rom_data, struct_start)[0]
                rom_off = ptr & 0x01FFFFFF
                
                # 1. Extract the name (Offset + 0)
                val = b""
                curr = rom_off
                while curr < len(rom_data) and rom_data[curr] != 0:
                    val += bytes([rom_data[curr]])
                    curr += 1
                    if len(val) > 20: 
                        val += b"..."
                        break
                        
                try:
                    str_val = val.decode('utf-8')
                except:
                    str_val = "<data>"
                    
                # 1.5 Extract the description (Offset + 12 in a 16-byte stride)
                desc_val = ""
                if stride >= 16:
                    desc_ptr_raw = struct.unpack_from('<I', rom_data, struct_start + 12)[0]
                    if is_valid_string_ptr(desc_ptr_raw):
                        desc_off = desc_ptr_raw & 0x01FFFFFF
                        d_val = b""
                        d_curr = desc_off
                        while d_curr < len(rom_data) and rom_data[d_curr] != 0:
                            d_val += bytes([rom_data[d_curr]])
                            d_curr += 1
                            if len(d_val) > 100: # Descriptions can be longer
                                d_val += b"..."
                                break
                        try:
                            # Replace newlines for clean printing
                            desc_val = d_val.decode('utf-8').replace('\n', ' | ') 
                        except:
                            desc_val = "<desc_data>"
                    
                # 2. Extract the raw structural data (Prices, Stamina, Affection offsets)
                raw_struct = rom_data[struct_start : struct_start + stride]
                hex_dump = " ".join(f"{b:02X}" for b in raw_struct)
                
                desc_print = f"\n  -> Desc: {desc_val}" if desc_val else ""
                print(f"ID [{i:03d}] Nombre: {str_val:<15} | Raw Struct: [{hex_dump}]{desc_print}")
                
            print(f"\n")
            
        if cat_name == "Items":
            print(f"=== REPORTE TABLA Items (Bloque Alta Entropia Herramientas_Clave) ===")
            print(f"Activando Rastreador de Calor: Buscando punteros de variables dispersas desde 0x0F6CD8...")
            
            curr_loc = 0x0F6CD8
            end_limit = 0x0F8000  # Límite heurístico para la tabla de ítems extendida
            tool_idx = 171
            
            # Rastreador de Entropía: En lugar de forzar un stride, buscamos densidades de punteros que apunten a texto válido
            while curr_loc < end_limit:
                ptr_raw = struct.unpack_from('<I', rom_data, curr_loc)[0]
                
                # Check 1: ¿Es un puntero válido a la zona ROM 0x08?
                if is_valid_string_ptr(ptr_raw):
                    rom_off = ptr_raw & 0x01FFFFFF
                    
                    # Decodificamos el nombre hipotético
                    val = b""
                    c = rom_off
                    while c < len(rom_data) and rom_data[c] != 0:
                        val += bytes([rom_data[c]])
                        c += 1
                        if len(val) > 20: 
                            val += b"..."
                            break
                            
                    try:
                        str_val = val.decode('utf-8')
                        # Check 2: Entropía de Texto (Descartar basuras como "!#$" o strings vacíos)
                        if len(str_val.strip()) > 1 and any(c.isalpha() for c in str_val):
                            
                            # Check 3: Descubrimiento Dinámico de Stride
                            # Averiguamos de qué tamaño es el struct explorando dónde está el SIGUIENTE puntero válido
                            next_valid_offset = curr_loc + 4
                            detected_stride = 12 # Default fallback
                            
                            for lookahead in [12, 16, 20]:
                                if curr_loc + lookahead < end_limit:
                                    test_next = struct.unpack_from('<I', rom_data, curr_loc + lookahead)[0]
                                    if is_valid_string_ptr(test_next):
                                        detected_stride = lookahead
                                        break
                                        
                            raw_struct = rom_data[curr_loc : curr_loc + detected_stride]
                            hex_dump = " ".join(f"{b:02X}" for b in raw_struct)
                            
                            print(f"ID [{tool_idx:03d}] Nombre: {str_val:<15} | Raw Struct: [{hex_dump}] ({detected_stride} bytes)")
                            
                            tool_idx += 1
                            curr_loc += detected_stride
                            continue
                    except:
                        pass
                
                # Si no es un bloque válido, o hubo error, avanzamos en minúsculos pasos buscando el siguiente ancla
                curr_loc += 4
                    
            print(f"\nExtracción Heurística por Calor Finalizada.\n")
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m SlipSpace_Engine scan-tables <rom.gba>")
        sys.exit(1)
        
    try:
        with open(sys.argv[1], 'rb') as f:
            data = f.read()
        scan_fomt_tables(data)
    except Exception as e:
        print(f"Error: {e}")
