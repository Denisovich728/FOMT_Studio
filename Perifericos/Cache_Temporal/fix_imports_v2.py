# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.1.0)
# "The Imposibility Update"
# Desarrollado por: Denisovich728
# ============================================================
import os
import re

ROOT_DIR = r"j:\Repositorios\fomt_studio"

MAPPINGS = [
    (r"from fomt_studio\.core\.utils\.compression import decompress_lz10", "from Nucleos_de_Procesamiento.Nucleo_de_Datos.Utilidades.compresion import decompress_lz10"),
    (r"from fomt_studio\.core\.utils\.popuri_unpacker import popuri_unpack", "from Nucleos_de_Procesamiento.Nucleo_de_Datos.Utilidades.desempaquetado_popuri import popuri_unpack"),
    (r"from fomt_studio\.core\.memory_manager import MemoryManager", "from Nucleos_de_Procesamiento.Nucleo_de_Datos.gestor_memoria import MemoryManager"),
    # General catch-all for anything missed
    (r"fomt_studio\.core\.utils", "Nucleos_de_Procesamiento.Nucleo_de_Datos.Utilidades"),
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