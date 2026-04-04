from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, 
    QPushButton, QLabel, QMessageBox, QHeaderView,
    QDialog, QTextEdit, QGridLayout
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt

from Perifericos.Interfaz_Usuario.widgets.utils import NameEditDelegate
from Perifericos.Traducciones.i18n import tr

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
        
        toolbar.addWidget(self.lbl_title)
        toolbar.addStretch()
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
        self.delegate = NameEditDelegate(self)
        self.table.setItemDelegateForColumn(1, self.delegate)
        
        layout.addWidget(self.table)
        
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
                
            c_id = QStandardItem(f"[{stats.get('ID', 0):03d}]")
            c_id.setEditable(False)
            
            c_name = QStandardItem(stats.get('Nombre', 'Desconocido'))
            c_name.setEditable(True) # Permitir editar el nombre limitadamente
            c_name.setData(i, Qt.ItemDataRole.UserRole)
            c_name.setData(stats.get('max_len', 10), Qt.ItemDataRole.UserRole + 2) # Guardar limite para el delegado
            
            c_role = QStandardItem(stats.get('Rol', '-'))
            c_role.setEditable(False)
            
            c_ptr = QStandardItem(stats.get('Ptr_Personalidad', '0x00000000'))
            c_ptr.setEditable(False)
            # Decoración simulando link
            c_ptr.setForeground(Qt.GlobalColor.blue)
            font = c_ptr.font()
            font.setUnderline(True)
            c_ptr.setFont(font)
            
            self.model.appendRow([c_id, c_name, c_role, c_ptr])

    def save_data(self):
        if not self.project or not self.npcs: return
        
        cambios = 0
        for row in range(self.model.rowCount()):
            # La columna 1 es Nombre, su DataRole guarda el indice en self.npcs
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
        if index.column() != 3: # Solo abrir si se cliquea el Puntero (Columna 3)
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
        name = npc.name_str.strip('\x00')
        self.setWindowTitle(f"Perfil de Personalidad: {name}")
        self.resize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # Cabecera
        app = parent.window() if parent else None
        lang = getattr(app, 'current_lang', 'es') if app else 'es'
        role_label = npc.get_translated_role(lang)
        header = QLabel(f"<h2>{name}</h2><b>{role_label}</b><br>ID Motor: [{npc.index:03d}]")
        layout.addWidget(header)
        
        # Puntero simulando el hipervínculo interno del engine
        ptr_str = f"0x{getattr(npc, 'personality_ptr', 0):08X}"
        lbl_ptr = QLabel(f"<b>{tr('ptr_rom', lang)}</b> <span style='color:blue;'><u>{ptr_str}</u></span>")
        lbl_ptr.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        layout.addWidget(lbl_ptr)
        
        # Bloque de notas o simulación de descifrado individual
        self.txt_data = QTextEdit()
        self.txt_data.setReadOnly(True)
        
        # Invocar a la librería de Rutinas (Stan Heuristic IA)
        schedule_parser = getattr(parent.project, 'schedule_parser', None)
        
        if schedule_parser:
            cpp, pseudo = schedule_parser.decode_npc_schedule(npc)
            base_info = f"{tr('lbl_routine', lang)}\n\n"
            base_info += "--- 1. CÓDIGO CRUTO GBA (C++ Macros) ---\n"
            base_info += cpp + "\n\n"
            base_info += f"--- 2. {tr('sched_analysis', lang).format(name='AI')} ---\n"
            base_info += pseudo
        else:
            base_info = "[Error] Motor de Rutinas desconectado."
            
        self.txt_data.setPlainText(base_info)
        layout.addWidget(self.txt_data)
        
        lang = getattr(parent.window(), 'current_lang', 'es')
        btn_close = QPushButton(tr('btn_close_viewer', lang))
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)
