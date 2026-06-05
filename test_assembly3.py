import os
from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.sprite_decoder import SpriteRenderer
import struct
from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.codec_tiles import bgr555_to_rgb

def test_assembly3():
    rom_path = r"j:\scratch\Harvest Moon - Friends of Mineral Town.gba"
    with open(rom_path, 'rb') as f:
        rom_data = f.read()

    tile_offset = 0x62329C
    palette_offset = 0x662AC0

    tile_data = rom_data[tile_offset : tile_offset + 192]
    pal_data = rom_data[palette_offset : palette_offset + 32]
    palette = [bgr555_to_rgb(struct.unpack_from('<H', pal_data, i*2)[0]) for i in range(16)]

    # Probar ensamble 4: Izquierda 8x16, Derecha 8x16, Pies 16x8
    oam_4 = [
        {"x": 0, "y": 0, "w": 8, "h": 16, "tile_id": 0},
        {"x": 8, "y": 0, "w": 8, "h": 16, "tile_id": 2},
        {"x": 0, "y": 16, "w": 16, "h": 8, "tile_id": 4}
    ]

    # Probar ensamble 5: Cabeza 16x8, TorsoIzq 8x16, TorsoDer 8x16
    oam_5 = [
        {"x": 0, "y": 0, "w": 16, "h": 8, "tile_id": 0},
        {"x": 0, "y": 8, "w": 8, "h": 16, "tile_id": 2},
        {"x": 8, "y": 8, "w": 8, "h": 16, "tile_id": 4}
    ]

    img4 = SpriteRenderer.render_with_oam(tile_data, palette, oam_4, (16, 24))
    img5 = SpriteRenderer.render_with_oam(tile_data, palette, oam_5, (16, 24))
    
    os.makedirs("test_assembly", exist_ok=True)
    img4.save("test_assembly/karen_oam4.png")
    img5.save("test_assembly/karen_oam5.png")

if __name__ == "__main__":
    test_assembly3()
