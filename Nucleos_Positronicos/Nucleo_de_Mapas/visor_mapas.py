import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QLabel, QScrollArea,
    QPushButton, QSpinBox, QMessageBox, QSplitter, QProgressBar, QCheckBox, QComboBox, QFormLayout, QTabWidget, QLineEdit, QDialog
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
            
            if 0 <= click_x < img_w and 0 <= click_y < img_h:
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
        
        self.lbl_warning = QLabel("⚠️ Al aplicar, se asignará nuevo espacio en ROM\ny se actualizará la tabla maestra y punteros.")
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

        self.btn_refresh = QPushButton("🔄 Recargar Lista")
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
        self.btn_zoom_out = QPushButton("🔍 -")
        self.btn_zoom_in = QPushButton("🔍 +")
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
        
        tools_container_layout.addLayout(tools_row1)
        tools_container_layout.addLayout(tools_row2)
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
        self.lbl_image.mouseMoved.connect(self._on_map_clicked)
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
        self.cmb_ts_pal.addItems([f"Pal {i}" for i in range(16)])
        self.cmb_ts_pal.currentIndexChanged.connect(self._re_render_tileset)
        ts_controls.addWidget(self.cmb_ts_pal)
        
        self.btn_edit_palette = QPushButton("🎨 Editar Paleta")
        self.btn_edit_palette.clicked.connect(self._open_palette_editor)
        ts_controls.addWidget(self.btn_edit_palette)
        
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
        self.lbl_info.setText(
            f"⏳ Cargando mapa [{map_obj.map_id:03X}] {map_obj.get_name()} "
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
        self.lbl_col_brush.setVisible(is_col)
        self.cmb_col_brush.setVisible(is_col)
        self._re_render()
        
    def _re_render(self):
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
        self._re_render_tileset()

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
            self.lbl_info.setText("⚠️ No se pudo renderizar el mapa (faltan datos).")
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
        
        info = f"✅ Renderizado: {w}×{h} celdas | "
        info += f"{len(palettes)} paletas | {len(self.renderer.tiles)} tiles | "
        info += f"Triggers: Ptr6=0x{mh.p_obj1:08X}, Ptr7=0x{mh.p_obj2:08X}"
        self.lbl_info.setText(info)
        
        self._update_collision_brush()

    def _on_map_error(self, error_msg):
        self.progress.setVisible(False)
        self.lbl_info.setText(f"❌ Error: {error_msg[:120]}")
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
        self.lbl_info.setText(f"Pincel Tile: 0x{self.selected_tile:03X}")
        self._re_render_tileset()

    def _on_map_mouse_released(self):
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

    def _on_map_clicked(self, px, py):
        px = int(px / self.zoom_factor)
        py = int(py / self.zoom_factor)
        cell_x = px // 8
        cell_y = py // 8
        self.selected_cell = (cell_x, cell_y)
        
        w = self.renderer.width
        h = self.renderer.height
        idx = cell_y * w + cell_x
        
        # Guardar estado antes del primer cambio
        if not self._save_state_pending:
            self._push_undo_state()
            self._save_state_pending = True
        
        # Lógica de pintado según la pestaña activa
        tab_idx = self.tabs_edit_mode.currentIndex()
        if hasattr(self, 'selected_tile') and tab_idx in [1, 2, 3]: # Modo pintar BG
            copied_from_map = getattr(self, '_copied_from_map', False)
            
            # Si no fue clonado (se eligió del panel), inyectamos la paleta activa del combobox
            if not copied_from_map:
                active_pal = self.cmb_ts_pal.currentIndex()
                new_val = (active_pal << 12) | (self.selected_tile & 0x03FF)
            else:
                new_val = self.selected_tile

            if tab_idx == 1 and idx < len(self.renderer.tilemap_bg3):
                self.renderer.tilemap_bg3[idx] = new_val
            elif tab_idx == 2 and idx < len(self.renderer.tilemap_bg2):
                self.renderer.tilemap_bg2[idx] = new_val
            elif tab_idx == 3 and idx < len(self.renderer.tilemap_bg1):
                self.renderer.tilemap_bg1[idx] = new_val
            self._re_render()
        elif tab_idx == 4 and self.renderer.collision_map: # Modo pintar colisión
            val_text = self.cmb_col_brush.currentText()
            if ":" in val_text:
                val = int(val_text.split(":")[0], 16)
            else:
                val = 0
            if idx < len(self.renderer.collision_map):
                self.renderer.collision_map = bytearray(self.renderer.collision_map)
                self.renderer.collision_map[idx] = val
                self._re_render()

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
