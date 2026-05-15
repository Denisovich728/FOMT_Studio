# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.6.5)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
import os
from Nucleos_de_Procesamiento.Nucleo_de_Datos.parche_font import apply_font_patch

# ============================================================================
# SOBERANÍA DE LA Ñ - Inyector de Hardware v3.0
# ============================================================================
# Arquitectura del Font de FoMT (USA):
#   - Tileset Base ROM:  0x0075A440  (13 refs en el código del juego)
#   - Formato:           4bpp, 8x8 píxeles, 32 bytes por tile
#   - Renderizado:       8x16 (2 tiles: TOP + BOTTOM separados por 9 tiles)
#
# Layout del tileset (confirmado por dump visual):
#   - Tiles 0-10:    Dígitos y símbolos del HUD (tops)
#   - Tiles 19-30:   Símbolos del HUD (bottoms/extras)
#   - Tiles 32-40:   Grupo B
#   - Tiles 64-72:   Grupo C  
#   - Tiles 96-104:  Grupo D TOPS (chars 0xCA-0xD2)
#   - Tiles 105-116: Grupo D BOTTOMS + extras (chars 0xD3-0xDE / bottoms)
#   - Tiles 128-136: Grupo E
#
# Mapeo de chars objetivo:
#   - Char 0xCB: TOP=tile 97 @ 0x0075B060, BOTTOM=tile 106 @ 0x0075B180
#   - Char 0xCC: TOP=tile 98 @ 0x0075B080, BOTTOM=tile 107 @ 0x0075B1A0
#
# El tile viewer de la VRAM muestra 30 tiles por fila. Los chars 8x16
# se ven con el top en fila N y el bottom en fila N+1 (offset +30 tiles
# en VRAM). En ROM, el offset entre top y bottom es +9 tiles (9 chars 
# por grupo, tops contiguos seguidos de bottoms contiguos).
#
# Paleta del font: 0=transparente, 1=cuerpo letra, 2=sombra
# ============================================================================

TILESET_BASE = 0x0075A440
TILE_SIZE = 32  # 8x8 4bpp = 32 bytes
BOTTOM_OFFSET = 9  # El tile bottom de un char está 9 tiles después del top

# Offsets TOP:  TILESET_BASE + tile_index * TILE_SIZE
# Offsets BOT:  TILESET_BASE + (tile_index + 9) * TILE_SIZE
OFFSET_CB_TOP = TILESET_BASE + 97 * TILE_SIZE   # = 0x0075B060
OFFSET_CB_BOT = TILESET_BASE + 106 * TILE_SIZE  # = 0x0075B180
OFFSET_CC_TOP = TILESET_BASE + 98 * TILE_SIZE   # = 0x0075B080
OFFSET_CC_BOT = TILESET_BASE + 107 * TILE_SIZE  # = 0x0075B1A0


def _encode_tile(pixel_rows):
    """
    Codifica 8 filas de texto visual en 32 bytes de datos 4bpp GBA.
    Cada fila es un string de 8 caracteres: '.'=0, '#'=1, 'S'=2
    En GBA 4bpp: nibble bajo = pixel izquierdo, nibble alto = pixel derecho.
    """
    CHAR_TO_IDX = {'.': 0, '#': 1, 'S': 2}
    data = bytearray()
    for row in pixel_rows:
        pixels = [CHAR_TO_IDX[c] for c in row]
        for i in range(0, 8, 2):
            data.append(pixels[i] | (pixels[i + 1] << 4))
    return bytes(data)


# ============================================================================
# PAYLOAD GRÁFICO: Glifos de Ñ y ñ en 8x16 (TOP 8x8 + BOTTOM 8x8)
# Diseñados para coincidir con el estilo del font de FoMT:
#   '.' = transparente (idx 0)
#   '#' = cuerpo de la letra (idx 1)
#   'S' = sombra inferior-derecha (idx 2)
# ============================================================================

# ── Ñ MAYÚSCULA ──────────────────────────────────────────────────────
# TOP: Tilde + inicio del cuerpo de N
TILE_ENE_MAYUS_TOP = _encode_tile([
    '.##.##S.',  # Tilde ~
    '.SS.SSS.',  # Sombra tilde
    '#S...#S.',  # N: trazo izquierdo + derecho
    '##S..#S.',  # N: diagonal empieza
    '###S.#S.',  # N: diagonal baja
    '#S##S#S.',  # N: diagonal centro
    '#S.###S.',  # N: diagonal termina
    '#S...#S.',  # N: trazos verticales
])

# BOTTOM: Final del cuerpo de N + sombra
TILE_ENE_MAYUS_BOT = _encode_tile([
    '#S...#S.',  # N: trazos verticales
    '#S...#S.',  # N: trazos verticales
    '.S....S.',  # Sombra inferior
    '........',  # Transparente
    '........',  # Transparente
    '........',  # Transparente
    '........',  # Transparente
    '........',  # Transparente
])

# ── ñ MINÚSCULA ──────────────────────────────────────────────────────
# TOP: Tilde + arco de n
TILE_ENE_MIN_TOP = _encode_tile([
    '.##.##S.',  # Tilde ~
    '.SS.SSS.',  # Sombra tilde
    '........',  # Espacio
    '#S###S..',  # n: trazo + arco superior
    '####S#S.',  # n: arco completo
    '#S..##S.',  # n: cuerpo recto
    '#S..##S.',  # n: cuerpo recto
    '#S..##S.',  # n: cuerpo recto
])

# BOTTOM: Fin de n + sombra
TILE_ENE_MIN_BOT = _encode_tile([
    '.S...SS.',  # Sombra inferior
    '........',  # Transparente
    '........',  # Transparente
    '........',  # Transparente
    '........',  # Transparente
    '........',  # Transparente
    '........',  # Transparente
    '........',  # Transparente
])


# ── Gráficos Adicionales (UI/Naming Screen) ──────────────────────────
# Set 1 (Encontrado por el usuario)
OFFSET_N_MAJ_UI_1 = 0x4F9420
OFFSET_N_MIN_UI_1 = 0x4F942C

# Set 2 (Offset activo detectado por escaneo de patrones)
OFFSET_N_MAJ_UI_2 = 0x117B50
OFFSET_N_MIN_UI_2 = 0x117B44

BYTES_N_MAJ_UI_ORIG = bytes([0x28, 0x54, 0x4C, 0x4C, 0x54, 0x54, 0x54, 0x64, 0x64, 0x44, 0x00, 0x00])
BYTES_N_MAJ_UI_FIXED = bytes([0x14, 0x2A, 0x32, 0x32, 0x2A, 0x2A, 0x2A, 0x26, 0x26, 0x22, 0x00, 0x00])
BYTES_N_MIN_UI = bytes([0x00, 0x38, 0x00, 0x78, 0x44, 0x44, 0x44, 0x44, 0x44, 0x44, 0x00, 0x00])


def aplicar_parche_n(project):
    """
    Aplica el parche de Soberanía de la Ñ a la ROM.
    Usa el motor del proyecto para escribir en disco y actualizar la memoria virtual.

    Fases:
      1. Teclado UI: Reasignar teclas ♂/♀ → Ñ/ñ
      2. Gráficos: Inyectar tiles 4bpp en el tileset del font (TOP + BOTTOM)
      3. UI Graphics: Inyectar glifos en ambos sets de offsets (Primario + Alternativo)
      4. Firma: Marcar la ROM con flag N_MODE para persistencia
    """
    if not project or not project.base_rom_path:
        raise ValueError("Proyecto no válido o ROM base no encontrada.")

    # ── Fase 1: Teclado UI (Redirección Lógica) ──────────────────────
    # Reemplazamos el char 0xB7 (♂ en Row 2) por Ñ (0xCB)
    project.write_patch(0x000E89EF, b'\xCB')
    # Reemplazamos el char 0xB6 (♀ en Row 2) por ñ (0xCC)
    project.write_patch(0x000E89ED, b'\xCC')

    # ── Fase 2: Inyección Gráfica Font (TOP + BOTTOM) ─────────────────────
    project.write_patch(OFFSET_CB_TOP, TILE_ENE_MAYUS_TOP)
    project.write_patch(OFFSET_CB_BOT, TILE_ENE_MAYUS_BOT)
    project.write_patch(OFFSET_CC_TOP, TILE_ENE_MIN_TOP)
    project.write_patch(OFFSET_CC_BOT, TILE_ENE_MIN_BOT)

    # ── Fase 3: Gráficos Adicionales (UI/Naming Screen) ──────────────────
    # Aplicar a ambos sets de offsets
    # En el set 1 mantenemos el original
    project.write_patch(OFFSET_N_MAJ_UI_1, BYTES_N_MAJ_UI_ORIG)
    project.write_patch(OFFSET_N_MIN_UI_1, BYTES_N_MIN_UI)
    
    # En el set 2 (el activo) aplicamos la corrección de espejo (FIXED)
    project.write_patch(OFFSET_N_MAJ_UI_2, BYTES_N_MAJ_UI_FIXED)
    project.write_patch(OFFSET_N_MIN_UI_2, BYTES_N_MIN_UI)

    # ── Fase 4: Gráficos de Interfaz (HUD/Etiquetas) ──────────────────
    # Bloques de 32 bytes (8x8 4bpp) para diversos elementos de la UI
    project.write_patch(0x75A5A0, bytes.fromhex("B0 BB BB 00 B0 0B B0 0B B0 0B B0 0B B0 0B B0 0B B0 BB BB 00 B0 0B 00 00 B0 0B 00 00 B0 0B 00 00"))
    project.write_patch(0x75A5C0, bytes.fromhex("B0 BB BB 00 B0 0B B0 0B B0 0B B0 0B B0 0B B0 0B B0 BB BB 00 B0 0B BB 00 B0 0B B0 0B B0 0B B0 BB"))
    project.write_patch(0x75A5E0, bytes.fromhex("55 00 00 55 55 00 00 55 50 05 50 05 50 05 50 05 00 55 55 00 00 55 55 00 00 50 05 00 00 50 05 00"))
    project.write_patch(0x75A600, bytes.fromhex("55 55 55 00 55 55 55 00 55 00 00 00 55 55 00 00 55 55 00 00 55 00 00 00 55 55 55 00 55 55 55 00"))
    project.write_patch(0x75A620, bytes.fromhex("40 44 44 04 40 44 44 04 44 00 00 44 44 00 00 44 44 00 00 44 44 00 00 44 40 44 44 04 40 44 44 04"))
    project.write_patch(0x75A640, bytes.fromhex("40 44 44 04 40 44 44 04 00 40 04 00 00 40 04 00 00 40 04 00 00 40 04 00 00 40 04 00 00 40 04 00"))
    project.write_patch(0x75A660, bytes.fromhex("00 FF FF 00 00 F0 0F 00 00 F0 0F 00 00 F0 0F 00 00 F0 0F 00 00 F0 0F 00 00 F0 0F 00 00 FF FF 00"))
    project.write_patch(0x75A680, bytes.fromhex("FF 00 00 FF FF 00 00 FF FF 0F 00 FF FF FF 00 FF FF F0 0F FF FF 00 FF FF FF 00 F0 FF FF 00 00 FF"))

    # ── Fase 5: Firma de Ñ Mode (Espacio Libre del Sistema) ──────────
    project.write_patch(0x0013AA24, b'N_MODE')

    # ── Fase 6: Parcheo de Font (Acentos y O) ───────────────────────
    # Esta fase corrige el offset de las mayúsculas, inserta la 'O' 
    # y añade las vocales con tilde (ÁÉÍÓÚ áéíóú)
    vowel_ids = apply_font_patch(project)

    # ── Fase 6: Días de la Semana (HUD Chunky) ─────────────────────
    # Cada día ocupa 3 tiles de 32 bytes (96 bytes total por día)
    
    # 1. Dom (0x75B040)
    project.write_patch(0x75B040, bytes.fromhex("11 11 11 00 11 00 11 02 11 00 11 02 11 00 11 02 11 00 11 02 11 00 11 02 11 11 11 02 20 22 22 02"))
    project.write_patch(0x75B060, bytes.fromhex("00 00 00 00 00 00 00 00 10 11 01 10 10 00 21 10 10 00 21 10 10 00 21 10 10 11 21 10 00 22 22 20"))
    project.write_patch(0x75B080, bytes.fromhex("00 00 00 00 00 00 00 00 01 11 10 21 01 11 10 21 01 11 10 21 01 11 10 21 01 11 10 21 02 22 20 02"))

    # 2. Lun (0x75B0A0)
    project.write_patch(0x75B0A0, bytes.fromhex("11 00 00 00 11 00 00 00 11 00 00 00 11 00 00 00 11 00 00 00 11 00 00 00 11 11 11 00 20 22 22 02"))
    project.write_patch(0x75B0C0, bytes.fromhex("00 00 00 00 00 00 00 00 11 00 11 10 11 00 11 12 11 00 11 12 11 00 11 12 11 11 11 12 20 22 22 20"))
    project.write_patch(0x75B0E0, bytes.fromhex("00 00 00 00 00 00 00 00 11 11 01 00 01 10 21 00 01 10 21 00 01 10 21 00 01 10 21 00 20 02 02 00"))

    # 3. Mar (0x75B100)
    project.write_patch(0x75B100, bytes.fromhex("11 11 10 11 11 10 10 11 11 00 00 11 11 00 00 11 11 00 00 11 11 00 00 11 11 00 00 11 22 00 00 22"))
    project.write_patch(0x75B120, bytes.fromhex("00 00 00 00 00 00 00 00 10 11 01 10 00 10 21 10 10 11 21 10 11 10 21 10 10 11 21 10 00 22 02 20"))
    project.write_patch(0x75B140, bytes.fromhex("00 00 00 00 00 00 00 00 11 01 00 00 11 00 00 00 11 00 00 00 11 00 00 00 11 00 00 00 22 00 00 00"))

    # 4. Mie (0x75B160)
    project.write_patch(0x75B160, bytes.fromhex("11 11 10 11 11 10 10 11 11 00 00 11 11 00 00 11 11 00 00 11 11 00 00 11 11 00 00 11 22 00 00 22"))
    project.write_patch(0x75B180, bytes.fromhex("00 00 00 00 10 21 00 00 00 00 00 00 10 21 10 10 10 21 10 11 10 21 10 00 10 21 00 11 20 02 00 02"))
    project.write_patch(0x75B1A0, bytes.fromhex("00 00 00 00 00 00 00 00 11 00 00 00 10 02 00 00 11 02 00 00 00 00 00 00 11 02 00 00 22 00 00 00"))

    # 5. Jue (0x75B1C0)
    project.write_patch(0x75B1C0, bytes.fromhex("00 10 11 01 00 00 10 21 00 00 10 21 00 00 10 21 11 00 10 21 11 00 10 21 10 11 11 00 00 22 22 00"))
    project.write_patch(0x75B1E0, bytes.fromhex("00 00 00 00 00 00 00 00 11 00 11 00 11 00 11 12 11 00 11 12 11 00 11 12 10 11 11 02 00 22 22 00"))
    project.write_patch(0x75B200, bytes.fromhex("00 00 00 00 00 00 00 00 11 11 00 00 01 10 02 00 11 11 02 00 01 00 00 00 10 11 02 00 00 22 00 00"))

    # 6. Vie (0x75B220)
    project.write_patch(0x75B220, bytes.fromhex("11 00 00 11 11 00 00 11 10 01 10 01 10 01 10 01 00 11 11 00 00 11 11 00 00 10 01 00 00 20 02 00"))
    project.write_patch(0x75B240, bytes.fromhex("00 00 00 00 10 21 00 00 00 00 11 11 10 21 01 10 10 21 11 11 10 21 01 00 10 21 10 11 20 02 00 22"))
    project.write_patch(0x75B260, bytes.fromhex("00 00 00 00 00 00 00 00 00 00 00 00 02 00 00 00 02 00 00 00 00 00 00 00 02 00 00 00 00 00 00 00"))

    # 7. Sab (0x75B280)
    project.write_patch(0x75B280, bytes.fromhex("10 11 10 00 11 00 10 21 11 00 00 00 10 11 00 00 00 00 11 21 11 00 10 21 10 11 10 00 00 22 22 00"))
    project.write_patch(0x75B2A0, bytes.fromhex("00 00 00 00 00 00 00 00 10 11 01 00 00 10 21 00 10 11 21 00 11 10 21 00 10 11 21 00 00 22 02 00"))
    project.write_patch(0x75B2C0, bytes.fromhex("11 00 00 00 11 00 00 00 11 11 01 00 11 00 11 02 11 00 11 02 11 00 11 02 11 11 01 00 20 22 02 00"))

    print("Soberanía de la Ñ v3.5 (Full Days HUD) instalada correctamente.")
    print(f"  Ñ: Font @ 0x{OFFSET_CB_TOP:08X}, UI Active (Fixed) @ 0x{OFFSET_N_MAJ_UI_2:08X}")
