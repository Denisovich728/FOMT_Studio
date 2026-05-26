import os
import struct

def validar_e_inyectar_splash(project):
    """
    Validación de seguridad crítica: el sistema entero depende de que el logo (Cilixes)
    esté inyectado apenas se abre la ROM. Si el archivo no existe, la inicialización debe fallar.
    """
    # Si el proyecto se inicializa desde una carpeta temporal (por ejemplo, app init),
    # el project_dir podría estar vacío o apuntar a la sesión. El asset debe estar en la carpeta fuente.
    # Como la estructura es fija, intentamos localizar el asset usando rutas relativas robustas.
    
    from Nucleos_de_Procesamiento.Nucleo_de_Datos.Utilidades.rutas import get_resource_path
    
    asset_path = get_resource_path(os.path.join(
        "Nucleos_de_Procesamiento",
        "Nucleo_de_Datos",
        "assets",
        "splash_logo.bin"
    ))
    
    if not os.path.exists(asset_path):
        raise RuntimeError(
            f"[CRITICAL ERROR] Sistema de Control de Integridad: Falta el archivo obligatorio '{asset_path}'. "
            "No se puede abrir la sesión de modificación de FoMT sin la firma obligatoria."
        )
        
    with open(asset_path, "rb") as f:
        splash_data = f.read()
        
    # Verificar la FIRMA EXCLUSIVA en el espacio libre para saber si ya se inyectó.
    # Usaremos 0x0013AA2C (justo después del 'N_MODE' del parche_n)
    SIGNATURE_OFFSET = 0x0013AA2C
    SIGNATURE_BYTES = b'CILIXES'
    
    current_sig = project.virtual_rom[SIGNATURE_OFFSET : SIGNATURE_OFFSET + len(SIGNATURE_BYTES)]
    
    if current_sig == SIGNATURE_BYTES:
        print("[Splash Enforcer] Firma 'CILIXES' detectada. La ROM ya tiene el logo inyectado.")
        return True

    # 1. Asignar memoria libre
    new_offset = project.allocate_free_space(len(splash_data))
    
    # 2. Inyectar gráficos en virtual_rom (para que persistatn en toda la sesión)
    project.write_patch(new_offset, splash_data)
    
    # 3. Redirigir los punteros reales del booteo (Natsume Logo)
    new_pointer_gba = new_offset | 0x08000000
    
    ptr_bytes = struct.pack("<I", new_pointer_gba)
    project.write_patch(0xFE8, ptr_bytes)
    project.write_patch(0x77990, ptr_bytes)
    
    # 4. Inyectar la paleta (splash.pal)
    pal_path = get_resource_path(os.path.join("Nucleos_de_Procesamiento", "Nucleo_de_Datos", "assets", "splash.pal"))
    if os.path.exists(pal_path):
        with open(pal_path, "rb") as f:
            pal_data = f.read()
            
        pal_offset = project.allocate_free_space(len(pal_data))
        project.write_patch(pal_offset, pal_data)
        
        new_pal_gba = pal_offset | 0x08000000
        pal_ptr_bytes = struct.pack("<I", new_pal_gba)
        
        # Redirigir los verdaderos punteros de la paleta (descubiertos junto al logo)
        project.write_patch(0xFEC, pal_ptr_bytes)
        project.write_patch(0x77998, pal_ptr_bytes)
    
    # 5. Escribir la firma para no volver a inyectar a cada rato
    project.write_patch(SIGNATURE_OFFSET, SIGNATURE_BYTES)
    
    print(f"[Splash Enforcer] Integridad validada. Logo inyectado en 0x{new_offset:08X} y firmado con 'CILIXES'.")
    return True
