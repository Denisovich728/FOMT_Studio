# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.6.5)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QCheckBox, QPushButton, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt

class DecorationControlDialog(QDialog):
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.setWindowTitle("Panel de Control de Decorados")
        self.setFixedSize(300, 250)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        self.settings = settings or {
            "strings": True,
            "items": True,
            "characters": True,
            "flags": True,
            "coords": True
        }
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("<b>Configuración de Descompilación Inteligente</b>"))
        layout.addWidget(QLabel("<small>Selecciona qué elementos se deben decorar en el código:</small>"))
        
        self.chk_strings = QCheckBox("Mensajes (const MESSAGE_X)")
        self.chk_items = QCheckBox("Nombres de Ítems / Herramientas")
        self.chk_chars = QCheckBox("Nombres de NPCs / Candidatas")
        self.chk_flags = QCheckBox("Nombres de Flags (Banderas)")
        self.chk_coords = QCheckBox("Etiquetas de Coordenadas (Pos_X/Y)")
        
        self.chk_strings.setChecked(self.settings.get("strings", True))
        self.chk_items.setChecked(self.settings.get("items", True))
        self.chk_chars.setChecked(self.settings.get("characters", True))
        self.chk_flags.setChecked(self.settings.get("flags", True))
        self.chk_coords.setChecked(self.settings.get("coords", True))
        
        layout.addWidget(self.chk_strings)
        layout.addWidget(self.chk_items)
        layout.addWidget(self.chk_chars)
        layout.addWidget(self.chk_flags)
        layout.addWidget(self.chk_coords)
        
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        self.btn_apply = QPushButton("Aplicar Cambios")
        self.btn_apply.clicked.connect(self.accept)
        self.btn_apply.setStyleSheet("background-color: #2E86C1; color: white; font-weight: bold; padding: 5px;")
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_apply)
        layout.addLayout(btn_layout)

    def get_settings(self):
        return {
            "strings": self.chk_strings.isChecked(),
            "items": self.chk_items.isChecked(),
            "characters": self.chk_chars.isChecked(),
            "flags": self.chk_flags.isChecked(),
            "coords": self.chk_coords.isChecked()
        }
