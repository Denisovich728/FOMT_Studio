# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v4.0.0)
# Sistema Internacionalizacion (i18n) - Formato JSON Utilitario
# Desarrollado por: Denisovich728
# ============================================================
import os
import json

_JSON_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "i18n.json")

def _load_translations() -> dict:
    if os.path.exists(_JSON_FILE):
        try:
            with open(_JSON_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[i18n] Error al cargar {_JSON_FILE}: {e}")
    return {}

# Diccionario maestro cargado desde JSON (compatible con consumo legado)
TRANSLATIONS = _load_translations()

def reload_translations():
    """Recarga en caliente las cadenas de traduccion desde el archivo JSON."""
    global TRANSLATIONS
    TRANSLATIONS = _load_translations()
    return TRANSLATIONS

def get_available_languages() -> list:
    """Devuelve la lista de codigos de idioma disponibles."""
    return list(TRANSLATIONS.keys())

def tr(key: str, lang: str = "es") -> str:
    """
    Traduce una clave al idioma especificado con fallback a espanol y a la clave misma.
    Jerga formal, utilitarismo puro y sin modismos.
    """
    lang_dict = TRANSLATIONS.get(lang, TRANSLATIONS.get("es", {}))
    if key in lang_dict:
        return lang_dict[key]
    # Fallback a espanol
    es_dict = TRANSLATIONS.get("es", {})
    return es_dict.get(key, key)

def active_lang(fallback: str = "es") -> str:
    """Idioma activo de la aplicacion, tal como lo guarda la ventana principal."""
    try:
        from PyQt6.QtCore import QSettings
        return QSettings("FoMTStudio", "ModdingSuite").value("language", fallback)
    except Exception:
        return fallback

def t(key: str, **kwargs) -> str:
    """
    Traduce una clave con el idioma activo y rellena los huecos {nombre}.
    Util en widgets creados sin ventana padre, donde no hay current_lang.
    """
    text = tr(key, active_lang())
    return text.format(**kwargs) if kwargs else text

def get_lang_from_widget(widget, fallback="es") -> str:
    """Obtiene el codigo de idioma actual inspeccionando la jerarquia de widgets Qt."""
    p = widget
    while p:
        if hasattr(p, 'current_lang'):
            return p.current_lang
        if hasattr(p, 'window') and hasattr(p.window, 'current_lang'):
            return p.window.current_lang
        try:
            p = p.parent()
        except Exception:
            break
    return fallback
