# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v4.0.0)
# "The Greatest Show - Final Release"
# Desarrollado por: Denisovich728
# ============================================================
"""
visor_sprites.py - Explorador Canonico de Sprites y Animaciones FoMT GBA
Bases maestras verificadas en ROM limpia mediante Symphony Metasprite Engine:
- SPRITE_TILES_BASE = 0x5A33FC
- SPRITE_PAL_BASE   = 0x661DC0
- FRAME_ARRAY_BASE  = 0x58E20C
- OAM_ARRAY_BASE    = 0x599E20
- ANIM_TABLE_BASE   = 0x58BA2C
- SCRIPT_BASE       = 0x663208
"""

import os
import csv
import struct
import io
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget,
    QListWidgetItem, QLabel, QPushButton, QScrollArea, QFileDialog,
    QSpinBox, QFrame, QLineEdit, QSlider, QProgressBar, QMessageBox,
    QTabWidget, QCheckBox, QComboBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor, QPen

from Banco_de_Datos.Utilidades.rutas import get_data_path
from Consola_de_Comando.i18n import tr, get_lang_from_widget
from Consola_de_Comando.i18n import t as _t


# ============================================================
#  CONSTANTES CANONICAS DE HARDWARE Y MEMORIA GBA
# ============================================================

SPRITE_TILES_BASE = 0x5A33FC
SPRITE_PAL_BASE   = 0x661DC0
FRAME_ARRAY_BASE  = 0x58E20C
OAM_ARRAY_BASE    = 0x599E20
ANIM_TABLE_BASE   = 0x58BA2C
SCRIPT_BASE       = 0x663208

OAM_DIMS = {
    (0, 0): (8, 8),   (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64),
    (1, 0): (16, 8),  (1, 1): (32, 8),  (1, 2): (32, 16), (1, 3): (64, 32),
    (2, 0): (8, 16),  (2, 1): (8, 32),  (2, 2): (16, 32), (2, 3): (32, 64)
}


def bgr555_to_rgb(c: int) -> Tuple[int, int, int]:
    r = (c & 0x1F) << 3
    g = ((c >> 5) & 0x1F) << 3
    b = ((c >> 10) & 0x1F) << 3
    return (r, g, b)


def pil_to_qpixmap(pil_img: Optional[Image.Image], scale: int = 1) -> QPixmap:
    if pil_img is None:
        return QPixmap()
    if scale > 1:
        pil_img = pil_img.resize(
            (pil_img.width * scale, pil_img.height * scale),
            Image.Resampling.NEAREST
        )
    if pil_img.mode != "RGBA":
        pil_img = pil_img.convert("RGBA")
    data = pil_img.tobytes("raw", "RGBA")
    qimg = QImage(data, pil_img.width, pil_img.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg)


# ============================================================
#  MOTOR CANONICO DE METASPRITES FoMT (Symphony Engine)
# ============================================================

class SymphonySpriteEngine:
    def __init__(self, rom_data: bytes):
        self.rom = rom_data
        self._tile_cache: Dict[int, List[int]] = {}
        self._palette_cache: Dict[int, List[Tuple[int, int, int, int]]] = {}

    def decode_palette(self, pal_idx: int) -> List[Tuple[int, int, int, int]]:
        if pal_idx in self._palette_cache:
            return self._palette_cache[pal_idx]

        pal: List[Tuple[int, int, int, int]] = []
        off = SPRITE_PAL_BASE + pal_idx * 32
        for i in range(16):
            if off + i * 2 + 2 <= len(self.rom):
                c = struct.unpack_from('<H', self.rom, off + i * 2)[0]
                r, g, b = bgr555_to_rgb(c)
                alpha = 255 if i > 0 else 0
                pal.append((r, g, b, alpha))
            else:
                pal.append((0, 0, 0, 0))

        self._palette_cache[pal_idx] = pal
        return pal

    def decode_tile(self, tile_idx: int) -> List[int]:
        if tile_idx in self._tile_cache:
            return self._tile_cache[tile_idx]

        off = SPRITE_TILES_BASE + tile_idx * 32
        px: List[int] = []
        for y in range(8):
            for x in range(4):
                if off + y * 4 + x < len(self.rom):
                    b = self.rom[off + y * 4 + x]
                    px.append(b & 0x0F)
                    px.append(b >> 4)
                else:
                    px.extend([0, 0])

        self._tile_cache[tile_idx] = px
        return px

    def render_frame_with_meta(self, frame_idx: int) -> Tuple[Optional[Image.Image], int, int]:
        frame_off = FRAME_ARRAY_BASE + frame_idx * 16
        if frame_off + 16 > len(self.rom):
            return None, 0, 0

        fields = struct.unpack_from('<HHHHHHHH', self.rom, frame_off)
        oam_count = fields[0]
        oam_offset = fields[1]
        gfx_off_tiles = fields[3]
        pal_idx = fields[5]

        if oam_count == 0 or oam_count > 64:
            return None, pal_idx, 0

        pal = self.decode_palette(pal_idx)
        canvas = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        origin_x, origin_y = 32, 48

        for p_i in range(oam_count):
            part_off = OAM_ARRAY_BASE + (oam_offset + p_i) * 8
            if part_off + 8 > len(self.rom):
                continue

            attr0, attr1, attr2, _ = struct.unpack_from('<hhhh', self.rom, part_off)
            y = attr0 & 0xFF
            if y > 127:
                y -= 256
            shape = (attr0 >> 14) & 3

            x = attr1 & 0x1FF
            if x > 255:
                x -= 512
            size = (attr1 >> 14) & 3
            h_flip = (attr1 >> 12) & 1
            v_flip = (attr1 >> 13) & 1
            tile_rel = attr2 & 0x3FF

            final_tile = gfx_off_tiles + tile_rel
            w, h = OAM_DIMS.get((shape, size), (8, 8))
            w_tiles = w // 8
            h_tiles = h // 8

            sub = Image.new('RGBA', (w, h), (0, 0, 0, 0))
            sub_pix = sub.load()

            t = 0
            for ty in range(h_tiles):
                for tx in range(w_tiles):
                    pixels = self.decode_tile(final_tile + t)
                    for py in range(8):
                        for px in range(8):
                            c_idx = pixels[py * 8 + px]
                            if c_idx > 0:
                                sub_pix[tx * 8 + px, ty * 8 + py] = pal[c_idx]
                    t += 1

            if h_flip:
                sub = sub.transpose(Image.FLIP_LEFT_RIGHT)
            if v_flip:
                sub = sub.transpose(Image.FLIP_TOP_BOTTOM)

            canvas.paste(sub, (origin_x + x, origin_y + y), sub)

        return canvas, pal_idx, oam_count

    def render_animation_data(self, anim_id: int) -> Optional[Dict[str, Any]]:
        anim_off = ANIM_TABLE_BASE + anim_id * 4
        if anim_off + 4 > len(self.rom):
            return None

        val = struct.unpack_from('<I', self.rom, anim_off)[0]
        frame_count = val & 0xFFFF
        script_offset = val >> 16
        script_off = SCRIPT_BASE + script_offset * 4

        if script_off >= len(self.rom) or frame_count == 0 or frame_count > 128:
            return None

        frames: List[Image.Image] = []
        durations: List[int] = []
        frame_indices: List[int] = []
        unique_frames: List[Image.Image] = []
        seen_hashes = set()
        last_pal_idx = 0
        total_oam_parts = 0

        for i in range(frame_count):
            if script_off + i * 4 + 4 > len(self.rom):
                break
            f_idx, wait_f = struct.unpack_from('<HH', self.rom, script_off + i * 4)
            canvas, p_idx, oam_parts = self.render_frame_with_meta(f_idx)
            if canvas:
                frames.append(canvas)
                dur = max(20, int(wait_f * 16.666))
                durations.append(dur)
                frame_indices.append(f_idx)
                last_pal_idx = p_idx
                total_oam_parts += oam_parts

                h_bytes = canvas.tobytes()
                if h_bytes not in seen_hashes:
                    seen_hashes.add(h_bytes)
                    unique_frames.append(canvas)

        if not frames:
            return None

        # Composicion de Spritesheet (mosaico regular de 64x64)
        cols = min(8, max(1, len(unique_frames)))
        rows = (len(unique_frames) + cols - 1) // cols
        sheet = Image.new('RGBA', (cols * 64, rows * 64), (0, 0, 0, 0))
        for idx, u_img in enumerate(unique_frames):
            cx = (idx % cols) * 64
            cy = (idx // cols) * 64
            sheet.paste(u_img, (cx, cy))

        # Composicion de Tira Horizontal
        strip = Image.new('RGBA', (len(unique_frames) * 64, 64), (0, 0, 0, 0))
        for idx, u_img in enumerate(unique_frames):
            strip.paste(u_img, (idx * 64, 0))

        raw_pal = self.decode_palette(last_pal_idx)
        palette_rgb = [(c[0], c[1], c[2]) for c in raw_pal]

        return {
            "anim_id": anim_id,
            "frame_count": frame_count,
            "script_rom_addr": 0x08000000 + script_off,
            "frames": frames,
            "durations": durations,
            "frame_indices": frame_indices,
            "unique_frames": unique_frames,
            "sheet": sheet,
            "strip": strip,
            "pal_idx": last_pal_idx,
            "palette_rgb": palette_rgb,
            "avg_oam_parts": total_oam_parts // len(frames) if frames else 0
        }


# ============================================================
#  WIDGETS VISUALES AUXILIARES
# ============================================================

class PaletteStrip(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.colors = [(0, 0, 0)] * 16
        self.setFixedSize(256, 20)

    def set_palette(self, colors):
        self.colors = colors[:16] if colors else [(0, 0, 0)] * 16
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        cw = self.width() // 16
        for i, (r, g, b) in enumerate(self.colors):
            p.fillRect(i * cw, 0, cw, self.height(), QColor(r, g, b))
            p.setPen(QColor(40, 40, 50))
            p.drawRect(i * cw, 0, cw - 1, self.height() - 1)
        p.end()


class CheckerboardLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background: #0E0E14; border: 1px solid #222230; border-radius: 4px;")
        self._pixmap = None
        self._checker_pattern = self._create_checker_pixmap()

    def _create_checker_pixmap(self) -> QPixmap:
        pm = QPixmap(16, 16)
        p = QPainter(pm)
        c1 = QColor(18, 18, 24)
        c2 = QColor(26, 26, 36)
        p.fillRect(0, 0, 8, 8, c1)
        p.fillRect(8, 8, 8, 8, c1)
        p.fillRect(8, 0, 8, 8, c2)
        p.fillRect(0, 8, 8, 8, c2)
        p.end()
        return pm

    def set_image(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawTiledPixmap(self.rect(), self._checker_pattern)
        if self._pixmap and not self._pixmap.isNull():
            x = (self.width() - self._pixmap.width()) // 2
            y = (self.height() - self._pixmap.height()) // 2
            p.drawPixmap(x, y, self._pixmap)
        elif self.text():
            p.setPen(QColor(120, 120, 140))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        p.end()


# ============================================================
#  PANEL DE INFORMACION TECNICA
# ============================================================

class SpriteInfoPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(280)
        self.setStyleSheet("""
            SpriteInfoPanel {
                background: #0A0A10;
                border: 1px solid #1F1F2C;
                border-radius: 6px;
            }
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        title = QLabel(_t("spr_telemetry"))
        title.setStyleSheet("color: #00FF96; font-size: 12px; font-weight: bold; letter-spacing: 2px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #1F1F2C;")
        layout.addWidget(sep)

        self.lbl_name = self._field(_t("spr_f_anim") + ":")
        self.lbl_id = self._field("ID:")
        self.lbl_category = self._field(_t("spr_f_category") + ":")
        self.lbl_rom_addr = self._field("Script ROM:")
        self.lbl_frames = self._field("Frames:")
        self.lbl_unique = self._field(_t("spr_f_unique") + ":")
        self.lbl_oam = self._field(_t("spr_f_oam") + ":")
        self.lbl_pal_idx = self._field(_t("spr_f_pal") + ":")

        for lbl in [
            self.lbl_name, self.lbl_id, self.lbl_category, self.lbl_rom_addr,
            self.lbl_frames, self.lbl_unique, self.lbl_oam, self.lbl_pal_idx
        ]:
            layout.addWidget(lbl)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #1F1F2C;")
        layout.addWidget(sep2)

        lbl_pal = QLabel(_t("spr_active_pal"))
        lbl_pal.setStyleSheet("color: #FFD700; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(lbl_pal)

        self.pal_preview = PaletteStrip()
        layout.addWidget(self.pal_preview)

        layout.addStretch()

    def _field(self, text: str) -> QLabel:
        lbl = QLabel(f"{text} --")
        lbl.setStyleSheet("color: #CCCCCC; font-size: 11px; font-family: 'Consolas';")
        return lbl

    def update_info(self, name: str, anim_id: int, category: str, anim_data: Dict[str, Any]):
        self.lbl_name.setText(f"{_t('spr_f_anim')}: {name}")
        self.lbl_id.setText(f"ID: 0x{anim_id:04X} ({anim_id})")

        cat_colors = {
            "Player": "#00FF96",
            "Herramientas": "#00BFFF",
            "Animales": "#FFD700",
            "NPCs": "#FF77AA",
            "Varios": "#CCCCCC"
        }
        color = cat_colors.get(category, "#CCCCCC")
        self.lbl_category.setText(f"{_t('spr_f_category')}: {category}")
        self.lbl_category.setStyleSheet(f"color: {color}; font-size: 11px; font-family: 'Consolas'; font-weight: bold;")

        self.lbl_rom_addr.setText(f"Script ROM: 0x{anim_data['script_rom_addr']:08X}")
        self.lbl_frames.setText(f"Frames: {len(anim_data['frames'])}")
        self.lbl_unique.setText(f"{_t('spr_f_unique')}: {len(anim_data['unique_frames'])}")
        self.lbl_oam.setText(f"{_t('spr_f_oam')}: " + _t("spr_avg", n=anim_data['avg_oam_parts']))
        self.lbl_pal_idx.setText(f"{_t('spr_f_pal')}: #{anim_data['pal_idx']}")

        self.pal_preview.set_palette(anim_data.get("palette_rgb", []))

    def clear_info(self):
        for lbl in [
            self.lbl_name, self.lbl_id, self.lbl_category, self.lbl_rom_addr,
            self.lbl_frames, self.lbl_unique, self.lbl_oam, self.lbl_pal_idx
        ]:
            prefix = lbl.text().split(":")[0]
            lbl.setText(f"{prefix}: --")
        self.pal_preview.set_palette(None)


# ============================================================
#  REPRODUCTOR DE ANIMACION CANONICO EN VIVO
# ============================================================

class LiveAnimationPlayer(QWidget):
    frame_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.anim_data: Optional[Dict[str, Any]] = None
        self.current_frame = 0
        self.is_playing = True
        self.speed_multiplier = 1.0
        self.zoom = 4

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._on_timer_tick)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Visor central
        self.display = CheckerboardLabel()
        self.display.setMinimumSize(256, 256)
        layout.addWidget(self.display, 1)

        # Timeline y Controles
        ctrl_box = QFrame()
        ctrl_box.setStyleSheet("background: #0E0E14; border: 1px solid #1F1F2C; border-radius: 4px; padding: 4px;")
        ctrl_layout = QVBoxLayout(ctrl_box)
        ctrl_layout.setContentsMargins(6, 4, 6, 4)
        ctrl_layout.setSpacing(4)

        # Slider de Timeline
        t_row = QHBoxLayout()
        self.lbl_frame_counter = QLabel("Frame: 0 / 0")
        self.lbl_frame_counter.setStyleSheet("color: #00FF96; font-family: 'Consolas'; font-size: 11px;")
        t_row.addWidget(self.lbl_frame_counter)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal { height: 4px; background: #222230; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #00FF96; border-radius: 2px; }
            QSlider::handle:horizontal { background: #FFFFFF; width: 12px; margin-top: -4px; margin-bottom: -4px; border-radius: 6px; }
        """)
        self.slider.sliderMoved.connect(self._on_slider_moved)
        t_row.addWidget(self.slider)

        self.lbl_duration = QLabel("0 ms")
        self.lbl_duration.setStyleSheet("color: #888899; font-family: 'Consolas'; font-size: 10px;")
        t_row.addWidget(self.lbl_duration)
        ctrl_layout.addLayout(t_row)

        # Botones de transporte
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self.btn_step_prev = QPushButton("|<")
        self.btn_step_prev.setFixedSize(32, 26)
        self.btn_step_prev.clicked.connect(self._step_prev)
        btn_row.addWidget(self.btn_step_prev)

        self.btn_play_pause = QPushButton(_t("spr_pause"))
        self.btn_play_pause.setFixedSize(70, 26)
        self.btn_play_pause.setProperty("variant", "primary")
        self.btn_play_pause.clicked.connect(self._toggle_play)
        btn_row.addWidget(self.btn_play_pause)

        self.btn_step_next = QPushButton(">|")
        self.btn_step_next.setFixedSize(32, 26)
        self.btn_step_next.clicked.connect(self._step_next)
        btn_row.addWidget(self.btn_step_next)

        btn_row.addSpacing(10)

        # Selector de Velocidad
        btn_row.addWidget(QLabel(_t("spr_speed"), styleSheet="color: #888899; font-size: 10px;"))
        self.combo_speed = QComboBox()
        self.combo_speed.addItems(["0.25x", "0.5x", "1.0x", "2.0x"])
        self.combo_speed.setCurrentText("1.0x")
        self.combo_speed.setStyleSheet("background: #181822; color: white; padding: 2px 6px; font-size: 10px;")
        self.combo_speed.currentTextChanged.connect(self._on_speed_changed)
        btn_row.addWidget(self.combo_speed)

        btn_row.addSpacing(10)

        # Zoom
        btn_row.addWidget(QLabel("Zoom:", styleSheet="color: #888899; font-size: 10px;"))
        self.spn_zoom = QSpinBox()
        self.spn_zoom.setRange(1, 8)
        self.spn_zoom.setValue(4)
        self.spn_zoom.setStyleSheet("background: #181822; color: white; padding: 2px 6px; font-size: 10px;")
        self.spn_zoom.valueChanged.connect(self._on_zoom_changed)
        btn_row.addWidget(self.spn_zoom)

        btn_row.addStretch()
        ctrl_layout.addLayout(btn_row)

        layout.addWidget(ctrl_box)

    def load_animation(self, anim_data: Optional[Dict[str, Any]]):
        self.timer.stop()
        self.anim_data = anim_data
        self.current_frame = 0

        if not anim_data or not anim_data.get("frames"):
            self.display.set_image(QPixmap())
            self.display.setText(_t("spr_no_anim_data"))
            self.lbl_frame_counter.setText("Frame: 0 / 0")
            self.lbl_duration.setText("0 ms")
            self.slider.setRange(0, 0)
            return

        total_frames = len(anim_data["frames"])
        self.slider.setRange(0, total_frames - 1)
        self.slider.setValue(0)
        self._update_current_frame()

        if self.is_playing:
            self._schedule_next_frame()

    def _update_current_frame(self):
        if not self.anim_data or not self.anim_data["frames"]:
            return

        idx = self.current_frame
        frames = self.anim_data["frames"]
        if idx >= len(frames):
            idx = 0
            self.current_frame = 0

        pil_img = frames[idx]
        pix = pil_to_qpixmap(pil_img, self.zoom)
        self.display.set_image(pix)

        total = len(frames)
        dur = self.anim_data["durations"][idx]
        self.lbl_frame_counter.setText(f"Frame: {idx + 1} / {total}")
        self.lbl_duration.setText(f"{dur} ms (Orig: 0x{self.anim_data['frame_indices'][idx]:04X})")

        self.slider.blockSignals(True)
        self.slider.setValue(idx)
        self.slider.blockSignals(False)

        self.frame_changed.emit(idx)

    def _schedule_next_frame(self):
        if not self.anim_data or not self.anim_data["frames"] or not self.is_playing:
            return

        dur = self.anim_data["durations"][self.current_frame]
        delay_ms = max(10, int(dur / self.speed_multiplier))
        self.timer.start(delay_ms)

    def _on_timer_tick(self):
        if not self.anim_data or not self.anim_data["frames"]:
            return

        total = len(self.anim_data["frames"])
        self.current_frame = (self.current_frame + 1) % total
        self._update_current_frame()

        if self.is_playing:
            self._schedule_next_frame()

    def _toggle_play(self):
        self.is_playing = not self.is_playing
        if self.is_playing:
            self.btn_play_pause.setText(_t("spr_pause"))
            self.btn_play_pause.setProperty("variant", "primary")
            self._schedule_next_frame()
        else:
            self.timer.stop()
            self.btn_play_pause.setText(_t("spr_play"))
            self.btn_play_pause.setProperty("variant", "primary")

    def _step_next(self):
        if not self.anim_data or not self.anim_data["frames"]:
            return
        self.timer.stop()
        self.is_playing = False
        self.btn_play_pause.setText(_t("spr_play"))
        self.btn_play_pause.setProperty("variant", "primary")

        total = len(self.anim_data["frames"])
        self.current_frame = (self.current_frame + 1) % total
        self._update_current_frame()

    def _step_prev(self):
        if not self.anim_data or not self.anim_data["frames"]:
            return
        self.timer.stop()
        self.is_playing = False
        self.btn_play_pause.setText(_t("spr_play"))
        self.btn_play_pause.setProperty("variant", "primary")

        total = len(self.anim_data["frames"])
        self.current_frame = (self.current_frame - 1 + total) % total
        self._update_current_frame()

    def _on_slider_moved(self, val: int):
        self.timer.stop()
        self.current_frame = val
        self._update_current_frame()

    def _on_speed_changed(self, text: str):
        val = text.replace("x", "")
        try:
            self.speed_multiplier = float(val)
        except ValueError:
            self.speed_multiplier = 1.0

    def _on_zoom_changed(self, val: int):
        self.zoom = val
        self._update_current_frame()


# ============================================================
#  VISOR DE SPRITE SHEET COMPLETO
# ============================================================

class SheetViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sheet_img: Optional[Image.Image] = None
        self.zoom = 2
        self.mode = "mosaic"  # 'mosaic' o 'strip'
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: #0E0E14; border: 1px solid #1F1F2C; border-radius: 4px;")

        self.display = CheckerboardLabel()
        scroll.setWidget(self.display)
        layout.addWidget(scroll, 1)

        # Controles de Sheet
        bar = QHBoxLayout()
        bar.setSpacing(8)

        bar.addWidget(QLabel(_t("spr_sheet_mode"), styleSheet="color: #888899; font-size: 10px;"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItems([_t("spr_mode_grid"), _t("spr_mode_strip")])
        self.combo_mode.setStyleSheet("background: #181822; color: white; padding: 2px 6px; font-size: 10px;")
        self.combo_mode.currentIndexChanged.connect(self._on_mode_changed)
        bar.addWidget(self.combo_mode)

        bar.addSpacing(10)

        bar.addWidget(QLabel(_t("spr_sheet_zoom"), styleSheet="color: #888899; font-size: 10px;"))
        self.spn_zoom = QSpinBox()
        self.spn_zoom.setRange(1, 8)
        self.spn_zoom.setValue(2)
        self.spn_zoom.setStyleSheet("background: #181822; color: white; padding: 2px 6px; font-size: 10px;")
        self.spn_zoom.valueChanged.connect(self._on_zoom_changed)
        bar.addWidget(self.spn_zoom)

        self.lbl_dims = QLabel("-- x -- px")
        self.lbl_dims.setStyleSheet("color: #00FF96; font-family: 'Consolas'; font-size: 10px;")
        bar.addWidget(self.lbl_dims)

        bar.addStretch()
        layout.addLayout(bar)

    def load_sheet_data(self, anim_data: Optional[Dict[str, Any]]):
        if not anim_data:
            self.sheet_img = None
            self.display.set_image(QPixmap())
            self.display.setText(_t("spr_no_sheet"))
            self.lbl_dims.setText("-- x -- px")
            return

        if self.mode == "strip":
            self.sheet_img = anim_data.get("strip")
        else:
            self.sheet_img = anim_data.get("sheet")

        self._refresh()

    def _refresh(self):
        if self.sheet_img is None:
            self.display.set_image(QPixmap())
            return

        pix = pil_to_qpixmap(self.sheet_img, self.zoom)
        self.display.set_image(pix)
        bytes_len = pix.toImage().sizeInBytes() if pix and not pix.isNull() else 0
        self.lbl_dims.setText(f"{self.sheet_img.width}x{self.sheet_img.height} px ({bytes_len} bytes)")

    def _on_mode_changed(self, idx: int):
        self.mode = "strip" if idx == 1 else "mosaic"
        # Notificar recarga al padre si fuera necesario

    def _on_zoom_changed(self, val: int):
        self.zoom = val
        self._refresh()


# ============================================================
#  VISOR DE SPRITES PRINCIPAL
# ============================================================

class VisorSprites(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.project = None
        self.engine: Optional[SymphonySpriteEngine] = None
        self._animations: List[Dict[str, Any]] = []
        self._filtered_indices: List[int] = []
        self._current_anim_data: Optional[Dict[str, Any]] = None
        self.current_filter = "ALL"

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Header principal
        header_layout = QHBoxLayout()
        header = QLabel(_t("spr_title"))
        header.setStyleSheet("font-size: 15px; font-weight: bold; color: #00FF96; letter-spacing: 1px;")
        header_layout.addWidget(header)
        header_layout.addStretch()

        self.lbl_status = QLabel(_t("spr_ready_wait"))
        self.lbl_status.setStyleSheet("color: #888899; font-size: 11px;")
        header_layout.addWidget(self.lbl_status)
        layout.addLayout(header_layout)

        # Barra de busqueda y filtros rapidos
        filter_box = QHBoxLayout()
        filter_box.setSpacing(6)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText(_t("spr_search"))
        self.txt_search.setStyleSheet("""
            QLineEdit {
                background: #0D0D14; color: #00E5FF;
                border: 1px solid #2A2A38; border-radius: 4px;
                padding: 6px 10px; font-size: 11px; font-family: 'Consolas';
            }
            QLineEdit:focus { border-color: #00FF96; }
        """)
        self.txt_search.textChanged.connect(self._on_search_changed)
        filter_box.addWidget(self.txt_search, 2)

        # Botones de Categoria
        self.filter_buttons: Dict[str, QPushButton] = {}
        categories = [
            ("ALL", "TODOS", "#FFFFFF"),
            ("Player", "JUGADOR", "#00FF96"),
            ("Herramientas", "HERRAMIENTAS", "#00BFFF"),
            ("Animales", "ANIMALES", "#FFD700"),
            ("NPCs", "NPCS", "#FF77AA"),
            ("Varios", "VARIOS", "#AAAAAA"),
        ]

        for cat_key, cat_label, color in categories:
            btn = QPushButton(cat_label)
            btn.setCheckable(True)
            btn.setChecked(cat_key == "ALL")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: #14141E; color: {color};
                    border: 1px solid #2A2A38; border-radius: 4px;
                    padding: 5px 10px; font-size: 10px; font-weight: bold;
                }}
                QPushButton:checked {{
                    background: {color}; color: #000000;
                }}
                QPushButton:hover {{ border-color: {color}; }}
            """)
            btn.clicked.connect(lambda chk, k=cat_key: self._on_filter_changed(k))
            filter_box.addWidget(btn)
            self.filter_buttons[cat_key] = btn

        self.lbl_count = QLabel("0 / 0")
        self.lbl_count.setStyleSheet("color: #777788; font-family: 'Consolas'; font-size: 11px;")
        filter_box.addWidget(self.lbl_count)

        layout.addLayout(filter_box)

        # Area Central con Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle { background-color: #1F1F2C; }
        """)

        # 1. Lista Lateral Izquierda
        list_container = QWidget()
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(4)

        self.anim_list = QListWidget()
        self.anim_list.setFixedWidth(280)
        self.anim_list.setStyleSheet("""
            QListWidget {
                background: #09090F; color: #FFFFFF;
                border: 1px solid #1F1F2C; border-radius: 4px;
                font-family: 'Consolas'; font-size: 11px;
            }
            QListWidget::item { padding: 4px 6px; border-bottom: 1px solid #141420; }
            QListWidget::item:selected { background: #163328; border-left: 3px solid #00FF96; color: #00FF96; }
            QListWidget::item:hover { background: #141420; }
        """)
        self.anim_list.currentRowChanged.connect(self._on_item_selected)
        list_layout.addWidget(self.anim_list)

        splitter.addWidget(list_container)

        # 2. Area Central: Reproductor y Sheet
        center_container = QWidget()
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(4, 0, 4, 0)
        center_layout.setSpacing(6)

        # Pestañas: Animacion en Vivo / Spritesheet
        self.tab_views = QTabWidget()
        self.tab_views.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #1F1F2C; background: #0A0A10; }
            QTabBar::tab { background: #12121A; color: #888899; padding: 6px 16px; border: 1px solid #1F1F2C; }
            QTabBar::tab:selected { background: #1E1E2C; color: #00FF96; font-weight: bold; border-bottom: 2px solid #00FF96; }
        """)

        self.player_widget = LiveAnimationPlayer()
        self.tab_views.addTab(self.player_widget, _t("spr_tab_live"))

        self.sheet_widget = SheetViewer()
        self.tab_views.addTab(self.sheet_widget, _t("spr_tab_sheet"))

        center_layout.addWidget(self.tab_views, 1)

        # Botones de Accion Inferiores
        action_bar = QHBoxLayout()
        action_bar.setSpacing(8)

        self.btn_export_gif = QPushButton(_t("spr_btn_gif"))
        self.btn_export_gif.setProperty("variant", "secondary")
        self.btn_export_gif.clicked.connect(self._on_export_gif)
        action_bar.addWidget(self.btn_export_gif)

        self.btn_export_sheet = QPushButton(_t("spr_btn_sheet"))
        self.btn_export_sheet.setProperty("variant", "secondary")
        self.btn_export_sheet.clicked.connect(self._on_export_sheet)
        action_bar.addWidget(self.btn_export_sheet)

        self.btn_export_strip = QPushButton(_t("spr_btn_strip"))
        self.btn_export_strip.setProperty("variant", "secondary")
        self.btn_export_strip.clicked.connect(self._on_export_strip)
        action_bar.addWidget(self.btn_export_strip)

        action_bar.addStretch()

        self.btn_export_bulk = QPushButton(_t("spr_btn_bulk"))
        self.btn_export_bulk.setProperty("variant", "secondary")
        self.btn_export_bulk.clicked.connect(self._on_export_bulk)
        action_bar.addWidget(self.btn_export_bulk)

        center_layout.addLayout(action_bar)
        splitter.addWidget(center_container)

        # 3. Panel Lateral Derecho: Telemetria e Info
        self.info_panel = SpriteInfoPanel()
        splitter.addWidget(self.info_panel)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        layout.addWidget(splitter, 1)

    # ============================================================
    #  API PUBLICA Y PROYECTO
    # ============================================================

    def set_project(self, project):
        self.project = project
        if not project or not project.base_rom_data:
            self.lbl_status.setText(_t("spr_no_rom"))
            return

        from Banco_de_Datos.parche_splash import require_rom_signature
        require_rom_signature(project, auto_sign=True, module_name='VisorSprites')
        self.engine = SymphonySpriteEngine(project.base_rom_data)
        mode = "mfomt" if getattr(project, "is_mfomt", False) else "fomt"
        self._load_animations_database(mode)
        self._apply_filters()
        self.lbl_status.setText(_t("spr_rom_ready", n=len(self._animations)))

    def reset(self):
        self.project = None
        self.engine = None
        self._animations = []
        self._filtered_indices = []
        self._current_anim_data = None
        self.anim_list.clear()
        self.player_widget.load_animation(None)
        self.sheet_widget.load_sheet_data(None)
        self.info_panel.clear_info()
        self.lbl_status.setText(_t("spr_reset"))

    # ============================================================
    #  CARGA DE DATOS CANONICOS
    # ============================================================

    def _load_animations_database(self, mode: str):
        self._animations = []

        # Buscar Fomt_Animations_Base.csv o Fomt_Animations.csv
        csv_path = get_data_path(mode, "Fomt_Animations_Base.csv")
        if not os.path.exists(csv_path):
            csv_path = get_data_path(mode, "Fomt_Animations.csv")

        # Fallback a directorio cilixes
        if not os.path.exists(csv_path):
            alt_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "Banco_de_Datos", "Cilixes", "fomt", "Fomt_Animations_Base.csv"
            )
            if os.path.exists(alt_path):
                csv_path = alt_path

        if not os.path.exists(csv_path):
            print(f"[VisorSprites] No se encontro el archivo de animaciones canonicas en {csv_path}")
            return

        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                r = csv.reader(f)
                next(r, None)  # header
                for row in r:
                    if not row or len(row) < 2 or not row[1].strip():
                        continue
                    name = row[0].strip()
                    try:
                        anim_id = int(row[1].strip(), 16)
                    except ValueError:
                        continue

                    category = self._categorize_name(name)
                    self._animations.append({
                        "name": name,
                        "anim_id": anim_id,
                        "category": category
                    })
        except Exception as e:
            print(f"[VisorSprites] Error leyendo base de animaciones: {e}")

    def _categorize_name(self, name: str) -> str:
        n = name.lower()
        if any(k in n for k in ["player", "eat", "drimk", "dizzy", "withdraw"]):
            return "Player"
        elif any(k in n for k in [
            "axe", "hammer", "hoe", "sickle", "fishing", "watering", "brush", "milker", "shears", "tool"
        ]):
            return "Herramientas"
        elif any(k in n for k in [
            "dog", "horse", "sheep", "cow", "chicken", "chick", "bee", "scarab", "animal", "bird", "crab", "beetle", "rabbit"
        ]):
            return "Animales"
        elif any(k in n for k in [
            "karen", "popuri", "ann", "mary", "elli", "doctor", "cliff", "gray", "kai", "rick", "won",
            "zack", "gotz", "carter", "mayor", "thomas", "harris", "barley", "may", "elena", "lillia",
            "saibara", "duke", "manna", "doug", "ellen", "stu", "jeff", "sasha", "gourmet", "chef",
            "aqua", "hoggy", "timid", "staid", "nappy", "bold", "baby", "goddess", "kappa"
        ]):
            return "NPCs"
        return "Varios"

    # ============================================================
    #  FILTRADO Y SELECCION
    # ============================================================

    def _on_filter_changed(self, category: str):
        self.current_filter = category
        for k, btn in self.filter_buttons.items():
            btn.setChecked(k == category)
        self._apply_filters()

    def _on_search_changed(self, text: str):
        self._apply_filters()

    def _apply_filters(self):
        query = self.txt_search.text().strip().lower()
        self.anim_list.clear()
        self._filtered_indices = []

        cat_colors = {
            "Player": "#00FF96",
            "Herramientas": "#00BFFF",
            "Animales": "#FFD700",
            "NPCs": "#FF77AA",
            "Varios": "#CCCCCC"
        }

        for idx, item in enumerate(self._animations):
            if self.current_filter != "ALL" and item["category"] != self.current_filter:
                continue

            if query:
                hex_id = f"0x{item['anim_id']:04x}"
                dec_id = str(item['anim_id'])
                if query not in item["name"].lower() and query not in hex_id and query not in dec_id:
                    continue

            self._filtered_indices.append(idx)
            text = f"[0x{item['anim_id']:04X}] {item['name']}"
            list_item = QListWidgetItem(text)
            color = cat_colors.get(item["category"], "#CCCCCC")
            list_item.setForeground(QColor(color))
            self.anim_list.addItem(list_item)

        self.lbl_count.setText(f"{len(self._filtered_indices)} / {len(self._animations)}")

        if self._filtered_indices:
            self.anim_list.setCurrentRow(0)
        else:
            self.player_widget.load_animation(None)
            self.sheet_widget.load_sheet_data(None)
            self.info_panel.clear_info()

    def _on_item_selected(self, row: int):
        if row < 0 or row >= len(self._filtered_indices):
            return

        global_idx = self._filtered_indices[row]
        item = self._animations[global_idx]
        self._render_selected_animation(item)

    def _render_selected_animation(self, item: Dict[str, Any]):
        if not self.engine:
            return

        anim_id = item["anim_id"]
        data = self.engine.render_animation_data(anim_id)

        if not data:
            self.lbl_status.setText(_t("spr_no_frames", id=f"0x{anim_id:04X}", name=item['name']))
            self.player_widget.load_animation(None)
            self.sheet_widget.load_sheet_data(None)
            self.info_panel.clear_info()
            return

        self._current_anim_data = data
        self.player_widget.load_animation(data)
        self.sheet_widget.load_sheet_data(data)
        self.info_panel.update_info(item["name"], anim_id, item["category"], data)
        self.lbl_status.setText(_t("spr_showing", name=item['name'], id=f"0x{anim_id:04X}", n=len(data['frames'])))

    # ============================================================
    #  EXPORTACION CANONICA
    # ============================================================

    def _on_export_gif(self):
        if not self._current_anim_data or not self.anim_list.currentItem():
            QMessageBox.warning(self, _t("msg_warning"), _t("spr_no_anim_selected"))
            return

        row = self.anim_list.currentRow()
        item = self._animations[self._filtered_indices[row]]
        name = "".join(c if c not in '\\/:*?"<>|' else '_' for c in item["name"])

        path, _ = QFileDialog.getSaveFileName(self, _t("spr_dlg_gif"), f"{name}.gif", "GIF (*.gif)")
        if not path:
            return

        frames = self._current_anim_data["frames"]
        durations = self._current_anim_data["durations"]
        if not frames:
            return

        try:
            frames[0].save(
                path,
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                loop=0,
                disposal=2
            )
            QMessageBox.information(self, _t("spr_export_ok_title"), _t("spr_gif_saved", path=path))
        except Exception as e:
            QMessageBox.critical(self, _t("msg_error"), _t("spr_gif_error", err=e))

    def _on_export_sheet(self):
        if not self._current_anim_data or not self.anim_list.currentItem():
            QMessageBox.warning(self, _t("msg_warning"), _t("spr_no_sheet_avail"))
            return

        row = self.anim_list.currentRow()
        item = self._animations[self._filtered_indices[row]]
        name = "".join(c if c not in '\\/:*?"<>|' else '_' for c in item["name"])

        path, _ = QFileDialog.getSaveFileName(self, _t("spr_dlg_sheet"), f"{name}_sheet.png", "PNG (*.png)")
        if not path:
            return

        sheet = self._current_anim_data.get("sheet")
        if not sheet:
            return

        try:
            sheet.save(path, format="PNG")
            QMessageBox.information(self, _t("spr_export_ok_title"), _t("spr_sheet_saved", path=path))
        except Exception as e:
            QMessageBox.critical(self, _t("msg_error"), _t("spr_sheet_error", err=e))

    def _on_export_strip(self):
        if not self._current_anim_data or not self.anim_list.currentItem():
            QMessageBox.warning(self, _t("msg_warning"), _t("spr_no_strip"))
            return

        row = self.anim_list.currentRow()
        item = self._animations[self._filtered_indices[row]]
        name = "".join(c if c not in '\\/:*?"<>|' else '_' for c in item["name"])

        path, _ = QFileDialog.getSaveFileName(self, _t("spr_dlg_strip"), f"{name}_strip.png", "PNG (*.png)")
        if not path:
            return

        strip = self._current_anim_data.get("strip")
        if not strip:
            return

        try:
            strip.save(path, format="PNG")
            QMessageBox.information(self, _t("spr_export_ok_title"), _t("spr_strip_saved", path=path))
        except Exception as e:
            QMessageBox.critical(self, _t("msg_error"), _t("spr_strip_error", err=e))

    def _on_export_bulk(self):
        if not self.engine or not self._animations:
            QMessageBox.warning(self, _t("msg_warning"), _t("spr_no_bulk_data"))
            return

        out_dir = QFileDialog.getExistingDirectory(self, _t("spr_dlg_bulk_dir"))
        if not out_dir:
            return

        target_items = [self._animations[i] for i in self._filtered_indices]
        count = len(target_items)

        reply = QMessageBox.question(
            self,
            _t("spr_bulk_confirm_title"),
            _t("spr_bulk_confirm", count=count, path=out_dir),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        dir_gifs = os.path.join(out_dir, "gifs")
        dir_sheets = os.path.join(out_dir, "sheets")
        os.makedirs(dir_gifs, exist_ok=True)
        os.makedirs(dir_sheets, exist_ok=True)

        exported = 0
        for item in target_items:
            data = self.engine.render_animation_data(item["anim_id"])
            if not data or not data["frames"]:
                continue

            clean_name = "".join(c if c not in '\\/:*?"<>|' else '_' for c in item["name"])
            gif_path = os.path.join(dir_gifs, f"{clean_name}.gif")
            sheet_path = os.path.join(dir_sheets, f"{clean_name}_sheet.png")

            try:
                data["frames"][0].save(
                    gif_path,
                    save_all=True,
                    append_images=data["frames"][1:],
                    duration=data["durations"],
                    loop=0,
                    disposal=2
                )
                if data.get("sheet"):
                    data["sheet"].save(sheet_path, format="PNG")
                exported += 1
            except Exception:
                pass

        QMessageBox.information(
            self,
            _t("spr_bulk_done_title"),
            _t("spr_bulk_done", exported=exported, count=count, path=out_dir)
        )
