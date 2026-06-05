import os
from PIL import Image
from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.sprite_decoder import SpriteRenderer
import struct
from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.codec_tiles import bgr555_to_rgb

def test_tiles():
    rom_path = r"j:\scratch\Harvest Moon - Friends of Mineral Town.gba"
    with open(rom_path, 'rb') as f:
        rom_data = f.read()

    # Karen-Daily base
    tile_offset = 0x62329C
    palette_offset = 0x662AC0

    # Leer un frame (6 tiles = 192 bytes)
    tile_data = rom_data[tile_offset : tile_offset + 192]
    pal_data = rom_data[palette_offset : palette_offset + 32]
    
    palette = [bgr555_to_rgb(struct.unpack_from('<H', pal_data, i*2)[0]) for i in range(16)]

    os.makedirs("test_assembly", exist_ok=True)

    # Renderizar los 6 tiles individuales (cada uno es 8x8)
    for i in range(6):
        # Tomar 32 bytes para 1 tile
        single_tile_data = tile_data[i*32 : (i+1)*32]
        img = SpriteRenderer.render_tile_sheet(single_tile_data, palette, 1)
        if img:
            # Escalar a 4x para que sea fácil de ver
            img = img.resize((32, 32), Image.NEAREST)
            img.save(f"test_assembly/karen_tile_{i}.png")
            
    # También renderizar una tira horizontal de los 6 tiles
    img_strip = SpriteRenderer.render_tile_sheet(tile_data, palette, 6)
    if img_strip:
        img_strip = img_strip.resize((6 * 32, 32), Image.NEAREST)
        img_strip.save("test_assembly/karen_strip_all_6.png")

    print("Tiles individuales guardados en test_assembly/")

if __name__ == "__main__":
    test_tiles()
