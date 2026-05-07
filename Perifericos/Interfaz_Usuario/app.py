import os
import sys
import re
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QSplitter, QTreeView, QMenuBar, QMenu,
    QStatusBar, QFileDialog, QMessageBox, QLabel, QLineEdit
)
from PyQt6.QtCore import Qt, QSettings, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QAction, QStandardItemModel, QStandardItem, QDesktopServices

from Perifericos.Interfaz_Usuario.themes import get_light_theme, get_dark_theme, get_matrix_theme
from Perifericos.Traducciones.i18n import tr

from Nucleos_de_Procesamiento.Nucleo_de_Datos.proyecto import FoMTProject
from Perifericos.Interfaz_Usuario.widgets.item_editor import ItemEditorWidget
from Perifericos.Interfaz_Usuario.widgets.script_ide import ScriptIDEWidget
from Perifericos.Interfaz_Usuario.widgets.event_visual import VisualEventMaker
from Perifericos.Interfaz_Usuario.widgets.pointer_editor import MasterPointerEditor
from Perifericos.Interfaz_Usuario.widgets.npc_editor import NpcEditorWidget
from Perifericos.Interfaz_Usuario.widgets.map_editor import MapEditorWidget
from Perifericos.Interfaz_Usuario.widgets.tile_viewer import TileViewerWidget
from Perifericos.Interfaz_Usuario.widgets.help_widget import HelpWidget
from Perifericos.Interfaz_Usuario.componentes.visor_sonido import SappyAudioViewer
from Perifericos.Interfaz_Usuario.componentes.visor_sprites import VisorSprites
from PyQt6.QtGui import QAction, QShortcut, QKeySequence, QCursor
from PyQt6.QtWidgets import QDialog

class FloatingWindow(QMainWindow):
    def __init__(self, widget, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setCentralWidget(widget)
        self.resize(800, 600)
        self.parent_app = parent
        
    def closeEvent(self, event):
        super().closeEvent(event)

class ProjectLoaderThread(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)
    step_finished = pyqtSignal(int)

    def __init__(self, mode, rom_path, proj_path):
        super().__init__()
        self.mode = mode
        self.rom_path = rom_path
        self.proj_path = proj_path
        self.project = None

    def run(self):
        try:
            self.project = FoMTProject()
            if self.mode == 'session':
                self.progress.emit(10, "status_ready")
                proj_dir = self.project.open_rom_session(self.rom_path)
                self.proj_path = os.path.join(proj_dir, f"{self.project.name}.fsp")
                self.progress.emit(25, "status_scanning_events")
                self.project.step_2_scan_events()
                self.step_finished.emit(2)
                self.progress.emit(50, "status_scanning_graphics")
                self.project.step_3_scan_graphics()
                self.step_finished.emit(3)
                self.progress.emit(80, "status_scanning_audio")
                self.project.step_4_scan_audio()
                self.step_finished.emit(4)

            elif self.mode == 'new':
                self.progress.emit(10, "status_ready")
                self.project.step_1_detect_rom(self.rom_path, self.proj_path)
                self.progress.emit(25, "status_scanning_events")
                self.project.step_2_scan_events()
                self.step_finished.emit(2)
                self.progress.emit(50, "status_scanning_graphics")
                self.project.step_3_scan_graphics()
                self.step_finished.emit(3)
                self.progress.emit(80, "status_scanning_audio")
                self.project.step_4_scan_audio()
                self.step_finished.emit(4)
                self.project.save()
            else:
                self.progress.emit(20, "menu_load")
                self.project.load(self.proj_path)
                self.project.step_2_scan_events()
                self.step_finished.emit(2)
                self.progress.emit(50, "status_scanning_graphics")
                self.project.step_3_scan_graphics()
                self.step_finished.emit(3)
                self.progress.emit(80, "status_scanning_audio")
                self.project.step_4_scan_audio()
                self.step_finished.emit(4)
            
            self.progress.emit(100, "status_scan_complete")
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))

class FoMTStudioApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.floating_windows = []
        self.project = None
        self.setWindowTitle("FoMT Studio v2.0.0 - The Shiao_Fujikawa Update")
        self.resize(1024, 768)
        
        self.project = None
        self.item_editor = None
        self.npc_editor = None
        self.pointer_editor = None
        self.script_ide = None
        self.visual_maker = None
        self.map_editor = None
        self.tile_viewer = None
        self.audio_viewer = None
        self.sprite_viewer = None
        self.cat_events_item = None
        
        self.settings = QSettings("FoMTStudio", "ModdingSuite")
        self.current_lang = self.settings.value("language", "es")
        self.current_theme = self.settings.value("theme", "light")
        self.last_rom_dir = self.settings.value("last_rom_dir", "")
        
        self._setup_ui()
        self._setup_menu()
        self.apply_theme(self.current_theme)
        self.apply_language(self.current_lang)
        
        QShortcut(QKeySequence("Ctrl+O"), self, self.action_open_rom)
        QShortcut(QKeySequence("Ctrl+S"), self, self.action_save_project)
        QShortcut(QKeySequence("Ctrl+P"), self, self._on_shortcut_event_up)
        QShortcut(QKeySequence("Ctrl+L"), self, self._on_shortcut_event_down)
        
        self._check_for_crash_report()
        
    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        left_panel = QVBoxLayout()
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText(tr("search_placeholder", self.current_lang))
        self.search_bar.textChanged.connect(self.on_search_text_changed)
        
        self.tree_view = QTreeView()
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels([tr("explorer_header", self.current_lang)])
        self.tree_view.setModel(self.tree_model)
        
        left_panel.addWidget(self.search_bar)
        left_panel.addWidget(self.tree_view)
        
        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        splitter.addWidget(left_widget)
        
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.customContextMenuRequested.connect(self._on_tab_context_menu)
        splitter.addWidget(self.tabs)

        self.help_dialog = None
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([200, 800])
        
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        
        from PyQt6.QtWidgets import QProgressBar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(150)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("QProgressBar { height: 12px; font-size: 10px; }")
        self.status.addPermanentWidget(self.progress_bar)
        
        self.status.showMessage(tr("status_ready", self.current_lang))
        
    def _setup_menu(self):
        menubar = self.menuBar()
        lang = self.current_lang
        
        file_menu = menubar.addMenu(tr("menu_file", lang))
        new_proj_action = QAction(tr("menu_new", lang), self)
        new_proj_action.triggered.connect(self.action_new_project)
        file_menu.addAction(new_proj_action)
        load_proj_action = QAction(tr("menu_load", lang), self)
        load_proj_action.triggered.connect(self.action_load_project)
        file_menu.addAction(load_proj_action)
        file_menu.addSeparator()
        save_action = QAction(tr("menu_save", lang), self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.action_save_project)
        file_menu.addAction(save_action)
        compile_action = QAction(tr("menu_compile", lang), self)
        compile_action.triggered.connect(self.action_compile_rom)
        file_menu.addAction(compile_action)
        
        config_menu = menubar.addMenu(tr("menu_config", lang))
        theme_menu = config_menu.addMenu(tr("menu_theme", lang))
        light_action = QAction(tr("theme_light", lang), self)
        light_action.triggered.connect(lambda: self.apply_theme("light"))
        dark_action = QAction(tr("theme_dark", lang), self)
        dark_action.triggered.connect(lambda: self.apply_theme("dark"))
        matrix_action = QAction(tr("theme_matrix", lang), self)
        matrix_action.triggered.connect(lambda: self.apply_theme("matrix"))
        theme_menu.addActions([light_action, dark_action, matrix_action])
        
        lang_menu = config_menu.addMenu(tr("menu_lang", lang))
        for l_code in ["es", "en", "jp", "ru", "de", "zh", "hi", "pt"]:
            act = QAction(tr(f"lang_{l_code}", lang), self)
            act.triggered.connect(lambda checked, lc=l_code: self.apply_language(lc))
            lang_menu.addAction(act)
        
        help_menu = menubar.addMenu(tr("menu_help", lang))
        shortcuts_action = QAction(tr("tab_help", lang), self)
        shortcuts_action.triggered.connect(self._on_action_help)
        help_menu.addAction(shortcuts_action)

    def apply_theme(self, theme_name):
        self.current_theme = theme_name
        self.settings.setValue("theme", theme_name)
        if theme_name == "matrix":
            self.setStyleSheet(get_matrix_theme())
        elif theme_name == "dark":
            self.setStyleSheet(get_dark_theme())
        else:
            self.setStyleSheet(get_light_theme())
        
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if hasattr(widget, "highlighter") and widget.highlighter:
                widget.highlighter.update_colors(theme_name)
        
        for win in self.floating_windows:
            w = win.centralWidget()
            if hasattr(w, "highlighter") and w.highlighter:
                w.highlighter.update_colors(theme_name)

    def apply_language(self, lang_code):
        self.current_lang = lang_code
        self.settings.setValue("language", lang_code)
        self.menuBar().clear()
        self._setup_menu()
        title_hint = tr('explorer_title', lang_code)
        self.setWindowTitle(f"FoMT Studio - {title_hint}")
        self.status.showMessage(tr("status_ready", lang_code))
        if self.project:
            self._on_project_loaded()
        else:
            header_text = tr("explorer_header", lang_code)
            self.tree_model.setHorizontalHeaderLabels([header_text])

    def _check_close_project(self) -> bool:
        if self.project:
            ret = QMessageBox.warning(
                self, 
                tr("title_close_project", self.current_lang),
                tr("msg_close_project", self.current_lang),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            return ret == QMessageBox.StandardButton.Yes
        return True
            
    def action_open_rom(self):
        if not self._check_close_project(): return
        path, _ = QFileDialog.getOpenFileName(self, "Abrir ROM (Crear Sesión FSP)", self.last_rom_dir, "GBA ROM (*.gba)")
        if not path: return
        self.last_rom_dir = os.path.dirname(path)
        self.settings.setValue("last_rom_dir", self.last_rom_dir)
        self._start_async_load('session', path, None)

    def action_new_project(self):
        if not self._check_close_project(): return
        path, _ = QFileDialog.getOpenFileName(self, tr("menu_new", self.current_lang), self.last_rom_dir, "GBA ROM (*.gba)")
        if not path: return
        self.last_rom_dir = os.path.dirname(path)
        self.settings.setValue("last_rom_dir", self.last_rom_dir)
        proj_dir = QFileDialog.getExistingDirectory(self, "Selecciona Carpeta para tu Nuevo Proyecto FoMT Studio")
        if not proj_dir: return
        self._start_async_load('new', path, proj_dir)
            
    def action_load_project(self):
        if not self._check_close_project(): return
        path, _ = QFileDialog.getOpenFileName(self, tr("menu_load", self.current_lang), "", "FoMT Studio Project (*.fsp *.json)")
        if not path: return
        self._start_async_load('load', None, path)

    def _start_async_load(self, mode, rom_path, proj_path):
        self.status.showMessage("Iniciando tarea de fondo...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.loader_thread = ProjectLoaderThread(mode, rom_path, proj_path)
        self.loader_thread.progress.connect(self._on_load_progress)
        self.loader_thread.step_finished.connect(self._on_project_step_finished)
        self.loader_thread.finished.connect(self._on_async_load_finished)
        self.loader_thread.start()
        self.menuBar().setEnabled(False)
        self.tree_view.setEnabled(False)

    def _on_load_progress(self, value, status_key):
        self.progress_bar.setValue(value)
        self.status.showMessage(tr(status_key, self.current_lang))

    def _on_project_step_finished(self, step):
        if self.loader_thread:
            self.project = self.loader_thread.project
        if step == 2:
            self._on_project_loaded()
            self.menuBar().setEnabled(True)
            self.tree_view.setEnabled(True)
        else:
            self._populate_ui_step(step)

    def _on_async_load_finished(self, success, error_msg):
        self.menuBar().setEnabled(True)
        self.tree_view.setEnabled(True)
        self.progress_bar.setVisible(False)
        if success:
            self.status.showMessage(tr("status_scan_complete", self.current_lang), 5000)
            if self.project:
                game_label = "FOMT" if not self.project.is_mfomt else "MFOMT"
                csv_name = "Fomt_Events_Listname.csv" if not self.project.is_mfomt else "MFomt_Events_Listname.csv"
                reply = QMessageBox.question(
                    self, 
                    tr("title_detection", self.current_lang),
                    tr("msg_fomt_detected", self.current_lang).format(game=game_label),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    if self.project.super_lib.load_event_names_from_csv(csv_name):
                        if hasattr(self, "cat_events") and self.cat_events:
                            self.cat_events.removeRows(0, self.cat_events.rowCount())
                            self._populate_ui_step(2)
                        self.status.showMessage(f"Lista de nombres {game_label} cargada correctamente.")
        else:
            QMessageBox.critical(self, tr("err_fatal", self.current_lang), error_msg)
            self.status.showMessage("Error en carga.")

    def action_save_project(self):
        if not self.project: return
        try:
            self.project.save()
            self.status.showMessage("Progreso guardado en el archivo de proyecto.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error guardando: {e}")
            
    def action_compile_rom(self):
        if not self.project: return
        dest, _ = QFileDialog.getSaveFileName(self, "Exportar ROM Compilada", "Modded_FoMT.gba", "GBA ROM (*.gba)")
        if dest:
            try:
                self.project.compile_to_rom(dest)
                self.status.showMessage(f"ROM parcheada y exportada a {dest}!")
            except Exception as e:
                QMessageBox.critical(self, "Error de Compilación", f"Ocurrió un fallo durante la exportación:\n{e}")

    def _on_project_loaded(self):
        self.tabs.clear()
        self.tree_model.clear()
        self.tile_viewer = None
        self.audio_viewer = None
        self.sprite_viewer = None
        proj_label = tr("explorer_proj", self.current_lang).format(name=self.project.name)
        self.tree_model.setHorizontalHeaderLabels([proj_label])
        root = self.tree_model.invisibleRootItem()
        self.cat_npcs = QStandardItem(tr("cat_npcs", self.current_lang))
        self.cat_items = QStandardItem(tr("cat_items", self.current_lang))
        self.cat_bulk_items = QStandardItem("Lista Maestra (Nombres/Desc)")
        self.cat_events = QStandardItem(tr("cat_events", self.current_lang))
        self.cat_maps = QStandardItem(tr("cat_maps", self.current_lang))
        root.appendRow(self.cat_npcs)
        root.appendRow(self.cat_items)
        root.appendRow(self.cat_bulk_items)
        root.appendRow(self.cat_events)
        root.appendRow(self.cat_maps)
        self._populate_ui_step(2)
        item_bulk = QStandardItem("Items (Bulk Edit Mode)")
        item_bulk.setData("BULK_ITEMS", Qt.ItemDataRole.UserRole + 1)
        self.cat_bulk_items.appendRow(item_bulk)
        self.cat_events_item = self.cat_events
        try: self.tree_view.doubleClicked.disconnect()
        except: pass
        self.tree_view.doubleClicked.connect(self._on_tree_double_click)
        self.visual_maker = VisualEventMaker(self.project, self)
        self.tabs.addTab(self.visual_maker, tr("tab_visual", self.current_lang))
        self.apply_theme(self.current_theme)

    def _populate_ui_step(self, step):
        if not self.project: return
        if step == 2:
            self.cat_npcs.removeRows(0, self.cat_npcs.rowCount())
            for i, npc in enumerate(self.project.npc_parser.npcs):
                item = QStandardItem(f"[{i:02d}] {npc.name_str.strip('\x00')}")
                item.setData("NPC", Qt.ItemDataRole.UserRole + 1)
                item.setData(i, Qt.ItemDataRole.UserRole)
                self.cat_npcs.appendRow(item)
            self.cat_events.removeRows(0, self.cat_events.rowCount())
            self.cat_events.setText(f"{tr('cat_events', self.current_lang)} ({self.project.event_parser.get_event_count()})")
            for i in range(1, self.project.event_parser.get_event_count() + 1):
                ev_item = QStandardItem(self.project.super_lib.get_baptized_name(i, ""))
                ev_item.setData("EVENT", Qt.ItemDataRole.UserRole + 1)
                ev_item.setData(i, Qt.ItemDataRole.UserRole)
                self.cat_events.appendRow(ev_item)
            self.cat_maps.removeRows(0, self.cat_maps.rowCount())
            for m in self.project.map_parser.maps:
                m_name = self.project.super_lib.get_map_name_hint(m.map_id)
                map_label = "MAPA" if self.current_lang == "es" else "MAP"
                map_item = QStandardItem(f"{map_label} {m.map_id:03d}: {m_name}")
                map_item.setData("MAP", Qt.ItemDataRole.UserRole + 1)
                map_item.setData(m.map_id, Qt.ItemDataRole.UserRole)
                self.cat_maps.appendRow(map_item)
            self.tree_view.expand(self.cat_events.index())
        elif step == 3:
            if not self.sprite_viewer:
                self.sprite_viewer = VisorSprites(self)
                self.sprite_viewer.set_project(self.project)
                self.tabs.addTab(self.sprite_viewer, "🎨 Sprites & Portraits")
        elif step == 4:
            if not self.audio_viewer:
                self.audio_viewer = SappyAudioViewer(self.project, self)
                self.tabs.addTab(self.audio_viewer, tr("tab_audio", self.current_lang))
        
    def _on_tree_double_click(self, index):
        item = self.tree_model.itemFromIndex(index)
        if not item: return
        type = item.data(Qt.ItemDataRole.UserRole + 1)
        val = item.data(Qt.ItemDataRole.UserRole)
        if type == "EVENT":
            self.open_event(val)
        elif type == "NPC":
            self.open_npc_routine(val)
        elif type == "MAP":
            map_id = val
            map_header = self.project.map_parser.get_map_by_id(map_id)
            if map_header:
                for i in range(self.tabs.count()):
                    if self.tabs.tabText(i).startswith(f"Map {map_id}"):
                        self.tabs.setCurrentIndex(i)
                        return
                editor = MapEditorWidget(self)
                editor.project = self.project
                editor.load_map(map_header)
                editor.openScriptRequested.connect(self.open_event)
                self.tabs.addTab(editor, f"Map {map_id:03d}")
                self.tabs.setCurrentWidget(editor)
        elif type == "BULK_ITEMS":
            for i in range(self.tabs.count()):
                if self.tabs.tabText(i) == "Bulk Items":
                    self.tabs.setCurrentIndex(i)
                    return
            ide = ScriptIDEWidget(self.project, self)
            lines = [f"// --- ITEM 0x{itm.index:02X} ({itm.category}) ---\nNAME: {itm.name_str}\nDESC: {itm.desc_str}\n" 
                     for itm in self.project.item_parser.items]
            ide.editor.setPlainText("\n".join(lines))
            self.tabs.addTab(ide, "Bulk Items")
            self.tabs.setCurrentWidget(ide)

    def open_event(self, event_id):
        tab_name = self.project.super_lib.get_baptized_name(event_id, "")
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == tab_name:
                self.tabs.setCurrentIndex(i)
                return
        ide = ScriptIDEWidget(self.project, self)
        ide.load_event(event_id)
        self.tabs.addTab(ide, tab_name)
        self.tabs.setCurrentWidget(ide)

    def open_npc_routine(self, npc_id):
        npc_data = self.project.npc_parser.npcs[npc_id]
        tab_name = f"Routine: {npc_data.name_str.strip()}"
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == tab_name:
                self.tabs.setCurrentIndex(i)
                return
        ide = ScriptIDEWidget(self.project, self)
        code, _ = self.project.schedule_parser.decode_npc_schedule(npc_data)
        ide.editor.setPlainText(code)
        self.tabs.addTab(ide, tab_name)
        self.tabs.setCurrentWidget(ide)

    def open_script_by_ref(self, ref):
        """Busca un script por nombre o ID y lo abre."""
        event_id = None
        if ref.startswith("0x"):
            try: event_id = int(ref, 16)
            except: pass
        elif ref.isdigit():
            event_id = int(ref)
        else:
            for eid, name in self.project.super_lib.event_names.items():
                if name == ref:
                    event_id = eid
                    break
            if event_id is None and ref.startswith("Script_"):
                try: event_id = int(ref.replace("Script_", ""), 16)
                except: pass
        
        if event_id is not None:
            self.open_event(event_id)
        else:
            self.status.showMessage(f"No se pudo encontrar el script: {ref}", 3000)

    def _close_tab(self, index):
        widget = self.tabs.widget(index)
        if widget:
            widget.deleteLater()
        self.tabs.removeTab(index)

    def _on_tab_context_menu(self, position):
        index = self.tabs.tabBar().tabAt(position)
        if index == -1: return
        
        menu = QMenu()
        float_action = QAction("Hacer Flotante", self)
        float_action.triggered.connect(lambda: self._float_tab(index))
        menu.addAction(float_action)
        
        close_action = QAction("Cerrar", self)
        close_action.triggered.connect(lambda: self._close_tab(index))
        menu.addAction(close_action)
        
        menu.exec(self.tabs.tabBar().mapToGlobal(position))

    def _float_tab(self, index):
        widget = self.tabs.widget(index)
        title = self.tabs.tabText(index)
        
        # Remover del tab widget sin destruir
        self.tabs.removeTab(index)
        
        # Crear ventana flotante
        float_win = FloatingWindow(widget, title, self)
        float_win.show()
        self.floating_windows.append(float_win)

    def _on_shortcut_event_up(self):
        self._navigate_event(-1)

    def _on_shortcut_event_down(self):
        self._navigate_event(1)

    def _navigate_event(self, direction):
        if not self.cat_events_item: return
        
        # Obtener índice seleccionado actual en el árbol
        current_index = self.tree_view.currentIndex()
        if not current_index.isValid():
            # Si no hay nada seleccionado, empezamos por el primero de eventos
            new_idx = self.cat_events_item.child(0).index()
        else:
            # Seleccionar el siguiente/anterior relativo al actual
            row = current_index.row()
            parent = current_index.parent()
            
            # Si el padre es la categoría de eventos
            if parent == self.cat_events_item.index():
                new_row = (row + direction) % self.cat_events_item.rowCount()
                new_idx = self.cat_events_item.child(new_row).index()
            else:
                # Si no estamos en eventos, forzamos ir al primero de eventos
                new_idx = self.cat_events_item.child(0).index()
        
        self.tree_view.setCurrentIndex(new_idx)
        self._on_tree_double_click(new_idx)

    def _on_action_help(self):
        """Abre el Centro de Ayuda como un Pop-up independiente."""
        from PyQt6.QtWidgets import QDialog
        
        # Crear diálogo si no existe
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("help_title", self.current_lang))
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(500)
        
        lay = QVBoxLayout(dialog)
        help_content = HelpWidget(self)
        lay.addWidget(help_content)
        
        dialog.exec()

    def _check_for_crash_report(self):
        """Busca el archivo de log y pregunta al usuario si desea enviarlo (si está PENDING)."""
        root_dir = os.path.dirname(os.path.abspath(sys.argv[0])) # Usar sys.argv[0] para main.py
        log_path = os.path.join(root_dir, "fomt_studio_error.log")
        
        if not os.path.exists(log_path):
            return

        try:
            with open(log_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            if "[STATUS: PENDING]" not in content:
                return

            # Preguntar al usuario
            reply = QMessageBox.question(
                self, 
                tr("crash_detected_title", self.current_lang),
                tr("crash_detected_msg", self.current_lang),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self._send_error_report(content)

            # Marcar como HANDLED re-escribiendo el archivo
            new_content = content.replace("[STATUS: PENDING]", "[STATUS: HANDLED]")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(new_content)
        except Exception as e:
            print(f"Error al procesar el log de fallos: {e}")

    def _send_error_report(self, log_text):
        """Abre el cliente de correo con el log codificado."""
        email = "fomtstudio.logs@gmail.com" # Placeholder solicitado
        subject = tr("crash_report_subject", self.current_lang)
        
        # Limpiar el texto para el mailto (escapar caracteres especiales)
        # Solo enviamos el contenido útil (después del tag)
        body = log_text.replace("[STATUS: PENDING]", "").strip()
        
        from urllib.parse import quote
        mailto_url = f"mailto:{email}?subject={quote(subject)}&body={quote(body)}"
        
        QDesktopServices.openUrl(QUrl(mailto_url))

    def filter_events(self, event_ids):
        """Oculta todos los eventos excepto los que coinciden con los resultados de búsqueda global."""
        if not self.cat_events: return
        self.tree_view.setUpdatesEnabled(False)
        try:
            for row in range(self.cat_events.rowCount()):
                item = self.cat_events.child(row)
                eid = item.data(Qt.ItemDataRole.UserRole)
                # Ocultar si el ID no está en los resultados
                self.tree_view.setRowHidden(row, self.cat_events.index(), eid not in event_ids)
            
            self.tree_view.expand(self.cat_events.index())
            self.status.showMessage(f"Filtro global activo: {len(event_ids)} resultados.")
        finally:
            self.tree_view.setUpdatesEnabled(True)

    def clear_event_filter(self):
        """Muestra todos los eventos nuevamente."""
        if not self.cat_events: return
        self.tree_view.setUpdatesEnabled(False)
        try:
            for row in range(self.cat_events.rowCount()):
                self.tree_view.setRowHidden(row, self.cat_events.index(), False)
            self.status.showMessage("Filtro global limpiado.")
        finally:
            self.tree_view.setUpdatesEnabled(True)

    def on_search_text_changed(self, text):
        """Filtra el árbol de proyecto según el texto ingresado."""
        text = text.lower().strip()
        self.tree_view.setUpdatesEnabled(False) # Evitar parpadeo
        try:
            for i in range(self.tree_model.rowCount()):
                parent_item = self.tree_model.item(i)
                self._filter_item_recursive(parent_item, text)
            
            if not text:
                # Si se limpia la búsqueda, colapsar categorías grandes por orden
                self.tree_view.collapseAll()
                self.tree_view.expand(self.cat_events.index()) # Mantener eventos expandidos
        finally:
            self.tree_view.setUpdatesEnabled(True)

    def _filter_item_recursive(self, item, text):
        """Oculta/Muestra items recursivamente y expande resultados."""
        has_visible_child = False
        for i in range(item.rowCount()):
            child = item.child(i)
            if self._filter_item_recursive(child, text):
                has_visible_child = True
        
        # Un item es visible si coincide con el texto O si alguno de sus hijos es visible
        match = not text or (text in item.text().lower())
        visible = match or has_visible_child
        
        index = item.index()
        if index.isValid():
            parent_index = index.parent()
            self.tree_view.setRowHidden(index.row(), parent_index, not visible)
            
            # Auto-expandir si hay resultados internos
            if text and has_visible_child:
                self.tree_view.setExpanded(index, True)
        
        return visible
