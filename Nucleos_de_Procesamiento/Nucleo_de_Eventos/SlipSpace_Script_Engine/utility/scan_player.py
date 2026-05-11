# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.1.0)
# "The Imposibility Update"
# Desarrollado por: Denisovich728
# ============================================================
import struct

def scan_player_stats(rom_data: bytes) -> str:
    """
    Busca la tabla de inicialización del jugador en la ROM,
    utilizando las direcciones RAM (Cheats) proporcionadas por el usuario.
    
    RAM Conocida:
    - Dinero: 0x02004090
    - Stamina: 0x02004205
    - Fatiga: 0x02004206
    """
    reporte = "=== REPORTE TABLA DE IDENTIFICACIÓN DEL JUGADOR ===\n"
    reporte += "Rastreando Bloque Base usando Punteros RAM (Little Endian) de Cheats...\n\n"
    
    # 1. Empacar las direcciones RAM en Little Endian para buscar instrucciones ASM
    # La CPU ARM (GBA) carga memoria empaquetada. Buscaremos las direcciones tal cual.
    targets_ram = {
        # --- Jugador ---
        "Dinero_Oro": struct.pack('<I', 0x02004090),
        "Stamina_Max": struct.pack('<I', 0x02004205),
        "Inventario_Bolsa": struct.pack('<I', 0x02004234),
        # --- Animales ---
        "Caballo_Afecto": struct.pack('<I', 0x02002618),
        "Perro_Afecto": struct.pack('<I', 0x02004272),
        "Gallinas_Start": struct.pack('<I', 0x02002A1E),
        "Ganado_Start": struct.pack('<I', 0x02002C12),
        # --- Casa/Almacenaje ---
        "Refrigerador": struct.pack('<I', 0x020025D8),
        "Estanteria": struct.pack('<I', 0x02002618),
        "Caja_Herramientas": struct.pack('<I', 0x02002958),
    }
    
    hallazgos = {}
    
    for label, byte_pattern in targets_ram.items():
        idx = rom_data.find(byte_pattern)
        ocurrencias = []
        while idx != -1:
            ocurrencias.append(idx)
            idx = rom_data.find(byte_pattern, idx + 4)
            
        hallazgos[label] = ocurrencias
        reporte += f"[{label}] (Puntero: {byte_pattern.hex().upper()}) -> Encontrado en {len(ocurrencias)} ubicaciones de la ROM.\n"
        
    reporte += "\nBuscando cruces de memoria (Aglomeraciones donde se inicien Stamina y Oro simultáneamente)...\n"
    
    # Evaluar cruces: Buscamos un bloque de código ROM donde se referencien al menos 2 punteros de estado muy cerca (ej. dentro de 512 bytes)
    cruces_encontrados = []
    oro_locs = hallazgos["Dinero_Oro"]
    stam_locs = hallazgos["Stamina"]
    
    for o_loc in oro_locs:
        for s_loc in stam_locs:
            dist = abs(o_loc - s_loc)
            if dist <= 512:
                # Este bloque de ROM parece ser la rutina de "New Game" general.
                # Extraemos la ventana de código:
                start_window = min(o_loc, s_loc) - 64
                end_window = max(o_loc, s_loc) + 128
                cruces_encontrados.append((start_window, end_window, dist))
                
    if not cruces_encontrados:
        reporte += "[-] No se encontraron inicializaciones simultáneas. Cada variable parece cargarse en rutinas aisladas.\n\n"
        reporte += "Mostrando las 3 direcciones primarias para inyección dinámica de Bot:\n"
        for label, locs in hallazgos.items():
            if locs:
                reporte += f" -> Rutina de {label} probablemente empieza en ROM: 0x{locs[0]:06X}\n"
    else:
        # Sort por la distancia más cercana
        cruces_encontrados.sort(key=lambda x: x[2])
        reporte += f"[+] ¡BINGO! Se localizaron {len(cruces_encontrados)} rutinas maestras de inicialización de partida.\n\n"
        
        for i, (w_start, w_end, dist) in enumerate(cruces_encontrados[:3]):
            reporte += f"--- Rutina Maestra #{i+1} (Inicio ROM: 0x{w_start:06X} | Rango: {w_end - w_start} bytes) ---\n"
            window = rom_data[w_start:w_end]
            
            for row in range(0, len(window), 16):
                chunk = window[row:row+16]
                hex_str = " ".join([f"{b:02X}" for b in chunk])
                ascii_str = "".join([chr(b) if 32 <= b <= 126 else "." for b in chunk])
                addr = w_start + row
                
                # Marcar los punteros exactos
                marker = ""
                for lbl, locs in hallazgos.items():
                    if any(addr <= loc < addr + 16 for loc in locs):
                        marker += f" <- [{lbl}]"
                        
                reporte += f"  0x{addr:06X}: {hex_str:<48} | {ascii_str}{marker}\n"
            reporte += "\n"
            
    return reporte