# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v4.1.0)
# "The Greatest Show - Final Release"
# Desarrollado por: Denisovich728
# ============================================================
from Banco_de_Datos.parche_font import apply_font_patch, CHARMAP_ES

# ============================================================================
# SOBERANÍA ROMANCE (ES/PT/FR/IT) - Inyector Unificado
# ============================================================================
# Fases activas (sin colisiones de offsets):
#   1. Teclado Naming Screen: Reasignar teclas ♀/♂ (0xB6/0xB7) -> ñ/Ñ (0xCA/0xD1)
#   2. Iconos UI Naming Screen: Actualizar bitmaps 8x12 en 0x117B44 (ñ) y 0x117B50 (Ñ)
#   3. Fuente 1-Byte (0x4F90CC): Desplazamiento +1px Y global + 28 glifos Romance (0xC4..0xDD + 0xAD..0xAE)
#   4. Gráficos HUD/Etiquetas (0x75A5A0..0x75A69F): Marcos y elementos de interfaz
#   5. Días de la Semana HUD 4bpp (0x75B040..0x75B2DF): Dom, Lun, Mar, Mie, Jue, Vie, Sab
#   6. Firma de sistema: Marcar flag N_MODE en 0x0013AA24
# ============================================================================

# Iconos 8x12 1bpp de la pantalla de nombres (reemplazan ♀ y ♂ en el teclado)
OFFSET_N_MIN_UI_2 = 0x117B44
OFFSET_N_MAJ_UI_2 = 0x117B50

BYTES_N_MIN_UI = bytes([0x00, 0x28, 0x50, 0x00, 0x78, 0x44, 0x44, 0x44, 0x44, 0x44, 0x44, 0x00])
BYTES_N_MAJ_UI = bytes([0x28, 0x50, 0x00, 0x44, 0x44, 0x64, 0x54, 0x54, 0x4C, 0x4C, 0x44, 0x00])


def aplicar_parche_n(project):
    """
    Aplica el parche completo de localización Romance sobre el proyecto ROM.
    Retorna el diccionario de equivalencias {carácter: byte_id} para el inyector.
    """
    if not project or not project.base_rom_path:
        raise ValueError("Proyecto no válido o ROM base no encontrada.")

    # ── Fase 1: Teclado Naming Screen (Redirección Lógica a 0xCA / 0xD1) ──
    # 0x0E89ED tenía 0xB6 (♀) -> ahora apunta a 0xCA (ñ)
    project.write_patch(0x000E89ED, bytes([CHARMAP_ES["ñ"]]))
    # 0x0E89EF tenía 0xB7 (♂) -> ahora apunta a 0xD1 (Ñ)
    project.write_patch(0x000E89EF, bytes([CHARMAP_ES["Ñ"]]))

    # ── Fase 2: Iconos Visuales del Teclado Naming Screen (8x12 1bpp) ─────
    project.write_patch(OFFSET_N_MIN_UI_2, BYTES_N_MIN_UI)
    project.write_patch(OFFSET_N_MAJ_UI_2, BYTES_N_MAJ_UI)

    # ── Fase 3: Fuente Principal 1-Byte (Desplazamiento + 28 Glifos Romance) ─
    char_ids = apply_font_patch(project)

    # ── Fase 4: Gráficos de Interfaz (HUD/Etiquetas 4bpp) ─────────────────
    project.write_patch(0x75A5A0, bytes.fromhex("B0 BB BB 00 B0 0B B0 0B B0 0B B0 0B B0 0B B0 0B B0 BB BB 00 B0 0B 00 00 B0 0B 00 00 B0 0B 00 00"))
    project.write_patch(0x75A5C0, bytes.fromhex("B0 BB BB 00 B0 0B B0 0B B0 0B B0 0B B0 0B B0 0B B0 BB BB 00 B0 0B BB 00 B0 0B B0 0B B0 0B B0 BB"))
    project.write_patch(0x75A5E0, bytes.fromhex("55 00 00 55 55 00 00 55 50 05 50 05 50 05 50 05 00 55 55 00 00 55 55 00 00 50 05 00 00 50 05 00"))
    project.write_patch(0x75A600, bytes.fromhex("55 55 55 00 55 55 55 00 55 00 00 00 55 55 00 00 55 55 00 00 55 00 00 00 55 55 55 00 55 55 55 00"))
    project.write_patch(0x75A620, bytes.fromhex("40 44 44 04 40 44 44 04 44 00 00 44 44 00 00 44 44 00 00 44 44 00 00 44 40 44 44 04 40 44 44 04"))
    project.write_patch(0x75A640, bytes.fromhex("40 44 44 04 40 44 44 04 00 40 04 00 00 40 04 00 00 40 04 00 00 40 04 00 00 40 04 00 00 40 04 00"))
    project.write_patch(0x75A660, bytes.fromhex("00 FF FF 00 00 F0 0F 00 00 F0 0F 00 00 F0 0F 00 00 F0 0F 00 00 F0 0F 00 00 F0 0F 00 00 FF FF 00"))
    project.write_patch(0x75A680, bytes.fromhex("FF 00 00 FF FF 00 00 FF FF 0F 00 FF FF FF 00 FF FF F0 0F FF FF 00 FF FF FF 00 F0 FF FF 00 00 FF"))

    # ── Fase 5: Días de la Semana (HUD Chunky 4bpp - sin colisiones) ──────
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

    # ── Fase 6: Firma de N_MODE (Espacio Libre del Sistema) ───────────────
    project.write_patch(0x0013AA24, b"N_MODE")

    print("Soberanía Romance v4.1 instalada (Teclado + Fuente 1bpp 28 glifos + HUD Días).")
    return char_ids