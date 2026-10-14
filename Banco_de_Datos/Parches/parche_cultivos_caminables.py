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

    # 2. Renderizado de Cultivos Campo Principal (func_080AA6D0 @ 0x080AA6D0):
    # En 0x080AA748: ldr r1, [r7, #0x18] escribía la fila superior (Y-1) en la capa frontal
    # (BG1 / prioridad 1), dibujándose encima del sprite del jugador (OAM prioridad 2).
    # Al cambiar a 'ldr r1, [r7, #0x14]' (0x79, 0x69), la fila superior se dibuja en BG2 (prioridad 2).
    # En GBA, ante empate de prioridad (2 vs 2), los sprites siempre tienen prioridad sobre el BG,
    # por lo que el jugador se dibuja al frente y el cultivo no se superpone sobre él.
    patch_bg_main = bytes([0x79, 0x69])

    # 3. Renderizado de Cultivos Sub-parcelas (func_080CFEA8 @ 0x080CFEA8):
    # En 0x080CFF20: ldr r1, [r6, #0x18] -> cambiar a ldr r1, [r6, #0x14] (0x71, 0x69).
    patch_bg_sub = bytes([0x71, 0x69])

    try:
        # Inyectar mediante el sistema de parches del proyecto
        if hasattr(project, 'write_patch'):
            project.write_patch(0x00A07C, patch_collision)
            project.write_patch(0x0AA748, patch_bg_main)
            project.write_patch(0x0CFF20, patch_bg_sub)

        # Sincronizar buffer directo si es mutable
        if hasattr(project, 'base_rom_data') and isinstance(project.base_rom_data, bytearray):
            project.base_rom_data[0x00A07C : 0x00A07C + len(patch_collision)] = patch_collision
            project.base_rom_data[0x0AA748 : 0x0AA748 + len(patch_bg_main)] = patch_bg_main
            project.base_rom_data[0x0CFF20 : 0x0CFF20 + len(patch_bg_sub)] = patch_bg_sub

        if hasattr(project, 'save'):
            try:
                project.save()
            except Exception:
                pass
        return True
    except Exception as e:
        raise Exception(f"Fallo al aplicar parche de cultivos:\n{e}")


