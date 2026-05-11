# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.1.0)
# "The Imposibility Update"
# Desarrollado por: Denisovich728
# ============================================================
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
        self.delegate = NameEditDelegate(self, max_limit=10)
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
                
            c_id = QStandardItem(stats.get('idx', '0x01'))
            c_id.setEditable(False)
            
            c_name = QStandardItem(stats.get('Nombre', 'Desconocido'))
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
        name = npc.name_str.strip('\x00')
        self.setWindowTitle(f"Perfil de Personalidad: {name}")
        self.resize(600, 500)
        
        self.layout_main = QHBoxLayout(self)
        
        # LADO IZQUIERDO: Visualización (Retrato)
        self.side_graphics = QVBoxLayout()
        self.lbl_portrait = QLabel()
        self.lbl_portrait.setFixedSize(128, 128)
        self.lbl_portrait.setStyleSheet("background-color: #222; border: 1px solid #444;")
        self.lbl_portrait.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.side_graphics.addWidget(self.lbl_portrait)
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
        header = QLabel(f"<h2>{name}</h2><b>{role_label}</b><br>ID Motor: 0x{npc.index + 1:02X}")
        layout.addWidget(header)
        
        ptr_str = f"0x{getattr(npc, 'personality_ptr', 0):08X}"
        lbl_ptr = QLabel(f"<b>{tr('ptr_rom', lang)}</b> <span style='color:blue;'><u>{ptr_str}</u></span>")
        lbl_ptr.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        layout.addWidget(lbl_ptr)
        
        self.txt_data = QTextEdit()
        self.txt_data.setReadOnly(True)
        
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

        btn_close = QPushButton(tr('btn_close_viewer', lang))
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)
        
    def _load_npc_portrait(self, npc, parent):
        """Intenta extraer y mostrar el retrato o sprite del NPC usando el motor RAW."""
        try:
            import struct
            from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.codec_tiles import assemble_sprite
            from PyQt6.QtGui import QImage, QPixmap
            
            project = parent.project
            p_offset = npc.portrait_offset
            
            # Motor RAW: cargamos 2KB directamente
            raw_data = project.read_rom(p_offset, 2048)
            if not raw_data: 
                self.lbl_portrait.setText("No ROM Data")
                return
            
            # Cargar Paleta Maestra (0x58B3E0)
            pal_raw = project.read_rom(npc.parser.master_palette_off, 32)
            pal = []
            if pal_raw:
                for i in range(16):
                    c16 = struct.unpack_from('<H', pal_raw, i*2)[0]
                    r = (c16 & 0x1F) << 3
                    g = ((c16 >> 5) & 0x1F) << 3
                    b = ((c16 >> 10) & 0x1F) << 3
                    pal.append((r, g, b))
            else:
                pal = [(i*16, i*16, i*16) for i in range(16)] # Fallback grayscale
            
            size = 64
            oam = {
                "w": size, "h": size, "tile_id": 0, "is_8bpp": False,
                "palette_bank": 0
            }
            
            canvas = assemble_sprite(raw_data, oam)
            
            img = QImage(size, size, QImage.Format.Format_RGB32)
            for y in range(size):
                for x in range(size):
                    c = pal[canvas[y][x]]
                    img.setPixel(x, y, (c[0] << 16) | (c[1] << 8) | c[2])
            
            pix = QPixmap.fromImage(img).scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
            self.lbl_portrait.setPixmap(pix)
        except Exception as e:
            print(f"Portrait Error: {e}")
            self.lbl_portrait.setText("Render Error")

    def _on_close(self):
        self.close()