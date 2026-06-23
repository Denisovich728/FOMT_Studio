import os

def aplicar_parche_cultivos(project):
    """
    Aplica el parche para hacer que todos los cultivos sean caminables y 
    corrige su Z-Sorting pasándolos a la capa BG2.
    """
    if not getattr(project, 'is_loaded', False) and not getattr(project, 'base_rom_path', None):
        raise Exception("Debes cargar un proyecto o ROM primero.")

    current_dir = os.path.dirname(os.path.abspath(__file__))
    payload_path = os.path.join(current_dir, "payload.bin")
    if not os.path.exists(payload_path):
        raise Exception("No se encuentra payload.bin en Banco_de_Datos/Parches/")
        
    with open(payload_path, 'rb') as f:
        payload = f.read()

    # 1. Código de Colisión (extraído del payload original de fomt_studio)
    crops_collision_code = payload[0x324 : 0x324+48]
    
    # 2. Asignar Espacio Dinámicamente para la colisión
    crops_addr = project.allocate_free_space(len(crops_collision_code))
    crops_ptr = crops_addr + 0x08000000 + 1 # +1 para THUMB
    
    import struct
    hook_crops = bytes([0x01, 0x49, 0x08, 0x47]) + struct.pack('<I', crops_ptr)

    # 3. Fix Visual Original de app.py
    visual_crops_code = bytes([
        0x24, 0x09, 0x07, 0x34, 0x1F, 0x25, 0x2C, 0x40, 
        0x46, 0x09, 0x2E, 0x40, 0xE6, 0x1A, 0x01, 0x36, 
        0x2E, 0x40, 0x04, 0x2E, 0x01, 0xDA
    ])

    # 4. Fix de Capa BG2 para evitar hojas rotas
    bg2_patch_crops = bytes([0x1A, 0x31])
    bg2_patch_turnips = bytes([0x1A, 0x30])

    try:
        # Inyectar Código Libre
        project.write_patch(crops_addr, crops_collision_code)
        
        # Inyectar Hook de Colisión
        project.write_patch(0x0A07C, hook_crops)
        
        # Inyectar Fix Visual en 0x07D5A4
        project.write_patch(0x07D5A4, visual_crops_code)
        
        # Inyectar Fix BG2
        project.write_patch(0x6EDFC, bg2_patch_crops)
        project.write_patch(0x6EDCC, bg2_patch_turnips)

        project.save()
        return True
    except Exception as e:
        raise Exception(f"Fallo al aplicar parche de cultivos:\n{e}")
