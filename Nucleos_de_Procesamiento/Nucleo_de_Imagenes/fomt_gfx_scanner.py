# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.0.0)
# "The Imposibility Update"
# Desarrollado por: Denisovich728
# ============================================================
"""
fomt_gfx_scanner.py — Motor de Escaneo de Gráficos de FoMT
══════════════════════════════════════════════════════════════
Escanea la ROM para localizar todos los bancos de gráficos:
- Bloques LZ77 comprimidos (sprites, tilesets, paletas)
- Tablas de punteros a gráficos
- Paletas BGR555

Basado en ingeniería inversa de BlueSpider y HM Studio.
"""
import struct
from typing import Dict, List, Optional, Tuple

# ═══════════════════════════════════════════════════════════════
#  TIPOS DE DATOS
# ═══════════════════════════════════════════════════════════════

class GfxBlock:
    """Representa un bloque de gráficos descubierto en la ROM."""
    __slots__ = ('offset', 'size', 'kind', 'palette_offset', 'name')

    KIND_PALETTE  = "PALETTE"
    KIND_SPRITE   = "SPRITE_SHEET"
    KIND_PORTRAIT = "PORTRAIT"
    KIND_TILESET  = "TILESET"
    KIND_DATA     = "DATA"

    def __init__(self, offset: int, size: int, kind: str = "DATA",
                 palette_offset: int = -1, name: str = ""):
        self.offset = offset
        self.size = size
        self.kind = kind
        self.palette_offset = palette_offset
        self.name = name or f"{kind}_{offset:06X}"

    @property
    def tile_count(self) -> int:
        return self.size // 32

    @property
    def estimated_dimensions(self) -> Tuple[int, int]:
        """Estima las dimensiones en píxeles del gráfico."""
        tiles = self.tile_count
        if tiles == 0:
            return (0, 0)
        # Dimensiones comunes de sprites GBA
        dim_map = {
            1: (8, 8), 2: (16, 8), 4: (16, 16), 8: (16, 32),
            16: (32, 32), 24: (32, 48), 32: (32, 64),
            64: (64, 64), 128: (128, 64),
        }
        if tiles in dim_map:
            return dim_map[tiles]
        # Calcular la mejor disposición cuadrada
        import math
        tw = int(math.ceil(math.sqrt(tiles)))
        th = (tiles + tw - 1) // tw
        return (tw * 8, th * 8)

    def __repr__(self):
        return f"GfxBlock({self.kind}, 0x{self.offset:06X}, {self.size}B)"


class PaletteEntry:
    """Paleta BGR555 de 16 colores."""
    __slots__ = ('offset', 'colors_rgb', 'is_compressed')

    def __init__(self, offset: int, colors_rgb: List[Tuple[int,int,int]],
                 is_compressed: bool = False):
        self.offset = offset
        self.colors_rgb = colors_rgb
        self.is_compressed = is_compressed


# ═══════════════════════════════════════════════════════════════
#  FUNCIONES DE UTILIDAD
# ═══════════════════════════════════════════════════════════════

def _read_u32(rom: bytes, off: int) -> int:
    return struct.unpack_from('<I', rom, off)[0]

def _read_u16(rom: bytes, off: int) -> int:
    return struct.unpack_from('<H', rom, off)[0]

def _is_gba_ptr(val: int) -> bool:
    return 0x08000000 <= val <= 0x09FFFFFF

def _gba_to_rom(ptr: int) -> int:
    return ptr & 0x01FFFFFF

def _bgr555_to_rgb(c16: int) -> Tuple[int, int, int]:
    return ((c16 & 0x1F) << 3, ((c16 >> 5) & 0x1F) << 3, ((c16 >> 10) & 0x1F) << 3)


# ═══════════════════════════════════════════════════════════════
#  ESCÁNER PRINCIPAL
# ═══════════════════════════════════════════════════════════════

class FoMTGfxScanner:
    """
    Escáner de gráficos para ROM de Harvest Moon: FoMT.
    Descubre automáticamente sprites, portraits, paletas y tilesets.
    """

    # Tamaños conocidos de bloques de gráficos
    PALETTE_SIZES = {32, 512}       # 16 colores o 256 colores
    PORTRAIT_SIZE = 2048            # 64x64 4bpp
    SPRITE_SHEET_SIZE = 4096        # 128 tiles (sprite sheet estándar)
    TILESET_SIZES = {8192, 16384}   # Tilesets de mapas

    def __init__(self, rom_data: bytes):
        self.rom = rom_data
        self.gfx_blocks: Dict[int, GfxBlock] = {}
        self.palettes: Dict[int, PaletteEntry] = {}
        self._lz77_cache: Dict[int, int] = {}  # offset -> decompressed_size

    def scan_all(self, progress_callback=None) -> None:
        """Ejecuta el escaneo completo de la ROM."""
        self._scan_lz77_blocks(progress_callback)
        self._scan_raw_palettes()
        self._classify_blocks()
        self._link_palettes()

    def _scan_lz77_blocks(self, progress_callback=None) -> None:
        """Escanea todos los bloques LZ77 en la ROM."""
        from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.mapas import decompress_lz77

        total = len(self.rom)
        for off in range(0, total - 4, 4):
            if progress_callback and off % 0x40000 == 0:
                progress_callback(off / total)

            if self.rom[off] != 0x10:
                continue

            size = _read_u32(self.rom, off) >> 8
            if size < 32 or size > 0x20000:
                continue

            try:
                data = decompress_lz77(self.rom, off)
                if data and len(data) == size:
                    self._lz77_cache[off] = size
                    self.gfx_blocks[off] = GfxBlock(off, size)

                    # Paletas comprimidas
                    if size in self.PALETTE_SIZES:
                        colors = [_bgr555_to_rgb(_read_u16(data, i*2))
                                  for i in range(min(16, len(data)//2))]
                        self.palettes[off] = PaletteEntry(off, colors, True)
            except (ValueError, IndexError):
                continue

    def _scan_raw_palettes(self) -> None:
        """Busca paletas sin comprimir (primer color transparente)."""
        for off in range(0, len(self.rom) - 32, 32):
            if _read_u16(self.rom, off) != 0x0000:
                continue

            valid = True
            total = 0
            for c in range(1, 16):
                val = _read_u16(self.rom, off + c * 2)
                if val > 0x7FFF:
                    valid = False
                    break
                total += val

            if valid and total > 500:
                colors = [_bgr555_to_rgb(_read_u16(self.rom, off + i*2))
                          for i in range(16)]
                if off not in self.palettes:
                    self.palettes[off] = PaletteEntry(off, colors, False)

    def _classify_blocks(self) -> None:
        """Clasifica cada bloque por su tamaño y contenido."""
        for off, block in self.gfx_blocks.items():
            if block.size in self.PALETTE_SIZES:
                block.kind = GfxBlock.KIND_PALETTE
            elif block.size == self.PORTRAIT_SIZE:
                block.kind = GfxBlock.KIND_PORTRAIT
            elif block.size == self.SPRITE_SHEET_SIZE:
                block.kind = GfxBlock.KIND_SPRITE
            elif block.size in self.TILESET_SIZES:
                block.kind = GfxBlock.KIND_TILESET
            elif block.size % 32 == 0 and 128 <= block.size <= 8192:
                block.kind = GfxBlock.KIND_SPRITE

    def _link_palettes(self) -> None:
        """Intenta vincular cada sprite con su paleta más cercana."""
        palette_offsets = sorted(self.palettes.keys())
        if not palette_offsets:
            return

        for off, block in self.gfx_blocks.items():
            if block.kind in (GfxBlock.KIND_PALETTE, GfxBlock.KIND_DATA):
                continue

            # Buscar via pointer chain
            pal_off = self._find_palette_by_pointer(off)
            if pal_off is not None:
                block.palette_offset = pal_off
                continue

            # Fallback: paleta más cercana anterior
            import bisect
            idx = bisect.bisect_left(palette_offsets, off)
            if idx > 0:
                block.palette_offset = palette_offsets[idx - 1]

    def _find_palette_by_pointer(self, sprite_offset: int) -> Optional[int]:
        """Busca la paleta asociada a un sprite via cadena de punteros."""
        sprite_ptr = sprite_offset | 0x08000000
        ptr_bytes = struct.pack('<I', sprite_ptr)

        pos = 0
        while True:
            ref = self.rom.find(ptr_bytes, pos)
            if ref < 0:
                break

            for delta in [4, -4, 8, -8]:
                nearby = ref + delta
                if 0 <= nearby < len(self.rom) - 4:
                    val = _read_u32(self.rom, nearby)
                    if _is_gba_ptr(val):
                        pal_rom = _gba_to_rom(val)
                        if pal_rom in self.palettes:
                            return pal_rom
            pos = ref + 1

        return None

    # ═══════════════════════════════════════════════════════════
    #  ACCESO A DATOS
    # ═══════════════════════════════════════════════════════════

    def get_sprites(self) -> List[GfxBlock]:
        """Retorna todos los bloques de tipo sprite."""
        return sorted(
            [b for b in self.gfx_blocks.values()
             if b.kind in (GfxBlock.KIND_SPRITE, GfxBlock.KIND_PORTRAIT)],
            key=lambda b: b.offset
        )

    def get_portraits(self) -> List[GfxBlock]:
        """Retorna todos los bloques de tipo portrait."""
        return sorted(
            [b for b in self.gfx_blocks.values()
             if b.kind == GfxBlock.KIND_PORTRAIT],
            key=lambda b: b.offset
        )

    def get_palettes(self) -> List[PaletteEntry]:
        """Retorna todas las paletas encontradas."""
        return sorted(self.palettes.values(), key=lambda p: p.offset)

    def get_palette_for(self, gfx_block: GfxBlock) -> Optional[PaletteEntry]:
        """Retorna la paleta asociada a un bloque gráfico."""
        if gfx_block.palette_offset >= 0:
            return self.palettes.get(gfx_block.palette_offset)
        return None

    def decompress_block(self, offset: int) -> Optional[bytes]:
        """Descomprime un bloque LZ77 dado su offset."""
        from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.mapas import decompress_lz77
        try:
            return decompress_lz77(self.rom, offset)
        except (ValueError, IndexError):
            return None

    @property
    def stats(self) -> dict:
        """Estadísticas del escaneo."""
        kinds = {}
        for b in self.gfx_blocks.values():
            kinds[b.kind] = kinds.get(b.kind, 0) + 1
        return {
            "total_blocks": len(self.gfx_blocks),
            "total_palettes": len(self.palettes),
            "by_kind": kinds,
        }
