import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QLabel, QScrollArea,
    QPushButton, QSpinBox, QMessageBox, QSplitter, QProgressBar, QCheckBox, QComboBox, QFormLayout, QTabWidget, QLineEdit, QDialog
)
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.mapas import MapParser
from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.fomt_mapdata import FomtMapRenderer


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
                    self.clicked.emit(click_x, click_y)
                elif event.button() == Qt.MouseButton.RightButton:
                    self.rightClicked.emit(click_x, click_y)
        super().mousePressEvent(event)

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
        self._setup_ui()
        self.load_maps()

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
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(4, 4, 4, 4)

        # Modos de Edición por Pestañas
        self.tabs_mode = QTabWidget()
        self.tabs_mode.addTab(QWidget(), "General")
        self.tabs_mode.addTab(QWidget(), "Fondo (p_bg3)")
        self.tabs_mode.addTab(QWidget(), "Medio (p_bg2)")
        self.tabs_mode.addTab(QWidget(), "Frente (p_bg1)")
        self.tabs_mode.addTab(QWidget(), "Colisiones")
        self.tabs_mode.currentChanged.connect(self._on_tab_changed)
        
        # Controles de Herramientas
        tools_layout = QHBoxLayout()
        tools_layout.addWidget(self.tabs_mode)
        
        self.cmb_bank = QComboBox()
        self.cmb_bank.addItems(["Paleta 1 (Verano/Día)", "Paleta 2 (Invierno/Noche)"])
        tools_layout.addWidget(QLabel("Variante:"))
        tools_layout.addWidget(self.cmb_bank)
        
        self.chk_invert_bg = QCheckBox("Invertir Z-Index (BG1/BG3)")
        tools_layout.addWidget(self.chk_invert_bg)
        
        # Paleta de Colisiones
        self.cmb_col_brush = QComboBox()
        self.behavior_names = [
            "00: Caminable (Vacío)",
            "01: Trigger Caminable",
            "02: Caminable Alternativo",
            "03: Agua (No caminable)",
            "04: Cultivable (Tierra)",
            "05: Trigger Sólido",
            "08: Sólido Genérico",
            "09: Sólido (Borde Alto)",
            "0C: Trigger de Borde",
            "10: Hielo",
            "11: Trigger en Hielo",
            "18: Sólido Elevado",
            "20: Arena",
            "21: Trigger Arena",
            "28: Sólido Arena",
            "40: Trigger Sólido Extra",
            "80: Sólido Irregular",
            "C0: Obstáculo Fijo"
        ]
        self.cmb_col_brush.addItems(self.behavior_names)
        self.cmb_col_brush.setVisible(False)
        self.lbl_col_brush = QLabel("Pincel Colisión:")
        self.lbl_col_brush.setVisible(False)
        
        tools_layout.addWidget(self.lbl_col_brush)
        tools_layout.addWidget(self.cmb_col_brush)
        
        
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
        tools_layout.addLayout(zoom_layout)
        
        tools_layout.addStretch()
        right_layout.addLayout(tools_layout)

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
        ts_layout.addLayout(ts_controls)
        
        self.ts_scroll = QScrollArea()
        self.ts_scroll.setWidgetResizable(True)
        self.lbl_ts = ClickableMapLabel()
        self.lbl_ts.clicked.connect(self._on_tileset_clicked)
        self.lbl_ts.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.lbl_ts.setStyleSheet("background-color: #111; border: 1px solid #333;")
        self.ts_scroll.setWidget(self.lbl_ts)
        ts_layout.addWidget(self.ts_scroll)
        
        # Inspector de celda
        self.inspector_panel = QWidget()
        insp_layout = QVBoxLayout(self.inspector_panel)
        insp_layout.addWidget(QLabel("<b>Inspector de Celda</b>"))
        self.lbl_coord = QLabel("Coord: -")
        self.lbl_bg3 = QLabel("Fondo (p_bg3): -")
        self.lbl_bg2 = QLabel("Medio (p_bg2): -")
        self.lbl_bg1 = QLabel("Frente (p_bg1): -")
        self.lbl_col = QLabel("Colisión: -")
        
        self.btn_save = QPushButton("Guardar Cambios (ROM)")
        self.btn_save.clicked.connect(self._save_map)
        
        insp_layout.addWidget(self.lbl_coord)
        insp_layout.addWidget(self.lbl_bg3)
        insp_layout.addWidget(self.lbl_bg2)
        insp_layout.addWidget(self.lbl_bg1)
        insp_layout.addWidget(self.lbl_col)
        insp_layout.addWidget(self.btn_save)
        insp_layout.addStretch()

        viewers_layout.addWidget(self.inspector_panel, stretch=1)
        viewers_layout.addLayout(ts_layout, stretch=1)
        
        # Wrapper widget para forzar que los visores ocupen el espacio
        viewers_container = QWidget()
        viewers_container.setLayout(viewers_layout)
        right_layout.addWidget(viewers_container, stretch=1)


        splitter.addWidget(right_panel)
        splitter.setSizes([220, 780])

    def _zoom_in(self):
        if self.zoom_factor < 8.0:
            self.zoom_factor += 0.5
            self.lbl_zoom.setText(f"Zoom: {int(self.zoom_factor * 100)}%")
            self._re_render()
            self._re_render_tileset()

    def _zoom_out(self):
        if self.zoom_factor > 1.0:
            self.zoom_factor -= 0.5
            self.lbl_zoom.setText(f"Zoom: {int(self.zoom_factor * 100)}%")
            self._re_render()
            self._re_render_tileset()

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
        idx = self.tabs_mode.currentIndex()
        # Ocultar capas no seleccionadas
        show_bg3 = (idx in [0, 1, 4])
        show_bg2 = (idx in [0, 2])
        show_bg1 = (idx in [0, 3])
        show_col = (idx == 4)
        
        return {
            'show_bg1': show_bg1,
            'show_bg2': show_bg2,
            'show_bg3': show_bg3,
            'show_col': show_col
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

    def _on_tab_changed(self, index):
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
            self._set_pixmap(self.lbl_ts, ts_img)

    def _set_pixmap(self, label, img):
        img_data = img.tobytes("raw", "RGB")
        qim = QImage(img_data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qim)
        if self.zoom_factor != 1.0:
            pix = pix.scaled(int(img.width * self.zoom_factor), int(img.height * self.zoom_factor), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
        label.setPixmap(pix)

    def _on_map_loaded(self, result):
        self.progress.setVisible(False)
        img, ts_img = result
        if img is None:
            self.lbl_info.setText("⚠️ No se pudo renderizar el mapa (faltan datos).")
            self.lbl_image.clear()
            self.lbl_ts.clear()
            return

        self._set_pixmap(self.lbl_image, img)
        if ts_img:
            self._set_pixmap(self.lbl_ts, ts_img)

        h = self.renderer.height
        w = self.renderer.width
        palettes = self.renderer.palettes_1 if self.cmb_bank.currentIndex() == 0 else self.renderer.palettes_2
        mh = self._loader_thread.map_header
        
        info = f"✅ Renderizado: {w}×{h} celdas | "
        info += f"{len(palettes)} paletas | {len(self.renderer.tiles)} tiles | "
        info += f"Triggers: Ptr6=0x{mh.p_obj1:08X}, Ptr7=0x{mh.p_obj2:08X}"
        self.lbl_info.setText(info)

    def _on_map_error(self, error_msg):
        self.progress.setVisible(False)
        self.lbl_info.setText(f"❌ Error: {error_msg[:120]}")
        print(f"[VisorMapas] Error:\n{error_msg}")

    def _on_tileset_clicked(self, px, py):
        px = int(px / self.zoom_factor)
        py = int(py / self.zoom_factor)
        cell_x = px // 8
        cell_y = py // 8
        tileset_width = 32 # 256 pixels / 8
        self.selected_tile = cell_y * tileset_width + cell_x
        self.lbl_info.setText(f"Pincel Tile: 0x{self.selected_tile:03X}")

    def _on_map_clicked(self, px, py):
        px = int(px / self.zoom_factor)
        py = int(py / self.zoom_factor)
        cell_x = px // 8
        cell_y = py // 8
        self.selected_cell = (cell_x, cell_y)
        self.lbl_coord.setText(f"Coord: X={cell_x}, Y={cell_y}")
        
        w = self.renderer.width
        h = self.renderer.height
        idx = cell_y * w + cell_x
        
        # Lógica de pintado según la pestaña activa
        tab_idx = self.tabs_mode.currentIndex()
        if hasattr(self, 'selected_tile') and tab_idx in [1, 2, 3]: # Modo pintar BG
            if tab_idx == 1 and idx < len(self.renderer.tilemap_bg3):
                self.renderer.tilemap_bg3[idx] = (self.renderer.tilemap_bg3[idx] & 0xFC00) | self.selected_tile
            elif tab_idx == 2 and idx < len(self.renderer.tilemap_bg2):
                self.renderer.tilemap_bg2[idx] = (self.renderer.tilemap_bg2[idx] & 0xFC00) | self.selected_tile
            elif tab_idx == 3 and idx < len(self.renderer.tilemap_bg1):
                self.renderer.tilemap_bg1[idx] = (self.renderer.tilemap_bg1[idx] & 0xFC00) | self.selected_tile
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
        
        if idx < len(self.renderer.tilemap_bg3):
            t3 = self.renderer.tilemap_bg3[idx] & 0x3FF
            self.lbl_bg3.setText(f"Fondo (p_bg3): {t3}")
        if idx < len(self.renderer.tilemap_bg2):
            t2 = self.renderer.tilemap_bg2[idx] & 0x3FF
            self.lbl_bg2.setText(f"Medio (p_bg2): {t2}")
        if idx < len(self.renderer.tilemap_bg1):
            t1 = self.renderer.tilemap_bg1[idx] & 0x3FF
            self.lbl_bg1.setText(f"Frente (p_bg1): {t1}")
            
        if self.renderer.collision_map and idx < len(self.renderer.collision_map):
            val = self.renderer.collision_map[idx]
            # Mostrar el nombre del comportamiento si lo tenemos en la lista
            name = f"0x{val:02X}"
            for b in self.behavior_names:
                if b.startswith(f"{val:02X}"):
                    name = b
                    break
            self.lbl_col.setText(f"Colisión: {name}")

    def _on_map_right_clicked(self, px, py):
        tab_idx = self.tabs_mode.currentIndex()
        if tab_idx != 4: return
        
        px = int(px / self.zoom_factor)
        py = int(py / self.zoom_factor)
        cell_x = px // 8
        cell_y = py // 8
        w = self.renderer.width
        idx = cell_y * w + cell_x
        
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
        
    def _save_map(self):
        from PyQt6.QtWidgets import QMessageBox
        if self.selected_map_index >= 0:
            try:
                self.map_parser.save_map(self.selected_map_index, self.renderer)
                QMessageBox.information(self, "Exito", "Mapa compilado y guardado en la ROM exitosamente.")
            except Exception as e:
                import traceback
                QMessageBox.critical(self, "Error", f"Error guardando mapa:\n{e}\n{traceback.format_exc()}")
