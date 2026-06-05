import os
import csv
import struct
import argparse
from typing import List, Dict, Any

from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.sprite_decoder import SpriteRenderer
from Nucleos_de_Procesamiento.Nucleo_de_Datos.Utilidades.rutas import get_data_path

def parse_offset(raw_str: str) -> int:
    """Convierte 'BC D7 64 00' (LE) o '5FA73C' (HEX) a offset entero."""
    raw_str = raw_str.strip()
    if not raw_str: return 0
    if ' ' in raw_str:
        try:
            byte_vals = [int(b, 16) for b in raw_str.split()]
            if len(byte_vals) == 4:
                return struct.unpack('<I', bytes(byte_vals))[0]
        except (ValueError, struct.error):
            pass
    try:
        return int(raw_str, 16)
    except ValueError:
        return 0

def load_sprite_data(mode: str) -> List[Dict[str, Any]]:
    """Carga y procesa el CSV de sprites."""
    sprites = []
    prefix = "MFomt_" if mode == "mfomt" else "Fomt_"
    csv_path = get_data_path(mode, f"{prefix}Sprite_data.csv")
    
    if not os.path.exists(csv_path):
        print(f"ERROR: {csv_path} no encontrado.")
        return sprites

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        for row in reader:
            if not row or len(row) < 2: continue
            
            name = row[0].strip()
            tile_off = parse_offset(row[1])
            pal_off = parse_offset(row[2] if len(row) > 2 else "")
            
            if tile_off <= 0: continue
            
            if ' ' in row[1]:
                category = "Animal"
            elif any(k in name.lower() for k in ["player", "map-"]):
                category = "Portrait"
            else:
                category = "Overworld"

            sprites.append({
                "name": name,
                "tile_offset": tile_off,
                "palette_offset": pal_off,
                "category": category,
            })

    # Calcular max_size
    sorted_by_off = sorted(sprites, key=lambda x: x["tile_offset"])
    for i in range(len(sorted_by_off)):
        curr = sorted_by_off[i]
        next_off = 0
        for j in range(i + 1, len(sorted_by_off)):
            if sorted_by_off[j]["tile_offset"] > curr["tile_offset"]:
                next_off = sorted_by_off[j]["tile_offset"]
                break
        
        if next_off > 0:
            curr["max_size"] = next_off - curr["tile_offset"]
        else:
            curr["max_size"] = 4096

    return sprites

def dump_all(rom_path: str, mode: str, output_dir: str):
    if not os.path.exists(rom_path):
        print(f"ROM no encontrada en {rom_path}")
        return

    with open(rom_path, 'rb') as f:
        rom_data = f.read()

    os.makedirs(output_dir, exist_ok=True)
    sprites = load_sprite_data(mode)
    
    if not sprites:
        return

    print(f"Iniciando volcado de {len(sprites)} sprites en '{output_dir}'...")

    for sp in sprites:
        safe_name = sp["name"].replace("/", "_").replace("\\", "_").replace(" ", "_")
        print(f"Procesando: {safe_name} (0x{sp['tile_offset']:X})")

        # Configurar tiles_wide para PNG y dimensiones para GIF
        tiles_wide = 4
        frame_width = 16
        frame_height = 24 # Base standard para overworld humanos (16x24)

        if sp["category"] == "Animal":
            tiles_wide = 8
            frame_width = 32
            frame_height = 32
        elif sp["category"] == "Portrait":
            tiles_wide = 4
            frame_width = 16
            frame_height = 32

        # 1. Exportar Tilesheet completo (PNG)
        img = SpriteRenderer.render_from_csv_entry(
            rom_data, sp["tile_offset"], sp["palette_offset"], tiles_wide, sp["max_size"]
        )
        
        if not img:
            print(f"  -> Fallo renderizado de {safe_name}")
            continue

        png_path = os.path.join(output_dir, f"{safe_name}.png")
        img.save(png_path, "PNG")

        # 2. Exportar Animación (GIF)
        # Leer data y paleta directamente para frame extraction
        tile_data = rom_data[sp["tile_offset"] : sp["tile_offset"] + min(sp["max_size"], 0x10000)]
        pal_data = rom_data[sp["palette_offset"] : sp["palette_offset"] + 32]
        
        import struct
        from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.codec_tiles import bgr555_to_rgb
        
        palette = [(0,0,0)] * 16
        if len(pal_data) >= 32:
            palette = [bgr555_to_rgb(struct.unpack_from('<H', pal_data, i*2)[0]) for i in range(16)]

        # Intentar extraer frames con la heurística
        frames = SpriteRenderer.extract_frames_from_sheet(tile_data, palette, frame_width, frame_height)
        
        # Si falló porque el tilesheet es más pequeño o raro, intentar fallback
        if not frames or len(frames) < 2:
            if frame_height != 16:
                frames_fallback = SpriteRenderer.extract_frames_from_sheet(tile_data, palette, 16, 16)
                if frames_fallback and len(frames_fallback) > len(frames):
                    frames = frames_fallback

        if frames:
            gif_path = os.path.join(output_dir, f"{safe_name}.gif")
            SpriteRenderer.create_animated_gif(frames, gif_path, duration=200, loop=0)

    print("¡Volcado completado con éxito!")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Extrae todos los sprites del ROM (PNG y GIF)")
    parser.add_argument("rom", help="Ruta al archivo ROM (.gba)")
    parser.add_argument("--mode", default="fomt", choices=["fomt", "mfomt"], help="Modo de juego")
    parser.add_argument("--out", default="sprites_dump", help="Carpeta de salida")
    args = parser.parse_args()
    
    dump_all(args.rom, args.mode, args.out)
