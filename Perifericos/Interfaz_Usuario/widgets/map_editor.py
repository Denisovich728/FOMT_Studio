from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFrame, QGridLayout)
from PyQt6.QtCore import Qt
from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.codec_tiles import bgr555_to_rgb

class MapEditorWidget(QWidget):
    """
    Visor de Metadatos de Mapa.
    En esta fase inicial muestra la información técnica y permite saltar al script.
    """
    def __init__(self, main_window):
        super().__init__()
        self.window = main_window
        self.current_map = None
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Encabezado
        self.title_label = QLabel("<h2>Detalles del Mapa</h2>")
        layout.addWidget(self.title_label)

        # Panel de Información
        info_frame = QFrame()
        info_frame.setFrameShape(QFrame.Shape.StyledPanel)
        info_frame.setStyleSheet("QFrame { background-color: #2b2b2b; border-radius: 8px; padding: 10px; }")
        
        grid = QGridLayout(info_frame)
        
        self.lbl_id = QLabel("ID:")
        self.lbl_dim = QLabel("Dimensiones:")
        self.lbl_tileset = QLabel("Tileset ID:")
        self.lbl_script = QLabel("Script Pointer:")
        
        # Valores
        self.val_id = QLabel("-")
        self.val_dim = QLabel("-")
        self.val_tileset = QLabel("-")
        self.val_script = QLabel("-")
        
        # Estilo valores
        for lbl in [self.val_id, self.val_dim, self.val_tileset, self.val_script]:
            lbl.setStyleSheet("color: #00ff00; font-weight: bold;")

        grid.addWidget(self.lbl_id, 0, 0)
        grid.addWidget(self.val_id, 0, 1)
        grid.addWidget(self.lbl_dim, 1, 0)
        grid.addWidget(self.val_dim, 1, 1)
        grid.addWidget(self.lbl_tileset, 2, 0)
        grid.addWidget(self.val_tileset, 2, 1)
        grid.addWidget(self.lbl_script, 3, 0)
        grid.addWidget(self.val_script, 3, 1)

        layout.addWidget(info_frame)

        # Botones de Acción
        actions_layout = QHBoxLayout()
        
        btn_view_script = QPushButton("Ver Script del Mapa")
        btn_view_script.setMinimumHeight(40)
        btn_view_script.setStyleSheet("QPushButton { background-color: #444; color: white; border-radius: 4px; } QPushButton:hover { background-color: #555; }")
        btn_view_script.clicked.connect(self._on_view_script)
        
        btn_view_tiles = QPushButton("Isolar Gráficos")
        btn_view_tiles.setMinimumHeight(40)
        btn_view_tiles.setStyleSheet("QPushButton { background-color: #2e7d32; color: white; border-radius: 4px; font-weight: bold; } QPushButton:hover { background-color: #388e3c; }")
        btn_view_tiles.clicked.connect(self._on_view_tiles)
        
        actions_layout.addWidget(btn_view_script)
        actions_layout.addWidget(btn_view_tiles)
        layout.addLayout(actions_layout)
        
        layout.addStretch()

    def load_map(self, map_header):
        self.current_map = map_header
        name = self.window.project.super_lib.get_map_name_hint(map_header.map_id)
        self.title_label.setText(f"<h2>{name}</h2>")
        
        self.val_id.setText(f"{map_header.map_id:03d}")
        self.val_dim.setText(f"{map_header.width} x {map_header.height}")
        self.val_tileset.setText(f"0x{map_header.tileset_id:02X}")
        self.val_script.setText(f"0x{map_header.script_offset:08X}")

    def _on_view_script(self):
        if self.current_map and self.current_map.script_offset > 0:
            self.window.script_ide.load_rom_script(self.current_map.script_offset)
            self.window.tabs.setCurrentWidget(self.window.script_ide)

    def _on_view_tiles(self):
        if self.current_map and self.window.tile_viewer:
            gfx_off, pal_off = self.current_map.get_assets(self.window.project)
            if gfx_off:
                # Cargar gráfico
                self.window.tile_viewer.load_graphic(gfx_off)
                
                # Intentar cargar paleta específica si existe
                if pal_off:
                    try:
                        raw_pal = self.window.project.decompress(pal_off)
                        new_pal = []
                        for i in range(0, min(32, len(raw_pal)), 2):
                            c16 = int.from_bytes(raw_pal[i:i+2], 'little')
                            new_pal.append(bgr555_to_rgb(c16))
                        self.window.tile_viewer.current_palette = new_pal
                        self.window.tile_viewer._render()
                    except: pass
                
                self.window.tabs.setCurrentWidget(self.window.tile_viewer)
                self.window.status.showMessage(f"Graphics Isolated for Map {self.current_map.map_id:03d}")
            else:
                self.window.status.showMessage("Este mapa no usa un tileset independiente.")
