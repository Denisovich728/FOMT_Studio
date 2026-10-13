# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.7.0)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
"""
macro_map_view.py
══════════════════════════════════════════════════════════════════
Lienzo interactivo tipo Google Maps para Macro-Mapas de Mineral Town.
Permite organizar nodos de mapas, conectar warps interactivamente,
y visualizar la ruta de rutinas diarias de los NPCs.
"""

import math
from typing import Dict, List, Optional, Tuple
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsRectItem,
    QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsTextItem,
    QMenu, QInputDialog, QMessageBox, QToolTip
)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QPainterPath, QFont,
    QLinearGradient, QWheelEvent, QMouseEvent, QKeyEvent
)

from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.world_graph import (
    WorldGraph, MapNode, WarpPoint, WarpConnection
)


class WarpPinItem(QGraphicsEllipseItem):
    """Pin visual de una puerta/warp dentro de una tarjeta de mapa."""
    def __init__(self, warp: WarpPoint, parent_node: 'MapNodeItem'):
        super().__init__(-6, -6, 12, 12, parent_node)
        self.warp = warp
        self.parent_node = parent_node
        self.setZValue(10)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setBrush(QBrush(QColor("#00E5FF")))
        self.setPen(QPen(QColor("#FFFFFF"), 2))
        self.setToolTip(f"🚪 {warp.name}\nID: {warp.warp_id} | Coords: ({warp.x}, {warp.y})")

    def hoverEnterEvent(self, event):
        self.setBrush(QBrush(QColor("#FFD600")))
        self.setRect(-8, -8, 16, 16)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setBrush(QBrush(QColor("#00E5FF")))
        self.setRect(-6, -6, 12, 12)
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            view = self.scene().views()[0] if self.scene().views() else None
            if view and hasattr(view, "handle_pin_clicked"):
                view.handle_pin_clicked(self)
                event.accept()
                return
        super().mousePressEvent(event)


class MapNodeItem(QGraphicsRectItem):
    """Tarjeta interactiva que representa un mapa en el macromapa."""
    def __init__(self, node: MapNode, graph: WorldGraph, on_moved_callback=None):
        width = max(160.0, node.width * 2.5)
        height = max(110.0, node.height * 2.0)
        super().__init__(0, 0, width, height)

        self.node = node
        self.graph = graph
        self.on_moved_callback = on_moved_callback
        self.pins: Dict[str, WarpPinItem] = {}

        self.setPos(node.canvas_x, node.canvas_y)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(2)

        self._refresh_pins()

    def _refresh_pins(self):
        # Limpiar pines anteriores
        for pin in self.pins.values():
            if pin.scene():
                self.scene().removeItem(pin)
        self.pins.clear()

        w_rect = self.rect().width()
        h_rect = self.rect().height()

        # Posicionar pines relativos al mapa
        for warp in self.node.warps.values():
            pin = WarpPinItem(warp, self)
            # Mapear coordenadas (x, y) de tiles a la escala de la tarjeta
            norm_x = (warp.x / max(1, self.node.width * 16)) if self.node.width else 0.5
            norm_y = (warp.y / max(1, self.node.height * 16)) if self.node.height else 0.5
            norm_x = max(0.1, min(0.9, norm_x))
            norm_y = max(0.25, min(0.9, norm_y))

            pin.setPos(norm_x * w_rect, norm_y * h_rect)
            self.pins[warp.warp_id] = pin

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Fondo con gradiente oscuro estilo FoMT Studio Cyberpunk/Forerunner
        is_sel = self.isSelected()
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        if is_sel:
            grad.setColorAt(0.0, QColor("#1E2D4A"))
            grad.setColorAt(1.0, QColor("#121A2C"))
            border_color = QColor("#00E5FF")
            border_w = 2.5
        else:
            grad.setColorAt(0.0, QColor("#161B22"))
            grad.setColorAt(1.0, QColor("#0D1117"))
            border_color = QColor("#30363D")
            border_w = 1.5

        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(border_color, border_w))
        painter.drawRoundedRect(rect, 10, 10)

        # Encabezado
        header_rect = QRectF(rect.x(), rect.y(), rect.width(), 28)
        header_grad = QLinearGradient(header_rect.topLeft(), header_rect.bottomLeft())
        header_grad.setColorAt(0.0, QColor("#21262D"))
        header_grad.setColorAt(1.0, QColor("#161B22"))
        painter.setBrush(QBrush(header_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(header_rect, 10, 10)
        # Cuadrado inferior del encabezado para no redondear esquinas bajas
        painter.drawRect(QRectF(rect.x(), rect.y() + 18, rect.width(), 10))

        # Texto de Encabezado: [ID] Nombre
        painter.setPen(QColor("#58A6FF" if not is_sel else "#79C0FF"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        title = f"[{self.node.map_id:02X}] {self.node.name}"
        painter.drawText(QRectF(rect.x() + 10, rect.y() + 4, rect.width() - 20, 20),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)

        # Subtítulo con dimensiones
        painter.setPen(QColor("#8B949E"))
        painter.setFont(QFont("Consolas", 8))
        dim_text = f"{self.node.width}×{self.node.height} | {len(self.node.warps)} Puertas"
        painter.drawText(QRectF(rect.x() + 10, rect.bottom() - 20, rect.width() - 20, 16),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, dim_text)

        # Mini grid decorativo
        painter.setPen(QPen(QColor(255, 255, 255, 12), 1, Qt.PenStyle.DotLine))
        grid_step = 20
        y = rect.y() + 35
        while y < rect.bottom() - 20:
            painter.drawLine(int(rect.x() + 8), int(y), int(rect.right() - 8), int(y))
            y += grid_step

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.node.canvas_x = self.pos().x()
            self.node.canvas_y = self.pos().y()
            if self.on_moved_callback:
                self.on_moved_callback(self)
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event):
        # Doble click para añadir una nueva puerta en esa coordenada
        p = event.pos()
        rect = self.rect()
        tx = int((p.x() / rect.width()) * (self.node.width * 16))
        ty = int((p.y() / rect.height()) * (self.node.height * 16))

        name, ok = QInputDialog.getText(
            None, "Nueva Puerta/Warp",
            f"Mapa: {self.node.name}\nCoordenadas estimadas: ({tx}, {ty})\nNombre del Warp:",
            text=f"Puerta_{len(self.node.warps)+1}"
        )
        if ok and name.strip():
            wid = f"w_{len(self.node.warps)+1}"
            wp = WarpPoint(wid, name.strip(), tx, ty)
            self.node.add_warp(wp)
            self._refresh_pins()
            self.update()
        super().mouseDoubleClickEvent(event)


class WarpConnectionItem(QGraphicsPathItem):
    """Línea de conexión interactiva entre dos warps."""
    def __init__(self, conn: WarpConnection, pin_from: Optional[WarpPinItem],
                 pin_to: Optional[WarpPinItem]):
        super().__init__()
        self.conn = conn
        self.pin_from = pin_from
        self.pin_to = pin_to
        self.setZValue(1)
        self.setAcceptHoverEvents(True)
        self.update_path()

    def update_path(self):
        if not self.pin_from or not self.pin_to:
            self.setPath(QPainterPath())
            return

        p1 = self.pin_from.scenePos()
        p2 = self.pin_to.scenePos()

        path = QPainterPath()
        path.moveTo(p1)

        # Curva de Bézier suave
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        ctrl1 = QPointF(p1.x() + dx * 0.5, p1.y())
        ctrl2 = QPointF(p1.x() + dx * 0.5, p2.y())
        path.cubicTo(ctrl1, ctrl2, p2)

        self.setPath(path)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#00E5FF" if not self.isSelected() else "#FFD600"), 2.5)
        if self.conn.bidirectional:
            pen.setStyle(Qt.PenStyle.SolidLine)
        else:
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawPath(self.path())


class RouteOverlayItem(QGraphicsItem):
    """Capa de visualización de la ruta de un NPC sobre el Macromapa."""
    def __init__(self):
        super().__init__()
        self.setZValue(20)
        self.waypoints_data: List[dict] = []
        self.path_points: List[Tuple[QPointF, str]] = []

    def set_route(self, waypoints: List[dict], node_items: Dict[int, MapNodeItem]):
        self.waypoints_data = waypoints
        self.path_points.clear()

        for idx, wp in enumerate(waypoints):
            mid = wp.get("map_id", 0)
            n_item = node_items.get(mid)
            if not n_item:
                continue

            # Mapear posición dentro del nodo
            w_rect = n_item.rect().width()
            h_rect = n_item.rect().height()
            nx = (wp.get("spawn_x", 0) / max(1, n_item.node.width * 16))
            ny = (wp.get("spawn_y", 0) / max(1, n_item.node.height * 16))
            nx = max(0.1, min(0.9, nx))
            ny = max(0.2, min(0.9, ny))

            sc_pos = n_item.pos() + QPointF(nx * w_rect, ny * h_rect)
            time_str = wp.get("time_str", f"{wp.get('time_val', 0)}m")
            self.path_points.append((sc_pos, f"#{idx+1} {time_str}"))

        self.prepareGeometryChange()
        self.update()

    def boundingRect(self) -> QRectF:
        if not self.path_points:
            return QRectF()
        rect = QRectF(self.path_points[0][0], self.path_points[0][0])
        for pt, _ in self.path_points:
            rect = rect.united(QRectF(pt.x() - 40, pt.y() - 40, 80, 80))
        return rect.adjusted(-50, -50, 50, 50)

    def paint(self, painter: QPainter, option, widget=None):
        if len(self.path_points) < 1:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Línea continua animada de la ruta
        if len(self.path_points) > 1:
            route_path = QPainterPath()
            route_path.moveTo(self.path_points[0][0])
            for pt, _ in self.path_points[1:]:
                route_path.lineTo(pt)

            glow_pen = QPen(QColor(255, 64, 129, 90), 8)
            painter.setPen(glow_pen)
            painter.drawPath(route_path)

            route_pen = QPen(QColor("#FF4081"), 3, Qt.PenStyle.DashLine)
            painter.setPen(route_pen)
            painter.drawPath(route_path)

        # 2. Pines de hitos numerados (Google Maps style)
        for idx, (pt, label) in enumerate(self.path_points):
            # Círculo del pin
            painter.setBrush(QBrush(QColor("#FF4081")))
            painter.setPen(QPen(QColor("#FFFFFF"), 2))
            painter.drawEllipse(pt, 12, 12)

            # Número
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(QRectF(pt.x() - 10, pt.y() - 10, 20, 20),
                             Qt.AlignmentFlag.AlignCenter, str(idx + 1))

            # Etiqueta con hora
            painter.setBrush(QBrush(QColor(20, 20, 25, 220)))
            painter.setPen(QPen(QColor("#FF80AB"), 1))
            lbl_rect = QRectF(pt.x() - 40, pt.y() - 32, 80, 18)
            painter.drawRoundedRect(lbl_rect, 4, 4)
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(lbl_rect, Qt.AlignmentFlag.AlignCenter, label)


class MacroMapView(QGraphicsView):
    """Vista interactiva con soporte para Zoom, Panning y Conexión de Warps."""

    connection_created = pyqtSignal(str, int, str, int, str)  # (id, from_m, from_w, to_m, to_w)

    def __init__(self, world_graph: WorldGraph, parent=None):
        super().__init__(parent)
        self.world_graph = world_graph
        self.scene_obj = QGraphicsScene(self)
        self.setScene(self.scene_obj)

        self.node_items: Dict[int, MapNodeItem] = {}
        self.conn_items: List[WarpConnectionItem] = []
        self.route_overlay = RouteOverlayItem()
        self.scene_obj.addItem(self.route_overlay)

        # Estados de navegación
        self._is_panning = False
        self._pan_start = QPointF()
        self._connect_mode = False
        self._connecting_source_pin: Optional[WarpPinItem] = None

        # Configuración estética del visor
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setBackgroundBrush(QBrush(QColor("#0A0C10")))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        self.setSceneRect(-2000, -2000, 5000, 5000)
        self.rebuild_scene()

    def rebuild_scene(self):
        """Reconstruye todos los elementos gráficos a partir del WorldGraph."""
        # Limpiar ítems previos excepto route_overlay
        for item in list(self.scene_obj.items()):
            if item != self.route_overlay:
                self.scene_obj.removeItem(item)

        self.node_items.clear()
        self.conn_items.clear()

        # 1. Crear Nodos de Mapas
        for node in self.world_graph.nodes.values():
            item = MapNodeItem(node, self.world_graph, self._on_node_moved)
            self.scene_obj.addItem(item)
            self.node_items[node.map_id] = item

        # 2. Crear Conexiones
        self._rebuild_connections()

    def _rebuild_connections(self):
        for conn_item in self.conn_items:
            if conn_item.scene():
                self.scene_obj.removeItem(conn_item)
        self.conn_items.clear()

        for conn in self.world_graph.connections:
            from_node = self.node_items.get(conn.from_map_id)
            to_node = self.node_items.get(conn.to_map_id)
            if not from_node or not to_node:
                continue

            pin_from = from_node.pins.get(conn.from_warp_id)
            pin_to = to_node.pins.get(conn.to_warp_id)

            conn_item = WarpConnectionItem(conn, pin_from, pin_to)
            self.scene_obj.addItem(conn_item)
            self.conn_items.append(conn_item)

    def _on_node_moved(self, node_item: MapNodeItem):
        """Actualiza las líneas de conexión al arrastrar un mapa."""
        for conn_item in self.conn_items:
            conn_item.update_path()

    def set_connect_mode(self, active: bool):
        self._connect_mode = active
        self._connecting_source_pin = None
        if active:
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def handle_pin_clicked(self, pin: WarpPinItem):
        if not self._connect_mode:
            return

        if self._connecting_source_pin is None:
            # Seleccionar pin origen
            self._connecting_source_pin = pin
            pin.setBrush(QBrush(QColor("#FF1744")))
            QToolTip.showText(self.mapToGlobal(self.mapFromScene(pin.scenePos())),
                              "Origen seleccionado. Ahora haz clic en el Pin Destino.")
        else:
            # Pin destino seleccionado -> Crear conexión
            src = self._connecting_source_pin
            dst = pin

            if src == dst:
                src.setBrush(QBrush(QColor("#00E5FF")))
                self._connecting_source_pin = None
                return

            cid = f"conn_{src.parent_node.node.map_id}_{dst.parent_node.node.map_id}_{len(self.world_graph.connections)+1}"
            new_conn = WarpConnection(
                conn_id=cid,
                from_map_id=src.parent_node.node.map_id,
                from_warp_id=src.warp.warp_id,
                to_map_id=dst.parent_node.node.map_id,
                to_warp_id=dst.warp.warp_id,
                bidirectional=True,
                note=f"{src.parent_node.node.name} <-> {dst.parent_node.node.name}"
            )

            self.world_graph.add_connection(new_conn)
            src.setBrush(QBrush(QColor("#00E5FF")))
            self._connecting_source_pin = None
            self.set_connect_mode(False)
            self._rebuild_connections()

            self.connection_created.emit(cid, new_conn.from_map_id, new_conn.from_warp_id,
                                         new_conn.to_map_id, new_conn.to_warp_id)

            QMessageBox.information(
                self, "Warp Conectado",
                f"✅ Conexión establecida:\n"
                f"[{src.parent_node.node.name}] ({src.warp.name}) ⟷\n"
                f"[{dst.parent_node.node.name}] ({dst.warp.name})"
            )

    def set_active_npc_route(self, waypoints: List[dict]):
        """Dibuja en tiempo real la ruta del NPC activo sobre el Macromapa."""
        self.route_overlay.set_route(waypoints, self.node_items)

    def drawBackground(self, painter: QPainter, rect: QRectF):
        super().drawBackground(painter, rect)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Rejilla suave estilo Google Maps / Figma
        grid_size = 50
        pen_sub = QPen(QColor(255, 255, 255, 8), 1)
        pen_main = QPen(QColor(255, 255, 255, 18), 1)

        left = int(math.floor(rect.left() / grid_size) * grid_size)
        top = int(math.floor(rect.top() / grid_size) * grid_size)

        # Líneas verticales
        x = left
        while x < rect.right():
            painter.setPen(pen_main if x % (grid_size * 5) == 0 else pen_sub)
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
            x += grid_size

        # Líneas horizontales
        y = top
        while y < rect.bottom():
            painter.setPen(pen_main if y % (grid_size * 5) == 0 else pen_sub)
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)
            y += grid_size

    def wheelEvent(self, event: QWheelEvent):
        # Zoom suave centrado en cursor
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self.scale(factor, factor)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            self._is_panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_panning:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor if not self._connect_mode else Qt.CursorShape.CrossCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape and self._connect_mode:
            self.set_connect_mode(False)
            if self._connecting_source_pin:
                self._connecting_source_pin.setBrush(QBrush(QColor("#00E5FF")))
                self._connecting_source_pin = None
            event.accept()
            return
        super().keyPressEvent(event)
