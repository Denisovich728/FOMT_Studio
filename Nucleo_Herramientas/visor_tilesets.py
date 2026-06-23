import os
import sys
from PIL import Image
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QComboBox, QMessageBox, QFileDialog, QScrollArea, QFrame)
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor, QPen
from PyQt6.QtCore import Qt

class VisorTilesetsWidget(QWidget):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.tileset_pointers = [] # lista de (ptr, map_id_referencia)
        self.current_img = None
        self._setup_ui()
        self._load_tileset_list()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Cabecera
        h_header = QHBoxLayout()
        self.cmb_tilesets = QComboBox()
        self.cmb_tilesets.currentIndexChanged.connect(self._render_current_tileset)
        
        self.cmb_palette = QComboBox()
        self.cmb_palette.addItems([f"Sub-Paleta {i}" for i in range(16)])
        self.cmb_palette.currentIndexChanged.connect(self._render_current_tileset)
        
        h_header.addWidget(QLabel("Tileset (Puntero GFX):"))
        h_header.addWidget(self.cmb_tilesets, 1)
        h_header.addWidget(QLabel("Paleta Preview:"))
        h_header.addWidget(self.cmb_palette)
        
        # Botones
        self.btn_export = QPushButton("⬇ Exportar a PNG")
        self.btn_export.clicked.connect(self._export_png)
        
        self.btn_import = QPushButton("⬆ Importar PNG")
        self.btn_import.clicked.connect(self._import_png)
        
        self.btn_inject = QPushButton("💉 Reinsertar Dinámico")
        self.btn_inject.clicked.connect(self._inject_tileset)
        self.btn_inject.setStyleSheet("background-color: #A31515; color: white; font-weight: bold;")
        
        h_header.addWidget(self.btn_export)
        h_header.addWidget(self.btn_import)
        h_header.addWidget(self.btn_inject)
        
        layout.addLayout(h_header)
        
        # Visor Gráfico
        self.scroll_area = QScrollArea()
        self.lbl_image = QLabel()
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.lbl_image.setStyleSheet("background-color: #11111B;")
        self.scroll_area.setWidget(self.lbl_image)
        self.scroll_area.setWidgetResizable(True)
        
        layout.addWidget(self.scroll_area, 1)
        
    def _load_tileset_list(self):
        if not self.project or not self.project.base_rom_data: return
        
        seen_ptrs = set()
        self.tileset_pointers.clear()
        
        # Extraer de todos los mapas
        for mh in self.project.map_parser.maps:
            if mh and mh.p_gfx not in seen_ptrs:
                seen_ptrs.add(mh.p_gfx)
                self.tileset_pointers.append((mh.p_gfx, mh.map_id))
                
        self.tileset_pointers.sort(key=lambda x: x[0])
        
        self.cmb_tilesets.blockSignals(True)
        self.cmb_tilesets.clear()
        for ptr, mid in self.tileset_pointers:
            self.cmb_tilesets.addItem(f"0x{ptr:08X} (usado por Map {mid:03d})")
        self.cmb_tilesets.blockSignals(False)
        self._render_current_tileset()
        
    def _render_current_tileset(self):
        idx = self.cmb_tilesets.currentIndex()
        if idx < 0: return
        
        ptr, mid = self.tileset_pointers[idx]
        
        # Renderizar usando FomtMapRenderer
        from Nucleos_Positronicos.Nucleo_de_Mapas.fomt_mapdata import FomtMapRenderer
        renderer = FomtMapRenderer(self.project.base_rom_data)
        mh = self.project.map_parser.get_map_by_id(mid)
        renderer.load_map(mh)
        
        pal_idx = self.cmb_palette.currentIndex()
        ts_img = renderer.render_tileset(pal_idx=pal_idx, bank=1)
        
        if ts_img:
            self.current_img = ts_img
            img_data = ts_img.convert("RGBA").tobytes("raw", "RGBA")
            qim = QImage(img_data, ts_img.width, ts_img.height, ts_img.width * 4, QImage.Format.Format_RGBA8888)
            pix = QPixmap.fromImage(qim)
            
            # Aplicar Zoom x2 visualmente
            pix = pix.scaled(ts_img.width * 2, ts_img.height * 2, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
            self.lbl_image.setPixmap(pix)
            
    def _export_png(self):
        if not self.current_img: return
        idx = self.cmb_tilesets.currentIndex()
        ptr, _ = self.tileset_pointers[idx]
        
        path, _ = QFileDialog.getSaveFileName(self, "Exportar Tileset", f"tileset_{ptr:08X}.png", "Images (*.png)")
        if path:
            self.current_img.save(path)
            QMessageBox.information(self, "Exportado", "Tileset exportado correctamente.")
            
    def _import_png(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importar Tileset PNG", "", "Images (*.png)")
        if not path: return
        
        try:
            img = Image.open(path).convert("RGBA")
            if img.width != 256:
                QMessageBox.warning(self, "Error de tamaño", "El tileset debe tener 256 píxeles de ancho.")
                return
                
            self.current_img = img
            img_data = img.tobytes("raw", "RGBA")
            qim = QImage(img_data, img.width, img.height, img.width * 4, QImage.Format.Format_RGBA8888)
            pix = QPixmap.fromImage(qim)
            pix = pix.scaled(img.width * 2, img.height * 2, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
            self.lbl_image.setPixmap(pix)
            
            QMessageBox.information(self, "Importado", "Tileset cargado visualmente.\nRevisa que los colores coincidan. Usa 'Reinsertar Dinámico' para inyectarlo en la ROM.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al leer PNG:\n{e}")
            
    def _inject_tileset(self):
        if not self.current_img: return
        
        reply = QMessageBox.question(self, "Confirmar Inyección", 
            "¿Deseas compilar y reinyectar este tileset?\n"
            "El sistema buscará espacio libre, lo inyectará, y repunteará todos los mapas que usan el tileset original.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
        if reply != QMessageBox.StandardButton.Yes: return
        
        # 1. Obtener la paleta actual del mapa referencia para codificar
        idx = self.cmb_tilesets.currentIndex()
        old_ptr, mid = self.tileset_pointers[idx]
        
        from Nucleos_Positronicos.Nucleo_de_Mapas.fomt_mapdata import FomtMapRenderer
        renderer = FomtMapRenderer(self.project.base_rom_data)
        mh = self.project.map_parser.get_map_by_id(mid)
        renderer.load_map(mh)
        
        pal_idx = self.cmb_palette.currentIndex()
        palette = renderer.palettes_1[pal_idx] # RGB tuples
        
        # Mapeo rápido de color RGB -> Índice 4bpp
        def closest_color(r, g, b):
            best_dist = 999999
            best_idx = 0
            for i, (pr, pg, pb) in enumerate(palette):
                dist = (r-pr)**2 + (g-pg)**2 + (b-pb)**2
                if dist < best_dist:
                    best_dist = dist
                    best_idx = i
            return best_idx
            
        # 2. Codificar la imagen a 4bpp
        w, h = self.current_img.size
        pixels = self.current_img.load()
        raw_4bpp = bytearray()
        
        for ty in range(h // 8):
            for tx in range(w // 8):
                # Codificar tile 8x8
                for py in range(8):
                    for px in range(0, 8, 2):
                        cx1, cy1 = tx*8 + px, ty*8 + py
                        cx2, cy2 = cx1 + 1, cy1
                        
                        p1 = pixels[cx1, cy1]
                        p2 = pixels[cx2, cy2]
                        
                        # Transparencia = índice 0, sino buscar el más cercano
                        i1 = 0 if p1[3] < 128 else closest_color(p1[0], p1[1], p1[2])
                        i2 = 0 if p2[3] < 128 else closest_color(p2[0], p2[1], p2[2])
                        
                        raw_4bpp.append((i2 << 4) | i1)
                        
        # 3. Comprimir LZ77 Popuri (0x70)
        sys.path.insert(0, r'j:\Repositorios')
        from Motor_Compresion_Mapas.lz77 import compress_lz77
        
        compressed = bytearray(compress_lz77(raw_4bpp))
        compressed[0] = 0x70 # Popuri Engine Header signature
        
        # 4. Encontrar espacio libre
        free_space = self.project.gestor_memoria._find_free_space(len(compressed))
        if free_space < 0:
            QMessageBox.critical(self, "Error", "No hay espacio libre en la ROM.")
            return
            
        new_ptr = free_space + 0x08000000
        
        # Escribir nueva data
        rom = bytearray(self.project.base_rom_data)
        rom[free_space : free_space + len(compressed)] = compressed
        
        # 5. Repuntear en todos los mapas
        maps_updated = 0
        from struct import pack, unpack
        
        for mh in self.project.map_parser.maps:
            map_id = mh.map_id
            m_header_ptr = self.project.map_parser.map_headers_table + (map_id * 32)
            p_gfx = unpack('<I', rom[m_header_ptr+16:m_header_ptr+20])[0]
            if p_gfx == old_ptr:
                rom[m_header_ptr+16:m_header_ptr+20] = pack('<I', new_ptr)
                maps_updated += 1
                
        self.project.base_rom_data = bytes(rom)
        if hasattr(self.project, 'virtual_rom'):
            self.project.virtual_rom = rom
        
        with open(self.project.base_rom_path, 'wb') as f:
            f.write(rom)
            
        self.project.unsaved_changes = True
        self._load_tileset_list() # Recargar la UI
        
        QMessageBox.information(self, "Éxito", 
            f"Tileset inyectado dinámicamente en 0x{free_space:08X}.\n"
            f"Se repuntearon {maps_updated} mapas exitosamente.")
