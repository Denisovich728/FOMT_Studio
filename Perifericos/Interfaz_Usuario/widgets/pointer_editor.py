# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.0.0)
# "The Imposibility Update"
# Desarrollado por: Denisovich728
# ============================================================
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QTableWidget, QTableWidgetItem, QPushButton, QLabel, QHeaderView
)
from PyQt6.QtCore import Qt
import struct
from Perifericos.Traducciones.i18n import tr

class MasterPointerEditor(QWidget):
    """
    Submódulo de PyQt6: Editor estilo "AdvanceMap" puro de la Tabla Maestra.
    Permite redirigir manualmente el puntero de un evento hacia otro offset de la ROM.
    """
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.lang = getattr(parent, 'current_lang', 'es') if parent else 'es'
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        lang = self.lang
        
        # Toolbar Top
        toolbar = QHBoxLayout()
        lbl = QLabel(f"<h3>{tr('ptr_editor_title', lang)}</h3>")
        
        btn_refresh = QPushButton(tr('btn_refresh_ptr', lang))
        btn_refresh.clicked.connect(self.load_pointers)
        
        btn_save = QPushButton(tr('btn_save_ptr', lang))
        btn_save.setStyleSheet("background-color: #388e3c; color: white; font-weight: bold;")
        btn_save.clicked.connect(self.save_pointers)
        
        btn_relocate = QPushButton("Expandir Tabla (Relocalizar)")
        btn_relocate.setStyleSheet("background-color: #ff9800; color: black; font-weight: bold;")
        btn_relocate.clicked.connect(self.relocate_table)
        
        toolbar.addWidget(lbl)
        toolbar.addStretch()
        toolbar.addWidget(btn_refresh)
        toolbar.addWidget(btn_save)
        toolbar.addWidget(btn_relocate)
        layout.addLayout(toolbar)
        
        # Table Grid
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels([
            tr('col_ptr_id', lang), tr('col_ptr_hint', lang), tr('col_ptr_val', lang)
        ])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        
        # Configurar colores de la tabla
        self.table.setStyleSheet(
            "QTableWidget { background-color: #212121; color: #e0e0e0; gridline-color: #424242; font-family: 'Consolas'; font-size: 14px; }"
            "QHeaderView::section { background-color: #424242; color: white; padding: 4px; font-weight: bold; border: 1px solid #616161; }"
        )
        
        layout.addWidget(self.table)
        
        self.load_pointers()
        
    def load_pointers(self):
        """Lee los 1329 punteros de la memoria cruda y los lista."""
        self.table.setRowCount(0)
        
        if not self.project.super_lib:
            return
            
        limit = self.project.super_lib.event_limit
        table_base = self.project.super_lib.table_offset
        
        self.table.setRowCount(limit)
        
        for i in range(limit):
            # Leemos el pointer puro de 4 bytes
            ptr_loc = table_base + (i * 4)
            data = self.project.read_rom(ptr_loc, 4)
            ptr_val = struct.unpack('<I', data)[0]
            
            hint = self.project.super_lib.get_event_name_hint(i)
            
            # Column 1: ID
            item_id = QTableWidgetItem(f"{i} (0x{i:04X})")
            item_id.setFlags(item_id.flags() & ~Qt.ItemFlag.ItemIsEditable) 
            self.table.setItem(i, 0, item_id)
            
            # Column 2: Hint
            item_hint = QTableWidgetItem(hint)
            item_hint.setFlags(item_hint.flags() & ~Qt.ItemFlag.ItemIsEditable) 
            self.table.setItem(i, 1, item_hint)
            
            # Column 3: The Pointer
            # Formateamos bonito: 0x08123456
            item_ptr = QTableWidgetItem(f"0x{ptr_val:08X}")
            self.table.setItem(i, 2, item_ptr)
            
    def save_pointers(self):
        """
        Recorre la tabla, verifica si algún puntero ha sido cambiado por el usuario (modding explícito)
        y lo escribe como Parche en el Virtual File (.fsp).
        """
        limit = self.project.super_lib.event_limit
        table_base = self.project.super_lib.table_offset
        cambios = 0
        
        for i in range(limit):
            item_ptr = self.table.item(i, 2)
            if not item_ptr:
                continue
                
            txt_val = item_ptr.text().strip()
            # Try to parse el valor
            try:
                if txt_val.startswith("0x"):
                    new_val = int(txt_val, 16)
                else:
                    new_val = int(txt_val)
                    
                # Leemos el valor actual en RAM virtual para comparar
                ptr_loc = table_base + (i * 4)
                data_old = self.project.read_rom(ptr_loc, 4)
                old_val = struct.unpack('<I', data_old)[0]
                
                if new_val != old_val:
                    # Empaquetamos y escribimos el parche!
                    new_bytes = struct.pack('<I', new_val)
                    self.project.write_patch(ptr_loc, new_bytes)
                    cambios += 1
                    
            except Exception as e:
                print(f"Error parseando puntero de evento {i}: {e}")
                
        if cambios > 0:
            self.project.save()
            from PyQt6.QtWidgets import QMessageBox
            lang = self.lang
            msg = tr('msg_pointers_saved', lang).format(count=cambios)
            QMessageBox.information(self, tr('btn_save_ptr', lang), msg)

    def relocate_table(self):
        """Maneja el diálogo y la llamada a la reubicación de la tabla."""
        from PyQt6.QtWidgets import QInputDialog, QMessageBox
        
        old_limit = self.project.super_lib.event_limit
        new_capacity, ok = QInputDialog.getInt(
            self, 
            "Expandir Tabla de Eventos", 
            f"Límite actual: {old_limit}\nIngresa el nuevo límite de eventos (ej: {old_limit + 500}):", 
            value=old_limit + 500, 
            min=old_limit + 1, 
            max=10000
        )
        
        if ok:
            new_offset, msg = self.project.memory.relocate_master_event_table(new_capacity)
            if new_offset:
                self.project.save()  # Guardar el parche
                QMessageBox.information(self, "Éxito", msg)
                self.load_pointers()  # Recargar tabla con nuevos límites
            else:
                QMessageBox.warning(self, "Error", msg)
