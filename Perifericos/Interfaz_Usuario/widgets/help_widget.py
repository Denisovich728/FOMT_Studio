# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.6.5)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView
from PyQt6.QtCore import Qt
from Perifericos.Traducciones.i18n import tr

class HelpWidget(QWidget):
    """
    Pestaña de Ayuda y Atajos.
    Muestra una tabla con los comandos rápidos del programa.
    """
    def __init__(self, main_window):
        super().__init__()
        self.window = main_window
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Título
        self.lbl_title = QLabel(f"<h1>{tr('help_title', self.window.current_lang)}</h1>")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_title)

        # Descripción
        self.lbl_desc = QLabel(tr('help_desc', self.window.current_lang))
        self.lbl_desc.setStyleSheet("font-size: 14px; color: #aaa;")
        self.lbl_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_desc)

        # Tabla de Atajos
        self.table = QTableWidget(6, 2)
        self.table.setHorizontalHeaderLabels(["Comando", "Acción"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setStyleSheet("""
            QTableWidget { background-color: #1a1a1a; gridline-color: #333; color: white; border-radius: 8px; }
            QHeaderView::section { background-color: #333; color: #00ff00; padding: 5px; border: none; font-weight: bold; }
        """)

        self.refresh_translations()
        layout.addWidget(self.table)
        
        layout.addStretch()

    def refresh_translations(self):
        lang = self.window.current_lang
        self.lbl_title.setText(f"<h1>{tr('help_title', lang)}</h1>")
        self.lbl_desc.setText(tr('help_desc', lang))
        
        shortcuts = [
            ("Ctrl + P", tr('key_event_up', lang)),
            ("Ctrl + O", tr('key_event_down', lang)),
            ("Shift + / -", tr('key_tileset_up', lang) + " / " + tr('key_tileset_down', lang)),
            ("AltGr + / -", tr('key_palette_up', lang) + " / " + tr('key_palette_down', lang)),
            ("Ctrl + S", tr('menu_save', lang)),
            ("F5", tr('btn_refresh_ptr', lang)),
        ]

        for i, (key, desc) in enumerate(shortcuts):
            item_key = QTableWidgetItem(key)
            item_key.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_key.setForeground(Qt.GlobalColor.green)
            
            item_desc = QTableWidgetItem(desc)
            
            self.table.setItem(i, 0, item_key)
            self.table.setItem(i, 1, item_desc)
            
        self.table.setHorizontalHeaderLabels(["Keyboard Key", "Function"]) # Simple header
