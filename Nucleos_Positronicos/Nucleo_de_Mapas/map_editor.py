# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.7.0)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
"""
MapEditorWidget — Editor de Mapas de FoMT Studio v1.8.0
═══════════════════════════════════════════════════════
Inspirado en Blue Spider; mantiene la lógica de eventos/items/NPCs de FoMT Studio.

Características:
  • Renderizado multicapa (BG0 / BG1 / BG2) con toggle individual
  • Malla de Colisiones binaria (0 = libre, 1 = bloqueado)
  • Indicadores de Warps  → icono 'W' amarillo clicable
  • Indicadores de Scripts → icono 'S' cian sobre carteles/muebles
  • CRUD de Warps (añadir, editar, eliminar) con re-inserción en ROM
  • Panel lateral con propiedades del elemento seleccionado
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QScrollArea, QToolButton, QLabel, QGroupBox,
    QFormLayout, QSpinBox, QLineEdit, QPushButton,
    QMessageBox, QDialog, QDialogButtonBox, QComboBox, QCheckBox
)
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QFont, QPixmap, QImage,
    QBrush
)
from PyQt6.QtCore import Qt, QSize, QRect, pyqtSignal, QPoint

from Nucleos_Positronicos.Nucleo_de_Mapas.mapas import (
    MapHeader, Warp, ScriptTrigger, MOVEMENT_LABELS
)


# ─────────────────────────────────────────────────────────────────────────────
#  Paleta de colores del editor
# ─────────────────────────────────────────────────────────────────────────────
COLOR_FREE    = QColor(255, 255, 255,  60)   # Tile libre (0)
COLOR_BLOCK   = QColor(255,  80,  80, 120)   # Tile bloqueado (1)
COLOR_WATER   = QColor( 80, 160, 255,  80)   # Agua (~)
COLOR_LEDGE   = QColor(255, 200,   0,  80)   # Borde (^)
COLOR_WARP_BG = QColor(255, 215,   0, 180)   # Fondo del 'W'
COLOR_WARP_FG = QColor(  0,   0,   0, 255)   # Letra 'W'
COLOR_SCRIPT_BG = QColor( 0, 200, 200, 180)  # Fondo del 'S'
COLOR_SCRIPT_FG = QColor(  0,   0,   0, 255) # Letra 'S'
COLOR_SELECTED  = QColor(255, 140,   0, 200)  # Resalte de selección


TILE_PX = 8    # Píxeles por tile (tamaño nativo GBA)
DEFAULT_ZOOM = 3   # Zoom inicial × 3 → 24 px / tile visible


# ─────────────────────────────────────────────────────────────────────────────
#  Canvas (el lienzo real con QPainter)
# ─────────────────────────────────────────────────────────────────────────────
class MapCanvas(QWidget):
    """Lienzo de dibujo del mapa. Emite señales al hacer click en elementos."""

    warpClicked   = pyqtSignal(object)    # Warp seleccionado
    scriptClicked = pyqtSignal(object)    # ScriptTrigger seleccionado
    tileClicked   = pyqtSignal(int, int)  # (tile_x, tile_y)

    def __init__(self, editor: "MapEditorWidget"):
        super().__init__()
        self.editor = editor
        self.setMouseTracking(True)

        self._zoom     = DEFAULT_ZOOM
        self._hover_tx = -1    # Tile bajo el cursor
        self._hover_ty = -1
        self._selected : object = None   # Warp o Script seleccionado

        # Pixmap cacheado de los tiles (reconstruido cuando cambia el mapa)
        self._tile_cache : QPixmap | None = None

    # ── Acceso al mapa actual ────────────────────────────────
    @property
    def _map(self) -> MapHeader | None:
        return self.editor.current_map

    # ── Zoom ─────────────────────────────────────────────────
    @property
    def zoom(self) -> int:
        return self._zoom

    @zoom.setter
    def zoom(self, z: int):
        self._zoom = max(1, min(z, 6))
        self._resize_to_map()
        self.update()

    def _resize_to_map(self):
        if not self._map:
            return
        w = self._map.width  * TILE_PX * self._zoom
        h = self._map.height * TILE_PX * self._zoom
        self.setFixedSize(w, h)

    # ── Actualizar tras cargar mapa nuevo ────────────────────
    def refresh(self):
        self._tile_cache = None
        self._selected   = None
        self._resize_to_map()
        self._build_tile_cache()
        self.update()

    def _build_tile_cache(self):
        """
        Renderiza el mapa usando el motor BlueSpider (MapHeader.render_map).
        Convierte la imagen Pillow RGBA a QPixmap para Qt.
        """
        if not self._map or not self._map._loaded:
            self._draw_placeholder()
            return

        try:
            pil_img = self._map.render_map()
            if pil_img is None:
                self._draw_placeholder()
                return

            # Convertir PIL RGBA → QImage → QPixmap
            pil_img = pil_img.convert('RGBA')
            raw = pil_img.tobytes('raw', 'RGBA')
            qimg = QImage(raw, pil_img.width, pil_img.height,
                          QImage.Format.Format_RGBA8888)
            self._tile_cache = QPixmap.fromImage(qimg)
        except Exception as e:
            print(f"[MapCanvas] render_map error: {e}")
            self._draw_placeholder()

    def _draw_placeholder(self):
        """Damero gris mientras no hay datos del mapa."""
        if not self._map:
            self._tile_cache = None
            return
        w = self._map.width  * 8
        h = self._map.height * 8
        img = QImage(w, h, QImage.Format.Format_RGB32)
        img.fill(QColor(40, 40, 40))
        c0, c1 = QColor(50,50,50).rgb(), QColor(65,65,65).rgb()
        for ty in range(self._map.height):
            for tx in range(self._map.width):
                c = c0 if (tx+ty)%2==0 else c1
                for py in range(8):
                    for px in range(8):
                        img.setPixel(tx*8+px, ty*8+py, c)
        self._tile_cache = QPixmap.fromImage(img)

    # ── Pintado principal ────────────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        z = self._zoom

        # 1. TILES (del caché, escalado)
        if self._tile_cache:
            scaled = self._tile_cache.scaled(
                self._tile_cache.width() * z,
                self._tile_cache.height() * z,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation
            )
            painter.drawPixmap(0, 0, scaled)
        else:
            painter.fillRect(self.rect(), QColor(30, 30, 30))

        if not self._map:
            return

        tpx = TILE_PX * z   # Tamaño visual de un tile en píxeles

        # 2. COLISIONES  (malla 0 / 1)
        if self.editor.show_collisions and self._map.collision:
            self._draw_collisions(painter, tpx)

        # 3. WARPS  (W)
        if self.editor.show_warps:
            self._draw_warps(painter, tpx)

        # 4. SCRIPTS  (S)
        if self.editor.show_scripts:
            self._draw_scripts(painter, tpx)

        # 5. HOVER
        if 0 <= self._hover_tx < self._map.width and 0 <= self._hover_ty < self._map.height:
            painter.setPen(QPen(QColor(255, 255, 255, 80), 1))
            painter.drawRect(self._hover_tx*tpx, self._hover_ty*tpx, tpx-1, tpx-1)

    def _draw_collisions(self, painter: QPainter, tpx: int):
        font = QFont("Consolas", max(6, tpx // 3))
        font.setBold(True)
        painter.setFont(font)
        m = self._map
        
        # 18 colors for collisions matching fomt_mapdata.py (Alpha ~100)
        col_colors = {
            0x00: QColor(0, 255, 0, 100),       # Verde: Caminable
            0x01: QColor(255, 0, 0, 100),       # Rojo: Bloqueado
            0x02: QColor(0, 0, 255, 100),       # Azul: Agua / Nadable
            0x03: QColor(255, 255, 0, 100),     # Amarillo: Acción / Interacción
            0x04: QColor(255, 165, 0, 100),     # Naranja: Puerta / Transición
            0x05: QColor(128, 0, 128, 100),     # Morado: Límite / Borde de mapa
            0x06: QColor(0, 255, 255, 100),     # Cian: Escaleras / Elevación
            0x07: QColor(255, 192, 203, 100),   # Rosa: Evento
            0x08: QColor(165, 42, 42, 100),     # Marrón: Suelo de tierra
            0x09: QColor(128, 128, 128, 100),   # Gris: Suelo de piedra
            0x0A: QColor(0, 128, 0, 100),       # Verde oscuro: Hierba alta
            0x0B: QColor(139, 69, 19, 100),     # Chocolate: Madera
            0x0C: QColor(255, 20, 147, 100),    # Rosa profundo: NPC / Personaje
            0x0D: QColor(64, 224, 208, 100),    # Turquesa: Objeto recogible
            0x0E: QColor(255, 215, 0, 100),     # Oro: Cofre / Tesoro
            0x0F: QColor(192, 192, 192, 100),   # Plata: Especial 1
            0x10: QColor(0, 0, 128, 100),       # Azul marino: Especial 2
            0x11: QColor(128, 0, 0, 100),       # Granate: Peligro / Daño
        }
        
        for idx, byte in enumerate(m.collision):
            tx = idx % m.width
            ty = idx // m.width
            rx = tx * tpx
            ry = ty * tpx
            label = MOVEMENT_LABELS.get(byte, "?")
            
            fill_color = col_colors.get(byte, QColor(255, 100, 100, 200))
            if byte == 0x00:
                painter.setPen(QColor(255, 255, 255, 100))
            else:
                painter.setPen(QColor(255, 100, 100, 200))
            
            painter.fillRect(rx, ry, tpx, tpx, fill_color)
            painter.drawText(
                QRect(rx, ry, tpx, tpx),
                Qt.AlignmentFlag.AlignCenter,
                label
            )

    def _draw_warps(self, painter: QPainter, tpx: int):
        font = QFont("Arial", max(7, tpx // 2))
        font.setBold(True)
        painter.setFont(font)
        for w in self._map.warps:
            rx, ry = w.x * tpx, w.y * tpx
            is_sel = (self._selected is w)
            bg = COLOR_SELECTED if is_sel else COLOR_WARP_BG
            painter.fillRect(rx+1, ry+1, tpx-2, tpx-2, bg)
            painter.setPen(QPen(COLOR_WARP_FG))
            painter.drawText(
                QRect(rx, ry, tpx, tpx),
                Qt.AlignmentFlag.AlignCenter, "W"
            )

    def _draw_scripts(self, painter: QPainter, tpx: int):
        font = QFont("Arial", max(7, tpx // 2))
        font.setBold(True)
        painter.setFont(font)
        for s in self._map.scripts:
            rx, ry = s.x * tpx, s.y * tpx
            is_sel = (self._selected is s)
            bg = COLOR_SELECTED if is_sel else COLOR_SCRIPT_BG
            painter.fillRect(rx+1, ry+1, tpx-2, tpx-2, bg)
            painter.setPen(QPen(COLOR_SCRIPT_FG))
            painter.drawText(
                QRect(rx, ry, tpx, tpx),
                Qt.AlignmentFlag.AlignCenter, "S"
            )

    # ── Manejo del ratón ─────────────────────────────────────
    def mouseMoveEvent(self, event):
        tpx = TILE_PX * self._zoom
        self._hover_tx = event.position().x().__int__() // tpx
        self._hover_ty = event.position().y().__int__() // tpx
        self.update()

    def mousePressEvent(self, event):
        if not self._map:
            return
        tpx = TILE_PX * self._zoom
        tx = int(event.position().x()) // tpx
        ty = int(event.position().y()) // tpx

        # ¿Clic sobre un Warp?
        for w in self._map.warps:
            if w.x == tx and w.y == ty:
                self._selected = w
                self.warpClicked.emit(w)
                self.update()
                return

        # ¿Clic sobre un Script?
        for s in self._map.scripts:
            if s.x == tx and s.y == ty:
                self._selected = s
                self.scriptClicked.emit(s)
                self.update()
                return

        # Clic libre en tile
        self._selected = None
        self.tileClicked.emit(tx, ty)
        self.update()

    def leaveEvent(self, event):
        self._hover_tx = self._hover_ty = -1
        self.update()


# ─────────────────────────────────────────────────────────────────────────────
#  Diálogo de Warp (Añadir / Editar)
# ─────────────────────────────────────────────────────────────────────────────
class WarpDialog(QDialog):
    def __init__(self, target=None, map_names: list[str] = [], parent=None):
        super().__init__(parent)
        is_script = isinstance(target, ScriptTrigger)
        self.setWindowTitle("Script Trigger" if is_script else ("Warp" if target else "Nuevo Warp"))
        self.resize(300, 220)

        # Usamos duck typing, ambos (Warp y ScriptTrigger) tienen x, y, script_id, metadata
        t = target or Warp(b'\x00' * 8, 0)

        form = QFormLayout(self)

        self.spin_x  = QSpinBox(); self.spin_x.setRange(0, 255);  self.spin_x.setValue(t.x)
        self.spin_y  = QSpinBox(); self.spin_y.setRange(0, 255);  self.spin_y.setValue(t.y)
        
        self.spin_script = QSpinBox()
        self.spin_script.setRange(0, 0xFFFF)
        self.spin_script.setDisplayIntegerBase(16)
        self.spin_script.setPrefix("0x")
        self.spin_script.setValue(t.script_id)
        
        self.edit_meta = QLineEdit()
        self.edit_meta.setText(t.metadata.hex().upper())
        self.edit_meta.setPlaceholderText("Ej. 00000000")

        form.addRow("X:", self.spin_x)
        form.addRow("Y:", self.spin_y)
        form.addRow("Script ID (Hex):", self.spin_script)
        form.addRow("Metadata (4 bytes Hex):", self.edit_meta)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def get_values(self):
        try:
            meta = bytes.fromhex(self.edit_meta.text().replace(" ", ""))
            if len(meta) != 4: meta = meta.ljust(4, b'\x00')[:4]
        except Exception:
            meta = b'\x00\x00\x00\x00'
        return (self.spin_x.value(), self.spin_y.value(), self.spin_script.value(), meta)

# ─────────────────────────────────────────────────────────────────────────────
#  Diálogo de Diccionario de Comportamientos (Behavior Dict)
# ─────────────────────────────────────────────────────────────────────────────
class BehaviorDictDialog(QDialog):
    def __init__(self, map_header, project, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gestor de Comportamientos (Triggers)")
        self.resize(400, 300)
        self.map_header = map_header
        self.project = project
        self.dict_data = bytearray()
        self._load_dict()
        
        # Build UI
        layout = QVBoxLayout(self)
        
        top_lay = QHBoxLayout()
        top_lay.addWidget(QLabel("Índice de Colisión (Hex):"))
        self.combo_index = QComboBox()
        for i in range(256):
            self.combo_index.addItem(f"0x{i:02X}")
        self.combo_index.currentIndexChanged.connect(self._on_index_changed)
        top_lay.addWidget(self.combo_index)
        layout.addLayout(top_lay)
        
        # Edit Form
        form = QFormLayout()
        self.chk_solid = QCheckBox("Sólido (No caminable)")
        self.spin_script = QSpinBox()
        self.spin_script.setRange(0, 0xFFFF)
        self.spin_script.setDisplayIntegerBase(16)
        self.spin_script.setPrefix("0x")
        
        self.chk_immediate = QCheckBox("Modo Inmediato (Script directo en ID)")
        
        form.addRow(self.chk_solid)
        form.addRow(self.chk_immediate)
        form.addRow("Script ID / Offset Array:", self.spin_script)
        layout.addLayout(form)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # Load the first index
        self._on_index_changed(0)
        
    def _load_dict(self):
        old_ptr = self.map_header.p_obj1 & 0x01FFFFFF
        limit = (self.map_header.p_obj2 & 0x01FFFFFF) - old_ptr
        if limit <= 0 or limit > 1024:
            limit = 1024 # Safenet
        if old_ptr > 0:
            raw = self.project.read_rom(old_ptr, limit)
            self.dict_data = bytearray(raw)
        else:
            self.dict_data = bytearray(1024)
            
    def _on_index_changed(self, idx):
        import struct
        if idx * 4 + 3 < len(self.dict_data):
            word = struct.unpack_from('<I', self.dict_data, idx * 4)[0]
        else:
            word = 0
            
        if word > 0x00010000:
            self.chk_immediate.setChecked(True)
            flags = word & 0xFFFF
            script = (word >> 16) & 0xFFFF
            self.chk_solid.setChecked(bool(flags & 1))
            self.spin_script.setValue(script)
        else:
            self.chk_immediate.setChecked(False)
            self.chk_solid.setChecked(False)
            self.spin_script.setValue(word & 0xFFFF)
            
    def _on_save(self):
        import struct
        idx = self.combo_index.currentIndex()
        
        # Ensure array is large enough
        if len(self.dict_data) < (idx + 1) * 4:
            self.dict_data.extend(b'\x00' * ((idx + 1) * 4 - len(self.dict_data)))
            
        flags = 1 if self.chk_solid.isChecked() else 0
        script = self.spin_script.value()
        
        if self.chk_immediate.isChecked():
            word = flags | (script << 16)
        else:
            word = script
            
        struct.pack_into('<I', self.dict_data, idx * 4, word)
        
        ok = self.map_header.save_behavior_dict_to_rom(self.project, bytes(self.dict_data))
        if ok:
            QMessageBox.information(self, "Éxito", "Diccionario de comportamientos guardado y/o repunteado.")
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "No se pudo guardar ni repuntear el diccionario.")


# ─────────────────────────────────────────────────────────────────────────────
#  Panel lateral de propiedades
# ─────────────────────────────────────────────────────────────────────────────
class PropertiesPanel(QWidget):
    warpChanged = pyqtSignal()   # Solicita que el canvas se actualice
    openScriptRequested = pyqtSignal(int) # Solicita abrir un script por ID

    def __init__(self, editor: "MapEditorWidget"):
        super().__init__()
        self.editor  = editor
        self._target : Warp | ScriptTrigger | None = None
        self.setMinimumWidth(150)
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # — Info del mapa —
        self.grp_map = QGroupBox("Mapa")
        form_map = QFormLayout(self.grp_map)
        self.lbl_id   = QLabel("—")
        self.lbl_size = QLabel("—")
        self.lbl_ts   = QLabel("—")
        form_map.addRow("ID:",         self.lbl_id)
        form_map.addRow("Tamaño:",     self.lbl_size)
        form_map.addRow("Tileset ID:", self.lbl_ts)
        layout.addWidget(self.grp_map)

        # — Elemento seleccionado —
        self.grp_elem = QGroupBox("Elemento seleccionado")
        self.form_elem = QFormLayout(self.grp_elem)
        self.lbl_type = QLabel("—")
        self.lbl_pos  = QLabel("—")
        self.lbl_dest = QLabel("—")
        self.btn_go_script = QPushButton("🔗 Ver Script")
        self.btn_go_script.setEnabled(False)
        self.btn_go_script.clicked.connect(self._on_go_script)
        
        self.form_elem.addRow("Tipo:",    self.lbl_type)
        self.form_elem.addRow("Pos:",     self.lbl_pos)
        self.form_elem.addRow("Destino:", self.lbl_dest)
        self.form_elem.addRow(self.btn_go_script)
        layout.addWidget(self.grp_elem)

        # — CRUD de Triggers —
        self.grp_triggers = QGroupBox("Gestión de Triggers")
        btn_lay = QHBoxLayout(self.grp_triggers)
        self.btn_add_warp   = QPushButton("+ Tr. Losa")
        self.btn_add_script = QPushButton("+ Tr. Interacción")
        self.btn_edit_warp  = QPushButton("✎ Editar")
        self.btn_del_warp   = QPushButton("✕ Borrar")
        self.btn_edit_warp.setEnabled(False)
        self.btn_del_warp.setEnabled(False)
        btn_lay.addWidget(self.btn_add_warp)
        btn_lay.addWidget(self.btn_add_script)
        btn_lay.addWidget(self.btn_edit_warp)
        btn_lay.addWidget(self.btn_del_warp)
        layout.addWidget(self.grp_triggers)

        # — Gestor de Diccionario —
        self.btn_open_dict = QPushButton("📖 Gestor de Comportamientos")
        self.btn_open_dict.setStyleSheet("background-color:#004080; color:white; font-weight:bold; padding:4px;")
        layout.addWidget(self.btn_open_dict)

        # — Guardar en ROM —
        self.btn_save_rom = QPushButton("💾 Guardar en ROM")
        self.btn_save_rom.setStyleSheet(
            "background-color:#1a6b1a; color:white; font-weight:bold; padding:4px;")
        layout.addWidget(self.btn_save_rom)

        layout.addStretch()

        # Señales
        self.btn_add_warp.clicked.connect(self._on_add_warp)
        self.btn_add_script.clicked.connect(self._on_add_script)
        self.btn_edit_warp.clicked.connect(self._on_edit_warp)
        self.btn_del_warp.clicked.connect(self._on_del_warp)
        self.btn_open_dict.clicked.connect(self._on_open_dict)
        self.btn_save_rom.clicked.connect(self._on_save_rom)

    def _on_open_dict(self):
        m = self.editor.current_map
        if not m: return
        dlg = BehaviorDictDialog(m, self.editor.project, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.warpChanged.emit()

    # ── Actualizar info del mapa ─────────────────────────────
    def update_map_info(self, m: MapHeader):
        self.lbl_id.setText(str(m.map_id))
        self.lbl_size.setText(f"{m.width} × {m.height} tiles")
        self.lbl_ts.setText(str(m.tileset_id))

    # ── Actualizar elemento seleccionado ─────────────────────
    def show_warp(self, w: Warp):
        self._target = w
        self.lbl_type.setText(f"Warp #{w.id}")
        self.lbl_pos.setText(f"({w.x}, {w.y})")
        self.lbl_dest.setText(f"Script: 0x{w.script_id:04X}")
        self.btn_edit_warp.setEnabled(True)
        self.btn_del_warp.setEnabled(True)
        self.btn_go_script.setEnabled(True)

    def show_script(self, s: ScriptTrigger):
        self._target = s
        self.lbl_type.setText(f"Script #{s.id}")
        self.lbl_pos.setText(f"({s.x}, {s.y})")
        self.lbl_dest.setText(f"Script ID: {s.script_id // 2} (Raw: 0x{s.script_id:04X})")
        self.btn_edit_warp.setEnabled(True)
        self.btn_del_warp.setEnabled(True)
        self.btn_go_script.setEnabled(True)

    def clear_selection(self):
        self._target = None
        self.lbl_type.setText("—")
        self.lbl_pos.setText("—")
        self.lbl_dest.setText("—")
        self.btn_edit_warp.setEnabled(False)
        self.btn_del_warp.setEnabled(False)
        self.btn_go_script.setEnabled(False)

    def _on_go_script(self):
        if self._target:
            self.openScriptRequested.emit(self._target.script_id)

    # ── Acciones CRUD ────────────────────────────────────────
    def _on_add_warp(self):
        m = self.editor.current_map
        if not m:
            return
        dlg = WarpDialog(parent=self)
        dlg.setWindowTitle("Nuevo Trigger de Losa")
        if dlg.exec() == QDialog.DialogCode.Accepted:
            import struct
            x, y, sid, meta = dlg.get_values()
            data = struct.pack('<BBH', x, y, sid) + meta
            w = Warp(data, len(m.warps), m.objects_offset)
            m.warps.append(w)
            self.show_warp(w)
            self.warpChanged.emit()

    def _on_add_script(self):
        m = self.editor.current_map
        if not m:
            return
        dlg = WarpDialog(parent=self)
        dlg.setWindowTitle("Nuevo Trigger de Interacción")
        if dlg.exec() == QDialog.DialogCode.Accepted:
            import struct
            x, y, sid, meta = dlg.get_values()
            data = struct.pack('<BBH', x, y, sid) + meta
            s = ScriptTrigger(data, len(m.scripts), m.objects_offset)
            m.scripts.append(s)
            self.show_script(s)
            self.warpChanged.emit()

    def _on_edit_warp(self):
        if not (isinstance(self._target, Warp) or isinstance(self._target, ScriptTrigger)):
            return
        dlg = WarpDialog(self._target, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            x, y, sid, meta = dlg.get_values()
            self._target.x = x
            self._target.y = y
            self._target.script_id = sid
            self._target.metadata = meta
            if isinstance(self._target, Warp):
                self.show_warp(self._target)
            else:
                self.show_script(self._target)
            self.warpChanged.emit()

    def _on_del_warp(self):
        if not self._target:
            return
        m = self.editor.current_map
        if not m:
            return
        tipo = "Warp" if isinstance(self._target, Warp) else "Script"
        reply = QMessageBox.question(
            self, f"Eliminar {tipo}",
            f"¿Eliminar {tipo} #{self._target.id} en ({self._target.x},{self._target.y})?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if isinstance(self._target, Warp):
                m.warps.remove(self._target)
                for i, w in enumerate(m.warps): w.id = i
            else:
                m.scripts.remove(self._target)
                for i, s in enumerate(m.scripts): s.id = i
            self.clear_selection()
            self.warpChanged.emit()

    def _on_save_rom(self):
        m = self.editor.current_map
        if not m:
            return
        ok1 = m.save_warps_to_rom(self.editor.project)
        ok2 = m.save_layout_to_rom(self.editor.project)
        if ok1 and ok2:
            QMessageBox.information(self, "Guardado", "Objetos y Layout guardados en la ROM.")
        elif ok1 or ok2:
            QMessageBox.warning(self, "Guardado Parcial", "Se guardaron algunos datos pero otros fallaron.")
        else:
            QMessageBox.warning(self, "Error", "No se pudo guardar nada en la ROM.")


# ─────────────────────────────────────────────────────────────────────────────
#  Widget principal del Editor de Mapas
# ─────────────────────────────────────────────────────────────────────────────
class MapEditorWidget(QWidget):
    """
    Panel principal del editor de mapas.
    Se instancia UNA VEZ en app.py y recibe mapas mediante load_map().
    """
    openScriptRequested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        # project se obtiene de la ventana principal
        self.project     = None
        self.current_map : MapHeader | None = None

        # Flags de visibilidad
        self.show_collisions = True
        self.show_warps      = True
        self.show_scripts    = True
        self.show_bg         = [True, True, True]

        self._build_ui()

    # ── Lazy-load del proyecto ───────────────────────────────
    def _get_project(self):
        if self.project:
            return self.project
        # Subir por jerarquía hasta encontrar la ventana principal
        w = self.parent()
        while w:
            if hasattr(w, 'project') and w.project:
                self.project = w.project
                return self.project
            w = w.parent()
        return None

    # ── Construcción de la UI ────────────────────────────────
    def _build_ui(self):
        root = QHBoxLayout(self)

        # ─ Zona izquierda: Toolbar + Canvas ─
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)

        # Canvas se crea PRIMERO para que _build_toolbar pueda conectar sus señales
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.scroll.setStyleSheet("background:#1a1a1a;")
        from PyQt6.QtWidgets import QSizePolicy
        self.scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.canvas = MapCanvas(self)
        self.canvas.setFixedSize(600, 400)
        self.scroll.setWidget(self.canvas)

        # Toolbar (ya puede referenciar self.canvas)
        tb = QHBoxLayout()
        self._build_toolbar(tb)
        left_lay.addLayout(tb)
        left_lay.addWidget(self.scroll)

        # ─ Panel derecho: Propiedades ─
        self.props = PropertiesPanel(self)

        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(self.props)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)

        # Señales canvas → propiedades
        self.canvas.warpClicked.connect(self.props.show_warp)
        self.canvas.scriptClicked.connect(self.props.show_script)
        self.canvas.tileClicked.connect(lambda tx, ty: self.props.clear_selection())
        self.props.warpChanged.connect(self.canvas.update)
        self.props.openScriptRequested.connect(self.openScriptRequested.emit)

    def _build_toolbar(self, tb: QHBoxLayout):
        """Crea los botones de toggle para capas y overlays."""

        def toggle_btn(label, initial, slot):
            btn = QToolButton()
            btn.setText(label)
            btn.setCheckable(True)
            btn.setChecked(initial)
            btn.setFixedHeight(24)
            btn.clicked.connect(slot)
            tb.addWidget(btn)
            return btn

        # BG layers
        for i in range(3):
            toggle_btn(f"BG{i}", True,
                       lambda chk, idx=i: self._toggle_bg(idx, chk))

        tb.addSpacing(12)

        # Overlay layers
        self.btn_col = toggle_btn("Col 0/1", True, self._toggle_col)
        self.btn_w   = toggle_btn("Losa (W)", True, self._toggle_warps)
        self.btn_s   = toggle_btn("Int. (S)", True, self._toggle_scripts)

        tb.addSpacing(12)

        # Zoom
        tb.addWidget(QLabel("Zoom:"))
        self.btn_zoom_in  = QPushButton("+"); self.btn_zoom_in.setFixedWidth(28)
        self.btn_zoom_out = QPushButton("−"); self.btn_zoom_out.setFixedWidth(28)
        self.btn_zoom_in.clicked.connect(lambda: setattr(self.canvas, 'zoom', self.canvas.zoom + 1))
        self.btn_zoom_out.clicked.connect(lambda: setattr(self.canvas, 'zoom', self.canvas.zoom - 1))
        tb.addWidget(self.btn_zoom_in)
        tb.addWidget(self.btn_zoom_out)

        tb.addStretch()

        # Coordenadas hover
        self.lbl_coords = QLabel("Tile: —")
        tb.addWidget(self.lbl_coords)
        self.canvas.tileClicked.connect(
            lambda tx, ty: self.lbl_coords.setText(f"Tile: ({tx},{ty})")
        )

    def _toggle_bg(self, idx, state):
        self.show_bg[idx] = state
        self.canvas.update()

    def _toggle_col(self, state):
        self.show_collisions = state
        self.canvas.update()

    def _toggle_warps(self, state):
        self.show_warps = state
        self.canvas.update()

    def _toggle_scripts(self, state):
        self.show_scripts = state
        self.canvas.update()

    # ── API pública: cargar mapa ─────────────────────────────
    def load_map(self, map_header):
        proj = self._get_project()
        self.current_map = map_header

        if proj and proj.base_rom_data:
            # Motor BlueSpider: carga paletas, tiles, bloques, tilemap, warps, scripts
            ok = map_header.load_data(proj.base_rom_data)
            if not ok:
                print(f"[MapEditor] No se pudieron cargar los datos del mapa {map_header.map_id}")
        else:
            print("[MapEditor] No hay ROM cargada")

        # Actualizar panel de propiedades
        self.props.update_map_info(map_header)
        # Renderizar (muestra damero si load_data falló)
        self.canvas.refresh()
