# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.1.0)
# "The Imposibility Update"
# Desarrollado por: Denisovich728
# ============================================================
import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame, QHBoxLayout, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt
from Perifericos.Traducciones.i18n import tr

class VisualEventMaker(QWidget):
    """
    VisualEventMaker proporciona una representación visual en formato "RPG Maker XP".
    Traduce el C++ puro extraído del Engine SlipSpace_Engine a bloques apilados,
    usando colores semánticos pedidos por el usuario.
    """
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.current_event = None
        self.lang = getattr(parent, 'current_lang', 'es') if parent else 'es'
        self.setup_ui()
        
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        lang = self.lang
        
        self.lbl_title = QLabel(f"<h3>{tr('vis_title_none', lang)}</h3>")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.lbl_title)
        
        # Area scrolleable donde apilaremos los "bloques"
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background-color: #f0f0f0;")
        
        self.block_container = QWidget()
        self.block_layout = QVBoxLayout(self.block_container)
        self.block_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.block_container)
        main_layout.addWidget(self.scroll_area)
        
    def load_statements(self, event_id, stmts):
        """
        Recibe la lista AST 'stmts' desde app.py.
        Para mayor solidez, volveremos a formatearlos con format_script y parsearemos sus strings
        para convertirlos en bloques visuales 2D.
        """
        self.current_event = event_id
        
        # Limpiar canvas
        for i in reversed(range(self.block_layout.count())): 
            widget = self.block_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
                
        # Dependemos de fomt_studio.core.parsers.SlipSpace_Script_Engine.decompiler.formatter para el text-pass
        try:
            from fomt_studio.core.parsers.SlipSpace_Script_Engine.decompiler.formatter import format_script
            c_code = format_script(stmts)
        except Exception as e:
            err = QLabel(f"Error generando visual: {e}")
            self.block_layout.addWidget(err)
            return

        lang = getattr(self.window(), 'current_lang', 'es')
        hint_name = self.project.super_lib.get_event_name_hint(event_id)
        # Standardized naming for the visual title
        self.lbl_title.setText(f"<h3>{tr('vis_title_flow', lang).format(id=event_id, name=f'Script {event_id:04d}')}</h3>")

        identation_lvl = 0
        
        for line in c_code.splitlines():
            line = line.strip()
            if not line or line == "{" or line == "}":
                continue
                
            color_hex, bold, title, content = self._parse_line_color(line)
            
            # Crear Bloque RPG Maker Style
            frame = QFrame()
            frame.setObjectName("BlockFrame")
            frame.setStyleSheet(f"""
                QFrame#BlockFrame {{
                    background-color: {color_hex};
                    border: 1px solid #777;
                    border-radius: 6px;
                    margin: 2px {40 - (identation_lvl * 5)}px 2px {identation_lvl * 25}px;
                }}
            """)
            
            f_layout = QHBoxLayout(frame)
            f_layout.setContentsMargins(10, 8, 10, 8)
            
            bl_icon = QLabel(f"<b>{title}:</b>")
            bl_icon.setStyleSheet("color: #111;" if bold else "color: #222;")
            
            bl_text = QLabel(content)
            bl_text.setStyleSheet("color: #111; font-weight: bold;" if bold else "color: #333;")
            bl_text.setWordWrap(True)
            
            f_layout.addWidget(bl_icon)
            f_layout.addWidget(bl_text)
            f_layout.addStretch()
            
            self.block_layout.addWidget(frame)
            
    def _parse_line_color(self, text):
        lang = self.lang
        
        # Textos / Dialogos (Caja Verde)
        if "Message" in text or "msg_" in text or text.startswith('"'):
            return ("#a5d6a7", False, f"[{tr('vis_dialog', lang)}]", text) 
            
        # Variables Globales / Flags / If (Caja Morada)
        if "var_" in text or "flag_" in text or "unk_" in text or text.startswith("if "):
            return ("#ce93d8", True, f"[{tr('vis_cond', lang)}]", text) 
            
        # Saltos (Gotos) / Label / Script Jumps (Naranja)
        if text.startswith("goto ") or "Label_" in text or text.startswith("CallCode") or "Jump" in text:
            return ("#ffcc80", True, f"[{tr('vis_jump', lang)}]", text) 
            
        # Comandos Especiales End, Exit, Return (Amarillo)
        if text == "Exit()" or text == "Return()" or "Branch" in text:
            return ("#fff59d", True, f"[{tr('vis_flow', lang)}]", text) 
            
        # Standard Opcodes y Llamadas C++ (Azul)
        if "(" in text and ")" in text:
            # extraer el nombre de la funciòn
            func_name = text.split("(")[0]
            return ("#90caf9", False, f"[{tr('vis_module', lang)}: {func_name}]", text) 
            
        # Default o Asignaciones
        return ("#e0e0e0", False, f"[{tr('vis_generic', lang)}]", text) 