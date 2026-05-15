# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.6.5)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
"""
visor_sprites.py — Explorador Visual de Sprites (CSV-Driven)
═══════════════════════════════════════════════════════════════
Visor renovado con estética del visor de audio (dark theme).
Carga sprites desde sprite_data.csv usando el motor GBA Graphic Editor.
"""
import os
import csv
import struct
import io
import sys
from Nucleos_de_Procesamiento.Nucleo_de_Datos.Utilidades.rutas import get_data_path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget,
    QListWidgetItem, QLabel, QComboBox, QPushButton, QGroupBox,
    QScrollArea, QFileDialog, QSpinBox, QFrame
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor
from PIL import Image


def pil_to_qpixmap(pil_img, scale=1):
    if scale > 1:
        pil_img = pil_img.resize(
            (pil_img.width * scale, pil_img.height * scale), Image.NEAREST
        )
    buf = io.BytesIO()
    pil_img.save(buf, format='PNG')
    buf.seek(0)
    qimg = QImage()
    qimg.loadFromData(buf.read())
    return QPixmap.fromImage(qimg)


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
            p.setPen(QColor(60, 60, 60))
            p.drawRect(i * cw, 0, cw - 1, self.height() - 1)
        p.end()


# ═══════════════════════════════════════════════════════════════
# PANEL DE INFORMACIÓN (Estilo SongInfoPanel del visor de audio)
# ═══════════════════════════════════════════════════════════════

class SpriteInfoPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(260)
        self.setStyleSheet("""
            SpriteInfoPanel {
                background: #0D0D12;
                border: 1px solid #2A2A35;
                border-radius: 6px;
            }
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        title = QLabel("SPRITE INFO")
        title.setStyleSheet("color: #00FF96; font-size: 13px; font-weight: bold; letter-spacing: 2px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine); sep.setStyleSheet("color: #2A2A35;")
        layout.addWidget(sep)

        self.lbl_name = self._field("Name:")
        self.lbl_offset = self._field("Tile Offset:")
        self.lbl_palette = self._field("Palette Offset:")
        self.lbl_size = self._field("Data Size:")
        self.lbl_dims = self._field("Dimensions:")
        self.lbl_category = self._field("Category:")

        for lbl in [self.lbl_name, self.lbl_offset, self.lbl_palette, self.lbl_size, self.lbl_dims, self.lbl_category]:
            layout.addWidget(lbl)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine); sep2.setStyleSheet("color: #2A2A35;")
        layout.addWidget(sep2)

        self.pal_preview = PaletteStrip()
        layout.addWidget(QLabel("PALETTE", styleSheet="color: #FFD700; font-size: 11px; font-weight: bold; letter-spacing: 1px;"))
        layout.addWidget(self.pal_preview)
        layout.addStretch()

    def _field(self, text):
        lbl = QLabel(f"{text} —")
        lbl.setStyleSheet("color: #CCCCCC; font-size: 11px; font-family: 'Consolas';")
        return lbl

    def update_info(self, name, tile_off, pal_off, data_size, dims, category, palette_colors=None):
        self.lbl_name.setText(f"Name: {name}")
        self.lbl_offset.setText(f"Tile Offset: 0x{tile_off:06X}")
        self.lbl_palette.setText(f"Palette Offset: 0x{pal_off:06X}")
        self.lbl_size.setText(f"Data Size: {data_size} bytes")
        self.lbl_dims.setText(f"Dimensions: {dims}")
        cat_colors = {"Overworld": "#00FF96", "Portrait": "#00BFFF", "Animal": "#FFD700"}
        c = cat_colors.get(category, "#AAAAAA")
        self.lbl_category.setText(f"Category: {category}")
        self.lbl_category.setStyleSheet(f"color: {c}; font-size: 11px; font-family: 'Consolas'; font-weight: bold;")
        if palette_colors:
            self.pal_preview.set_palette(palette_colors)

    def clear_info(self):
        for lbl in [self.lbl_name, self.lbl_offset, self.lbl_palette, self.lbl_size, self.lbl_dims]:
            lbl.setText(lbl.text().split(":")[0] + ": —")
        self.lbl_category.setText("Category: —")
        self.pal_preview.set_palette(None)


# ═══════════════════════════════════════════════════════════════
# VISOR DE SPRITES PRINCIPAL
# ═══════════════════════════════════════════════════════════════

class VisorSprites(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.project = None
        self._sprites = []  # List of dicts from CSV
        self._current_image = None
        self._current_palette = None
        self.current_filter = "ALL"
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── Header ──
        header = QLabel("🎨 Explorador de Sprites (GBA Graphic Editor)")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #00FF96;")
        layout.addWidget(header)

        # ── Filtros pill-buttons (estilo visor de audio) ──
        filter_layout = QHBoxLayout()
        filter_label = QLabel("Filter:")
        filter_label.setStyleSheet("color: #888888; font-size: 11px;")
        filter_layout.addWidget(filter_label)

        self.filter_buttons = {}
        filter_defs = [
            ("ALL",       "All",              "#FFFFFF"),
            ("Overworld", "🧍 Overworld",     "#00FF96"),
            ("Portrait",  "👤 Portraits",     "#00BFFF"),
            ("Animal",    "🐾 Animals",       "#FFD700"),
        ]
        for cat_key, cat_label, cat_color in filter_defs:
            btn = QPushButton(cat_label)
            btn.setCheckable(True)
            btn.setChecked(cat_key == "ALL")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: #1A1A1E; color: {cat_color};
                    border: 1px solid #333; border-radius: 4px;
                    padding: 4px 10px; font-size: 11px;
                }}
                QPushButton:checked {{
                    background: {cat_color}; color: #000000; font-weight: bold;
                }}
                QPushButton:hover {{ border-color: {cat_color}; }}
            """)
            btn.clicked.connect(lambda checked, k=cat_key: self._on_filter(k))
            filter_layout.addWidget(btn)
            self.filter_buttons[cat_key] = btn

        filter_layout.addStretch()
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #555555; font-size: 11px;")
        filter_layout.addWidget(self.count_label)
        layout.addLayout(filter_layout)

        # ── Main area ──
        main_h = QHBoxLayout()

        # 1. Lista de sprites (estilo song list)
        self.sprite_list = QListWidget()
        self.sprite_list.setFixedWidth(300)
        self.sprite_list.setStyleSheet("""
            QListWidget {
                background: #0D0D12; color: white;
                border: 1px solid #2A2A35; border-radius: 4px;
                font-family: 'Consolas'; font-size: 11px;
            }
            QListWidget::item { padding: 3px 6px; border-bottom: 1px solid #1A1A1E; }
            QListWidget::item:selected { background: #1A3A2A; border-left: 3px solid #00FF96; }
            QListWidget::item:hover { background: #151520; }
        """)
        self.sprite_list.currentRowChanged.connect(self._on_sprite_selected)
        main_h.addWidget(self.sprite_list)

        # 2. Panel central (preview + controles)
        center_panel = QVBoxLayout()

        # Preview con scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: #1a1a2e; border: 1px solid #2A2A35; border-radius: 4px;")
        self.lbl_preview = QLabel("Selecciona un sprite para previsualizar")
        self.lbl_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview.setStyleSheet("color: #666; font-size: 14px;")
        scroll.setWidget(self.lbl_preview)
        center_panel.addWidget(scroll, 3)

        # Controles
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("Zoom:", styleSheet="color: #888; font-size: 11px;"))
        self.spn_zoom = QSpinBox()
        self.spn_zoom.setRange(1, 8)
        self.spn_zoom.setValue(4)
        self.spn_zoom.setStyleSheet("background: #1A1A1E; color: white; border: 1px solid #333; padding: 4px; border-radius: 3px;")
        self.spn_zoom.valueChanged.connect(self._refresh_preview)
        ctrl_layout.addWidget(self.spn_zoom)

        ctrl_layout.addWidget(QLabel("Tiles/Row:", styleSheet="color: #888; font-size: 11px;"))
        self.spn_tiles = QSpinBox()
        self.spn_tiles.setRange(1, 32)
        self.spn_tiles.setValue(4)
        self.spn_tiles.setStyleSheet("background: #1A1A1E; color: white; border: 1px solid #333; padding: 4px; border-radius: 3px;")
        self.spn_tiles.valueChanged.connect(self._refresh_preview)
        ctrl_layout.addWidget(self.spn_tiles)

        ctrl_layout.addStretch()

        self.btn_export_bmp = QPushButton("💾 Export BMP")
        self.btn_export_bmp.setStyleSheet("""
            QPushButton { background: #00BFFF; color: black; font-weight: bold; padding: 8px 16px; border-radius: 4px; font-size: 11px; }
            QPushButton:hover { background: #33CCFF; }
        """)
        self.btn_export_bmp.clicked.connect(self._on_export_bmp)
        ctrl_layout.addWidget(self.btn_export_bmp)

        self.btn_export_gif = QPushButton("🎞 Export GIF")
        self.btn_export_gif.setStyleSheet("""
            QPushButton { background: #00FF96; color: black; font-weight: bold; padding: 8px 16px; border-radius: 4px; font-size: 11px; }
            QPushButton:hover { background: #33FFB0; }
        """)
        self.btn_export_gif.clicked.connect(self._on_export_gif)
        ctrl_layout.addWidget(self.btn_export_gif)

        self.btn_export_all = QPushButton("📦 Export All")
        self.btn_export_all.setStyleSheet("""
            QPushButton { background: #FFD700; color: black; font-weight: bold; padding: 8px 16px; border-radius: 4px; font-size: 11px; }
            QPushButton:hover { background: #FFE033; }
        """)
        self.btn_export_all.clicked.connect(self._on_export_all)
        ctrl_layout.addWidget(self.btn_export_all)

        center_panel.addLayout(ctrl_layout)
        main_h.addLayout(center_panel)

        # 3. Info panel (derecha)
        self.info_panel = SpriteInfoPanel()
        main_h.addWidget(self.info_panel)

        layout.addLayout(main_h)

    # ═══════════════════════════════════════════════════════════
    #  API PÚBLICA
    # ═══════════════════════════════════════════════════════════

    def set_project(self, project):
        self.project = project
        mode = "mfomt" if project.is_mfomt else "fomt"
        self._load_sprite_data(mode)
        self._populate_list()

    def reset(self):
        self.project = None
        self._sprites = []
        self.sprite_list.clear()
        self.lbl_preview.setPixmap(QPixmap())
        self.lbl_preview.setText("Selecciona un sprite para previsualizar")
        self.info_panel.clear_info()

    # ═══════════════════════════════════════════════════════════
    #  CARGA DESDE CSV
    # ═══════════════════════════════════════════════════════════

    def _load_sprite_data(self, mode):
        """Carga sprite_data.csv con soporte para múltiples formatos y secciones."""
        self._sprites = []
        
        # Usar la utilidad de rutas para encontrar el CSV
        prefix = "MFomt_" if mode == "mfomt" else "Fomt_"
        csv_path = get_data_path(mode, f"{prefix}Sprite_data.csv")
        
        if not os.path.exists(csv_path):
            print(f"⚠️ [VisorSprites] {csv_path} no encontrado")
            return

        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, None)  # Saltar cabecera: Nombre,Offset_LE,Paleta_LE
                
                for row in reader:
                    if not row or len(row) < 2:
                        continue
                    
                    name = row[0].strip()
                    off_raw = row[1].strip()
                    pal_raw = row[2].strip() if len(row) > 2 else ""
                    
                    tile_off = self._parse_offset(off_raw)
                    pal_off = self._parse_offset(pal_raw)
                    
                    if tile_off <= 0:
                        continue
                    
                    # Detección inteligente de categoría
                    if ' ' in off_raw:
                        category = "Animal"
                    elif any(k in name.lower() for k in ["player", "map-"]):
                        category = "Portrait"
                    else:
                        category = "Overworld"

                    self._sprites.append({
                        "name": name,
                        "tile_offset": tile_off,
                        "palette_offset": pal_off,
                        "category": category,
                    })

            # Calcular el límite de bytes (max_size) basado en el siguiente offset diferente
            # Esto evita que se "pisen" o se vean otros spritesheets en el visor.
            sorted_by_off = sorted(self._sprites, key=lambda x: x["tile_offset"])
            for i in range(len(sorted_by_off)):
                curr = sorted_by_off[i]
                next_off = 0
                for j in range(i + 1, len(sorted_by_off)):
                    if sorted_by_off[j]["tile_offset"] > curr["tile_offset"]:
                        next_off = sorted_by_off[j]["tile_offset"]
                        break
                
                if next_off > 0:
                    curr["max_size"] = next_off - curr["tile_offset"]
                else:
                    curr["max_size"] = 4096 # Default 128 tiles
            
            print(f"✅ [VisorSprites] Cargados {len(self._sprites)} sprites desde {csv_path}")
        except Exception as e:
            print(f"❌ [VisorSprites] Error cargando CSV: {e}")

    def _parse_offset(self, raw_str):
        """Convierte 'BC D7 64 00' (LE) o '5FA73C' (HEX) a offset entero."""
        raw_str = raw_str.strip()
        if not raw_str:
            return 0
            
        # Caso 1: Bytes separados por espacios (Little Endian)
        if ' ' in raw_str:
            try:
                byte_vals = [int(b, 16) for b in raw_str.split()]
                if len(byte_vals) == 4:
                    return struct.unpack('<I', bytes(byte_vals))[0]
            except (ValueError, struct.error):
                pass
                
        # Caso 2: Hexadecimal directo (offset crudo de archivo)
        try:
            return int(raw_str, 16)
        except ValueError:
            return 0

    # ═══════════════════════════════════════════════════════════
    #  FILTROS Y LISTA
    # ═══════════════════════════════════════════════════════════

    def _on_filter(self, category):
        self.current_filter = category
        for key, btn in self.filter_buttons.items():
            btn.setChecked(key == category)
        self._populate_list()

    def _populate_list(self):
        self.sprite_list.clear()
        visible = 0
        cat_colors = {"Overworld": "#00FF96", "Portrait": "#00BFFF", "Animal": "#FFD700"}

        for i, sp in enumerate(self._sprites):
            if self.current_filter != "ALL" and sp["category"] != self.current_filter:
                continue
            cat_icon = {"Overworld": "🧍", "Portrait": "👤", "Animal": "🐾"}.get(sp["category"], "")
            text = f"[{i:03d}] {cat_icon} {sp['name']}"
            item = QListWidgetItem(text)
            item.setForeground(QColor(cat_colors.get(sp["category"], "#FFFFFF")))
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.sprite_list.addItem(item)
            visible += 1

        self.count_label.setText(f"{visible} / {len(self._sprites)} sprites")

    def _on_sprite_selected(self, row):
        if row < 0:
            self.info_panel.clear_info()
            return
        item = self.sprite_list.item(row)
        if not item:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx is None or idx >= len(self._sprites):
            return
        self._render_sprite(self._sprites[idx])

    def _refresh_preview(self):
        row = self.sprite_list.currentRow()
        if row >= 0:
            self._on_sprite_selected(row)

    # ═══════════════════════════════════════════════════════════
    #  RENDERIZADO
    # ═══════════════════════════════════════════════════════════

    def _render_sprite(self, sp):
        if not self.project or not self.project.base_rom_data:
            self.lbl_preview.setText("Error: No hay ROM cargada")
            return

        from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.sprite_decoder import SpriteRenderer
        from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.codec_tiles import bgr555_to_rgb

        rom = self.project.base_rom_data
        tiles_wide = self.spn_tiles.value()
        zoom = self.spn_zoom.value()

        max_size = sp.get("max_size", 4096)
        img = SpriteRenderer.render_from_csv_entry(
            rom, sp["tile_offset"], sp["palette_offset"], tiles_wide, max_size
        )

        if img:
            self._current_image = img
            pixmap = pil_to_qpixmap(img, zoom)
            self.lbl_preview.setPixmap(pixmap)
            self.lbl_preview.setText("")

            # Leer paleta para el info panel
            pal_data = rom[sp["palette_offset"]:sp["palette_offset"] + 32]
            palette_colors = []
            if len(pal_data) >= 32:
                palette_colors = [bgr555_to_rgb(struct.unpack_from('<H', pal_data, i * 2)[0]) for i in range(16)]
            self._current_palette = palette_colors

            self.info_panel.update_info(
                sp["name"], sp["tile_offset"], sp["palette_offset"],
                img.width * img.height // 2,  # Approx 4bpp
                f"{img.width}×{img.height}px",
                sp["category"], palette_colors
            )
        else:
            self.lbl_preview.setText("No se pudo renderizar el sprite")
            self._current_image = None

    # ═══════════════════════════════════════════════════════════
    #  EXPORTACIÓN
    # ═══════════════════════════════════════════════════════════

    def _on_export_bmp(self):
        if not self._current_image:
            return
        row = self.sprite_list.currentRow()
        item = self.sprite_list.item(row)
        idx = item.data(Qt.ItemDataRole.UserRole) if item else 0
        sp = self._sprites[idx] if idx < len(self._sprites) else {"name": "sprite"}
        path, _ = QFileDialog.getSaveFileName(self, "Exportar BMP", f"{sp['name']}.bmp", "BMP (*.bmp)")
        if path:
            self._current_image.save(path, 'BMP')

    def _on_export_gif(self):
        if not self.project or not self.project.base_rom_data:
            return
        row = self.sprite_list.currentRow()
        item = self.sprite_list.item(row)
        if not item:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        sp = self._sprites[idx]

        from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.sprite_decoder import SpriteRenderer
        from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.codec_tiles import bgr555_to_rgb
        from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.mapas import decompress_lz77

        rom = self.project.base_rom_data
        tile_data = None
        try:
            tile_data = decompress_lz77(rom, sp["tile_offset"])
        except (ValueError, IndexError):
            pass
        if not tile_data:
            raw_size = min(4096, len(rom) - sp["tile_offset"])
            tile_data = rom[sp["tile_offset"]:sp["tile_offset"] + raw_size]

        pal_data = rom[sp["palette_offset"]:sp["palette_offset"] + 32]
        palette = [(0, 0, 0)] * 16
        if len(pal_data) >= 32:
            palette = [bgr555_to_rgb(struct.unpack_from('<H', pal_data, i * 2)[0]) for i in range(16)]

        # Extraer frames (asumiendo 16x32 o 16x16 por frame)
        frames = SpriteRenderer.extract_frames_from_sheet(tile_data, palette, 16, 32)
        if not frames:
            frames = SpriteRenderer.extract_frames_from_sheet(tile_data, palette, 16, 16)

        if frames:
            path, _ = QFileDialog.getSaveFileName(self, "Exportar GIF", f"{sp['name']}.gif", "GIF (*.gif)")
            if path:
                SpriteRenderer.create_animated_gif(frames, path, duration=150)

    def _on_export_all(self):
        if not self._sprites or not self.project:
            return
        folder = QFileDialog.getExistingDirectory(self, "Carpeta de exportación")
        if not folder:
            return

        from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.sprite_decoder import SpriteRenderer

        rom = self.project.base_rom_data
        count = 0
        for sp in self._sprites:
            if self.current_filter != "ALL" and sp["category"] != self.current_filter:
                continue
            img = SpriteRenderer.render_from_csv_entry(
                rom, sp["tile_offset"], sp["palette_offset"], self.spn_tiles.value()
            )
            if img:
                safe_name = sp["name"].replace("/", "_").replace("\\", "_").replace(" ", "_")
                img.save(os.path.join(folder, f"{safe_name}.bmp"), 'BMP')
                count += 1

        self.count_label.setText(f"✅ Exportados {count} sprites a {folder}")
