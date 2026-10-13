# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.7.0)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
"""
editor_rutinas_npc.py
══════════════════════════════════════════════════════════════════
Editor Integral de Rutinas Diarias de NPCs con Macromapa Interactivo.
Combina navegación gráfica del mundo (estilo Google Maps), cálculo
automático de rutas con A* y re-inyección/repunteo nativo en ROM GBA.
"""

import os
import json
from typing import Optional, Dict, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QGroupBox,
    QLabel, QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QSpinBox, QFormLayout, QMessageBox, QFileDialog,
    QToolBar, QStatusBar
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QIcon, QAction

from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.world_graph import (
    WorldGraph, MapNode, WarpPoint, WarpConnection,
    DIR_DOWN, DIR_UP, DIR_LEFT, DIR_RIGHT, DIR_FACE
)
from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.macro_map_view import MacroMapView
from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.routine_codec import (
    RoutineCodec, NPCData, NPCSchedule, RoutineWaypoint, NPC_NAMES, NPC_COUNT
)


class EditorRutinasNPCWidget(QWidget):
    """Widget principal del Editor de Rutinas Diarias y Macromapa."""

    def __init__(self, project=None, parent=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("🗺️ Editor de Rutinas Diarias de NPCs & Macromapa")
        self.resize(1300, 800)

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

        self._setup_ui()
        self._load_rom_routines()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ==========================================
        # PANEL IZQUIERDO: Editor de Rutinas y Horarios
        # ==========================================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # 1. Selector de NPC
        npc_group = QGroupBox("Aldeano / NPC Seleccionado")
        npc_form = QFormLayout(npc_group)
        self.combo_npc = QComboBox()
        for nid in range(NPC_COUNT):
            name = NPC_NAMES.get(nid, f"NPC #{nid}")
            self.combo_npc.addItem(f"[{nid:02d}] {name}", nid)
        self.combo_npc.currentIndexChanged.connect(self._on_npc_changed)
        npc_form.addRow("NPC:", self.combo_npc)

        self.lbl_eval_func = QLabel("Evaluador THUMB: -")
        self.lbl_eval_func.setFont(QFont("Consolas", 9))
        self.lbl_eval_func.setStyleSheet("color: #79C0FF;")
        npc_form.addRow("Función:", self.lbl_eval_func)
        left_layout.addWidget(npc_group)

        # 2. Selector de Horario / Condición
        sched_group = QGroupBox("Horario / Condición Diaria")
        sched_layout = QVBoxLayout(sched_group)
        sched_h_layout = QHBoxLayout()
        self.combo_schedule = QComboBox()
        self.combo_schedule.currentIndexChanged.connect(self._on_schedule_changed)
        sched_h_layout.addWidget(QLabel("Horario:"))
        sched_h_layout.addWidget(self.combo_schedule, 1)

        self.btn_add_sched = QPushButton("➕ Nuevo")
        self.btn_add_sched.clicked.connect(self._on_add_schedule)
        sched_h_layout.addWidget(self.btn_add_sched)
        sched_layout.addLayout(sched_h_layout)
        left_layout.addWidget(sched_group)

        # 3. Línea Temporal de la Rutina
        timeline_group = QGroupBox("Línea Temporal de la Rutina (Waypoints)")
        timeline_layout = QVBoxLayout(timeline_group)

        self.table_timeline = QTableWidget()
        self.table_timeline.setColumnCount(5)
        self.table_timeline.setHorizontalHeaderLabels(["#", "Hora", "Mapa", "Coords (X,Y)", "Dir"])
        self.table_timeline.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_timeline.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_timeline.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_timeline.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_timeline.itemSelectionChanged.connect(self._on_waypoint_selected)
        timeline_layout.addWidget(self.table_timeline)

        # Botones de control de hitos
        btn_wp_layout = QHBoxLayout()
        self.btn_add_wp = QPushButton("➕ Añadir Hito")
        self.btn_add_wp.clicked.connect(self._on_add_waypoint)
        self.btn_del_wp = QPushButton("➖ Eliminar Hito")
        self.btn_del_wp.clicked.connect(self._on_delete_waypoint)
        btn_wp_layout.addWidget(self.btn_add_wp)
        btn_wp_layout.addWidget(self.btn_del_wp)
        timeline_layout.addLayout(btn_wp_layout)
        left_layout.addWidget(timeline_group)

        # 4. Editor de Parámetros del Hito
        edit_wp_group = QGroupBox("Parámetros del Hito Seleccionado")
        edit_wp_form = QFormLayout(edit_wp_group)

        # Hora y minutos
        time_layout = QHBoxLayout()
        self.spin_hour = QSpinBox()
        self.spin_hour.setRange(0, 23)
        self.spin_minute = QSpinBox()
        self.spin_minute.setRange(0, 59)
        self.spin_minute.setSingleStep(10)
        time_layout.addWidget(QLabel("Hora:"))
        time_layout.addWidget(self.spin_hour)
        time_layout.addWidget(QLabel("Minutos:"))
        time_layout.addWidget(self.spin_minute)
        edit_wp_form.addRow("Tiempo:", time_layout)

        # Mapa destino
        self.combo_target_map = QComboBox()
        self._populate_maps_combo()
        edit_wp_form.addRow("Mapa Destino:", self.combo_target_map)

        # Coordenadas X, Y
        coords_layout = QHBoxLayout()
        self.spin_x = QSpinBox()
        self.spin_x.setRange(0, 2048)
        self.spin_x.setSingleStep(8)
        self.spin_y = QSpinBox()
        self.spin_y.setRange(0, 2048)
        self.spin_y.setSingleStep(8)
        coords_layout.addWidget(QLabel("X:"))
        coords_layout.addWidget(self.spin_x)
        coords_layout.addWidget(QLabel("Y:"))
        coords_layout.addWidget(self.spin_y)
        edit_wp_form.addRow("Posición:", coords_layout)

        # Dirección / Orientación
        self.combo_dir = QComboBox()
        self.combo_dir.addItem("Abajo (Sur)", DIR_DOWN)
        self.combo_dir.addItem("Arriba (Norte)", DIR_UP)
        self.combo_dir.addItem("Izquierda (Oeste)", DIR_LEFT)
        self.combo_dir.addItem("Derecha (Este)", DIR_RIGHT)
        self.combo_dir.addItem("Frente / Especial", DIR_FACE)
        edit_wp_form.addRow("Orientación:", self.combo_dir)

        # Conectar cambios de formulario para actualizar en vivo
        self.spin_hour.valueChanged.connect(self._on_wp_form_changed)
        self.spin_minute.valueChanged.connect(self._on_wp_form_changed)
        self.combo_target_map.currentIndexChanged.connect(self._on_wp_form_changed)
        self.spin_x.valueChanged.connect(self._on_wp_form_changed)
        self.spin_y.valueChanged.connect(self._on_wp_form_changed)
        self.combo_dir.currentIndexChanged.connect(self._on_wp_form_changed)

        # Botón para calcular ruta con el Macromapa
        self.btn_calc_route = QPushButton("🧭 Calcular Ruta con Macromapa (A*)")
        self.btn_calc_route.setStyleSheet("background-color: #1F6FEB; color: white; font-weight: bold; padding: 6px;")
        self.btn_calc_route.clicked.connect(self._on_calc_route_clicked)
        edit_wp_form.addRow(self.btn_calc_route)

        left_layout.addWidget(edit_wp_group)

        # 5. Inyección a ROM y Exportación
        actions_layout = QHBoxLayout()
        self.btn_inject_rom = QPushButton("💉 Inyectar Rutina en ROM")
        self.btn_inject_rom.setStyleSheet("background-color: #238636; color: white; font-weight: bold; padding: 8px;")
        self.btn_inject_rom.clicked.connect(self._on_inject_rom_clicked)

        self.btn_export_json = QPushButton("💾 Exportar JSON")
        self.btn_export_json.clicked.connect(self._on_export_json)

        actions_layout.addWidget(self.btn_inject_rom, 2)
        actions_layout.addWidget(self.btn_export_json, 1)
        left_layout.addLayout(actions_layout)

        splitter.addWidget(left_widget)

        # ==========================================
        # PANEL DERECHO: Macromapa Interactivo (Google Maps style)
        # ==========================================
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        # Barra de herramientas del macromapa
        map_toolbar = QToolBar("Herramientas del Macromapa")
        map_toolbar.setStyleSheet("background-color: #161B22; border-bottom: 1px solid #30363D; padding: 4px;")

        self.act_connect = QAction("🔗 Conectar Warps", self)
        self.act_connect.setCheckable(True)
        self.act_connect.triggered.connect(self._on_toggle_connect_mode)
        map_toolbar.addAction(self.act_connect)

        self.act_save_topo = QAction("💾 Guardar Topología", self)
        self.act_save_topo.triggered.connect(self._on_save_topology)
        map_toolbar.addAction(self.act_save_topo)

        self.act_reload_topo = QAction("🔄 Recargar", self)
        self.act_reload_topo.triggered.connect(self._on_reload_topology)
        map_toolbar.addAction(self.act_reload_topo)

        map_toolbar.addSeparator()

        self.act_zoom_in = QAction("🔍+", self)
        self.act_zoom_in.triggered.connect(lambda: self.macro_view.scale(1.2, 1.2))
        map_toolbar.addAction(self.act_zoom_in)

        self.act_zoom_out = QAction("🔍-", self)
        self.act_zoom_out.triggered.connect(lambda: self.macro_view.scale(1.0 / 1.2, 1.0 / 1.2))
        map_toolbar.addAction(self.act_zoom_out)

        self.act_zoom_reset = QAction("🎯 100%", self)
        self.act_zoom_reset.triggered.connect(lambda: self.macro_view.resetTransform())
        map_toolbar.addAction(self.act_zoom_reset)

        right_layout.addWidget(map_toolbar)

        # Lienzo MacroMapView
        self.macro_view = MacroMapView(self.world_graph, self)
        self.macro_view.connection_created.connect(self._on_connection_created_signal)
        right_layout.addWidget(self.macro_view)

        # Barra de estado inferior con guía rápida
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("background-color: #0D1117; color: #8B949E; font-size: 11px;")
        self.status_bar.showMessage("💡 Guía: Rueda para Zoom | Botón Central/Derecho para Pan | Arrastra mapas para organizarlos | Doble-clic en mapa para crear puerta")
        right_layout.addWidget(self.status_bar)

        splitter.addWidget(right_widget)
        splitter.setSizes([450, 850])
        main_layout.addWidget(splitter)

    def _populate_maps_combo(self):
        self.combo_target_map.clear()
        for node in self.world_graph.nodes.values():
            self.combo_target_map.addItem(f"[{node.map_id:02X}] {node.name}", node.map_id)

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

        if rom_data:
            self.all_npcs = RoutineCodec.decode_all(rom_data)
        else:
            # Fallback a estructuras vacías iniciales para los 32 aldeanos
            for nid in range(NPC_COUNT):
                self.all_npcs[nid] = NPCData(nid, NPC_NAMES.get(nid, f"NPC_{nid}"))

        self._on_npc_changed(0)

    def _on_npc_changed(self, index: int):
        npc_id = self.combo_npc.currentData()
        self.current_npc = self.all_npcs.get(npc_id)

        if not self.current_npc:
            return

        self.lbl_eval_func.setText(f"Evaluador THUMB: 0x{self.current_npc.evaluator_func:08X}")

        self.combo_schedule.blockSignals(True)
        self.combo_schedule.clear()
        for idx, sched in enumerate(self.current_npc.schedules):
            if sched:
                self.combo_schedule.addItem(f"Horario #{idx} ({len(sched.waypoints)} hitos)", idx)
            else:
                self.combo_schedule.addItem(f"Horario #{idx} [NULL / Sin asignar]", idx)
        self.combo_schedule.blockSignals(False)

        if self.combo_schedule.count() > 0:
            self.combo_schedule.setCurrentIndex(0)
            self._on_schedule_changed(0)

    def _on_schedule_changed(self, index: int):
        if not self.current_npc or index < 0 or index >= len(self.current_npc.schedules):
            self.current_schedule = None
            self._refresh_timeline_table()
            return

        self.current_schedule = self.current_npc.schedules[index]
        self._refresh_timeline_table()

    def _refresh_timeline_table(self):
        self.table_timeline.blockSignals(True)
        self.table_timeline.setRowCount(0)

        if not self.current_schedule:
            self.table_timeline.blockSignals(False)
            self.macro_view.set_active_npc_route([])
            return

        wps = self.current_schedule.waypoints
        self.table_timeline.setRowCount(len(wps))

        route_display_data = []

        for row, wp in enumerate(wps):
            map_node = self.world_graph.get_node(wp.map_id)
            map_name = map_node.name if map_node else f"Mapa 0x{wp.map_id:02X}"

            dir_str = ["Abajo", "Arriba", "Izq", "Der", "Frente"][wp.spawn_dir] if wp.spawn_dir <= 4 else str(wp.spawn_dir)

            item_idx = QTableWidgetItem(str(row + 1))
            item_time = QTableWidgetItem(wp.time_to_str())
            item_map = QTableWidgetItem(f"[{wp.map_id:02X}] {map_name}")
            item_coords = QTableWidgetItem(f"({wp.spawn_x}, {wp.spawn_y})")
            item_dir = QTableWidgetItem(dir_str)

            for item in (item_idx, item_time, item_map, item_coords, item_dir):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table_timeline.setItem(row, 0, item_idx)
            self.table_timeline.setItem(row, 1, item_time)
            self.table_timeline.setItem(row, 2, item_map)
            self.table_timeline.setItem(row, 3, item_coords)
            self.table_timeline.setItem(row, 4, item_dir)

            route_display_data.append({
                "map_id": wp.map_id,
                "spawn_x": wp.spawn_x,
                "spawn_y": wp.spawn_y,
                "time_str": wp.time_to_str(),
                "time_val": wp.time_val
            })

        self.table_timeline.blockSignals(False)

        # Actualizar capa visual de la ruta en el Macromapa
        self.macro_view.set_active_npc_route(route_display_data)

        if len(wps) > 0:
            self.table_timeline.selectRow(0)

    def _on_waypoint_selected(self):
        rows = self.table_timeline.selectionModel().selectedRows()
        if not rows or not self.current_schedule:
            return

        row = rows[0].row()
        if row >= len(self.current_schedule.waypoints):
            return

        wp = self.current_schedule.waypoints[row]

        # Actualizar campos del formulario
        self.spin_hour.blockSignals(True)
        self.spin_minute.blockSignals(True)
        self.combo_target_map.blockSignals(True)
        self.spin_x.blockSignals(True)
        self.spin_y.blockSignals(True)
        self.combo_dir.blockSignals(True)

        self.spin_hour.setValue(wp.time_val // 60)
        self.spin_minute.setValue(wp.time_val % 60)

        # Buscar mapa en combo
        idx_map = self.combo_target_map.findData(wp.map_id)
        if idx_map >= 0:
            self.combo_target_map.setCurrentIndex(idx_map)

        self.spin_x.setValue(wp.spawn_x)
        self.spin_y.setValue(wp.spawn_y)

        idx_dir = self.combo_dir.findData(wp.spawn_dir)
        if idx_dir >= 0:
            self.combo_dir.setCurrentIndex(idx_dir)

        self.spin_hour.blockSignals(False)
        self.spin_minute.blockSignals(False)
        self.combo_target_map.blockSignals(False)
        self.spin_x.blockSignals(False)
        self.spin_y.blockSignals(False)
        self.combo_dir.blockSignals(False)

    def _on_wp_form_changed(self):
        rows = self.table_timeline.selectionModel().selectedRows()
        if not rows or not self.current_schedule:
            return

        row = rows[0].row()
        if row >= len(self.current_schedule.waypoints):
            return

        wp = self.current_schedule.waypoints[row]
        wp.time_val = self.spin_hour.value() * 60 + self.spin_minute.value()
        wp.map_id = self.combo_target_map.currentData()
        wp.spawn_x = self.spin_x.value()
        wp.spawn_y = self.spin_y.value()
        wp.spawn_dir = self.combo_dir.currentData()

        # Actualizar tabla visual sin perder selección
        map_node = self.world_graph.get_node(wp.map_id)
        map_name = map_node.name if map_node else f"0x{wp.map_id:02X}"
        dir_str = ["Abajo", "Arriba", "Izq", "Der", "Frente"][wp.spawn_dir] if wp.spawn_dir <= 4 else str(wp.spawn_dir)

        self.table_timeline.item(row, 1).setText(wp.time_to_str())
        self.table_timeline.item(row, 2).setText(f"[{wp.map_id:02X}] {map_name}")
        self.table_timeline.item(row, 3).setText(f"({wp.spawn_x}, {wp.spawn_y})")
        self.table_timeline.item(row, 4).setText(dir_str)

        # Actualizar ruta en el macromapa
        route_display_data = [{
            "map_id": w.map_id, "spawn_x": w.spawn_x, "spawn_y": w.spawn_y,
            "time_str": w.time_to_str(), "time_val": w.time_val
        } for w in self.current_schedule.waypoints]
        self.macro_view.set_active_npc_route(route_display_data)

    def _on_add_schedule(self):
        if not self.current_npc:
            return
        new_id = len(self.current_npc.schedules)
        new_sched = NPCSchedule(new_id)
        self.current_npc.schedules.append(new_sched)
        self._on_npc_changed(self.combo_npc.currentIndex())
        self.combo_schedule.setCurrentIndex(new_id)

    def _on_add_waypoint(self):
        if not self.current_schedule:
            QMessageBox.warning(self, "Aviso", "Primero seleccione o cree un horario activo.")
            return

        last_wp = self.current_schedule.waypoints[-1] if self.current_schedule.waypoints else None
        next_time = (last_wp.time_val + 120) if last_wp else 360  # +2 horas por defecto
        next_map = last_wp.map_id if last_wp else 0x02
        next_x = last_wp.spawn_x if last_wp else 160
        next_y = last_wp.spawn_y if last_wp else 160

        new_wp = RoutineWaypoint(
            time_val=min(1439, next_time),
            spawn_dir=DIR_DOWN,
            spawn_x=next_x,
            spawn_y=next_y,
            map_id=next_map
        )
        self.current_schedule.waypoints.append(new_wp)
        self._refresh_timeline_table()
        self.table_timeline.selectRow(len(self.current_schedule.waypoints) - 1)

    def _on_delete_waypoint(self):
        rows = self.table_timeline.selectionModel().selectedRows()
        if not rows or not self.current_schedule:
            return
        row = rows[0].row()
        del self.current_schedule.waypoints[row]
        self._refresh_timeline_table()

    def _on_calc_route_clicked(self):
        """Calcula el trayecto automático a través de los mapas y warps conectados."""
        rows = self.table_timeline.selectionModel().selectedRows()
        if not rows or not self.current_schedule:
            return

        curr_row = rows[0].row()
        if curr_row == 0:
            QMessageBox.information(
                self, "Hito Inicial",
                "Este es el punto inicial de la rutina diaria. Los vectores se calculan a partir de un punto previo."
            )
            return

        prev_wp = self.current_schedule.waypoints[curr_row - 1]
        curr_wp = self.current_schedule.waypoints[curr_row]

        steps, vectors = self.world_graph.find_world_path(
            start_map_id=prev_wp.map_id,
            start_x=prev_wp.spawn_x,
            start_y=prev_wp.spawn_y,
            target_map_id=curr_wp.map_id,
            target_x=curr_wp.spawn_x,
            target_y=curr_wp.spawn_y
        )

        curr_wp.x_vectors = vectors

        # Detalle del cálculo para el usuario
        step_descs = []
        for s in steps:
            if s["type"] == "walk":
                m_obj = self.world_graph.get_node(s["map_id"])
                m_name = m_obj.name if m_obj else f"0x{s['map_id']:02X}"
                step_descs.append(f"• Caminata en [{m_name}]: {s['from']} ➔ {s['to']}")
            elif s["type"] == "warp":
                step_descs.append(f"• 🚪 Warp: {s.get('note', 'Transición entre mapas')}")

        report = "\n".join(step_descs)
        QMessageBox.information(
            self, "Ruta Calculada con Éxito",
            f"🧭 Algoritmo A* completado a través de la topología:\n\n{report}\n\n"
            f"Vectores GBA generados: {len(vectors)} pasos (asignados al hito)."
        )

    def _on_inject_rom_clicked(self):
        """Inyecta o repuntea la rutina actual directamente en la ROM del proyecto."""
        if not self.current_npc:
            return

        reply = QMessageBox.question(
            self, "Confirmar Inyección en ROM",
            f"¿Desea compilar y reinyectar las rutinas de {self.current_npc.name} en la ROM?\n"
            f"Los punteros de la Master Table (0x3D9A4) serán actualizados.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        ok, msg = RoutineCodec.reinject_npc_to_project(self.project, self.current_npc.npc_id, self.current_npc)
        if ok:
            QMessageBox.information(self, "Inyección Exitosa", msg)
        else:
            QMessageBox.critical(self, "Error al Inyectar", msg)

    def _on_export_json(self):
        if not self.current_npc:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, f"Exportar Rutinas de {self.current_npc.name}",
            f"{self.current_npc.name}_schedules.json", "Archivos JSON (*.json)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.current_npc.to_dict(), f, indent=2, ensure_ascii=False)
            QMessageBox.information(self, "Exportado", f"Rutinas guardadas en {path}")

    def _on_toggle_connect_mode(self, checked: bool):
        self.macro_view.set_connect_mode(checked)
        if checked:
            self.status_bar.showMessage("🔗 MODO CONECTAR ACTIVO: Haz clic en el Pin de la Puerta Origen y luego en la Puerta Destino.")
        else:
            self.status_bar.showMessage("💡 Modo navegación activo.")

    def _on_connection_created_signal(self, cid, f_m, f_w, t_m, t_w):
        self.act_connect.setChecked(False)
        self.macro_view.set_connect_mode(False)
        self.status_bar.showMessage(f"✅ Conexión establecida: {cid}")

    def _on_save_topology(self):
        self.world_graph.save_to_json(self.default_graph_path)
        QMessageBox.information(
            self, "Topología Guardada",
            f"✅ Grafo del macromapa guardado exitosamente en:\n{self.default_graph_path}\n"
            f"Nodos: {len(self.world_graph.nodes)} | Conexiones: {len(self.world_graph.connections)}"
        )

    def _on_reload_topology(self):
        self.world_graph = WorldGraph.load_from_json(self.default_graph_path)
        self.macro_view.world_graph = self.world_graph
        self.macro_view.rebuild_scene()
        self._populate_maps_combo()
        if self.current_schedule:
            self._refresh_timeline_table()
        self.status_bar.showMessage("🔄 Topología recargada desde el archivo.")
