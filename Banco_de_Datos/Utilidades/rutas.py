# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v4.0.0)
# "The Greatest Show"
# Desarrollado por: Denisovich728
# ============================================================
import os
import sys

def get_resource_path(relative_path):
    """
    Obtiene la ruta absoluta a un recurso, compatible con el entorno de desarrollo
    y con el ejecutable empaquetado por PyInstaller (onedir o onefile).
    """
    if os.path.isabs(relative_path) and os.path.exists(relative_path):
        return relative_path

    # 1. Modo congelado (PyInstaller): sys._MEIPASS (_internal)
    base_path = getattr(sys, '_MEIPASS', None)

    # 2. Si no estamos en _MEIPASS, usar la raíz del proyecto calculada dinámicamente
    if not base_path:
        # rutas.py está en: <root>/Banco_de_Datos/Utilidades/rutas.py (3 niveles arriba)
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    full_path = os.path.join(base_path, relative_path)
    if os.path.exists(full_path):
        return full_path

    # 3. Fallback en modo onedir: buscar junto al ejecutable (nivel raíz de dist)
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        alt_path = os.path.join(exe_dir, relative_path)
        if os.path.exists(alt_path):
            return alt_path

    return full_path

def get_data_path(game_mode, filename):
    """
    Acceso rápido a archivos dentro de Banco_de_Datos/Cilixes/
    game_mode debe ser 'fomt' o 'mfomt'
    """
    subfolder = "Mfomt" if game_mode.lower() == "mfomt" else "fomt"
    return get_resource_path(os.path.join("Banco_de_Datos", "Cilixes", subfolder, filename))

def get_app_root_dir() -> str:
    """
    Obtiene el directorio raíz de la aplicación de forma dinámica y 100% portable.
    - Si la aplicación está congelada (PyInstaller onedir o onefile), retorna la carpeta
      donde reside el ejecutable principal (.exe).
    - En entorno de desarrollo, retorna la raíz del repositorio.
    Alojar sesiones y proyectos en subdirectorios locales de la aplicación previene de raíz
    los bloqueos de 'Acceso controlado a carpetas' (Controlled Folder Access) de Windows Defender
    en la carpeta Mis Documentos.
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    # En desarrollo: 3 niveles arriba de Banco_de_Datos/Utilidades/rutas.py
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_documents_dir() -> str:
    """
    Obtiene de forma dinámica la ruta real al directorio de Documentos del usuario
    del sistema operativo, resolviendo variantes en español ('Documentos'),
    redirecciones a OneDrive o rutas personalizadas.
    """
    # 1. Intentar vía QStandardPaths si PyQt6 está disponible
    try:
        from PyQt6.QtCore import QStandardPaths
        docs = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        if docs and os.path.exists(docs):
            return os.path.normpath(docs)
    except Exception:
        pass

    # 2. En Windows, consultar API de Shell nativa (SHGetFolderPathW CSIDL_PERSONAL)
    if sys.platform == "win32":
        try:
            import ctypes
            import ctypes.wintypes
            CSIDL_PERSONAL = 5  # Mis Documentos
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            if ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, 0, buf) == 0:
                win_docs = buf.value
                if win_docs and os.path.exists(win_docs):
                    return os.path.normpath(win_docs)
        except Exception:
            pass

    # 3. Fallback dinámico sobre variables de entorno de usuario
    user_home = os.path.expanduser("~")
    for candidate in ["Documents", "Documentos"]:
        p = os.path.join(user_home, candidate)
        if os.path.exists(p):
            return p

    # 4. Fallback final: Directorio HOME del usuario
    return user_home

def get_default_workspace_dir() -> str:
    """
    Determina el directorio de trabajo por defecto para FoMT Studio de forma dinámica.
    Ubica el espacio de trabajo en un subdirectorio 'Workspace' dentro de la carpeta
    de la aplicación para máxima portabilidad y evitar bloqueos de Windows Defender
    en Mis Documentos.
    """
    # 1. Revisar si hay un default_project_dir configurado manualmente (que no sea Documentos)
    try:
        from Nucleo_Herramientas.config_manager import ConfigManager
        custom_dir = ConfigManager.get("default_project_dir")
        if custom_dir and os.path.isdir(custom_dir) and "Documents" not in custom_dir and "Documentos" not in custom_dir:
            return os.path.normpath(custom_dir)
    except Exception:
        pass

    # 2. Workspace local dentro del directorio de la aplicación
    workspace = os.path.join(get_app_root_dir(), "Workspace")
    os.makedirs(workspace, exist_ok=True)
    return os.path.normpath(workspace)

def get_sessions_dir() -> str:
    """
    Retorna la ruta dinámica hacia el directorio de sesiones de trabajo automáticas,
    alojado en un subdirectorio 'Sessions' directamente dentro de la carpeta de la
    aplicación. Esto elimina dependencias externas y bloqueos por permisos en Documents.
    """
    app_root = get_app_root_dir()
    sessions = os.path.join(app_root, "Sessions")
    os.makedirs(sessions, exist_ok=True)
    return os.path.normpath(sessions)

def get_config_file_path() -> str:
    """
    Retorna la ruta dinámica del archivo de configuración general fomt_config.json.
    Prioriza la raíz de la aplicación para evitar bloqueos por permisos.
    """
    # 1. En el directorio raíz de la aplicación
    app_root = get_app_root_dir()
    app_cfg = os.path.join(app_root, "fomt_config.json")
    if os.path.exists(app_cfg):
        return app_cfg

    # 2. En el workspace local
    ws_cfg = os.path.join(get_default_workspace_dir(), "fomt_config.json")
    if os.path.exists(ws_cfg):
        return ws_cfg

    # 3. En el directorio de trabajo actual
    cwd_cfg = os.path.join(os.getcwd(), "fomt_config.json")
    if os.path.exists(cwd_cfg):
        return cwd_cfg

    # Por defecto escribir junto al ejecutable/raíz
    return app_cfg

def resolve_project_fsp_path(target_path: str) -> str:
    """
    Resuelve dinámicamente la ruta a un archivo de proyecto .fsp cuando el usuario
    proporciona:
    - Una ruta directa a un archivo .fsp o .json.
    - Una carpeta de proyecto/sesión (busca el archivo .fsp interno).
    - Un nombre de sesión relativo (ej. 'Session_20261104_212050').
    Retorna la ruta absoluta normalizada o None si no se localiza.
    """
    if not target_path or not isinstance(target_path, str):
        return None

    target = os.path.normpath(target_path.strip('"\''))

    # Caso 1: Archivo directo existente (.fsp o .json)
    if os.path.isfile(target):
        if target.lower().endswith((".fsp", ".json")):
            return os.path.abspath(target)
        if target.lower().endswith(".gba"):
            # Si el usuario seleccionó source.gba dentro de la sesión, resolver el .fsp hermano
            parent_dir = os.path.dirname(target)
            sub_res = resolve_project_fsp_path(parent_dir)
            if sub_res:
                return sub_res

    # Caso 2: Es un directorio existente
    if os.path.isdir(target):
        # 2a. Buscar archivo con el mismo nombre de la carpeta: <nombre>.fsp
        dir_name = os.path.basename(target)
        named_fsp = os.path.join(target, f"{dir_name}.fsp")
        if os.path.isfile(named_fsp):
            return os.path.abspath(named_fsp)

        # 2b. Buscar cualquier archivo .fsp dentro de la carpeta
        try:
            candidates = [os.path.join(target, f) for f in os.listdir(target) if f.lower().endswith(".fsp")]
            if candidates:
                return os.path.abspath(candidates[0])
        except Exception:
            pass

        # 2c. Buscar cualquier archivo .json (excepto configuraciones)
        try:
            candidates = [
                os.path.join(target, f) for f in os.listdir(target) 
                if f.lower().endswith(".json") and "config" not in f.lower()
            ]
            if candidates:
                return os.path.abspath(candidates[0])
        except Exception:
            pass

    # Caso 3: Ruta sin extensión .fsp
    if os.path.isfile(target + ".fsp"):
        return os.path.abspath(target + ".fsp")

    # Caso 4: Nombre de sesión relativo dentro del directorio de sesiones local
    sessions_dir = get_sessions_dir()
    rel_path = os.path.join(sessions_dir, target)
    if os.path.isfile(rel_path):
        return os.path.abspath(rel_path)
    if os.path.isdir(rel_path):
        sub_resolve = resolve_project_fsp_path(rel_path)
        if sub_resolve:
            return sub_resolve
    if os.path.isfile(rel_path + ".fsp"):
        return os.path.abspath(rel_path + ".fsp")

    # Caso 5: Fallback secundario de compatibilidad en Documentos previo
    try:
        docs = get_documents_dir()
        old_sessions = os.path.join(docs, "FoMTStudio", "Sessions", target)
        if os.path.isfile(old_sessions):
            return os.path.abspath(old_sessions)
        if os.path.isdir(old_sessions):
            sub_res = resolve_project_fsp_path(old_sessions)
            if sub_res:
                return sub_res
        if os.path.isfile(old_sessions + ".fsp"):
            return os.path.abspath(old_sessions + ".fsp")
    except Exception:
        pass

    return None
