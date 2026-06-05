import os
from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.sprite_decoder import SpriteRenderer
import struct
from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.codec_tiles import bgr555_to_rgb

def test_assembly():
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

    # Probar ensamble 1: 16x16 cabeza/torso + 16x8 piernas
    oam_1 = [
        {"x": 0, "y": 0, "w": 16, "h": 16, "tile_id": 0},
        {"x": 0, "y": 16, "w": 16, "h": 8, "tile_id": 4}
    ]

    # Probar ensamble 2: 16x8 cabeza + 16x16 torso/piernas
    oam_2 = [
        {"x": 0, "y": 0, "w": 16, "h": 8, "tile_id": 0},
        {"x": 0, "y": 8, "w": 16, "h": 16, "tile_id": 2}
    ]

    # Probar ensamble 3: 8x24 izquierda + 8x24 derecha (muy raro pero posible, 8x24 no existe en hw, serian tres 8x8)
    oam_3 = [
        {"x": 0, "y": 0, "w": 8, "h": 8, "tile_id": 0},
        {"x": 0, "y": 8, "w": 8, "h": 16, "tile_id": 1},
        {"x": 8, "y": 0, "w": 8, "h": 8, "tile_id": 3},
        {"x": 8, "y": 8, "w": 8, "h": 16, "tile_id": 4}
    ]

    img1 = SpriteRenderer.render_with_oam(tile_data, palette, oam_1, (16, 24))
    img2 = SpriteRenderer.render_with_oam(tile_data, palette, oam_2, (16, 24))
    
    os.makedirs("test_assembly", exist_ok=True)
    img1.save("test_assembly/karen_oam1.png")
    img2.save("test_assembly/karen_oam2.png")
    print("Test images saved to test_assembly/")

if __name__ == "__main__":
    test_assembly()
