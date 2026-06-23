import os

def aplicar_parche_escaleras(project):
    """Aplica el parche anti-softlock y de escaleras visibles en la mina."""
    if not getattr(project, 'is_loaded', False) and not project.base_rom_path:
        raise Exception("Debes cargar un proyecto o ROM primero.")

    current_dir = os.path.dirname(os.path.abspath(__file__))
    payload_path = os.path.join(current_dir, "payload.bin")
    if not os.path.exists(payload_path):
        raise Exception("No se encuentra payload.bin en Banco_de_Datos/Parches/")
        
    with open(payload_path, 'rb') as f:
        map_data = f.read()[:692]

    stairs_code = bytes([21, 73, 136, 120, 0, 40, 1, 208, 20, 75, 0, 224, 18, 75, 28, 120, 50, 44, 26, 208, 0, 40, 1, 209, 17, 73, 0, 224, 17, 73, 18, 79, 0, 38, 1, 55, 203, 93, 4, 37, 43, 66, 10, 208, 0, 46, 4, 209, 1, 38, 1, 63, 2, 35, 203, 85, 1, 55, 203, 93, 251, 37, 43, 64, 203, 85, 1, 63, 2, 63, 0, 212, 235, 231, 12, 152, 13, 153, 8, 96, 13, 152, 6, 75, 24, 71, 0, 191, 248, 92, 0, 2, 252, 39, 0, 2, 52, 84, 0, 2, 104, 124, 0, 2, 30, 6, 0, 0, 89, 209, 9, 8])

    # Generar Map Data dinámicamente
    map_addr = project.allocate_free_space(len(map_data))
    map_ptr = map_addr + 0x08000000
    project.write_patch(map_addr, map_data)

    # Generar subrutina de escaleras dinámicamente
    stairs_addr = project.allocate_free_space(len(stairs_code))
    stairs_ptr = stairs_addr + 0x08000000 + 1 # +1 para THUMB mode
    project.write_patch(stairs_addr, stairs_code)
    
    # Generar Hook dinámicamente
    import struct
    hook_stairs = bytes([0x00, 0x49, 0x08, 0x47]) + struct.pack('<I', stairs_ptr)
    project.write_patch(0x09D150, hook_stairs)
    
    # Repuntear el mapa original
    project.write_patch(0x000FE8, struct.pack('<I', map_ptr))
    project.write_patch(0x077990, struct.pack('<I', map_ptr))

    project.save()
    return True
