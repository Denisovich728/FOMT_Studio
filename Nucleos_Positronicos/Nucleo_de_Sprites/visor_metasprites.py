# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.7.0)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
import os
import csv
import struct
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, 
    QLabel, QPushButton, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QGroupBox, QFormLayout, QSpinBox, QMessageBox, QLineEdit, QFileDialog, QGridLayout, QFrame
)
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPixmap, QColor, QBrush, QPen, QImage, QPainter, QShortcut, QKeySequence

from Nucleos_Positronicos.Nucleo_de_Sprites.metasprites import PortraitCompiler
from Banco_de_Datos.Utilidades.rutas import get_data_path, get_resource_path
from Nucleos_Positronicos.Nucleo_de_Sprites.visor_sprites import pil_to_qpixmap
import Nucleos_Positronicos.Nucleo_de_Portraits.Melody_Portrait_Engine.repack_portraits as rp

# Mapeo de paletas cargado dinámicamente
PORTRAIT_PALETTES = {}

def decode_gba_color(color16):
    r = (color16 & 0x1F) << 3
    g = ((color16 >> 5) & 0x1F) << 3
    b = ((color16 >> 10) & 0x1F) << 3
    return QColor(r, g, b)

class PixelCanvas(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setBackgroundBrush(QBrush(QColor("#1A1A2E")))
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        
        self.image = QImage(256, 256, QImage.Format.Format_Indexed8)
        self.image.setColorCount(16)
        self.image.fill(0)
        
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        
        self.current_tool = "brush" # brush, eyedropper, eraser, fill
        self.current_color = QColor(255, 255, 255)
        self.current_color_idx = 1
        self.brush_size = 1
        self.parent_visor = None
        self.is_painting = False
        
        self.undo_stack = []
        self.redo_stack = []
        self.max_history = 30
        
        self.snapshot_image = self.image.copy()
        self.old_colors_for_live = []

    def _update_snapshot(self):
        self.snapshot_image = self.image.copy()
        if self.parent_visor:
            self.old_colors_for_live = list(self.parent_visor.palette_colors)

    def _save_state(self):
        self.undo_stack.append(self.image.copy())
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.image.copy())
            self.image = self.undo_stack.pop()
            self.update_pixmap()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.image.copy())
            self.image = self.redo_stack.pop()
            self.update_pixmap()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            zoom_in = event.angleDelta().y() > 0
            factor = 1.25 if zoom_in else 0.8
            self.scale(factor, factor)
        else:
            super().wheelEvent(event)

    def load_image(self, filepath):
        if os.path.exists(filepath):
            img = QImage(filepath)
            if img.format() != QImage.Format.Format_Indexed8:
                img = img.convertToFormat(QImage.Format.Format_Indexed8)
            self.image = img
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.update_pixmap()
            self.scene.setSceneRect(0, 0, self.image.width(), self.image.height())
            self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def update_pixmap(self):
        self.pixmap_item.setPixmap(QPixmap.fromImage(self.image))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._save_state()
            self.is_painting = True
            self.apply_tool(event.position().toPoint())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_painting and self.current_tool != "fill":
            self.apply_tool(event.position().toPoint())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_painting = False
            self._update_snapshot()
        super().mouseReleaseEvent(event)

    def apply_tool(self, pos):
        scene_pos = self.mapToScene(pos)
        x, y = int(scene_pos.x()), int(scene_pos.y())
        
        w, h = self.image.width(), self.image.height()
        if not (0 <= x < w and 0 <= y < h):
            return

        if self.current_tool in ("brush", "eraser"):
            idx = self.current_color_idx
            if self.current_tool == "eraser":
                idx = 0

            offset = self.brush_size // 2
            for dy in range(self.brush_size):
                for dx in range(self.brush_size):
                    px = x - offset + dx
                    py = y - offset + dy
                    if 0 <= px < w and 0 <= py < h:
                        self.image.setPixel(px, py, idx)
            self.update_pixmap()

        elif self.current_tool == "fill":
            target_idx = self.image.pixelIndex(x, y)
            fill_idx = self.current_color_idx
            
            if target_idx == fill_idx:
                return
                
            stack = [(x, y)]
            while stack:
                cx, cy = stack.pop()
                if self.image.pixelIndex(cx, cy) == target_idx:
                    self.image.setPixel(cx, cy, fill_idx)
                    if cx > 0: stack.append((cx - 1, cy))
                    if cx < w - 1: stack.append((cx + 1, cy))
                    if cy > 0: stack.append((cx, cy - 1))
                    if cy < h - 1: stack.append((cx, cy + 1))
            self.update_pixmap()

        elif self.current_tool == "eyedropper":
            idx = self.image.pixelIndex(x, y)
            if idx > 0:
                if self.parent_visor:
                    self.parent_visor._select_palette_color(idx)


class VisorMetasprites(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.project = None
        self.current_hex_id = None
        self.palette_colors = []
        
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        
        # --- Panel Izquierdo: Lista de Retratos ---
        left_panel = QVBoxLayout()
        
        self.lbl_title = QLabel("🖼 Tile Editor Extreme (Portraits)")
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #00BFFF;")
        left_panel.addWidget(self.lbl_title)
        
        self.list_portraits = QListWidget()
        self.list_portraits.setStyleSheet("""
            QListWidget {
                background: #0D0D12; color: white;
                border: 1px solid #2A2A35;
            }
            QListWidget::item:selected { background: #00BFFF; color: black; }
        """)
        self.list_portraits.itemSelectionChanged.connect(self._on_portrait_selected)
        
        left_panel.addWidget(QLabel("Selecciona un Retrato:"))
        left_panel.addWidget(self.list_portraits)
        
        layout.addLayout(left_panel, 1)
        
        # --- Panel Central: Pixel Art Canvas ---
        center_panel = QVBoxLayout()
        
        # Herramientas
        tools_layout = QHBoxLayout()
        
        self.canvas = PixelCanvas()
        self.canvas.parent_visor = self
        
        self.btn_brush = QPushButton("🖌 Pincel")
        self.btn_brush.setCheckable(True)
        self.btn_brush.setChecked(True)
        self.btn_brush.clicked.connect(lambda: self._set_tool("brush"))
        
        self.btn_eraser = QPushButton("🧹 Borrador")
        self.btn_eraser.setCheckable(True)
        self.btn_eraser.clicked.connect(lambda: self._set_tool("eraser"))
        
        self.btn_eyedropper = QPushButton("💧 Gotero")
        self.btn_eyedropper.setCheckable(True)
        self.btn_eyedropper.clicked.connect(lambda: self._set_tool("eyedropper"))
        
        self.btn_fill = QPushButton("🪣 Cubeta")
        self.btn_fill.setCheckable(True)
        self.btn_fill.clicked.connect(lambda: self._set_tool("fill"))
        
        lbl_size = QLabel("Grosor:")
        self.spin_size = QSpinBox()
        self.spin_size.setRange(1, 16)
        self.spin_size.setValue(1)
        self.spin_size.valueChanged.connect(self._set_brush_size)
        
        self.btn_undo = QPushButton("↩ Deshacer")
        self.btn_undo.clicked.connect(self.canvas.undo)
        
        self.btn_redo = QPushButton("↪ Rehacer")
        self.btn_redo.clicked.connect(self.canvas.redo)
        
        self.btn_zoom_in = QPushButton("🔍+")
        self.btn_zoom_in.clicked.connect(lambda: self.canvas.scale(1.25, 1.25))
        
        self.btn_zoom_out = QPushButton("🔍-")
        self.btn_zoom_out.clicked.connect(lambda: self.canvas.scale(0.8, 0.8))
        
        tools_layout.addWidget(self.btn_brush)
        tools_layout.addWidget(self.btn_eraser)
        tools_layout.addWidget(self.btn_eyedropper)
        tools_layout.addWidget(self.btn_fill)
        tools_layout.addWidget(lbl_size)
        tools_layout.addWidget(self.spin_size)
        tools_layout.addStretch()
        tools_layout.addWidget(self.btn_undo)
        tools_layout.addWidget(self.btn_redo)
        tools_layout.addWidget(self.btn_zoom_in)
        tools_layout.addWidget(self.btn_zoom_out)
        
        center_panel.addLayout(tools_layout)
        
        # Shortcuts
        self.shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.shortcut_undo.activated.connect(self.canvas.undo)
        
        self.shortcut_redo = QShortcut(QKeySequence("Ctrl+Y"), self)
        self.shortcut_redo.activated.connect(self.canvas.redo)
        
        center_panel.addWidget(self.canvas, 3)
        
        # Botones de Acción
        action_layout = QHBoxLayout()
        
        self.btn_import = QPushButton("📂 Importar PNG")
        self.btn_import.clicked.connect(self._import_png)
        
        self.btn_export = QPushButton("💾 Dumpear PNG actual")
        self.btn_export.clicked.connect(self._export_png)

        self.btn_dump_all = QPushButton("📥 Extraer Todos los Retratos")
        self.btn_dump_all.setStyleSheet("background: #007ACC; color: white; font-weight: bold;")
        self.btn_dump_all.clicked.connect(self._dump_all_portraits)
        
        self.btn_inject = QPushButton("🚀 Inyectar (Melody Engine)")
        self.btn_inject.setStyleSheet("background: #d32f2f; color: white; font-weight: bold;")
        self.btn_inject.clicked.connect(self._inject_to_rom)
        
        action_layout.addWidget(self.btn_import)
        action_layout.addWidget(self.btn_export)
        action_layout.addWidget(self.btn_dump_all)
        action_layout.addWidget(self.btn_inject)
        
        center_panel.addLayout(action_layout)
        layout.addLayout(center_panel, 3)
        
        # --- Panel Derecho: Paleta de 16 Colores ---
        right_panel = QVBoxLayout()
        
        lbl_pal = QLabel("<b>Paleta de Colores ROM</b>")
        lbl_pal.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_panel.addWidget(lbl_pal)
        
        self.pal_grid = QGridLayout()
        self.pal_buttons = []
        
        for i in range(16):
            btn = QPushButton()
            btn.setFixedSize(32, 32)
            btn.setStyleSheet("background-color: #000000; border: 1px solid #555;")
            btn.clicked.connect(lambda checked, idx=i: self._select_palette_color(idx))
            self.pal_buttons.append(btn)
            self.pal_grid.addWidget(btn, i // 4, i % 4)
            
        right_panel.addLayout(self.pal_grid)
        
        self.btn_edit_pal = QPushButton("🎨 Editar Paleta")
        self.btn_edit_pal.setStyleSheet("background: #1F3A5F; color: #89B4FA; font-weight: bold; border-color: #4A90D9;")
        self.btn_edit_pal.clicked.connect(self._open_palette_editor)
        right_panel.addWidget(self.btn_edit_pal)
        
        self.lbl_color_preview = QLabel()
        self.lbl_color_preview.setFixedSize(64, 64)
        self.lbl_color_preview.setStyleSheet("background-color: #FFFFFF; border: 2px solid white;")
        right_panel.addWidget(QLabel("Color Actual:"))
        right_panel.addWidget(self.lbl_color_preview)
        
        right_panel.addStretch()
        layout.addLayout(right_panel, 1)

    def set_project(self, project):
        self.project = project
        self._load_csv()

    def _load_csv(self):
        self.list_portraits.clear()
        csv_path = get_data_path("fomt", "Fomt_Portraits.csv")
        if os.path.exists(csv_path):
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None) # skip header
                for row in reader:
                    if len(row) >= 2:
                        item = QListWidgetItem(row[0])
                        item.setData(Qt.ItemDataRole.UserRole, row[1].strip()) # Hex ID
                        self.list_portraits.addItem(item)

    def _set_tool(self, tool_name):
        self.canvas.current_tool = tool_name
        self.btn_brush.setChecked(tool_name == "brush")
        self.btn_eraser.setChecked(tool_name == "eraser")
        self.btn_eyedropper.setChecked(tool_name == "eyedropper")
        self.btn_fill.setChecked(tool_name == "fill")

    def _set_brush_size(self, size):
        self.canvas.brush_size = size

    def _on_portrait_selected(self):
        self.edited_palette = None
        selected = self.list_portraits.selectedItems()
        if not selected: return
        
        item = selected[0]
        hex_id_str = item.data(Qt.ItemDataRole.UserRole)
        name = item.text()
        
        self.current_hex_id = int(hex_id_str, 16)
        
        # Cargar PNG
        dump_dir = os.path.join(os.getcwd(), "portraits_dump")
        if self.project and hasattr(self.project, 'project_dir') and self.project.project_dir:
            dump_dir = os.path.join(self.project.project_dir, "portraits_dump")

        png_path = os.path.join(dump_dir, f"{hex_id_str}_{name}.png")

        if not os.path.exists(png_path) and self.project and (hasattr(self.project, 'virtual_rom') or self.project.base_rom_data):
            try:
                current_rom = bytes(self.project.virtual_rom) if hasattr(self.project, 'virtual_rom') and self.project.virtual_rom else self.project.base_rom_data
                import Nucleos_Positronicos.Nucleo_de_Portraits.Melody_Portrait_Engine.dump_portraits as dp
                counts, ptrs = dp.get_bundle_headers(current_rom)
                dp.dump_single(current_rom, self.current_hex_id, name, dump_dir, counts, ptrs)
            except Exception as e:
                print(f"Error dumpeando retrato al vuelo: {e}")

        if os.path.exists(png_path):
            self.canvas.load_image(png_path)
        else:
            # Clear canvas
            self.canvas.image.fill(Qt.GlobalColor.transparent)
            self.canvas.update_pixmap()
            
        # Cargar Paleta
        self._load_palette_from_rom(self.current_hex_id)

    def _load_palette_from_rom(self, decimal_id):
        self.palette_colors = []
        if self.project and (hasattr(self.project, 'virtual_rom') or self.project.base_rom_data):
            rom = bytes(self.project.virtual_rom) if hasattr(self.project, 'virtual_rom') and self.project.virtual_rom else self.project.base_rom_data
            offset = None
            try:
                import Nucleos_Positronicos.Nucleo_de_Portraits.Melody_Portrait_Engine.dump_portraits as dp
                counts, ptrs = dp.get_bundle_headers(rom)
                if decimal_id < counts[0]:
                    idx = dp.read_hword(rom, ptrs[0] + decimal_id * 4 + 2)
                    if idx < counts[1]:
                        struct_base = ptrs[1] + idx * 16
                        fA = dp.read_hword(rom, struct_base + 0xA)
                        ptr_PAL = ptrs[4] + fA * 32
                        offset = ptr_PAL - 0x08000000
            except Exception as e:
                print(f"Error resolviendo paleta dinamica: {e}")
                
            # Fallback a diccionario estático si falló la resolución dinámica o la ROM es vainilla sin expandir
            if offset is None and str(decimal_id) in PORTRAIT_PALETTES:
                offset_str = PORTRAIT_PALETTES[str(decimal_id)]
                offset = int(offset_str, 16) & 0x01FFFFFF
                
            if offset is not None:
                for i in range(16):
                    addr = offset + (i * 2)
                    if addr + 2 <= len(rom):
                        color16 = struct.unpack('<H', rom[addr:addr+2])[0]
                        qcolor = decode_gba_color(color16)
                        self.palette_colors.append(qcolor)
                        
                        # Actualizar botón UI
                        btn = self.pal_buttons[i]
                        r, g, b = qcolor.red(), qcolor.green(), qcolor.blue()
                        btn.setStyleSheet(f"background-color: rgb({r},{g},{b}); border: 1px solid #555;")
                        
                # Enforce Canvas Color Table
                c0 = QColor(self.palette_colors[0])
                c0.setAlpha(0)
                color_table = [c0.rgba()] + [c.rgba() for c in self.palette_colors[1:]]
                while len(color_table) < 256:
                    color_table.append(0)
                self.canvas.image.setColorTable(color_table)
                self.canvas.update_pixmap()
                self.canvas._update_snapshot()
                        
                # Auto select first color
                self._select_palette_color(1)
                return
                
        # Reset (if completely failed or no ROM)
        for btn in self.pal_buttons:
            btn.setStyleSheet("background-color: #000; border: 1px solid #555;")

    def _select_palette_color(self, idx):
        if idx < len(self.palette_colors):
            self.canvas.current_color = self.palette_colors[idx]
            self.canvas.current_color_idx = idx
            self.update_current_color_preview()
            self._set_tool("brush")

    def update_current_color_preview(self):
        c = self.canvas.current_color
        self.lbl_color_preview.setStyleSheet(f"background-color: rgb({c.red()},{c.green()},{c.blue()}); border: 2px solid white;")

    def _import_png(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Importar PNG", "", "Images (*.png)")
        if file_path:
            self.canvas.load_image(file_path)
            self._extract_palette_from_image()

    def _extract_palette_from_image(self):
        img = self.canvas.image
        w, h = img.width(), img.height()
        
        unique_colors = []
        for y in range(h):
            for x in range(w):
                px = img.pixelColor(x, y)
                if px.alpha() >= 128:
                    # Cuantizar a espacio de color GBA (15-bit) para evitar falsos duplicados
                    r = (px.red() >> 3) << 3
                    g = (px.green() >> 3) << 3
                    b = (px.blue() >> 3) << 3
                    qc = QColor(r, g, b)
                    
                    if not any(c.rgb() == qc.rgb() for c in unique_colors):
                        unique_colors.append(qc)
                        
        if len(unique_colors) > 15:
            QMessageBox.warning(self, "Demasiados Colores", 
                                f"El PNG tiene {len(unique_colors)} colores detectados.\n\nLa GBA solo soporta 15 colores opacos + 1 transparente. La paleta se truncará, lo que causará pérdida de color al inyectar.")
            unique_colors = unique_colors[:15]
            
        new_pal = [QColor(0, 255, 0)] # Transparente default
        if len(self.palette_colors) > 0:
            new_pal[0] = self.palette_colors[0]
            
        new_pal.extend(unique_colors)
        
        while len(new_pal) < 16:
            new_pal.append(QColor(0, 0, 0))
            
        self.palette_colors = new_pal
        self.edited_palette = [(c.red(), c.green(), c.blue()) for c in new_pal]
        
        for i, qc in enumerate(self.palette_colors):
            btn = self.pal_buttons[i]
            btn.setStyleSheet(f"background-color: rgb({qc.red()},{qc.green()},{qc.blue()}); border: 1px solid #555;")
            
        # Re-map the imported image to our strict 16-color table indices
        new_image = QImage(w, h, QImage.Format.Format_Indexed8)
        new_image.setColorCount(16)
        new_image.fill(0)
        
        c0 = QColor(self.palette_colors[0])
        c0.setAlpha(0)
        color_table = [c0.rgba()] + [c.rgba() for c in self.palette_colors[1:]]
        while len(color_table) < 256:
            color_table.append(0)
        new_image.setColorTable(color_table)
        
        for y in range(h):
            for x in range(w):
                px = img.pixelColor(x, y)
                if px.alpha() >= 128:
                    r, g, b = (px.red()>>3)<<3, (px.green()>>3)<<3, (px.blue()>>3)<<3
                    best_idx = 1
                    best_dist = float('inf')
                    for i, pc in enumerate(self.palette_colors):
                        if i == 0: continue
                        d = (r - pc.red())**2 + (g - pc.green())**2 + (b - pc.blue())**2
                        if d < best_dist:
                            best_dist = d
                            best_idx = i
                    new_image.setPixel(x, y, best_idx)
                    
        self.canvas.image = new_image
        self.canvas.update_pixmap()
        self.canvas._update_snapshot()
        
        self._select_palette_color(1)

    def _export_png(self):
        save_path, _ = QFileDialog.getSaveFileName(self, "Exportar PNG", f"dump_{self.current_hex_id:02X}.png", "Images (*.png)")
        if save_path:
            self.canvas.image.save(save_path)
            QMessageBox.information(self, "Éxito", "PNG guardado correctamente.")

    def _dump_all_portraits(self):
        if not self.project or (not hasattr(self.project, 'virtual_rom') and not self.project.base_rom_data):
            QMessageBox.warning(self, "Error", "Debes tener un ROM cargado en el proyecto.")
            return
            
        reply = QMessageBox.question(self, "Extraer Retratos", 
            "Esto extraerá los 184 retratos del ROM a la carpeta 'portraits_dump'.\n\n¿Deseas continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
        if reply == QMessageBox.StandardButton.Yes:
            try:
                import Nucleos_Positronicos.Nucleo_de_Portraits.Melody_Portrait_Engine.dump_portraits as dp
                
                # Usamos el rom actual (virtual_rom si existe) en un archivo temporal si no tenemos la ruta a source
                rom_path = getattr(self.project, 'base_rom_path', 'temp_rom.gba')
                current_rom = bytes(self.project.virtual_rom) if hasattr(self.project, 'virtual_rom') and self.project.virtual_rom else self.project.base_rom_data
                if not os.path.exists(rom_path) or current_rom != self.project.base_rom_data:
                    with open("temp_rom.gba", 'wb') as f:
                        f.write(current_rom)
                    rom_path = "temp_rom.gba"
                        
                csv_path = get_data_path("fomt", "Fomt_Portraits.csv")
                out_dir = os.path.join(os.getcwd(), "portraits_dump")
                
                dp.dump_all(rom_path, csv_path, out_dir)
                
                QMessageBox.information(self, "Éxito", f"¡Retratos extraídos en la carpeta:\n{out_dir}")
                
                # Refrescar portrait actual si hay uno
                if self.current_hex_id is not None:
                    self._on_portrait_selected()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Fallo al extraer retratos:\n{e}")

    def _inject_to_rom(self):
        if self.current_hex_id is None:
            QMessageBox.warning(self, "Error", "Selecciona un retrato primero.")
            return
            
        fork_palette = False
        if getattr(self, 'edited_palette', None):
            msg = QMessageBox(self)
            msg.setWindowTitle("Modo de Paleta")
            msg.setText("Has editado la paleta. ¿Cómo deseas guardarla?\n\n"
                        "• Global: Afectará a este retrato y a todos los que compartan esta paleta (ej. otras expresiones del personaje).\n"
                        "• Desvincular: Creará una paleta única exclusiva para este retrato.")
            btn_global = msg.addButton("Aplicar a TODOS (Global)", QMessageBox.ButtonRole.AcceptRole)
            btn_unique = msg.addButton("Solo a ESTE (Desvincular)", QMessageBox.ButtonRole.AcceptRole)
            btn_cancel = msg.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
            
            msg.exec()
            
            if msg.clickedButton() == btn_cancel:
                return
            elif msg.clickedButton() == btn_unique:
                fork_palette = True
                
            reply = QMessageBox.StandardButton.Yes
        else:
            reply = QMessageBox.question(self, "Inyectar Portrait", 
                "Melody Engine va a compilar los tiles 4bpp, generar sus atributos OAM "
                "y empujar las tablas (Shifting) para inyectar este Portrait en la ROM.\n\n¿Deseas continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
        if reply == QMessageBox.StandardButton.Yes:
            try:
                import sys
                import importlib
                importlib.reload(rp)
                
                # Definir directorios correctos
                dump_dir = os.path.join(os.getcwd(), "portraits_dump")
                if self.project and hasattr(self.project, 'project_dir') and self.project.project_dir:
                    dump_dir = os.path.join(self.project.project_dir, "portraits_dump")
                
                os.makedirs(dump_dir, exist_ok=True)
                temp_path = os.path.join(dump_dir, "temp_inject.png")
                self.canvas.image.save(temp_path)
                
                # Inyectar usando la ROM actual (virtual si existe)
                rom_data = None
                if self.project:
                    rom_data = bytes(self.project.virtual_rom) if hasattr(self.project, 'virtual_rom') and self.project.virtual_rom else self.project.base_rom_data
                    
                new_rom = rp.repack(
                    self.current_hex_id, 
                    temp_path, 
                    rom_data, 
                    custom_palette=getattr(self, 'edited_palette', None),
                    fork_palette=fork_palette
                )
                
                if self.project:
                    current_virtual = bytes(self.project.virtual_rom) if hasattr(self.project, 'virtual_rom') and self.project.virtual_rom else self.project.base_rom_data
                    old_rom_len = len(current_virtual)
                    
                    # Generar parche delta
                    for i in range(0, len(new_rom), 4096):
                        chunk_new = new_rom[i:i+4096]
                        chunk_old = current_virtual[i:i+4096] if i < old_rom_len else b'\x00' * len(chunk_new)
                        
                        if chunk_new != chunk_old:
                            start = 0
                            while start < len(chunk_new) and start < len(chunk_old) and chunk_new[start] == chunk_old[start]:
                                start += 1
                            end = len(chunk_new)
                            while end > start and end <= len(chunk_old) and chunk_new[end-1] == chunk_old[end-1]:
                                end -= 1
                                
                            if hasattr(self.project, 'write_patch'):
                                self.project.write_patch(i + start, bytes(chunk_new[start:end]))
                    
                    if hasattr(self.project, 'virtual_rom'):
                        self.project.virtual_rom = bytearray(new_rom)
                        
                    # Limpiar caché de retratos para forzar re-dumpeo con los nuevos datos/paletas
                    import glob
                    for f_path in glob.glob(os.path.join(dump_dir, "*.png")):
                        if "temp_inject" not in f_path:
                            try:
                                os.remove(f_path)
                            except:
                                pass
                                
                    self.project.unsaved_changes = True
                    QMessageBox.information(self, "Éxito", "¡Retrato reinyectado!\n\nLos cambios se han guardado permanentemente en la ROM del proyecto.")
                    
                    # Recargar el retrato actual desde la ROM fresca
                    self._on_portrait_selected()
                else:
                    QMessageBox.information(self, "Éxito", "¡Retrato reinyectado correctamente usando empuje dinámico!\nRecarga la ROM para ver los cambios.")
            except Exception as e:
                QMessageBox.critical(self, "Error Fatal", f"Falló la inyección:\n{e}")

    def _open_palette_editor(self):
        if self.current_hex_id is None:
            QMessageBox.warning(self, "Error", "Selecciona un retrato primero.")
            return
            
        if hasattr(self, '_pal_dlg') and self._pal_dlg.isVisible():
            self._pal_dlg.raise_()
            self._pal_dlg.activateWindow()
            return
        
        from Nucleos_Positronicos.Nucleo_de_Sprites.palette_editor import PaletteEditorDialog
        
        # Convert QColor objects to RGB tuples
        rgb_colors = []
        for qc in self.palette_colors:
            rgb_colors.append((qc.red(), qc.green(), qc.blue()))
            
        self._pal_dlg = PaletteEditorDialog(rgb_colors, parent=self)
        
        orig_colors = list(self.palette_colors)
        self.canvas.old_colors_for_live = list(self.palette_colors)
        self.canvas._update_snapshot()
        
        def on_live_update(new_pal):
            new_qcolors = [QColor(r, g, b) for r, g, b in new_pal]
            
            c0 = QColor(new_qcolors[0])
            c0.setAlpha(0)
            
            color_table = [c0.rgba()] + [c.rgba() for c in new_qcolors[1:]]
            
            # Pad to 256 colors if needed
            while len(color_table) < 256:
                color_table.append(0)
                
            self.canvas.image.setColorTable(color_table)
            self.canvas.update_pixmap()
            
            self.palette_colors = new_qcolors
            for i, qc in enumerate(self.palette_colors):
                btn = self.pal_buttons[i]
                btn.setStyleSheet(f"background-color: rgb({qc.red()},{qc.green()},{qc.blue()}); border: 1px solid #555;")
            
            # Actualizar el color actual del pincel para que coincida con la nueva paleta
            idx = self.canvas.current_color_idx
            if idx < len(new_qcolors):
                self.canvas.current_color = new_qcolors[idx]
                self.update_current_color_preview()
                    
            self.canvas._update_snapshot()

        def on_accepted(new_pal):
            self.edited_palette = new_pal
            self.canvas._update_snapshot()
            
        def on_rejected():
            on_live_update([(c.red(), c.green(), c.blue()) for c in orig_colors])

        self._pal_dlg.palette_changed_live.connect(on_live_update)
        self._pal_dlg.palette_accepted.connect(on_accepted)
        self._pal_dlg.rejected.connect(on_rejected)
        
        self._pal_dlg.show()
