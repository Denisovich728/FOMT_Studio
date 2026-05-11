# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.0.0)
# "The Imposibility Update"
# Desarrollado por: Denisovich728
# ============================================================
import os

# Importamos las herramientas de bajo nivel que ya existían
from Nucleos_de_Procesamiento.Nucleo_de_Datos.Utilidades.compression import decompress_lz10
from Nucleos_de_Procesamiento.Nucleo_de_Datos.Utilidades.popuri_unpacker import popuri_unpack

def descomprimir_rom(proyecto, offset):
    """
    Subrutina Maestra de Descompresión (LZ77 BIOS y Popuri).
    Ubicación Central: Nucleo_de_Imagenes/descompresor.py
    """
    # Usamos el directorio de caché del proyecto
    cache_dir = os.path.join(proyecto.project_dir, ".cache")
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)
        
    cache_path = os.path.join(cache_dir, f"decomp_0x{offset:06X}.bin")
    
    # 1. Intentar cargar desde el Caché en Disco
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'rb') as f:
                return f.read()
        except: pass
        
    # 2. Si no hay caché, leer desde la ROM virtual del proyecto
    header = proyecto.read_rom(offset, 1)[0]
    data = None
    
    # Heurística de detección de formato
    if header == 0x10:
        # BIOS LZ10 Estándar (GBA)
        raw_data = proyecto.read_rom(offset, 0x20000) 
        data = decompress_lz10(raw_data)
    elif header == 0x70:
        # Popuri Engine (Compresión personalizada de FoMT)
        raw_data = proyecto.read_rom(offset, 0x20000)
        data, _, _ = popuri_unpack(raw_data)
    else:
        # No es un formato comprimido conocido o el offset es incorrecto
        return None
        
    # 3. Guardar en Caché para optimizar futuros accesos
    if data:
        try:
            with open(cache_path, 'wb') as f:
                f.write(data)
        except: pass
        
    return data
