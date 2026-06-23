import os

def generate_menu():
    lines = []
    lines.append("script TestFontMenu {")
    lines.append("    var choice;")
    lines.append("")
    lines.append("label_start:")
    lines.append('    TalkMessage("=== MENU DEBUG DE FUENTE ===\\nElige una opcion:");')
    lines.append('    choice = TalkChoice6("Vista Agrupada 80-9F", "Vista Agrupada A0-BF", "Vista Agrupada C0-DF", "Vista Agrupada E0-FF", "Probar 1 a 1...", "Salir");')
    lines.append("")
    
    ranges = [
        (0x80, 0x9F, 0),
        (0xA0, 0xBF, 1),
        (0xC0, 0xDF, 2),
        (0xE0, 0xFF, 3)
    ]
    
    # Grupos grandes (opciones 0 a 3)
    for start, end, idx in ranges:
        lines.append(f"    if (choice == {idx}) {{")
        # 8 caracteres por mensaje (4 por linea)
        for chunk_start in range(start, end + 1, 8):
            msg = ""
            for i in range(chunk_start, min(chunk_start + 4, end + 1)):
                msg += f"{i:02X}:\\x{i:02X}  "
            msg = msg.strip() + "\\n"
            for i in range(chunk_start + 4, min(chunk_start + 8, end + 1)):
                msg += f"{i:02X}:\\x{i:02X}  "
            msg = msg.strip()
            lines.append(f'        TalkMessage("{msg}");')
        lines.append("        goto label_start;")
        lines.append("    }")

    # Submenu 1 a 1 (opcion 4)
    lines.append("    if (choice == 4) {")
    lines.append('        TalkMessage("Elija el rango para probar 1 a 1:");')
    lines.append('        choice = TalkChoice5("Rango 80-9F", "Rango A0-BF", "Rango C0-DF", "Rango E0-FF", "Volver");')
    
    for start, end, idx in ranges:
        lines.append(f"        if (choice == {idx}) {{")
        for i in range(start, end + 1):
            hex_val = f"{i:02X}"
            lines.append(f'            TalkMessage("Probando ID individual:\\nID 0x{hex_val} -> \\x{hex_val}");')
        lines.append("            goto label_start;")
        lines.append("        }")
    
    lines.append("        goto label_start;")
    lines.append("    }")
    
    # Salir (opcion 5)
    lines.append("    if (choice == 5) {")
    lines.append("        exit;")
    lines.append("    }")
    
    # Just in case indices are 1-based in some engine versions
    lines.append("    if (choice == 6) {")
    lines.append("        exit;")
    lines.append("    }")
    
    lines.append("    goto label_start;")
    lines.append("}")

    output_path = r"j:\Repositorios\fomt_studio\Banco_de_Datos\test_font.src"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Menu debug generado en: {output_path}")

if __name__ == "__main__":
    generate_menu()
