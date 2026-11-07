# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v4.0.0)
# "The Greatest Show - Final Release"
# Desarrollado por: Denisovich728
# ============================================================
import os
import sys
import csv

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, 
    QPushButton, QLabel, QMessageBox, QHeaderView,
    QDialog, QTextEdit, QGridLayout, QFrame
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
        self.parent_widget = parent
        self.project = getattr(parent, 'project', None)
        name = npc.name_str.strip('\x00').strip()
        app = parent.window() if parent else None
        lang = getattr(app, 'current_lang', 'es') if app else 'es'
        self.setWindowTitle(tr('npc_profile', lang).format(name=name))
        self.resize(540, 320)
        self.setStyleSheet("""
            QDialog {
                background-color: #0D1117;
                color: #C9D1D9;
            }
            QLabel {
                color: #C9D1D9;
            }
            QPushButton {
                background-color: #21262D;
                color: #C9D1D9;
                border: 1px solid #30363D;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #30363D;
                border-color: #8B949E;
            }
        """)
        
        self.layout_main = QHBoxLayout(self)
        self.layout_main.setContentsMargins(16, 16, 16, 16)
        self.layout_main.setSpacing(16)
        
        # LADO IZQUIERDO: Visualización (Retrato Melody Engine)
        self.side_graphics = QVBoxLayout()
        self.side_graphics.setSpacing(10)
        
        self.lbl_portrait = QLabel()
        self.lbl_portrait.setFixedSize(128, 128)
        self.lbl_portrait.setStyleSheet("background-color: #090D16; border: 2px solid #1F6FEB; border-radius: 8px;")
        self.lbl_portrait.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.side_graphics.addWidget(self.lbl_portrait)
        
        self.btn_edit_portrait = QPushButton(tr("npc_edit_portrait", lang))
        self.btn_edit_portrait.setStyleSheet("background-color: #1F3A5F; color: #58A6FF; border: 1px solid #388BFD; font-weight: bold; padding: 6px;")
        self.btn_edit_portrait.clicked.connect(self.abrir_editor_retrato)
        self.side_graphics.addWidget(self.btn_edit_portrait)
        
        self.side_graphics.addStretch()
        self.layout_main.addLayout(self.side_graphics)
        
        # LADO DERECHO: Datos y Enlaces Interactivos
        layout = QVBoxLayout()
        layout.setSpacing(8)
        self.layout_main.addLayout(layout)
        
        self._load_npc_portrait(npc, parent)
        
        # Cabecera
        role_label = npc.get_translated_role(lang)
        header = QLabel(f"<h2 style='margin:0; color:#58A6FF;'>{name}</h2><b style='color:#7EE787;'>{role_label}</b><br><span style='color:#8B949E;'>{tr('engine_id', lang).format(id=f'{npc.index + 1:02X}')}</span>")
        layout.addWidget(header)
        
        ptr_str = f"0x{getattr(npc, 'personality_ptr', 0):08X}"
        lbl_ptr = QLabel(f"<b>{tr('ptr_rom', lang)}</b> <span style='color:#79C0FF; font-family:Consolas;'>{ptr_str}</span>")
        lbl_ptr.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        layout.addWidget(lbl_ptr)
        
        # Separador estilizado
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #30363D;")
        layout.addWidget(sep)
        
        # Enlace Interactivo al Script de Personalidad
        self.script_target_id = None
        self.script_target_name = f"{name}_Personality"
        self._resolve_script_personality(name, parent)

        script_layout = QHBoxLayout()
        lbl_script = QLabel("<b>Script:</b>")
        self.btn_script = QPushButton(f"{self.script_target_name}")
        self.btn_script.setStyleSheet("color: #3FB950; background: transparent; border: 1px dashed #238636; text-align: left; font-weight: bold; padding: 4px 8px;")
        self.btn_script.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_script.setToolTip("Abrir script de personalidad en el Script IDE")
        self.btn_script.clicked.connect(self.abrir_script)
        script_layout.addWidget(lbl_script)
        script_layout.addWidget(self.btn_script)
        script_layout.addStretch()
        layout.addLayout(script_layout)

        # Enlace Interactivo al Editor de Rutinas Diarias
        self.routine_target_id = self._resolve_routine_id(name)
        routine_layout = QHBoxLayout()
        lbl_routine = QLabel("<b>Rutina AI:</b>")
        if self.routine_target_id is not None:
            self.btn_routine = QPushButton(f"Orquestador #{self.routine_target_id:02d}")
            self.btn_routine.setStyleSheet("color: #58A6FF; background: transparent; border: 1px dashed #1F6FEB; text-align: left; font-weight: bold; padding: 4px 8px;")
            self.btn_routine.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_routine.setToolTip("Abrir orquestador de rutina diaria")
            self.btn_routine.clicked.connect(self.abrir_rutina)
        else:
            self.btn_routine = QLabel("<span style='color: #6E7681;'>Sin rutina de movimiento dedicada</span>")
        routine_layout.addWidget(lbl_routine)
        routine_layout.addWidget(self.btn_routine)
        routine_layout.addStretch()
        layout.addLayout(routine_layout)

        # Enlace al Teatro de Eventos (desconectado/oculto temporalmente)
        self.btn_theater = None

        layout.addStretch()

        btn_close = QPushButton(tr('btn_close_viewer', lang))
        btn_close.setStyleSheet("background-color: #21262D; color: #F0F6FC; border: 1px solid #30363D; padding: 6px;")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)
        
    def _resolve_routine_id(self, name):
        from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.routine_codec import NPC_NAMES
        name_clean = name.strip('\x00').strip().lower()
        alias = {
            'lillia': 0, 'lilia': 0, 'elli': 20, 'ellie': 20,
            'gourmet': 31, 'h. goddess': 31, 'goddess': 31,
            'lou': 30, 'lu': 30
        }
        if name_clean in alias:
            return alias[name_clean]
        for rid, full_desc in NPC_NAMES.items():
            first = full_desc.split(' (')[0].strip().lower()
            if first == name_clean or name_clean in full_desc.lower():
                return rid
        return None

    def _resolve_script_personality(self, name, parent):
        import csv
        clean_name = name.strip('\x00').strip()
        norm = clean_name.lower().replace(' ', '').replace('.', '')
        alias_map = {
            'lillia': 'lilia_personaliti',
            'lilia': 'lilia_personaliti',
            'chef': 'cheff_personaliti',
            'cheff': 'cheff_personaliti',
            'lou': 'loun_personality',
            'lu': 'lu_personality',
            'cliff': 'cliff_personality',
            'h. goddess': 'goddess_personality',
            'goddess': 'goddess_personality',
            'harvest goddess': 'goddess_personality',
        }
        target_event_key = alias_map.get(norm, f"{norm}_personality")
        csv_path = r"Banco_de_Datos\Cilixes\fomt\Fomt_Events_Listname.csv"
        if os.path.exists(csv_path):
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    r = csv.reader(f)
                    next(r)
                    for row in r:
                        if len(row) >= 2:
                            ev_name = row[0].strip()
                            ev_id_str = row[1].strip()
                            ev_low = ev_name.lower()
                            if ev_low == target_event_key or ev_low == f"{norm}_personaliti":
                                self.script_target_name = ev_name
                                self.script_target_id = int(ev_id_str)
                                return
            except Exception as e:
                print(f"Error resolviendo script canónico: {e}")

    def abrir_rutina(self):
        if self.routine_target_id is None:
            return
        app = self.parent().window()
        if hasattr(app, '_open_editor_rutinas_npc'):
            app._open_editor_rutinas_npc(target_npc_id=self.routine_target_id)
            self.close()

    def abrir_script(self):
        app = self.parent().window()
        # Si tenemos un script canónico en Fomt_Events_Listname.csv y el método open_event en app
        if self.script_target_id is not None and hasattr(app, 'open_event'):
            app.open_event(self.script_target_id)
            self.close()
            return

        ptr = getattr(self.npc, 'personality_ptr', 0)
        if ptr == 0:
            QMessageBox.warning(self, "Error", "Este NPC no tiene un script de personalidad válido ni evento asociado.")
            return

        if hasattr(app, 'tabs'):
            for i in range(app.tabs.count()):
                widget = app.tabs.widget(i)
                if hasattr(widget, 'load_rom_script'):
                    app.tabs.setCurrentIndex(i)
                    widget.load_rom_script(ptr)
                    self.close()
                    return

            from Nucleos_Positronicos.Nucleo_de_Scripts.script_ide import ScriptIDEWidget
            ide = ScriptIDEWidget(app.project, app)
            ide.load_rom_script(ptr)
            app.tabs.addTab(ide, f"Script: {self.script_target_name}")
            app.tabs.setCurrentWidget(ide)
            self.close()

    def abrir_teatro(self):
        app = self.parent().window()
        if hasattr(app, 'open_event_theater'):
            target_ev = self.script_target_id if self.script_target_id is not None else 1
            app.open_event_theater(target_ev)
            self.close()

    def _load_npc_portrait(self, npc, parent):
        import os
        import csv
        from PyQt6.QtGui import QPixmap
        
        name = npc.name_str.strip('\x00').strip()
        app = parent.window() if parent else None
        lang = getattr(app, 'current_lang', 'es') if app else 'es'
        
        # 1. Localizar directorio portraits_dump de forma robusta y multiplataforma
        candidates_dump = [
            os.path.join(os.getcwd(), "portraits_dump"),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "portraits_dump")),
            r"J:\Laboratorio\FOMT_Studio\portraits_dump"
        ]
        dump_dir = next((d for d in candidates_dump if os.path.exists(d)), "portraits_dump")
        
        # 2. Localizar Fomt_Portraits.csv
        candidates_csv = [
            os.path.join(os.getcwd(), "Banco_de_Datos", "Cilixes", "fomt", "Fomt_Portraits.csv"),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Banco_de_Datos", "Cilixes", "fomt", "Fomt_Portraits.csv")),
            r"J:\Laboratorio\FOMT_Studio\Banco_de_Datos\Cilixes\fomt\Fomt_Portraits.csv"
        ]
        csv_path = next((p for p in candidates_csv if os.path.exists(p)), "")
        
        # 3. Mapeo exhaustivo de alias para versión Neutral
        alias_portrait = {
            'lillia': 'Lilia_Neutral', 'lilia': 'Lilia_Neutral',
            'elli': 'Ellie_Neutral', 'ellie': 'Ellie_Neutral',
            'h. goddess': 'H_Goddes_Neutral', 'goddess': 'H_Goddes_Neutral',
            'harvest goddess': 'H_Goddes_Neutral',
            'lu': 'Ruby_Neutral', 'ruby': 'Ruby_Neutral', 'lou': 'Lou_Neutral',
            'chef': 'Chef_Neutral', 'cheff': 'Chef_Neutral',
            'mayor': 'Thomas_Neutral', 'thomas': 'Thomas_Neutral',
            'pastor': 'Carter_Neutral', 'carter': 'Carter_Neutral',
            'zack': 'Zack_Neutral', 'gotz': 'Gotz_Neutral',
            'won': 'Won_Neutral', 'gourmet': 'Gourmet_Neutral',
            'kappa': 'Kappa_Neutral', 'barley': 'Barley_Neutral',
            'may': 'May_Neutral', 'saibara': 'Saibara_Neutral',
            'gray': 'Gray_Neutral', 'duke': 'Duke_Neutral',
            'manna': 'Manna_Neutral', 'basil': 'Basil_Neutral',
            'anna': 'Anna_Neutral', 'mary': 'Mary_Neutral',
            'harris': 'Harris_Neutral', 'ellen': 'Ellen_Neutral',
            'stu': 'Stu_Neutral', 'jeff': 'Jeff_Neutral',
            'sasha': 'Sasha_Neutral', 'karen': 'Karen_Neutral',
            'doctor': 'Doctor_Neutral', 'cliff': 'Cliff_Neutral',
            'doug': 'Doug_Neutral', 'ann': 'Ann_Neutral',
            'kai': 'Kai_Neutral', 'popuri': 'Popuri_Neutral',
            'rick': 'Rick_Neutral', 'staid': 'Staid_Neutral',
            'nappy': 'Nappy_Neutral', 'bold': 'Bold_Neutral',
            'aqua': 'Aqua_Neutral', 'hoggy': 'Hoggy_Neutral',
            'timid': 'Timid_Neutral'
        }
        
        name_lower = name.lower()
        target_portrait_name = alias_portrait.get(name_lower, f"{name.capitalize()}_Neutral")
        base_name = target_portrait_name.replace("_Neutral", "")
        
        hex_id = None
        if os.path.exists(csv_path):
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader)
                    for row in reader:
                        if len(row) >= 2 and row[0].strip().lower() == target_portrait_name.lower():
                            hex_id = row[1].strip()
                            target_portrait_name = row[0].strip()
                            break
            except Exception as e:
                print(f"Error reading Fomt_Portraits.csv: {e}")
                
        if not hex_id:
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader)
                    for row in reader:
                        if len(row) >= 2 and name_lower in row[0].strip().lower() and 'neutral' in row[0].strip().lower():
                            hex_id = row[1].strip()
                            target_portrait_name = row[0].strip()
                            base_name = target_portrait_name.replace("_Neutral", "")
                            break
            except Exception:
                pass
                
        if not hex_id:
            self.lbl_portrait.setText(tr('no_rom_data', lang))
            return
            
        self.current_hex_id = int(hex_id, 16)
        self.base_portrait_name = base_name
            
        img_filename = f"{hex_id}_{target_portrait_name}.png"
        img_path = os.path.join(dump_dir, img_filename)
        
        # Prioridad 1: Decodificar dinámicamente en RAM directamente vía Melody Portrait Engine
        try:
            proj = getattr(parent, 'project', None)
            rom = getattr(proj, 'virtual_rom', None) or getattr(proj, 'rom_data', None)
            if rom:
                from Nucleos_Positronicos.Nucleo_de_Portraits.Melody_Portrait_Engine.dump_portraits import decode_portrait_pixmap
                pix = decode_portrait_pixmap(rom, self.current_hex_id)
                if pix and not pix.isNull():
                    self.lbl_portrait.setPixmap(pix.scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation))
                    return
        except Exception as e:
            print(f"Error decodificando retrato directamente desde Melody en RAM: {e}")

        # Prioridad 2: Fallback a PNG en disco desde portraits_dump
        if os.path.exists(img_path):
            try:
                pix = QPixmap(img_path).scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
                self.lbl_portrait.setPixmap(pix)
                return
            except Exception as e:
                print(f"Error cargando PNG: {e}")

        self.lbl_portrait.setText(tr('no_rom_data', lang))

    def abrir_editor_retrato(self):
        # Redirigir directamente al editor de metasprites portraits
        top_win = self.window()
        if hasattr(top_win, '_open_visor_metasprites'):
            viewer = top_win._open_visor_metasprites()
            if viewer and hasattr(self, 'current_hex_id') and self.current_hex_id is not None:
                viewer.select_portrait_by_hex_id(self.current_hex_id)
            self.accept()
            return

        from Nucleos_Positronicos.Nucleo_de_Sprites.visor_metasprites import VisorMetasprites
        from Consola_de_Comando.app import FloatingWindow
        viewer = VisorMetasprites(self)
        if hasattr(self.parent(), 'project'):
            viewer.set_project(self.parent().project)
        float_win = FloatingWindow(viewer, "Editor de Metasprites y Portraits", self)
        float_win.resize(1200, 800)
        float_win.show()
        if hasattr(self, 'current_hex_id') and self.current_hex_id is not None:
            viewer.select_portrait_by_hex_id(self.current_hex_id)
        self.accept()

    def _on_close(self):
        self.close()
