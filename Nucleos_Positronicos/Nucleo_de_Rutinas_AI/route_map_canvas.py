# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.8.0)
# Visor y Lienzo de Vista General de Mapas & Rutas Ortogonales AWSD
# ============================================================
"""
route_map_canvas.py
══════════════════════════════════════════════════════════════
Lienzo interactivo del Editor de Rutinas para pintar la vista general
del mapa y trazar las rutas ortogonales AWSD (sin diagonales),
nodos de movimiento, vectores y la malla de tiles caminables de la ROM.
"""

import math
from typing import Optional, List, Dict, Tuple, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QGraphicsItem, QToolBar, QLabel, QPushButton,
    QGraphicsPathItem, QGraphicsEllipseItem, QGraphicsTextItem, QToolTip
)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPixmap, QImage,
    QPainterPath, QPolygonF, QLinearGradient, QRadialGradient,
    QWheelEvent, QMouseEvent, QResizeEvent
)

from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.fomt_map_names import (
    get_map_display_name, get_map_header_id_for_event_map, unpack_fomt_map_id
)
from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.world_graph import (
    DIR_DOWN, DIR_UP, DIR_LEFT, DIR_RIGHT, DIR_FACE
)
from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.tile_pathfinder import TilePathfinder


def ensure_orthogonal_path(nodes: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """
    Garantiza que todos los pasos consecutivos entre nodos sean estrictamente ortogonales (AWSD)
    sin diagonales, manteniendo la compatibilidad exacta con el motor GBA de Harvest Moon: FoMT.
    """
    if not nodes or len(nodes) < 2:
        return list(nodes) if nodes else []

    result = [nodes[0]]
    for i in range(1, len(nodes)):
        prev_x, prev_y = result[-1]
        curr_x, curr_y = nodes[i]

        if prev_x != curr_x and prev_y != curr_y:
            # Descomponer diagonal en dos tramos ortogonales en L
            if abs(curr_x - prev_x) >= abs(curr_y - prev_y):
                result.append((curr_x, prev_y))
            else:
                result.append((prev_x, curr_y))
            result.append((curr_x, curr_y))
        elif (curr_x, curr_y) != (prev_x, prev_y):
            result.append((curr_x, curr_y))

    if len(result) < 3:
        return result

    cleaned = [result[0]]
    for i in range(1, len(result) - 1):
        p_prev = cleaned[-1]
        p_curr = result[i]
        p_next = result[i + 1]

        is_collinear_h = (p_prev[1] == p_curr[1] == p_next[1])
        is_collinear_v = (p_prev[0] == p_curr[0] == p_next[0])
        if not (is_collinear_h or is_collinear_v):
            cleaned.append(p_curr)

    cleaned.append(result[-1])
    return cleaned


class RouteVectorOverlayItem(QGraphicsItem):
    """Capa gráfica que dibuja las líneas de movimiento ortogonales AWSD, paradas y malla caminable."""

    def __init__(self, canvas_view: 'RouteMapCanvas'):
        super().__init__()
        self.canvas_view = canvas_view
        self.setZValue(10)
        self.segments: List[dict] = []
        self.highlight_id: Optional[str] = None
        self.show_vectors = True
        self.show_labels = True
        self.show_walkable_grid = False

    def set_segments(self, segments: List[dict], highlight_id: Optional[str] = None):
        self.prepareGeometryChange()
        self.segments = segments or []
        self.highlight_id = highlight_id
        self.update()

    def boundingRect(self) -> QRectF:
        if self.canvas_view.map_pixmap and not self.canvas_view.map_pixmap.isNull():
            return QRectF(0, 0, self.canvas_view.map_pixmap.width(), self.canvas_view.map_pixmap.height())
        return QRectF(0, 0, 1024, 768)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # 0. Dibujar malla de colisión caminable si está activada
        if self.show_walkable_grid and self.canvas_view.current_map_id is not None:
            col_pix = self.canvas_view.get_collision_overlay_pixmap(self.canvas_view.current_map_id)
            if col_pix and not col_pix.isNull():
                painter.drawPixmap(0, 0, col_pix)

        if not self.segments:
            return

        # Paleta de colores para NPCs
        colors = [
            "#00E5FF", "#FF1744", "#76FF03", "#FFD600",
            "#D500F9", "#FF6D00", "#00E676", "#2979FF"
        ]

        # 1. Filtrar segmentos del mapa actual
        current_map_id = self.canvas_view.current_map_id
        current_base_id = (current_map_id & 0x3FF) if current_map_id is not None else None

        map_segments: List[Tuple[int, dict]] = []
        for idx, seg in enumerate(self.segments):
            seg_mid = seg.get("base_map_id")
            if seg_mid is None:
                seg_mid = unpack_fomt_map_id(seg.get("map_id", 0))[0]

            if current_base_id is not None and seg_mid != current_base_id:
                continue
            map_segments.append((idx, seg))

        if not map_segments:
            return

        # 2. Agrupar por NPC en este mapa para detectar múltiples rutas
        npc_segments: Dict[int, List[Tuple[int, dict]]] = {}
        for orig_idx, seg in map_segments:
            nid = seg.get("npc_id", 0)
            npc_segments.setdefault(nid, []).append((orig_idx, seg))

        # 3. Determinar qué rutas se dibujan:
        # Si hay varias del mismo NPC en el mapa, solo se dibuja la seleccionada con sus flechas de dirección
        segments_to_draw: List[Tuple[int, dict]] = []
        for nid, seg_list in npc_segments.items():
            if len(seg_list) == 1:
                # Solo hay una ruta de este NPC en el mapa
                segments_to_draw.append(seg_list[0])
            else:
                # Hay VARIAS rutas del mismo NPC en el mapa:
                # Buscar si alguna coincide con la seleccionada (highlight_id)
                hl_item = next((item for item in seg_list if item[1].get("id") == self.highlight_id), None)
                if hl_item is not None:
                    # SOLO se dibuja la seleccionada
                    segments_to_draw.append(hl_item)
                else:
                    # Si ninguna de este NPC coincide con highlight_id:
                    # Si no hay ningún highlight_id activo en general, tomamos la primera por defecto;
                    # si hay otro segmento seleccionado en el mapa, no dibujar rutas de este NPC para evitar saturación
                    if self.highlight_id is None:
                        segments_to_draw.append(seg_list[0])

        # 4. Dibujar las rutas seleccionadas / únicas sobre el mapa
        for orig_idx, seg in segments_to_draw:
            seg_mid = seg.get("base_map_id")
            if seg_mid is None:
                seg_mid = unpack_fomt_map_id(seg.get("map_id", 0))[0]

            is_hl = (seg.get("id") == self.highlight_id)
            c = QColor(colors[seg.get("npc_id", 0) % len(colors)])

            ax, ay = seg.get("ax", 0), seg.get("ay", 0)
            bx, by = seg.get("bx", 0), seg.get("by", 0)

            # Obtener nodos ortogonales AWSD del tramo
            path_nodes = seg.get("path_nodes")
            wp_ref = seg.get("wp_ref")
            if not path_nodes and wp_ref:
                path_nodes = getattr(wp_ref, "path_nodes", None)

            if not path_nodes or len(path_nodes) < 2:
                if (ax, ay) != (bx, by):
                    # Resolver con pathfinder o Manhattan ortogonal
                    path_nodes = self.canvas_view.get_orthogonal_nodes(seg_mid, ax, ay, bx, by)
                else:
                    path_nodes = [(ax, ay)]

            is_loop = len(path_nodes) > 1 and (path_nodes[0] == path_nodes[-1])
            is_moving = len(path_nodes) > 1 and ((ax, ay) != (bx, by) or is_loop)

            if is_moving and self.show_vectors:
                # Construir trayectoria ortogonal exacta (AWSD)
                path = QPainterPath()
                start_pt = path_nodes[0]
                path.moveTo(start_pt[0], start_pt[1])

                for node in path_nodes[1:]:
                    path.lineTo(node[0], node[1])

                if is_loop:
                    path.closeSubpath()

                # Halo resplandeciente exterior (glow) - Sin relleno de polígonos negros
                halo_alpha = 130 if is_hl else 70
                halo_width = 10.0 if is_hl else 6.0
                halo_pen = QPen(QColor(c.red(), c.green(), c.blue(), halo_alpha), halo_width)
                painter.setPen(halo_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.strokePath(path, halo_pen)

                # Trazo principal del vector ortogonal AWSD (trazo puro, sin relleno)
                pen = QPen(c if is_hl else QColor(c.red(), c.green(), c.blue(), 210),
                           4.0 if is_hl else 2.5,
                           Qt.PenStyle.SolidLine if (is_hl or is_loop) else Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.strokePath(path, pen)

                # Flechas de dirección de movimiento estilizadas (sin triángulos negros)
                for step_i in range(1, len(path_nodes)):
                    p0 = path_nodes[step_i - 1]
                    p1 = path_nodes[step_i]
                    dx = p1[0] - p0[0]
                    dy = p1[1] - p0[1]
                    seg_len = math.hypot(dx, dy)
                    if seg_len >= 20:
                        angle = math.atan2(dy, dx)
                        if seg_len < 48:
                            # 1 flecha centrada en el vector
                            mx = (p0[0] + p1[0]) / 2.0
                            my = (p0[1] + p1[1]) / 2.0
                            self._draw_arrowhead(painter, mx, my, angle, c, is_hl)
                        else:
                            # Tramos largos: distribuir flechas cada ~36-44 px
                            num_arrows = max(1, int(round(seg_len / 40.0)))
                            step_t = 1.0 / (num_arrows + 1)
                            for a_idx in range(1, num_arrows + 1):
                                t = a_idx * step_t
                                ax_pos = p0[0] + dx * t
                                ay_pos = p0[1] + dy * t
                                self._draw_arrowhead(painter, ax_pos, ay_pos, angle, c, is_hl)

                # Puntos de esquina / giro intermedios (nodos de inflexión interactivos)
                for step_i in range(1, len(path_nodes) - 1):
                    p_curr = QPointF(path_nodes[step_i][0], path_nodes[step_i][1])
                    is_node_active = is_hl and (getattr(self.canvas_view, "active_node_idx", None) == step_i)
                    is_node_hovered = is_hl and (getattr(self.canvas_view, "_hovered_node_idx", None) == step_i)

                    if is_node_active or is_node_hovered:
                        # Halo de resalto interactivo
                        halo_r = 11.0 if is_node_active else 9.0
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        painter.setPen(QPen(QColor("#FFD600" if is_node_active else "#00E5FF"), 2.5))
                        painter.drawEllipse(p_curr, halo_r, halo_r)

                        # Cuerpo del nodo activo / hover
                        node_r = 7.5 if is_node_active else 6.5
                        painter.setBrush(QBrush(QColor("#FFD600" if is_node_active else "#00E5FF")))
                        painter.setPen(QPen(QColor("#FFFFFF"), 2.0))
                        painter.drawEllipse(p_curr, node_r, node_r)

                        # Número del punto de inflexión en color oscuro de alto contraste
                        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                        painter.setPen(QColor("#0D1117"))
                        painter.drawText(QRectF(p_curr.x() - 7, p_curr.y() - 7, 14, 14),
                                         Qt.AlignmentFlag.AlignCenter, str(step_i))
                    else:
                        # Nodo normal estilizado
                        painter.setBrush(QBrush(QColor("#161B22") if is_hl else QColor(255, 255, 255, 230)))
                        painter.setPen(QPen(c if is_hl else QColor("#FFFFFF"), 2.0 if is_hl else 1.2))
                        node_r = 5.5 if is_hl else 3.5
                        painter.drawEllipse(p_curr, node_r, node_r)

                        if is_hl:
                            painter.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
                            painter.setPen(QColor("#FFFFFF"))
                            painter.drawText(QRectF(p_curr.x() - 5, p_curr.y() - 5, 10, 10),
                                             Qt.AlignmentFlag.AlignCenter, str(step_i))

                    # Si el nodo tiene delay > 0 en tramo resaltado, mostrar badge de delay
                    if is_hl:
                        wp_ref = seg.get("wp_ref")
                        node_d = wp_ref.get_node_delay(step_i) if (wp_ref and hasattr(wp_ref, "get_node_delay")) else 0
                        if node_d > 0:
                            delay_badge = f"{node_d}f ({node_d/60.0:.1f}s)"
                            painter.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
                            painter.setBrush(QBrush(QColor(13, 17, 23, 230)))
                            painter.setPen(QPen(QColor("#58A6FF"), 1.0))
                            badge_rect = QRectF(p_curr.x() - 20, p_curr.y() - 20, 40, 12)
                            painter.drawRoundedRect(badge_rect, 3, 3)
                            painter.setPen(QColor("#79C0FF"))
                            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, delay_badge)

                # Punto A (Inicio) en Verde esmeralda con halo interactivo
                pt_a = QPointF(path_nodes[0][0], path_nodes[0][1])
                is_a_active = is_hl and (getattr(self.canvas_view, "active_node_idx", None) == 0)
                is_a_hovered = is_hl and (getattr(self.canvas_view, "_hovered_node_idx", None) == 0)

                if not is_loop:
                    if is_a_active or is_a_hovered:
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        painter.setPen(QPen(QColor("#00E676"), 2.5))
                        painter.drawEllipse(pt_a, 11, 11)

                    painter.setBrush(QBrush(QColor("#00E676")))
                    painter.setPen(QPen(QColor("#FFFFFF"), 2.0))
                    painter.drawEllipse(pt_a, 8.5 if (is_a_active or is_a_hovered) else 7, 8.5 if (is_a_active or is_a_hovered) else 7)
                    painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                    painter.setPen(QColor("#0D1117"))
                    painter.drawText(QRectF(pt_a.x() - 6, pt_a.y() - 6, 12, 12), Qt.AlignmentFlag.AlignCenter, "A")

            # Punto B (Llegada / Destino) con halo interactivo
            final_node = path_nodes[-1]
            pt_b = QPointF(final_node[0], final_node[1])
            is_b_active = is_hl and (getattr(self.canvas_view, "active_node_idx", None) == len(path_nodes) - 1)
            is_b_hovered = is_hl and (getattr(self.canvas_view, "_hovered_node_idx", None) == len(path_nodes) - 1)

            if is_b_active or is_b_hovered:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor("#FFD600"), 2.5))
                painter.drawEllipse(pt_b, 12, 12)

            if not is_moving:
                # Hito estacionario: dibujar círculo con indicador de orientación
                painter.setBrush(QBrush(QColor(56, 139, 253, 220) if not is_hl else QColor("#FFD600")))
                painter.setPen(QPen(QColor("#FFFFFF"), 2.0))
                painter.drawEllipse(pt_b, 8 if is_hl else 6, 8 if is_hl else 6)
                self._draw_facing_indicator(painter, pt_b, seg.get("dir", 0))
            elif is_loop:
                # Hito en Bucle: dibujar nodo central con halo verde/morado
                painter.setBrush(QBrush(QColor("#8A2BE2") if not is_hl else QColor("#FFD600")))
                painter.setPen(QPen(QColor("#00E676"), 2.5 if is_hl else 2.0))
                painter.drawEllipse(pt_b, 10 if is_hl else 8, 10 if is_hl else 8)
                painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                painter.setPen(QColor("#FFFFFF" if not is_hl else "#0D1117"))
                painter.drawText(QRectF(pt_b.x() - 6, pt_b.y() - 6, 12, 12), Qt.AlignmentFlag.AlignCenter, "A")
            else:
                b_brush = QBrush(QColor("#FF1744") if not is_hl else QColor("#FFD600"))
                painter.setBrush(b_brush)
                painter.setPen(QPen(QColor("#FFFFFF"), 2.0))
                painter.drawEllipse(pt_b, 9 if is_hl else 7, 9 if is_hl else 7)

            # Número de hito (se dibuja en el nodo si no es bucle)
            if not is_loop:
                painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                painter.setPen(QColor("#FFFFFF" if not is_hl else "#0D1117"))
                painter.drawText(QRectF(pt_b.x() - 10, pt_b.y() - 10, 20, 20),
                                 Qt.AlignmentFlag.AlignCenter, str(orig_idx + 1))

            # Etiqueta informativa del hito (Hora, Espera y Badge de Bucle)
            if self.show_labels:
                time_str = seg.get("time_str", "")
                delay_str = seg.get("delay_str", "0m")
                loop_tag = "  Bucle" if is_loop else ""
                tag_text = f"#{orig_idx+1}{loop_tag} {time_str} ({delay_str})"

                lbl_w = 110 if is_loop else 90
                lbl_rect = QRectF(pt_b.x() - lbl_w / 2, pt_b.y() - 34, lbl_w, 20)
                painter.setBrush(QBrush(QColor(13, 17, 23, 230)))
                border_color = QColor("#8A2BE2") if is_loop else (c if is_hl else QColor("#30363D"))
                painter.setPen(QPen(border_color, 1.5 if is_hl else 1.0))
                painter.drawRoundedRect(lbl_rect, 4, 4)

                painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold if (is_hl or is_loop) else QFont.Weight.Normal))
                painter.setPen(QColor("#A371F7" if is_loop else ("#FFD600" if is_hl else "#FFFFFF")))
                painter.drawText(lbl_rect, Qt.AlignmentFlag.AlignCenter, tag_text)
                painter.setBrush(Qt.BrushStyle.NoBrush)

    def _draw_facing_indicator(self, painter: QPainter, pt: QPointF, facing: int):
        """Dibuja un pequeño indicador direccional para un NPC estacionario (0=Abajo, 1=Arriba, 2=Izq, 3=Der)."""
        arrow_len = 8
        fx, fy = 0, 0
        if facing == 0:  # Abajo
            fy = arrow_len
        elif facing == 1:  # Arriba
            fy = -arrow_len
        elif facing == 2:  # Izquierda
            fx = -arrow_len
        elif facing == 3:  # Derecha
            fx = arrow_len
        else:
            fy = arrow_len

        target = QPointF(pt.x() + fx, pt.y() + fy)
        painter.setPen(QPen(QColor("#FFFFFF"), 2.0))
        painter.drawLine(pt, target)

    def _draw_arrowhead(self, painter: QPainter, x: float, y: float, angle: float, color: QColor, is_hl: bool):
        """
        Dibuja una flecha direccional estilizada tipo chevron sobre el vector ortogonal.
        Elimina por completo cualquier triángulo negro o polígono oscuro cerrado.
        """
        arrow_size = 7.5 if is_hl else 6.0
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        # Punta frontal de la flecha
        tip = QPointF(x + cos_a * (arrow_size * 0.7), y + sin_a * (arrow_size * 0.7))

        # Brazos laterales del chevron
        back_len = arrow_size * 1.15
        wing_w = arrow_size * 0.8
        left = QPointF(tip.x() - cos_a * back_len - sin_a * wing_w,
                       tip.y() - sin_a * back_len + cos_a * wing_w)
        right = QPointF(tip.x() - cos_a * back_len + sin_a * wing_w,
                        tip.y() - sin_a * back_len - cos_a * wing_w)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # 1. Halo exterior de sombra suave para contraste contra cualquier fondo (sin triángulos)
        halo_color = QColor(0, 0, 0, 180)
        halo_w = 4.2 if is_hl else 3.2
        halo_pen = QPen(halo_color, halo_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(halo_pen)
        painter.drawLine(left, tip)
        painter.drawLine(right, tip)

        # 2. Flecha chevron luminosa de alta visibilidad (blanco puro en highlight o color de ruta)
        arrow_color = QColor("#FFFFFF") if is_hl else QColor(color.red(), color.green(), color.blue(), 235)
        arrow_w = 2.4 if is_hl else 1.8
        arrow_pen = QPen(arrow_color, arrow_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(arrow_pen)
        painter.drawLine(left, tip)
        painter.drawLine(right, tip)

        painter.restore()


class RouteMapCanvas(QGraphicsView):
    """
    Lienzo de Vista General del Mapa & Rutas Ortogonales AWSD.
    Permite zoom interactivo, paneo, renderizado con tiles de ROM y edición visual de rutas.
    """

    point_clicked = pyqtSignal(int, int)  # (x, y) en píxeles del mapa
    point_double_clicked = pyqtSignal(int, int)
    node_selected = pyqtSignal(int, int, int)       # (node_idx, x, y)
    node_moved = pyqtSignal(int, int, int)          # (node_idx, x, y)
    node_drag_finished = pyqtSignal(int, int, int)  # (node_idx, x, y)
    node_inserted = pyqtSignal(int, int, int)       # (insert_idx, x, y)
    node_deleted = pyqtSignal(int)                  # (node_idx)

    def __init__(self, project=None, parent=None):
        super().__init__(parent)
        self.project = project
        self.rom_data: Optional[bytes] = None
        self.current_map_id: Optional[int] = None
        self.map_pixmap: Optional[QPixmap] = None

        self.scene_obj = QGraphicsScene(self)
        self.setScene(self.scene_obj)

        self.map_pixmap_item = QGraphicsPixmapItem()
        self.map_pixmap_item.setZValue(1)
        self.scene_obj.addItem(self.map_pixmap_item)

        self.overlay_item = RouteVectorOverlayItem(self)
        self.scene_obj.addItem(self.overlay_item)

        # Pathfinding y Colisiones
        self.pathfinder = TilePathfinder(self.project, self.rom_data)

        # Cachés de mapas y capas de colisión
        self._rendered_maps_cache: Dict[int, QPixmap] = {}
        self._collision_overlay_cache: Dict[int, QPixmap] = {}

        # Configuración visual
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(QColor("#0D1117")))

        # Panning y Manipulación de Nodos de Inflexión
        self._is_panning = False
        self._pan_start = QPointF()

        self.active_node_idx: Optional[int] = None
        self._hovered_node_idx: Optional[int] = None
        self._dragged_node_idx: Optional[int] = None
        self._is_dragging_node: bool = False
        self._drag_start_pos: Optional[QPointF] = None

    def get_orthogonal_nodes(self, map_id: int, ax: int, ay: int, bx: int, by: int) -> List[Tuple[int, int]]:
        """Calcula los nodos ortogonales AWSD utilizando la cuadrícula de colisiones."""
        if self.pathfinder:
            if not self.pathfinder.rom_data and self.rom_data:
                self.pathfinder.rom_data = self.rom_data
            return self.pathfinder.find_orthogonal_path(map_id, ax, ay, bx, by)
        # Fallback ortogonal Manhattan en L
        if ax == bx or ay == by:
            return [(ax, ay), (bx, by)]
        return [(ax, ay), (bx, ay), (bx, by)]

    def get_collision_overlay_pixmap(self, base_id: int) -> Optional[QPixmap]:
        """Genera y almacena en caché la capa semitransparente de tiles transitables y sólidos."""
        if base_id in self._collision_overlay_cache:
            return self._collision_overlay_cache[base_id]

        if not self.pathfinder:
            return None

        if not self.pathfinder.rom_data and self.rom_data:
            self.pathfinder.rom_data = self.rom_data

        grid = self.pathfinder.get_map_grid(base_id)
        if not grid:
            return None

        w, h = grid["width"], grid["height"]
        pix_w, pix_h = grid["pixel_w"], grid["pixel_h"]

        pix = QPixmap(pix_w, pix_h)
        pix.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pix)
        walkable_brush = QBrush(QColor(46, 204, 113, 28))  # Verde suave para caminables
        solid_brush = QBrush(QColor(231, 76, 60, 45))      # Rojo suave para muros/bloqueos
        fine_pen = QPen(QColor(255, 255, 255, 15), 0.5)

        for ty in range(h):
            for tx in range(w):
                is_walk = self.pathfinder.is_tile_walkable(grid, tx, ty)
                rect = QRectF(tx * 8, ty * 8, 8, 8)
                painter.fillRect(rect, walkable_brush if is_walk else solid_brush)
                painter.setPen(fine_pen)
                painter.drawRect(rect)

        painter.end()
        self._collision_overlay_cache[base_id] = pix
        return pix

    def load_map_view(self, map_id: int):
        """Carga y renderiza la vista general del mapa correspondiente."""
        base_id, season = unpack_fomt_map_id(map_id)
        if self.current_map_id == base_id and self.map_pixmap:
            return

        self.current_map_id = base_id

        # 1. Buscar en caché
        if base_id in self._rendered_maps_cache:
            self._apply_map_pixmap(self._rendered_maps_cache[base_id])
            return

        # 2. Renderizar desde la ROM
        rendered = self._render_map_from_rom(base_id, season)
        if rendered and not rendered.isNull():
            self._rendered_maps_cache[base_id] = rendered
            self._apply_map_pixmap(rendered)
            return

        # 3. Fallback a plano sintético estructurado de alta fidelidad
        synthetic = self._generate_synthetic_map(base_id)
        self._rendered_maps_cache[base_id] = synthetic
        self._apply_map_pixmap(synthetic)

    def _render_map_from_rom(self, base_id: int, season: int) -> Optional[QPixmap]:
        """Utiliza FomtMapRenderer para generar el pixmap exacto de la ROM."""
        import os
        rom_data = getattr(self, "rom_data", None)

        if not rom_data and self.project:
            if getattr(self.project, "virtual_rom", None):
                rom_data = bytes(self.project.virtual_rom)
            elif getattr(self.project, "base_rom_data", None):
                rom_data = self.project.base_rom_data
            elif getattr(self.project, "base_rom_path", None) and os.path.exists(self.project.base_rom_path):
                with open(self.project.base_rom_path, "rb") as f:
                    rom_data = f.read()

        if self.project:
            from Banco_de_Datos.parche_splash import require_rom_signature
            require_rom_signature(self.project, auto_sign=True, module_name="RouteMapCanvas")

        if not rom_data:
            return None

        self.rom_data = rom_data
        if self.pathfinder:
            self.pathfinder.rom_data = rom_data

        map_parser = getattr(self.project, "map_parser", None) if self.project else None
        if not map_parser:
            try:
                from Nucleos_Positronicos.Nucleo_de_Mapas.mapas import MapParser
                class _StandaloneProj:
                    def __init__(self, rdata):
                        self.virtual_rom = bytearray(rdata)
                        self.base_rom_data = rdata
                proj = self.project if self.project else _StandaloneProj(rom_data)
                map_parser = MapParser(proj)
                map_parser.scan_maps()
                if self.project:
                    self.project.map_parser = map_parser
            except Exception as e:
                print(f"[RouteMapCanvas] Error escaneando mapas: {e}")
                return None

        header_id = get_map_header_id_for_event_map(base_id)
        if header_id is None:
            header_id = base_id

        mh = map_parser.get_map_by_id(header_id)
        if not mh:
            return None

        try:
            from Nucleos_Positronicos.Nucleo_de_Mapas.fomt_mapdata import FomtMapRenderer
            renderer = FomtMapRenderer(rom_data)
            if renderer.load_map(mh):
                img = renderer.render()
                if img:
                    img_data = img.convert("RGBA").tobytes("raw", "RGBA")
                    qim = QImage(img_data, img.width, img.height, img.width * 4, QImage.Format.Format_RGBA8888)
                    return QPixmap.fromImage(qim)
        except Exception as e:
            print(f"[RouteMapCanvas] Error renderizando mapa {base_id} (header {header_id}): {e}")

        return None

    def _generate_synthetic_map(self, base_id: int) -> QPixmap:
        """Genera un plano estético del mapa con colores y proporciones de Mineral Town."""
        is_large_outdoor = base_id in (0x00, 0x01, 0x02, 0x03, 0x05, 0x06, 0x07, 0x08)
        w = 1200 if is_large_outdoor else 380
        h = 600 if is_large_outdoor else 320

        pix = QPixmap(w, h)
        pix.fill(QColor("#161B22"))

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if base_id == 0x02:  # Granja
            painter.fillRect(0, 0, w, h, QColor("#2E5339"))
            painter.fillRect(200, 150, 700, 350, QColor("#4A3525"))
        elif base_id in (0x05, 0x07, 0x06):  # Calles / Pueblo
            painter.fillRect(0, 0, w, h, QColor("#3B4252"))
            painter.fillRect(0, h // 2 - 40, w, 80, QColor("#4C566A"))
        elif base_id == 0x01:  # Playa
            painter.fillRect(0, 0, w, h, QColor("#D8A36D"))
            painter.fillRect(0, h - 180, w, 180, QColor("#2E6A9E"))
        else:  # Interiores
            painter.fillRect(0, 0, w, h, QColor("#3F2E21"))
            painter.fillRect(20, 20, w - 40, h - 40, QColor("#5A4230"))
            painter.fillRect(w // 4, h // 4, w // 2, h // 2, QColor("#7B241C"))

        # Cuadrícula técnica de 32x32
        painter.setPen(QPen(QColor(255, 255, 255, 18), 1))
        for x in range(0, w, 32):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, 32):
            painter.drawLine(0, y, w, y)

        painter.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        painter.setPen(QColor(255, 255, 255, 40))
        painter.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, get_map_display_name(base_id))

        painter.end()
        return pix

    def _apply_map_pixmap(self, pixmap: QPixmap):
        self.map_pixmap = pixmap
        self.map_pixmap_item.setPixmap(pixmap)
        self.scene_obj.setSceneRect(0, 0, pixmap.width(), pixmap.height())
        self.overlay_item.prepareGeometryChange()
        self.overlay_item.update()

    def set_route_segments(self, segments: List[dict], highlight_id: Optional[str] = None):
        """Actualiza los tramos y líneas de movimiento trazados sobre este mapa."""
        self.overlay_item.set_segments(segments, highlight_id)

    def zoom_in(self):
        self.scale(1.25, 1.25)

    def zoom_out(self):
        self.scale(0.8, 0.8)

    def zoom_fit(self):
        if self.map_pixmap and not self.map_pixmap.isNull():
            self.fitInView(self.map_pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def zoom_reset(self):
        self.resetTransform()

    def toggle_vectors(self, show: bool):
        self.overlay_item.show_vectors = show
        self.overlay_item.update()

    def toggle_labels(self, show: bool):
        self.overlay_item.show_labels = show
        self.overlay_item.update()

    def toggle_walkable_grid(self, show: bool):
        self.overlay_item.show_walkable_grid = show
        self.overlay_item.update()

    def wheelEvent(self, event: QWheelEvent):
        factor = 1.15 if event.angleDelta().y() > 0 else (1.0 / 1.15)
        self.scale(factor, factor)
        event.accept()

    def get_selected_segment(self) -> Optional[dict]:
        """Obtiene el segmento actualmente seleccionado/resaltado en el lienzo."""
        hl_id = self.overlay_item.highlight_id
        if not hl_id:
            return None
        for s in self.overlay_item.segments:
            if s.get("id") == hl_id:
                return s
        return None

    def get_active_path_nodes(self) -> List[Tuple[int, int]]:
        """Obtiene la lista mutable de nodos del tramo actualmente seleccionado."""
        seg = self.get_selected_segment()
        if not seg:
            return []
        nodes = seg.get("path_nodes")
        if not nodes:
            nodes = [(seg.get("ax", 0), seg.get("ay", 0)), (seg.get("bx", 0), seg.get("by", 0))]
            seg["path_nodes"] = nodes
        return nodes

    def set_active_node(self, idx: Optional[int]):
        """Establece qué nodo de la ruta está seleccionado en el inspector."""
        self.active_node_idx = idx
        self.overlay_item.update()

    def find_node_at(self, sc_pos: QPointF, threshold: float = 12.0) -> Optional[int]:
        """Encuentra el índice del nodo bajo el cursor (0=A, 1..N-2=Inflexión, N-1=B)."""
        nodes = self.get_active_path_nodes()
        if not nodes:
            return None
        px, py = sc_pos.x(), sc_pos.y()
        for i, (nx, ny) in enumerate(nodes):
            if math.hypot(px - nx, py - ny) <= threshold:
                return i
        return None

    def find_segment_at(self, sc_pos: QPointF, threshold: float = 10.0) -> Optional[Tuple[int, Tuple[int, int]]]:
        """Determina si el cursor está sobre un tramo lineal entre dos nodos y devuelve el índice y el punto proyectado."""
        nodes = self.get_active_path_nodes()
        if len(nodes) < 2:
            return None
        px, py = sc_pos.x(), sc_pos.y()
        for i in range(len(nodes) - 1):
            ax, ay = nodes[i]
            bx, by = nodes[i + 1]
            dx = bx - ax
            dy = by - ay
            l2 = dx * dx + dy * dy
            if l2 == 0:
                continue
            t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
            proj_x = ax + t * dx
            proj_y = ay + t * dy
            d = math.hypot(px - proj_x, py - proj_y)
            if d <= threshold:
                return i, (int(round(proj_x)), int(round(proj_y)))
        return None

    def mousePressEvent(self, event: QMouseEvent):
        sc_pos = self.mapToScene(event.pos())
        if event.button() == Qt.MouseButton.RightButton:
            node_i = self.find_node_at(sc_pos, threshold=12.0)
            if node_i is not None and node_i > 0:
                nodes = self.get_active_path_nodes()
                if node_i < len(nodes) - 1:
                    # Menú contextual sobre un punto de inflexión intermedio
                    self._show_inflection_context_menu(event.globalPosition().toPoint(), node_i)
                    event.accept()
                    return

            self._is_panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        elif event.button() == Qt.MouseButton.LeftButton:
            node_i = self.find_node_at(sc_pos, threshold=12.0)
            if node_i is not None:
                # Iniciar arrastre interactivo del nodo
                self._is_dragging_node = True
                self._dragged_node_idx = node_i
                self.active_node_idx = node_i
                self._drag_start_pos = sc_pos
                nodes = self.get_active_path_nodes()
                nx, ny = nodes[node_i]
                self.node_selected.emit(node_i, nx, ny)
                self.overlay_item.update()
                event.accept()
                return

            x, y = int(sc_pos.x()), int(sc_pos.y())
            self.point_clicked.emit(x, y)

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_panning:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(int(self.horizontalScrollBar().value() - delta.x()))
            self.verticalScrollBar().setValue(int(self.verticalScrollBar().value() - delta.y()))
            event.accept()
            return

        sc_pos = self.mapToScene(event.pos())
        cur_x, cur_y = int(sc_pos.x()), int(sc_pos.y())

        if self._is_dragging_node and self._dragged_node_idx is not None:
            nodes = self.get_active_path_nodes()
            if 0 <= self._dragged_node_idx < len(nodes):
                seg = self.get_selected_segment()
                is_loop = (seg.get("is_loop", False) if seg else False) or (len(nodes) > 1 and nodes[0] == nodes[-1])

                if is_loop and (self._dragged_node_idx == 0 or self._dragged_node_idx == len(nodes) - 1):
                    nodes[0] = (cur_x, cur_y)
                    nodes[-1] = (cur_x, cur_y)
                    if seg:
                        seg["ax"], seg["ay"] = cur_x, cur_y
                        seg["bx"], seg["by"] = cur_x, cur_y
                else:
                    nodes[self._dragged_node_idx] = (cur_x, cur_y)
                    if seg:
                        if self._dragged_node_idx == 0:
                            seg["ax"], seg["ay"] = cur_x, cur_y
                        elif self._dragged_node_idx == len(nodes) - 1:
                            seg["bx"], seg["by"] = cur_x, cur_y
                self.node_moved.emit(self._dragged_node_idx, cur_x, cur_y)
                self.overlay_item.update()
            event.accept()
            return

        # Detección de hover sobre nodos de inflexión o trayectoria
        prev_hover = self._hovered_node_idx
        node_i = self.find_node_at(sc_pos, threshold=12.0)
        self._hovered_node_idx = node_i

        if node_i is not None:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
            nodes = self.get_active_path_nodes()
            nx, ny = nodes[node_i]
            is_loop = (len(nodes) > 1 and nodes[0] == nodes[-1])
            if node_i == 0:
                if is_loop:
                    self.setToolTip(f" [Punto A/B (Bucle Continuo)]: ({nx}, {ny})\nArrastra para trasladar el circuito del bucle")
                else:
                    self.setToolTip(f" [Punto A (Inicio)]: ({nx}, {ny})\nArrastra para mover el inicio de la ruta")
            elif node_i == len(nodes) - 1:
                if is_loop:
                    self.setToolTip(f" [Punto A/B (Bucle Continuo)]: ({nx}, {ny})\nArrastra para trasladar el circuito del bucle")
                else:
                    self.setToolTip(f" [Punto B (Destino)]: ({nx}, {ny})\nArrastra para mover el destino de la ruta")
            else:
                self.setToolTip(f" [Punto de Inflexión #{node_i}]: ({nx}, {ny})\nArrastra para centrar en la calle o Clic Derecho para opciones")
        else:
            seg_match = self.find_segment_at(sc_pos, threshold=8.0)
            if seg_match is not None:
                self.setCursor(Qt.CursorShape.CrossCursor)
                self.setToolTip(f"➕ Trayectoria: ({cur_x}, {cur_y})\nDoble clic aquí para insertar un nuevo Punto de Inflexión")
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
                self.setToolTip(f"Coordenadas: ({cur_x}, {cur_y})")

        if prev_hover != self._hovered_node_idx:
            self.overlay_item.update()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.RightButton:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        elif event.button() == Qt.MouseButton.LeftButton:
            if self._is_dragging_node:
                self._is_dragging_node = False
                sc_pos = self.mapToScene(event.pos())
                fin_x, fin_y = int(sc_pos.x()), int(sc_pos.y())
                idx = self._dragged_node_idx
                self._dragged_node_idx = None
                if idx is not None:
                    self.node_drag_finished.emit(idx, fin_x, fin_y)
                self.overlay_item.update()
                event.accept()
                return

        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            sc_pos = self.mapToScene(event.pos())
            seg_match = self.find_segment_at(sc_pos, threshold=12.0)
            if seg_match is not None:
                seg_idx, (proj_x, proj_y) = seg_match
                insert_idx = seg_idx + 1
                self.node_inserted.emit(insert_idx, proj_x, proj_y)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def _show_inflection_context_menu(self, global_pt: QPointF, node_idx: int):
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtCore import QPoint
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #161B22; color: #F0F6FC; border: 1px solid #30363D; padding: 4px; }"
            "QMenu::item { padding: 5px 20px; border-radius: 3px; }"
            "QMenu::item:selected { background-color: #1F6FEB; color: white; }"
        )
        act_snap = menu.addAction(f" Centrar Inflexión #{node_idx} en Calle/Tile")
        act_del = menu.addAction(f"️ Eliminar Punto de Inflexión #{node_idx}")

        pt = global_pt.toPoint() if hasattr(global_pt, "toPoint") else QPoint(int(global_pt.x()), int(global_pt.y()))
        action = menu.exec(pt)
        if action == act_del:
            self.node_deleted.emit(node_idx)
        elif action == act_snap:
            nodes = self.get_active_path_nodes()
            if 0 <= node_idx < len(nodes):
                nx, ny = nodes[node_idx]
                if self.pathfinder and self.current_map_id is not None:
                    grid = self.pathfinder.get_map_grid(self.current_map_id)
                    if grid:
                        tx, ty = self.pathfinder.snap_to_walkable(grid, nx, ny)
                        nodes[node_idx] = (tx * 8 + 4, ty * 8 + 4)
                        self.node_moved.emit(node_idx, nodes[node_idx][0], nodes[node_idx][1])
                        self.node_drag_finished.emit(node_idx, nodes[node_idx][0], nodes[node_idx][1])
                        self.overlay_item.update()

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        if hasattr(self, "on_view_resized") and callable(self.on_view_resized):
            self.on_view_resized()
