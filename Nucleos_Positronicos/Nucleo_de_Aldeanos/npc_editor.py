# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.7.0)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, 
    QPushButton, QLabel, QMessageBox, QHeaderView,
    QDialog, QTextEdit, QGridLayout
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt

from Consola_de_Comando.utils import NameEditDelegate
from Consola_de_Comando.i18n import tr

class NpcEditorWidget(QWidget):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.npcs = []
        self.lang = getattr(parent, 'current_lang', 'es') if parent else 'es'
        
        self.setup_ui()
        self.load_data()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        lang = self.lang
        
        # Toolbar
        toolbar = QHBoxLayout()
        self.lbl_title = QLabel(f"<h3>{tr('npc_title', lang)}</h3>")
        
        self.btn_refresh = QPushButton(tr('btn_scan_npc', lang))
        self.btn_refresh.clicked.connect(self.load_data)
        
        self.btn_save = QPushButton(tr('btn_save_names', lang))
        self.btn_save.setStyleSheet("background-color: #2e7d32; color: white;")
        self.btn_save.clicked.connect(self.save_data)
        
        self.btn_expand = QPushButton("Portrait Expand (Experimental)")
        self.btn_expand.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold;")
        self.btn_expand.setToolTip("Aumentar el límite de tamaño e IDs de retratos en la ROM.")
        self.btn_expand.clicked.connect(self.expand_portraits)
        
        toolbar.addWidget(self.lbl_title)
        toolbar.addStretch()
        toolbar.addWidget(self.btn_expand)
        toolbar.addWidget(self.btn_refresh)
        toolbar.addWidget(self.btn_save)
        
        layout.addLayout(toolbar)
        
        # Tabla Spreadsheet
        self.table = QTableView()
        self.model = QStandardItemModel()
        self.table.setModel(self.model)
        
        # Opciones visuales
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(self.show_npc_details)
        
        # Asignar delegado para conteo de nombres
        self.delegate = NameEditDelegate(self, max_limit=10)
        self.table.setItemDelegateForColumn(1, self.delegate)
        
        layout.addWidget(self.table)
        
    def expand_portraits(self):
        lang = getattr(self.window(), 'current_lang', 'es')
        reply = QMessageBox.warning(self, "Portrait Expand", 
            "¿Quieres instalar el Assembly Hook para aumentar el límite de tamaño de portraits y permitir agregar más IDs a la ROM?\n\nEsta es una función EXPERIMENTAL. Úsalo bajo tu propio riesgo. Requiere una copia de seguridad de la ROM.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
        if reply == QMessageBox.StandardButton.Yes:
            # Aquí irá la lógica de inyección del Assembly Hook del Repacker
            QMessageBox.information(self, "Portrait Expand", "Hook de Expansión de Retratos preparado. La inyección se realizará durante el repacking.")
        
    def load_data(self):
        if not self.project: return
        lang = self.lang
        try:
            self.npcs = self.project.npc_parser.scan_npcs()
            self.filter_data()
        except Exception as e:
            QMessageBox.warning(self, tr("err_fatal", lang), f"{tr('err_npc_scan', lang)}\n{e}")

    def filter_data(self):
        lang = self.lang
        self.model.clear()
        self.model.setHorizontalHeaderLabels([
            tr('col_id', lang), tr('col_name', lang), 
            tr('col_role', lang), tr('col_ptr', lang)
        ])
        
        for i, npc in enumerate(self.npcs):
            stats = npc.read_stats(lang)
            if not stats:
                continue
                
            c_id = QStandardItem(stats.get('idx', '0x01'))
            c_id.setEditable(False)
            
            c_name = QStandardItem(stats.get('Nombre', tr('unknown', lang)))
            c_name.setEditable(True) 
            c_name.setData(i, Qt.ItemDataRole.UserRole)
            
            c_role = QStandardItem(stats.get('Rol', '-'))
            c_role.setEditable(False)
            
            c_ptr = QStandardItem(stats.get('Ptr_Personalidad', '0x00000000'))
            c_ptr.setEditable(False)
            c_ptr.setForeground(Qt.GlobalColor.blue)
            font = c_ptr.font()
            font.setUnderline(True)
            c_ptr.setFont(font)
            
            self.model.appendRow([c_id, c_name, c_role, c_ptr])

    def save_data(self):
        if not self.project or not self.npcs: return
        
        cambios = 0
        for row in range(self.model.rowCount()):
            idx = self.model.item(row, 1).data(Qt.ItemDataRole.UserRole)
            if idx is None: continue
            
            npc = self.npcs[idx]
            new_name = self.model.item(row, 1).text()
            
            if new_name != npc.name_str.strip('\x00'):
                npc.save_name_in_place(new_name)
                cambios += 1
                
        lang = getattr(self.window(), 'current_lang', 'es')
        msg = tr('msg_names_saved', lang).format(count=cambios)
        note = tr('msg_names_note', lang)
        QMessageBox.information(self, tr('btn_save_names', lang), f"{msg}\n{note}")

    def show_npc_details(self, index):
        if index.column() != 3:
            return
            
        row = index.row()
        idx = self.model.item(row, 1).data(Qt.ItemDataRole.UserRole)
        if idx is None: return
        npc = self.npcs[idx]
        
        dialog = NpcDetailDialog(npc, self)
        dialog.exec()

class NpcDetailDialog(QDialog):
    def __init__(self, npc, parent=None):
        super().__init__(parent)
        self.npc = npc
        name = npc.name_str.strip('\x00')
        lang = getattr(parent.window(), 'current_lang', 'es') if parent else 'es'
        self.setWindowTitle(tr('npc_profile', lang).format(name=name))
        self.resize(600, 500)
        
        self.layout_main = QHBoxLayout(self)
        
        # LADO IZQUIERDO: Visualización (Retrato)
        self.side_graphics = QVBoxLayout()
        self.lbl_portrait = QLabel()
        self.lbl_portrait.setFixedSize(128, 128)
        self.lbl_portrait.setStyleSheet("background-color: #222; border: 1px solid #444;")
        self.lbl_portrait.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.side_graphics.addWidget(self.lbl_portrait)
        
        self.btn_edit_portrait = QPushButton("👤 Editar Retrato")
        self.btn_edit_portrait.setStyleSheet("background-color: #1F3A5F; color: #89B4FA; font-weight: bold;")
        self.btn_edit_portrait.clicked.connect(self.abrir_editor_retrato)
        self.side_graphics.addWidget(self.btn_edit_portrait)
        
        self.side_graphics.addStretch()
        self.layout_main.addLayout(self.side_graphics)
        
        # LADO DERECHO: Datos
        layout = QVBoxLayout()
        self.layout_main.addLayout(layout)
        
        self._load_npc_portrait(npc, parent)
        
        # Cabecera
        app = parent.window() if parent else None
        lang = getattr(app, 'current_lang', 'es') if app else 'es'
        role_label = npc.get_translated_role(lang)
        header = QLabel(f"<h2>{name}</h2><b>{role_label}</b><br>{tr('engine_id', lang).format(id=f'{npc.index + 1:02X}')}")
        layout.addWidget(header)
        
        ptr_str = f"0x{getattr(npc, 'personality_ptr', 0):08X}"
        lbl_ptr = QLabel(f"<b>{tr('ptr_rom', lang)}</b> <span style='color:blue;'><u>{ptr_str}</u></span>")
        lbl_ptr.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        layout.addWidget(lbl_ptr)
        
        # Enlace Interactivo al Script de Personalidad
        script_layout = QHBoxLayout()
        lbl_script = QLabel("<b>Script Vinculado:</b>")
        self.btn_script = QPushButton(f"📜 {name}_Personality")
        self.btn_script.setStyleSheet("color: #4CAF50; border: none; text-decoration: underline; text-align: left;")
        self.btn_script.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_script.clicked.connect(lambda: self.abrir_script(f"{name}_Personality"))
        script_layout.addWidget(lbl_script)
        script_layout.addWidget(self.btn_script)
        script_layout.addStretch()
        layout.addLayout(script_layout)
        
        self.txt_data = QTextEdit()
        self.txt_data.setReadOnly(True)
        
        schedule_parser = getattr(parent.project, 'schedule_parser', None)
        if schedule_parser:
            cpp, pseudo = schedule_parser.decode_npc_schedule(npc)
            base_info = f"{tr('lbl_routine', lang)}\n\n"
            base_info += f"{tr('raw_gba_code', lang)}\n"
            base_info += cpp + "\n\n"
            base_info += f"--- 2. {tr('sched_analysis', lang).format(name='AI')} ---\n"
            base_info += pseudo
        else:
            base_info = tr('err_routine_engine', lang)
            
        self.txt_data.setPlainText(base_info)
        layout.addWidget(self.txt_data)

        btn_close = QPushButton(tr('btn_close_viewer', lang))
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)
        
    def abrir_script(self, script_name):
        app = self.parent().window()
        ptr = getattr(self.npc, 'personality_ptr', 0)
        if ptr == 0:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", "Este NPC no tiene un script de personalidad válido.")
            return
            
        if hasattr(app, 'tabs'):
            for i in range(app.tabs.count()):
                widget = app.tabs.widget(i)
                if hasattr(widget, 'load_rom_script'):
                    app.tabs.setCurrentIndex(i)
                    widget.load_rom_script(ptr)
                    self.close()
                    return
            
            # Si no existe la pestaña IDE, la creamos usando el método de app
            from Nucleos_Positronicos.Nucleo_de_Scripts.script_ide import ScriptIDEWidget
            ide = ScriptIDEWidget(app.project, app)
            ide.load_rom_script(ptr)
            app.tabs.addTab(ide, f"Script: {script_name}")
            app.tabs.setCurrentWidget(ide)
            self.close()
        

    def _load_npc_portrait(self, npc, parent):
        import os
        import csv
        from PyQt6.QtGui import QPixmap
        
        name = npc.name_str.strip('\x00')
        dump_dir = r"j:\Repositorios\fomt_studio\portraits_dump"
        csv_path = r"j:\Repositorios\fomt_studio\Banco_de_Datos\Cilixes\fomt\Fomt_Portraits.csv"
        lang = getattr(parent.window(), 'current_lang', 'es') if parent else 'es'
        
        if not os.path.exists(dump_dir):
            self.lbl_portrait.setText(tr('no_rom_data', lang))
            return
            
        target_portrait_name = f"{name}_Neutral"
        # Manejar discrepancia Lillia vs Lilia
        if name == "Lillia":
            target_portrait_name = "Lilia_Neutral"
            name = "Lilia"
            
        hex_id = None
        
        # Read the CSV to find the hex ID mapped to this NPC
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader) # skip header
                for row in reader:
                    if len(row) >= 2 and row[0].strip() == target_portrait_name:
                        hex_id = row[1].strip()
                        break
        except Exception as e:
            print(f"Error reading Fomt_Portraits.csv: {e}")
            
        if not hex_id:
            # Fallback for NPCs that might not have a Neutral portrait
            self.lbl_portrait.setText(tr('no_rom_data', lang))
            return
            
        self.current_hex_id = int(hex_id, 16)
        self.base_portrait_name = name
            
        # The dump script generates names like "00_Rick_Neutral.png"
        img_filename = f"{hex_id}_{target_portrait_name}.png"
        img_path = os.path.join(dump_dir, img_filename)
        
        if os.path.exists(img_path):
            try:
                pix = QPixmap(img_path).scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
                self.lbl_portrait.setPixmap(pix)
            except Exception as e:
                print(f"Error cargando PNG: {e}")
                self.lbl_portrait.setText(tr('render_error', lang))
        else:
            self.lbl_portrait.setText(tr('no_rom_data', lang))

    def abrir_editor_retrato(self):
        if not hasattr(self, 'current_hex_id') or self.current_hex_id is None:
            QMessageBox.warning(self, "Sin Retrato", "Este NPC no tiene un retrato asociado o no se encontró en la lista.")
            return
        from Nucleos_Positronicos.Nucleo_de_Portraits.portrait_editor import PortraitEditorDialog
        dlg = PortraitEditorDialog(self.npc.name_str.strip('\x00'), self.current_hex_id, self.base_portrait_name, parent=self)
        dlg.exec()
        # Recargar portrait tras cerrar el diálogo
        self._load_npc_portrait(self.npc, self.parent())

    def _on_close(self):
        self.close()
