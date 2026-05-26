import sys
import struct
import json
import os
from typing import List, Dict

def find_all_riffs(rom_data: bytes) -> List[int]:
    """
    Escanea la ROM buscando la firma b'RIFF' seguida por la sub-firma b'SCR '.
    Devuelve una lista de offsets donde comienzan estos scripts.
    """
    print("Iniciando escaneo agresivo de RIFF/SCR...")
    script_offsets = []
    offset = 0
    rom_size = len(rom_data)
    
    # We can use bytes.find to quickly locate b'RIFF'
    while True:
        idx = rom_data.find(b'RIFF', offset)
        if idx == -1:
            break
            
        if idx + 12 <= rom_size:
            magic2 = rom_data[idx+8 : idx+12]
            if magic2 == b'SCR ':
                riff_len = struct.unpack('<I', rom_data[idx+4 : idx+8])[0]
                # Básico chequeo de cordura (por ejemplo, script maximo de 256KB y dentro de bounds)
                if riff_len < 0x40000 and idx + 8 + riff_len <= rom_size:
                    script_offsets.append(idx)
        
        offset = idx + 4
        
    print(f"Total de scripts RIFF encontrados: {len(script_offsets)}")
    return script_offsets

def find_pointer_chains(rom_data: bytes, script_offsets: List[int]) -> List[Dict]:
    """
    Busca referencias a los offsets de scripts extraídos.
    Retorna cadenas contiguas de punteros.
    """
    print("Mapeando punteros y agrupando en cadenas (chains)...")
    rom_size = len(rom_data)
    
    # 1. Crear un diccionario rápido de puntero a offset
    valid_pointers = {}
    for off in script_offsets:
        ptr = off | 0x08000000
        valid_pointers[ptr] = off
        
    # 2. Localizar todas las direcciones de memoria donde se almacenan los punteros
    pointer_locations = []
    
    # Escaneamos cada palabra de 32-bits alineada
    for i in range(0, rom_size - 3, 4):
        val = struct.unpack_from('<I', rom_data, i)[0]
        if val in valid_pointers:
            pointer_locations.append((i, val, valid_pointers[val]))
            
    print(f"Total de referencias a punteros encontradas: {len(pointer_locations)}")
    
    if not pointer_locations:
        return []
        
    # 3. Agrupar referencias adyacentes en "cadenas"
    # Una cadena son punteros a scripts almacenados secuencialmente cada 4 bytes.
    # Ordenamos por ubicación
    pointer_locations.sort(key=lambda x: x[0])
    
    chains = []
    current_chain = {
        "start": pointer_locations[0][0],
        "pointers": [{"loc": pointer_locations[0][0], "ptr": pointer_locations[0][1], "script_offset": pointer_locations[0][2]}]
    }
    
    for i in range(1, len(pointer_locations)):
        loc, ptr, off = pointer_locations[i]
        last_loc = current_chain["pointers"][-1]["loc"]
        
        # Si la distancia es exactamente 4 bytes, pertenecen a la misma tabla
        if loc == last_loc + 4:
            current_chain["pointers"].append({"loc": loc, "ptr": ptr, "script_offset": off})
        else:
            # Finaliza la cadena anterior
            current_chain["count"] = len(current_chain["pointers"])
            chains.append(current_chain)
            
            # Comienza una nueva
            current_chain = {
                "start": loc,
                "pointers": [{"loc": loc, "ptr": ptr, "script_offset": off}]
            }
            
    # Agregar la última cadena
    if current_chain["pointers"]:
        current_chain["count"] = len(current_chain["pointers"])
        chains.append(current_chain)
        
    print(f"Total de cadenas/tablas (chains) detectadas: {len(chains)}")
    return chains

def save_metadata(chains: List[Dict], rom_path: str):
    """
    Guarda los resultados del escaneo en un JSON de sesión.
    """
    base_name = os.path.basename(rom_path)
    session_file = f"scan_session_{base_name}.json"
    
    # Limpiamos los datos para que sean fáciles de leer en JSON
    output_data = {
        "rom_name": base_name,
        "tables": []
    }
    
    for c in chains:
        table_data = {
            "start": f"0x{c['start']:06X}",
            "count": c["count"],
            "entries": []
        }
        for p in c["pointers"]:
            table_data["entries"].append({
                "loc": f"0x{p['loc']:06X}",
                "script_ptr": f"0x{p['ptr']:08X}",
                "script_offset": f"0x{p['script_offset']:06X}"
            })
        output_data["tables"].append(table_data)
        
    try:
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=4)
        print(f"Metadata de sesión guardada exitosamente en: {session_file}")
    except Exception as e:
        print(f"Error al guardar metadata: {e}")

def run_aggressive_scan(rom_path: str):
    if not os.path.exists(rom_path):
        print(f"Error: No se encontro el archivo ROM: {rom_path}")
        return
        
    with open(rom_path, 'rb') as f:
        rom_data = f.read()
        
    script_offsets = find_all_riffs(rom_data)
    if not script_offsets:
        print("No se encontraron scripts RIFF/SCR en esta ROM.")
        return
        
    chains = find_pointer_chains(rom_data, script_offsets)
    
    if chains:
        save_metadata(chains, rom_path)
        
        # Opcional: imprimir las tablas más grandes (probablemente las listas principales de eventos)
        print("\\n--- Top 5 Tablas Mas Grandes ---")
        chains.sort(key=lambda x: x["count"], reverse=True)
        for i, c in enumerate(chains[:5]):
            print(f"Tabla {i+1}: Inicio en 0x{c['start']:06X} con {c['count']} scripts enlazados.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scan_aggressive_scripts.py <archivo.gba>")
        sys.exit(1)
        
    run_aggressive_scan(sys.argv[1])
