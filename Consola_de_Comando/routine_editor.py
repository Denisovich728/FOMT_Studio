# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.7.0)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QListWidget, QTableWidget, QTableWidgetItem, 
    QPushButton, QLabel, QHeaderView, QMessageBox,
    QSplitter
)
from PyQt6.QtCore import Qt
import struct
import importlib.util
import sys
import os

class RoutineEditorWidget(QWidget):
    """
    Editor Dual de Rutinas de Movimiento (X e Y).
    Edita los TargetVectors (Coordinate, Action) directamente en ROM.
    """
    def __init__(self, proyecto):
        super().__init__()
        self.proyecto = proyecto
        self.npc_schedules = {}
        self.current_npc = None
        self.current_sched = None
        
        self.init_ui()
        self.load_data()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        
        # Panel Izquierdo: Selección
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        left_layout.addWidget(QLabel("<b>NPCs</b>"))
        self.npc_list = QListWidget()
        self.npc_list.itemSelectionChanged.connect(self.on_npc_selected)
        left_layout.addWidget(self.npc_list)
        
        left_layout.addWidget(QLabel("<b>Horarios</b>"))
        self.sched_list = QListWidget()
        self.sched_list.itemSelectionChanged.connect(self.on_sched_selected)
        left_layout.addWidget(self.sched_list)
        
        main_layout.addWidget(left_panel, 1)
        
        # Panel Central: Vectores
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Vectores X
        right_layout.addWidget(QLabel("<b>Ruta Eje X (x_vectors)</b>"))
        self.table_x = QTableWidget(0, 2)
        self.table_x.setHorizontalHeaderLabels(["Coordenada X (Pixel)", "Acción / Velocidad"])
        self.table_x.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        right_layout.addWidget(self.table_x)
        
        # Vectores Y
        right_layout.addWidget(QLabel("<b>Ruta Eje Y (y_vectors)</b>"))
        self.table_y = QTableWidget(0, 2)
        self.table_y.setHorizontalHeaderLabels(["Coordenada Y (Pixel)", "Animación Especial"])
        self.table_y.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        right_layout.addWidget(self.table_y)
        
        # Controles
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("💾 Guardar Rutina en ROM")
        btn_save.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        btn_save.clicked.connect(self.save_routine)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        
        right_layout.addLayout(btn_layout)
        
        main_layout.addWidget(right_panel, 3)

    def load_data(self):
        # Cargar NPC_Schedules_Code dinámicamente
        path = os.path.join(os.path.dirname(__file__), "..", "Nucleos_Positronicos", "Nucleo_de_Rutinas_AI", "npc_schedules.py")
        if not os.path.exists(path):
            QMessageBox.warning(self, "Error", "No se encontró npc_schedules.py")
            return
            
        spec = importlib.util.spec_from_file_location("npc_schedules", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["npc_schedules"] = module
        spec.loader.exec_module(module)
        
        self.npc_schedules = module.NPC_SCHEDULES
        
        self.npc_list.clear()
        for npc in sorted(self.npc_schedules.keys()):
            self.npc_list.addItem(npc)

    def on_npc_selected(self):
        if not self.npc_list.currentItem(): return
        self.current_npc = self.npc_list.currentItem().text()
        
        self.sched_list.clear()
        self.table_x.setRowCount(0)
        self.table_y.setRowCount(0)
        
        npc_data = self.npc_schedules.get(self.current_npc, {})
        for sched in npc_data.get('schedules', []):
            action = sched.get('action')
            if action == "NULL" or action == "INVALID": continue
            
            map_name = sched.get('map', 'Desconocido')
            self.sched_list.addItem(f"Horario {sched['id']} - {map_name}")
            
    def on_sched_selected(self):
        if not self.sched_list.currentItem() or not self.current_npc: return
        
        idx = self.sched_list.currentRow()
        npc_data = self.npc_schedules[self.current_npc]
        valid_scheds = [s for s in npc_data['schedules'] if s.get('action') not in ("NULL", "INVALID")]
        
        if idx >= len(valid_scheds): return
        self.current_sched = valid_scheds[idx]
        
        self.populate_tables()

    def populate_tables(self):
        # Llenar Tabla X
        x_raw = self.current_sched.get('x_vectors_raw', [])
        self.table_x.setRowCount(len(x_raw))
        for r, (coord, action) in enumerate(x_raw):
            self.table_x.setItem(r, 0, QTableWidgetItem(str(coord)))
            self.table_x.setItem(r, 1, QTableWidgetItem(f"0x{action:04X}"))
            
        # Llenar Tabla Y
        y_raw = self.current_sched.get('y_vectors_raw', [])
        self.table_y.setRowCount(len(y_raw))
        for r, (coord, action) in enumerate(y_raw):
            self.table_y.setItem(r, 0, QTableWidgetItem(str(coord)))
            self.table_y.setItem(r, 1, QTableWidgetItem(f"0x{action:04X}"))

    def save_routine(self):
        if not self.current_sched: return
        if not self.proyecto or not self.proyecto.virtual_rom:
            QMessageBox.warning(self, "Error", "No hay ROM cargada.")
            return
            
        try:
            # Empaquetar X
            x_bytes = bytearray()
            for r in range(self.table_x.rowCount()):
                coord = int(self.table_x.item(r, 0).text(), 0)
                action = int(self.table_x.item(r, 1).text(), 0)
                x_bytes.extend(struct.pack('<HH', coord, action))
                
            # Empaquetar Y
            y_bytes = bytearray()
            for r in range(self.table_y.rowCount()):
                coord = int(self.table_y.item(r, 0).text(), 0)
                action = int(self.table_y.item(r, 1).text(), 0)
                y_bytes.extend(struct.pack('<HH', coord, action))
                
            QMessageBox.information(self, "Editor de Rutinas", "¡Funcionalidad de inyección lista para ser conectada al MemoryManager!\nLos bytes se han empacado correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al empacar vectores: {e}")
