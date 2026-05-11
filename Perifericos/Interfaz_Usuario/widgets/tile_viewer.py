# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.1.0)
# "The Imposibility Update"
# Desarrollado por: Denisovich728
# ============================================================
"""
TileViewerWidget v2.0 — Visor de Gráficos BlueSpider
══════════════════════════════════════════════════════
Reemplaza completamente el visor antiguo que producía basura.
Usa el motor BlueSpider (GBATile, GBAPalette) de mapas.py
para renderizar tilesets LZ77 correctamente.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QComboBox, QPushButton, QSlider, QSpinBox, QCheckBox,
    QFileDialog, QStyledItemDelegate, QStyleOptionViewItem
)
from PyQt6.QtCore import Qt, QSize, QRect
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor

from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.mapas import (
    GBATile, GBAPalette, decompress_auto, decompress_lz77
)
from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.codec_tiles import (
    bgr555_to_rgb, rgb_to_bgr555, render_tiles_to_pil
)


# ─────────────────────────────────────────────────────────────────
#  Delegate visual para el selector de paleta
# ─────────────────────────────────────────────────────────────────
class PaletteDelegate(QStyledItemDelegate):
    """Muestra 16 rectángulos de color junto al nombre de la paleta."""
    def paint(self, painter, option, index):
        painter.save()
        text = index.data(Qt.ItemDataRole.DisplayRole)
        colors = index.data(Qt.ItemDataRole.UserRole + 1)   # lista de (r,g,b)

        # Texto
        text_rect = QRect(option.rect.x()+4, option.rect.y(),
                          option.rect.width()-168, option.rect.height())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, text or "")

        # Grid de colores (16 cuadros × 10px)
        if colors:
            gx = option.rect.right() - 168
            gy = option.rect.y() + 5
            for i, (r, g, b) in enumerate(colors[:16]):
                painter.fillRect(gx + i*10, gy, 10, 10, QColor(r, g, b))
        painter.restore()

    def sizeHint(self, option, index):
        return QSize(300, 24)


# ─────────────────────────────────────────────────────────────────
#  Widget principal
# ─────────────────────────────────────────────────────────────────
class TileViewerWidget(QWidget):
    """
    Visor de Gráficos conectado al motor BlueSpider.
    Renderiza tilesets LZ77 con paletas GBA correctas en tiempo real.
    """
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project

        # Estado
        self.raw_tiles: bytes = b''          # datos descomprimidos
        self.tiles    : list  = []           # List[GBATile]
        self.palettes : list  = []           # List[GBAPalette] del proyecto
        self.cur_pal_idx: int = 0
        self.zoom     : int  = 3
        self.tiles_wide: int = 16
        self.is_8bpp  : bool = False

        self._current_offset = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._init_ui()

    # ── UI ─────────────────────────────────────────────────────────
    def _init_ui(self):
        root = QVBoxLayout(self)

        # ── Toolbar ──
        tb = QHBoxLayout()

        self.lbl_info = QLabel("Visor de Gráficos — Motor BlueSpider")
        self.lbl_info.setStyleSheet("font-weight:bold; color:#00d8ff;")
        tb.addWidget(self.lbl_info)
        tb.addStretch()

        # Paleta
        tb.addWidget(QLabel("Paleta:"))
        self.combo_pal = QComboBox()
        self.combo_pal.setMinimumWidth(280)
        self.combo_pal.setItemDelegate(PaletteDelegate())
        self.combo_pal.currentIndexChanged.connect(self._on_palette_changed)
        tb.addWidget(self.combo_pal)

        # Ancho en tiles
        tb.addWidget(QLabel("Ancho:"))
        self.spin_width = QSpinBox()
        self.spin_width.setRange(4, 64)
        self.spin_width.setSingleStep(4)
        self.spin_width.setValue(16)
        self.spin_width.valueChanged.connect(self._on_width_changed)
        tb.addWidget(self.spin_width)

        # 8bpp toggle
        self.btn_8bpp = QPushButton("4bpp")
        self.btn_8bpp.setCheckable(True)
        self.btn_8bpp.setFixedWidth(55)
        self.btn_8bpp.setStyleSheet(
            "QPushButton { background:#1a2a1a; color:#88ff88; border:1px solid #226622; border-radius:3px; }"
            "QPushButton:checked { background:#006600; color:white; }")
        self.btn_8bpp.toggled.connect(self._on_bpp_toggled)
        tb.addWidget(self.btn_8bpp)

        # Zoom
        tb.addWidget(QLabel("Zoom:"))
        self.slider_zoom = QSlider(Qt.Orientation.Horizontal)
        self.slider_zoom.setRange(1, 10)
        self.slider_zoom.setValue(3)
        self.slider_zoom.setFixedWidth(80)
        self.slider_zoom.valueChanged.connect(self._on_zoom_changed)
        tb.addWidget(self.slider_zoom)

        # Exportar
        btn_export = QPushButton("⬇ Exportar PNG")
        btn_export.clicked.connect(self._on_export_png)
        tb.addWidget(btn_export)

        # Referencias
        btn_refs = QPushButton("🔍 Refs")
        btn_refs.clicked.connect(self._on_find_references)
        tb.addWidget(btn_refs)
        self.lbl_refs = QLabel("Refs: –")
        self.lbl_refs.setStyleSheet("color:#ffa500; font-size:11px;")
        tb.addWidget(self.lbl_refs)

        root.addLayout(tb)

        # ── Canvas ──
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background:#111; border:1px solid #333;")
        self.canvas = QLabel()
        self.canvas.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll.setWidget(self.canvas)
        root.addWidget(self.scroll)

    # ── Carga de gráfico ────────────────────────────────────────────
    def load_graphic(self, offset: int):
        """
        Punto de entrada principal. Recibe un offset físico de la ROM,
        descomprime con el motor BlueSpider y renderiza.
        """
        self._current_offset = offset
        rom = self.project.base_rom_data
        if not rom:
            self.canvas.setText("No hay ROM cargada.")
            return

        try:
            header = rom[offset]
            if header in (0x10, 0x70):
                self.raw_tiles = decompress_auto(rom, offset)
            else:
                # Datos crudos — leer los próximos 32 KB
                self.raw_tiles = rom[offset: offset + 0x8000]
        except Exception as e:
            self.canvas.setText(f"Error: {e}")
            return

        info = self.project.super_lib.data_banks.get(offset, {})
        size_kb = len(self.raw_tiles) / 1024
        self.lbl_info.setText(
            f"GFX 0x{offset:06X} | {info.get('name','?')} | "
            f"{len(self.raw_tiles):,}b ({size_kb:.1f}KB)"
        )

        # Construir lista de GBATile
        tile_bytes = 64 if self.is_8bpp else GBATile.BYTES
        self.tiles = []
        for i in range(0, len(self.raw_tiles) - tile_bytes + 1, tile_bytes):
            self.tiles.append(GBATile(self.raw_tiles[i:i+tile_bytes]))

        # Cargar paletas del proyecto y actualizar combo
        self._reload_palette_combo()
        self._render()

    def _reload_palette_combo(self):
        """Recarga el combo con todas las paletas disponibles en el proyecto."""
        self.combo_pal.blockSignals(True)
        self.combo_pal.clear()
        self.combo_pal.addItem("Escala de Grises", None)

        rom = self.project.base_rom_data
        banks = self.project.super_lib.data_banks

        self.palettes = []
        for offset, info in sorted(banks.items()):
            if info.get('type') != 'PALETTE':
                continue
            try:
                raw_pal = self.project.decompress(offset)
                pal_obj = GBAPalette(raw_pal)
                rgb_colors = [c[:3] for c in pal_obj.colors]  # sin alpha
                idx = self.combo_pal.count()
                self.combo_pal.addItem(f"Paleta 0x{offset:06X}", offset)
                self.combo_pal.setItemData(idx, rgb_colors, Qt.ItemDataRole.UserRole + 1)
                self.palettes.append((offset, pal_obj))
            except:
                pass

        self.combo_pal.blockSignals(False)

    # ── Renderizado BlueSpider ──────────────────────────────────────
    def _render(self):
        if not self.raw_tiles:
            return

        tile_bytes  = 64 if self.is_8bpp else GBATile.BYTES
        num_tiles   = len(self.raw_tiles) // tile_bytes
        if num_tiles == 0:
            self.canvas.setText("Sin tiles válidos en este offset.")
            return

        # Obtener paleta activa
        pal_obj = self._current_palette_obj()
        pal_colors = [c[:3] for c in pal_obj.colors] if pal_obj else None

        tiles_w = self.spin_width.value()
        tiles_h = (num_tiles + tiles_w - 1) // tiles_w
        img_w = tiles_w * 8
        img_h = tiles_h * 8

        # Renderizar con GBATile o render_tiles_to_pil
        if pal_obj:
            from PIL import Image as PilImage
            img_pil = PilImage.new('RGBA', (img_w, img_h), (0,0,0,0))
            for t in range(num_tiles):
                tx = (t % tiles_w) * 8
                ty = (t // tiles_w) * 8
                off = t * tile_bytes
                tile = GBATile(self.raw_tiles[off:off+tile_bytes])
                tile_img = tile.render(pal_obj)
                img_pil.paste(tile_img, (tx, ty))
            # Pillow → QImage → QPixmap
            raw = img_pil.convert('RGBA').tobytes('raw', 'RGBA')
            qimg = QImage(raw, img_w, img_h, QImage.Format.Format_RGBA8888)
        else:
            # Escala de grises
            qimg = QImage(img_w, img_h, QImage.Format.Format_RGB32)
            qimg.fill(QColor(0,0,0))
            for t in range(num_tiles):
                tx = (t % tiles_w) * 8
                ty = (t // tiles_w) * 8
                off = t * tile_bytes
                for py in range(8):
                    for px in range(8):
                        if self.is_8bpp:
                            idx = self.raw_tiles[off + py*8+px] if off+py*8+px < len(self.raw_tiles) else 0
                        else:
                            b_off = off + py*4 + px//2
                            byte = self.raw_tiles[b_off] if b_off < len(self.raw_tiles) else 0
                            idx = (byte & 0xF) if px%2==0 else (byte>>4)
                        v = idx * 16
                        qimg.setPixel(tx+px, ty+py, (v<<16)|(v<<8)|v)

        # Escalar y mostrar
        pix = QPixmap.fromImage(qimg)
        z = self.zoom
        pix = pix.scaled(img_w*z, img_h*z,
                         Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.FastTransformation)
        self.canvas.setPixmap(pix)
        self.canvas.setFixedSize(pix.size())

    def _current_palette_obj(self):
        """Retorna el GBAPalette activo o None (escala de grises)."""
        offset = self.combo_pal.currentData()
        if offset is None:
            return None
        for off, pal in self.palettes:
            if off == offset:
                return pal
        return None

    # ── Señales de controles ────────────────────────────────────────
    def _on_palette_changed(self, _):
        self._render()

    def _on_width_changed(self, v):
        self.spin_width.setValue(v)
        self._render()

    def _on_bpp_toggled(self, checked):
        self.is_8bpp = checked
        self.btn_8bpp.setText("8bpp" if checked else "4bpp")
        # Reconstruir tiles
        if self.raw_tiles:
            tile_bytes = 64 if checked else GBATile.BYTES
            self.tiles = [
                GBATile(self.raw_tiles[i:i+tile_bytes])
                for i in range(0, len(self.raw_tiles)-tile_bytes+1, tile_bytes)
            ]
        self._render()

    def _on_zoom_changed(self, v):
        self.zoom = v
        self._render()

    # ── Exportar PNG ────────────────────────────────────────────────
    def _on_export_png(self):
        if not self.raw_tiles:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar Tileset", "tileset.png", "PNG (*.png)")
        if not path:
            return
        pal_obj = self._current_palette_obj()
        colors = [c[:3] for c in pal_obj.colors] if pal_obj else [(i*16,)*3 for i in range(16)]
        img = render_tiles_to_pil(self.raw_tiles, colors,
                                  self.spin_width.value(), self.is_8bpp)
        img.save(path)
        w = self.window()
        if hasattr(w, 'status'):
            w.status.showMessage(f"Tileset exportado → {path}")

    # ── Buscar referencias ──────────────────────────────────────────
    def _on_find_references(self):
        if self._current_offset is None:
            return
        refs = self.project.super_lib.find_references(
            self.project.base_rom_data, self._current_offset)
        if not refs:
            self.lbl_refs.setText("Refs: Ninguna")
        else:
            self.lbl_refs.setText("Refs: " + ", ".join(f"0x{r:06X}" for r in refs[:3]) +
                                  ("…" if len(refs) > 3 else ""))

    # ── Navegación por teclado ──────────────────────────────────────
    def _cycle_asset(self, asset_type, direction):
        banks = self.project.super_lib.data_banks
        offsets = sorted(o for o, i in banks.items() if i.get('type') == asset_type)
        if not offsets:
            return
        current = self._current_offset
        try:
            idx = (offsets.index(current) + direction) % len(offsets)
        except (ValueError, TypeError):
            idx = 0
        if asset_type == "TILESET":
            self.load_graphic(offsets[idx])

    def keyPressEvent(self, event):
        mod = event.modifiers()
        key = event.key()
        if mod & Qt.KeyboardModifier.ShiftModifier:
            if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                self._cycle_asset("TILESET", 1)
            elif key == Qt.Key.Key_Minus:
                self._cycle_asset("TILESET", -1)
        super().keyPressEvent(event)