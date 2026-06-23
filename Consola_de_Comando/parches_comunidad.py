import os

def aplicar_parche_escaleras(project):
    """Inyecta el mapa y la rutina anti-softlock de escaleras usando repunteo dinámico."""
    if not project or not project.base_rom_data:
        return False, "No hay ROM cargada."
        
    rom = project.base_rom_data
    
    # 1. Comprobar si el hook ya fue aplicado (leyendo 0x09D150)
    hook_actual = rom[0x09D150:0x09D150+4]
    if hook_actual != bytearray([0x59, 0x49, 0x0A, 0x68]): 
        # LDR R1, [PC, #0x59] ya no está, probablemente ya tiene LDR R1, [PC] -> BX R1
        if hook_actual == bytearray([0x00, 0x49, 0x08, 0x47]):
            return False, "El parche de escaleras ya está instalado."
            
    # Datos a inyectar
    payload_path = os.path.join(os.path.dirname(__file__), "payload.bin")
    map_data = bytearray()
    if os.path.exists(payload_path):
        with open(payload_path, 'rb') as f:
            map_data = bytearray(f.read()[:692])
    else:
        return False, "No se encontró payload.bin."

    stairs_code = bytearray([
        21, 73, 136, 120, 0, 40, 1, 208, 20, 75, 0, 224, 18, 75, 28, 120, 50, 44, 26, 208, 0, 40, 1, 209, 17, 73, 0, 224, 17, 73, 18, 79, 0, 38, 1, 55, 203, 93, 4, 37, 43, 66, 10, 208, 0, 46, 4, 209, 1, 38, 1, 63, 2, 35, 203, 85, 1, 55, 203, 93, 251, 37, 43, 64, 203, 85, 1, 63, 2, 63, 0, 212, 235, 231, 12, 152, 13, 153, 8, 96, 13, 152, 6, 75, 24, 71, 0, 191, 248, 92, 0, 2, 252, 39, 0, 2, 52, 84, 0, 2, 104, 124, 0, 2, 30, 6, 0, 0, 89, 209, 9, 8
    ])

    total_size = len(map_data) + len(stairs_code) + 8 # +8 para padding
    free_space = project.gestor_memoria._find_free_space(total_size)
    
    # Inyectar Mapa
    rom[free_space : free_space+len(map_data)] = map_data
    map_ptr = free_space + 0x08000000
    
    # Inyectar Escaleras
    stairs_offset = free_space + len(map_data)
    if stairs_offset % 4 != 0: stairs_offset += 4 - (stairs_offset % 4)
    rom[stairs_offset : stairs_offset+len(stairs_code)] = stairs_code
    stairs_ptr = stairs_offset + 0x08000000 + 1

    # Repunteo Map Data Hook
    map_bytes = map_ptr.to_bytes(4, 'little')
    rom[0x000FE8 : 0x000FE8+4] = map_bytes
    rom[0x077990 : 0x077990+4] = map_bytes
    
    # Repunteo Stairs Hook (0x09D150)
    hook_stairs = bytearray([0x00, 0x49, 0x08, 0x47]) + stairs_ptr.to_bytes(4, 'little')
    rom[0x09D150 : 0x09D150+8] = hook_stairs
    
    return True, f"Parche instalado. Rutina alojada en 0x{free_space:06X}."

def aplicar_parche_cultivos(project):
    """Inyecta la rutina de cultivos traspasables y el parche visual."""
    if not project or not project.base_rom_data:
        return False, "No hay ROM cargada."
        
    rom = project.base_rom_data
    
    # Comprobar hook (leyendo 0x00A07C)
    if rom[0x00A07C:0x00A07C+4] == bytearray([0x00, 0x49, 0x08, 0x47]):
        return False, "El parche de cultivos ya está instalado."
        
    crops_collision_code = bytearray([
        0x10, 0xB5, 0x01, 0x68, 0x08, 0x05, 0x00, 0x0F, 0x01, 0x28, 0x06, 0xD9, 
        0x07, 0x28, 0x0B, 0xD8, 0x74, 0x46, 0x06, 0x4A, 0x94, 0x42, 0x07, 0xD0, 
        0x00, 0xE0, 0xC0, 0x06, 0x00, 0x0E, 0x14, 0x28, 0x02, 0xD0, 0x00, 0x20, 
        0x10, 0xBD, 0x00, 0x20, 0x10, 0xBD, 0x01, 0x20, 0x10, 0xBD, 0x34, 0x2A, 
        0x01, 0x08
    ])
    
    free_space = project.gestor_memoria._find_free_space(len(crops_collision_code))
    
    # Inyectar Crops Code
    rom[free_space : free_space+len(crops_collision_code)] = crops_collision_code
    crops_ptr = free_space + 0x08000000 + 1
    
    # Hook Crops Collision
    hook_crops = bytearray([0x00, 0x49, 0x08, 0x47]) + crops_ptr.to_bytes(4, 'little')
    rom[0x00A07C : 0x00A07C+8] = hook_crops
    
    # Visual Crops Patch
    visual_crops_code = bytearray([
        0x24, 0x09, 0x07, 0x34, 0x1F, 0x25, 0x2C, 0x40, 
        0x46, 0x09, 0x2E, 0x40, 0xE6, 0x1A, 0x01, 0x36, 
        0x2E, 0x40, 0x04, 0x2E, 0x01, 0xDA
    ])
    rom[0x07D5A4 : 0x07D5A4+len(visual_crops_code)] = visual_crops_code
    
    return True, f"Parche instalado. Rutina alojada en 0x{free_space:06X}."

def aplicar_parche_tp_stone(project):
    """Aplica un NOP para remover la restricción de año 3 para el Teleport Stone."""
    if not project or not project.base_rom_data:
        return False, "No hay ROM cargada."
        
    rom = project.base_rom_data
    
    # Comprobar si ya está parcheado
    if rom[0x09DBC2 : 0x09DBC2+2] == bytes.fromhex('c046'):
        return False, "El parche de Teleport Stone ya está instalado."
        
    rom[0x09DBC2 : 0x09DBC2+2] = bytes.fromhex('c046')
    return True, "Parche de Teleport Stone instalado. (Requisito Año 3 eliminado)"
