import os
import re

ROOT_DIR = r"j:\Repositorios\fomt_studio"

MAPPINGS = [
    (r"fomt_studio\.core\.super_lib", "Nucleos_de_Procesamiento.Nucleo_de_Datos.super_lib"),
    (r"fomt_studio\.core\.project", "Nucleos_de_Procesamiento.Nucleo_de_Datos.proyecto"),
    (r"fomt_studio\.core\.parsers\.events", "Nucleos_de_Procesamiento.Nucleo_de_Eventos.eventos"),
    (r"fomt_studio\.core\.parsers\.npcs", "Nucleos_de_Procesamiento.Nucleo_de_Eventos.npcs"),
    (r"fomt_studio\.core\.parsers\.schedules", "Nucleos_de_Procesamiento.Nucleo_de_Eventos.horarios"),
    (r"fomt_studio\.core\.parsers\.tile_codec", "Nucleos_de_Procesamiento.Nucleo_de_Imagenes.codec_tiles"),
    (r"fomt_studio\.core\.parsers\.maps", "Nucleos_de_Procesamiento.Nucleo_de_Imagenes.mapas"),
    (r"fomt_studio\.core\.parsers\.items", "Nucleos_de_Procesamiento.Nucleo_de_Imagenes.objetos"),
    (r"fomt_studio\.core\.parsers\.shops", "Nucleos_de_Procesamiento.Nucleo_de_Imagenes.tiendas"),
    (r"fomt_studio\.gui\.i18n", "Perifericos.Traducciones.i18n"),
    (r"fomt_studio\.gui", "Perifericos.Interfaz_Usuario"),
    (r"from Perifericos.Interfaz_Usuario", "from Perifericos.Interfaz_Usuario"),
    (r"from Nucleos_de_Procesamiento.Nucleo_de_Datos", "from Nucleos_de_Procesamiento.Nucleo_de_Datos"),
]

def fix_imports(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    new_content = content
    for old, new in MAPPINGS:
        new_content = re.sub(old, new, new_content)
    
    if new_content != content:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Fixed: {file_path}")

for root, dirs, files in os.walk(ROOT_DIR):
    for file in files:
        if file.endswith(".py"):
            fix_imports(os.path.join(root, file))
