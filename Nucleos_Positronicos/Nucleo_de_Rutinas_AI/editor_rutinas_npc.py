# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v4.0.0)
# "The Greatest Show - Final Release"
# Desarrollado por: Denisovich728
# ============================================================
"""
editor_rutinas_npc.py
══════════════════════════════════════════════════════════════════
Editor y Orquestador de Rutinas Diarias de NPCs & Macromapa.
Soporta visualización dual (Por Aldeano y Por Mapa), visualización
de condiciones climáticas y temporales de activación de horarios,
nombres canónicos de mapas y visor interactivo de mapas con líneas
de movimiento vectoriales.
"""

import os
import json
import math
from typing import Optional, Dict, List, Tuple

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QGroupBox,
    QLabel, QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QSpinBox, QDoubleSpinBox, QFormLayout, QMessageBox, QFileDialog,
    QToolBar, QStatusBar, QRadioButton, QButtonGroup, QLineEdit, QTabWidget,
    QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QFont, QColor, QIcon, QAction, QMouseEvent
from Consola_de_Comando.i18n import t as _t

from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.world_graph import (
    WorldGraph, MapNode, WarpPoint, WarpConnection,
    DIR_DOWN, DIR_UP, DIR_LEFT, DIR_RIGHT, DIR_FACE
)
from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.macro_map_view import MacroMapView
from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.routine_codec import (
    RoutineCodec, NPCData, NPCSchedule, RoutineWaypoint, NPC_NAMES, NPC_COUNT
)
from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.npc_schedule_conditions import (
    get_npc_schedule_condition, ScheduleCondition
)
from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.fomt_map_names import (
    get_map_display_name, unpack_fomt_map_id, CANONICAL_MAP_INFO
)
from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.route_map_canvas import RouteMapCanvas, ensure_orthogonal_path
from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.tile_pathfinder import TilePathfinder


class FloatingInspector(QWidget):
    """
    Inspector flotante independiente y libre de restricciones.
    Se despliega como ventana de herramientas (Tool Window) sobre el visor de mapas,
    permitiendo moverla con total libertad por toda la pantalla sin bloqueos de lienzo.
    """
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.WindowCloseButtonHint)
        self.setObjectName("floating_inspector")
        self.setWindowTitle(_t("rut_inspector_title"))
        self.setFixedWidth(340)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._user_moved = False
        self._drag_pos = None

        self.setStyleSheet("""
            QWidget#floating_inspector {
                background-color: #161B22;
                border: 1px solid #30363D;
                border-radius: 8px;
            }
            QLabel {
                color: #C9D1D9;
                font-size: 11px;
            }
            QSpinBox, QComboBox {
                background-color: #0D1117;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 4px;
                padding: 3px 6px;
                font-size: 11px;
                font-weight: bold;
            }
            QSpinBox:focus, QComboBox:focus {
                border-color: #58A6FF;
            }
            QPushButton {
                background-color: #21262D;
                color: #C9D1D9;
                border: 1px solid #30363D;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #30363D;
                color: #FFFFFF;
            }
            QRadioButton {
                color: #C9D1D9;
                font-size: 11px;
                font-weight: bold;
            }
            QRadioButton::indicator {
                width: 13px;
                height: 13px;
            }
            QRadioButton::indicator:checked {
                background-color: #58A6FF;
                border: 2px solid #FFFFFF;
                border-radius: 6px;
            }
        """)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            self._user_moved = True
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def moveEvent(self, event):
        super().moveEvent(event)
        self._user_moved = True

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)



class EditorRutinasNPCWidget(QWidget):
    """Widget principal del Editor de Rutinas Diarias y Orquestador de Movimientos."""

    def __init__(self, project=None, parent=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle(_t("rut_window_title"))
        self.resize(1380, 880)

        # Rutas de persistencia de topología
        self.default_graph_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "Banco_de_Datos", "world_graph.json"
        )

        # Cargar grafo mundial
        self.world_graph = WorldGraph.load_from_json(self.default_graph_path)

        # Estado de datos
        self.all_npcs: Dict[int, NPCData] = {}
        self.current_npc: Optional[NPCData] = None
        self.current_schedule: Optional[NPCSchedule] = None
        self.current_mode = "BY_NPC"  # "BY_NPC" o "BY_MAP"
        self.current_segments: List[dict] = []
        self._updating_ui = False

        self._setup_ui()
        self._load_rom_routines()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ==============================================================
        # PANEL IZQUIERDO: Selector de Modo, Orquestador y Controles
        # ==============================================================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # 1. Selector de Modo: Por NPC vs Por Mapa
        mode_group = QGroupBox(_t("rut_grp_mode"))
        mode_layout = QHBoxLayout(mode_group)
        self.rb_by_npc = QRadioButton(_t("rut_by_npc"))
        self.rb_by_map = QRadioButton(_t("rut_by_map"))
        self.rb_by_npc.setChecked(True)

        self.btn_group_mode = QButtonGroup(self)
        self.btn_group_mode.addButton(self.rb_by_npc)
        self.btn_group_mode.addButton(self.rb_by_map)
        self.rb_by_npc.toggled.connect(self._on_mode_toggled)

        mode_layout.addWidget(self.rb_by_npc)
        mode_layout.addWidget(self.rb_by_map)
        left_layout.addWidget(mode_group)

        # 2. Contenedor de Selectores (NPC / Mapa según el modo)
        self.sel_group = QGroupBox(_t("rut_grp_filter"))
        self.sel_form = QFormLayout(self.sel_group)

        # Fila NPC
        self.combo_npc = QComboBox()
        for nid in range(NPC_COUNT):
            name = NPC_NAMES.get(nid, f"NPC #{nid}")
            self.combo_npc.addItem(f"[{nid:02d}] {name}", nid)
        self.combo_npc.currentIndexChanged.connect(self._on_npc_changed)
        self.lbl_npc_row = QLabel(_t("rut_villager"))
        self.sel_form.addRow(self.lbl_npc_row, self.combo_npc)

        # Fila Horario
        self.combo_schedule = QComboBox()
        self.combo_schedule.currentIndexChanged.connect(self._on_schedule_changed)
        self.lbl_sched_row = QLabel(_t("rut_schedule"))
        self.sel_form.addRow(self.lbl_sched_row, self.combo_schedule)

        # Fila Mapa (para modo "Por Mapa")
        self.combo_filter_map = QComboBox()
        self.combo_filter_map.currentIndexChanged.connect(self._on_filter_map_changed)
        self.lbl_map_row = QLabel(_t("rut_map"))
        self.sel_form.addRow(self.lbl_map_row, self.combo_filter_map)
        self.lbl_map_row.hide()
        self.combo_filter_map.hide()

        left_layout.addWidget(self.sel_group)

        # 2.1 Tarjeta Informativa de Condiciones de Activación
        self.cond_group = QGroupBox(_t("rut_grp_cond"))
        self.cond_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #58A6FF;
                border: 1px solid #30363D;
                border-radius: 6px;
                margin-top: 4px;
                padding-top: 8px;
                background-color: #0D1117;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
        """)
        cond_layout = QVBoxLayout(self.cond_group)
        cond_layout.setContentsMargins(10, 6, 10, 8)
        cond_layout.setSpacing(3)

        self.lbl_cond_badge = QLabel(_t("rut_cond_badge_default"))
        self.lbl_cond_badge.setStyleSheet("font-weight: bold; color: #58A6FF; font-size: 11px;")

        self.lbl_cond_name = QLabel(_t("rut_main_schedule"))
        self.lbl_cond_name.setStyleSheet("font-size: 12px; font-weight: bold; color: #FFFFFF;")

        self.lbl_cond_desc = QLabel(_t("rut_cond_desc_default"))
        self.lbl_cond_desc.setWordWrap(True)
        self.lbl_cond_desc.setStyleSheet("color: #8B949E; font-size: 10px;")

        self.lbl_cond_loc = QLabel(_t("rut_zone_unknown"))
        self.lbl_cond_loc.setStyleSheet("color: #3FB950; font-size: 10px; font-weight: bold;")

        cond_layout.addWidget(self.lbl_cond_badge)
        cond_layout.addWidget(self.lbl_cond_name)
        cond_layout.addWidget(self.lbl_cond_desc)
        cond_layout.addWidget(self.lbl_cond_loc)
        left_layout.addWidget(self.cond_group)

        # 3. Tabla Orquestadora de Tramos A  B (Delays, Velocidades y Coordenadas)
        self.tbl_group = QGroupBox(_t("rut_grp_table"))
        tbl_layout = QVBoxLayout(self.tbl_group)

        self.table_segments = QTableWidget()
        self.table_segments.setColumnCount(9)
        self.table_segments.setHorizontalHeaderLabels([
            _t("rut_col_step"), _t("rut_col_map"), "NPC", _t("rut_col_point_a"), _t("rut_col_point_b"), _t("rut_col_distance"), _t("rut_col_speed"), _t("rut_col_wait"), _t("rut_col_time")
        ])
        self.table_segments.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_segments.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_segments.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_segments.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_segments.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_segments.itemSelectionChanged.connect(self._on_segment_selected)
        tbl_layout.addWidget(self.table_segments)

        # Botones de gestión de tramos
        btn_seg_layout = QHBoxLayout()
        self.btn_add_step = QPushButton(_t("rut_btn_add_step"))
        self.btn_add_step.clicked.connect(self._on_add_waypoint)
        self.btn_del_step = QPushButton(_t("rut_btn_delete"))
        self.btn_del_step.clicked.connect(self._on_delete_waypoint)
        self.btn_edit_step = QPushButton(_t("rut_btn_edit_step"))
        self.btn_edit_step.setStyleSheet("background-color: #1F6FEB; color: white; font-weight: bold;")
        self.btn_edit_step.clicked.connect(self._on_edit_step_clicked)

        btn_seg_layout.addWidget(self.btn_add_step)
        btn_seg_layout.addWidget(self.btn_del_step)
        btn_seg_layout.addWidget(self.btn_edit_step)
        tbl_layout.addLayout(btn_seg_layout)
        left_layout.addWidget(self.tbl_group)

        # 4. Botones de Inyección en ROM y Guardado
        rom_actions = QHBoxLayout()
        self.btn_inject_rom = QPushButton(_t("rut_btn_inject"))
        self.btn_inject_rom.setStyleSheet("background-color: #238636; color: white; font-weight: bold; padding: 7px;")
        self.btn_inject_rom.clicked.connect(self._on_inject_rom_clicked)

        self.btn_export_json = QPushButton(_t("rut_btn_export_json"))
        self.btn_export_json.clicked.connect(self._on_export_json)

        rom_actions.addWidget(self.btn_inject_rom, 2)
        rom_actions.addWidget(self.btn_export_json, 1)
        left_layout.addLayout(rom_actions)

        splitter.addWidget(left_widget)

        # ==============================================================
        # PANEL DERECHO: Tabbed View (Vista General del Mapa & Macromapa)
        # ==============================================================
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        self.right_tabs = QTabWidget()
        self.right_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #30363D;
                background-color: #0D1117;
            }
            QTabBar::tab {
                background-color: #161B22;
                color: #8B949E;
                padding: 7px 16px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                border: 1px solid #30363D;
                border-bottom: none;
                margin-right: 2px;
                font-weight: bold;
                font-size: 11px;
            }
            QTabBar::tab:selected {
                background-color: #21262D;
                color: #58A6FF;
                border-bottom: 2px solid #58A6FF;
            }
            QTabBar::tab:hover {
                color: #C9D1D9;
            }
        """)

        # -------------------------------------------------------------
        # TAB 1: Vista General del Mapa & Líneas de Movimiento
        # -------------------------------------------------------------
        tab_route = QWidget()
        tab_route_layout = QVBoxLayout(tab_route)
        tab_route_layout.setContentsMargins(0, 0, 0, 0)
        tab_route_layout.setSpacing(2)

        # Barra de herramientas del visor de rutas
        route_toolbar = QToolBar("Herramientas de Visor de Rutas")
        route_toolbar.setStyleSheet("background-color: #161B22; border-bottom: 1px solid #30363D; padding: 4px;")

        self.lbl_canvas_map_name = QLabel(_t("rut_map_not_loaded"))
        self.lbl_canvas_map_name.setStyleSheet("font-weight: bold; color: #58A6FF; padding: 2px 8px; font-size: 11px;")
        route_toolbar.addWidget(self.lbl_canvas_map_name)

        self.act_open_in_map_editor = QAction(_t("rut_open_map_editor"), self)
        self.act_open_in_map_editor.setToolTip(_t("rut_open_map_editor_tip"))
        self.act_open_in_map_editor.triggered.connect(self._on_open_in_map_editor_clicked)
        route_toolbar.addAction(self.act_open_in_map_editor)

        route_toolbar.addSeparator()

        self.act_rc_zoom_in = QAction("+", self)
        self.act_rc_zoom_in.triggered.connect(lambda: self.route_canvas.zoom_in())
        route_toolbar.addAction(self.act_rc_zoom_in)

        self.act_rc_zoom_out = QAction("-", self)
        self.act_rc_zoom_out.triggered.connect(lambda: self.route_canvas.zoom_out())
        route_toolbar.addAction(self.act_rc_zoom_out)

        self.act_rc_zoom_fit = QAction(_t("rut_fit"), self)
        self.act_rc_zoom_fit.triggered.connect(lambda: self.route_canvas.zoom_fit())
        route_toolbar.addAction(self.act_rc_zoom_fit)

        self.act_rc_zoom_reset = QAction("100%", self)
        self.act_rc_zoom_reset.triggered.connect(lambda: self.route_canvas.zoom_reset())
        route_toolbar.addAction(self.act_rc_zoom_reset)

        route_toolbar.addSeparator()

        self.act_rc_vectors = QAction(_t("rut_vectors"), self)
        self.act_rc_vectors.setCheckable(True)
        self.act_rc_vectors.setChecked(True)
        self.act_rc_vectors.toggled.connect(lambda chk: self.route_canvas.toggle_vectors(chk))
        route_toolbar.addAction(self.act_rc_vectors)

        self.act_rc_labels = QAction(_t("rut_labels"), self)
        self.act_rc_labels.setCheckable(True)
        self.act_rc_labels.setChecked(True)
        self.act_rc_labels.toggled.connect(lambda chk: self.route_canvas.toggle_labels(chk))
        route_toolbar.addAction(self.act_rc_labels)

        self.act_rc_walkable = QAction(_t("rut_walkable"), self)
        self.act_rc_walkable.setCheckable(True)
        self.act_rc_walkable.setChecked(False)
        self.act_rc_walkable.toggled.connect(lambda chk: self.route_canvas.toggle_walkable_grid(chk))
        route_toolbar.addAction(self.act_rc_walkable)

        route_toolbar.addSeparator()

        self.act_rc_inspector = QAction(_t("rut_floating_inspector"), self)
        self.act_rc_inspector.setCheckable(True)
        self.act_rc_inspector.setChecked(True)
        self.act_rc_inspector.setToolTip(_t("rut_floating_inspector_tip"))
        self.act_rc_inspector.toggled.connect(self._toggle_floating_inspector)
        route_toolbar.addAction(self.act_rc_inspector)

        tab_route_layout.addWidget(route_toolbar)

        self.route_canvas = RouteMapCanvas(self.project, self)
        self.route_canvas.point_clicked.connect(self._on_canvas_point_clicked)
        self.route_canvas.node_selected.connect(self._on_canvas_node_selected)
        self.route_canvas.node_moved.connect(self._on_canvas_node_moved)
        self.route_canvas.node_drag_finished.connect(self._on_canvas_node_drag_finished)
        self.route_canvas.node_inserted.connect(self._on_canvas_node_inserted)
        self.route_canvas.node_deleted.connect(self._on_canvas_node_deleted)
        tab_route_layout.addWidget(self.route_canvas)

        # Inspector flotante sobre el visor de mapas
        self.floating_inspector = FloatingInspector(self)
        self._build_floating_inspector_ui()
        self.floating_inspector.closed.connect(lambda: self.act_rc_inspector.setChecked(False))
        self.route_canvas.on_view_resized = self._reposition_floating_inspector
        self._reposition_floating_inspector()

        self.right_tabs.addTab(tab_route, _t("rut_tab_route"))

        # -------------------------------------------------------------
        # TAB 2: Macromapa Global de Mineral Town (Red A*)
        # -------------------------------------------------------------
        tab_macro = QWidget()
        tab_macro_layout = QVBoxLayout(tab_macro)
        tab_macro_layout.setContentsMargins(0, 0, 0, 0)
        tab_macro_layout.setSpacing(2)

        # Toolbar Macromapa
        map_toolbar = QToolBar("Herramientas del Macromapa")
        map_toolbar.setStyleSheet("background-color: #161B22; border-bottom: 1px solid #30363D; padding: 4px;")

        self.act_connect = QAction(_t("rut_connect_warps"), self)
        self.act_connect.setCheckable(True)
        self.act_connect.triggered.connect(self._on_toggle_connect_mode)
        map_toolbar.addAction(self.act_connect)

        self.act_save_topo = QAction(_t("rut_save_topo"), self)
        self.act_save_topo.triggered.connect(self._on_save_topology)
        map_toolbar.addAction(self.act_save_topo)

        self.act_reload_topo = QAction(_t("rut_reload"), self)
        self.act_reload_topo.triggered.connect(self._on_reload_topology)
        map_toolbar.addAction(self.act_reload_topo)

        map_toolbar.addSeparator()

        self.act_zoom_in = QAction("+", self)
        self.act_zoom_in.triggered.connect(lambda: self.macro_view.scale(1.2, 1.2))
        map_toolbar.addAction(self.act_zoom_in)

        self.act_zoom_out = QAction("-", self)
        self.act_zoom_out.triggered.connect(lambda: self.macro_view.scale(1.0 / 1.2, 1.0 / 1.2))
        map_toolbar.addAction(self.act_zoom_out)

        self.act_zoom_reset = QAction(" 100%", self)
        self.act_zoom_reset.triggered.connect(lambda: self.macro_view.resetTransform())
        map_toolbar.addAction(self.act_zoom_reset)

        tab_macro_layout.addWidget(map_toolbar)

        # Lienzo MacroMapView
        self.macro_view = MacroMapView(self.world_graph, self)
        self.macro_view.connection_created.connect(self._on_connection_created_signal)
        self.macro_view.map_selected.connect(self._on_macro_map_selected)
        tab_macro_layout.addWidget(self.macro_view)

        self.right_tabs.addTab(tab_macro, _t("rut_tab_macro"))

        right_layout.addWidget(self.right_tabs)

        # Barra de estado
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("background-color: #0D1117; color: #8B949E; font-size: 11px;")
        self.status_bar.showMessage(_t("rut_status_help"))
        right_layout.addWidget(self.status_bar)

        splitter.addWidget(right_widget)
        splitter.setSizes([380, 1000])
        main_layout.addWidget(splitter)

    def _load_rom_routines(self):
        """Carga y decodifica las rutinas desde la ROM activa."""
        rom_data = None
        if self.project and getattr(self.project, "virtual_rom", None):
            rom_data = bytes(self.project.virtual_rom)
        elif self.project and getattr(self.project, "base_rom_data", None):
            rom_data = self.project.base_rom_data
        elif self.project and getattr(self.project, "base_rom_path", None):
            if os.path.exists(self.project.base_rom_path):
                with open(self.project.base_rom_path, "rb") as f:
                    rom_data = f.read()

        if self.project:
            from Banco_de_Datos.parche_splash import require_rom_signature
            require_rom_signature(self.project, auto_sign=True, module_name="NpcRoutineEditor")

        if rom_data:
            self.all_npcs = RoutineCodec.decode_all(rom_data)
            self.route_canvas.rom_data = rom_data
            if hasattr(self.route_canvas, "pathfinder") and self.route_canvas.pathfinder:
                self.route_canvas.pathfinder.rom_data = rom_data
        else:
            for nid in range(NPC_COUNT):
                self.all_npcs[nid] = NPCData(nid, NPC_NAMES.get(nid, f"NPC_{nid}"))

        self._populate_filter_maps()
        self._on_npc_changed(0)

    def _populate_filter_maps(self):
        """Llena el combo de filtrado por mapa con conteo de presencia de NPCs."""
        self.combo_filter_map.blockSignals(True)
        self.combo_filter_map.clear()

        # Calcular estadísticas de presencia por mapa (usando base_map_id con máscara canónica 0xFF)
        map_stats: Dict[int, set] = {}
        map_tramo_counts: Dict[int, int] = {}

        for nid, npc in self.all_npcs.items():
            for sched in npc.schedules:
                if not sched:
                    continue
                for wp in sched.waypoints:
                    base_mid = wp.map_id & 0xFF
                    map_stats.setdefault(base_mid, set()).add(nid)
                    map_tramo_counts[base_mid] = map_tramo_counts.get(base_mid, 0) + 1

        for mid, node in sorted(self.world_graph.nodes.items(), key=lambda x: x[0]):
            base_mid = mid & 0xFF
            npc_set = map_stats.get(base_mid, set())
            tramos = map_tramo_counts.get(base_mid, 0)
            map_name = get_map_display_name(base_mid)
            label = f"{map_name} ({len(npc_set)} NPCs, {tramos} tramos)"
            self.combo_filter_map.addItem(label, base_mid)

        self.combo_filter_map.blockSignals(False)

    def _on_mode_toggled(self):
        """Alterna entre ver por NPC y ver por Mapa."""
        if self.rb_by_npc.isChecked():
            self.current_mode = "BY_NPC"
            self.lbl_npc_row.show()
            self.combo_npc.show()
            self.lbl_sched_row.show()
            self.combo_schedule.show()
            self.lbl_map_row.hide()
            self.combo_filter_map.hide()
            self.cond_group.show()
            self.status_bar.showMessage(_t("rut_status_mode_npc"))
            self._refresh_npc_segments()
        else:
            self.current_mode = "BY_MAP"
            self.lbl_npc_row.hide()
            self.combo_npc.hide()
            self.lbl_sched_row.hide()
            self.combo_schedule.hide()
            self.lbl_map_row.show()
            self.combo_filter_map.show()
            self.cond_group.hide()
            self.status_bar.showMessage(_t("rut_status_mode_map"))
            self._refresh_map_segments()

    def _on_npc_changed(self, index: int):
        npc_id = self.combo_npc.currentData()
        self.current_npc = self.all_npcs.get(npc_id)
        if not self.current_npc:
            return

        self.combo_schedule.blockSignals(True)
        self.combo_schedule.clear()
        for idx, sched in enumerate(self.current_npc.schedules):
            if sched:
                raw_cond = getattr(sched, "condition_info", None) or get_npc_schedule_condition(self.current_npc.npc_id, idx, sched)
                cond = ScheduleCondition.from_data(raw_cond)
                icon = getattr(cond, "icon", "") or ""
                label = f"#{idx}: {icon} {cond.name} [{cond.location_badge}] ({len(sched.waypoints)} hitos)"
                self.combo_schedule.addItem(label, idx)
            else:
                self.combo_schedule.addItem(_t("rut_schedule_empty", idx=idx), idx)
        self.combo_schedule.blockSignals(False)

        if self.combo_schedule.count() > 0:
            first_valid = 0
            for idx, s in enumerate(self.current_npc.schedules):
                if s and len(s.waypoints) > 0:
                    first_valid = idx
                    break
            self.combo_schedule.setCurrentIndex(first_valid)
            self._on_schedule_changed(first_valid)

    def _on_schedule_changed(self, index: int):
        if not self.current_npc or index < 0 or index >= len(self.current_npc.schedules):
            self.current_schedule = None
            self._refresh_npc_segments()
            self._update_condition_banner(None)
            return

        self.current_schedule = self.current_npc.schedules[index]
        self._refresh_npc_segments()

        cond = None
        if self.current_schedule:
            raw_cond = getattr(self.current_schedule, "condition_info", None) or get_npc_schedule_condition(
                self.current_npc.npc_id, index, self.current_schedule
            )
            cond = ScheduleCondition.from_data(raw_cond)
        self._update_condition_banner(cond)

    def _update_condition_banner(self, cond: Optional[ScheduleCondition]):
        """Actualiza la tarjeta visual informativa de condiciones de activación."""
        if not cond:
            self.lbl_cond_badge.setText(_t("rut_no_schedule"))
            self.lbl_cond_name.setText(_t("rut_schedule_unavailable"))
            self.lbl_cond_desc.setText(_t("rut_select_hint"))
            self.lbl_cond_loc.setText(_t("rut_location_na"))
            return

        icon = getattr(cond, "icon", "") or ""
        badge_text = f"{icon} Clima: {cond.weather}  |   Días: {cond.days}"
        if getattr(cond, "is_festival", False):
            badge_text += "  |   Festival"
        if getattr(cond, "is_marriage", False):
            badge_text += "  |   Matrimonio"

        self.lbl_cond_badge.setText(badge_text)
        self.lbl_cond_name.setText(cond.name)
        self.lbl_cond_desc.setText(cond.condition_desc)
        self.lbl_cond_loc.setText(_t("rut_main_zone", zone=cond.location_badge))

    def _on_filter_map_changed(self, index: int):
        if self.current_mode == "BY_MAP":
            self._refresh_map_segments()

    def _refresh_npc_segments(self):
        """Genera los tramos A  B para el NPC y horario actualmente seleccionados."""
        self.current_segments.clear()
        if not self.current_schedule:
            self._populate_table_with_segments([])
            self.macro_view.set_active_orchestrated_segments([])
            self.route_canvas.set_route_segments([])
            return

        wps = self.current_schedule.waypoints
        segments = []

        for i in range(len(wps)):
            curr_wp = wps[i]
            prev_wp = wps[i - 1] if i > 0 else curr_wp

            curr_mid = curr_wp.map_id & 0xFF
            ax, ay = curr_wp.spawn_x, curr_wp.spawn_y
            bx, by = curr_wp.dest_x, curr_wp.dest_y

            # Distancia ortogonal Manhattan real sobre path_nodes
            if curr_wp.path_nodes and len(curr_wp.path_nodes) > 1:
                dist = sum(
                    abs(curr_wp.path_nodes[k][0] - curr_wp.path_nodes[k - 1][0]) +
                    abs(curr_wp.path_nodes[k][1] - curr_wp.path_nodes[k - 1][1])
                    for k in range(1, len(curr_wp.path_nodes))
                )
            else:
                dist = abs(bx - ax) + abs(by - ay)

            delay_m = max(0, curr_wp.time_val - prev_wp.time_val) if i > 0 else 0
            speed_val = 1.0

            map_name = curr_wp.map_name
            is_loop = len(curr_wp.path_nodes) > 1 and curr_wp.path_nodes[0] == curr_wp.path_nodes[-1]

            seg = {
                "id": f"npc_{self.current_npc.npc_id}_s{self.current_schedule.schedule_id}_w{i}",
                "npc_id": self.current_npc.npc_id,
                "npc_name": self.current_npc.name,
                "map_id": curr_wp.map_id,
                "base_map_id": curr_mid,
                "map_name": map_name,
                "ax": ax, "ay": ay,
                "bx": bx, "by": by,
                "dist": dist,
                "speed_val": speed_val,
                "speed_str": f"{speed_val:.1f}x",
                "delay_str": f"{delay_m}m",
                "delay_val": delay_m,
                "time_str": curr_wp.time_to_str(),
                "time_val": curr_wp.time_val,
                "dir": curr_wp.spawn_dir,
                "path_nodes": list(curr_wp.path_nodes),
                "is_loop": is_loop,
                "wp_ref": curr_wp,
                "prev_wp_ref": prev_wp
            }
            segments.append(seg)

        self.current_segments = segments
        self._populate_table_with_segments(segments)
        self.macro_view.set_active_orchestrated_segments(segments)

        # Actualizar vista general del mapa y trazar líneas de movimiento
        if segments:
            # Buscar el primer tramo ACTIVO (con coordenadas reales distintas de 0,0 o no despawn)
            active_seg = next((s for s in segments if s.get("ax", 0) > 0 or s.get("ay", 0) > 0 or s.get("bx", 0) > 0 or s.get("by", 0) > 0), segments[0])
            first_map = active_seg["map_id"]
            self.route_canvas.load_map_view(first_map)
            self.lbl_canvas_map_name.setText(f" {active_seg['map_name']}")
            self.route_canvas.set_route_segments(segments, highlight_id=active_seg["id"])
            if active_seg.get("ax") or active_seg.get("ay"):
                self.route_canvas.center_on_point(active_seg["ax"], active_seg["ay"])
        else:
            self.route_canvas.set_route_segments([])

    def _refresh_map_segments(self):
        """Extrae y genera los tramos de TODOS los NPCs que pasan por el mapa seleccionado."""
        self.current_segments.clear()
        target_map_id = self.combo_filter_map.currentData()
        if target_map_id is None:
            return

        target_base = target_map_id & 0xFF
        segments = []

        for nid, npc in self.all_npcs.items():
            for sid, sched in enumerate(npc.schedules):
                if not sched:
                    continue
                wps = sched.waypoints
                for wid in range(len(wps)):
                    curr_wp = wps[wid]
                    curr_base = curr_wp.map_id & 0xFF

                    if curr_base == target_base:
                        prev_wp = wps[wid - 1] if wid > 0 else curr_wp
                        ax = curr_wp.spawn_x
                        ay = curr_wp.spawn_y
                        bx = curr_wp.dest_x
                        by = curr_wp.dest_y

                        if curr_wp.path_nodes and len(curr_wp.path_nodes) > 1:
                            dist = sum(
                                abs(curr_wp.path_nodes[k][0] - curr_wp.path_nodes[k - 1][0]) +
                                abs(curr_wp.path_nodes[k][1] - curr_wp.path_nodes[k - 1][1])
                                for k in range(1, len(curr_wp.path_nodes))
                            )
                        else:
                            dist = abs(bx - ax) + abs(by - ay)

                        delay_m = max(0, curr_wp.time_val - prev_wp.time_val) if wid > 0 else 0
                        map_name = curr_wp.map_name
                        is_loop = len(curr_wp.path_nodes) > 1 and curr_wp.path_nodes[0] == curr_wp.path_nodes[-1]

                        seg = {
                            "id": f"map_{target_base}_npc_{nid}_s{sid}_w{wid}",
                            "npc_id": nid,
                            "npc_name": npc.name,
                            "map_id": curr_wp.map_id,
                            "base_map_id": target_base,
                            "map_name": map_name,
                            "ax": ax, "ay": ay,
                            "bx": bx, "by": by,
                            "dist": dist,
                            "speed_val": 1.0,
                            "speed_str": "1.0x",
                            "delay_str": f"{delay_m}m",
                            "delay_val": delay_m,
                            "time_str": curr_wp.time_to_str(),
                            "time_val": curr_wp.time_val,
                            "dir": curr_wp.spawn_dir,
                            "path_nodes": list(curr_wp.path_nodes),
                            "is_loop": is_loop,
                            "wp_ref": curr_wp,
                            "prev_wp_ref": prev_wp
                        }
                        segments.append(seg)

        self.current_segments = segments
        self._populate_table_with_segments(segments)
        self.macro_view.set_active_orchestrated_segments(segments)

        # Actualizar lienzo con el mapa seleccionado
        self.route_canvas.load_map_view(target_map_id)
        self.lbl_canvas_map_name.setText(f" {get_map_display_name(target_map_id)}")
        self.route_canvas.set_route_segments(segments)

    def _populate_table_with_segments(self, segments: List[dict]):
        self.table_segments.blockSignals(True)
        self.table_segments.setRowCount(len(segments))

        for row, s in enumerate(segments):
            is_loop = s.get("is_loop", False)
            loop_badge = " " if is_loop else ""
            item_lbl = QTableWidgetItem(f"#{row+1}{loop_badge}")
            item_map = QTableWidgetItem(s.get("map_name", f"Mapa {s.get('map_id', 0)}"))
            item_npc = QTableWidgetItem(s["npc_name"])
            item_pt_a = QTableWidgetItem(f"({s['ax']}, {s['ay']})")
            if is_loop:
                num_legs = max(1, len(s.get("path_nodes", [])) - 1)
                item_pt_b = QTableWidgetItem(f" ({s['bx']}, {s['by']})")
                item_pt_b.setToolTip(_t("rut_loop_tip", n=num_legs))
                item_pt_b.setForeground(QColor("#A371F7"))
            else:
                item_pt_b = QTableWidgetItem(f"({s['bx']}, {s['by']})")
            item_dist = QTableWidgetItem(f"{s['dist']} px")
            item_spd = QTableWidgetItem(s["speed_str"])
            item_delay = QTableWidgetItem(s["delay_str"])
            item_time = QTableWidgetItem(s["time_str"])

            item_map.setForeground(QColor("#58A6FF"))
            font_bold = item_lbl.font()
            font_bold.setBold(True)
            item_lbl.setFont(font_bold)
            item_map.setFont(font_bold)

            for it in (item_lbl, item_map, item_npc, item_pt_a, item_pt_b, item_dist, item_spd, item_delay, item_time):
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table_segments.setItem(row, 0, item_lbl)
            self.table_segments.setItem(row, 1, item_map)
            self.table_segments.setItem(row, 2, item_npc)
            self.table_segments.setItem(row, 3, item_pt_a)
            self.table_segments.setItem(row, 4, item_pt_b)
            self.table_segments.setItem(row, 5, item_dist)
            self.table_segments.setItem(row, 6, item_spd)
            self.table_segments.setItem(row, 7, item_delay)
            self.table_segments.setItem(row, 8, item_time)

        self.table_segments.blockSignals(False)

        if len(segments) > 0:
            self.table_segments.selectRow(0)

    def _build_floating_inspector_ui(self):
        """Construye los controles interactivos dentro de la tarjeta flotante sobre el mapa."""
        insp_layout = QVBoxLayout(self.floating_inspector)
        insp_layout.setContentsMargins(12, 10, 12, 10)
        insp_layout.setSpacing(6)

        # 1. Cabecera con título, badge de hito y botón de cierre
        header_layout = QHBoxLayout()
        lbl_insp_title = QLabel(_t("rut_node_inspector"))
        lbl_insp_title.setStyleSheet("font-weight: bold; color: #58A6FF; font-size: 12px;")
        self.lbl_insp_badge = QLabel(_t("rut_step_1"))
        self.lbl_insp_badge.setStyleSheet("background-color: #21262D; color: #79C0FF; border-radius: 3px; padding: 2px 6px; font-size: 10px; font-weight: bold;")
        btn_close_insp = QPushButton("")
        btn_close_insp.setFixedSize(20, 20)
        btn_close_insp.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close_insp.setStyleSheet("background-color: transparent; border: none; color: #8B949E; font-size: 12px; font-weight: bold;")
        btn_close_insp.clicked.connect(lambda: self.act_rc_inspector.setChecked(False))

        header_layout.addWidget(lbl_insp_title)
        header_layout.addWidget(self.lbl_insp_badge)
        header_layout.addStretch()
        header_layout.addWidget(btn_close_insp)
        insp_layout.addLayout(header_layout)

        # 1.1 Selector de Mapa del Hito
        row_map = QHBoxLayout()
        lbl_map_tag = QLabel(_t("rut_map"))
        lbl_map_tag.setStyleSheet("color: #58A6FF; font-weight: bold; font-size: 11px;")
        self.combo_seg_map = QComboBox()
        self.combo_seg_map.setStyleSheet("font-size: 11px; padding: 2px;")
        for mid, minfo in sorted(CANONICAL_MAP_INFO.items()):
            self.combo_seg_map.addItem(f"[{mid:02X}] {minfo['name_es']}", mid)
        self.combo_seg_map.currentIndexChanged.connect(self._on_segment_map_changed)
        row_map.addWidget(lbl_map_tag)
        row_map.addWidget(self.combo_seg_map, 1)
        insp_layout.addLayout(row_map)

        # 2. Selector de asignación de clics en el lienzo
        click_target_box = QGroupBox(_t("rut_grp_click_target"))
        click_target_box.setStyleSheet("QGroupBox { font-size: 10px; color: #8B949E; border: 1px solid #30363D; border-radius: 4px; margin-top: 6px; padding-top: 6px; } QGroupBox::title { subcontrol-origin: margin; left: 8px; }")
        click_tgt_lay = QHBoxLayout(click_target_box)
        click_tgt_lay.setContentsMargins(8, 4, 8, 4)
        self.rb_target_b = QRadioButton(_t("rut_target_b"))
        self.rb_target_a = QRadioButton(_t("rut_target_a"))
        self.rb_target_inflection = QRadioButton(_t("rut_target_c"))
        self.rb_target_inflection.setToolTip(_t("rut_target_c_tip"))
        self.rb_target_b.setChecked(True)
        click_tgt_lay.addWidget(self.rb_target_b)
        click_tgt_lay.addWidget(self.rb_target_a)
        click_tgt_lay.addWidget(self.rb_target_inflection)
        insp_layout.addWidget(click_target_box)

        # 3. Coordenadas de Inicio (A) y Fin (B)
        pts_box = QGroupBox(_t("rut_grp_coords"))
        pts_box.setStyleSheet("QGroupBox { font-size: 10px; color: #8B949E; border: 1px solid #30363D; border-radius: 4px; margin-top: 6px; padding-top: 6px; } QGroupBox::title { subcontrol-origin: margin; left: 8px; }")
        pts_lay = QVBoxLayout(pts_box)
        pts_lay.setContentsMargins(8, 6, 8, 6)
        pts_lay.setSpacing(4)

        row_a = QHBoxLayout()
        lbl_a_tag = QLabel(" A:")
        lbl_a_tag.setStyleSheet("color: #00E676; font-weight: bold; font-size: 11px;")
        self.spin_ax = QSpinBox()
        self.spin_ax.setRange(0, 4096)
        self.spin_ax.setSingleStep(8)
        self.spin_ax.setPrefix("X: ")
        self.spin_ay = QSpinBox()
        self.spin_ay.setRange(0, 4096)
        self.spin_ay.setSingleStep(8)
        self.spin_ay.setPrefix("Y: ")
        row_a.addWidget(lbl_a_tag)
        row_a.addWidget(self.spin_ax, 1)
        row_a.addWidget(self.spin_ay, 1)
        pts_lay.addLayout(row_a)

        row_b = QHBoxLayout()
        lbl_b_tag = QLabel(" B:")
        lbl_b_tag.setStyleSheet("color: #FFD600; font-weight: bold; font-size: 11px;")
        self.spin_bx = QSpinBox()
        self.spin_bx.setRange(0, 4096)
        self.spin_bx.setSingleStep(8)
        self.spin_bx.setPrefix("X: ")
        self.spin_by = QSpinBox()
        self.spin_by.setRange(0, 4096)
        self.spin_by.setSingleStep(8)
        self.spin_by.setPrefix("Y: ")
        row_b.addWidget(lbl_b_tag)
        row_b.addWidget(self.spin_bx, 1)
        row_b.addWidget(self.spin_by, 1)
        pts_lay.addLayout(row_b)

        self.lbl_auto_status = QLabel(_t("rut_auto_adjust"))
        self.lbl_auto_status.setStyleSheet("color: #3FB950; font-size: 10px; font-weight: bold; padding-top: 2px;")
        pts_lay.addWidget(self.lbl_auto_status)
        insp_layout.addWidget(pts_box)

        # 3.1 Puntos de Inflexión Intermedios (Giro en Calles AWSD)
        inflection_box = QGroupBox(_t("rut_grp_inflection"))
        inflection_box.setStyleSheet("QGroupBox { font-size: 10px; color: #8B949E; border: 1px solid #30363D; border-radius: 4px; margin-top: 6px; padding-top: 6px; } QGroupBox::title { subcontrol-origin: margin; left: 8px; }")
        infl_lay = QVBoxLayout(inflection_box)
        infl_lay.setContentsMargins(8, 6, 8, 6)
        infl_lay.setSpacing(4)

        row_infl_sel = QHBoxLayout()
        row_infl_sel.addWidget(QLabel(_t("rut_point")))
        self.combo_inflection_nodes = QComboBox()
        self.combo_inflection_nodes.currentIndexChanged.connect(self._on_inflection_combo_changed)
        row_infl_sel.addWidget(self.combo_inflection_nodes, 1)
        infl_lay.addLayout(row_infl_sel)

        row_infl_coord = QHBoxLayout()
        self.spin_node_x = QSpinBox()
        self.spin_node_x.setRange(0, 4096)
        self.spin_node_x.setSingleStep(8)
        self.spin_node_x.setPrefix("X: ")
        self.spin_node_x.valueChanged.connect(self._on_inflection_spin_changed)

        self.spin_node_y = QSpinBox()
        self.spin_node_y.setRange(0, 4096)
        self.spin_node_y.setSingleStep(8)
        self.spin_node_y.setPrefix("Y: ")
        self.spin_node_y.valueChanged.connect(self._on_inflection_spin_changed)

        row_infl_coord.addWidget(self.spin_node_x, 1)
        row_infl_coord.addWidget(self.spin_node_y, 1)
        infl_lay.addLayout(row_infl_coord)

        row_infl_btns = QHBoxLayout()
        self.btn_add_inflection = QPushButton(_t("rut_btn_add"))
        self.btn_add_inflection.setToolTip(_t("rut_btn_add_tip"))
        self.btn_add_inflection.clicked.connect(self._on_add_inflection_clicked)

        self.btn_del_inflection = QPushButton(_t("rut_btn_remove"))
        self.btn_del_inflection.setToolTip(_t("rut_btn_remove_tip"))
        self.btn_del_inflection.clicked.connect(self._on_del_inflection_clicked)

        self.btn_snap_node = QPushButton(_t("rut_btn_snap_node"))
        self.btn_snap_node.setToolTip(_t("rut_btn_snap_node_tip"))
        self.btn_snap_node.clicked.connect(self._on_snap_node_clicked)

        row_infl_btns.addWidget(self.btn_add_inflection)
        row_infl_btns.addWidget(self.btn_del_inflection)
        row_infl_btns.addWidget(self.btn_snap_node)
        infl_lay.addLayout(row_infl_btns)

        insp_layout.addWidget(inflection_box)

        # 4. Dinámica y Tiempo
        time_box = QGroupBox(_t("rut_grp_time"))
        time_box.setStyleSheet("QGroupBox { font-size: 10px; color: #8B949E; border: 1px solid #30363D; border-radius: 4px; margin-top: 6px; padding-top: 6px; } QGroupBox::title { subcontrol-origin: margin; left: 8px; }")
        time_lay = QVBoxLayout(time_box)
        time_lay.setContentsMargins(8, 6, 8, 6)
        time_lay.setSpacing(4)

        row_t = QHBoxLayout()
        row_t.addWidget(QLabel(_t("rut_time")))
        self.spin_hour = QSpinBox()
        self.spin_hour.setRange(0, 23)
        self.spin_hour.setSuffix("h")
        self.spin_minute = QSpinBox()
        self.spin_minute.setRange(0, 59)
        self.spin_minute.setSingleStep(10)
        self.spin_minute.setSuffix("m")
        row_t.addWidget(self.spin_hour)
        row_t.addWidget(self.spin_minute)
        row_t.addWidget(QLabel(_t("rut_wait")))
        self.spin_delay = QSpinBox()
        self.spin_delay.setRange(0, 720)
        self.spin_delay.setSingleStep(5)
        self.spin_delay.setSuffix(" min")
        row_t.addWidget(self.spin_delay)
        time_lay.addLayout(row_t)

        row_v = QHBoxLayout()
        row_v.addWidget(QLabel(_t("rut_view")))
        self.combo_dir = QComboBox()
        self.combo_dir.addItem(_t("rut_dir_down"), DIR_DOWN)
        self.combo_dir.addItem(_t("rut_dir_up"), DIR_UP)
        self.combo_dir.addItem(_t("rut_dir_left"), DIR_LEFT)
        self.combo_dir.addItem(_t("rut_dir_right"), DIR_RIGHT)
        self.combo_dir.addItem(_t("rut_dir_face"), DIR_FACE)
        row_v.addWidget(self.combo_dir, 1)

        row_v.addWidget(QLabel(_t("rut_speed")))
        self.combo_speed = QComboBox()
        self.combo_speed.addItem(_t("rut_speed_normal"), 1.0)
        self.combo_speed.addItem(_t("rut_speed_slow"), 0.5)
        self.combo_speed.addItem(_t("rut_speed_light"), 1.5)
        self.combo_speed.addItem(_t("rut_speed_rush"), 2.0)
        row_v.addWidget(self.combo_speed, 1)
        time_lay.addLayout(row_v)
        insp_layout.addWidget(time_box)

        # 5. Botones de acción rápida
        insp_btn_lay = QHBoxLayout()
        self.btn_snap_tiles = QPushButton(_t("rut_btn_snap_tiles"))
        self.btn_snap_tiles.setToolTip(_t("rut_btn_snap_tiles_tip"))
        self.btn_snap_tiles.clicked.connect(self._on_snap_to_walkable_clicked)

        self.btn_recalc_path = QPushButton(_t("rut_btn_recalc"))
        self.btn_recalc_path.setStyleSheet("background-color: #1F6FEB; color: white; font-weight: bold;")
        self.btn_recalc_path.clicked.connect(self._on_recalc_a_star_clicked)

        self.btn_toggle_loop = QPushButton(_t("rut_btn_loop_mode"))
        self.btn_toggle_loop.setToolTip(_t("rut_btn_loop_tip"))
        self.btn_toggle_loop.clicked.connect(self._on_toggle_loop_clicked)

        insp_btn_lay.addWidget(self.btn_snap_tiles)
        insp_btn_lay.addWidget(self.btn_recalc_path)
        insp_btn_lay.addWidget(self.btn_toggle_loop)
        insp_layout.addLayout(insp_btn_lay)

        # Conectar señales para auto-ajuste de malla en tiempo real
        self.spin_ax.valueChanged.connect(self._on_auto_path_change)
        self.spin_ay.valueChanged.connect(self._on_auto_path_change)
        self.spin_bx.valueChanged.connect(self._on_auto_path_change)
        self.spin_by.valueChanged.connect(self._on_auto_path_change)
        self.spin_hour.valueChanged.connect(self._on_auto_path_change)
        self.spin_minute.valueChanged.connect(self._on_auto_path_change)
        self.spin_delay.valueChanged.connect(self._on_auto_path_change)
        self.combo_dir.currentIndexChanged.connect(self._on_auto_path_change)
        self.combo_speed.currentIndexChanged.connect(self._on_auto_path_change)

    def _toggle_floating_inspector(self, checked: bool):
        if hasattr(self, "floating_inspector") and self.floating_inspector:
            self.floating_inspector.setVisible(checked)
            if checked and not getattr(self.floating_inspector, "_user_moved", False):
                self._reposition_floating_inspector()

    def _reposition_floating_inspector(self):
        if not hasattr(self, "floating_inspector") or not self.floating_inspector:
            return
        if getattr(self.floating_inspector, "_user_moved", False):
            return
        if self.route_canvas and self.route_canvas.isVisible():
            canvas_rect = self.route_canvas.geometry()
            global_pt = self.route_canvas.mapToGlobal(QPoint(max(10, canvas_rect.width() - self.floating_inspector.width() - 30), 40))
            self.floating_inspector.move(global_pt)

    def _on_edit_step_clicked(self):
        """Cambia a la pestaña de mapa y asegura que el inspector flotante esté visible sin bloquear su posición."""
        self.right_tabs.setCurrentIndex(0)
        self.act_rc_inspector.setChecked(True)
        self.floating_inspector.show()
        self.floating_inspector.raise_()
        self.floating_inspector.activateWindow()
        if not getattr(self.floating_inspector, "_user_moved", False):
            self._reposition_floating_inspector()

    def closeEvent(self, event):
        if hasattr(self, "floating_inspector") and self.floating_inspector:
            self.floating_inspector.close()
        super().closeEvent(event)

    def _on_open_in_map_editor_clicked(self):
        """Abre el mapa activo en ventana dedicada del Editor de Mapas de FOMT Studio."""
        target_map_id = 0
        rows = self.table_segments.selectionModel().selectedRows()
        if rows and len(self.current_segments) > 0:
            row = rows[0].row()
            if row < len(self.current_segments):
                target_map_id = self.current_segments[row].get("map_id", 0)
        elif self.combo_filter_map.currentData() is not None:
            target_map_id = self.combo_filter_map.currentData()

        base_id, _ = unpack_fomt_map_id(target_map_id)
        header_id = get_map_header_id_for_event_map(base_id)
        if header_id is None:
            header_id = base_id

        # Intentar invocar el método open_map_editor de la ventana principal de FOMT Studio
        main_app = None
        for candidate in [self.parent(), self.window(), getattr(self.window(), 'orig_parent', None)]:
            if candidate and hasattr(candidate, "open_map_editor"):
                main_app = candidate
                break

        if main_app:
            main_app.open_map_editor(header_id)
            return

        QMessageBox.information(
            self, "Editor de Mapas",
            f" Mapa: {get_map_display_name(base_id)} (Header ID: {header_id})."
        )

    def _on_segment_selected(self):
        rows = self.table_segments.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        if row >= len(self.current_segments):
            return

        seg = self.current_segments[row]

        # Actualizar formulario del inspector bloqueando señales para evitar recálculos redundantes
        self._updating_ui = True
        try:
            self.spin_ax.setValue(seg["ax"])
            self.spin_ay.setValue(seg["ay"])
            self.spin_bx.setValue(seg["bx"])
            self.spin_by.setValue(seg["by"])
            self.spin_delay.setValue(seg["delay_val"])
            self.spin_hour.setValue(seg["time_val"] // 60)
            self.spin_minute.setValue(seg["time_val"] % 60)

            idx_dir = self.combo_dir.findData(seg["dir"])
            if idx_dir >= 0:
                self.combo_dir.setCurrentIndex(idx_dir)

            if hasattr(self, "combo_seg_map"):
                idx_map = self.combo_seg_map.findData(seg["base_map_id"])
                if idx_map >= 0:
                    self.combo_seg_map.setCurrentIndex(idx_map)

            speed_val = seg.get("speed_val", 1.0)
            idx_spd = self.combo_speed.findData(speed_val)
            if idx_spd >= 0:
                self.combo_speed.setCurrentIndex(idx_spd)

            is_loop = seg.get("is_loop", False) or (len(seg.get("path_nodes", [])) > 1 and seg["path_nodes"][0] == seg["path_nodes"][-1])
            loop_badge = " - " + _t("rut_loop") if is_loop else ""
            self.lbl_insp_badge.setText(_t("rut_step_badge", n=row + 1, loop=loop_badge, time=seg['time_str']))
            if is_loop:
                num_legs = max(1, len(seg.get("path_nodes", [])) - 1)
                self.lbl_auto_status.setText(_t("rut_loop_active", n=num_legs))
                self.lbl_auto_status.setStyleSheet("color: #A371F7; font-size: 10px; font-weight: bold; padding-top: 2px;")
                self.btn_toggle_loop.setText(_t("rut_open_loop"))
                self.spin_bx.setEnabled(False)
                self.spin_by.setEnabled(False)
                self.spin_bx.setToolTip(_t("rut_b_locked_tip"))
                self.spin_by.setToolTip(_t("rut_b_locked_tip"))
                self.rb_target_b.setEnabled(False)
                self.rb_target_b.setToolTip(_t("rut_b_locked_rb_tip"))
                if self.rb_target_b.isChecked():
                    self.rb_target_inflection.setChecked(True)
            else:
                self.lbl_auto_status.setText(_t("rut_auto_adjust"))
                self.lbl_auto_status.setStyleSheet("color: #3FB950; font-size: 10px; font-weight: bold; padding-top: 2px;")
                self.btn_toggle_loop.setText(_t("rut_close_loop"))
                self.spin_bx.setEnabled(True)
                self.spin_by.setEnabled(True)
                self.spin_bx.setToolTip("")
                self.spin_by.setToolTip("")
                self.rb_target_b.setEnabled(True)
                self.rb_target_b.setToolTip("")
        finally:
            self._updating_ui = False

        # Resaltar en el Macromapa el tramo específico
        self.macro_view.set_active_orchestrated_segments(self.current_segments, highlight_id=seg["id"])

        # Actualizar mapa en el RouteMapCanvas y enfocar el tramo
        self.route_canvas.load_map_view(seg["map_id"])
        self.lbl_canvas_map_name.setText(f" {seg['map_name']}")
        self.route_canvas.set_route_segments(self.current_segments, highlight_id=seg["id"])

        # Centrar suavemente la cámara sobre las coordenadas del tramo seleccionado
        if seg.get("ax") or seg.get("ay"):
            self.route_canvas.center_on_point(seg["ax"], seg["ay"])
        elif seg.get("bx") or seg.get("by"):
            self.route_canvas.center_on_point(seg["bx"], seg["by"])

        # Sincronizar el selector de mapa del filtro si estamos en modo por mapa
        if self.current_mode == "BY_MAP":
            idx_m = self.combo_filter_map.findData(seg["base_map_id"])
            if idx_m >= 0 and self.combo_filter_map.currentIndex() != idx_m:
                self.combo_filter_map.blockSignals(True)
                self.combo_filter_map.setCurrentIndex(idx_m)
                self.combo_filter_map.blockSignals(False)

        # Asegurar posicionamiento del inspector flotante
        if self.act_rc_inspector.isChecked():
            self.floating_inspector.show()
            self._reposition_floating_inspector()

        # Poblar controles de puntos de inflexión
        self._populate_inflection_combo(seg["wp_ref"])

    def _on_segment_map_changed(self, index: int):
        """Permite al usuario reasignar el mapa canónico del hito seleccionado."""
        if self._updating_ui:
            return
        new_mid = self.combo_seg_map.currentData()
        if new_mid is None:
            return
        rows = self.table_segments.selectionModel().selectedRows()
        if not rows or not self.current_schedule:
            return
        row = rows[0].row()
        if row >= len(self.current_schedule.waypoints):
            return
        wp = self.current_schedule.waypoints[row]
        wp.map_id = new_mid
        wp.is_edited = True
        self._refresh_npc_segments()
        self.table_segments.selectRow(row)

    def _on_macro_map_selected(self, map_id: int):
        """Responde a clics sobre nodos del Macromapa para sincronizar el visor y filtro."""
        base_id, _ = unpack_fomt_map_id(map_id)
        self.route_canvas.load_map_view(base_id)
        self.lbl_canvas_map_name.setText(f" {get_map_display_name(base_id)}")

        if self.current_mode == "BY_MAP":
            idx = self.combo_filter_map.findData(base_id)
            if idx >= 0:
                self.combo_filter_map.setCurrentIndex(idx)
        else:
            # En modo Por Aldeano, si este NPC tiene algún tramo en este mapa, seleccionarlo
            for r, s in enumerate(self.current_segments):
                if (s.get("base_map_id", 0) & 0xFF) == base_id:
                    self.table_segments.selectRow(r)
                    break

    def _on_recalc_a_star_clicked(self):
        """Fuerza un recálculo A* completo desde Inicio (A) hasta Destino (B)."""
        self._on_auto_path_change(force_recalc=True)

    def _populate_inflection_combo(self, wp: RoutineWaypoint, active_node_idx: Optional[int] = None):
        """Puebla el selector de puntos de inflexión intermedios."""
        if not hasattr(self, "combo_inflection_nodes"):
            return
        self.combo_inflection_nodes.blockSignals(True)
        self.combo_inflection_nodes.clear()

        mid_nodes = []
        if wp and wp.path_nodes and len(wp.path_nodes) > 2:
            mid_nodes = [(idx, pt) for idx, pt in enumerate(wp.path_nodes) if 0 < idx < len(wp.path_nodes) - 1]

        if mid_nodes:
            sel_idx = 0
            for list_i, (node_idx, (nx, ny)) in enumerate(mid_nodes):
                self.combo_inflection_nodes.addItem(_t("rut_point_item", n=node_idx, x=nx, y=ny), node_idx)
                if active_node_idx is not None and node_idx == active_node_idx:
                    sel_idx = list_i
            self.combo_inflection_nodes.setCurrentIndex(sel_idx)
            cur_node_idx = self.combo_inflection_nodes.currentData()
            cur_pt = wp.path_nodes[cur_node_idx]
            self.spin_node_x.blockSignals(True)
            self.spin_node_y.blockSignals(True)
            self.spin_node_x.setValue(cur_pt[0])
            self.spin_node_y.setValue(cur_pt[1])
            self.spin_node_x.setEnabled(True)
            self.spin_node_y.setEnabled(True)
            self.btn_del_inflection.setEnabled(True)
            self.btn_snap_node.setEnabled(True)
            self.spin_node_x.blockSignals(False)
            self.spin_node_y.blockSignals(False)
        else:
            self.combo_inflection_nodes.addItem(_t("rut_no_points"), -1)
            self.spin_node_x.setEnabled(False)
            self.spin_node_y.setEnabled(False)
            self.btn_del_inflection.setEnabled(False)
            self.btn_snap_node.setEnabled(False)

        self.combo_inflection_nodes.blockSignals(False)

    def _on_inflection_combo_changed(self, index: int):
        node_idx = self.combo_inflection_nodes.currentData()
        if node_idx is None or node_idx <= 0:
            return
        rows = self.table_segments.selectionModel().selectedRows()
        if not rows or not self.current_segments:
            return
        row = rows[0].row()
        wp = self.current_segments[row]["wp_ref"]
        if 0 < node_idx < len(wp.path_nodes) - 1:
            nx, ny = wp.path_nodes[node_idx]
            self.spin_node_x.blockSignals(True)
            self.spin_node_y.blockSignals(True)
            self.spin_node_x.setValue(nx)
            self.spin_node_y.setValue(ny)
            self.spin_node_x.blockSignals(False)
            self.spin_node_y.blockSignals(False)
            self.route_canvas.active_node_idx = node_idx
            self.route_canvas.overlay_item.update()

    def _on_inflection_spin_changed(self):
        if getattr(self, "_updating_ui", False):
            return
        node_idx = self.combo_inflection_nodes.currentData()
        if node_idx is None or node_idx <= 0:
            return
        rows = self.table_segments.selectionModel().selectedRows()
        if not rows or not self.current_segments:
            return
        row = rows[0].row()
        seg = self.current_segments[row]
        wp = seg["wp_ref"]
        is_loop = seg.get("is_loop", False) or (len(wp.path_nodes) > 1 and wp.path_nodes[0] == wp.path_nodes[-1])

        if 0 < node_idx < len(wp.path_nodes) - 1:
            nx = self.spin_node_x.value()
            ny = self.spin_node_y.value()
            wp.path_nodes[node_idx] = (nx, ny)
            wp.path_nodes = ensure_orthogonal_path(wp.path_nodes)
            if is_loop and (not wp.path_nodes or wp.path_nodes[0] != wp.path_nodes[-1]):
                wp.path_nodes.append(wp.path_nodes[0])
            wp.is_edited = True
            wp.raw_bytes = None
            seg["path_nodes"] = list(wp.path_nodes)
            if is_loop:
                seg["is_loop"] = True
                wp.dest_x, wp.dest_y = wp.path_nodes[0]
                seg["bx"], seg["by"] = wp.path_nodes[0]
            self._on_auto_path_change(force_recalc=False)

    def _on_canvas_node_selected(self, node_idx: int, x: int, y: int):
        rows = self.table_segments.selectionModel().selectedRows()
        if not rows or not self.current_segments:
            return
        row = rows[0].row()
        seg = self.current_segments[row]
        wp = seg["wp_ref"]
        is_loop = seg.get("is_loop", False) or (len(wp.path_nodes) > 1 and wp.path_nodes[0] == wp.path_nodes[-1])

        if node_idx == 0 or (is_loop and node_idx == len(wp.path_nodes) - 1):
            self.rb_target_a.setChecked(True)
        elif node_idx == len(wp.path_nodes) - 1:
            self.rb_target_b.setChecked(True)
        else:
            self.rb_target_inflection.setChecked(True)
            self._populate_inflection_combo(wp, active_node_idx=node_idx)

    def _on_canvas_node_moved(self, node_idx: int, x: int, y: int):
        rows = self.table_segments.selectionModel().selectedRows()
        if not rows or not self.current_segments:
            return
        row = rows[0].row()
        seg = self.current_segments[row]
        wp = seg["wp_ref"]
        is_loop = seg.get("is_loop", False) or (len(wp.path_nodes) > 1 and wp.path_nodes[0] == wp.path_nodes[-1])

        if 0 <= node_idx < len(wp.path_nodes):
            wp.is_edited = True
            wp.raw_bytes = None
            if is_loop and (node_idx == 0 or node_idx == len(wp.path_nodes) - 1):
                wp.path_nodes[0] = (x, y)
                wp.path_nodes[-1] = (x, y)
                self.spin_ax.blockSignals(True)
                self.spin_ay.blockSignals(True)
                self.spin_bx.blockSignals(True)
                self.spin_by.blockSignals(True)
                self.spin_ax.setValue(x)
                self.spin_ay.setValue(y)
                self.spin_bx.setValue(x)
                self.spin_by.setValue(y)
                self.spin_ax.blockSignals(False)
                self.spin_ay.blockSignals(False)
                self.spin_bx.blockSignals(False)
                self.spin_by.blockSignals(False)
                wp.spawn_x, wp.spawn_y = x, y
                wp.dest_x, wp.dest_y = x, y
                seg["ax"], seg["ay"] = x, y
                seg["bx"], seg["by"] = x, y
            elif node_idx == 0:
                wp.path_nodes[0] = (x, y)
                self.spin_ax.blockSignals(True)
                self.spin_ay.blockSignals(True)
                self.spin_ax.setValue(x)
                self.spin_ay.setValue(y)
                self.spin_ax.blockSignals(False)
                self.spin_ay.blockSignals(False)
                wp.spawn_x, wp.spawn_y = x, y
                seg["ax"], seg["ay"] = x, y
            elif node_idx == len(wp.path_nodes) - 1:
                wp.path_nodes[-1] = (x, y)
                self.spin_bx.blockSignals(True)
                self.spin_by.blockSignals(True)
                self.spin_bx.setValue(x)
                self.spin_by.setValue(y)
                self.spin_bx.blockSignals(False)
                self.spin_by.blockSignals(False)
                wp.dest_x, wp.dest_y = x, y
                seg["bx"], seg["by"] = x, y
            else:
                wp.path_nodes[node_idx] = (x, y)
                self.spin_node_x.blockSignals(True)
                self.spin_node_y.blockSignals(True)
                self.spin_node_x.setValue(x)
                self.spin_node_y.setValue(y)
                self.spin_node_x.blockSignals(False)
                self.spin_node_y.blockSignals(False)

    def _on_canvas_node_drag_finished(self, node_idx: int, x: int, y: int):
        rows = self.table_segments.selectionModel().selectedRows()
        if not rows or not self.current_segments:
            return
        row = rows[0].row()
        seg = self.current_segments[row]
        wp = seg["wp_ref"]
        is_loop = seg.get("is_loop", False) or (len(wp.path_nodes) > 1 and wp.path_nodes[0] == wp.path_nodes[-1])

        wp.path_nodes = ensure_orthogonal_path(wp.path_nodes)
        if is_loop:
            if not wp.path_nodes or len(wp.path_nodes) < 2:
                wp.path_nodes = [(x, y), (x, y)]
            elif wp.path_nodes[0] != wp.path_nodes[-1]:
                wp.path_nodes.append(wp.path_nodes[0])
            wp.dest_x, wp.dest_y = wp.path_nodes[0]
            wp.spawn_x, wp.spawn_y = wp.path_nodes[0]
            seg["ax"], seg["ay"] = wp.path_nodes[0]
            seg["bx"], seg["by"] = wp.path_nodes[0]
            seg["is_loop"] = True

        wp.is_edited = True
        wp.raw_bytes = None
        seg["path_nodes"] = list(wp.path_nodes)
        self._populate_inflection_combo(wp, node_idx if (0 < node_idx < len(wp.path_nodes) - 1) else None)
        self._on_auto_path_change(force_recalc=False)

    def _on_canvas_node_inserted(self, insert_idx: int, x: int, y: int):
        rows = self.table_segments.selectionModel().selectedRows()
        if not rows or not self.current_segments:
            return
        row = rows[0].row()
        seg = self.current_segments[row]
        wp = seg["wp_ref"]
        is_loop = seg.get("is_loop", False) or (len(wp.path_nodes) > 1 and wp.path_nodes[0] == wp.path_nodes[-1])

        if hasattr(self.route_canvas, "pathfinder") and self.route_canvas.pathfinder:
            grid = self.route_canvas.pathfinder.get_map_grid(seg["map_id"])
            if grid:
                tx, ty = self.route_canvas.pathfinder.snap_to_walkable(grid, x, y)
                x, y = tx * 8 + 4, ty * 8 + 4

        if is_loop:
            if insert_idx <= 0:
                insert_idx = 1
            if insert_idx >= len(wp.path_nodes):
                insert_idx = max(1, len(wp.path_nodes) - 1)

        wp.path_nodes.insert(insert_idx, (x, y))
        wp.path_nodes = ensure_orthogonal_path(wp.path_nodes)
        if is_loop and (not wp.path_nodes or wp.path_nodes[0] != wp.path_nodes[-1]):
            wp.path_nodes.append(wp.path_nodes[0])

        wp.is_edited = True
        wp.raw_bytes = None
        seg["path_nodes"] = list(wp.path_nodes)
        if is_loop:
            seg["is_loop"] = True
            wp.dest_x, wp.dest_y = wp.path_nodes[0]
            seg["bx"], seg["by"] = wp.path_nodes[0]

        self._populate_inflection_combo(wp, insert_idx)
        self._on_auto_path_change(force_recalc=False)
        self.status_bar.showMessage(_t("rut_st_point_inserted", n=insert_idx, x=x, y=y), 3000)

    def _on_canvas_node_deleted(self, node_idx: int):
        rows = self.table_segments.selectionModel().selectedRows()
        if not rows or not self.current_segments:
            return
        row = rows[0].row()
        seg = self.current_segments[row]
        wp = seg["wp_ref"]
        is_loop = seg.get("is_loop", False) or (len(wp.path_nodes) > 1 and wp.path_nodes[0] == wp.path_nodes[-1])

        if 0 < node_idx < len(wp.path_nodes) - 1:
            del wp.path_nodes[node_idx]
            wp.path_nodes = ensure_orthogonal_path(wp.path_nodes)
            if is_loop and (not wp.path_nodes or wp.path_nodes[0] != wp.path_nodes[-1]):
                if len(wp.path_nodes) >= 1:
                    wp.path_nodes.append(wp.path_nodes[0])
            wp.is_edited = True
            wp.raw_bytes = None
            seg["path_nodes"] = list(wp.path_nodes)
            if is_loop:
                seg["is_loop"] = True
                wp.dest_x, wp.dest_y = wp.path_nodes[0]
                seg["bx"], seg["by"] = wp.path_nodes[0]

            self._populate_inflection_combo(wp)
            self._on_auto_path_change(force_recalc=False)
            self.status_bar.showMessage(_t("rut_st_point_removed", n=node_idx), 3000)

    def _on_add_inflection_clicked(self):
        rows = self.table_segments.selectionModel().selectedRows()
        if not rows or not self.current_segments:
            return
        row = rows[0].row()
        seg = self.current_segments[row]
        wp = seg["wp_ref"]

        if len(wp.path_nodes) >= 2:
            p0 = wp.path_nodes[0]
            p1 = wp.path_nodes[1]
            mx = (p0[0] + p1[0]) // 2
            my = (p0[1] + p1[1]) // 2
            self._on_canvas_node_inserted(1, mx, my)
        else:
            self._on_canvas_node_inserted(1, wp.spawn_x + 16, wp.spawn_y + 16)

    def _on_del_inflection_clicked(self):
        node_idx = self.combo_inflection_nodes.currentData()
        if node_idx is not None and node_idx > 0:
            self._on_canvas_node_deleted(node_idx)

    def _on_snap_node_clicked(self):
        node_idx = self.combo_inflection_nodes.currentData()
        if node_idx is None or node_idx <= 0:
            return
        rows = self.table_segments.selectionModel().selectedRows()
        if not rows or not self.current_segments:
            return
        row = rows[0].row()
        seg = self.current_segments[row]
        wp = seg["wp_ref"]
        is_loop = seg.get("is_loop", False) or (len(wp.path_nodes) > 1 and wp.path_nodes[0] == wp.path_nodes[-1])

        if 0 < node_idx < len(wp.path_nodes) - 1:
            nx, ny = wp.path_nodes[node_idx]
            if hasattr(self.route_canvas, "pathfinder") and self.route_canvas.pathfinder:
                grid = self.route_canvas.pathfinder.get_map_grid(seg["map_id"])
                if grid:
                    tx, ty = self.route_canvas.pathfinder.snap_to_walkable(grid, nx, ny)
                    snapped_x, snapped_y = tx * 8 + 4, ty * 8 + 4
                    wp.path_nodes[node_idx] = (snapped_x, snapped_y)
                    wp.path_nodes = ensure_orthogonal_path(wp.path_nodes)
                    if is_loop and (not wp.path_nodes or wp.path_nodes[0] != wp.path_nodes[-1]):
                        wp.path_nodes.append(wp.path_nodes[0])
                    wp.is_edited = True
                    wp.raw_bytes = None
                    seg["path_nodes"] = list(wp.path_nodes)
                    if is_loop:
                        seg["is_loop"] = True
                        wp.dest_x, wp.dest_y = wp.path_nodes[0]
                        seg["bx"], seg["by"] = wp.path_nodes[0]
                    self._populate_inflection_combo(wp, node_idx)
                    self._on_auto_path_change(force_recalc=False)
                    self.status_bar.showMessage(_t("rut_st_point_snapped", n=node_idx, x=snapped_x, y=snapped_y), 3000)

    def _on_toggle_loop_clicked(self):
        """Alterna el tramo actual entre recorrido lineal A  B o circuito cerrado en bucle (B = A)."""
        rows = self.table_segments.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        if row >= len(self.current_segments):
            return

        seg = self.current_segments[row]
        wp = seg["wp_ref"]
        is_loop = seg.get("is_loop", False) or (len(wp.path_nodes) > 1 and wp.path_nodes[0] == wp.path_nodes[-1])

        if not is_loop:
            ax, ay = wp.spawn_x, wp.spawn_y
            bx, by = wp.dest_x, wp.dest_y
            if (ax, ay) == (bx, by) or len(wp.path_nodes) <= 1:
                # Circuito rectangular básico de 24x24 px sobre tiles caminables
                nodes = [(ax, ay), (ax + 24, ay), (ax + 24, ay + 24), (ax, ay + 24), (ax, ay)]
            else:
                # Volver de B hacia A para cerrar el circuito
                return_nodes = self.route_canvas.get_orthogonal_nodes(wp.map_id, bx, by, ax, ay)
                nodes = list(wp.path_nodes) + (return_nodes[1:] if return_nodes else [(ax, ay)])
            wp.dest_x = ax
            wp.dest_y = ay
            wp.path_nodes = ensure_orthogonal_path(nodes)
            if wp.path_nodes[0] != wp.path_nodes[-1]:
                wp.path_nodes.append(wp.path_nodes[0])
            wp.is_edited = True
            wp.raw_bytes = None
            seg["is_loop"] = True
            self.spin_bx.setValue(ax)
            self.spin_by.setValue(ay)
            self.spin_bx.setEnabled(False)
            self.spin_by.setEnabled(False)
            self.rb_target_b.setEnabled(False)
            if self.rb_target_b.isChecked():
                self.rb_target_inflection.setChecked(True)
            self.status_bar.showMessage(_t("rut_st_to_loop"), 3000)
        else:
            # Abrir bucle: separar B eliminando el último nodo de retorno
            if len(wp.path_nodes) >= 2:
                prev_node = wp.path_nodes[-2]
                wp.dest_x = prev_node[0]
                wp.dest_y = prev_node[1]
                wp.path_nodes = wp.path_nodes[:-1]
                wp.is_edited = True
                wp.raw_bytes = None
                seg["is_loop"] = False
                self.spin_bx.setValue(prev_node[0])
                self.spin_by.setValue(prev_node[1])
                self.spin_bx.setEnabled(True)
                self.spin_by.setEnabled(True)
                self.rb_target_b.setEnabled(True)
                self.status_bar.showMessage(_t("rut_st_loop_opened"), 3000)

        if self.current_mode == "BY_NPC":
            self._refresh_npc_segments()
        else:
            self._refresh_map_segments()
        self.table_segments.selectRow(row)

    def _on_canvas_point_clicked(self, x: int, y: int):
        """Asigna la coordenada del clic a Inicio (A), Destino (B) o Inflexión (C) y auto-ajusta la malla de caminata."""
        rows = self.table_segments.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        if row >= len(self.current_segments):
            return

        seg = self.current_segments[row]
        wp = seg["wp_ref"]
        is_loop = seg.get("is_loop", False) or (len(wp.path_nodes) > 1 and wp.path_nodes[0] == wp.path_nodes[-1])

        # Ajustar automáticamente al tile caminable más cercano en la matriz de colisión
        if hasattr(self.route_canvas, "pathfinder") and self.route_canvas.pathfinder:
            grid = self.route_canvas.pathfinder.get_map_grid(seg["map_id"])
            if grid:
                tx, ty = self.route_canvas.pathfinder.snap_to_walkable(grid, x, y)
                x, y = tx * 8 + 4, ty * 8 + 4

        if is_loop:
            if self.rb_target_a.isChecked() or self.rb_target_b.isChecked():
                # Trasladar el circuito completo al nuevo punto de origen
                old_ax, old_ay = wp.spawn_x, wp.spawn_y
                dx = x - old_ax
                dy = y - old_ay
                self._updating_ui = True
                self.spin_ax.setValue(x)
                self.spin_ay.setValue(y)
                self.spin_bx.setValue(x)
                self.spin_by.setValue(y)
                self._updating_ui = False
                wp.path_nodes = [(nx + dx, ny + dy) for nx, ny in wp.path_nodes]
                wp.path_nodes[0] = (x, y)
                wp.path_nodes[-1] = (x, y)
                wp.spawn_x, wp.spawn_y = x, y
                wp.dest_x, wp.dest_y = x, y
                wp.is_edited = True
                wp.raw_bytes = None
                seg["ax"], seg["ay"] = x, y
                seg["bx"], seg["by"] = x, y
                seg["path_nodes"] = list(wp.path_nodes)
                seg["is_loop"] = True
                self._populate_inflection_combo(wp)
                self._on_auto_path_change(force_recalc=False)
                self.status_bar.showMessage(_t("rut_st_loop_moved", x=x, y=y), 3500)
                return
            else:
                # Inflexión (C) en bucle: insertar antes del cierre del bucle
                insert_idx = max(1, len(wp.path_nodes) - 1)
                wp.path_nodes.insert(insert_idx, (x, y))
                wp.path_nodes = ensure_orthogonal_path(wp.path_nodes)
                if wp.path_nodes[0] != wp.path_nodes[-1]:
                    wp.path_nodes.append(wp.path_nodes[0])
                wp.dest_x, wp.dest_y = wp.path_nodes[0]
                wp.is_edited = True
                wp.raw_bytes = None
                seg["path_nodes"] = list(wp.path_nodes)
                seg["is_loop"] = True
                self._populate_inflection_combo(wp, insert_idx)
                self._on_auto_path_change(force_recalc=False)
                self.status_bar.showMessage(_t("rut_st_loop_point_added", x=x, y=y), 3500)
                return

        # Ruta lineal normal (no bucle)
        if self.rb_target_a.isChecked():
            target_name = "Inicio (A)"
            self.spin_ax.setValue(x)
            self.spin_ay.setValue(y)
        elif self.rb_target_b.isChecked():
            target_name = "Destino (B)"
            self.spin_bx.setValue(x)
            self.spin_by.setValue(y)
        else:
            # Inflexión (C)
            target_name = "Punto de Inflexión"
            if len(wp.path_nodes) >= 2:
                insert_idx = len(wp.path_nodes) - 1
                wp.path_nodes.insert(insert_idx, (x, y))
            else:
                wp.path_nodes.append((x, y))
                insert_idx = len(wp.path_nodes) - 1
            wp.path_nodes = ensure_orthogonal_path(wp.path_nodes)
            wp.is_edited = True
            wp.raw_bytes = None
            seg["path_nodes"] = list(wp.path_nodes)
            self._populate_inflection_combo(wp, insert_idx)
            self._on_auto_path_change(force_recalc=False)

        self.status_bar.showMessage(
            f" Coordenada caminable ({x}, {y}) fijada en {target_name}. "
            f"Malla de caminata AWSD sincronizada.", 3500
        )

    def _on_auto_path_change(self, force_recalc: bool = False):
        """
        Sincroniza en tiempo real los nodos de la ruta ortogonal AWSD,
        preservando puntos de inflexión manuales y manteniendo invariantes los circuitos en bucle.
        """
        if getattr(self, "_updating_ui", False):
            return

        rows = self.table_segments.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        if row >= len(self.current_segments):
            return

        seg = self.current_segments[row]
        wp = seg["wp_ref"]

        ax = self.spin_ax.value()
        ay = self.spin_ay.value()
        is_loop = seg.get("is_loop", False) or (len(wp.path_nodes) > 1 and wp.path_nodes[0] == wp.path_nodes[-1])

        if is_loop:
            # En rutas en bucle, B siempre equivale a A
            bx, by = ax, ay
            self.spin_bx.blockSignals(True)
            self.spin_by.blockSignals(True)
            self.spin_bx.setValue(ax)
            self.spin_by.setValue(ay)
            self.spin_bx.blockSignals(False)
            self.spin_by.blockSignals(False)

            if len(wp.path_nodes) > 2:
                dx = ax - wp.path_nodes[0][0]
                dy = ay - wp.path_nodes[0][1]
                if dx != 0 or dy != 0:
                    nodes = [(nx + dx, ny + dy) for nx, ny in wp.path_nodes]
                    nodes[0] = (ax, ay)
                    nodes[-1] = (ax, ay)
                else:
                    existing_mid = wp.path_nodes[1:-1]
                    candidate = [(ax, ay)] + existing_mid + [(ax, ay)]
                    nodes = ensure_orthogonal_path(candidate)
                    if nodes[0] != nodes[-1]:
                        nodes.append(nodes[0])
            else:
                nodes = [(ax, ay), (ax + 24, ay), (ax + 24, ay + 24), (ax, ay + 24), (ax, ay)]
        else:
            bx = self.spin_bx.value()
            by = self.spin_by.value()

            # Recalcular ruta ortogonal AWSD respetando puntos de inflexión manuales
            if force_recalc or not wp.path_nodes or len(wp.path_nodes) <= 2:
                if (ax, ay) != (bx, by):
                    nodes = self.route_canvas.get_orthogonal_nodes(wp.map_id, ax, ay, bx, by)
                else:
                    nodes = [(ax, ay)]
            else:
                # Preservar los puntos de inflexión intermedios ya existentes
                existing_mid = wp.path_nodes[1:-1]
                candidate_nodes = [(ax, ay)] + existing_mid + [(bx, by)]
                nodes = ensure_orthogonal_path(candidate_nodes)

        wp.spawn_x = ax
        wp.spawn_y = ay
        wp.dest_x = bx
        wp.dest_y = by
        wp.path_nodes = nodes
        wp.is_edited = True
        wp.raw_bytes = None
        wp.spawn_dir = self.combo_dir.currentData()
        wp.time_val = self.spin_hour.value() * 60 + self.spin_minute.value()

        # Comprobar nuevamente condición de bucle
        is_loop = is_loop or (len(nodes) > 1 and nodes[0] == nodes[-1])

        # Distancia Manhattan real sobre nodos
        if len(nodes) > 1:
            dist = sum(
                abs(nodes[k][0] - nodes[k - 1][0]) + abs(nodes[k][1] - nodes[k - 1][1])
                for k in range(1, len(nodes))
            )
        else:
            dist = abs(bx - ax) + abs(by - ay)

        delay_val = self.spin_delay.value()
        speed_val = self.combo_speed.currentData() or 1.0

        # Actualizar estructura del segmento en memoria
        seg["ax"] = ax
        seg["ay"] = ay
        seg["bx"] = bx
        seg["by"] = by
        seg["dist"] = dist
        seg["time_val"] = wp.time_val
        seg["time_str"] = wp.time_to_str()
        seg["delay_val"] = delay_val
        seg["delay_str"] = f"{delay_val}m"
        seg["speed_val"] = speed_val
        seg["speed_str"] = f"{speed_val:.1f}x"
        seg["dir"] = wp.spawn_dir
        seg["path_nodes"] = list(nodes)
        seg["is_loop"] = is_loop

        # Actualizar fila de la tabla sin perder selección
        self.table_segments.blockSignals(True)
        it_lbl = self.table_segments.item(row, 0)
        if it_lbl:
            loop_badge = " " if is_loop else ""
            it_lbl.setText(f"#{row+1}{loop_badge}")
        it_a = self.table_segments.item(row, 3)
        if it_a: it_a.setText(f"({ax}, {ay})")
        it_b = self.table_segments.item(row, 4)
        if it_b:
            if is_loop:
                num_legs = max(1, len(nodes) - 1)
                it_b.setText(f" ({bx}, {by})")
                it_b.setToolTip(_t("rut_loop_tip", n=num_legs))
                it_b.setForeground(QColor("#A371F7"))
            else:
                it_b.setText(f"({bx}, {by})")
                it_b.setForeground(QColor("#F0F6FC"))
        it_dist = self.table_segments.item(row, 5)
        if it_dist: it_dist.setText(f"{dist} px")
        it_spd = self.table_segments.item(row, 6)
        if it_spd: it_spd.setText(f"{speed_val:.1f}x")
        it_delay = self.table_segments.item(row, 7)
        if it_delay: it_delay.setText(f"{delay_val}m")
        it_time = self.table_segments.item(row, 8)
        if it_time: it_time.setText(wp.time_to_str())
        self.table_segments.blockSignals(False)

        # Actualizar visualización en tiempo real en el lienzo
        self.route_canvas.set_route_segments(self.current_segments, highlight_id=seg["id"])
        self.macro_view.set_active_orchestrated_segments(self.current_segments, highlight_id=seg["id"])

        if is_loop:
            num_legs = max(1, len(nodes) - 1)
            self.lbl_auto_status.setText(_t("rut_loop_active", n=num_legs))
            self.lbl_auto_status.setStyleSheet("color: #A371F7; font-size: 10px; font-weight: bold; padding-top: 2px;")
            self.btn_toggle_loop.setText(_t("rut_open_loop"))
        else:
            self.lbl_auto_status.setText(_t("rut_nodes_synced", n=len(nodes)))
            self.lbl_auto_status.setStyleSheet("color: #3FB950; font-size: 10px; font-weight: bold; padding-top: 2px;")
            self.btn_toggle_loop.setText(_t("rut_close_loop"))

    def _on_snap_to_walkable_clicked(self):
        """Ajusta las coordenadas A y B directamente a los tiles transitables de la ROM."""
        rows = self.table_segments.selectionModel().selectedRows()
        if not rows or not self.current_segments:
            return
        row = rows[0].row()
        seg = self.current_segments[row]
        wp = seg["wp_ref"]
        is_loop = seg.get("is_loop", False) or (len(wp.path_nodes) > 1 and wp.path_nodes[0] == wp.path_nodes[-1])

        if hasattr(self.route_canvas, "pathfinder") and self.route_canvas.pathfinder:
            grid = self.route_canvas.pathfinder.get_map_grid(seg["map_id"])
            if grid:
                if is_loop:
                    tax, tay = self.route_canvas.pathfinder.snap_to_walkable(grid, self.spin_ax.value(), self.spin_ay.value())
                    new_ax, new_ay = tax * 8 + 4, tay * 8 + 4
                    dx = new_ax - wp.spawn_x
                    dy = new_ay - wp.spawn_y
                    wp.path_nodes = [(nx + dx, ny + dy) for nx, ny in wp.path_nodes]
                    wp.path_nodes[0] = (new_ax, new_ay)
                    wp.path_nodes[-1] = (new_ax, new_ay)
                    wp.spawn_x, wp.spawn_y = new_ax, new_ay
                    wp.dest_x, wp.dest_y = new_ax, new_ay
                    wp.is_edited = True
                    wp.raw_bytes = None
                    self._updating_ui = True
                    self.spin_ax.setValue(new_ax)
                    self.spin_ay.setValue(new_ay)
                    self.spin_bx.setValue(new_ax)
                    self.spin_by.setValue(new_ay)
                    self._updating_ui = False
                    seg["ax"], seg["ay"] = new_ax, new_ay
                    seg["bx"], seg["by"] = new_ax, new_ay
                    seg["path_nodes"] = list(wp.path_nodes)
                    seg["is_loop"] = True
                    self._populate_inflection_combo(wp)
                    self._on_auto_path_change(force_recalc=False)
                    self.status_bar.showMessage(_t("rut_st_loop_snapped"), 3000)
                    return

                tax, tay = self.route_canvas.pathfinder.snap_to_walkable(grid, self.spin_ax.value(), self.spin_ay.value())
                tbx, tby = self.route_canvas.pathfinder.snap_to_walkable(grid, self.spin_bx.value(), self.spin_by.value())
                self.spin_ax.setValue(tax * 8 + 4)
                self.spin_ay.setValue(tay * 8 + 4)
                self.spin_bx.setValue(tbx * 8 + 4)
                self.spin_by.setValue(tby * 8 + 4)
                self.status_bar.showMessage(_t("rut_st_ab_snapped"), 3000)

    def _on_apply_segment_vars(self):
        """Compatibilidad: invoca el auto-ajuste de ruta en tiempo real."""
        self._on_auto_path_change()

    def _on_calc_route_clicked(self):
        """Compatibilidad: invoca el recálculo A* ortogonal."""
        self._on_auto_path_change()

    def _on_add_waypoint(self):
        if not self.current_schedule:
            QMessageBox.warning(self, _t("msg_warning"), _t("rut_select_schedule"))
            return

        last_wp = self.current_schedule.waypoints[-1] if self.current_schedule.waypoints else None
        next_time = (last_wp.time_val + 60) if last_wp else 360
        
        # Si el último hito es un despawn (mapa 0x34 o coords 0,0), usar el mapa actualmente en pantalla
        if last_wp and (last_wp.map_id & 0xFF) != 0x34 and (last_wp.spawn_x > 0 or last_wp.spawn_y > 0):
            next_map = last_wp.map_id & 0xFF
            next_x = last_wp.spawn_x + 16
            next_y = last_wp.spawn_y + 16
        else:
            next_map = self.route_canvas.current_map_id if self.route_canvas.current_map_id is not None else 0x02
            next_x = 160
            next_y = 160

        new_wp = RoutineWaypoint(
            time_val=min(1439, next_time),
            spawn_dir=DIR_DOWN,
            spawn_x=next_x,
            spawn_y=next_y,
            map_id=next_map
        )
        self.current_schedule.waypoints.append(new_wp)
        self._refresh_npc_segments()
        self.table_segments.selectRow(len(self.current_schedule.waypoints) - 1)

    def _on_delete_waypoint(self):
        rows = self.table_segments.selectionModel().selectedRows()
        if not rows or not self.current_schedule:
            return
        row = rows[0].row()
        del self.current_schedule.waypoints[row]
        self._refresh_npc_segments()

    def _on_inject_rom_clicked(self):
        if not self.current_npc:
            return

        reply = QMessageBox.question(
            self, _t("rut_confirm_inject_title"),
            _t("rut_confirm_inject", name=self.current_npc.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        ok, msg = RoutineCodec.reinject_npc_to_project(self.project, self.current_npc.npc_id, self.current_npc)
        if ok:
            QMessageBox.information(self, _t("msg_success"), msg)
        else:
            QMessageBox.critical(self, _t("msg_error"), msg)

    def _on_export_json(self):
        if not self.current_npc:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, _t("rut_dlg_export", name=self.current_npc.name),
            f"{self.current_npc.name}_schedules.json", _t("rut_filter_json")
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.current_npc.to_dict(), f, indent=2, ensure_ascii=False)
            QMessageBox.information(self, _t("rut_saved_title"), _t("rut_exported_to", path=path))

    def _on_toggle_connect_mode(self, checked: bool):
        self.macro_view.set_connect_mode(checked)
        if checked:
            self.status_bar.showMessage(_t("rut_st_connect_mode"))
        else:
            self.status_bar.showMessage(_t("rut_st_nav_mode"))

    def _on_connection_created_signal(self, cid, f_m, f_w, t_m, t_w):
        self.act_connect.setChecked(False)
        self.macro_view.set_connect_mode(False)
        self.status_bar.showMessage(_t("rut_st_connected", id=cid))

    def _on_save_topology(self):
        self.world_graph.save_to_json(self.default_graph_path)
        QMessageBox.information(
            self, "Topología Guardada",
            f" Grafo guardado en {self.default_graph_path}\n"
            f"Nodos: {len(self.world_graph.nodes)} | Conexiones: {len(self.world_graph.connections)}"
        )

    def _on_reload_topology(self):
        self.world_graph = WorldGraph.load_from_json(self.default_graph_path)
        self.macro_view.world_graph = self.world_graph
        self.macro_view.rebuild_scene()
        self._populate_filter_maps()
        if self.current_mode == "BY_NPC":
            self._refresh_npc_segments()
        else:
            self._refresh_map_segments()
        self.status_bar.showMessage(_t("rut_st_topo_reloaded"))
