from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QScrollArea, QComboBox, QPushButton, QSlider, 
                             QSpinBox, QCheckBox, QStyledItemDelegate, QStyleOptionViewItem)
from PyQt6.QtCore import Qt, QSize, QRect
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor, QPalette
from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.codec_tiles import decode_4bpp_tile, bgr555_to_rgb

class PaletteDelegate(QStyledItemDelegate):
    """
    Dibuja una previsualización de 8x2 colores al lado del texto de la paleta.
    """
    def paint(self, painter, option, index):
        painter.save()
        
        # Obtener datos
        text = index.data(Qt.ItemDataRole.DisplayRole)
        p_offset = index.data(Qt.ItemDataRole.UserRole)
        
        # Dibujar fondo estándar
        # Corregido: PyQt6 enum check
        # Usamos state check de forma segura
        # if option.state & QStyleOptionViewItem.StateFlag.State_Selected:
        #     painter.fillRect(option.rect, option.palette.highlight())
        
        # Área de texto
        text_rect = QRect(option.rect.x() + 5, option.rect.y(), option.rect.width() - 100, option.rect.height())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, text)
        
        # Área de colores (derecha)
        if p_offset:
            # USAR CACHÉ DE LA SUPER LIBRERÍA (Sin descompresión lenta)
            try:
                viewer = index.model().parent()
                colors = viewer.project.super_lib.palette_cache.get(p_offset)
                
                if colors:
                    grid_x = option.rect.x() + option.rect.width() - 90
                    grid_y = option.rect.y() + 4
                    
                    for i in range(min(16, len(colors))):
                        r, g, b = colors[i]
                        painter.setBrush(QColor(r, g, b))
                        painter.setPen(Qt.GlobalColor.black)
                        
                        px = grid_x + (i % 8) * 10
                        py = grid_y + (i // 8) * 10
                        painter.drawRect(px, py, 10, 10)
            except: pass
            
        painter.restore()

    def sizeHint(self, option, index):
        return QSize(200, 30)

class TileViewerWidget(QWidget):
    """
    Visor de Tiles Avanzado.
    Permite visualizar bancos LZ77 como tilesets 4bpp o 8bpp con paletas dinámicas.
    """
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.current_data = None
        self.current_palette = [(i*16, i*16, i*16) for i in range(16)]
        self.zoom = 4
        self.tile_width = 16
        self.is_8bpp = False
        self._current_offset = None
        
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Barra de Herramientas
        toolbar = QHBoxLayout()
        
        self.lbl_info = QLabel("Pestaña de Análisis Gráfico")
        self.lbl_info.setStyleSheet("font-weight: bold; color: #00ff00;")
        toolbar.addWidget(self.lbl_info)
        
        toolbar.addStretch()
        
        # Selector de Paleta con Delegate Visual
        toolbar.addWidget(QLabel("Paleta:"))
        self.combo_palette = QComboBox()
        self.combo_palette.setMinimumWidth(250) # Más ancho para la grid
        self.combo_palette.setItemDelegate(PaletteDelegate())
        self.combo_palette.currentIndexChanged.connect(self._on_palette_changed)
        toolbar.addWidget(self.combo_palette)
        
        # Configuración de Nitidez (Ancho)
        toolbar.addWidget(QLabel("Ancho (Tiles):"))
        self.spin_width = QSpinBox()
        self.spin_width.setRange(4, 64)
        self.spin_width.setSingleStep(4)
        self.spin_width.setValue(16)
        self.spin_width.valueChanged.connect(self._on_width_changed)
        toolbar.addWidget(self.spin_width)
        
        # Botón Toggle 8bpp (Rojo Estilo Retro)
        self.btn_8bpp = QPushButton("8bpp")
        self.btn_8bpp.setCheckable(True)
        self.btn_8bpp.setFixedWidth(60)
        self.btn_8bpp.setStyleSheet("""
            QPushButton { 
                background-color: #550000; color: #ff9999; border: 2px solid #330000; 
                border-radius: 4px; font-weight: bold; 
            }
            QPushButton:checked { 
                background-color: #ff0000; color: white; border: 2px solid #880000; 
                padding-top: 2px; padding-left: 2px;
            }
            QPushButton:hover { background-color: #770000; }
        """)
        self.btn_8bpp.toggled.connect(self._on_8bpp_changed)
        toolbar.addWidget(self.btn_8bpp)
        
        # Zoom
        toolbar.addWidget(QLabel("Zoom:"))
        self.slider_zoom = QSlider(Qt.Orientation.Horizontal)
        self.slider_zoom.setRange(1, 10)
        self.slider_zoom.setValue(4)
        self.slider_zoom.setFixedWidth(80)
        self.slider_zoom.valueChanged.connect(self._on_zoom_changed)
        toolbar.addWidget(self.slider_zoom)
        
        # Botón Referencias
        btn_refs = QPushButton("Buscar Referencias")
        btn_refs.clicked.connect(self._on_find_references)
        toolbar.addWidget(btn_refs)
        
        # Etiqueta de Referencias
        self.lbl_refs = QLabel("Refs: -")
        self.lbl_refs.setStyleSheet("color: #ffa500; font-size: 11px;")
        toolbar.addWidget(self.lbl_refs)
        
        layout.addLayout(toolbar)
        
        # Área de Visualización
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background-color: #1a1a1a; border: 1px solid #333;")
        
        self.canvas = QLabel()
        self.canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setWidget(self.canvas)
        
        layout.addWidget(self.scroll)

    def load_graphic(self, offset):
        self._current_offset = offset
        info = self.project.super_lib.data_banks.get(offset, {})
        self.lbl_info.setText(f"GFX [0x{offset:06X}] | Size: {info.get('size', 0)}b")
        
        if self.combo_palette.count() == 0:
            self._update_palette_list()
            
        try:
            self.current_data = self.project.decompress(offset)
            self._render()
        except:
            self.canvas.setText("Carga fallida o datos no gráficos.")

    def _update_palette_list(self):
        self.combo_palette.clear()
        self.combo_palette.addItem("Escala de Grises", None)
        
        banks = self.project.super_lib.data_banks
        for offset, info in sorted(banks.items()):
            if info['type'] == "PALETTE":
                self.combo_palette.addItem(f"Paleta 0x{offset:06X}", offset)

    def _on_palette_changed(self, index):
        p_offset = self.combo_palette.itemData(index)
        if p_offset is None:
            self.current_palette = [(i*16, i*16, i*16) for i in range(256 if self.is_8bpp else 16)]
        else:
            try:
                raw_pal = self.project.decompress(p_offset)
                new_pal = []
                for i in range(0, len(raw_pal), 2):
                    c16 = int.from_bytes(raw_pal[i:i+2], 'little')
                    new_pal.append(bgr555_to_rgb(c16))
                self.current_palette = new_pal
            except: pass
        self._render()

    def _on_width_changed(self, value):
        self.tile_width = value
        self._render()

    def _on_8bpp_changed(self, is_checked):
        self.is_8bpp = is_checked
        # Recargar paleta actual por si el tamaño cambió
        self._on_palette_changed(self.combo_palette.currentIndex())

    def _on_zoom_changed(self, value):
        self.zoom = value
        self._render()

    def _render(self):
        if self.current_data is None: return
        
        tile_size = 64 if self.is_8bpp else 32
        num_tiles = len(self.current_data) // tile_size
        if num_tiles == 0: return
        
        tiles_x = self.tile_width
        tiles_y = (num_tiles + tiles_x - 1) // tiles_x
        
        full_w = tiles_x * 8
        full_h = tiles_y * 8
        
        img = QImage(full_w, full_h, QImage.Format.Format_RGB32)
        img.fill(Qt.GlobalColor.black)
        
        for t_idx in range(num_tiles):
            t_off = t_idx * tile_size
            tx_base = (t_idx % tiles_x) * 8
            ty_base = (t_idx // tiles_x) * 8
            
            for py in range(8):
                for px in range(8):
                    if self.is_8bpp:
                        p_idx = self.current_data[t_off + py*8 + px]
                    else:
                        byte = self.current_data[t_off + (py*4) + (px // 2)]
                        p_idx = (byte & 0x0F) if (px % 2 == 0) else (byte >> 4)
                    
                    color = self.current_palette[p_idx] if p_idx < len(self.current_palette) else (0,0,0)
                    img.setPixel(tx_base + px, ty_base + py, (color[0] << 16) | (color[1] << 8) | color[2])
                    
        pixmap = QPixmap.fromImage(img)
        scaled = pixmap.scaled(full_w * self.zoom, full_h * self.zoom, 
                                Qt.AspectRatioMode.KeepAspectRatio, 
                                Qt.TransformationMode.FastTransformation)
        self.canvas.setPixmap(scaled)

    def _cycle_asset(self, asset_type, direction):
        banks = self.project.super_lib.data_banks
        offsets = sorted([off for off, info in banks.items() if info['type'] == asset_type])
        if not offsets: return
        
        current = self.combo_palette.currentData() if asset_type == "PALETTE" else self._current_offset
        if current is None: idx = 0
        else:
            try: idx = (offsets.index(current) + direction) % len(offsets)
            except: idx = 0
            
        new_off = offsets[idx]
        if asset_type == "TILESET": self.load_graphic(new_off)
        else: self.combo_palette.setCurrentIndex(self.combo_palette.findData(new_off))

    def keyPressEvent(self, event):
        mod = event.modifiers()
        key = event.key()
        if mod & Qt.KeyboardModifier.ShiftModifier:
            if key in [Qt.Key.Key_Plus, Qt.Key.Key_Equal]: self._cycle_asset("TILESET", 1)
            elif key == Qt.Key.Key_Minus: self._cycle_asset("TILESET", -1)
        elif (mod & Qt.KeyboardModifier.ControlModifier) and (mod & Qt.KeyboardModifier.AltModifier):
            if key in [Qt.Key.Key_Plus, Qt.Key.Key_Equal]: self._cycle_asset("PALETTE", 1)
            elif key == Qt.Key.Key_Minus: self._cycle_asset("PALETTE", -1)
        super().keyPressEvent(event)

    def _on_find_references(self):
        if self._current_offset is None: return
        
        # Buscar punteros en la ROM
        refs = self.project.super_lib.find_references(self.project.base_rom_data, self._current_offset)
        
        if not refs:
            self.lbl_refs.setText("Refs: Ninguna")
        else:
            # Mostrar los primeros 3 offsets que apuntan aquí
            ref_strs = [f"0x{r:06X}" for r in refs[:3]]
            text = "Refs: " + ", ".join(ref_strs)
            if len(refs) > 3: text += "..."
            self.lbl_refs.setText(text)
            self.window.status.showMessage(f"Se encontraron {len(refs)} punteros a este gráfico.")
