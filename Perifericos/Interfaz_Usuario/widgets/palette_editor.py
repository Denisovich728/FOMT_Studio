# ============================================================
# FOMT Studio - Palette Editor Widget
# Melody Portrait Engine - GBA Color Picker
# Desarrollado por: Denisovich728
# ============================================================
import struct
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QSlider, QFrame, QGridLayout, QSizePolicy,
    QScrollArea, QWidget, QMessageBox, QSpinBox
)
from PyQt6.QtGui import (
    QPixmap, QPainter, QColor, QLinearGradient, QConicalGradient,
    QRadialGradient, QPen, QBrush, QMouseEvent, QPaintEvent,
    QImage, QFont
)
from PyQt6.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal

# ─────────────────────────────────────────────────────────────────────────────
# GBA Color Helpers
# ─────────────────────────────────────────────────────────────────────────────

def rgb888_to_gba(r, g, b):
    """Convierte RGB888 → color GBA 15-bit (BGR555)."""
    r5 = (r >> 3) & 0x1F
    g5 = (g >> 3) & 0x1F
    b5 = (b >> 3) & 0x1F
    return r5 | (g5 << 5) | (b5 << 10)


def gba_to_rgb888(c16):
    """Convierte color GBA 15-bit → RGB888 (se pierden los bits bajos, normal en GBA)."""
    r = (c16 & 0x1F) << 3
    g = ((c16 >> 5) & 0x1F) << 3
    b = ((c16 >> 10) & 0x1F) << 3
    return r, g, b


def quantize_to_gba(r, g, b):
    """Cuantiza un color RGB888 a la precisión GBA (pasos de 8)."""
    r5 = r >> 3
    g5 = g >> 3
    b5 = b >> 3
    return (r5 << 3), (g5 << 3), (b5 << 3)


# ─────────────────────────────────────────────────────────────────────────────
# HSV Color Square (Saturation × Value canvas with hue background)
# ─────────────────────────────────────────────────────────────────────────────

class HSVSquare(QWidget):
    """Canvas cuadrado de Saturación × Brillo para un hue fijo."""
    color_changed = pyqtSignal(int, int, int)  # r, g, b

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hue = 0          # 0-359
        self._sat = 255        # 0-255
        self._val = 255        # 0-255
        self._dragging = False
        self.setMinimumSize(200, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._rebuild_gradient()

    def _rebuild_gradient(self):
        self._gradient_cache = None  # invalidate

    def set_hsv(self, h, s, v, emit=False):
        self._hue = h
        self._sat = s
        self._val = v
        self._rebuild_gradient()
        self.update()
        if emit:
            color = QColor.fromHsv(h, s, v)
            self.color_changed.emit(color.red(), color.green(), color.blue())

    def get_hsv(self):
        return self._hue, self._sat, self._val

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Build gradient image: hue-saturated left→right, value top→bottom
        img = QImage(w, h, QImage.Format.Format_RGB32)
        for px in range(w):
            s = int(px / (w - 1) * 255) if w > 1 else 255
            for py in range(h):
                v = int((1 - py / (h - 1)) * 255) if h > 1 else 255
                c = QColor.fromHsv(self._hue, s, v)
                img.setPixel(px, py, c.rgb())

        p.drawImage(0, 0, img)

        # Draw cursor
        cx = int(self._sat / 255 * (w - 1))
        cy = int((1 - self._val / 255) * (h - 1))
        pen_out = QPen(Qt.GlobalColor.white, 2)
        pen_in = QPen(Qt.GlobalColor.black, 1)
        p.setPen(pen_out)
        p.drawEllipse(QPoint(cx, cy), 7, 7)
        p.setPen(pen_in)
        p.drawEllipse(QPoint(cx, cy), 6, 6)

    def _pick_from_pos(self, x, y):
        w, h = self.width(), self.height()
        x = max(0, min(x, w - 1))
        y = max(0, min(y, h - 1))
        s = int(x / (w - 1) * 255) if w > 1 else 255
        v = int((1 - y / (h - 1)) * 255) if h > 1 else 255
        self._sat = s
        self._val = v
        self.update()
        color = QColor.fromHsv(self._hue, s, v)
        self.color_changed.emit(color.red(), color.green(), color.blue())

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._pick_from_pos(e.position().x(), e.position().y())

    def mouseMoveEvent(self, e: QMouseEvent):
        if self._dragging:
            self._pick_from_pos(e.position().x(), e.position().y())

    def mouseReleaseEvent(self, e: QMouseEvent):
        self._dragging = False


# ─────────────────────────────────────────────────────────────────────────────
# Hue Bar (vertical rainbow gradient)
# ─────────────────────────────────────────────────────────────────────────────

class HueBar(QWidget):
    hue_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hue = 0
        self._dragging = False
        self.setFixedWidth(22)
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def set_hue(self, h, emit=False):
        self._hue = h
        self.update()
        if emit:
            self.hue_changed.emit(h)

    def paintEvent(self, event):
        p = QPainter(self)
        h = self.height()
        grad = QLinearGradient(0, 0, 0, h)
        for i in range(7):
            grad.setColorAt(i / 6, QColor.fromHsv(int(i / 6 * 359), 255, 255))
        p.fillRect(0, 0, self.width(), h, grad)

        # Cursor line
        cy = int(self._hue / 359 * (h - 1))
        p.setPen(QPen(Qt.GlobalColor.white, 2))
        p.drawLine(0, cy, self.width(), cy)
        p.setPen(QPen(Qt.GlobalColor.black, 1))
        p.drawLine(1, cy, self.width() - 1, cy)

    def _pick(self, y):
        h = self.height()
        y = max(0, min(y, h - 1))
        hue = int(y / (h - 1) * 359) if h > 1 else 0
        self._hue = hue
        self.update()
        self.hue_changed.emit(hue)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._pick(e.position().y())

    def mouseMoveEvent(self, e):
        if self._dragging:
            self._pick(e.position().y())

    def mouseReleaseEvent(self, e):
        self._dragging = False


# ─────────────────────────────────────────────────────────────────────────────
# Alpha / Value Bar (vertical gradient from black to current color)
# ─────────────────────────────────────────────────────────────────────────────

class ValueBar(QWidget):
    """Barra vertical de luminosidad (Value) independiente."""
    value_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hue = 0
        self._sat = 255
        self._val = 255
        self._dragging = False
        self.setFixedWidth(22)
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def set_hsv(self, h, s, v, emit=False):
        self._hue = h
        self._sat = s
        self._val = v
        self.update()
        if emit:
            self.value_changed.emit(v)

    def paintEvent(self, event):
        p = QPainter(self)
        h = self.height()
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, QColor.fromHsv(self._hue, self._sat, 255))
        grad.setColorAt(1, QColor.fromHsv(self._hue, self._sat, 0))
        p.fillRect(0, 0, self.width(), h, grad)

        cy = int((1 - self._val / 255) * (h - 1))
        p.setPen(QPen(Qt.GlobalColor.white, 2))
        p.drawLine(0, cy, self.width(), cy)
        p.setPen(QPen(Qt.GlobalColor.black, 1))
        p.drawLine(1, cy, self.width() - 1, cy)

    def _pick(self, y):
        h = self.height()
        y = max(0, min(y, h - 1))
        v = int((1 - y / (h - 1)) * 255) if h > 1 else 255
        self._val = v
        self.update()
        self.value_changed.emit(v)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._pick(e.position().y())

    def mouseMoveEvent(self, e):
        if self._dragging:
            self._pick(e.position().y())

    def mouseReleaseEvent(self, e):
        self._dragging = False


# ─────────────────────────────────────────────────────────────────────────────
# Color Swatch Grid (16-slot GBA palette)
# ─────────────────────────────────────────────────────────────────────────────

class PaletteSwatchGrid(QWidget):
    """Grid de 16 swatches para la paleta GBA (4×4)."""
    slot_selected = pyqtSignal(int)    # emite el índice seleccionado

    SWATCH = 30  # px por swatch
    COLS = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        # 16 colores: índice 0 = transparente
        self._colors = [(0, 0, 0)] * 16
        self._selected = 1
        rows = (16 + self.COLS - 1) // self.COLS
        self.setFixedSize(self.COLS * self.SWATCH, rows * self.SWATCH)

    def set_palette(self, colors):
        """colors: lista de (r,g,b) de hasta 16 elementos."""
        self._colors = list(colors[:16])
        while len(self._colors) < 16:
            self._colors.append((0, 0, 0))
        self.update()

    def set_color_at(self, idx, r, g, b):
        if 0 <= idx < 16:
            self._colors[idx] = (r, g, b)
            self.update()

    def get_colors(self):
        return list(self._colors)

    def paintEvent(self, event):
        p = QPainter(self)
        S = self.SWATCH
        for i, (r, g, b) in enumerate(self._colors):
            col = i % self.COLS
            row = i // self.COLS
            x, y = col * S, row * S
            if i == 0:
                # Transparent: checkered pattern
                p.fillRect(x, y, S, S, QColor(200, 200, 200))
                p.fillRect(x, y, S // 2, S // 2, QColor(255, 255, 255))
                p.fillRect(x + S // 2, y + S // 2, S // 2, S // 2, QColor(255, 255, 255))
            else:
                p.fillRect(x, y, S, S, QColor(r, g, b))

            # Selection border
            if i == self._selected:
                p.setPen(QPen(QColor(255, 255, 255), 3))
                p.drawRect(x + 1, y + 1, S - 3, S - 3)
                p.setPen(QPen(QColor(0, 0, 0), 1))
                p.drawRect(x + 3, y + 3, S - 7, S - 7)
            else:
                p.setPen(QPen(QColor(40, 40, 40), 1))
                p.drawRect(x, y, S - 1, S - 1)

        # Index labels
        p.setFont(QFont("Consolas", 7))
        for i in range(16):
            col = i % self.COLS
            row = i // self.COLS
            x, y = col * S, row * S
            r, g, b = self._colors[i]
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            p.setPen(Qt.GlobalColor.white if lum < 128 else Qt.GlobalColor.black)
            p.drawText(QRect(x, y + S - 11, S, 11), Qt.AlignmentFlag.AlignCenter, f"{i:X}")

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            S = self.SWATCH
            col = int(e.position().x()) // S
            row = int(e.position().y()) // S
            idx = row * self.COLS + col
            if 0 < idx < 16:  # No seleccionar slot 0 (transparente)
                self._selected = idx
                self.update()
                self.slot_selected.emit(idx)


# ─────────────────────────────────────────────────────────────────────────────
# Main Palette Editor Dialog
# ─────────────────────────────────────────────────────────────────────────────

class PaletteEditorDialog(QDialog):
    """
    Editor de paleta GBA completo con:
    - Cuadro HSV (Saturación × Brillo)
    - Barra de tono (Hue)
    - Barra de brillo (Value)
    - Entradas RGB individuales (0-248 cuantizadas a paso de 8)
    - Entrada HEX (#RRGGBB)
    - Grid de 16 swatches de paleta
    - Preview de color anterior vs nuevo
    - Opción de crear paleta nueva (todo negro excepto transparente)
    """
    palette_accepted = pyqtSignal(list)  # lista de (r,g,b) × 16
    palette_changed_live = pyqtSignal(list)  # se emite en tiempo real

    DARK_BG  = "#1E1E2E"
    MID_BG   = "#2A2A3E"
    ACCENT   = "#7C5CFC"
    TEXT     = "#CDD6F4"
    BORDER   = "#45475A"
    SLOT0_TIP = "El slot 0 es siempre transparente (color mágico del GBA). No se puede editar."

    def __init__(self, palette_colors, parent=None):
        """
        palette_colors: lista de (r,g,b) × 16 leída desde la ROM.
        """
        super().__init__(parent)
        self.setWindowTitle("Melody Portrait Engine — Editor de Paleta GBA")
        self.setModal(True)
        self.resize(680, 520)
        self.setMinimumSize(600, 480)

        # Internals
        self._palette = [tuple(c) for c in palette_colors[:16]]
        while len(self._palette) < 16:
            self._palette.append((0, 0, 0))
        self._orig_palette = list(self._palette)
        self._selected_slot = 1
        self._updating = False

        self._apply_stylesheet()
        self._build_ui()
        self._select_slot(1)

    def _apply_stylesheet(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {self.DARK_BG};
                color: {self.TEXT};
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
            }}
            QLabel {{
                color: {self.TEXT};
            }}
            QFrame#card {{
                background-color: {self.MID_BG};
                border: 1px solid {self.BORDER};
                border-radius: 8px;
                padding: 6px;
            }}
            QLineEdit, QSpinBox {{
                background-color: #313244;
                color: {self.TEXT};
                border: 1px solid {self.BORDER};
                border-radius: 4px;
                padding: 3px 6px;
                font-family: 'Consolas', monospace;
                font-size: 12px;
            }}
            QLineEdit:focus, QSpinBox:focus {{
                border: 1px solid {self.ACCENT};
            }}
            QSlider::groove:horizontal {{
                height: 6px;
                border-radius: 3px;
                background: #45475A;
            }}
            QSlider::handle:horizontal {{
                width: 14px; height: 14px;
                border-radius: 7px;
                background: {self.ACCENT};
                margin: -4px 0;
            }}
            QPushButton {{
                background-color: #45475A;
                color: {self.TEXT};
                border: 1px solid {self.BORDER};
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {self.ACCENT};
                color: white;
            }}
            QPushButton#btn_accept {{
                background-color: {self.ACCENT};
                color: white;
            }}
            QPushButton#btn_accept:hover {{
                background-color: #9D7EFF;
            }}
            QPushButton#btn_new_pal {{
                background-color: #2B4A2B;
                color: #A9EFAF;
                border-color: #4CAF50;
            }}
            QPushButton#btn_new_pal:hover {{
                background-color: #3D6E3D;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 16px;
            }}
        """)

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(12, 12, 12, 12)

        # ── LEFT COLUMN: Color picker ──────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(8)

        lbl_picker = QLabel("🎨  Selector de Color")
        lbl_picker.setStyleSheet("font-weight: bold; font-size: 13px;")
        left.addWidget(lbl_picker)

        # HSV square + bars row
        picker_row = QHBoxLayout()
        picker_row.setSpacing(6)

        self.hsv_square = HSVSquare()
        self.hsv_square.color_changed.connect(self._on_square_color)
        picker_row.addWidget(self.hsv_square)

        self.hue_bar = HueBar()
        self.hue_bar.hue_changed.connect(self._on_hue_changed)
        picker_row.addWidget(self.hue_bar)

        self.val_bar = ValueBar()
        self.val_bar.value_changed.connect(self._on_val_changed)
        picker_row.addWidget(self.val_bar)

        left.addLayout(picker_row)

        # ── Preview (old vs new) ───────────────────────────────────────────
        preview_row = QHBoxLayout()
        preview_row.setSpacing(4)
        lbl_prev = QLabel("Anterior:")
        lbl_prev.setFixedWidth(55)
        self.preview_old = QLabel()
        self.preview_old.setFixedSize(48, 24)
        self.preview_old.setStyleSheet("border: 1px solid #555; border-radius: 3px;")
        lbl_new = QLabel("Nuevo:")
        lbl_new.setFixedWidth(48)
        self.preview_new = QLabel()
        self.preview_new.setFixedSize(48, 24)
        self.preview_new.setStyleSheet("border: 1px solid #555; border-radius: 3px;")
        preview_row.addWidget(lbl_prev)
        preview_row.addWidget(self.preview_old)
        preview_row.addSpacing(8)
        preview_row.addWidget(lbl_new)
        preview_row.addWidget(self.preview_new)
        preview_row.addStretch()
        left.addLayout(preview_row)

        # ── HEX Input ─────────────────────────────────────────────────────
        hex_row = QHBoxLayout()
        lbl_hex = QLabel("HEX:")
        lbl_hex.setFixedWidth(38)
        self.inp_hex = QLineEdit()
        self.inp_hex.setPlaceholderText("#RRGGBB")
        self.inp_hex.setFixedWidth(90)
        self.inp_hex.setMaxLength(7)
        self.inp_hex.editingFinished.connect(self._on_hex_edited)

        lbl_gba = QLabel("GBA:")
        lbl_gba.setFixedWidth(35)
        self.lbl_gba_val = QLabel("0x0000")
        self.lbl_gba_val.setStyleSheet("font-family: Consolas; color: #89B4FA;")

        hex_row.addWidget(lbl_hex)
        hex_row.addWidget(self.inp_hex)
        hex_row.addSpacing(10)
        hex_row.addWidget(lbl_gba)
        hex_row.addWidget(self.lbl_gba_val)
        hex_row.addStretch()
        left.addLayout(hex_row)

        # ── RGB Sliders ────────────────────────────────────────────────────
        rgb_grid = QGridLayout()
        rgb_grid.setVerticalSpacing(4)

        self.sliders = {}
        self.spins = {}
        channel_info = [
            ("R", "#FF4444", 0),
            ("G", "#44FF88", 1),
            ("B", "#4488FF", 2),
        ]
        for row_idx, (ch, color, idx) in enumerate(channel_info):
            lbl = QLabel(ch)
            lbl.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 13px;")
            lbl.setFixedWidth(16)

            sld = QSlider(Qt.Orientation.Horizontal)
            sld.setRange(0, 255)
            sld.setSingleStep(8)
            sld.setPageStep(8)
            sld.setStyleSheet(f"""
                QSlider::groove:horizontal {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #1E1E2E, stop:1 {color}); height:6px; border-radius:3px; }}
                QSlider::handle:horizontal {{ width:14px; height:14px; border-radius:7px;
                    background: {color}; margin:-4px 0; }}
            """)

            spin = QSpinBox()
            spin.setRange(0, 255)
            spin.setSingleStep(8)
            spin.setFixedWidth(60)

            sld.valueChanged.connect(lambda val, c=ch: self._on_slider(c, val))
            spin.valueChanged.connect(lambda val, c=ch: self._on_spin(c, val))

            self.sliders[ch] = sld
            self.spins[ch] = spin

            rgb_grid.addWidget(lbl, row_idx, 0)
            rgb_grid.addWidget(sld, row_idx, 1)
            rgb_grid.addWidget(spin, row_idx, 2)

        left.addLayout(rgb_grid)

        # ── Apply to slot button ───────────────────────────────────────────
        btn_apply = QPushButton("✔  Aplicar color al slot seleccionado")
        btn_apply.setObjectName("btn_accept")
        btn_apply.clicked.connect(self._apply_to_slot)
        left.addWidget(btn_apply)

        left.addStretch()

        # ── RIGHT COLUMN: Palette swatches + actions ───────────────────────
        right = QVBoxLayout()
        right.setSpacing(8)

        lbl_pal = QLabel("🖌  Paleta GBA (16 colores)")
        lbl_pal.setStyleSheet("font-weight: bold; font-size: 13px;")
        right.addWidget(lbl_pal)

        tip = QLabel("Clic en un slot para seleccionarlo. El slot 0 es transparente.")
        tip.setStyleSheet("color: #6C7086; font-size: 10px;")
        tip.setWordWrap(True)
        right.addWidget(tip)

        self.swatch_grid = PaletteSwatchGrid()
        self.swatch_grid.set_palette(self._palette)
        self.swatch_grid.slot_selected.connect(self._select_slot)
        right.addWidget(self.swatch_grid, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # Slot info label
        self.lbl_slot_info = QLabel("Slot seleccionado: 1")
        self.lbl_slot_info.setStyleSheet("color: #89B4FA; font-weight: bold;")
        right.addWidget(self.lbl_slot_info)

        # ── Nueva paleta / resetear ────────────────────────────────────────
        btn_new = QPushButton("✨  Nueva Paleta (Todo Negro)")
        btn_new.setObjectName("btn_new_pal")
        btn_new.clicked.connect(self._new_palette)
        right.addWidget(btn_new)

        btn_reset = QPushButton("↺  Restaurar Paleta Original")
        btn_reset.clicked.connect(self._reset_palette)
        right.addWidget(btn_reset)

        # ── Herramientas de Paleta ─────────────────────────────────────────
        tools_grid = QGridLayout()
        tools_grid.setSpacing(4)
        
        btn_copy = QPushButton("📋 Copiar Hex")
        btn_copy.clicked.connect(self._copy_hex)
        tools_grid.addWidget(btn_copy, 0, 0)
        
        btn_paste = QPushButton("📝 Pegar Hex")
        btn_paste.clicked.connect(self._paste_hex)
        tools_grid.addWidget(btn_paste, 0, 1)
        
        btn_import = QPushButton("📂 Importar .pal")
        btn_import.clicked.connect(self._import_pal)
        tools_grid.addWidget(btn_import, 1, 0)
        
        btn_export = QPushButton("💾 Exportar .pal")
        btn_export.clicked.connect(self._export_pal)
        tools_grid.addWidget(btn_export, 1, 1)
        
        right.addLayout(tools_grid)

        right.addStretch()

        # ── Accept / Cancel ────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_ok = QPushButton("💾  Guardar Paleta")
        btn_ok.setObjectName("btn_accept")
        btn_ok.clicked.connect(self._accept)
        btn_cancel = QPushButton("✖  Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        right.addLayout(btn_row)

        # ── Assemble root ──────────────────────────────────────────────────
        root.addLayout(left, stretch=3)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {self.BORDER};")
        root.addWidget(sep)

        root.addLayout(right, stretch=2)

    # ── Slot selection ─────────────────────────────────────────────────────

    def _select_slot(self, idx):
        self._selected_slot = idx
        self.swatch_grid._selected = idx
        self.swatch_grid.update()
        self.lbl_slot_info.setText(f"Slot seleccionado: {idx}  (Índice GBA: {idx})")
        r, g, b = self._palette[idx]
        self._set_picker_rgb(r, g, b)
        self._update_old_preview(r, g, b)

    def _update_old_preview(self, r, g, b):
        rq, gq, bq = quantize_to_gba(r, g, b)
        self.preview_old.setStyleSheet(
            f"background-color: rgb({rq},{gq},{bq}); border: 1px solid #555; border-radius: 3px;"
        )

    def _set_picker_rgb(self, r, g, b):
        """Actualiza todos los controles para reflejar un color RGB dado."""
        self._updating = True
        rq, gq, bq = quantize_to_gba(r, g, b)

        # Sliders & spins
        for ch, val in zip("RGB", (rq, gq, bq)):
            self.sliders[ch].setValue(val)
            self.spins[ch].setValue(val)

        # HEX
        self.inp_hex.setText(f"#{rq:02X}{gq:02X}{bq:02X}")

        # GBA word
        gba_val = rgb888_to_gba(rq, gq, bq)
        self.lbl_gba_val.setText(f"0x{gba_val:04X}")

        # HSV picker
        color = QColor(rq, gq, bq)
        h, s, v, _ = color.getHsv()
        if h < 0: h = 0
        self.hsv_square.set_hsv(h, s, v)
        self.hue_bar.set_hue(h)
        self.val_bar.set_hsv(h, s, v)

        # New preview
        self.preview_new.setStyleSheet(
            f"background-color: rgb({rq},{gq},{bq}); border: 1px solid #555; border-radius: 3px;"
        )
        self._updating = False

    def _current_rgb(self):
        return (
            self.spins["R"].value(),
            self.spins["G"].value(),
            self.spins["B"].value()
        )

    def _on_square_color(self, r, g, b):
        if self._updating:
            return
        self._updating = True
        rq, gq, bq = quantize_to_gba(r, g, b)
        for ch, val in zip("RGB", (rq, gq, bq)):
            self.sliders[ch].setValue(val)
            self.spins[ch].setValue(val)
        self.inp_hex.setText(f"#{rq:02X}{gq:02X}{bq:02X}")
        gba_val = rgb888_to_gba(rq, gq, bq)
        self.lbl_gba_val.setText(f"0x{gba_val:04X}")
        self.preview_new.setStyleSheet(
            f"background-color: rgb({rq},{gq},{bq}); border: 1px solid #555; border-radius: 3px;"
        )
        # Sync hue/val bars to square's current hsv
        h, s, v = self.hsv_square.get_hsv()
        self.hue_bar.set_hue(h)
        self.val_bar.set_hsv(h, s, v)
        self._updating = False

    def _on_hue_changed(self, hue):
        if self._updating:
            return
        h, s, v = self.hsv_square.get_hsv()
        self.hsv_square.set_hsv(hue, s, v)
        self.val_bar.set_hsv(hue, s, v)
        color = QColor.fromHsv(hue, s, v)
        self._on_square_color(color.red(), color.green(), color.blue())

    def _on_val_changed(self, val):
        if self._updating:
            return
        h, s, _ = self.hsv_square.get_hsv()
        self.hsv_square.set_hsv(h, s, val)
        color = QColor.fromHsv(h, s, val)
        self._on_square_color(color.red(), color.green(), color.blue())

    def _on_slider(self, ch, val):
        if self._updating:
            return
        # Snap to GBA step (8)
        snapped = (val // 8) * 8
        if snapped != self.sliders[ch].value():
            self._updating = True
            self.sliders[ch].setValue(snapped)
            self._updating = False
        self._updating = True
        self.spins[ch].setValue(snapped)
        self._updating = False
        r, g, b = self._current_rgb()
        self._sync_from_rgb(r, g, b)

    def _on_spin(self, ch, val):
        if self._updating:
            return
        snapped = (val // 8) * 8
        if snapped != val:
            self._updating = True
            self.spins[ch].setValue(snapped)
            self._updating = False
        self._updating = True
        self.sliders[ch].setValue(snapped)
        self._updating = False
        r, g, b = self._current_rgb()
        self._sync_from_rgb(r, g, b)

    def _sync_from_rgb(self, r, g, b):
        rq, gq, bq = quantize_to_gba(r, g, b)
        self.inp_hex.setText(f"#{rq:02X}{gq:02X}{bq:02X}")
        gba_val = rgb888_to_gba(rq, gq, bq)
        self.lbl_gba_val.setText(f"0x{gba_val:04X}")
        color = QColor(rq, gq, bq)
        h, s, v, _ = color.getHsv()
        if h < 0: h = 0
        self._updating = True
        self.hsv_square.set_hsv(h, s, v)
        self.hue_bar.set_hue(h)
        self.val_bar.set_hsv(h, s, v)
        self._updating = False
        self.preview_new.setStyleSheet(
            f"background-color: rgb({rq},{gq},{bq}); border: 1px solid #555; border-radius: 3px;"
        )
        
        # Auto-aplicar en tiempo real al slot seleccionado
        if self._selected_slot != 0:
            self._palette[self._selected_slot] = (rq, gq, bq)
            self.swatch_grid.set_color_at(self._selected_slot, rq, gq, bq)
            self.palette_changed_live.emit(self._palette)

    def _on_hex_edited(self):
        txt = self.inp_hex.text().strip().lstrip("#")
        if len(txt) == 6:
            try:
                r = int(txt[0:2], 16)
                g = int(txt[2:4], 16)
                b = int(txt[4:6], 16)
                rq, gq, bq = quantize_to_gba(r, g, b)
                self._set_picker_rgb(rq, gq, bq)
            except ValueError:
                pass

    def _apply_to_slot(self):
        r, g, b = self._current_rgb()
        rq, gq, bq = quantize_to_gba(r, g, b)
        self._palette[self._selected_slot] = (rq, gq, bq)
        self.swatch_grid.set_color_at(self._selected_slot, rq, gq, bq)
        self._update_old_preview(rq, gq, bq)
        self.palette_changed_live.emit(self._palette)

    def _new_palette(self):
        reply = QMessageBox.question(
            self, "Nueva Paleta",
            "¿Crear una paleta nueva? Los 15 colores (slots 1-15) se pondrán en negro.\n"
            "El slot 0 siempre es transparente.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._palette = [(0, 0, 0)] * 16
            self.swatch_grid.set_palette(self._palette)
            self._select_slot(1)

    def _reset_palette(self):
        self._palette = list(self._orig_palette)
        self.swatch_grid.set_palette(self._palette)
        self._select_slot(self._selected_slot)
        self.palette_changed_live.emit(list(self._palette))

    def _accept(self):
        self.palette_accepted.emit(list(self._palette))
        self.accept()

    def get_palette(self):
        """Devuelve la paleta actual como lista de (r,g,b) × 16."""
        return list(self._palette)

    def get_palette_gba_bytes(self):
        """Devuelve la paleta como bytearray de 32 bytes GBA BGR555."""
        data = bytearray(32)
        for i, (r, g, b) in enumerate(self._palette):
            c16 = rgb888_to_gba(r, g, b)
            struct.pack_into('<H', data, i * 2, c16)
        return data

    # ── Exportar/Importar/Copiar/Pegar ─────────────────────────────────────

    def _copy_hex(self):
        from PyQt6.QtWidgets import QApplication
        hex_list = []
        for (r, g, b) in self._palette:
            rq, gq, bq = quantize_to_gba(r, g, b)
            hex_list.append(f"#{rq:02X}{gq:02X}{bq:02X}")
        text = ", ".join(hex_list)
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copiado", "Paleta copiada al portapapeles en formato Hexadecimal.")

    def _paste_hex(self):
        from PyQt6.QtWidgets import QApplication
        text = QApplication.clipboard().text()
        import re
        # Extraer cualquier secuencia de 6 caracteres hex (con o sin #)
        matches = re.findall(r'#?([0-9a-fA-F]{6})', text)
        if not matches:
            QMessageBox.warning(self, "Error", "No se encontraron colores hexadecimales válidos en el portapapeles.")
            return
            
        if len(matches) < 16:
            QMessageBox.warning(self, "Advertencia", f"Solo se encontraron {len(matches)} colores. Se rellenará el resto con negro.")
            
        new_pal = []
        for i in range(16):
            if i < len(matches):
                hx = matches[i]
                r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
                new_pal.append(quantize_to_gba(r, g, b))
            else:
                new_pal.append((0, 0, 0))
                
        # Mantener el primer color como transparente según GBA
        new_pal[0] = self._palette[0]
        
        self._palette = new_pal
        self.swatch_grid.set_palette(self._palette)
        self._select_slot(1)
        self.palette_changed_live.emit(list(self._palette))
        QMessageBox.information(self, "Pegado", "Paleta pegada correctamente.")

    def _import_pal(self):
        from PyQt6.QtWidgets import QFileDialog
        import os
        path, _ = QFileDialog.getOpenFileName(self, "Importar Paleta", "", "JASC-PAL (*.pal);;All Files (*)")
        if not path: return
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f.readlines() if l.strip()]
                
            if len(lines) >= 3 and lines[0] == "JASC-PAL":
                # Es JASC-PAL
                count = int(lines[2])
                color_lines = lines[3:3+count]
                new_pal = []
                for cl in color_lines:
                    parts = cl.split()
                    if len(parts) >= 3:
                        r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
                        new_pal.append(quantize_to_gba(r, g, b))
            else:
                # Intento leer lineas de "R G B" plano
                new_pal = []
                for cl in lines:
                    parts = cl.replace(",", " ").split()
                    if len(parts) >= 3:
                        try:
                            r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
                            new_pal.append(quantize_to_gba(r, g, b))
                        except: pass
                        
            if not new_pal:
                raise ValueError("No se encontraron colores validos.")
                
            while len(new_pal) < 16:
                new_pal.append((0,0,0))
                
            # Mantener transparente original
            new_pal[0] = self._palette[0]
            
            self._palette = new_pal[:16]
            self.swatch_grid.set_palette(self._palette)
            self._select_slot(1)
            self.palette_changed_live.emit(list(self._palette))
            QMessageBox.information(self, "Importado", "Paleta importada correctamente.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al importar paleta:\n{e}")

    def _export_pal(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Exportar Paleta", "paleta.pal", "JASC-PAL (*.pal)")
        if not path: return
        
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("JASC-PAL\n0100\n16\n")
                for r, g, b in self._palette:
                    rq, gq, bq = quantize_to_gba(r, g, b)
                    f.write(f"{rq} {gq} {bq}\n")
            QMessageBox.information(self, "Exportado", f"Paleta guardada en {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al exportar paleta:\n{e}")
