# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.1.0)
# "The Imposibility Update"
# Desarrollado por: Denisovich728
# ============================================================
import os
import struct
import sys

# Forzar encoding UTF-8 en consola de Windows si es posible
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def find_pointers_in_rom(rom_path, target_pointers):
    if not os.path.exists(rom_path):
        print(f"Error: No se encuentra la ROM en {rom_path}")
        return []

    with open(rom_path, "rb") as f:
        rom_data = f.read()

    results = []
    # Convertir punteros a bytes Little Endian
    pointer_bytes = {p: struct.pack("<I", p) for p in target_pointers}

    print(f"Escaneando ROM ({len(rom_data)} bytes) en busca de {len(target_pointers)} punteros...")

    # Escanear cada puntero en toda la ROM
    for p_val, p_bytes in pointer_bytes.items():
        start = 0
        while True:
            idx = rom_data.find(p_bytes, start)
            if idx == -1:
                break
            # Guardamos el offset absoluto (0x08000000 + idx) y el offset físico (idx)
            results.append({
                "Call_Offset_Phys": idx,
                "Call_Offset_GBA": idx + 0x08000000,
                "Pointer_Value": p_val,
                "Pointer_Hex": f"{p_val:08X}"
            })
            start = idx + 1
            
    return results

# Lista de punteros proporcionada por el usuario
targets = [
    0x080FB234, 0x080FB23C, 0x080FB27C, 0x080FB284, 0x080FB2CC, 0x080FB2F4,
    0x080FB300, 0x080FB308, 0x080FB394, 0x080FB3C8, 0x080FB420, 0x080FB46C,
    0x080FB480, 0x080FB4D4, 0x080FB51C, 0x080FB520, 0x080FB534, 0x080FB53C,
    0x080FB544, 0x080FB578, 0x080FB5D8, 0x080FB634, 0x080FB6A0, 0x080FB6C0,
    0x080FB710, 0x080FB738, 0x080FB754, 0x080FB7A0, 0x080FB7F0
]

rom_path = r"j:\Repositorios\fomt_studio\Modded_FoMT.gba"
findings = find_pointers_in_rom(rom_path, targets)

# Generar CSV
csv_path = r"j:\Repositorios\fomt_studio\Nucleos_de_Procesamiento\data\intro_pointers_audit.csv"
with open(csv_path, "w", encoding='utf-8') as f:
    f.write("Call_Offset_GBA,Call_Offset_Phys,Pointer_Target_GBA\n")
    for res in sorted(findings, key=lambda x: x['Call_Offset_Phys']):
        f.write(f"0x{res['Call_Offset_GBA']:08X},0x{res['Call_Offset_Phys']:08X},0x{res['Pointer_Hex']}\n")

print(f"Auditoria completada. Se encontraron {len(findings)} llamadas.")
print(f"Archivo generado: {csv_path}")