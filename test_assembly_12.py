import os
from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.sprite_decoder import SpriteRenderer
import struct
from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.codec_tiles import bgr555_to_rgb

def test_assembly12():
    rom_path = r"j:\scratch\Harvest Moon - Friends of Mineral Town.gba"
    with open(rom_path, 'rb') as f:
        rom_data = f.read()

    tile_offset = 0x62329C
    palette_offset = 0x662AC0

    # 12 tiles = 384 bytes (0x180)
    tile_data = rom_data[tile_offset : tile_offset + 384]
    pal_data = rom_data[palette_offset : palette_offset + 32]
    palette = [bgr555_to_rgb(struct.unpack_from('<H', pal_data, i*2)[0]) for i in range(16)]

    # Probar ensamblaje de 12 tiles asumiendo 32x16 (arriba) + 32x8 (abajo)
    # Como ambos son de 4 tiles de ancho (32 px), el mapeo lineal tw=4 deberia funcionar perfecto!
    oam_32x24 = [
        {"x": 0, "y": 0, "w": 32, "h": 16, "tile_id": 0},
        {"x": 0, "y": 16, "w": 32, "h": 8, "tile_id": 8}
    ]

    img = SpriteRenderer.render_with_oam(tile_data, palette, oam_32x24, (32, 24))
    
    os.makedirs("test_assembly", exist_ok=True)
    img.save("test_assembly/karen_12tiles_32x24.png")

    # Guardar tb como tira lineal
    img_linear = SpriteRenderer.render_single_frame(tile_data, palette, 4, 3, 0)
    img_linear.save("test_assembly/karen_12tiles_linear.png")

if __name__ == "__main__":
    test_assembly12()
