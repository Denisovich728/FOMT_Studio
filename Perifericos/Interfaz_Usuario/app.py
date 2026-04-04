import os
import re
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QSplitter, QTreeView, QMenuBar, QMenu,
    QStatusBar, QFileDialog, QMessageBox, QLabel
)
from PyQt6.QtCore import Qt, QSettings, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QStandardItemModel, QStandardItem

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
from PyQt6.QtGui import QAction, QShortcut, QKeySequence

class ProjectLoaderThread(QThread):
    progress = pyqtSignal(int, str) # (porcentaje, llave_traduccion)
    finished = pyqtSignal(bool, str)
    step_finished = pyqtSignal(int) # Emite el índice del paso completado

    def __init__(self, mode, rom_path, proj_path):
        super().__init__()
        self.mode = mode # 'new' or 'load'
        self.rom_path = rom_path
        self.proj_path = proj_path
        self.project = None

    def run(self):
        try:
            self.project = FoMTProject()
            if self.mode == 'new':
                # Paso 1: Identificación (Rápido)
                self.progress.emit(10, "status_ready")
                self.project.step_1_detect_rom(self.rom_path, self.proj_path)
                
                # Paso 2: Lógica y Eventos (Rápido)
                self.progress.emit(25, "status_scanning_events")
                self.project.step_2_scan_events()
                self.step_finished.emit(2)
                
                # Paso 3: Gráficos (Lento)
                self.progress.emit(50, "status_scanning_graphics")
                self.project.step_3_scan_graphics()
                self.step_finished.emit(3)
                
                # Paso 4: Audio (Lento)
                self.progress.emit(80, "status_scanning_audio")
                self.project.step_4_scan_audio()
                self.step_finished.emit(4)
                
                self.project.save()
            else:
                self.progress.emit(20, "menu_load")
                self.project.load(self.proj_path)
                
                # Para carga, repetimos el escaneo de fondo si es necesario
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
        self.setWindowTitle("FoMT Studio - The Master Suite")
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
        self.cat_events_item = None # Para navegación rápida
        
        # Configuraciones Persistentes
        self.settings = QSettings("FoMTStudio", "ModdingSuite")
        self.current_lang = self.settings.value("language", "es")
        self.current_theme = self.settings.value("theme", "light")
        self.last_rom_dir = self.settings.value("last_rom_dir", "")
        
        self.last_rom_dir = self.settings.value("last_rom_dir", "")
        
        self._setup_ui()
        self._setup_menu()
        self.apply_theme(self.current_theme)
        self.apply_language(self.current_lang)
        
        # Atajos Globales (Navegación de Eventos)
        QShortcut(QKeySequence("Ctrl+P"), self, self._on_shortcut_event_up)
        QShortcut(QKeySequence("Ctrl+O"), self, self._on_shortcut_event_down)
        
    def _setup_ui(self):
        # Main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Splitter to separate tree from editors
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left Panel (Project Explorer)
        self.tree_view = QTreeView()
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels([tr("explorer_header", self.current_lang)])
        self.tree_view.setModel(self.tree_model)
        splitter.addWidget(self.tree_view)
        
        # Right Panel (Tabbed Editors)
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(False)
        splitter.addWidget(self.tabs)

        # Módulo: Ayuda (Instancia única para diálogos)
        self.help_dialog = None
        
        # Splitter ratio: 1/5 for tree, 4/5 for editors
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([200, 800]) # Forzar tamaños iniciales aproximados
        
        # Status Bar con Progreso
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
        
        # Archivo
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
        
        # Configuración
        config_menu = menubar.addMenu(tr("menu_config", lang))
        
        # Submenú Temas
        theme_menu = config_menu.addMenu(tr("menu_theme", lang))
        light_action = QAction(tr("theme_light", lang), self)
        light_action.triggered.connect(lambda: self.apply_theme("light"))
        dark_action = QAction(tr("theme_dark", lang), self)
        dark_action.triggered.connect(lambda: self.apply_theme("dark"))
        matrix_action = QAction(tr("theme_matrix", lang), self)
        matrix_action.triggered.connect(lambda: self.apply_theme("matrix"))
        theme_menu.addActions([light_action, dark_action, matrix_action])
        
        # Submenú Idiomas
        lang_menu = config_menu.addMenu(tr("menu_lang", lang))
        es_action = QAction(tr("lang_es", lang), self)
        es_action.triggered.connect(lambda: self.apply_language("es"))
        en_action = QAction(tr("lang_en", lang), self)
        en_action.triggered.connect(lambda: self.apply_language("en"))
        jp_action = QAction(tr("lang_jp", lang), self)
        jp_action.triggered.connect(lambda: self.apply_language("jp"))
        lang_menu.addActions([es_action, en_action, jp_action])
        
        # Ayuda
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
        
        # Actualizar IDE si existe
        if self.script_ide:
            self.script_ide.highlighter.update_colors(theme_name)

    def apply_language(self, lang_code):
        self.current_lang = lang_code
        self.settings.setValue("language", lang_code)
        
        self.menuBar().clear()
        self._setup_menu()
        # Actualizar Título y Estado
        title_hint = tr('explorer_title', lang_code)
        self.setWindowTitle(f"FoMT Studio - {title_hint}")
        self.status.showMessage(tr("status_ready", lang_code))
        
        if self.project:
            self._on_project_loaded() # Recarga completa para refrescar todos los textos
        else:
            header_text = tr("explorer_header", lang_code)
            self.tree_model.setHorizontalHeaderLabels([header_text])

    def _update_tree_names(self):
        # Actualizar nombres de categorías en el árbol sin recargar todo
        pass # Implementado dentro de _on_project_loaded por ahora
        
    def action_new_project(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("menu_new", self.current_lang), self.last_rom_dir, "GBA ROM (*.gba)")
        if not path: return
        
        self.last_rom_dir = os.path.dirname(path)
        self.settings.setValue("last_rom_dir", self.last_rom_dir)
        
        proj_dir = QFileDialog.getExistingDirectory(self, "Selecciona Carpeta para tu Nuevo Proyecto FoMT Studio")
        if not proj_dir: return
        
        self._start_async_load('new', path, proj_dir)
            
    def action_load_project(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("menu_load", self.current_lang), "", "FoMT Studio Project (*.fsp *.json)")
        if not path: return
        self._start_async_load('load', None, path)

    def _start_async_load(self, mode, rom_path, proj_path):
        self.status.showMessage("Iniciando tarea de fondo...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.loader_thread = ProjectLoaderThread(mode, rom_path, proj_path)
        # Conectar señales nuevas
        self.loader_thread.progress.connect(self._on_load_progress)
        self.loader_thread.step_finished.connect(self._on_project_step_finished)
        self.loader_thread.finished.connect(self._on_async_load_finished)
        self.loader_thread.start()
        
        # Bloquear UI mínimamente para evitar clics dobles
        self.menuBar().setEnabled(False)
        self.tree_view.setEnabled(False)

    def _on_load_progress(self, value, status_key):
        self.progress_bar.setValue(value)
        self.status.showMessage(tr(status_key, self.current_lang))

    def _on_project_step_finished(self, step):
        """Puebla la UI conforme terminan los pasos de fondo."""
        if not self.project and self.loader_thread:
            self.project = self.loader_thread.project
            
        if step == 2:
            # Paso 2 completado: Ya podemos mostrar la estructura básica
            self._on_project_loaded()
            # Liberar UI para permitir edición mientras sigue escaneando
            self.menuBar().setEnabled(True)
            self.tree_view.setEnabled(True)
        else:
            # Otros pasos: Población incremental
            self._populate_ui_step(step)

    def _on_async_load_finished(self, success, error_msg):
        self.menuBar().setEnabled(True)
        self.tree_view.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if success:
            self.status.showMessage(tr("status_scan_complete", self.current_lang), 5000)
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
            self.project.compile_to_rom(dest)
            self.status.showMessage(f"ROM parcheada y exportada a {dest}!")

    def _on_project_loaded(self):
        """Inicializa la estructura de la UI al detectar la ROM (Paso 2)."""
        self.tabs.clear()
        self.tree_model.clear()
        proj_label = tr("explorer_proj", self.current_lang).format(name=self.project.name)
        self.tree_model.setHorizontalHeaderLabels([proj_label])
        
        root = self.tree_model.invisibleRootItem()
        
        # Categorías persistentes para población incremental
        self.cat_npcs = QStandardItem(tr("cat_npcs", self.current_lang))
        self.cat_items = QStandardItem(tr("cat_items", self.current_lang))
        self.cat_events = QStandardItem(tr("cat_events", self.current_lang))
        self.cat_maps = QStandardItem(tr("cat_maps", self.current_lang))
        self.cat_graphics = QStandardItem("Gráficos")
        self.cat_audio = QStandardItem(tr("tab_audio", self.current_lang))
        
        # Sub-estructuras para gráficos
        self.cat_tilesets = QStandardItem("Tilesets")
        self.cat_palettes = QStandardItem("Paletas")
        self.cat_layouts = QStandardItem("Layouts")
        self.cat_graphics.appendRow(self.cat_tilesets)
        self.cat_graphics.appendRow(self.cat_palettes)
        self.cat_graphics.appendRow(self.cat_layouts)
        
        root.appendRow(self.cat_npcs)
        root.appendRow(self.cat_items)
        root.appendRow(self.cat_events)
        root.appendRow(self.cat_maps)
        root.appendRow(self.cat_graphics)
        root.appendRow(self.cat_audio)

        # Poblar NPCs y Eventos (Paso 2 ya terminó en el thread)
        self._populate_ui_step(2)
        
        # Inicializar Editores Básicos
        self.item_editor = ItemEditorWidget(self.project, self)
        self.tabs.addTab(self.item_editor, tr("tab_items", self.current_lang))
        
        self.npc_editor = NpcEditorWidget(self.project, self)
        self.tabs.addTab(self.npc_editor, tr("tab_npcs", self.current_lang))
        
        self.pointer_editor = MasterPointerEditor(self.project, self)
        self.tabs.addTab(self.pointer_editor, tr("tab_pointers", self.current_lang))
        
        self.script_ide = ScriptIDEWidget(self.project, self)
        self.tabs.addTab(self.script_ide, tr("tab_ide", self.current_lang))
        
        self.visual_maker = VisualEventMaker(self.project, self)
        self.tabs.addTab(self.visual_maker, tr("tab_visual", self.current_lang))
        
        self.map_editor = MapEditorWidget(self)
        self.tabs.addTab(self.map_editor, tr("tab_maps", self.current_lang))

        # Conectar navegación
        self.cat_events_item = self.cat_events
        try: self.tree_view.doubleClicked.disconnect()
        except: pass
        self.tree_view.doubleClicked.connect(self._on_tree_double_click)
        
        self.apply_theme(self.current_theme)

    def _populate_ui_step(self, step):
        """Añade datos a la UI conforme el análisis avanza en segundo plano."""
        if not self.project: return
        
        if step == 2: # NPCs, Eventos y Mapas
            # NPCs
            self.cat_npcs.removeRows(0, self.cat_npcs.rowCount())
            for i, npc in enumerate(self.project.npc_parser.npcs):
                name = npc.name_str.strip('\x00')
                item = QStandardItem(f"[{i:02d}] {name}")
                item.setData("NPC", Qt.ItemDataRole.UserRole + 1)
                item.setData(i, Qt.ItemDataRole.UserRole)
                self.cat_npcs.appendRow(item)
            
            # Eventos
            self.cat_events.removeRows(0, self.cat_events.rowCount())
            self.cat_events.setText(f"{tr('cat_events', self.current_lang)} ({self.project.event_parser.get_event_count()})")
            for i in range(self.project.event_parser.get_event_count()):
                display_name = self.project.super_lib.get_baptized_name(i, "")
                ev_item = QStandardItem(display_name)
                ev_item.setData("EVENT", Qt.ItemDataRole.UserRole + 1)
                ev_item.setData(i, Qt.ItemDataRole.UserRole)
                self.cat_events.appendRow(ev_item)
            
            # Mapas
            self.cat_maps.removeRows(0, self.cat_maps.rowCount())
            for m in self.project.map_parser.maps:
                m_name = self.project.super_lib.get_map_name_hint(m.map_id)
                map_label = "MAPA" if self.current_lang == "es" else "MAP"
                map_item = QStandardItem(f"{map_label} {m.map_id:03d}: {m_name}")
                map_item.setData("MAP", Qt.ItemDataRole.UserRole + 1)
                map_item.setData(m.map_id, Qt.ItemDataRole.UserRole)
                self.cat_maps.appendRow(map_item)
            
            self.tree_view.expand(self.cat_events.index())

        elif step == 3: # Gráficos (StanHash)
            self.cat_tilesets.removeRows(0, self.cat_tilesets.rowCount())
            self.cat_palettes.removeRows(0, self.cat_palettes.rowCount())
            self.cat_layouts.removeRows(0, self.cat_layouts.rowCount())
            
            for offset, info in self.project.super_lib.data_banks.items():
                item = QStandardItem(f"[{offset:06X}] {info['name']}")
                item.setData("GRAPHIC", Qt.ItemDataRole.UserRole + 1)
                item.setData(offset, Qt.ItemDataRole.UserRole)
                
                if info['type'] == "TILESET": self.cat_tilesets.appendRow(item)
                elif info['type'] == "PALETTE": self.cat_palettes.appendRow(item)
                else: self.cat_layouts.appendRow(item)
            
            # Inicializar Visor de Gráficos si no existe
            if not self.tile_viewer:
                self.tile_viewer = TileViewerWidget(self.project, self)
                self.tabs.addTab(self.tile_viewer, "Visor de Gráficos")

        elif step == 4: # Audio (Sappy)
            self.cat_audio.removeRows(0, self.cat_audio.rowCount())
            for i, song in enumerate(self.project.songs):
                name = song.get('name', f"Song_{i}")
                item = QStandardItem(f"[{i:03d}] {name}")
                item.setData("AUDIO", Qt.ItemDataRole.UserRole + 1)
                item.setData(i, Qt.ItemDataRole.UserRole)
                self.cat_audio.appendRow(item)
            
            # Inicializar Visor de Audio si no existe
            if not self.audio_viewer:
                self.audio_viewer = SappyAudioViewer(self.project, self)
                self.tabs.addTab(self.audio_viewer, tr("tab_audio", self.current_lang))
        
    def _on_tree_double_click(self, index):
        item = self.tree_model.itemFromIndex(index)
        if not item: return
        
        type = item.data(Qt.ItemDataRole.UserRole + 1)
        val = item.data(Qt.ItemDataRole.UserRole)
        
        if type == "EVENT":
            event_id = val
            if not self.script_ide: return
            self.tabs.setCurrentWidget(self.script_ide)
            code, stmts = self.project.event_parser.decompile_to_ui(event_id)
            self.script_ide.current_event_id = event_id
            self.script_ide.editor.setPlainText(code)
            if self.visual_maker:
                self.visual_maker.load_statements(event_id, stmts)
            
        elif type == "NPC":
            npc_id = val
            if not self.npc_editor or not self.script_ide: return
            self.tabs.setCurrentWidget(self.npc_editor)
            # Pasamos los datos del NPC al visor de rutinas
            npc_data = self.project.npc_parser.npcs[npc_id]
            code, pseudo = self.project.schedule_parser.decode_npc_schedule(npc_data)
            self.script_ide.editor.setPlainText(code)
            self.tabs.setCurrentWidget(self.script_ide)
            self.status.showMessage(f"Routine Loaded: {npc_data.name_str}")
            
        elif type == "MAP":
            map_id = val
            map_header = self.project.map_parser.maps[map_id]
            if self.map_editor:
                self.map_editor.load_map(map_header)
                self.tabs.setCurrentWidget(self.map_editor)
                self.status.showMessage(f"Map Loaded: {map_id:03d}")
                
        elif type == "GRAPHIC":
            offset = val
            if self.tile_viewer:
                self.tile_viewer.load_graphic(offset)
                self.tabs.setCurrentWidget(self.tile_viewer)
                self.status.showMessage(f"Graphic Bank Loaded: 0x{offset:06X}")
                
        elif type == "AUDIO":
            song_idx = val
            if self.audio_viewer:
                self.tabs.setCurrentWidget(self.audio_viewer)
                self.audio_viewer.song_list.setCurrentRow(song_idx)
                self.status.showMessage(f"Audio Track Selected: {song_idx:03d}")

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
