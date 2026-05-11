# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.1.0)
# "The Imposibility Update"
# Desarrollado por: Denisovich728
# ============================================================
import os
import sys

def get_resource_path(relative_path):
    """
    Obtiene la ruta absoluta a un recurso, compatible con el entorno de desarrollo
    y con el ejecutable empaquetado por PyInstaller.
    """
    try:
        # PyInstaller crea una carpeta temporal y guarda la ruta en _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # En desarrollo, usamos la raíz del proyecto (un nivel arriba de Nucleos_de_Procesamiento)
        # Si este archivo está en Nucleos_de_Procesamiento/Nucleo_de_Datos/Utilidades/rutas.py
        # subimos 4 niveles para llegar a la raíz.
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

    return os.path.join(base_path, relative_path)

def get_data_path(game_mode, filename):
    """
    Acceso rápido a archivos dentro de Nucleos_de_Procesamiento/Cilixes/
    game_mode debe ser 'fomt' o 'mfomt'
    """
    subfolder = "Mfomt" if game_mode.lower() == "mfomt" else "fomt"
    return get_resource_path(os.path.join("Nucleos_de_Procesamiento", "Cilixes", subfolder, filename))