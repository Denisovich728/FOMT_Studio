# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.4.4)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QPushButton, 
    QHBoxLayout, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from Perifericos.Traducciones.i18n import tr
import re

class ItemBulkEditorWidget(QWidget):
    def __init__(self, project, category_label, category_filter, parent=None):
        super().__init__(parent)
        self.project = project
        self.category_label = category_label
        self.category_filter = category_filter
        self._init_ui()
        self.refresh_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # BANNER DE ADVERTENCIA EXPERIMENTAL
        warning_box = QLabel(tr("bulk_warning"))
        warning_box.setStyleSheet("background-color: #E74C3C; color: white; padding: 10px; "
                                 "font-weight: bold; border-radius: 5px;")
        warning_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(warning_box)
        
        header = QLabel(f"<b>{tr('bulk_title').format(category=self.category_label)}</b>")
        header.setStyleSheet("font-size: 14px; color: #3498DB; margin-top: 10px;")
        layout.addWidget(header)
        
        self.editor = QTextEdit()
        self.editor.setFont(QFont("Consolas", 10))
        self.editor.setPlaceholderText(tr("bulk_placeholder"))
        layout.addWidget(self.editor)
        
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton(tr("btn_bulk_sync").format(category=self.category_label.upper()))
        self.btn_save.setFixedHeight(45)
        self.btn_save.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold; border-radius: 5px;")
        self.btn_save.clicked.connect(self.save_to_rom)
        
        self.btn_refresh = QPushButton(tr("btn_bulk_refresh"))
        self.btn_refresh.clicked.connect(self.refresh_data)
        
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)

    def refresh_data(self):
        """Carga los datos en formato CSV-like para edición rápida."""
        items = [itm for itm in self.project.item_parser.items if itm.category == self.category_filter]
        lines = []
        for itm in items:
            lines.append(f"[0x{itm.index:02X}] {itm.name_str} | {itm.desc_str}")
        self.editor.setPlainText("\n".join(lines))

    def save_to_rom(self):
        """Aplica los cambios uno a uno con repunteo SlipSpace."""
        text = self.editor.toPlainText()
        lines = text.split("\n")
        
        items = [itm for itm in self.project.item_parser.items if itm.category == self.category_filter]
        changes = 0
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith("//"): continue
            
            # Regex para capturar [ID] Nombre | Descripción
            match = re.search(r'\[0x([A-Fa-f0-9]+)\]\s*(.*?)\s*\|\s*(.*)', line)
            if match:
                idx = int(match.group(1), 16)
                new_name = match.group(2).strip()
                new_desc = match.group(3).strip()
                
                itm = next((it for it in items if it.index == idx), None)
                if itm:
                    changed_item = False
                    if new_name != itm.name_str:
                        itm.save_name_in_place(new_name)
                        changed_item = True
                    if new_desc != itm.desc_str:
                        itm.save_desc_in_place(new_desc)
                        changed_item = True
                    
                    if changed_item:
                        changes += 1
                        
        if changes > 0:
            QMessageBox.information(self, tr("title_bulk_sync"), 
                                  tr("msg_bulk_success").format(count=changes))
            self.project.save_rom()
        else:
            QMessageBox.warning(self, tr("title_no_changes"), tr("msg_no_changes"))
        self.refresh_data()
