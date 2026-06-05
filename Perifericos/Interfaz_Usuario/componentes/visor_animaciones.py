import os
import glob
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QScrollArea, QGridLayout, QFileDialog, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QMovie

class AnimationCell(QFrame):
    clicked = pyqtSignal(str) # Emits the anim_name or anim_id

    def __init__(self, gif_path, title, parent=None):
        super().__init__(parent)
        self.gif_path = gif_path
        self.title = title
        
        self.setFixedSize(140, 160)
        self.setStyleSheet("""
            AnimationCell {
                background: #1a1a2e;
                border: 2px solid #2A2A35;
                border-radius: 6px;
            }
            AnimationCell:hover {
                border: 2px solid #00FF96;
                background: #1A3A2A;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.movie_label = QLabel()
        self.movie_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.movie = QMovie(gif_path)
        self.movie_label.setMovie(self.movie)
        self.movie.start()
        
        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("color: white; font-size: 11px; font-weight: bold;")
        self.title_label.setWordWrap(True)
        
        layout.addWidget(self.movie_label)
        layout.addWidget(self.title_label)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.title)
        super().mousePressEvent(event)

class VisorAnimaciones(QWidget):
    openEditorRequested = pyqtSignal(str) # Emits the animation name to edit

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project = None
        self.current_folder = ""
        self._init_ui()

    def set_project(self, project):
        self.project = project

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        header_layout = QHBoxLayout()
        header = QLabel("🏃 Visor de Animaciones Industriales")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #00FF96;")
        
        self.btn_load = QPushButton("📂 Cargar Carpeta Extracción")
        self.btn_load.setStyleSheet("""
            QPushButton {
                background: #00BFFF; color: black; font-weight: bold;
                padding: 6px 12px; border-radius: 4px; font-size: 12px;
            }
            QPushButton:hover { background: #33CCFF; }
        """)
        self.btn_load.clicked.connect(self.load_directory)
        
        # --- ZOOM SLIDER ---
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("🔍 Zoom:", styleSheet="color: #888; font-size: 12px;"))
        from PyQt6.QtWidgets import QSlider
        self.slider_zoom = QSlider(Qt.Orientation.Horizontal)
        self.slider_zoom.setRange(80, 300)
        self.slider_zoom.setValue(140)
        self.slider_zoom.setFixedWidth(150)
        self.slider_zoom.valueChanged.connect(self._on_zoom_changed)
        zoom_layout.addWidget(self.slider_zoom)
        
        header_layout.addWidget(header)
        header_layout.addStretch()
        header_layout.addLayout(zoom_layout)
        header_layout.addSpacing(20)
        header_layout.addWidget(self.btn_load)
        
        layout.addLayout(header_layout)
        
        # Scroll Area for the Grid
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: #0D0D12; border: 1px solid #2A2A35;")
        
        self.container = QWidget()
        self.grid_layout = QGridLayout(self.container)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

    def load_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de Extracción Masiva")
        if not folder:
            return
            
        self.current_folder = folder
        self._populate_grid()
        
    def _populate_grid(self):
        # Clear current grid
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        if not self.current_folder: return
                
        # Find all GIFs
        gif_files = glob.glob(os.path.join(self.current_folder, "*.gif"))
        gif_files.sort()
        
        columns = 6
        zoom_val = self.slider_zoom.value()
        for i, gif_path in enumerate(gif_files):
            basename = os.path.basename(gif_path)
            name = os.path.splitext(basename)[0]
            
            cell = AnimationCell(gif_path, name)
            cell.setFixedSize(zoom_val, zoom_val + 20)
            cell.movie.setScaledSize(cell.size() * 0.8)
            cell.clicked.connect(self._on_cell_clicked)
            
            row = i // columns
            col = i % columns
            self.grid_layout.addWidget(cell, row, col)

    def _on_zoom_changed(self, value):
        for i in range(self.grid_layout.count()):
            child = self.grid_layout.itemAt(i)
            if child and child.widget():
                w = child.widget()
                w.setFixedSize(value, value + 20)
                # Escalar el QMovie
                if isinstance(w, AnimationCell):
                    w.movie.setScaledSize(w.size() * 0.8)
                    w.movie_label.setFixedSize(value, value)

    def reload_cell(self, anim_name):
        """ Recarga el GIF de la celda si fue sobreescrito """
        for i in range(self.grid_layout.count()):
            child = self.grid_layout.itemAt(i)
            if child and child.widget():
                w = child.widget()
                if isinstance(w, AnimationCell) and w.title == anim_name:
                    # Reiniciar QMovie
                    w.movie.stop()
                    w.movie.setFileName(w.gif_path)
                    w.movie.setScaledSize(w.size() * 0.8)
                    w.movie.start()
                    break

    def _on_cell_clicked(self, anim_name):
        # Open tile editor for this animation
        self.openEditorRequested.emit(anim_name)
