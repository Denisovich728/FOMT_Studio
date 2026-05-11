# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.1.0)
# "The Imposibility Update"
# Desarrollado por: Denisovich728
# ============================================================
import os
import sys

def patch_pregnant_typo(rom_path: str):
    """
    Parche In-Place (Obligatorio) para corregir el typo de 'prengant' en el Evento 0001
    sin corromper el offset final (usando null-padding).
    """
    if not os.path.exists(rom_path):
        print(f"Error: ROM no encontrada en {rom_path}")
        return False
        
    try:
        with open(rom_path, 'rb') as f:
            rom_data = bytearray(f.read())
            
        # Secuencia a buscar (asumiendo codificación ASCII estándar del juego)
        # "\xFF%is \r\nprengant!\x05"
        # Bytes: FF 25 69 73 20 0D 0A 70 72 65 6E 67 61 6E 74 21 05
        target = b'\xff%is \r\nprengant!\x05'
        replacement = b'\xff%is \r\npregnant!\x00\x05'
        
        idx = rom_data.find(target)
        if idx != -1:
            print(f"[*] Typo 'prengant' encontrado en el offset: 0x{idx:06X}")
            print(f"[*] Aplicando parche hex In-Place sin alterar tamaño...")
            
            # Reemplazo estricto (misma longitud de 17 bytes)
            assert len(target) == len(replacement), "Error crítico: El parche In-Place altera el tamaño del string."
            rom_data[idx:idx+len(replacement)] = replacement
            
            patched_path = rom_path.replace('.gba', '_patched.gba')
            if '.gba' not in rom_path.lower():
                patched_path = rom_path + '_patched.gba'
                
            with open(patched_path, 'wb') as f:
                f.write(rom_data)
                
            print(f"[+] ROM parcheada guardada exitosamente en: {patched_path}")
            return patched_path
        else:
            print("[-] No se encontró el typo 'prengant' en esta ROM. ¿Quizás ya está parcheada?")
            return False
            
    except Exception as e:
        print(f"Error durante el parcheo: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m SlipSpace_Engine.utility.patcher <rom.gba>")
    else:
        patch_pregnant_typo(sys.argv[1])