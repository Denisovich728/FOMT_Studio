def aplicar_parche_teleport_stone(project):
    """
    Parche: Elimina el requerimiento del Año 3 para obtener la Piedra de Teletransporte.
    Dirección original: 0x0809DBC2
    Instrucción original: 01 27 (movs r7, #1)  -> Enciende bandera de rechazo
    Instrucción nueva: C0 46 (NOP)            -> Ignora el rechazo y permite el drop
    """
    if not project or not project.is_loaded:
        raise Exception("Debes cargar un proyecto o ROM primero.")

    try:
        # Inyectamos la instrucción NOP (0xC046 en little-endian) en 0x09DBC2
        nop_bytes = bytes.fromhex('c046')
        project.write_patch(0x09DBC2, nop_bytes)
        project.save()
        return True
    except Exception as e:
        raise Exception(f"Fallo al inyectar el parche de la Piedra de Teletransporte:\n{e}")
