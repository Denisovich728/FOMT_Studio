# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.4.4)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
"""
sprite_decoder.py — Decodificador de Sprites FoMT
══════════════════════════════════════════════════
Convierte datos crudos de tiles 4bpp en imágenes renderizadas.
Integra con fomt_gfx_scanner.py y el motor de mapas existente.

Usa las clases GBAPalette, GBATile de mapas.py como base.
"""
from typing import List, Optional, Tuple
from PIL import Image

from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.mapas import (
    decompress_lz77, decompress_auto, GBAPalette, GBATile, OAMEntry, OAM_DIMS
)
from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.codec_tiles import (
    bgr555_to_rgb, decode_4bpp_tile
)


# ═══════════════════════════════════════════════════════════════
#  RENDERIZADOR DE SPRITES
# ═══════════════════════════════════════════════════════════════

class SpriteRenderer:
    """
    Renderiza sprites desde datos crudos 4bpp con paleta BGR555.
    Soporta sprite sheets, frames individuales, y composición OAM.
    """

    # Paleta por defecto (escala de grises) para cuando no hay paleta
    DEFAULT_PALETTE = [(i * 17, i * 17, i * 17) for i in range(16)]

    @staticmethod
    def render_tile_sheet(tile_data: bytes,
                          palette: List[Tuple[int,int,int]],
                          tiles_wide: int = 16,
                          transparent_color: int = 0) -> Optional[Image.Image]:
        """
        Renderiza datos 4bpp como un sheet de tiles.

        Args:
            tile_data: Datos crudos 4bpp (32 bytes por tile)
            palette: Lista de 16 colores RGB
            tiles_wide: Número de tiles por fila
            transparent_color: Índice del color transparente (default: 0)

        Returns:
            Imagen RGBA del sprite sheet
        """
        tile_size = 32  # 8x8 tile en 4bpp
        num_tiles = len(tile_data) // tile_size
        if num_tiles == 0:
            return None

        tiles_x = min(tiles_wide, num_tiles)
        tiles_y = max(1, (num_tiles + tiles_x - 1) // tiles_x)

        img = Image.new('RGBA', (tiles_x * 8, tiles_y * 8), (0, 0, 0, 0))
        px = img.load()

        for t in range(num_tiles):
            base_x = (t % tiles_x) * 8
            base_y = (t // tiles_x) * 8
            off = t * tile_size

            pixels = decode_4bpp_tile(tile_data, off)

            for py in range(8):
                for pxx in range(8):
                    idx = pixels[py * 8 + pxx]
                    if idx == transparent_color:
                        continue  # Transparente (ya es RGBA 0,0,0,0)
                    if idx < len(palette):
                        r, g, b = palette[idx]
                        px[base_x + pxx, base_y + py] = (r, g, b, 255)

        return img

    @staticmethod
    def render_single_frame(tile_data: bytes,
                             palette: List[Tuple[int,int,int]],
                             width_tiles: int,
                             height_tiles: int,
                             start_tile: int = 0) -> Optional[Image.Image]:
        """
        Renderiza un frame de sprite de dimensiones específicas.

        Args:
            tile_data: Datos crudos 4bpp de todos los tiles
            palette: Paleta de 16 colores
            width_tiles: Ancho en tiles (1 tile = 8px)
            height_tiles: Alto en tiles
            start_tile: Índice del primer tile del frame
        """
        frame_tiles = width_tiles * height_tiles
        tile_size = 32
        start_off = start_tile * tile_size

        if start_off + frame_tiles * tile_size > len(tile_data):
            return None

        frame_data = tile_data[start_off:start_off + frame_tiles * tile_size]
        return SpriteRenderer.render_tile_sheet(
            frame_data, palette, width_tiles
        )

    @staticmethod
    def render_with_oam(tile_data: bytes,
                        palette: List[Tuple[int,int,int]],
                        oam_entries: List[dict],
                        canvas_size: Tuple[int,int] = (64, 64)) -> Image.Image:
        """
        Renderiza un sprite compuesto usando entradas OAM.

        Args:
            tile_data: Datos crudos 4bpp
            palette: Paleta de 16 colores
            oam_entries: Lista de dicts con campos: x, y, w, h, tile_id, flip_h, flip_v
            canvas_size: Tamaño del canvas final

        Returns:
            Imagen RGBA compuesta
        """
        canvas = Image.new('RGBA', canvas_size, (0, 0, 0, 0))

        for oam in oam_entries:
            x, y = oam.get('x', 0), oam.get('y', 0)
            w, h = oam.get('w', 8), oam.get('h', 8)
            tile_id = oam.get('tile_id', 0)
            flip_h = oam.get('flip_h', False)
            flip_v = oam.get('flip_v', False)

            tiles_x = w // 8
            tiles_y = h // 8

            piece = SpriteRenderer.render_single_frame(
                tile_data, palette, tiles_x, tiles_y, tile_id
            )
            if piece is None:
                continue

            if flip_h:
                piece = piece.transpose(Image.FLIP_LEFT_RIGHT)
            if flip_v:
                piece = piece.transpose(Image.FLIP_TOP_BOTTOM)

            # Clamp position to canvas
            paste_x = x if x < 128 else x - 256
            paste_y = y if y < 128 else y - 256

            canvas.paste(piece, (paste_x, paste_y), piece)

        return canvas

    @staticmethod
    def extract_frames_from_sheet(tile_data: bytes,
                                   palette: List[Tuple[int,int,int]],
                                   frame_width: int = 16,
                                   frame_height: int = 32) -> List[Image.Image]:
        """
        Extrae múltiples frames de un sprite sheet.
        Asume que los frames están organizados linealmente en tiles.

        Args:
            tile_data: Datos 4bpp del sheet completo
            palette: Paleta de 16 colores
            frame_width: Ancho de cada frame en píxeles
            frame_height: Alto de cada frame en píxeles

        Returns:
            Lista de imágenes RGBA, una por frame
        """
        tw = frame_width // 8
        th = frame_height // 8
        tiles_per_frame = tw * th
        total_tiles = len(tile_data) // 32
        num_frames = total_tiles // tiles_per_frame

        frames = []
        for f in range(num_frames):
            frame = SpriteRenderer.render_single_frame(
                tile_data, palette, tw, th, f * tiles_per_frame
            )
            if frame:
                frames.append(frame)

        return frames

    @staticmethod
    def create_animation_strip(frames: List[Image.Image],
                                horizontal: bool = True) -> Optional[Image.Image]:
        """
        Crea una tira de animación a partir de frames individuales.

        Args:
            frames: Lista de imágenes (todos del mismo tamaño)
            horizontal: True para tira horizontal, False para vertical

        Returns:
            Imagen con todos los frames en una tira
        """
        if not frames:
            return None

        fw, fh = frames[0].size
        if horizontal:
            strip = Image.new('RGBA', (fw * len(frames), fh), (0, 0, 0, 0))
            for i, frame in enumerate(frames):
                strip.paste(frame, (i * fw, 0), frame)
        else:
            strip = Image.new('RGBA', (fw, fh * len(frames)), (0, 0, 0, 0))
            for i, frame in enumerate(frames):
                strip.paste(frame, (0, i * fh), frame)

        return strip

    @staticmethod
    def render_from_rom(rom_data: bytes,
                        tile_offset: int,
                        palette_offset: int,
                        tiles_wide: int = 16,
                        palette_compressed: bool = False) -> Optional[Image.Image]:
        """
        Convenience method: Lee tiles y paleta directamente de la ROM.

        Args:
            rom_data: Datos de la ROM completa
            tile_offset: Offset en ROM de los datos de tiles (LZ77)
            palette_offset: Offset en ROM de la paleta
            tiles_wide: Tiles por fila
            palette_compressed: Si la paleta está comprimida con LZ77
        """
        # Descomprimir tiles
        try:
            tile_data = decompress_lz77(rom_data, tile_offset)
        except (ValueError, IndexError):
            return None

        if not tile_data:
            return None

        # Leer paleta
        if palette_compressed:
            try:
                pal_data = decompress_lz77(rom_data, palette_offset)
            except (ValueError, IndexError):
                pal_data = None
        else:
            pal_data = rom_data[palette_offset:palette_offset + 32]

        if pal_data and len(pal_data) >= 32:
            import struct
            palette = [bgr555_to_rgb(struct.unpack_from('<H', pal_data, i*2)[0])
                       for i in range(16)]
        else:
            palette = SpriteRenderer.DEFAULT_PALETTE

        return SpriteRenderer.render_tile_sheet(tile_data, palette, tiles_wide)

    @staticmethod
    def render_from_csv_entry(rom_data: bytes,
                               tile_offset: int,
                               palette_offset: int,
                               tiles_wide: int = 4,
                               max_size: int = 4096) -> Optional[Image.Image]:
        """
        Renderiza un sprite desde offsets del CSV sprite_data.
        Usa estrictamente datos RAW (sin compresor) como solicitó el usuario.
        
        Args:
            rom_data: Datos de la ROM completa
            tile_offset: Offset ROM del tileset
            palette_offset: Offset ROM de la paleta BGR555
            tiles_wide: Tiles por fila para el render
            max_size: Tamaño máximo en bytes antes de tocar el siguiente sprite.
        """
        import struct

        # Leer datos RAW (cortar en max_size o 4096 por seguridad)
        actual_size = min(max_size, 0x10000, len(rom_data) - tile_offset)
        if actual_size <= 0:
            return None
            
        tile_data = rom_data[tile_offset:tile_offset + actual_size]

        # Leer paleta estrictamente RAW (32 bytes)
        pal_data = rom_data[palette_offset:palette_offset + 32]

        if len(pal_data) >= 32:
            palette = [bgr555_to_rgb(struct.unpack_from('<H', pal_data, i*2)[0])
                       for i in range(16)]
        else:
            palette = SpriteRenderer.DEFAULT_PALETTE

        return SpriteRenderer.render_tile_sheet(tile_data, palette, tiles_wide)

    @staticmethod
    def create_animated_gif(frames: List[Image.Image],
                            output_path: str,
                            duration: int = 150,
                            loop: int = 0) -> bool:
        """
        Compila una lista de frames PIL en un GIF animado.

        Args:
            frames: Lista de imágenes RGBA
            output_path: Ruta de salida del archivo GIF
            duration: Duración de cada frame en milisegundos
            loop: Número de loops (0 = infinito)

        Returns:
            True si se exportó correctamente
        """
        if not frames:
            return False

        # Convertir RGBA a P (palettized) para GIF
        gif_frames = []
        for frame in frames:
            # Crear fondo blanco para transparencia
            bg = Image.new('RGBA', frame.size, (255, 255, 255, 255))
            bg.paste(frame, mask=frame.split()[3] if frame.mode == 'RGBA' else None)
            gif_frames.append(bg.convert('P', palette=Image.ADAPTIVE, colors=256))

        gif_frames[0].save(
            output_path,
            save_all=True,
            append_images=gif_frames[1:],
            duration=duration,
            loop=loop,
            optimize=False
        )
        return True
