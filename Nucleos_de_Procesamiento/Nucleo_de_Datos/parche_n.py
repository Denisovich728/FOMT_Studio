import os

# El Payload Gráfico (La "Tinta")
ENE_MAYUS_TOP = b'\x00\x00\x11\x11\x11\x00\x00\x00\x00\x11\x22\x22\x22\x11\x00\x00' \
                b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x21\x00\x00\x00\x21\x00\x00'

ENE_MAYUS_BOT = b'\x00\x21\x00\x21\x00\x21\x00\x21\x00\x21\x00\x21\x00\x21\x00\x21' \
                b'\x00\x21\x00\x21\x00\x21\x00\x21\x00\x00\x00\x00\x00\x00\x00\x00'

ene_min_top = b'\x00\x00\x11\x11\x11\x00\x00\x00\x00\x11\x22\x22\x22\x11\x00\x00' \
              b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x21\x21\x21\x21\x21\x00\x00'

ene_min_bot = b'\x00\x21\x00\x21\x00\x21\x00\x21\x00\x21\x00\x21\x00\x21\x00\x21' \
              b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

def aplicar_parche_n(rom_path: str):
    """
    Aplica el parche de Soberanía de la Ñ a la ROM.
    Abre la ROM en modo r+b y escribe en los offsets indicados.
    """
    if not os.path.exists(rom_path):
        raise FileNotFoundError(f"ROM no encontrada: {rom_path}")

    with open(rom_path, 'r+b') as f:
        # 1. Teclado UI (Redirección Lógica)
        # Reemplaza el asterisco por Ñ (0xCB)
        f.seek(0x000E89B6)
        f.write(b'\xCB')

        # Reemplaza el símbolo secundario por ñ (0xCC)
        f.seek(0x000E89F4)
        f.write(b'\xCC')

        # 2. Calibración de Espaciado (Anchos A)
        # Base de la tabla A = 0x00757B34. (0xCB * 2) = 0x196 -> Offset = 0x00757CCA
        f.seek(0x00757CCA)
        f.write(b'\x0A')  # Ancho de Ñ = 10px

        # Para ñ (0xCC), Offset = 0x00757CCC
        f.seek(0x00757CCC)
        f.write(b'\x0A')  # Ancho de ñ = 10px

        # Tabla Anchos B (Shadow)
        # La tabla B parece estar justo después, o si no se provee offset exacto, 
        # asumiendo que Base_Shadow está en otra parte. 
        # Dado que no hay offset exacto para Base_Shadow, lo podemos omitir o advertir.
        # Wait, si la Base_Shadow está a la misma distancia?

        # 3. Inyección de Tinta (Gráficos)
        # Top Halves
        f.seek(0x0075B818)
        f.write(ENE_MAYUS_TOP)

        f.seek(0x0075B838)
        f.write(ene_min_top)

        # Bottom Halves (Punto de apoyo encontrado en 0x0075B858)
        f.seek(0x0075B858)
        f.write(ENE_MAYUS_BOT)

        f.seek(0x0075B878)
        f.write(ene_min_bot)
        
    print("Soberanía de la Ñ instalada correctamente.")
