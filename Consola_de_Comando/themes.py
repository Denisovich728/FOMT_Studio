# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v4.0.0)
# "The Greatest Show - Final Release"
# Desarrollado por: Denisovich728
# ============================================================
# Sistema de temas basado en tokens de color.
#
# Cada tema define los mismos 12 colores con nombre (TOKENS). La hoja de
# estilo de cada tema se genera a partir de ellos, de modo que todos los
# widgets (combos, casillas, grupos, spin boxes, barras de progreso...)
# quedan cubiertos de forma coherente en los cinco temas.
#
# Para colorear un widget concreto, usar color("muted"), color("warning"),
# etc. en lugar de escribir un hex fijo: devuelve el color del tema activo.
#
# Botón principal de una pantalla:  boton.setProperty("variant", "primary")
# ============================================================
import os
import tempfile
from string import Template

DEFAULT_THEME = "forerunner"

TOKENS = {
    "forerunner": {
        "bg": "#050B15", "surface": "#0A192F", "surface_alt": "#0D2238", "border": "#1B5A72",
        "text": "#E0FBFF", "muted": "#7FC8D6", "accent": "#00E5FF", "accent_strong": "#00E5FF",
        "on_accent": "#050B15", "success": "#64FFDA", "warning": "#FFD166", "danger": "#FF7A8A",
    },
    "matrix": {
        "bg": "#000000", "surface": "#001000", "surface_alt": "#001A00", "border": "#0B6B22",
        "text": "#00FF41", "muted": "#2FBF55", "accent": "#00FF8C", "accent_strong": "#00FF41",
        "on_accent": "#000000", "success": "#7DFF9E", "warning": "#E2FF4D", "danger": "#FF5C5C",
    },
    "dark": {
        "bg": "#1E1E1E", "surface": "#252526", "surface_alt": "#2D2D2D", "border": "#3C3C3C",
        "text": "#D4D4D4", "muted": "#A0A0A0", "accent": "#4FA3FF", "accent_strong": "#0E639C",
        "on_accent": "#FFFFFF", "success": "#89D185", "warning": "#E9B949", "danger": "#F48771",
    },
    "light": {
        "bg": "#F3F3F3", "surface": "#FFFFFF", "surface_alt": "#E9E9E9", "border": "#C8C8C8",
        "text": "#1F1F1F", "muted": "#5F5F5F", "accent": "#005FB8", "accent_strong": "#005FB8",
        "on_accent": "#FFFFFF", "success": "#2E7D32", "warning": "#8A5A00", "danger": "#C62828",
    },
    "dracula": {
        "bg": "#282A36", "surface": "#21222C", "surface_alt": "#191A21", "border": "#44475A",
        "text": "#F8F8F2", "muted": "#A3ACD1", "accent": "#BD93F9", "accent_strong": "#BD93F9",
        "on_accent": "#282A36", "success": "#50FA7B", "warning": "#F1FA8C", "danger": "#FF6E6E",
    },
}

# Rasgos propios de cada tema que no son colores.
_STYLE = {
    "forerunner": {"font": "'Consolas', 'Segoe UI', sans-serif", "radius": "2px", "button_weight": "normal"},
    "matrix": {"font": "'Consolas', 'Courier New', monospace", "radius": "4px", "button_weight": "bold"},
    "dark": {"font": "'Segoe UI', Arial, sans-serif", "radius": "4px", "button_weight": "normal"},
    "light": {"font": "'Segoe UI', Arial, sans-serif", "radius": "4px", "button_weight": "normal"},
    "dracula": {"font": "'Segoe UI', 'Consolas', sans-serif", "radius": "4px", "button_weight": "bold"},
}

_QSS = Template("""
    QMainWindow, QDialog { background-color: $bg; color: $text; }
    QWidget { background-color: $bg; color: $text; font-family: $font; }

    QSplitter::handle { background-color: $border; }

    QMenuBar { background-color: $surface; color: $text; border-bottom: 1px solid $border; }
    QMenuBar::item:selected { background-color: $surface_alt; }
    QMenu { background-color: $surface; color: $text; border: 1px solid $border; }
    QMenu::item:selected { background-color: $surface_alt; color: $accent; }
    QMenu::item:disabled { color: $muted; }

    QToolBar { background-color: $surface; border-bottom: 1px solid $border; spacing: 4px; }
    QToolButton { background-color: transparent; color: $text; border: 1px solid transparent; border-radius: $radius; padding: 6px 10px; }
    QToolButton:hover { background-color: $surface_alt; border-color: $border; }
    QToolButton:pressed { background-color: $border; }
    QToolButton:checked { background-color: $surface_alt; border-color: $border; }
    QToolButton[variant="primary"] { background-color: $accent_strong; color: $on_accent; border-color: $accent_strong; font-weight: bold; }
    QToolButton[variant="primary"]:hover { border-color: $text; }
    QToolBar::separator { background: $border; width: 1px; margin: 6px 6px; }

    QPushButton#chipN { background-color: transparent; color: $warning; border: 1px solid $warning; border-radius: 12px; padding: 3px 12px; margin: 4px 10px 4px 0px; font-weight: bold; }
    QPushButton#chipN:hover { background-color: $surface_alt; color: $warning; border-color: $warning; }
    QPushButton#chipN:disabled { color: $muted; border-color: $border; }
    QPushButton#chipN[estado="activo"], QPushButton#chipN[estado="activo"]:disabled { color: $success; border-color: $success; }

    QTabWidget::pane { border: 1px solid $border; background-color: $bg; }
    QTabBar::tab { background: $surface; color: $muted; border: 1px solid $border; border-bottom: none; padding: 8px 14px; margin-right: 2px; border-top-left-radius: $radius; border-top-right-radius: $radius; }
    QTabBar::tab:hover { color: $text; }
    QTabBar::tab:selected { background: $bg; color: $text; border-bottom: 2px solid $accent; font-weight: bold; }
    QTabBar::close-button { image: url($close_icon); subcontrol-position: right; margin: 2px; border-radius: 3px; }
    QTabBar::close-button:hover { background-color: $surface_alt; image: url($close_icon_hover); }

    QTableView, QTreeView, QListView, QListWidget, QTableWidget, QTreeWidget {
        background-color: $surface; color: $text; border: 1px solid $border;
        gridline-color: $border; alternate-background-color: $surface_alt;
        selection-background-color: $surface_alt; selection-color: $accent;
    }
    QHeaderView::section { background-color: $surface_alt; color: $muted; padding: 4px; border: 1px solid $border; font-weight: bold; }

    QPushButton { background-color: $surface_alt; color: $text; border: 1px solid $border; padding: 6px 12px; border-radius: $radius; font-weight: $button_weight; }
    QPushButton:hover { border-color: $accent; color: $accent; }
    QPushButton:pressed { background-color: $border; }
    QPushButton:disabled { color: $muted; border-color: $border; }
    QPushButton[variant="primary"] { background-color: $accent_strong; color: $on_accent; border-color: $accent_strong; font-weight: bold; }
    QPushButton[variant="primary"]:hover { color: $on_accent; border-color: $text; }

    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
        background-color: $surface; color: $text; border: 1px solid $border; border-radius: $radius;
        padding: 3px 4px; selection-background-color: $accent_strong; selection-color: $on_accent;
    }
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: $accent; }
    QComboBox QAbstractItemView { background-color: $surface; color: $text; border: 1px solid $border; selection-background-color: $surface_alt; selection-color: $accent; }

    QCheckBox, QRadioButton { color: $text; spacing: 6px; background-color: transparent; }
    QCheckBox::indicator, QRadioButton::indicator { width: 14px; height: 14px; border: 1px solid $muted; background-color: $surface; }
    QCheckBox::indicator { border-radius: 3px; }
    QRadioButton::indicator { border-radius: 7px; }
    QCheckBox::indicator:checked, QRadioButton::indicator:checked { background-color: $accent; border-color: $accent; }

    QGroupBox { border: 1px solid $border; border-radius: $radius; margin-top: 14px; padding-top: 6px; }
    QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; color: $muted; font-weight: bold; }

    QProgressBar { border: 1px solid $border; border-radius: $radius; background-color: $surface; color: $text; text-align: center; }
    QProgressBar::chunk { background-color: $accent_strong; }

    QStatusBar { background-color: $surface; color: $text; border-top: 1px solid $border; }
    QToolTip { background-color: $surface; color: $text; border: 1px solid $accent; padding: 4px; }

    QScrollBar:vertical { border: none; background: $surface; width: 10px; margin: 0px; }
    QScrollBar::handle:vertical { background: $border; min-height: 24px; border-radius: 5px; }
    QScrollBar::handle:vertical:hover { background: $muted; }
    QScrollBar:horizontal { border: none; background: $surface; height: 10px; margin: 0px; }
    QScrollBar::handle:horizontal { background: $border; min-width: 24px; border-radius: 5px; }
    QScrollBar::handle:horizontal:hover { background: $muted; }
    QScrollBar::add-line, QScrollBar::sub-line { width: 0px; height: 0px; }
""")


_CLOSE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
    '<path d="M4.5 4.5l7 7M11.5 4.5l-7 7" stroke="{color}" stroke-width="1.6" stroke-linecap="round"/></svg>'
)


def _icon_path(name, color):
    """Escribe (una vez) un icono SVG del color pedido y devuelve su ruta para usarla en QSS."""
    folder = os.path.join(tempfile.gettempdir(), "fomt_studio_icons")
    path = os.path.join(folder, f"{name}_{color.lstrip('#').lower()}.svg")
    try:
        if not os.path.exists(path):
            os.makedirs(folder, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(_CLOSE_SVG.format(color=color))
    except OSError:
        return ""
    return path.replace("\\", "/")


def build_stylesheet(theme_name):
    """Genera la hoja de estilo Qt de un tema a partir de sus tokens."""
    name = theme_name if theme_name in TOKENS else "light"
    tokens = TOKENS[name]
    icons = {
        "close_icon": _icon_path("close", tokens["muted"]),
        "close_icon_hover": _icon_path("close", tokens["danger"]),
    }
    return _QSS.substitute(tokens, **_STYLE[name], **icons)


def active_theme_name():
    """Nombre del tema activo, tal como lo guarda la ventana principal."""
    try:
        from PyQt6.QtCore import QSettings
        name = QSettings("FoMTStudio", "ModdingSuite").value("theme", DEFAULT_THEME)
    except Exception:
        name = DEFAULT_THEME
    return name if name in TOKENS else "light"


def colors(theme_name=None):
    """Diccionario completo de tokens del tema indicado (o del activo)."""
    return dict(TOKENS[theme_name if theme_name in TOKENS else active_theme_name()])


def color(token, theme_name=None):
    """Color de un token ("muted", "warning", "accent"...) en el tema activo."""
    return colors(theme_name)[token]


def get_forerunner_theme():
    return build_stylesheet("forerunner")


def get_matrix_theme():
    return build_stylesheet("matrix")


def get_dark_theme():
    return build_stylesheet("dark")


def get_light_theme():
    return build_stylesheet("light")


def get_dracula_theme():
    return build_stylesheet("dracula")


def get_highlighter_colors(theme_name):
    if theme_name == "dracula":
        return {
            "command": "#ff79c6",
            "variable": "#50fa7b",
            "string": "#f1fa8c",
            "number": "#bd93f9",
            "comment": "#6272a4"
        }
    elif theme_name == "matrix":
        return {
            "command": "#00FF41",
            "variable": "#008F11",
            "string": "#00FF8C",
            "number": "#00A300",
            "comment": "#003B00"
        }
    elif theme_name == "dark":
        return {
            "command": "#569CD6",
            "variable": "#9CDCFE",
            "string": "#CE9178",
            "number": "#B5CEA8",
            "comment": "#6A9955"
        }
    elif theme_name == "forerunner":
        return {
            "command": "#00E5FF",
            "variable": "#00B8D4",
            "string": "#80DEEA",
            "number": "#B2EBF2",
            "comment": "#006064"
        }
    else: # Light
        return {
            "command": "#0000FF",
            "variable": "#001080",
            "string": "#A31515",
            "number": "#098658",
            "comment": "#008000"
        }
