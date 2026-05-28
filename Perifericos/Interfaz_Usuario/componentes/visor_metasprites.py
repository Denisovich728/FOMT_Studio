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
from PyQt6.QtGui import QPixmap, QColor, QBrush, QPen, QImage, QPainter

from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.metasprites import PortraitCompiler
from Nucleos_de_Procesamiento.Nucleo_de_Datos.Utilidades.rutas import get_data_path, get_resource_path
from Perifericos.Interfaz_Usuario.componentes.visor_sprites import pil_to_qpixmap
import Nucleos_de_Procesamiento.Nucleo_de_Imagenes.Melody_Portrait_Engine.repack_portraits as rp

# Mapeo de paletas cargado dinámicamente o estático
with open(get_resource_path(os.path.join('Nucleos_de_Procesamiento', 'Cilixes', 'fomt', 'portrait_palettes.json')), 'r') as f:
    PORTRAIT_PALETTES = json.load(f)

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
        
        self.image = QImage(256, 256, QImage.Format.Format_ARGB32)
        self.image.fill(Qt.GlobalColor.transparent)
        
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        
        self.current_tool = "brush" # brush, eyedropper, eraser
        self.current_color = QColor(255, 255, 255)
        self.parent_visor = None
        self.is_painting = False

    def load_image(self, filepath):
        if os.path.exists(filepath):
            self.image = QImage(filepath).convertToFormat(QImage.Format.Format_ARGB32)
            self.update_pixmap()
            self.scene.setSceneRect(0, 0, self.image.width(), self.image.height())
            self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def update_pixmap(self):
        self.pixmap_item.setPixmap(QPixmap.fromImage(self.image))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_painting = True
            self.apply_tool(event.position().toPoint())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_painting:
            self.apply_tool(event.position().toPoint())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_painting = False
        super().mouseReleaseEvent(event)

    def apply_tool(self, pos):
        scene_pos = self.mapToScene(pos)
        x, y = int(scene_pos.x()), int(scene_pos.y())
        
        if 0 <= x < self.image.width() and 0 <= y < self.image.height():
            if self.current_tool == "brush":
                self.image.setPixelColor(x, y, self.current_color)
                self.update_pixmap()
            elif self.current_tool == "eraser":
                # Borrador pinta transparente o color 0
                if self.parent_visor and self.parent_visor.palette_colors:
                    transparent_color = self.parent_visor.palette_colors[0]
                    # Transparente total
                    transparent_color.setAlpha(0)
                    self.image.setPixelColor(x, y, transparent_color)
                else:
                    self.image.setPixelColor(x, y, QColor(0,0,0,0))
                self.update_pixmap()
            elif self.current_tool == "eyedropper":
                color = self.image.pixelColor(x, y)
                if color.alpha() > 0:
                    self.current_color = color
                    if self.parent_visor:
                        self.parent_visor.update_current_color_preview()


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
        
        tools_layout.addWidget(self.btn_brush)
        tools_layout.addWidget(self.btn_eraser)
        tools_layout.addWidget(self.btn_eyedropper)
        tools_layout.addStretch()
        
        center_panel.addLayout(tools_layout)
        
        self.canvas = PixelCanvas()
        self.canvas.parent_visor = self
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

        if not os.path.exists(png_path) and self.project and self.project.base_rom_data:
            try:
                import Nucleos_de_Procesamiento.Nucleo_de_Imagenes.Melody_Portrait_Engine.dump_portraits as dp
                counts, ptrs = dp.get_bundle_headers(self.project.base_rom_data)
                dp.dump_single(self.project.base_rom_data, self.current_hex_id, name, dump_dir, counts, ptrs)
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
        if str(decimal_id) in PORTRAIT_PALETTES:
            offset_str = PORTRAIT_PALETTES[str(decimal_id)]
            offset = int(offset_str, 16) & 0x01FFFFFF
            
            if self.project and self.project.base_rom_data:
                rom = self.project.base_rom_data
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
                        
                # Auto select first color
                self._select_palette_color(1)
        else:
            # Reset
            for btn in self.pal_buttons:
                btn.setStyleSheet("background-color: #000; border: 1px solid #555;")

    def _select_palette_color(self, idx):
        if idx < len(self.palette_colors):
            self.canvas.current_color = self.palette_colors[idx]
            self.update_current_color_preview()
            self._set_tool("brush")

    def update_current_color_preview(self):
        c = self.canvas.current_color
        self.lbl_color_preview.setStyleSheet(f"background-color: rgb({c.red()},{c.green()},{c.blue()}); border: 2px solid white;")

    def _import_png(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Importar PNG", "", "Images (*.png)")
        if file_path:
            self.canvas.load_image(file_path)

    def _export_png(self):
        save_path, _ = QFileDialog.getSaveFileName(self, "Exportar PNG", f"dump_{self.current_hex_id:02X}.png", "Images (*.png)")
        if save_path:
            self.canvas.image.save(save_path)
            QMessageBox.information(self, "Éxito", "PNG guardado correctamente.")

    def _dump_all_portraits(self):
        if not self.project or not self.project.base_rom_data:
            QMessageBox.warning(self, "Error", "Debes tener un ROM cargado en el proyecto.")
            return
            
        reply = QMessageBox.question(self, "Extraer Retratos", 
            "Esto extraerá los 184 retratos del ROM a la carpeta 'portraits_dump'.\n\n¿Deseas continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
        if reply == QMessageBox.StandardButton.Yes:
            try:
                import Nucleos_de_Procesamiento.Nucleo_de_Imagenes.Melody_Portrait_Engine.dump_portraits as dp
                
                # Escribimos el rom en un archivo temporal si no tenemos la ruta a source
                rom_path = getattr(self.project, 'base_rom_path', 'temp_rom.gba')
                if not os.path.exists(rom_path):
                    with open(rom_path, 'wb') as f:
                        f.write(self.project.base_rom_data)
                        
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
            
        reply = QMessageBox.question(self, "Inyectar Portrait", 
            "Melody Engine va a compilar los tiles 4bpp, generar sus atributos OAM "
            "y empujar las tablas (Shifting) para inyectar este Portrait en la ROM.\n\n¿Deseas continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
        if reply == QMessageBox.StandardButton.Yes:
            try:
                import sys
                import importlib
                importlib.reload(rp)
                
                # Guardar PNG temporal
                temp_path = os.path.join(os.getcwd(), "portraits_dump", "temp_inject.png")
                self.canvas.image.save(temp_path)
                
                # Inyectar
                rom_data = None
                if self.project and self.project.base_rom_data:
                    rom_data = self.project.base_rom_data
                    
                new_rom = rp.repack(
                    self.current_hex_id, 
                    temp_path, 
                    rom_data, 
                    custom_palette=getattr(self, 'edited_palette', None)
                )
                
                if self.project:
                    # Aplicar a la memoria
                    self.project.base_rom_data = bytes(new_rom)
                    if hasattr(self.project, 'virtual_rom'):
                        self.project.virtual_rom = bytearray(new_rom)
                    
                    # Sobrescribir físicamente la ROM del proyecto (source.gba)
                    with open(self.project.base_rom_path, "wb") as f:
                        f.write(new_rom)
                        
                    self.project.unsaved_changes = True
                    QMessageBox.information(self, "Éxito", "¡Retrato reinyectado!\n\nLos cambios se han guardado permanentemente en la ROM del proyecto. Puedes compilarla para verlos en tu emulador.")
                else:
                    QMessageBox.information(self, "Éxito", "¡Retrato reinyectado correctamente usando empuje dinámico!\nRecarga la ROM para ver los cambios.")
            except Exception as e:
                QMessageBox.critical(self, "Error Fatal", f"Falló la inyección:\n{e}")

    def _open_palette_editor(self):
        if self.current_hex_id is None:
            QMessageBox.warning(self, "Error", "Selecciona un retrato primero.")
            return
        
        from Perifericos.Interfaz_Usuario.widgets.palette_editor import PaletteEditorDialog
        
        # Convert QColor objects to RGB tuples
        rgb_colors = []
        for qc in self.palette_colors:
            rgb_colors.append((qc.red(), qc.green(), qc.blue()))
            
        dlg = PaletteEditorDialog(rgb_colors, parent=self)
        if dlg.exec():
            new_pal = dlg.get_palette()
            # Update palette in memory
            self.palette_colors = [QColor(r, g, b) for r, g, b in new_pal]
            # Update UI buttons
            for i, qc in enumerate(self.palette_colors):
                btn = self.pal_buttons[i]
                r, g, b = qc.red(), qc.green(), qc.blue()
                btn.setStyleSheet(f"background-color: rgb({r},{g},{b}); border: 1px solid #555;")
            self._select_palette_color(1)
            self.edited_palette = new_pal
