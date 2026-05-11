# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.1.0)
# "The Imposibility Update"
# Desarrollado por: Denisovich728
# ============================================================
import sys
import os
import struct
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame, QGridLayout,
    QFileDialog, QMessageBox, QSpinBox, QComboBox, QCheckBox,
    QPlainTextEdit, QLineEdit, QButtonGroup, QToolButton
)
from PyQt6.QtGui import QColor, QPainter, QPen, QAction, QIcon
from PyQt6.QtCore import Qt, pyqtSignal, QSize

class TileCanvas(QWidget):
    pixelChanged = pyqtSignal()
    colorPicked = pyqtSignal(int)

    def __init__(self, scale=40):
        super().__init__()
        self.scale = scale
        self.tile_h = 16
        self.setFixedSize(8 * scale, self.tile_h * scale)
        self.pixels = [[0 for _ in range(8)] for _ in range(32)]
        self.palette = [QColor(0,0,0) for _ in range(256)]
        self.current_color = 1
        self.current_tool = "brush" # brush, eraser, picker
        self.interleave_rows = False
        self.bpp = 4
        self._init_palette()

    def _init_palette(self):
        # Colores básicos (16)
        colors = ["#1a1a1a", "#f0e6b4", "#000000", "#ff0000", "#00ff00", "#0000ff",
                  "#ffff00", "#ff00ff", "#00ffff", "#ffffff", "#888888", "#444444",
                  "#884400", "#448800", "#004488", "#444400"]
        for i, c in enumerate(colors): self.palette[i] = QColor(c)
        for i in range(16, 256): self.palette[i] = QColor(i, i, i)

    def _unpack_row(self, row_data, row_idx):
        if row_idx >= 32: return
        if self.bpp == 1:
            b = row_data[0]
            for x in range(8): self.pixels[row_idx][x] = (b >> x) & 1
        elif self.bpp == 2:
            for cp in range(2):
                b = row_data[cp]
                for i in range(4): self.pixels[row_idx][cp*4 + i] = (b >> (i*2)) & 3
        elif self.bpp == 4:
            for cp in range(4):
                b = row_data[cp]
                self.pixels[row_idx][cp*2] = b & 0xF
                self.pixels[row_idx][cp*2+1] = (b >> 4) & 0xF
        elif self.bpp == 8:
            for x in range(8): self.pixels[row_idx][x] = row_data[x]

    def _pack_row(self, row_idx):
        row_data = bytearray(self.bpp)
        if self.bpp == 1:
            b = 0
            for x in range(8):
                if self.pixels[row_idx][x]: b |= (1 << x)
            row_data[0] = b
        elif self.bpp == 2:
            for cp in range(2):
                b = 0
                for i in range(4):
                    p = self.pixels[row_idx][cp*4 + i]
                    b |= (p & 3) << (i*2)
                row_data[cp] = b
        elif self.bpp == 4:
            for cp in range(4):
                p0, p1 = self.pixels[row_idx][cp*2], self.pixels[row_idx][cp*2+1]
                row_data[cp] = (p0 & 0xF) | ((p1 & 0xF) << 4)
        elif self.bpp == 8:
            for x in range(8): row_data[x] = self.pixels[row_idx][x] & 0xFF
        return row_data

    def set_data(self, data, interleave_rows=False, bpp=4, h=16):
        self.interleave_rows, self.bpp, self.tile_h = interleave_rows, bpp, h
        self.setFixedSize(8 * self.scale, h * self.scale)
        bpr = self.bpp
        expected = h * bpr
        if len(data) < expected: data = data + bytearray(expected - len(data))
        
        if interleave_rows and h >= 16:
            half = h // 2
            for row in range(half):
                off_top = row * (2 * bpr)
                self._unpack_row(data[off_top : off_top + bpr], row)
                off_bot = off_top + bpr
                self._unpack_row(data[off_bot : off_bot + bpr], row + half)
        else:
            for row in range(h):
                self._unpack_row(data[row * bpr : (row+1) * bpr], row)
        self.update()

    def get_data(self):
        bpr = self.bpp
        data = bytearray(self.tile_h * bpr)
        if self.interleave_rows and self.tile_h >= 16:
            half = self.tile_h // 2
            for row in range(half):
                off_top = row * (2 * bpr)
                data[off_top : off_top + bpr] = self._pack_row(row)
                off_bot = off_top + bpr
                data[off_bot : off_bot + bpr] = self._pack_row(row + half)
        else:
            for row in range(self.tile_h):
                data[row * bpr : (row+1) * bpr] = self._pack_row(row)
        return data

    def paintEvent(self, event):
        qp = QPainter(self)
        for y in range(self.tile_h):
            for x in range(8):
                qp.fillRect(x*self.scale, y*self.scale, self.scale, self.scale, self.palette[self.pixels[y][x]])
        
        qp.setPen(QPen(QColor(255,255,255,30), 1))
        for i in range(9): qp.drawLine(i*self.scale, 0, i*self.scale, self.height())
        for i in range(self.tile_h + 1): qp.drawLine(0, i*self.scale, self.width(), i*self.scale)
        if self.tile_h >= 16:
            qp.setPen(QPen(QColor(255,0,0,120), 1, Qt.PenStyle.DashLine))
            qp.drawLine(0, (self.tile_h//2)*self.scale, self.width(), (self.tile_h//2)*self.scale)

    def mousePressEvent(self, event): self._handle_mouse(event)
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton: self._handle_mouse(event)

    def _handle_mouse(self, event):
        x, y = int(event.position().x() // self.scale), int(event.position().y() // self.scale)
        if 0 <= x < 8 and 0 <= y < self.tile_h:
            if event.button() == Qt.MouseButton.RightButton or self.current_tool == "picker":
                self.colorPicked.emit(self.pixels[y][x])
            else:
                color = self.current_color if self.current_tool == "brush" else 0
                if self.pixels[y][x] != color:
                    self.pixels[y][x] = color
                    self.update(); self.pixelChanged.emit()

    def flip_h(self):
        for y in range(self.tile_h): self.pixels[y] = self.pixels[y][::-1]
        self.update(); self.pixelChanged.emit()

    def flip_v(self):
        active = self.pixels[:self.tile_h]
        self.pixels[:self.tile_h] = active[::-1]
        self.update(); self.pixelChanged.emit()

class TileGridItem(QFrame):
    clicked = pyqtSignal(int)
    def __init__(self, index, data, offset=0, interleave_rows=False, bpp=4, h=16, palette=None):
        super().__init__()
        self.index, self.data, self.interleave_rows = index, data, interleave_rows
        self.bpp, self.tile_h, self.palette = bpp, h, palette
        self.offset, self.selected = offset, False
        self.setFixedSize(65, h * 6 + 25)
        self.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Plain)

    def paintEvent(self, event):
        super().paintEvent(event)
        qp = QPainter(self)
        if self.selected:
            qp.setPen(QPen(QColor(255,255,0), 2))
            qp.drawRect(1, 1, self.width()-2, self.height()-2)
        qp.setPen(QPen(QColor(180, 180, 180), 1))
        qp.drawText(5, self.height() - 5, f"{self.offset:06X}")
        ps, bpr, half = 6, self.bpp, self.tile_h // 2
        for row in range(self.tile_h):
            if self.interleave_rows and self.tile_h >= 16:
                off = row * (2 * bpr) if row < half else (row - half) * (2 * bpr) + bpr
            else: off = row * bpr
            if off >= len(self.data): continue
            if self.bpp == 1:
                b = self.data[off]
                for x in range(8):
                    if (b >> x) & 1: qp.fillRect(x*ps+6, row*ps+6, ps, ps, self.palette[1])
            elif self.bpp == 4:
                for cp in range(4):
                    if off+cp >= len(self.data): break
                    b = self.data[off+cp]
                    p0, p1 = b & 0xF, (b >> 4) & 0xF
                    if p0: qp.fillRect((cp*2)*ps+6, row*ps+6, ps, ps, self.palette[p0])
                    if p1: qp.fillRect((cp*2+1)*ps+6, row*ps+6, ps, ps, self.palette[p1])
            elif self.bpp == 8:
                for x in range(8):
                    if off+x >= len(self.data): break
                    p = self.data[off+x]
                    if p: qp.fillRect(x*ps+6, row*ps+6, ps, ps, self.palette[p])
    def mousePressEvent(self, event): self.clicked.emit(self.index)

class TileEditorWidget(QWidget):
    def __init__(self, parent=None, project=None, standalone_data=None):
        super().__init__(parent)
        self.project = project
        self.rom_data = None
        if project:
            self.rom_data = project.virtual_rom
        elif standalone_data:
            self.rom_data = standalone_data
            
        self.selected_idx = -1
        self._init_ui()
        if self.rom_data is not None: self._refresh()

    def set_rom_data(self, data):
        self.rom_data = data
        self._refresh()

    def set_project(self, project):
        self.project = project
        if project:
            self.rom_data = project.virtual_rom
            self._refresh()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        left = QWidget(); l_lay = QVBoxLayout(left)
        
        top = QHBoxLayout()
        if not self.project:
            btn_open = QPushButton("📂 Abrir ROM")
            btn_open.clicked.connect(self._open_file_standalone)
            top.addWidget(btn_open)

        top.addWidget(QLabel("Offset:"))
        self.edit_off = QLineEdit("75A440"); top.addWidget(self.edit_off)
        top.addWidget(QLabel("Fino:"))
        self.spin_fine = QSpinBox(); self.spin_fine.setRange(-1000, 1000); top.addWidget(self.spin_fine)
        btn_go = QPushButton("<"); btn_go.setFixedWidth(30); btn_go.clicked.connect(lambda: self._page(-1)); top.addWidget(btn_go)
        btn_go2 = QPushButton(">"); btn_go2.setFixedWidth(30); btn_go2.clicked.connect(lambda: self._page(1)); top.addWidget(btn_go2)
        btn_refresh = QPushButton("Ir"); btn_refresh.clicked.connect(self._refresh); top.addWidget(btn_refresh)
        l_lay.addLayout(top)

        cfg = QHBoxLayout()
        cfg.addWidget(QLabel("Alto:"))
        self.spin_h = QSpinBox(); self.spin_h.setRange(8, 32); self.spin_h.setValue(8); self.spin_h.setSingleStep(8); cfg.addWidget(self.spin_h)
        cfg.addWidget(QLabel("Grid:"))
        self.spin_w_grid = QSpinBox(); self.spin_w_grid.setRange(1, 40); self.spin_w_grid.setValue(15); cfg.addWidget(self.spin_w_grid)
        cfg.addWidget(QLabel("Stride:"))
        self.spin_stride = QSpinBox(); self.spin_stride.setRange(1, 255); self.spin_stride.setValue(30); cfg.addWidget(self.spin_stride)
        cfg.addWidget(QLabel("BPP:"))
        self.combo_bpp = QComboBox(); self.combo_bpp.addItems(["1 bpp", "2 bpp", "4 bpp", "8 bpp"]); self.combo_bpp.setCurrentIndex(2); cfg.addWidget(self.combo_bpp)
        l_lay.addLayout(cfg)

        self.chk_inter_rows = QCheckBox("Intercalar Filas"); self.chk_stride = QCheckBox("Usar Stride")
        self.chk_inter_rows.toggled.connect(self._refresh); self.chk_stride.toggled.connect(self._refresh)
        self.spin_h.valueChanged.connect(self._refresh); self.spin_w_grid.valueChanged.connect(self._refresh)
        self.spin_stride.valueChanged.connect(self._refresh); self.combo_bpp.currentIndexChanged.connect(self._refresh)
        chk_lay = QHBoxLayout(); chk_lay.addWidget(self.chk_inter_rows); chk_lay.addWidget(self.chk_stride); l_lay.addLayout(chk_lay)

        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.grid_w = QWidget(); self.grid_lay = QGridLayout(self.grid_w); self.grid_lay.setSpacing(2)
        self.scroll.setWidget(self.grid_w); l_lay.addWidget(self.scroll)
        layout.addWidget(left, 7)

        right = QWidget(); right.setFixedWidth(380); r_lay = QVBoxLayout(right)
        
        tools_lay = QHBoxLayout()
        self.btn_brush = QPushButton("🖌️ Pincel"); self.btn_brush.setCheckable(True); self.btn_brush.setChecked(True)
        self.btn_eraser = QPushButton("🧽 Borrador"); self.btn_eraser.setCheckable(True)
        self.btn_picker = QPushButton("🧪 Gotero"); self.btn_picker.setCheckable(True)
        self.tool_group = QButtonGroup(); self.tool_group.addButton(self.btn_brush); self.tool_group.addButton(self.btn_eraser); self.tool_group.addButton(self.btn_picker)
        self.btn_brush.clicked.connect(lambda: self._set_tool("brush"))
        self.btn_eraser.clicked.connect(lambda: self._set_tool("eraser"))
        self.btn_picker.clicked.connect(lambda: self._set_tool("picker"))
        tools_lay.addWidget(self.btn_brush); tools_lay.addWidget(self.btn_eraser); tools_lay.addWidget(self.btn_picker)
        
        tools_lay.addSpacing(10)
        tools_lay.addWidget(QLabel("Paleta ROM:"))
        self.palette_input = QLineEdit("0x117408")
        self.palette_input.setFixedWidth(70)
        self.palette_input.returnPressed.connect(self._load_palette_from_rom)
        tools_lay.addWidget(self.palette_input)
        
        btn_load_pal = QPushButton("🔄")
        btn_load_pal.setFixedWidth(30)
        btn_load_pal.clicked.connect(self._load_palette_from_rom)
        tools_lay.addWidget(btn_load_pal)
        
        btn_pal_prev = QPushButton("◀"); btn_pal_prev.setFixedWidth(25); btn_pal_prev.clicked.connect(lambda: self._step_palette(-32))
        btn_pal_next = QPushButton("▶"); btn_pal_next.setFixedWidth(25); btn_pal_next.clicked.connect(lambda: self._step_palette(32))
        tools_lay.addWidget(btn_pal_prev); tools_lay.addWidget(btn_pal_next)
        
        r_lay.addLayout(tools_lay)

        self.canvas = TileCanvas()
        self.canvas.pixelChanged.connect(self._apply_to_rom_silent)
        self.canvas.colorPicked.connect(self._on_color_picked)
        r_lay.addWidget(self.canvas, alignment=Qt.AlignmentFlag.AlignCenter)
        
        mirrors = QHBoxLayout()
        btn_flip_h = QPushButton("↔️ Espejo H"); btn_flip_h.clicked.connect(self.canvas.flip_h)
        btn_flip_v = QPushButton("↕️ Espejo V"); btn_flip_v.clicked.connect(self.canvas.flip_v)
        mirrors.addWidget(btn_flip_h); mirrors.addWidget(btn_flip_v); r_lay.addLayout(mirrors)

        c_grid = QGridLayout()
        self.pal_btns = []
        for i in range(16):
            b = QPushButton(str(i)); b.setFixedSize(30,30); b.setStyleSheet(f"background: {self.canvas.palette[i].name()}; border: 1px solid #555;")
            b.clicked.connect(lambda _, x=i: self._set_color(x)); c_grid.addWidget(b, i//8, i%8); self.pal_btns.append(b)
        r_lay.addLayout(c_grid)
        
        r_lay.addWidget(QLabel("Raw Hex Data:"))
        self.edit_hex = QPlainTextEdit(); self.edit_hex.setFixedHeight(80)
        self.edit_hex.setStyleSheet("font-family: 'Consolas'; background: #1a1a1a; color: #00ff00;")
        r_lay.addWidget(self.edit_hex)
        r_lay.addWidget(QPushButton("🔗 Sincronizar Hex -> Canvas", clicked=self._apply_hex))
        
        if self.project:
            r_lay.addWidget(QPushButton("💾 PERSISTIR CAMBIOS", clicked=self._persist_project))
        else:
            r_lay.addWidget(QPushButton("💾 GUARDAR EN ROM", clicked=self._save_to_rom_standalone))

        r_lay.addStretch()
        r_lay.addWidget(QLabel("--- PRESETS ---"))
        p1 = QHBoxLayout(); p1.addWidget(QPushButton("🅰️ Font Main", clicked=self._preset_main)); p1.addWidget(QPushButton("⌨️ Keyboard", clicked=self._preset_kb)); r_lay.addLayout(p1)
        p2 = QHBoxLayout(); p2.addWidget(QPushButton("📝 UI Naming", clicked=self._preset_naming)); p2.addWidget(QPushButton("⚧️ Symbols", clicked=self._preset_symbols)); r_lay.addLayout(p2)
        layout.addWidget(right, 3)

    def _open_file_standalone(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir ROM GBA", "", "GBA ROM (*.gba);;All Files (*)")
        if path:
            with open(path, "rb") as f:
                self.rom_data = bytearray(f.read())
                self.standalone_path = path
                self._refresh()

    def _save_to_rom_standalone(self):
        if not hasattr(self, 'standalone_path') or not self.standalone_path:
            QMessageBox.warning(self, "Error", "No hay un archivo abierto para guardar.")
            return
        try:
            with open(self.standalone_path, "wb") as f:
                f.write(self.rom_data)
            QMessageBox.information(self, "Éxito", f"Cambios guardados en {os.path.basename(self.standalone_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{e}")

    def _set_tool(self, tool): self.canvas.current_tool = tool
    def _set_color(self, idx):
        self.canvas.current_color = idx
        for i, b in enumerate(self.pal_btns):
            b.setStyleSheet(f"background: {self.canvas.palette[i].name()}; border: {'3px solid yellow' if i == idx else '1px solid #555'};")

    def _on_color_picked(self, idx):
        self._set_color(idx)
        self.btn_brush.setChecked(True); self._set_tool("brush")

    def _persist_project(self):
        if self.project:
            QMessageBox.information(self, "Proyecto", "Los cambios han sido integrados en la memoria virtual del proyecto.")
            self._refresh()

    def _load_palette_from_rom(self):
        if self.rom_data is None: return
        try:
            offset_str = self.palette_input.text()
            offset = int(offset_str, 16)
            pal_data = self.rom_data[offset : offset + 32]
            new_palette = []
            for i in range(0, 32, 2):
                color_val = struct.unpack("<H", pal_data[i:i+2])[0]
                r = (color_val & 0x1F) << 3
                g = ((color_val >> 5) & 0x1F) << 3
                b = ((color_val >> 10) & 0x1F) << 3
                new_palette.append(QColor(r, g, b))
            while len(new_palette) < 256: new_palette.append(QColor(0, 0, 0))
            self.canvas.palette = new_palette
            for i in range(16): self.pal_btns[i].setStyleSheet(f"background: {new_palette[i].name()}; border: 1px solid #555;")
            self.canvas.update(); self._refresh()
        except Exception as e: QMessageBox.warning(self, "Error de Paleta", f"No se pudo cargar la paleta:\n{e}")

    def _step_palette(self, step):
        try:
            curr = int(self.palette_input.text(), 16)
            self.palette_input.setText(f"0x{max(0, curr + step):X}")
            self._load_palette_from_rom()
        except: pass
            
    def _apply_to_rom_silent(self):
        if self.selected_idx == -1 or self.rom_data is None: return
        data = self.canvas.get_data()
        try: off_base = int(self.edit_off.text(), 16) + self.spin_fine.value()
        except: return
        use_stride, bpp, h = self.chk_stride.isChecked(), [1,2,4,8][self.combo_bpp.currentIndex()], self.spin_h.value()
        stride, t_size, c_size = self.spin_stride.value(), h * bpp, (h // 2) * bpp
        target_off = off_base + self.selected_idx * (t_size if not use_stride else c_size)
        if not use_stride:
            self.rom_data[target_off : target_off + t_size] = data
            if self.project: self.project.write_patch(target_off, data)
        else:
            self.rom_data[target_off : target_off + c_size] = data[:c_size]
            target_off_b = off_base + (self.selected_idx + stride) * c_size
            self.rom_data[target_off_b : target_off_b + c_size] = data[c_size:]
            if self.project:
                self.project.write_patch(target_off, data[:c_size])
                self.project.write_patch(target_off_b, data[c_size:])
        self._update_hex_view(data)
        item = self.grid_lay.itemAt(self.selected_idx).widget()
        if item: item.data = data; item.update()

    def _page(self, dir):
        try:
            off = int(self.edit_off.text(), 16); bpp = [1,2,4,8][self.combo_bpp.currentIndex()]; h = self.spin_h.value()
            step = (self.spin_w_grid.value() * 10) * (h * bpp if not self.chk_stride.isChecked() else (h//2) * bpp)
            self.edit_off.setText(f"0x{max(0, off + dir * step):x}"); self._refresh()
        except: pass

    def _refresh(self):
        if self.rom_data is None: return
        for i in reversed(range(self.grid_lay.count())):
            w = self.grid_lay.itemAt(i).widget()
            if w: w.deleteLater()
        try: off_base = int(self.edit_off.text(), 16) + self.spin_fine.value()
        except: return
        inter, use_stride, bpp, h = self.chk_inter_rows.isChecked(), self.chk_stride.isChecked(), [1,2,4,8][self.combo_bpp.currentIndex()], self.spin_h.value()
        stride, grid_w = self.spin_stride.value(), self.spin_w_grid.value()
        t_size, c_size = h * bpp, (h // 2) * bpp
        for i in range(grid_w * 10):
            if not use_stride:
                off = off_base + i * t_size
                if off + t_size > len(self.rom_data): break
                data = self.rom_data[off : off + t_size]
            else:
                off_t, off_b = off_base + i * c_size, off_base + (i + stride) * c_size
                if off_b + c_size > len(self.rom_data): break
                data = self.rom_data[off_t : off_t + c_size] + self.rom_data[off_b : off_b + c_size]
                off = off_t
            item = TileGridItem(i, data, off, inter, bpp, h, self.canvas.palette)
            item.clicked.connect(self._select_tile)
            if self.selected_idx == i: item.selected = True
            self.grid_lay.addWidget(item, i // grid_w, i % grid_w)

    def _update_hex_view(self, data):
        hex_text = ""
        for i in range(0, len(data), 8):
            chunk = data[i:i+8]
            hex_text += f"{i:02X}: " + " ".join(f"{b:02X}" for b in chunk) + "\n"
        self.edit_hex.setPlainText(hex_text)

    def _select_tile(self, idx):
        self.selected_idx = idx
        for i in range(self.grid_lay.count()):
            w = self.grid_lay.itemAt(i).widget()
            if w: w.selected = (i == idx); w.update()
        try: off_base = int(self.edit_off.text(), 16) + self.spin_fine.value()
        except: return
        inter, use_stride, bpp, h = self.chk_inter_rows.isChecked(), self.chk_stride.isChecked(), [1,2,4,8][self.combo_bpp.currentIndex()], self.spin_h.value()
        stride, t_size, c_size = self.spin_stride.value(), h * bpp, (h // 2) * bpp
        if not use_stride: data = self.rom_data[off_base + idx*t_size : off_base + idx*t_size + t_size]
        else: data = self.rom_data[off_base + idx*c_size : off_base + idx*c_size + c_size] + \
                    self.rom_data[off_base + (idx+stride)*c_size : off_base + (idx+stride)*c_size + c_size]
        self.canvas.set_data(data, inter, bpp, h)
        self._update_hex_view(data)

    def _apply_hex(self):
        if self.selected_idx == -1: return
        try:
            clean = "".join([l.split(":")[1] if ":" in l else l for l in self.edit_hex.toPlainText().split('\n')]).replace(" ","")
            data = bytearray.fromhex(clean)
            self.canvas.set_data(data, self.chk_inter_rows.isChecked(), [1,2,4,8][self.combo_bpp.currentIndex()], self.spin_h.value())
            self._apply_to_rom_silent()
        except Exception as e: QMessageBox.critical(self, "Error", f"Hex inválido: {e}")

    def _preset_main(self): self.edit_off.setText("75A440"); self.spin_h.setValue(8); self.combo_bpp.setCurrentIndex(2); self.chk_inter_rows.setChecked(False); self.chk_stride.setChecked(False); self._refresh()
    def _preset_kb(self): self.edit_off.setText("4F97EC"); self.spin_h.setValue(12); self.combo_bpp.setCurrentIndex(2); self.chk_inter_rows.setChecked(True); self.chk_stride.setChecked(True); self._refresh()
    def _preset_naming(self): self.edit_off.setText("4F8F70"); self.spin_h.setValue(8); self.combo_bpp.setCurrentIndex(0); self.chk_inter_rows.setChecked(False); self.chk_stride.setChecked(False); self._refresh()
    def _preset_symbols(self): self.edit_off.setText("117448"); self.spin_h.setValue(12); self.combo_bpp.setCurrentIndex(0); self.chk_inter_rows.setChecked(False); self.chk_stride.setChecked(False); self._refresh()

class StandaloneWindow(QMainWindow):
    def __init__(self, rom_path=None):
        super().__init__()
        self.setWindowTitle("Tile Editor Extreme Standalone")
        self.resize(1200, 800)
        
        self.editor = TileEditorWidget()
        self.setCentralWidget(self.editor)
        
        if rom_path:
            with open(rom_path, "rb") as f:
                self.editor.rom_data = bytearray(f.read())
                self.editor.standalone_path = rom_path
                self.editor._refresh()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    rom_path = sys.argv[1] if len(sys.argv) > 1 else None
    window = StandaloneWindow(rom_path)
    window.show()
    sys.exit(app.exec())