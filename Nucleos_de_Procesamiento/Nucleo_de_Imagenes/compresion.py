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
