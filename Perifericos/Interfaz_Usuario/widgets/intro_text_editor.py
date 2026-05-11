# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.0.0)
# "The Imposibility Update"
# Desarrollado por: Denisovich728
# ============================================================
import os
import csv
import struct
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
    QTableWidgetItem, QPushButton, QLabel, QHeaderView, 
    QMessageBox, QTextEdit
)
from PyQt6.QtCore import Qt
from Perifericos.Traducciones.i18n import tr

class IntroTextEditorWidget(QWidget):
    """
    Módulo para editar los textos de la introducción (Intro Dialogs).
    Utiliza el mapeo de punteros global para sincronizar todas las referencias.
    """
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.lang = getattr(parent, 'current_lang', 'es') if parent else 'es'
        self.mapping_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "Nucleos_de_Procesamiento", "data", "pointer_mapping_fomt.csv"
        )
        self.mappings = []
        self.setup_ui()
        self.load_mapping()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Toolbar
        toolbar = QHBoxLayout()
        lbl = QLabel("<h3>Editor de Texto Intro (Global Repointing)</h3>")
        
        btn_refresh = QPushButton("Refrescar")
        btn_refresh.clicked.connect(self.load_mapping)
        
        btn_save = QPushButton("Guardar Todo")
        btn_save.setStyleSheet("background-color: #388e3c; color: white; font-weight: bold;")
        btn_save.clicked.connect(self.save_all)
        
        toolbar.addWidget(lbl)
        toolbar.addStretch()
        toolbar.addWidget(btn_refresh)
        toolbar.addWidget(btn_save)
        layout.addLayout(toolbar)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Puntero Original", "Texto (Decorado)", "Referencias"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        
        # Estilo visual
        self.table.setStyleSheet(
            "QTableWidget { background-color: #1e1e1e; color: #d4d4d4; gridline-color: #333; font-family: 'Consolas'; }"
            "QHeaderView::section { background-color: #333; color: white; padding: 4px; }"
        )
        
        layout.addWidget(self.table)

    def load_mapping(self):
        if not os.path.exists(self.mapping_path):
            QMessageBox.warning(self, "Error", f"No se encontró el archivo de mapeo:\n{self.mapping_path}")
            return
            
        self.mappings = []
        try:
            with open(self.mapping_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.mappings.append(row)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error cargando CSV: {e}")
            return
            
        self.refresh_table()

    def refresh_table(self):
        """
        Lee los punteros reales desde los offsets de la ROM, los agrupa 
        y extrae el texto al que apuntan.
        """
        self.table.setRowCount(0)
        
        all_refs = set()
        for row in self.mappings:
            refs = [r.strip() for r in row["ReferenceOffsets"].split("|") if r.strip()]
            for r in refs:
                all_refs.add(int(r, 16))
        
        pointer_groups = {}
        for ref_off in sorted(list(all_refs)):
            try:
                data = self.project.read_rom(ref_off, 4)
                ptr_val = struct.unpack("<I", data)[0]
                if (ptr_val >> 24) == 0x08:
                    if ptr_val not in pointer_groups:
                        pointer_groups[ptr_val] = []
                    pointer_groups[ptr_val].append(ref_off)
            except:
                continue

        self.table.setRowCount(len(pointer_groups))
        
        for i, (ptr_val, refs) in enumerate(pointer_groups.items()):
            ptr_str = f"0x{ptr_val:08X}"
            
            # Texto
            try:
                offset_text = ptr_val & 0x01FFFFFF
                raw_bytes = bytearray()
                while len(raw_bytes) < 1000:
                    b = self.project.read_rom(offset_text + len(raw_bytes), 1)
                    if not b: break
                    raw_bytes.extend(b)
                    if b == b'\x05': break
                decorated_text = self.decorate_text(raw_bytes)
            except Exception as e:
                decorated_text = f"[ERROR: {e}]"
            
            # Columna 1: Puntero Actual (No editable)
            item_ptr = QTableWidgetItem(ptr_str)
            item_ptr.setData(Qt.ItemDataRole.UserRole, ptr_val) 
            item_ptr.setFlags(item_ptr.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 0, item_ptr)
            
            # Columna 2: Texto (Editable)
            self.table.setItem(i, 1, QTableWidgetItem(decorated_text))
            
            # Columna 3: Referencias (No editable, guardamos lista en UserRole)
            refs_str = ", ".join([f"0x{r:X}" for r in refs])
            item_refs = QTableWidgetItem(refs_str)
            item_refs.setData(Qt.ItemDataRole.UserRole, refs) # Guardamos lista de ints
            item_refs.setFlags(item_refs.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 2, item_refs)

    def decorate_text(self, data: bytes) -> str:
        """Convierte bytes de la ROM a texto con comandos legibles."""
        text = ""
        i = 0
        while i < len(data):
            b = data[i]
            if b == 0x0C: text += "\\x0c"
            elif b == 0x05: text += "\\x05"
            elif b == 0x0A: text += "\\x0d\\x0a"
            elif b == 0x0D: text += "\\x0d"
            elif b == 0x01: text += "{PLAYER}"
            elif b == 0xB1: text += "ñ"
            elif b == 0xB2: text += "Ñ"
            elif b == 0xFF: text += "\\xff"
            elif b < 0x20 or b > 0x7E:
                text += f"\\x{b:02x}"
            else:
                text += chr(b)
            i += 1
        return text

    def lex_text(self, text: str) -> bytes:
        """Convierte texto decorado de vuelta a bytes para la ROM."""
        buf = bytearray()
        i = 0
        while i < len(text):
            if text[i:i+4] == "\\x0c":
                buf.append(0x0C); i += 4
            elif text[i:i+4] == "\\x05":
                buf.append(0x05); i += 4
            elif text[i:i+8] == "\\x0d\\x0a":
                buf.append(0x0A); i += 8
            elif text[i:i+4] == "\\x0d":
                buf.append(0x0D); i += 4
            elif text[i:i+4] == "\\x0a":
                buf.append(0x0A); i += 4
            elif text[i:i+4] == "\\xff":
                buf.append(0xFF); i += 4
            elif text.startswith("{PLAYER}", i):
                buf.append(0x01); i += 8
            elif text[i] == 'ñ':
                buf.append(0xB1); i += 1
            elif text[i] == 'Ñ':
                buf.append(0xB2); i += 1
            elif text[i:i+2] == "\\x":
                try:
                    val = int(text[i+2:i+4], 16)
                    buf.append(val); i += 4
                except:
                    buf.append(ord(text[i])); i += 1
            else:
                try:
                    buf.extend(text[i].encode('windows-1252'))
                except:
                    buf.append(ord(text[i]))
                i += 1
        return bytes(buf)

    def save_all(self):
        cambios = 0
        for i in range(self.table.rowCount()):
            item_ptr = self.table.item(i, 0)
            ptr_val_orig = item_ptr.data(Qt.ItemDataRole.UserRole)
            txt_decorated = self.table.item(i, 1).text()
            
            # Obtener lista de offsets de referencia desde el UserRole (Seguridad total)
            item_refs = self.table.item(i, 2)
            refs_list = item_refs.data(Qt.ItemDataRole.UserRole)
            
            # Convertir a bytes
            new_data = self.lex_text(txt_decorated)
            
            # Offset original del texto
            offset_text_orig = ptr_val_orig & 0x01FFFFFF
            
            # Comparar con ROM actual
            old_data = bytearray()
            while len(old_data) < len(new_data):
                b = self.project.read_rom(offset_text_orig + len(old_data), 1)
                if not b: break
                old_data.extend(b)
            
            if bytes(old_data) != new_data:
                # 1. Asignar nuevo espacio
                new_offset = self.project.allocate_free_space(len(new_data))
                self.project.write_patch(new_offset, new_data)
                
                # 2. Generar nuevo puntero Little Endian
                new_ptr_val = new_offset | 0x08000000
                new_ptr_bytes = struct.pack('<I', new_ptr_val)
                
                # 3. PARCHEO GLOBAL: Actualizar todos los offsets que apuntaban al texto antiguo
                for ref_off in refs_list:
                    self.project.write_patch(ref_off, new_ptr_bytes)
                
                cambios += 1
                
        if cambios > 0:
            self.project.save()
            QMessageBox.information(self, "Éxito", f"Repunteo Global: Se han actualizado {cambios} textos únicos y se han parcheado TODAS sus referencias en la ROM.")
            self.refresh_table()
        else:
            QMessageBox.information(self, "Información", "No se detectaron cambios.")
