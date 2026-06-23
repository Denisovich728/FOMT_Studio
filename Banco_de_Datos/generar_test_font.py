import os

script_content = ["script TestFont {"]
for i in range(0x80, 0x100):
    hex_val = f"{i:02X}"
    script_content.append(f'    TalkMessage("ID 0x{hex_val}: \\x{hex_val}");')
script_content.append("}")

output_path = r"j:\Repositorios\fomt_studio\Banco_de_Datos\test_font.src"
with open(output_path, "w", encoding="utf-8") as f:
    f.write("\n".join(script_content) + "\n")

print(f"Archivo generado en: {output_path}")
