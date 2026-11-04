import os

def aplicar_parche_cultivos(project):
    """
    Aplica el parche nativo para hacer que todos los cultivos sean caminables y 
    corrige el renderizado de capas (Z-Sorting), redirigiendo la fila superior
    de cultivos a BG2 para evitar cualquier superposición sobre el jugador.
    """
    if not getattr(project, 'is_loaded', False) and not getattr(project, 'base_rom_path', None) and not getattr(project, 'virtual_rom', None):
        raise Exception("Debes cargar un proyecto o ROM primero.")

    # 1. Colisión de Cultivos (func_0800A07C @ 0x0800A07C):
    # En la ROM original, evalúa el crecimiento del cultivo y devuelve 1 (sólido) para etapas 2-8.
    # Al retornar 0 inmediatamente ('movs r0, #0; bx lr' -> 0x00, 0x20, 0x70, 0x47),
    # todos los evaluadores de mapa dejan el bit 0 de colisión en 0 (caminable).
    patch_collision = bytes([0x00, 0x20, 0x70, 0x47])

    # 2. Renderizado de Cultivos y Z-Sorting en Hardware VRAM Compositor:
    # 0x06EDCC: adds r0, #0x1a (1a 30) en vez de #0x1c (cambia base de screenblock a 0x1A)
    # 0x06EDFC: adds r1, #0x1a (1a 31) en vez de #0x18 (cambia base de screenblock a 0x1A)
    bg2_patch_turnips = bytes([0x1A, 0x30])
    bg2_patch_crops = bytes([0x1A, 0x31])

    # Revertir offsets 0x0AA748 y 0x0CFF20 a sus valores canónicos para prevenir crashes de memoria al warpear
    revert_bg_main = bytes([0xB9, 0x69])
    revert_bg_sub = bytes([0xB1, 0x69])

    try:
        # Inyectar mediante el sistema de parches del proyecto
        if hasattr(project, 'write_patch'):
            project.write_patch(0x00A07C, patch_collision)
            project.write_patch(0x06EDCC, bg2_patch_turnips)
            project.write_patch(0x06EDFC, bg2_patch_crops)
            project.write_patch(0x0AA748, revert_bg_main)
            project.write_patch(0x0CFF20, revert_bg_sub)

        # Sincronizar buffer directo si es mutable
        if hasattr(project, 'base_rom_data') and isinstance(project.base_rom_data, bytearray):
            project.base_rom_data[0x00A07C : 0x00A07C + len(patch_collision)] = patch_collision
            project.base_rom_data[0x06EDCC : 0x06EDCC + len(bg2_patch_turnips)] = bg2_patch_turnips
            project.base_rom_data[0x06EDFC : 0x06EDFC + len(bg2_patch_crops)] = bg2_patch_crops
            project.base_rom_data[0x0AA748 : 0x0AA748 + len(revert_bg_main)] = revert_bg_main
            project.base_rom_data[0x0CFF20 : 0x0CFF20 + len(revert_bg_sub)] = revert_bg_sub

        if hasattr(project, 'save'):
            try:
                project.save()
            except Exception:
                pass

        if hasattr(project, 'save_rom'):
            try:
                project.save_rom()
            except Exception:
                pass
        return True
    except Exception as e:
        raise Exception(f"Fallo al aplicar parche de cultivos:\n{e}")


