# ============================================================
# FOMT Studio - Portrait Editor Dialog
# Melody Portrait Engine - v2.0 (Con Editor de Paleta GBA)
# Desarrollado por: Denisovich728
# ============================================================
import os
import sys
import struct
import shutil
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QMessageBox, QFrame, QGridLayout,
    QCheckBox, QSizePolicy
)
from PyQt6.QtGui import QPixmap, QFont, QColor
from PyQt6.QtCore import Qt

# ─── Palette Editor ──────────────────────────────────────────────────────────
from Perifericos.Interfaz_Usuario.widgets.palette_editor import PaletteEditorDialog, gba_to_rgb888


# ─── Constants ───────────────────────────────────────────────────────────────
DUMP_DIR   = r"j:\Repositorios\fomt_studio\portraits_dump"
ROM_PATH   = r"j:\Repositorios\fomt_studio\Harvest Moon - Friends of Mineral Town.gba"
FOMT_BASE  = 0x08000000


# ─── ROM helpers ─────────────────────────────────────────────────────────────

def _read_rom_palette(hex_id: int, rom_path: str = ROM_PATH) -> list:
    """
    Lee la paleta GBA del portrait identificado por hex_id directamente
    desde la ROM nativa o la ROM ya expandida (auto-detecta ambas).
    Devuelve lista de 16 tuplas (r, g, b).
    """
    try:
        with open(rom_path, 'rb') as f:
            rom = f.read()

        # Detectar cabecera dinámica (igual que repack_portraits.py)
        header_addr = struct.unpack('<I', rom[0xadc7c:0xadc7c + 4])[0] - FOMT_BASE

        counts = []
        ptrs   = []
        r1     = header_addr
        for shift in [2, 4, 3, 5, 5, 3, 2]:
            cnt = struct.unpack('<I', rom[r1:r1 + 4])[0]
            counts.append(cnt)
            r1 += 4
            ptrs.append(r1)
            r1 += cnt * (1 << shift)

        # Tabla 1: portrait_id → internal_idx (word en offset +2)
        t1_base = ptrs[0]
        internal_idx = struct.unpack('<H', rom[t1_base + hex_id * 4 + 2:
                                              t1_base + hex_id * 4 + 4])[0]
        if internal_idx >= counts[1]:
            return [(0, 0, 0)] * 16

        # Tabla 2: metadata de 16 bytes por entrada
        meta_base = ptrs[1] + internal_idx * 16
        fA = struct.unpack('<H', rom[meta_base + 10: meta_base + 12])[0]  # palette start index

        # Tabla 5: paletas (32 bytes cada una)
        pal_base = ptrs[4] + fA * 32
        colors = []
        for i in range(16):
            c16 = struct.unpack('<H', rom[pal_base + i * 2: pal_base + i * 2 + 2])[0]
            r, g, b = gba_to_rgb888(c16)
            colors.append((r, g, b))
        return colors

    except Exception:
        return [(0, 0, 0)] * 16


# ─────────────────────────────────────────────────────────────────────────────
# Portrait Editor Dialog
# ─────────────────────────────────────────────────────────────────────────────

class PortraitEditorDialog(QDialog):
    """
    Diálogo principal del Melody Portrait Engine.

    Novedades v2.0:
    - Botón "Editar Paleta" que abre PaletteEditorDialog con la paleta real del portrait.
    - Checkbox "Romper límite de sombra" → fuerza Modo Expansión aunque el PNG quepa
      en el bounding box original, eliminando el recorte producido por los OAMs nativos.
    - La paleta editada se inyecta junto con el PNG en la misma operación de repacking.
    """

    # ── Stylesheet ────────────────────────────────────────────────────────────
    _SS = """
    QDialog {
        background-color: #1E1E2E;
        color: #CDD6F4;
        font-family: 'Segoe UI', sans-serif;
    }
    QLabel { color: #CDD6F4; }
    QFrame#visor {
        background-color: #11111B;
        border: 2px solid #45475A;
        border-radius: 8px;
    }
    QPushButton {
        background-color: #313244;
        color: #CDD6F4;
        border: 1px solid #45475A;
        border-radius: 6px;
        padding: 7px 16px;
        font-weight: bold;
    }
    QPushButton:hover { background-color: #7C5CFC; color: white; }
    QPushButton#btn_import {
        background-color: #A31515;
        color: white;
        border-color: #FF3333;
    }
    QPushButton#btn_import:hover { background-color: #CC1C1C; }
    QPushButton#btn_palette {
        background-color: #1F3A5F;
        color: #89B4FA;
        border-color: #4A90D9;
    }
    QPushButton#btn_palette:hover { background-color: #2B5280; color: white; }
    QPushButton#btn_close {
        background-color: #45475A;
        color: #BAC2DE;
    }
    QCheckBox { color: #CDD6F4; spacing: 6px; }
    QCheckBox::indicator {
        width: 16px; height: 16px;
        border: 1px solid #45475A;
        border-radius: 3px;
        background: #313244;
    }
    QCheckBox::indicator:checked {
        background: #7C5CFC;
        border-color: #7C5CFC;
    }
    """

    def __init__(self, npc_name: str, hex_id: int, base_name: str, parent=None):
        super().__init__(parent)
        self.npc_name  = npc_name
        self.hex_id    = hex_id
        self.base_name = base_name

        # Resolving dynamic paths from project if available
        self.project = None
        self.rom_path = ROM_PATH
        self.dump_dir = DUMP_DIR
        
        # Traverse up parents to find project
        curr = parent
        while curr:
            if hasattr(curr, 'project') and curr.project:
                self.project = curr.project
                break
            curr = curr.parent()
            
        if self.project:
            if hasattr(self.project, 'base_rom_path') and self.project.base_rom_path:
                self.rom_path = self.project.base_rom_path
            if hasattr(self.project, 'project_dir') and self.project.project_dir:
                self.dump_dir = os.path.join(self.project.project_dir, "portraits_dump")

        self.current_img_path = os.path.join(
            self.dump_dir, f"{self.hex_id:02X}_{self.base_name}_Neutral.png"
        )

        # Paleta cargada de la ROM (se actualiza si el usuario edita)
        self._palette: list = _read_rom_palette(hex_id, self.rom_path)
        # None = sin cambios (usará la paleta de la ROM original en el repacking)
        self._edited_palette: list | None = None

        self.setWindowTitle(
            f"Melody Portrait Engine  ·  {npc_name}  (ID: {hex_id:02X})"
        )
        self.setMinimumSize(540, 460)
        self.resize(560, 480)
        self.setStyleSheet(self._SS)

        self._build_ui()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(14, 14, 14, 14)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QLabel(
            f"<span style='font-size:15px; font-weight:bold; color:#CBA6F7;'>"
            f"Melody Portrait Engine</span>"
            f"<br><span style='color:#89DCEB;'>Editando: </span>"
            f"<span style='font-weight:bold;'>{self.npc_name}</span>"
            f"  <span style='color:#6C7086;'>ID: {self.hex_id:02X}h</span>"
        )
        hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(hdr)

        # ── Visor ─────────────────────────────────────────────────────────────
        visor = QFrame()
        visor.setObjectName("visor")
        visor.setMinimumHeight(240)
        vis_lay = QVBoxLayout(visor)

        self.lbl_image = QLabel()
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setMinimumSize(256, 220)
        self._refresh_preview()
        vis_lay.addWidget(self.lbl_image)

        # Palette preview strip (16 swatches)
        self.pal_strip = _PaletteStrip(self._palette)
        vis_lay.addWidget(self.pal_strip, alignment=Qt.AlignmentFlag.AlignCenter)

        root.addWidget(visor)

        # ── Mode Selector ─────────────────────────────────────────────────
        # Por defecto siempre usamos Modo Expansión al importar un PNG.
        # Sólo desactiva esto si el PNG es un retoque menor al MISMO portrait
        # (mismo tamaño, mismo layout de tiles) y quieres que sea rápido.
        chk_row = QHBoxLayout()
        self.chk_vanilla = QCheckBox(
            "Modo Vainilla (retoque rápido)  —  únicamente para el mismo portrait con cambios mínimos de píxel"
        )
        self.chk_vanilla.setToolTip(
            "DESACTIVADO por defecto = Modo Expansión (el correcto para portraits nuevos).\n\n"
            "Activa esto SOLO si:\n"
            "  • El PNG tiene exactamente el mismo tamaño que el portrait original.\n"
            "  • Solo cambió el color de alguno píxel (retoque fino).\n"
            "  • Quieres una inyección más rápida sin regenerar los OAMs.\n\n"
            "Si el portrait es nuevo o más grande, déjalo DESACTIVADO.\n"
            "El engine regenerará los OAMs automáticamente y actualizará la metadata."
        )
        self.chk_vanilla.setChecked(False)   # Expansión por defecto — siempre correcto
        chk_row.addWidget(self.chk_vanilla)
        chk_row.addStretch()
        root.addLayout(chk_row)

        # ── Controls Grid ─────────────────────────────────────────────────────
        grid = QGridLayout()
        grid.setSpacing(8)

        btn_dump = QPushButton("⬇  Extraer a PNG")
        btn_dump.setToolTip("Exporta el PNG extraído del volcado a una carpeta de tu elección.")
        btn_dump.clicked.connect(self._export_png)

        btn_import = QPushButton("⬆  Cargar y Reinyectar")
        btn_import.setObjectName("btn_import")
        btn_import.setToolTip(
            "Carga un PNG, lo compila a 4bpp GBA y lo reinyecta en la ROM\n"
            "usando el Shifting Engine (Modo Expansión)."
        )
        btn_import.clicked.connect(self._import_png)

        btn_palette = QPushButton("🎨  Editar Paleta")
        btn_palette.setObjectName("btn_palette")
        btn_palette.setToolTip(
            "Abre el editor de paleta GBA completo (HSV picker, RGB, HEX).\n"
            "Los cambios se aplican en la siguiente inyección."
        )
        btn_palette.clicked.connect(self._open_palette_editor)

        grid.addWidget(btn_dump,    0, 0)
        grid.addWidget(btn_import,  0, 1)
        grid.addWidget(btn_palette, 1, 0, 1, 2)   # full-width second row

        root.addLayout(grid)

        # ── Palette status label ───────────────────────────────────────────────
        self.lbl_pal_status = QLabel("Paleta: usando original de la ROM")
        self.lbl_pal_status.setStyleSheet("color: #6C7086; font-size: 10px;")
        root.addWidget(self.lbl_pal_status)

        # ── Close ─────────────────────────────────────────────────────────────
        btn_close = QPushButton("✖  Cerrar")
        btn_close.setObjectName("btn_close")
        btn_close.clicked.connect(self.close)
        root.addWidget(btn_close)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _refresh_preview(self):
        pix = self._render_hex_portrait()
        if pix:
            self.lbl_image.setPixmap(
                pix.scaled(256, 256,
                           Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.FastTransformation)
            )
        else:
            # Fallback a la imagen extraida (por si falla el engine ROM)
            path = self.current_img_path
            if path and os.path.exists(path):
                pix = QPixmap(path)
                self.lbl_image.setPixmap(
                    pix.scaled(256, 256,
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.FastTransformation)
                )
            else:
                self.lbl_image.setText(
                    "<span style='color:#F38BA8;'>No hay retrato disponible en el volcado.<br>"
                    "Usa <b>Extraer a PNG</b> primero.</span>"
                )

    def _render_hex_portrait(self):
        """Genera el QPixmap directamente desde los tiles 4bpp y OAMs en la ROM."""
        try:
            sys.path.insert(0, r'j:\Repositorios\fomt_studio')
            from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.Melody_Portrait_Engine.repack_portraits import _load_tables, _parse_oams
            from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.Melody_Portrait_Engine.engine import MelodyPortraitEngine
            
            if self.project and hasattr(self.project, 'base_rom_data') and self.project.base_rom_data:
                rom = bytearray(self.project.base_rom_data)
            else:
                with open(self.rom_path, 'rb') as f:
                    rom = bytearray(f.read())
                
            counts, ptrs, tables, _, _ = _load_tables(rom)
            t1, t2, t3, t4, t5, t6, t7 = tables
            
            internal_idx = struct.unpack('<H', t1[self.hex_id*4+2 : self.hex_id*4+4])[0]
            if internal_idx >= counts[1]: return None
            
            meta = internal_idx * 16
            f0  = struct.unpack('<H', t2[meta:meta+2])[0]
            f2  = struct.unpack('<H', t2[meta+2:meta+4])[0]
            f4  = struct.unpack('<H', t2[meta+4:meta+6])[0]
            f6  = struct.unpack('<H', t2[meta+6:meta+8])[0]
            
            engine = MelodyPortraitEngine(None)
            oams = _parse_oams(t3, t2, engine, f0, f2)
            
            if not oams: return None
            
            min_x = min(o['x'] for o in oams)
            min_y = min(o['y'] for o in oams)
            max_x = max(o['x'] + o['w'] for o in oams)
            max_y = max(o['y'] + o['h'] for o in oams)
            
            w = max_x - min_x
            h = max_y - min_y
            if w <= 0 or h <= 0: return None
            
            gfx_data = t4[f6 * 32 : (f6 + f4) * 32]
            palette = self._edited_palette if self._edited_palette else self._palette
            
            from PIL import Image
            from PyQt6.QtGui import QImage, QPixmap
            
            img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
            pixels = img.load()
            
            for oam in oams:
                ox = oam['x'] - min_x
                oy = oam['y'] - min_y
                ow, oh = oam['w'], oam['h']
                t_start = oam['tile']
                for ty in range(oh // 8):
                    for tx in range(ow // 8):
                        t_idx = t_start + (ty * (ow // 8)) + tx
                        if t_idx >= f4: continue
                        boff = t_idx * 32
                        for py in range(8):
                            for px in range(0, 8, 2):
                                cx = ox + tx*8 + px
                                cy = oy + ty*8 + py
                                if cx < 0 or cx >= w or cy < 0 or cy >= h: continue
                                if boff + py*4 + px//2 >= len(gfx_data): continue
                                byte = gfx_data[boff + py*4 + px//2]
                                idx1 = byte & 0xF
                                idx2 = (byte >> 4) & 0xF
                                
                                if idx1 != 0 and idx1 < len(palette) and cx < w:
                                    pixels[cx, cy] = palette[idx1] + (255,)
                                if idx2 != 0 and idx2 < len(palette) and cx+1 < w:
                                    pixels[cx+1, cy] = palette[idx2] + (255,)
            
            img_data = img.tobytes("raw", "RGBA")
            qim = QImage(img_data, img.width, img.height, QImage.Format.Format_RGBA8888)
            return QPixmap.fromImage(qim)
            
        except Exception as e:
            print(f"Error hex visualization: {e}")
            return None

    # ── Palette Editor ────────────────────────────────────────────────────────

    def _open_palette_editor(self):
        if not hasattr(self, '_pal_dlg') or not self._pal_dlg.isVisible():
            current_pal = self._edited_palette if self._edited_palette else self._palette
            self._pal_dlg = PaletteEditorDialog(current_pal, parent=self)
            self._pal_dlg.palette_accepted.connect(self._on_palette_accepted)
            self._pal_dlg.palette_changed_live.connect(self._on_palette_changed_live)
            self._pal_dlg.rejected.connect(self._on_palette_rejected)
            self._pal_dlg.show()
        else:
            self._pal_dlg.raise_()
            self._pal_dlg.activateWindow()

    def _on_palette_rejected(self):
        # Revertir a la paleta guardada previamente si se cancela
        self.pal_strip.set_palette(self._edited_palette if self._edited_palette else self._palette)
        self._refresh_preview()
        self.lbl_pal_status.setText(
            "Paleta: <b style='color:#FAB387;'>EDICIÓN CANCELADA</b> — se restauró la paleta previa."
        )
        self.lbl_pal_status.setTextFormat(Qt.TextFormat.RichText)

    def _on_palette_changed_live(self, palette: list):
        self._edited_palette = palette
        self.pal_strip.set_palette(palette)
        self._refresh_preview()
        self.lbl_pal_status.setText(
            "Paleta: <b style='color:#A6E3A1;'>EDICIÓN EN TIEMPO REAL</b> — click en Guardar para conservar."
        )
        self.lbl_pal_status.setTextFormat(Qt.TextFormat.RichText)

    def _on_palette_accepted(self, palette: list):
        self._edited_palette = palette
        self.pal_strip.set_palette(palette)
        self._refresh_preview()
        self.lbl_pal_status.setText(
            "Paleta: <b style='color:#A6E3A1;'>MODIFICADA</b> — se aplicará en la próxima inyección."
        )
        self.lbl_pal_status.setTextFormat(Qt.TextFormat.RichText)

    # ── Export PNG ────────────────────────────────────────────────────────────

    def _export_png(self):
        if not os.path.exists(self.current_img_path):
            QMessageBox.warning(self, "Sin volcado",
                                "El retrato no existe en la carpeta de volcados.\n"
                                "Ejecuta el volcado global desde el menú principal primero.")
            return
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar PNG", f"{self.npc_name}_Portrait.png", "Images (*.png)"
        )
        if save_path:
            try:
                shutil.copy2(self.current_img_path, save_path)
                QMessageBox.information(self, "Éxito", f"Retrato guardado en:\n{save_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{e}")

    # ── Import PNG → Repack ───────────────────────────────────────────────────

    def _import_png(self):
        from PIL import Image as _PilImage
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar PNG Modificado", "", "Images (*.png)"
        )
        if not file_path:
            return

        # Si el checkbox Vanilla está activado usamos vanilla (retoque rápido),
        # de lo contrario SIEMPRE usamos Expansión para garantizar que f0 se actualice.
        use_vanilla    = self.chk_vanilla.isChecked()
        force_exp      = not use_vanilla          # Expansión = default seguro
        has_custom_pal = self._edited_palette is not None

        try:
            with _PilImage.open(file_path) as _img:
                png_w, png_h = _img.size
        except Exception:
            png_w, png_h = 0, 0

        modo_txt = (
            "<b style='color:#FAB387;'>Vainilla</b> — retoque rápido, OAMs intactos"
            if use_vanilla else
            "<b style='color:#A6E3A1;'>Expansión</b> — recalcula OAMs y actualiza metadata"
        )

        msg = (
            f"<b>Melody Engine</b> va a compilar el PNG a <b>GBA 4bpp</b>,"
            f" generar los atributos OAM y relocalizar las tablas maestras.<br><br>"
            f"<b>Modo:</b> {modo_txt}<br>"
            f"<b>PNG:</b> {png_w}×{png_h} px<br>"
            f"<b>Paleta:</b> {'<b style=\'color:#CBA6F7;\'>PERSONALIZADA</b>' if has_custom_pal else 'Original de la ROM'}<br><br>"
            "¿Continuar?"
        )
        reply = QMessageBox.question(
            self, "Confirmar Inyección", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            sys.path.insert(0, r'j:\Repositorios\fomt_studio')
            from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.Melody_Portrait_Engine.repack_portraits import repack

            rom_data = None
            if self.project and hasattr(self.project, 'base_rom_data') and self.project.base_rom_data:
                rom_data = self.project.base_rom_data

            new_rom = repack(
                target_portrait_hex=self.hex_id,
                input_png_path=file_path,
                force_expansion=force_exp,         # True por defecto (Expansión)
                custom_palette=self._edited_palette,
                rom_data=rom_data
            )

            if self.project:
                self.project.base_rom_data = bytes(new_rom)
                if hasattr(self.project, 'virtual_rom'):
                    self.project.virtual_rom = bytearray(new_rom)
                
                with open(self.rom_path, 'wb') as f:
                    f.write(new_rom)
                self.project.unsaved_changes = True

            self._refresh_preview()
            modo_ok = "Vainilla (in-place)" if use_vanilla else "Expansión (metadata actualizada)"
            QMessageBox.information(
                self, "Inyección Exitosa",
                f"¡Portrait reinyectado correctamente! [{modo_ok}]\n\n"
                "• OAMs y metadata actualizados.\n"
                "• Tablas relocalizadas al espacio libre.\n"
                + ("• Paleta personalizada aplicada." if has_custom_pal else "")
            )

        except Exception as e:
            QMessageBox.critical(
                self, "Error de Inyección",
                f"Error crítico durante la recompresión:\n{e}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Mini palette strip (visor de 16 swatches en una fila)
# ─────────────────────────────────────────────────────────────────────────────

class _PaletteStrip(QLabel):
    """Strip horizontal de 16 swatches de 12×12 px para el visor del portrait."""

    SZ = 14

    def __init__(self, palette, parent=None):
        super().__init__(parent)
        self._palette = list(palette)
        self.setFixedHeight(self.SZ + 4)
        self.setMinimumWidth(self.SZ * 16 + 4)
        self.setToolTip("Paleta actual del portrait (16 colores GBA)\nSlot 0 = transparente")
        self._draw()

    def set_palette(self, palette):
        self._palette = list(palette)
        self._draw()

    def _draw(self):
        from PyQt6.QtGui import QPainter, QColor
        from PyQt6.QtCore import QRect
        w = self.SZ * 16 + 4
        h = self.SZ + 4
        pix = QPixmap(w, h)
        pix.fill(QColor(17, 17, 27))
        p = QPainter(pix)
        for i, (r, g, b) in enumerate(self._palette[:16]):
            x = 2 + i * self.SZ
            y = 2
            if i == 0:
                p.fillRect(x, y, self.SZ, self.SZ, QColor(180, 180, 180))
                p.fillRect(x, y, self.SZ // 2, self.SZ // 2, QColor(255, 255, 255))
                p.fillRect(x + self.SZ // 2, y + self.SZ // 2,
                           self.SZ // 2, self.SZ // 2, QColor(255, 255, 255))
            else:
                p.fillRect(x, y, self.SZ, self.SZ, QColor(r, g, b))
        p.end()
        self.setPixmap(pix)
