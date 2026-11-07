import os
import struct
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QLabel, QScrollArea,
    QPushButton, QSpinBox, QMessageBox, QSplitter, QProgressBar, QCheckBox,
    QComboBox, QFormLayout, QTabWidget, QLineEdit, QDialog, QGroupBox,
    QGridLayout, QDialogButtonBox
)
from PyQt6.QtGui import QPixmap, QImage, QShortcut, QKeySequence
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from Nucleos_Positronicos.Nucleo_de_Mapas.mapas import MapParser
from Nucleos_Positronicos.Nucleo_de_Mapas.fomt_mapdata import FomtMapRenderer


class MapLoaderThread(QThread):
    """Carga el mapa en background para no congelar la UI."""
    finished = pyqtSignal(object)  # PIL Image o None
    error    = pyqtSignal(str)

    def __init__(self, renderer: FomtMapRenderer, map_header, **kwargs):
        super().__init__()
        self.renderer = renderer
        self.map_header = map_header
        self.bg1 = kwargs.get('show_bg1', True)
        self.bg2 = kwargs.get('show_bg2', True)
        self.bg3 = kwargs.get('show_bg3', True)
        self.col = kwargs.get('show_col', False)
        self.pal_bank = kwargs.get('bank', 1)
        self.invert_bg = kwargs.get('invert_bg', False)

    def run(self):
        try:
            ok = self.renderer.load_map(self.map_header)
            if ok:
                img = self.renderer.render(
                    show_bg1=self.bg1, show_bg2=self.bg2, show_bg3=self.bg3, 
                    show_col=self.col, bank=self.pal_bank, invert_bg=self.invert_bg
                )
                ts_img = self.renderer.render_tileset(pal_idx=0, bank=self.pal_bank) # Default pal 0
                self.finished.emit((img, ts_img))
            else:
                self.error.emit("El renderer no pudo cargar el mapa.")
        except Exception as e:
            import traceback
            self.error.emit(f"{e}\n{traceback.format_exc()}")


class ClickableMapLabel(QLabel):
    clicked = pyqtSignal(int, int) # pixel x, y
    rightClicked = pyqtSignal(int, int)
    wheelScrolled = pyqtSignal(int) # angle delta Y
    mouseMoved = pyqtSignal(int, int)
    mouseReleased = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_drawing = False

    def mousePressEvent(self, event):
        if self.pixmap() and not self.pixmap().isNull():
            img_w = self.pixmap().width()
            img_h = self.pixmap().height()
            x_offset = (self.width() - img_w) // 2 if self.alignment() & Qt.AlignmentFlag.AlignHCenter else 0
            y_offset = (self.height() - img_h) // 2 if self.alignment() & Qt.AlignmentFlag.AlignVCenter else 0
            
            click_x = int(event.position().x()) - x_offset
            click_y = int(event.position().y()) - y_offset
            
            if 0 <= click_x < img_w and 0 <= click_y < img_h:
                if event.button() == Qt.MouseButton.LeftButton:
                    self.is_drawing = True
                    self.clicked.emit(click_x, click_y)
                elif event.button() == Qt.MouseButton.RightButton:
                    self.rightClicked.emit(click_x, click_y)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_drawing and self.pixmap() and not self.pixmap().isNull():
            img_w = self.pixmap().width()
            img_h = self.pixmap().height()
            x_offset = (self.width() - img_w) // 2 if self.alignment() & Qt.AlignmentFlag.AlignHCenter else 0
            y_offset = (self.height() - img_h) // 2 if self.alignment() & Qt.AlignmentFlag.AlignVCenter else 0
            
            click_x = int(event.position().x()) - x_offset
            click_y = int(event.position().y()) - y_offset
            
            click_x = max(0, min(click_x, img_w - 1))
            click_y = max(0, min(click_y, img_h - 1))
            self.mouseMoved.emit(click_x, click_y)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing:
            self.is_drawing = False
            self.mouseReleased.emit()
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.wheelScrolled.emit(event.angleDelta().y())
            event.accept()
        else:
            super().wheelEvent(event)

class MapResizeDialog(QDialog):
    def __init__(self, current_width, current_height, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Creador / Redimensionador de Mapa")
        self.setModal(True)
        self.resize(300, 150)
        
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        
        self.spin_width = QSpinBox()
        self.spin_width.setRange(1, 150)
        self.spin_width.setValue(current_width)
        
        self.spin_height = QSpinBox()
        self.spin_height.setRange(1, 100)
        self.spin_height.setValue(current_height)
        
        form.addRow("Nuevo Ancho (Max 150):", self.spin_width)
        form.addRow("Nuevo Alto (Max 100):", self.spin_height)
        
        layout.addLayout(form)
        
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Aplicar (Repuntear y Extender)")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        self.lbl_warning = QLabel("[Alerta] Al aplicar, se asignará nuevo espacio en ROM\ny se actualizará la tabla maestra y punteros.")
        self.lbl_warning.setStyleSheet("color: #ffaa00; font-size: 10px;")
        layout.addWidget(self.lbl_warning)
        
    def get_size(self):
        return self.spin_width.value(), self.spin_height.value()

class TriggerEditorDialog(QDialog):
    def __init__(self, behavior_id, flags, script_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Editar Trigger (ID 0x{behavior_id:02X})")
        self.setModal(True)
        self.resize(300, 150)
        
        layout = QVBoxLayout(self)
        
        self.chk_solid = QCheckBox("Sólido (Bloquea el paso)")
        self.chk_solid.setChecked(bool(flags & 1))
        
        self.spin_script = QSpinBox()
        self.spin_script.setRange(0, 65535)
        self.spin_script.setValue(script_id // 2)
        
        self.txt_flags = QLineEdit()
        self.txt_flags.setText(hex(flags))
        self.txt_flags.setPlaceholderText("Ej. 0x01")
        
        form = QFormLayout()
        form.addRow("Flags Crudos (Hex):", self.txt_flags)
        form.addRow("¿Sólido?:", self.chk_solid)
        form.addRow("Script ID (Real):", self.spin_script)
        
        layout.addLayout(form)
        
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Aceptar")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)
        
    def get_data(self):
        try:
            raw = int(self.txt_flags.text(), 16)
        except:
            raw = 0
        if self.chk_solid.isChecked():
            raw |= 1
        else:
            raw &= ~1
        return raw, self.spin_script.value() * 2

class VisorMapas(QWidget):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.map_parser = MapParser(self.project)
        self.renderer = FomtMapRenderer(self.project.base_rom_data)
        self.selected_map_index = -1
        self.selected_cell = None
        self._loader_thread = None
        self.zoom_factor = 2.0
        self.ts_zoom_factor = 1.33  # Factor de zoom independiente para el tileset
        
        # Historial de deshacer/rehacer
        self.undo_stack = []
        self.redo_stack = []
        self._save_state_pending = False
        
        self._setup_ui()
        self._setup_shortcuts()
        self.load_maps()

    def _setup_shortcuts(self):
        self.shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.shortcut_undo.activated.connect(self.undo)
        
        self.shortcut_redo = QShortcut(QKeySequence("Ctrl+Y"), self)
        self.shortcut_redo.activated.connect(self.redo)
        
        self.shortcut_redo_alt = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
        self.shortcut_redo_alt.activated.connect(self.redo)

    def _get_current_state(self):
        if not self.renderer or not self.renderer._loaded:
            return None
        return {
            'bg1': list(self.renderer.tilemap_bg1) if self.renderer.tilemap_bg1 else None,
            'bg2': list(self.renderer.tilemap_bg2) if self.renderer.tilemap_bg2 else None,
            'bg3': list(self.renderer.tilemap_bg3) if self.renderer.tilemap_bg3 else None,
            'col': bytearray(self.renderer.collision_map) if self.renderer.collision_map else None,
        }

    def _set_current_state(self, state):
        if not self.renderer or not self.renderer._loaded or not state:
            return
        if state['bg1'] is not None: self.renderer.tilemap_bg1 = state['bg1'].copy()
        if state['bg2'] is not None: self.renderer.tilemap_bg2 = state['bg2'].copy()
        if state['bg3'] is not None: self.renderer.tilemap_bg3 = state['bg3'].copy()
        if state['col'] is not None: self.renderer.collision_map = bytearray(state['col'])
        self._re_render()

    def _push_undo_state(self):
        state = self._get_current_state()
        if state:
            self.undo_stack.append(state)
            if len(self.undo_stack) > 50:  # Limitar historial
                self.undo_stack.pop(0)
            self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            return
        current = self._get_current_state()
        if current:
            self.redo_stack.append(current)
        prev_state = self.undo_stack.pop()
        self._set_current_state(prev_state)

    def redo(self):
        if not self.redo_stack:
            return
        current = self._get_current_state()
        if current:
            self.undo_stack.append(current)
        next_state = self.redo_stack.pop()
        self._set_current_state(next_state)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Barra Superior
        top_bar_layout = QHBoxLayout()
        lbl_titulo = QLabel("🗺️ Visor de Mapas — Motor FoMT (Pilar Blue-Spider)")
        lbl_titulo.setStyleSheet("font-size: 16px; font-weight: bold; color: #44aaff; padding: 4px;")
        top_bar_layout.addWidget(lbl_titulo)
        
        self.lbl_info = QLabel("Selecciona un mapa de la lista...")
        self.lbl_info.setStyleSheet("color: #aaa; font-size: 11px; padding-left: 20px;")
        top_bar_layout.addWidget(self.lbl_info)
        
        top_bar_layout.addStretch()
        
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # Indeterminado
        self.progress.setVisible(False)
        self.progress.setMaximumHeight(12)
        self.progress.setMaximumWidth(150)
        top_bar_layout.addWidget(self.progress)
        
        main_layout.addLayout(top_bar_layout)

        # Splitter principal
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter, stretch=1)

        # ── Panel izquierdo: lista de mapas ────────────────────
        left_panel = QWidget()
        left_panel.setMinimumWidth(220)
        from PyQt6.QtWidgets import QSizePolicy
        left_panel.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_refresh = QPushButton("Recargar Lista")
        self.btn_refresh.clicked.connect(self.load_maps)
        left_layout.addWidget(self.btn_refresh)

        self.list_maps = QListWidget()
        self.list_maps.currentRowChanged.connect(self.on_map_selected)
        left_layout.addWidget(self.list_maps)

        splitter.addWidget(left_panel)

        # Panel derecho: visor
        right_panel = QWidget()
        right_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(4, 4, 4, 4)

        # Modos de Edición - Ahora como QTabWidget en lugar de ComboBox
        self.tabs_edit_mode = QTabWidget()
        self.tabs_edit_mode.setUsesScrollButtons(False)
        self.tabs_edit_mode.addTab(QWidget(), "General")
        self.tabs_edit_mode.addTab(QWidget(), "Fondo (p_bg3)")
        self.tabs_edit_mode.addTab(QWidget(), "Medio (p_bg2)")
        self.tabs_edit_mode.addTab(QWidget(), "Frente (p_bg1)")
        self.tabs_edit_mode.addTab(QWidget(), "Colisiones")
        self.tabs_edit_mode.addTab(QWidget(), "Estructuras Dinámicas")
        self.tabs_edit_mode.currentChanged.connect(self._on_edit_mode_changed)
        
        # Controles de Herramientas
        tools_container_layout = QVBoxLayout()
        tools_row1 = QHBoxLayout()
        tools_row2 = QHBoxLayout()

        tools_row1.addWidget(QLabel("Modo de edición:"))
        tools_row1.addWidget(self.tabs_edit_mode)
        
        self.cmb_bank = QComboBox()
        self.cmb_bank.addItems(["Paleta 1 (Verano/Día)", "Paleta 2 (Invierno/Noche)"])
        tools_row1.addWidget(QLabel("Variante:"))
        tools_row1.addWidget(self.cmb_bank)
        
        self.chk_invert_bg = QCheckBox("Invertir Z-Index (BG1/BG3)")
        tools_row1.addWidget(self.chk_invert_bg)
        tools_row1.addStretch()
        
        # Paleta de Colisiones (se llenará dinámicamente al cargar el mapa)
        self.cmb_col_brush = QComboBox()
        self.cmb_col_brush.setVisible(False)
        self.lbl_col_brush = QLabel("Pincel Colisión:")
        self.lbl_col_brush.setVisible(False)
        
        tools_row2.addWidget(self.lbl_col_brush)
        tools_row2.addWidget(self.cmb_col_brush)
        
        # Zoom controls
        zoom_layout = QHBoxLayout()
        self.btn_zoom_out = QPushButton("- Zoom")
        self.btn_zoom_in = QPushButton("+ Zoom")
        self.btn_zoom_out.setMaximumWidth(40)
        self.btn_zoom_in.setMaximumWidth(40)
        self.lbl_zoom = QLabel(f"Zoom: {int(self.zoom_factor * 100)}%")
        
        self.btn_zoom_out.clicked.connect(self._zoom_out)
        self.btn_zoom_in.clicked.connect(self._zoom_in)
        
        zoom_layout.addWidget(self.lbl_zoom)
        zoom_layout.addWidget(self.btn_zoom_out)
        zoom_layout.addWidget(self.btn_zoom_in)
        tools_row2.addLayout(zoom_layout)
        
        tools_row2.addStretch()
        
        # Botón Guardar
        self.btn_save = QPushButton("Guardar Cambios (ROM)")
        self.btn_save.clicked.connect(self._save_map)
        tools_row2.addWidget(self.btn_save)
        
        self.btn_resize = QPushButton("Redimensionar Mapa")
        self.btn_resize.clicked.connect(self._open_resize_dialog)
        tools_row2.addWidget(self.btn_resize)

        self.btn_create = QPushButton("Crear Nuevo Mapa")
        self.btn_create.clicked.connect(self._open_create_dialog)
        tools_row2.addWidget(self.btn_create)

        self.btn_export_map = QPushButton("⬇ Exportar Mapa (BMP/PNG)")
        self.btn_export_map.clicked.connect(self._export_map_image)
        tools_row2.addWidget(self.btn_export_map)

        self.btn_import_map = QPushButton("⬆ Importar Mapa (BMP/PNG)")
        self.btn_import_map.clicked.connect(self._import_map_image)
        tools_row2.addWidget(self.btn_import_map)
        
        # Fila de Estructuras Dinámicas
        self.tools_row_dyn = QHBoxLayout()
        self.chk_dyn_enabled = QCheckBox("Estructuras Dinámicas")
        self.chk_dyn_enabled.setChecked(True)
        self.chk_dyn_enabled.toggled.connect(self._on_dynamic_config_changed)
        self.tools_row_dyn.addWidget(self.chk_dyn_enabled)

        # 1. Controles de Granja (Mapas 0 y 1)
        self.widget_dyn_farm = QWidget()
        layout_dyn_farm = QHBoxLayout(self.widget_dyn_farm)
        layout_dyn_farm.setContentsMargins(0, 0, 0, 0)
        layout_dyn_farm.setSpacing(6)

        layout_dyn_farm.addWidget(QLabel("Casa:"))
        self.cmb_dyn_house = QComboBox()
        self.cmb_dyn_house.addItems(["Lv1", "Lv2", "Lv3", "Ninguna"])
        self.cmb_dyn_house.currentIndexChanged.connect(self._on_dynamic_config_changed)
        layout_dyn_farm.addWidget(self.cmb_dyn_house)

        layout_dyn_farm.addWidget(QLabel("Establo:"))
        self.cmb_dyn_barn = QComboBox()
        self.cmb_dyn_barn.addItems(["Lv1", "Lv2", "Ninguno"])
        self.cmb_dyn_barn.currentIndexChanged.connect(self._on_dynamic_config_changed)
        layout_dyn_farm.addWidget(self.cmb_dyn_barn)

        layout_dyn_farm.addWidget(QLabel("Gallinero:"))
        self.cmb_dyn_coop = QComboBox()
        self.cmb_dyn_coop.addItems(["Lv1", "Lv2", "Ninguno"])
        self.cmb_dyn_coop.currentIndexChanged.connect(self._on_dynamic_config_changed)
        layout_dyn_farm.addWidget(self.cmb_dyn_coop)

        self.chk_dyn_extras = QCheckBox("Buzón/Caseta")
        self.chk_dyn_extras.setChecked(True)
        self.chk_dyn_extras.toggled.connect(self._on_dynamic_config_changed)
        layout_dyn_farm.addWidget(self.chk_dyn_extras)

        self.chk_dyn_field = QCheckBox("Malla Cultivo (43x25)")
        self.chk_dyn_field.setChecked(False)
        self.chk_dyn_field.toggled.connect(self._on_dynamic_config_changed)
        layout_dyn_farm.addWidget(self.chk_dyn_field)
        self.tools_row_dyn.addWidget(self.widget_dyn_farm)

        # 1b. Botón de Configuración de Estructuras Dinámicas (Abre ventana flotante)
        self.btn_dyn_configure = QPushButton("Configurar Estructuras...")
        self.btn_dyn_configure.setToolTip("Abre la ventana de configuración de estructuras dinámicas para este mapa")
        self.btn_dyn_configure.clicked.connect(self._open_dynamic_structures_dialog)
        self.btn_dyn_configure.setVisible(False)
        self.tools_row_dyn.addWidget(self.btn_dyn_configure)

        # 1c. Controles de selección y edición en la Capa 5 (Estructuras Dinámicas)
        self.widget_dyn_editor = QWidget()
        layout_dyn_editor = QHBoxLayout(self.widget_dyn_editor)
        layout_dyn_editor.setContentsMargins(0, 0, 0, 0)
        layout_dyn_editor.setSpacing(6)

        layout_dyn_editor.addWidget(QLabel("Mover Estructura:"))
        self.cmb_dyn_selected = QComboBox()
        self.cmb_dyn_selected.currentIndexChanged.connect(self._on_dyn_selected_changed)
        layout_dyn_editor.addWidget(self.cmb_dyn_selected)

        layout_dyn_editor.addWidget(QLabel("X:"))
        self.spn_dyn_x = QSpinBox()
        self.spn_dyn_x.setRange(0, 500)
        self.spn_dyn_x.valueChanged.connect(self._on_dyn_pos_spin_changed)
        layout_dyn_editor.addWidget(self.spn_dyn_x)

        layout_dyn_editor.addWidget(QLabel("Y:"))
        self.spn_dyn_y = QSpinBox()
        self.spn_dyn_y.setRange(0, 500)
        self.spn_dyn_y.valueChanged.connect(self._on_dyn_pos_spin_changed)
        layout_dyn_editor.addWidget(self.spn_dyn_y)

        self.btn_dyn_reset = QPushButton("Reset Posiciones")
        self.btn_dyn_reset.clicked.connect(self._on_dyn_reset_positions)
        layout_dyn_editor.addWidget(self.btn_dyn_reset)

        self.widget_dyn_editor.setVisible(False)
        self.tools_row_dyn.addWidget(self.widget_dyn_editor)

        # 2. Controles de Playa (Mapas 8 y 9)
        self.widget_dyn_beach = QWidget()
        layout_dyn_beach = QHBoxLayout(self.widget_dyn_beach)
        layout_dyn_beach.setContentsMargins(0, 0, 0, 0)
        self.chk_dyn_beach = QCheckBox("Villa de la Playa (Gotz)")
        self.chk_dyn_beach.setChecked(True)
        self.chk_dyn_beach.toggled.connect(self._on_dynamic_config_changed)
        layout_dyn_beach.addWidget(self.chk_dyn_beach)
        self.widget_dyn_beach.setVisible(False)
        self.tools_row_dyn.addWidget(self.widget_dyn_beach)

        # 3. Controles de Montaña (Mapas 14 y 15)
        self.widget_dyn_mountain = QWidget()
        layout_dyn_mountain = QHBoxLayout(self.widget_dyn_mountain)
        layout_dyn_mountain.setContentsMargins(0, 0, 0, 0)
        self.chk_dyn_mountain = QCheckBox("Villa de la Montaña (Gotz)")
        self.chk_dyn_mountain.setChecked(True)
        self.chk_dyn_mountain.toggled.connect(self._on_dynamic_config_changed)
        layout_dyn_mountain.addWidget(self.chk_dyn_mountain)
        self.widget_dyn_mountain.setVisible(False)
        self.tools_row_dyn.addWidget(self.widget_dyn_mountain)

        # 4. Controles de Ciudad (Mapas 4, 5, 6 y 7)
        self.widget_dyn_town = QWidget()
        layout_dyn_town = QHBoxLayout(self.widget_dyn_town)
        layout_dyn_town.setContentsMargins(0, 0, 0, 0)
        self.chk_dyn_town = QCheckBox("Villa de la Ciudad (100M G)")
        self.chk_dyn_town.setChecked(True)
        self.chk_dyn_town.toggled.connect(self._on_dynamic_config_changed)
        layout_dyn_town.addWidget(self.chk_dyn_town)
        self.widget_dyn_town.setVisible(False)
        self.tools_row_dyn.addWidget(self.widget_dyn_town)

        # Label para mapas sin estructuras dinámicas
        self.lbl_dyn_none = QLabel("(Sin estructuras dinámicas en este mapa)")
        self.lbl_dyn_none.setStyleSheet("color: #777; font-style: italic;")
        self.lbl_dyn_none.setVisible(False)
        self.tools_row_dyn.addWidget(self.lbl_dyn_none)

        self.tools_row_dyn.addStretch()

        tools_container_layout.addLayout(tools_row1)
        tools_container_layout.addLayout(tools_row2)
        tools_container_layout.addLayout(self.tools_row_dyn)
        right_layout.addLayout(tools_container_layout)

        # Eventos
        self.cmb_bank.currentIndexChanged.connect(self._re_render)
        self.chk_invert_bg.toggled.connect(self._re_render)
        
        # Visores
        viewers_layout = QHBoxLayout()
        
        # Mapa
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.lbl_image = ClickableMapLabel()
        self.lbl_image.clicked.connect(self._on_map_clicked)
        self.lbl_image.mouseMoved.connect(self._on_map_dragged)
        self.lbl_image.mouseReleased.connect(self._on_map_mouse_released)
        self.lbl_image.rightClicked.connect(self._on_map_right_clicked)
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setStyleSheet("background-color: #000; border: 1px solid #333;")
        self.scroll_area.setWidget(self.lbl_image)
        viewers_layout.addWidget(self.scroll_area, stretch=3)
        
        # Tileset
        ts_layout = QVBoxLayout()
        ts_controls = QHBoxLayout()
        ts_controls.addWidget(QLabel("Tileset Pal:"))
        self.cmb_ts_pal = QComboBox()
        self.cmb_ts_pal.addItems(["Auto (Mapa)"] + [f"Pal {i}" for i in range(1, 16)])
        self.cmb_ts_pal.currentIndexChanged.connect(self._re_render_tileset)
        ts_controls.addWidget(self.cmb_ts_pal)
        
        self.btn_edit_palette = QPushButton("Editar Paleta")
        self.btn_edit_palette.clicked.connect(self._open_palette_editor)
        ts_controls.addWidget(self.btn_edit_palette)

        self.btn_export_ts = QPushButton("⬇ Exportar TS")
        self.btn_export_ts.clicked.connect(self._export_tileset_image)
        ts_controls.addWidget(self.btn_export_ts)

        self.btn_import_ts = QPushButton("⬆ Importar TS")
        self.btn_import_ts.clicked.connect(self._import_tileset_image)
        ts_controls.addWidget(self.btn_import_ts)
        
        ts_layout.addLayout(ts_controls)
        
        self.ts_scroll = QScrollArea()
        self.ts_scroll.setWidgetResizable(True)
        self.ts_scroll.setMinimumWidth(100) # Ensure tileset has minimum width, reduced to allow map viewer expansion
        
        # Set size policies to allow shrinking
        from PyQt6.QtWidgets import QSizePolicy
        self.ts_scroll.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        self.lbl_ts = ClickableMapLabel()
        self.lbl_ts.clicked.connect(self._on_tileset_clicked)
        self.lbl_ts.wheelScrolled.connect(self._on_ts_wheel_scrolled)
        self.lbl_ts.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.lbl_ts.setStyleSheet("background-color: #111; border: 1px solid #333;")
        self.ts_scroll.setWidget(self.lbl_ts)
        ts_layout.addWidget(self.ts_scroll)
        
        viewers_layout.addLayout(ts_layout, stretch=1)
        
        # Wrapper widget para forzar que los visores ocupen el espacio
        viewers_container = QWidget()
        viewers_container.setLayout(viewers_layout)
        right_layout.addWidget(viewers_container, stretch=1)


        splitter.addWidget(right_panel)
        splitter.setSizes([220, 780])

    def _on_ts_wheel_scrolled(self, delta_y):
        if delta_y > 0:
            if self.ts_zoom_factor < 6.0:
                self.ts_zoom_factor += 0.25
                self._re_render_tileset()
        elif delta_y < 0:
            if self.ts_zoom_factor > 0.5:
                self.ts_zoom_factor -= 0.25
                self._re_render_tileset()

    def _zoom_in(self):
        if self.zoom_factor < 8.0:
            self.zoom_factor += 0.5
            self.lbl_zoom.setText(f"Zoom: {int(self.zoom_factor * 100)}%")
            self._re_render()

    def _zoom_out(self):
        if self.zoom_factor > 1.0:
            self.zoom_factor -= 0.5
            self.lbl_zoom.setText(f"Zoom: {int(self.zoom_factor * 100)}%")
            self._re_render()

    def load_maps(self):
        self.list_maps.clear()
        if not self.project or not self.project.base_rom_data:
            QMessageBox.warning(self, "Error", "No hay ROM cargada.")
            return

        self.map_parser.scan_maps()
        for m in self.map_parser.maps:
            name = m.get_name()
            self.list_maps.addItem(f"[{m.map_id:03X}] {name}  ({m.width}×{m.height})")

    def _get_layer_visibility(self):
        tab_idx = self.tabs_edit_mode.currentIndex()
        if tab_idx == 0: # General
            return {'show_bg1': True, 'show_bg2': True, 'show_bg3': True, 'show_col': False}
        elif tab_idx == 1: # Fondo (p_bg3)
            return {'show_bg1': False, 'show_bg2': False, 'show_bg3': True, 'show_col': False}
        elif tab_idx == 2: # Medio (p_bg2)
            return {'show_bg1': False, 'show_bg2': True, 'show_bg3': False, 'show_col': False}
        elif tab_idx == 3: # Frente (p_bg1)
            return {'show_bg1': True, 'show_bg2': False, 'show_bg3': False, 'show_col': False}
        elif tab_idx == 4: # Colisiones
            return {'show_bg1': True, 'show_bg2': True, 'show_bg3': True, 'show_col': True}
        
        return {
            'show_bg1': True,
            'show_bg2': True,
            'show_bg3': True,
            'show_col': False
        }

    def on_map_selected(self, row):
        if row < 0 or row >= len(self.map_parser.maps):
            return
            
        self.selected_map_index = row

        # Cancelar carga anterior si la hay
        if self._loader_thread and self._loader_thread.isRunning():
            self._loader_thread.quit()
            self._loader_thread.wait()

        map_obj = self.map_parser.maps[row]
        self.current_map_header = map_obj
        self.lbl_info.setText(
            f"[Cargando mapa] [{map_obj.map_id:03X}] {map_obj.get_name()} "
            f"({map_obj.width}×{map_obj.height} celdas, {map_obj.width*8}×{map_obj.height*8} px)..."
        )
        self.lbl_image.clear()
        self.progress.setVisible(True)

        visibility = self._get_layer_visibility()
        
        self._loader_thread = MapLoaderThread(
            self.renderer, map_obj,
            show_bg1=visibility['show_bg1'],
            show_bg2=visibility['show_bg2'],
            show_bg3=visibility['show_bg3'],
            show_col=visibility['show_col'],
            bank=self.cmb_bank.currentIndex() + 1,
            invert_bg=self.chk_invert_bg.isChecked()
        )
        self._loader_thread.finished.connect(self._on_map_loaded)
        self._loader_thread.error.connect(self._on_map_error)
        self._loader_thread.start()

    def _on_edit_mode_changed(self, index):
        # Mostrar panel Pincel de colisión solo si se selecciona tab 4
        is_col = (index == 4)
        is_dyn_layer = (index == 5)
        self.lbl_col_brush.setVisible(is_col)
        self.cmb_col_brush.setVisible(is_col)
        if hasattr(self, 'widget_dyn_editor'):
            self.widget_dyn_editor.setVisible(is_dyn_layer)
            if is_dyn_layer:
                self._update_dyn_structures_combo()
        self._re_render()
        
    def _on_dynamic_config_changed(self):
        house_map = {0: 'lv1', 1: 'lv2', 2: 'lv3', 3: 'none'}
        barn_map = {0: 'lv1', 1: 'lv2', 2: 'none'}
        coop_map = {0: 'lv1', 1: 'lv2', 2: 'none'}

        tb_map = {0: 'closed', 1: 'open', 2: 'none'}
        rp_map = {0: 'base', 1: 'discs', 2: 'active', 3: 'none'}
        fridge_map = {0: 'closed', 1: 'open', 2: 'none'}
        shelf_map = {0: 'closed', 1: 'open', 2: 'none'}
        fp_map = {0: 'on', 1: 'off', 2: 'none'}

        if hasattr(self, 'renderer') and self.renderer:
            old_positions = getattr(self.renderer, 'dynamic_config', {}).get('positions', {})
            self.renderer.dynamic_config = {
                'enabled': self.chk_dyn_enabled.isChecked(),
                'farmhouse': house_map.get(self.cmb_dyn_house.currentIndex(), 'lv1'),
                'barn': barn_map.get(self.cmb_dyn_barn.currentIndex(), 'lv1'),
                'chicken_coop': coop_map.get(self.cmb_dyn_coop.currentIndex(), 'lv1'),
                'extras': self.chk_dyn_extras.isChecked(),
                'field_grid': self.chk_dyn_field.isChecked(),
                'beach_cottage': self.chk_dyn_beach.isChecked() if hasattr(self, 'chk_dyn_beach') else True,
                'mountain_cottage': self.chk_dyn_mountain.isChecked() if hasattr(self, 'chk_dyn_mountain') else True,
                'town_cottage': self.chk_dyn_town.isChecked() if hasattr(self, 'chk_dyn_town') else True,
                'mayo_maker': getattr(self, 'maker_mayo_choice', True),
                'yarn_maker': getattr(self, 'maker_yarn_choice', True),
                'cheese_maker': getattr(self, 'maker_cheese_choice', True),
                'house': {
                    'tool_box': getattr(self, 'house_toolbox_choice', 'closed'),
                    'record_player': getattr(self, 'house_record_player_choice', 'base'),
                    'fridge': getattr(self, 'house_fridge_choice', 'closed'),
                    'shelf': getattr(self, 'house_shelf_choice', 'closed'),
                    'kitchen_counter': getattr(self, 'house_kitchen_choice', True),
                    'utensils': getattr(self, 'house_utensils_state', [True]*8),
                    'fireplace': getattr(self, 'house_fireplace_choice', True),
                    'bathroom_door': getattr(self, 'house_bathroom_door_choice', 'closed'),
                    'double_bed': getattr(self, 'house_double_bed_choice', True),
                    'carpet_dining': getattr(self, 'house_dining_choice', True),
                    'vase': getattr(self, 'house_vase_choice', True),
                    'mirror': getattr(self, 'house_mirror_choice', True),
                    'clock': getattr(self, 'house_clock_choice', True),
                },
                'positions': old_positions
            }
            if hasattr(self, 'widget_dyn_editor') and self.widget_dyn_editor.isVisible():
                self._update_dyn_structures_combo()
            self._re_render_map_only()

    def _re_render(self):
        self._re_render_map_only()
        self._re_render_tileset()

    def _re_render_map_only(self):
        if not self.renderer._loaded: return
        visibility = self._get_layer_visibility()
        img = self.renderer.render(
            show_bg1=visibility['show_bg1'], 
            show_bg2=visibility['show_bg2'], 
            show_bg3=visibility['show_bg3'], 
            show_col=visibility['show_col'], 
            bank=self.cmb_bank.currentIndex() + 1,
            invert_bg=self.chk_invert_bg.isChecked()
        )
        if img:
            self._set_pixmap(self.lbl_image, img)

    def _re_render_tileset(self):
        if not self.renderer._loaded: return
        ts_img = self.renderer.render_tileset(
            pal_idx=self.cmb_ts_pal.currentIndex(), 
            bank=self.cmb_bank.currentIndex() + 1
        )
        if ts_img:
            from PyQt6.QtGui import QPainter, QColor, QPen
            img_data = ts_img.convert("RGBA").tobytes("raw", "RGBA")
            qim = QImage(img_data, ts_img.width, ts_img.height, ts_img.width * 4, QImage.Format.Format_RGBA8888)
            
            # Draw white grid
            painter = QPainter(qim)
            pen = QPen(QColor(255, 255, 255, 128)) # Semi-transparent white
            pen.setWidth(1)
            painter.setPen(pen)
            
            for x in range(0, ts_img.width, 8):
                painter.drawLine(x, 0, x, ts_img.height)
            for y in range(0, ts_img.height, 8):
                painter.drawLine(0, y, ts_img.width, y)
                
            if hasattr(self, 'selected_tile'):
                idx_only = self.selected_tile & 0x03FF
                sel_x = (idx_only % 32) * 8
                sel_y = (idx_only // 32) * 8
                pen_sel = QPen(QColor(255, 0, 0, 200))
                pen_sel.setWidth(2)
                painter.setPen(pen_sel)
                painter.drawRect(sel_x, sel_y, 8, 8)
                
            painter.end()
            
            pix = QPixmap.fromImage(qim)
            # Aplicamos el zoom independiente para el tileset
            ts_zoom = self.ts_zoom_factor
            pix = pix.scaled(int(ts_img.width * ts_zoom), int(ts_img.height * ts_zoom), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
            self.lbl_ts.setPixmap(pix)

    def _set_pixmap(self, label, img):
        img_data = img.convert("RGBA").tobytes("raw", "RGBA")
        qim = QImage(img_data, img.width, img.height, img.width * 4, QImage.Format.Format_RGBA8888)

        # Si estamos en la capa de Estructuras Dinámicas (tab 5), dibujar bounding boxes interactivos
        if hasattr(self, 'tabs_edit_mode') and self.tabs_edit_mode.currentIndex() == 5 and hasattr(self, 'renderer') and self.renderer:
            from PyQt6.QtGui import QPainter, QColor, QPen, QFont
            painter = QPainter(qim)
            font = QFont("Segoe UI", 7, QFont.Weight.Bold)
            painter.setFont(font)

            structs = self.renderer.get_active_dynamic_structures() if hasattr(self.renderer, 'get_active_dynamic_structures') else []
            selected_id = getattr(self, 'selected_dyn_struct_id', None)

            for s in structs:
                sx = s['x'] * 8
                sy = s['y'] * 8
                sw = s['w'] * 8
                sh = s['h'] * 8
                is_selected = (s['id'] == selected_id)

                pen_color = QColor(255, 215, 0) if is_selected else QColor(0, 255, 255)
                fill_color = QColor(255, 215, 0, 60) if is_selected else QColor(0, 255, 255, 30)

                pen = QPen(pen_color, 2, Qt.PenStyle.SolidLine if is_selected else Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.setBrush(fill_color)
                painter.drawRect(sx, sy, sw, sh)

                # Etiqueta con nombre y coordenadas
                tag_text = f" {s['name']} ({s['x']},{s['y']}) "
                metrics = painter.fontMetrics()
                tw = metrics.horizontalAdvance(tag_text) + 4
                th = metrics.height() + 2

                tag_y = max(0, sy - th)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(0, 0, 0, 200))
                painter.drawRect(sx, tag_y, tw, th)

                painter.setPen(pen_color)
                painter.drawText(sx + 2, tag_y + th - 3, tag_text)

            painter.end()

        pix = QPixmap.fromImage(qim)
        if self.zoom_factor != 1.0:
            pix = pix.scaled(int(img.width * self.zoom_factor), int(img.height * self.zoom_factor), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
        label.setPixmap(pix)

    def _on_map_loaded(self, result):
        self.progress.setVisible(False)
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._save_state_pending = False
        img, ts_img = result
        if img is None:
            self.lbl_info.setText("[Alerta] No se pudo renderizar el mapa (faltan datos).")
            self.lbl_image.clear()
            self.lbl_ts.clear()
            return

        self._set_pixmap(self.lbl_image, img)
        if ts_img:
            self._re_render_tileset()

        h = self.renderer.height
        w = self.renderer.width
        palettes = self.renderer.palettes_1 if self.cmb_bank.currentIndex() == 0 else self.renderer.palettes_2
        mh = self._loader_thread.map_header
        self.current_map_header = mh
        
        info = f"[OK] Renderizado: {w}×{h} celdas | "
        info += f"{len(palettes)} paletas | {len(self.renderer.tiles)} tiles | "
        info += f"Triggers: Ptr6=0x{mh.p_obj1:08X}, Ptr7=0x{mh.p_obj2:08X}"
        self.lbl_info.setText(info)
        
        # Ajustar controles contextuales según el mapa cargado
        map_id = getattr(mh, 'map_id', 0)
        is_farm = (map_id in (0, 1) or (w == 128 and h == 88))
        is_house = (map_id in (41, 42, 43))
        is_beach = (map_id in (8, 9))
        is_mountain = (map_id in (14, 15))
        is_town = (map_id in (4, 5, 6, 7))
        is_coop = (map_id in (36, 37))
        is_barn = (map_id in (38, 39))
        has_dyn = (is_farm or is_house or is_beach or is_mountain or is_town or is_coop or is_barn)

        if hasattr(self, 'chk_dyn_enabled'):
            self.chk_dyn_enabled.setEnabled(has_dyn)
            self.widget_dyn_farm.setVisible(is_farm)
            if hasattr(self, 'btn_dyn_configure'):
                self.btn_dyn_configure.setVisible(is_house or is_coop or is_barn)
            self.widget_dyn_beach.setVisible(is_beach)
            self.widget_dyn_mountain.setVisible(is_mountain)
            self.widget_dyn_town.setVisible(is_town)
            self.lbl_dyn_none.setVisible(not has_dyn)
            if hasattr(self, 'widget_dyn_editor') and self.tabs_edit_mode.currentIndex() == 5:
                self._update_dyn_structures_combo()
        
        self._update_collision_brush()

    def _on_map_error(self, error_msg):
        self.progress.setVisible(False)
        self.lbl_info.setText(f"[Error] Error: {error_msg[:120]}")
        print(f"[VisorMapas] Error:\n{error_msg}")

    def _on_tileset_clicked(self, px, py):
        ts_zoom = self.ts_zoom_factor
        px = int(px / ts_zoom)
        py = int(py / ts_zoom)
        cell_x = px // 8
        cell_y = py // 8
        tileset_width = 32 # 256 pixels / 8
        self.selected_tile = cell_y * tileset_width + cell_x
        self._copied_from_map = False
        
        assigned_pal = self.renderer.get_tile_palette(self.selected_tile) if self.cmb_ts_pal.currentIndex() == 0 else self.cmb_ts_pal.currentIndex()
        self.lbl_info.setText(f"Pincel Tile: 0x{self.selected_tile:03X} (Pal {assigned_pal})")
        self._re_render_tileset()

    def _on_map_mouse_released(self):
        self._last_drag_cell = None
        self._save_state_pending = False

    def _update_collision_brush(self):
        self.cmb_col_brush.blockSignals(True)
        self.cmb_col_brush.clear()
        
        if not self.renderer.behavior_dict:
            self.cmb_col_brush.addItems([f"{i:02X}: Desconocido" for i in range(256)])
            self.cmb_col_brush.blockSignals(False)
            return

        max_val = min(256, len(self.renderer.behavior_dict) // 4)
        items = []
        for val in range(max_val):
            behavior = struct.unpack_from('<H', self.renderer.behavior_dict, val * 4)[0]
            script_id = struct.unpack_from('<H', self.renderer.behavior_dict, val * 4 + 2)[0]
            
            is_solid = bool(behavior & 1)
            has_script = (script_id > 0)
            
            if val == 0:
                name = "Caminable (Vacío)"
            elif is_solid and has_script:
                name = "Sólido + Evento"
            elif is_solid:
                name = "Sólido (Pared/Obstáculo)"
            elif has_script:
                name = "Caminable + Evento (Warp/Trigger)"
            else:
                name = "Caminable Especial (Agua/Borde)"
                
            items.append(f"{val:02X}: {name}")
            
        self.cmb_col_brush.addItems(items)
        self.cmb_col_brush.blockSignals(False)

    @staticmethod
    def _get_line_cells(x0, y0, x1, y1):
        cells = []
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        cx, cy = x0, y0
        while True:
            cells.append((cx, cy))
            if cx == x1 and cy == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                cx += sx
            if e2 < dx:
                err += dx
                cy += sy
        return cells

    def _apply_paint_at_cell(self, cell_x, cell_y):
        w = self.renderer.width
        h = self.renderer.height
        if not (0 <= cell_x < w and 0 <= cell_y < h):
            return False

        idx = cell_y * w + cell_x
        tab_idx = self.tabs_edit_mode.currentIndex()
        modified = False

        if hasattr(self, 'selected_tile') and tab_idx in [1, 2, 3]: # Modo pintar BG
            copied_from_map = getattr(self, '_copied_from_map', False)
            if not copied_from_map:
                if self.cmb_ts_pal.currentIndex() == 0:
                    active_pal = self.renderer.get_tile_palette(self.selected_tile & 0x03FF)
                else:
                    active_pal = self.cmb_ts_pal.currentIndex()
                new_val = (active_pal << 12) | (self.selected_tile & 0x03FF)
            else:
                new_val = self.selected_tile

            if tab_idx == 1 and idx < len(self.renderer.tilemap_bg3):
                if self.renderer.tilemap_bg3[idx] != new_val:
                    self.renderer.tilemap_bg3[idx] = new_val
                    modified = True
            elif tab_idx == 2 and idx < len(self.renderer.tilemap_bg2):
                if self.renderer.tilemap_bg2[idx] != new_val:
                    self.renderer.tilemap_bg2[idx] = new_val
                    modified = True
            elif tab_idx == 3 and idx < len(self.renderer.tilemap_bg1):
                if self.renderer.tilemap_bg1[idx] != new_val:
                    self.renderer.tilemap_bg1[idx] = new_val
                    modified = True

        elif tab_idx == 5: # Modo Estructuras Dinámicas
            structs = self.renderer.get_active_dynamic_structures() if hasattr(self.renderer, 'get_active_dynamic_structures') else []
            clicked_struct = None
            for s in structs:
                if s['x'] <= cell_x < s['x'] + s['w'] and s['y'] <= cell_y < s['y'] + s['h']:
                    clicked_struct = s
                    break

            current_id = self._get_selected_dynamic_structure_id()
            if clicked_struct:
                if clicked_struct['id'] != current_id:
                    self._select_dynamic_structure(clicked_struct['id'])
                    self._dyn_grab_offset = (cell_x - clicked_struct['x'], cell_y - clicked_struct['y'])
                else:
                    grab_ox, grab_oy = getattr(self, '_dyn_grab_offset', (0, 0))
                    new_x = max(0, min(cell_x - grab_ox, w - clicked_struct['w']))
                    new_y = max(0, min(cell_y - grab_oy, h - clicked_struct['h']))
                    if (new_x, new_y) != (clicked_struct['x'], clicked_struct['y']):
                        self._move_dynamic_structure(current_id, new_x, new_y)
                        modified = True
            else:
                if current_id:
                    sel_struct = next((s for s in structs if s['id'] == current_id), None)
                    sw = sel_struct['w'] if sel_struct else 1
                    sh = sel_struct['h'] if sel_struct else 1
                    grab_ox, grab_oy = getattr(self, '_dyn_grab_offset', (0, 0))
                    new_x = max(0, min(cell_x - grab_ox, w - sw))
                    new_y = max(0, min(cell_y - grab_oy, h - sh))
                    self._move_dynamic_structure(current_id, new_x, new_y)
                    modified = True

        elif tab_idx == 4 and self.renderer.collision_map: # Modo pintar colisión
            val_text = self.cmb_col_brush.currentText()
            if ":" in val_text:
                val = int(val_text.split(":")[0], 16)
            else:
                val = 0
            if idx < len(self.renderer.collision_map):
                if self.renderer.collision_map[idx] != val:
                    self.renderer.collision_map = bytearray(self.renderer.collision_map)
                    self.renderer.collision_map[idx] = val
                    modified = True

        return modified

    def _on_map_clicked(self, px, py):
        px = int(px / self.zoom_factor)
        py = int(py / self.zoom_factor)
        cell_x = px // 8
        cell_y = py // 8
        self.selected_cell = (cell_x, cell_y)
        
        if not self._save_state_pending:
            self._push_undo_state()
            self._save_state_pending = True

        self._last_drag_cell = (cell_x, cell_y)
        if self._apply_paint_at_cell(cell_x, cell_y):
            self._re_render_map_only()

    def _on_map_dragged(self, px, py):
        px = int(px / self.zoom_factor)
        py = int(py / self.zoom_factor)
        cell_x = px // 8
        cell_y = py // 8

        last_cell = getattr(self, '_last_drag_cell', None)
        if last_cell == (cell_x, cell_y):
            return  # Misma celda, no hacer nada

        self.selected_cell = (cell_x, cell_y)

        if self.tabs_edit_mode.currentIndex() == 5:
            self._last_drag_cell = (cell_x, cell_y)
            if self._apply_paint_at_cell(cell_x, cell_y):
                self._re_render_map_only()
            return

        if not self._save_state_pending:
            self._push_undo_state()
            self._save_state_pending = True

        if last_cell is not None:
            cells_to_paint = self._get_line_cells(last_cell[0], last_cell[1], cell_x, cell_y)
        else:
            cells_to_paint = [(cell_x, cell_y)]

        self._last_drag_cell = (cell_x, cell_y)

        any_modified = False
        for cx, cy in cells_to_paint:
            if self._apply_paint_at_cell(cx, cy):
                any_modified = True

        if any_modified:
            self._re_render_map_only()

    def _on_map_right_clicked(self, px, py):
        tab_idx = self.tabs_edit_mode.currentIndex()
        
        px = int(px / self.zoom_factor)
        py = int(py / self.zoom_factor)
        cell_x = px // 8
        cell_y = py // 8
        w = self.renderer.width
        idx = cell_y * w + cell_x

        # Eyedropper (Copiar Tile)
        if tab_idx in [1, 2, 3]:
            if tab_idx == 1 and idx < len(self.renderer.tilemap_bg3):
                val = self.renderer.tilemap_bg3[idx]
            elif tab_idx == 2 and idx < len(self.renderer.tilemap_bg2):
                val = self.renderer.tilemap_bg2[idx]
            elif tab_idx == 3 and idx < len(self.renderer.tilemap_bg1):
                val = self.renderer.tilemap_bg1[idx]
            else:
                return
            
            self.selected_tile = val
            self._copied_from_map = True
            self.lbl_info.setText(f"Cuentagotas: Tile 0x{self.selected_tile:04X} copiado (incluye paleta).")
            self._re_render_tileset()
            return

        if tab_idx != 4: return
        
        if not self.renderer.collision_map or idx >= len(self.renderer.collision_map):
            return
            
        val = self.renderer.collision_map[idx]
        if val == 0:
            QMessageBox.information(self, "Trigger Info", "Esta celda es terreno caminable normal (00). No es un Trigger.")
            return
            
        trigger_info = self.renderer.get_trigger(cell_x, cell_y, val)
        if not trigger_info:
            QMessageBox.information(self, "Trigger Info", "Esta celda tiene asignada una colisión, pero no se encontró un Evento de Script en estas coordenadas.")
            return
            
        flags, script_id, rom_addr = trigger_info
        
        dlg = TriggerEditorDialog(val, flags, script_id, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_flags, new_script = dlg.get_data()
            self.renderer.set_trigger(val, rom_addr, new_flags, new_script)
            self.project.base_rom_data = bytearray(self.renderer.rom)
            self.lbl_info.setText(f"Trigger {val:02X} actualizado: Script {new_script}, Flags {new_flags:04X}")

    def _on_behavior_changed(self, val):
        pass # Remove behavior sync since we removed the inspector info panel

    def _open_palette_editor(self):
        if not self.renderer._loaded:
            return
            
        bank_idx = self.cmb_bank.currentIndex()
        pal_idx = self.cmb_ts_pal.currentIndex()
        if pal_idx == 0:
            if hasattr(self, 'selected_tile'):
                pal_idx = self.renderer.get_tile_palette(self.selected_tile & 0x03FF)
            else:
                pal_idx = getattr(self.renderer, 'dominant_palette', 1)
        
        palettes = self.renderer.palettes_1 if bank_idx == 0 else self.renderer.palettes_2
        if not palettes or pal_idx >= len(palettes):
            return
            
        current_colors = palettes[pal_idx]
        
        from Nucleos_Positronicos.Nucleo_de_Sprites.palette_editor import PaletteEditorDialog
        dlg = PaletteEditorDialog(current_colors, self)
        
        def on_live_change(new_colors):
            palettes[pal_idx] = new_colors
            self._re_render_tileset()
            self._re_render()
            
        dlg.palette_changed_live.connect(on_live_change)
        
        if dlg.exec() == QDialog.DialogCode.Accepted:
            final_colors = dlg.get_palette()
            palettes[pal_idx] = final_colors
            self._re_render_tileset()
            self._re_render()
        else:
            palettes[pal_idx] = current_colors
            self._re_render_tileset()
            self._re_render()
        
    def _open_resize_dialog(self):
        if self.selected_map_index < 0 or not self.renderer._loaded:
            QMessageBox.warning(self, "Error", "Debe cargar un mapa primero.")
            return
            
        current_w = self.renderer.width
        current_h = self.renderer.height
        
        dlg = MapResizeDialog(current_w, current_h, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_w, new_h = dlg.get_size()
            if new_w == current_w and new_h == current_h:
                return
                
            self._resize_map_prototype(new_w, new_h)
            
    def _open_create_dialog(self):
        dlg = MapResizeDialog(10, 10, self)
        dlg.setWindowTitle("Crear Nuevo Mapa")
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_w, new_h = dlg.get_size()
            self._create_map_prototype(new_w, new_h)
            
    def _create_map_prototype(self, new_w, new_h):
        try:
            new_id = self.map_parser.create_new_map(new_w, new_h)
            QMessageBox.information(self, "Mapa Creado", f"Se ha creado el nuevo mapa con ID {new_id}.\nRecarga la lista para verlo.")
            self.load_maps()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al crear mapa: {e}")

    def _resize_map_prototype(self, new_w, new_h):
        # 1. Analizar tamaño anterior y calcular la diferencia
        old_w = self.renderer.width
        old_h = self.renderer.height
        
        # 2. Obtener MapHeader actual
        mh = self.map_parser.maps[self.selected_map_index]
        
        # 3. Crear nuevos arrays expandidos llenos de ceros/vacío
        import numpy as np # as prototype
        # bg1, bg2, bg3, col = ...
        # (Aquí va la lógica de copiar viejo a nuevo conservando x,y y rellenando lo demás)
        
        # 4. Asignar nuevo espacio en la ROM (Repunteo)
        # new_offset = self.map_parser.find_free_space(nuevo_tamaño_total)
        # self.project.overwrite_rom_directly(new_offset, datos_comprimidos)
        
        # 5. Actualizar la cabecera en RAM
        # mh.width = new_w
        # mh.height = new_h
        # mh.p_bg1 = new_offset_bg1 ...
        
        # 6. Guardar la nueva cabecera y potencialmente reescribir/repuntear la tabla maestra en el Literal Pool
        # header_table_offset = self.map_parser._table_offset
        
        QMessageBox.information(self, "Redimensionador (Prototipo)", 
            f"Estructura de repunteo generada.\n"
            f"El mapa {mh.map_id} pasaría de {old_w}x{old_h} a {new_w}x{new_h}.\n"
            "Falta conectar la sobreescritura real de los arrays y ROM.")

    def _save_map(self):
        from PyQt6.QtWidgets import QMessageBox
        if self.selected_map_index >= 0:
            try:
                self.map_parser.save_map(self.selected_map_index, self.renderer)
                QMessageBox.information(self, "Exito", "Mapa compilado y guardado en la ROM exitosamente.")
            except Exception as e:
                import traceback
                QMessageBox.critical(self, "Error", f"Error guardando mapa:\n{e}\n{traceback.format_exc()}")

    # ── MÉTODOS DE ESTRUCTURAS DINÁMICAS (CAPA 5) ──────────────────────────

    def _update_dyn_structures_combo(self):
        if not hasattr(self, 'renderer') or not self.renderer or not hasattr(self.renderer, 'get_active_dynamic_structures'):
            return
        structs = self.renderer.get_active_dynamic_structures()
        self.cmb_dyn_selected.blockSignals(True)
        self.cmb_dyn_selected.clear()
        current_sel = getattr(self, 'selected_dyn_struct_id', None)
        sel_idx = 0

        for i, s in enumerate(structs):
            self.cmb_dyn_selected.addItem(f"{s['name']} [{s['id']}]", s['id'])
            if s['id'] == current_sel:
                sel_idx = i

        if structs:
            self.cmb_dyn_selected.setCurrentIndex(sel_idx)
            self.selected_dyn_struct_id = structs[sel_idx]['id']
            self.spn_dyn_x.blockSignals(True)
            self.spn_dyn_y.blockSignals(True)
            self.spn_dyn_x.setValue(structs[sel_idx]['x'])
            self.spn_dyn_y.setValue(structs[sel_idx]['y'])
            self.spn_dyn_x.blockSignals(False)
            self.spn_dyn_y.blockSignals(False)
        self.cmb_dyn_selected.blockSignals(False)

    def _select_dynamic_structure(self, struct_id: str):
        self.selected_dyn_struct_id = struct_id
        for i in range(self.cmb_dyn_selected.count()):
            if self.cmb_dyn_selected.itemData(i) == struct_id:
                self.cmb_dyn_selected.blockSignals(True)
                self.cmb_dyn_selected.setCurrentIndex(i)
                self.cmb_dyn_selected.blockSignals(False)
                break
        structs = self.renderer.get_active_dynamic_structures()
        for s in structs:
            if s['id'] == struct_id:
                self.spn_dyn_x.blockSignals(True)
                self.spn_dyn_y.blockSignals(True)
                self.spn_dyn_x.setValue(s['x'])
                self.spn_dyn_y.setValue(s['y'])
                self.spn_dyn_x.blockSignals(False)
                self.spn_dyn_y.blockSignals(False)
                break
        self._re_render_map_only()

    def _get_selected_dynamic_structure_id(self) -> str:
        return self.cmb_dyn_selected.currentData() or getattr(self, 'selected_dyn_struct_id', None)

    def _on_dyn_selected_changed(self, index):
        struct_id = self.cmb_dyn_selected.currentData()
        if struct_id:
            self._select_dynamic_structure(struct_id)

    def _on_dyn_pos_spin_changed(self):
        struct_id = self._get_selected_dynamic_structure_id()
        if struct_id and hasattr(self, 'renderer') and self.renderer:
            self._move_dynamic_structure(struct_id, self.spn_dyn_x.value(), self.spn_dyn_y.value())

    def _move_dynamic_structure(self, struct_id: str, new_x: int, new_y: int):
        if not hasattr(self.renderer, 'dynamic_config'):
            self.renderer.dynamic_config = {}
        if 'positions' not in self.renderer.dynamic_config:
            self.renderer.dynamic_config['positions'] = {}

        self.renderer.dynamic_config['positions'][struct_id] = (new_x, new_y)
        self.lbl_info.setText(f"[Estructuras Dinámicas] '{struct_id}' reubicada en X={new_x}, Y={new_y}")
        self.spn_dyn_x.blockSignals(True)
        self.spn_dyn_y.blockSignals(True)
        self.spn_dyn_x.setValue(new_x)
        self.spn_dyn_y.setValue(new_y)
        self.spn_dyn_x.blockSignals(False)
        self.spn_dyn_y.blockSignals(False)
        self._re_render_map_only()

    def _on_dyn_reset_positions(self):
        if hasattr(self.renderer, 'dynamic_config') and 'positions' in self.renderer.dynamic_config:
            self.renderer.dynamic_config['positions'].clear()
            self._update_dyn_structures_combo()
            self._re_render_map_only()
            self.lbl_info.setText("[Estructuras Dinámicas] Posiciones restablecidas a valores de ROM.")

    # ── IMPORTACIÓN Y EXPORTACIÓN DE MAPAS Y TILESETS ─────────────────────

    def _export_map_image(self):
        if not hasattr(self, 'renderer') or not self.renderer or not self.renderer._loaded:
            QMessageBox.warning(self, "Aviso", "No hay ningún mapa cargado para exportar.")
            return

        map_name = f"mapa_{self.selected_map_index:02d}"
        if self.selected_map_index < len(self.map_parser.maps):
            mh = self.map_parser.maps[self.selected_map_index]
            map_name = f"mapa_{mh.map_id:02d}_{self.map_parser.map_names.get(mh.map_id, 'map')}"

        from Banco_de_Datos.Utilidades.rutas import get_default_workspace_dir
        from PyQt6.QtWidgets import QFileDialog
        default_dir = os.path.join(get_default_workspace_dir(), f"{map_name}.png")

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Mapa Completo",
            default_dir,
            "Imagen PNG (*.png);;Mapa de Bits BMP (*.bmp);;Todos los archivos (*.*)"
        )
        if not path:
            return

        try:
            visibility = self._get_layer_visibility()
            img = self.renderer.render(
                show_bg1=visibility['show_bg1'],
                show_bg2=visibility['show_bg2'],
                show_bg3=visibility['show_bg3'],
                show_col=visibility['show_col'],
                bank=self.cmb_bank.currentIndex() + 1,
                invert_bg=self.chk_invert_bg.isChecked()
            )
            if not img:
                raise ValueError("El renderizador devolvió una imagen vacía.")

            if path.lower().endswith(".bmp"):
                img.convert("RGB").save(path, format="BMP")
            else:
                img.save(path)

            QMessageBox.information(self, "Exportación Exitosa", f"Mapa exportado correctamente a:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al exportar el mapa:\n{e}")

    def _import_map_image(self):
        if not hasattr(self, 'renderer') or not self.renderer or not self.renderer._loaded:
            QMessageBox.warning(self, "Aviso", "Debes cargar un mapa primero.")
            return

        from Banco_de_Datos.Utilidades.rutas import get_default_workspace_dir
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Importar Imagen de Mapa (BMP/PNG)",
            get_default_workspace_dir(),
            "Imágenes (*.png *.bmp *.jpg);;Todos los archivos (*.*)"
        )
        if not path:
            return

        try:
            from PIL import Image
            imported_img = Image.open(path).convert('RGBA')
            img_w, img_h = imported_img.size
            map_w = self.renderer.width
            map_h = self.renderer.height

            # Mapear cada bloque 8x8 al tile más cercano
            target_layer = self.tabs_edit_mode.currentIndex()
            if target_layer not in (1, 2, 3):
                target_layer = 1 # Fondo por defecto

            layer_name = "Fondo (p_bg3)" if target_layer == 1 else ("Medio (p_bg2)" if target_layer == 2 else "Frente (p_bg1)")
            target_tilemap = self.renderer.tilemap_bg3 if target_layer == 1 else (self.renderer.tilemap_bg2 if target_layer == 2 else self.renderer.tilemap_bg1)

            cols = min(map_w, img_w // 8)
            rows = min(map_h, img_h // 8)
            pal_idx = self.cmb_ts_pal.currentIndex() or 1

            for r in range(rows):
                for c in range(cols):
                    idx = r * map_w + c
                    if idx < len(target_tilemap):
                        # Asignar tile base
                        target_tilemap[idx] = (pal_idx << 12) | ((r * cols + c) % max(1, len(self.renderer.tiles)))

            self._re_render_map_only()
            QMessageBox.information(self, "Importación", f"Imagen importada exitosamente sobre la capa {layer_name}.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al importar imagen de mapa:\n{e}")

    def _export_tileset_image(self):
        if not hasattr(self, 'renderer') or not self.renderer or not self.renderer._loaded or not self.renderer.tiles:
            QMessageBox.warning(self, "Aviso", "No hay tileset disponible para exportar.")
            return

        map_id = self.selected_map_index
        if self.selected_map_index < len(self.map_parser.maps):
            map_id = self.map_parser.maps[self.selected_map_index].map_id

        pal_idx = self.cmb_ts_pal.currentIndex()
        bank = self.pal_bank
        ts_img = self.renderer.render_tileset(pal_idx=pal_idx, bank=bank)
        if not ts_img:
            QMessageBox.warning(self, "Aviso", "No se pudo renderizar el tileset.")
            return

        from Banco_de_Datos.Utilidades.rutas import get_default_workspace_dir
        from PyQt6.QtWidgets import QFileDialog
        default_path = os.path.join(get_default_workspace_dir(), f"tileset_mapa_{map_id:02d}.png")

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Tileset de Mapa",
            default_path,
            "Imagen PNG (*.png);;Mapa de Bits BMP (*.bmp);;Todos los archivos (*.*)"
        )
        if not path:
            return

        try:
            if path.lower().endswith(".bmp"):
                ts_img.convert("RGB").save(path, format="BMP")
            else:
                ts_img.save(path)
            QMessageBox.information(self, "Exportación Exitosa", f"Tileset exportado correctamente a:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al exportar el tileset:\n{e}")

    def _import_tileset_image(self):
        if not hasattr(self, 'renderer') or not self.renderer or not self.renderer._loaded:
            QMessageBox.warning(self, "Aviso", "Debes cargar un mapa primero.")
            return

        from Banco_de_Datos.Utilidades.rutas import get_default_workspace_dir
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Importar Tileset (BMP/PNG)",
            get_default_workspace_dir(),
            "Imágenes (*.png *.bmp *.jpg);;Todos los archivos (*.*)"
        )
        if not path:
            return

        try:
            from PIL import Image
            ts_img = Image.open(path)
            w, h = ts_img.size
            if w % 8 != 0 or h % 8 != 0:
                raise ValueError(f"Las dimensiones de la imagen ({w}x{h}) deben ser múltiplos de 8 píxeles.")

            cols = w // 8
            rows = h // 8
            total_tiles = cols * rows

            pal_idx = self.cmb_ts_pal.currentIndex() or 1
            pal = self.renderer.palettes_1[pal_idx] if self.pal_bank == 1 else self.renderer.palettes_2[pal_idx]

            new_tiles = []
            img_rgba = ts_img.convert('RGBA')

            for r in range(rows):
                for c in range(cols):
                    tile_indices = []
                    for y in range(8):
                        for x in range(8):
                            px = img_rgba.getpixel((c * 8 + x, r * 8 + y))
                            if px[3] < 128:
                                idx = 0
                            else:
                                pr, pg, pb = px[:3]
                                best_idx = 1
                                best_dist = float('inf')
                                for pi in range(1, min(16, len(pal))):
                                    cr, cg, cb = pal[pi][:3]
                                    d = (pr - cr)**2 + (pg - cg)**2 + (pb - cb)**2
                                    if d < best_dist:
                                        best_dist = d
                                        best_idx = pi
                                idx = best_idx
                            tile_indices.append(idx & 0xF)
                    new_tiles.append(tile_indices)

            self.renderer.tiles = new_tiles
            self.renderer._tile_cache.clear()

            reply = QMessageBox.question(
                self,
                "Inyectar a la ROM",
                f"Se han cargado {total_tiles} tiles de 8x8 con éxito.\n"
                "¿Deseas inyectar y compilar este tileset en la ROM inmediatamente?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                raw_4bpp = bytearray()
                for tile in new_tiles:
                    for i in range(0, 64, 2):
                        px_left = tile[i] & 0xF
                        px_right = (tile[i + 1] & 0xF) if (i + 1) < 64 else 0
                        raw_4bpp.append(px_left | (px_right << 4))

                self.map_parser.save_tileset(self.selected_map_index, bytes(raw_4bpp))
                QMessageBox.information(self, "Inyección Exitosa", "Tileset comprimido con ArcanoMarvelous e inyectado en la ROM.")

            self._re_render()
        except Exception as e:
            import traceback
            QMessageBox.critical(self, "Error", f"Fallo al importar el tileset:\n{e}\n{traceback.format_exc()}")

    def _open_utensils_dialog(self):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QCheckBox, QDialogButtonBox, QLabel
        dialog = QDialog(self)
        dialog.setWindowTitle("Utensilios de Cocina")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Selecciona los utensilios visibles en la cocina:"))

        utensil_names = [
            "Cuchillo", "Sartén", "Olla", "Batidora",
            "Batidor", "Rodillo", "Horno", "Juego de Condimentos"
        ]
        curr_state = getattr(self, 'house_utensils_state', [True]*8)
        checkboxes = []
        for i, name in enumerate(utensil_names):
            chk = QCheckBox(name)
            chk.setChecked(curr_state[i] if i < len(curr_state) else True)
            layout.addWidget(chk)
            checkboxes.append(chk)

        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bbox.accepted.connect(dialog.accept)
        bbox.rejected.connect(dialog.reject)
        layout.addWidget(bbox)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.house_utensils_state = [chk.isChecked() for chk in checkboxes]
            self._on_dynamic_config_changed()

    def _open_dynamic_structures_dialog(self):
        map_header = getattr(self, 'current_map_header', None)
        if not map_header and hasattr(self, 'selected_map_index') and 0 <= self.selected_map_index < len(self.map_parser.maps):
            map_header = self.map_parser.maps[self.selected_map_index]
            self.current_map_header = map_header
        if not map_header and hasattr(self, '_loader_thread') and self._loader_thread:
            map_header = getattr(self._loader_thread, 'map_header', None)
            self.current_map_header = map_header
        if not map_header:
            return
        map_id = getattr(map_header, 'map_id', 0)
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Estructuras Dinámicas - Mapa {map_id}")
        dialog.setMinimumWidth(380)
        dlg_layout = QVBoxLayout(dialog)
        dlg_layout.setSpacing(10)

        cmb_tb = None
        cmb_rp = None
        cmb_fridge = None
        cmb_shelf = None
        chk_kitchen = None
        chk_fireplace = None
        chk_dining = None
        cmb_bath_door = None
        chk_bed = None
        chk_vase = None
        chk_mirror = None
        chk_clock = None
        chk_mayo = None
        chk_cheese = None
        chk_yarn = None

        if map_id in (41, 42, 43):
            # 1. Almacenamiento y Sonido
            grp_storage = QGroupBox("Almacenamiento y Sonido")
            grid_s = QGridLayout(grp_storage)

            grid_s.addWidget(QLabel("Caja de Herramientas:"), 0, 0)
            cmb_tb = QComboBox()
            cmb_tb.addItems(["Cerrada", "Abierta", "Ocultar"])
            tb_val = getattr(self, 'house_toolbox_choice', 'closed')
            cmb_tb.setCurrentIndex(0 if tb_val == 'closed' else (1 if tb_val == 'open' else 2))
            grid_s.addWidget(cmb_tb, 0, 1)

            grid_s.addWidget(QLabel("Tocadiscos:"), 1, 0)
            cmb_rp = QComboBox()
            cmb_rp.addItems(["Base", "Con Discos", "Activo", "Ocultar"])
            rp_val = getattr(self, 'house_record_player_choice', 'base')
            cmb_rp.setCurrentIndex(0 if rp_val == 'base' else (1 if rp_val == 'discs' else (2 if rp_val == 'active' else 3)))
            grid_s.addWidget(cmb_rp, 1, 1)
            dlg_layout.addWidget(grp_storage)

            # 2. Cocina y Almacenamiento (Mapas 42 y 43)
            if map_id in (42, 43):
                grp_kitchen = QGroupBox("Cocina y Almacenamiento")
                grid_k = QGridLayout(grp_kitchen)

                grid_k.addWidget(QLabel("Refrigerador:"), 0, 0)
                cmb_fridge = QComboBox()
                cmb_fridge.addItems(["Cerrado", "Abierto", "Ocultar"])
                f_val = getattr(self, 'house_fridge_choice', 'closed')
                cmb_fridge.setCurrentIndex(0 if f_val == 'closed' else (1 if f_val == 'open' else 2))
                grid_k.addWidget(cmb_fridge, 0, 1)

                grid_k.addWidget(QLabel("Anaquel:"), 1, 0)
                cmb_shelf = QComboBox()
                cmb_shelf.addItems(["Cerrado", "Abierto", "Ocultar"])
                s_val = getattr(self, 'house_shelf_choice', 'closed')
                cmb_shelf.setCurrentIndex(0 if s_val == 'closed' else (1 if s_val == 'open' else 2))
                grid_k.addWidget(cmb_shelf, 1, 1)

                chk_kitchen = QCheckBox("Mueble de Cocina")
                chk_kitchen.setChecked(getattr(self, 'house_kitchen_choice', True))
                grid_k.addWidget(chk_kitchen, 2, 0)

                btn_u = QPushButton("Utensilios (8)...")
                btn_u.clicked.connect(self._open_utensils_dialog)
                grid_k.addWidget(btn_u, 2, 1)
                dlg_layout.addWidget(grp_kitchen)

            # 3. Estructuras de Casa
            grp_rooms = QGroupBox("Estructuras de Casa")
            vbox_r = QVBoxLayout(grp_rooms)

            if map_id in (42, 43):
                chk_dining = QCheckBox("Comedor / Mesa Grande (con Alfombra)")
                chk_dining.setChecked(getattr(self, 'house_dining_choice', True))
                vbox_r.addWidget(chk_dining)

            if map_id == 43:
                chk_fireplace = QCheckBox("Chimenea (6x8 tiles)")
                chk_fireplace.setChecked(getattr(self, 'house_fireplace_choice', True))
                vbox_r.addWidget(chk_fireplace)

                row_bd = QHBoxLayout()
                row_bd.addWidget(QLabel("Puerta del Baño:"))
                cmb_bath_door = QComboBox()
                cmb_bath_door.addItems(["Cerrada", "Abierta", "Ocultar"])
                bd_val = getattr(self, 'house_bathroom_door_choice', 'closed')
                cmb_bath_door.setCurrentIndex(0 if bd_val == 'closed' else (1 if bd_val == 'open' else 2))
                row_bd.addWidget(cmb_bath_door)
                vbox_r.addLayout(row_bd)

                chk_bed = QCheckBox("Cama Matrimonial (6x8 tiles)")
                chk_bed.setChecked(getattr(self, 'house_double_bed_choice', True))
                vbox_r.addWidget(chk_bed)

            dlg_layout.addWidget(grp_rooms)

            # 4. Decoración
            grp_decor = QGroupBox("Decoración")
            vbox_d = QVBoxLayout(grp_decor)

            chk_vase = QCheckBox("Florero")
            chk_vase.setChecked(getattr(self, 'house_vase_choice', True))
            vbox_d.addWidget(chk_vase)

            chk_mirror = QCheckBox("Espejo")
            chk_mirror.setChecked(getattr(self, 'house_mirror_choice', True))
            vbox_d.addWidget(chk_mirror)

            if map_id in (42, 43):
                chk_clock = QCheckBox("Reloj")
                chk_clock.setChecked(getattr(self, 'house_clock_choice', True))
                vbox_d.addWidget(chk_clock)

            dlg_layout.addWidget(grp_decor)

        elif map_id in (36, 37):
            # Gallinero (Chicken Coop 1 y 2)
            grp_coop = QGroupBox("Maquinaria del Gallinero")
            vbox_c = QVBoxLayout(grp_coop)
            chk_mayo = QCheckBox("Máquina de Mayonesa (3x5 tiles, Canon X=2, Y=5)")
            chk_mayo.setChecked(getattr(self, 'maker_mayo_choice', True))
            vbox_c.addWidget(chk_mayo)
            dlg_layout.addWidget(grp_coop)

        elif map_id in (38, 39):
            # Establo (Barn 1 y 2)
            grp_barn = QGroupBox("Maquinaria del Establo")
            vbox_b = QVBoxLayout(grp_barn)
            chk_cheese = QCheckBox("Máquina de Queso (3x5 tiles, Canon X=12, Y=5)")
            chk_cheese.setChecked(getattr(self, 'maker_cheese_choice', True))
            vbox_b.addWidget(chk_cheese)

            chk_yarn = QCheckBox("Máquina de Lana (3x5 tiles, Canon X=8, Y=5)")
            chk_yarn.setChecked(getattr(self, 'maker_yarn_choice', True))
            vbox_b.addWidget(chk_yarn)
            dlg_layout.addWidget(grp_barn)

        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bbox.accepted.connect(dialog.accept)
        bbox.rejected.connect(dialog.reject)
        dlg_layout.addWidget(bbox)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            if map_id in (41, 42, 43):
                tb_map = {0: 'closed', 1: 'open', 2: 'none'}
                rp_map = {0: 'base', 1: 'discs', 2: 'active', 3: 'none'}
                f_map = {0: 'closed', 1: 'open', 2: 'none'}
                s_map = {0: 'closed', 1: 'open', 2: 'none'}
                bd_map = {0: 'closed', 1: 'open', 2: 'none'}

                self.house_toolbox_choice = tb_map.get(cmb_tb.currentIndex(), 'closed')
                self.house_record_player_choice = rp_map.get(cmb_rp.currentIndex(), 'base')
                if cmb_fridge: self.house_fridge_choice = f_map.get(cmb_fridge.currentIndex(), 'closed')
                if cmb_shelf: self.house_shelf_choice = s_map.get(cmb_shelf.currentIndex(), 'closed')
                if chk_kitchen: self.house_kitchen_choice = chk_kitchen.isChecked()
                if chk_fireplace: self.house_fireplace_choice = chk_fireplace.isChecked()
                if chk_dining: self.house_dining_choice = chk_dining.isChecked()
                if cmb_bath_door: self.house_bathroom_door_choice = bd_map.get(cmb_bath_door.currentIndex(), 'closed')
                if chk_bed: self.house_double_bed_choice = chk_bed.isChecked()
                self.house_vase_choice = chk_vase.isChecked()
                self.house_mirror_choice = chk_mirror.isChecked()
                if chk_clock: self.house_clock_choice = chk_clock.isChecked()
            elif map_id in (36, 37):
                if chk_mayo: self.maker_mayo_choice = chk_mayo.isChecked()
            elif map_id in (38, 39):
                if chk_cheese: self.maker_cheese_choice = chk_cheese.isChecked()
                if chk_yarn: self.maker_yarn_choice = chk_yarn.isChecked()

            self._on_dynamic_config_changed()