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

import os
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
    QLinearGradient, QWheelEvent, QMouseEvent, QKeyEvent,
    QPolygonF, QPixmap, QImage
)

from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.world_graph import (
    WorldGraph, MapNode, WarpPoint, WarpConnection
)
from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.fomt_map_names import (
    get_map_header_id_for_event_map, unpack_fomt_map_id, CANONICAL_MAP_INFO
)


class MacroMapImageManager:
    """Proveedor y caché en memoria de mapas de Mineral Town renderizados desde la ROM."""
    _cache: Dict[int, QPixmap] = {}
    _rom_data: Optional[bytes] = None
    _map_parser = None

    @classmethod
    def get_rom_data(cls) -> Optional[bytes]:
        if cls._rom_data:
            return cls._rom_data
        # La ROM debe provenir exclusivamente de la sesion del proyecto verificado
        return None
        return None

    @classmethod
    def get_map_pixmap(cls, map_id: int) -> Optional[QPixmap]:
        base_id, _ = unpack_fomt_map_id(map_id)
        if base_id in cls._cache:
            return cls._cache[base_id]

        rom_data = cls.get_rom_data()
        if rom_data:
            try:
                from Nucleos_Positronicos.Nucleo_de_Mapas.fomt_mapdata import FomtMapRenderer
                from Nucleos_Positronicos.Nucleo_de_Mapas.mapas import MapParser

                if cls._map_parser is None:
                    class _StandaloneProj:
                        def __init__(self, rdata):
                            self.virtual_rom = bytearray(rdata)
                            self.base_rom_data = rdata
                    cls._map_parser = MapParser(_StandaloneProj(rom_data))
                    cls._map_parser.scan_maps()

                header_id = get_map_header_id_for_event_map(base_id)
                if header_id is not None:
                    mh = cls._map_parser.get_map_by_id(header_id)
                    if mh:
                        renderer = FomtMapRenderer(rom_data)
                        if renderer.load_map(mh):
                            img = renderer.render(show_bg1=True, show_bg2=True, show_bg3=True)
                            if img:
                                img_data = img.convert("RGBA").tobytes("raw", "RGBA")
                                qim = QImage(img_data, img.width, img.height, img.width * 4, QImage.Format.Format_RGBA8888)
                                px = QPixmap.fromImage(qim)
                                cls._cache[base_id] = px
                                return px
            except Exception as e:
                print(f"[MacroMapImageManager] Error cargando mapa 0x{base_id:02X} desde ROM: {e}")

        # Fallback sintético detallado si no está en la ROM
        px = cls._generate_synthetic_map(base_id)
        cls._cache[base_id] = px
        return px

    @classmethod
    def _generate_synthetic_map(cls, base_id: int) -> QPixmap:
        """Genera un mapa sintético estético representativo con la identidad de Mineral Town."""
        is_large = base_id in (0x00, 0x01, 0x02, 0x03, 0x05, 0x06, 0x07, 0x08)
        w = 480 if is_large else 240
        h = 320 if is_large else 180

        qim = QImage(w, h, QImage.Format.Format_RGBA8888)
        qim.fill(QColor(18, 24, 32))
        p = QPainter(qim)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Paleta según tipo de mapa
        if base_id == 0x02: # Granja
            bg_c = QColor("#467032") # Pasto
            p.fillRect(0, 0, w, h, bg_c)
            # Tierra arada
            p.fillRect(int(w * 0.15), int(h * 0.35), int(w * 0.7), int(h * 0.5), QColor("#6B4423"))
            # Casa / Establo
            p.fillRect(int(w * 0.55), int(h * 0.1), 80, 50, QColor("#8B3A2B"))
            p.fillRect(int(w * 0.2), int(h * 0.1), 90, 55, QColor("#9E5D2A"))
        elif base_id in (0x05, 0x07): # Pueblo Norte / Sur
            bg_c = QColor("#546E42")
            p.fillRect(0, 0, w, h, bg_c)
            # Calles empedradas
            p.fillRect(0, int(h * 0.45), w, 40, QColor("#8A8F85"))
            p.fillRect(int(w * 0.48), 0, 40, h, QColor("#8A8F85"))
            # Techos de casas
            for cx, cy in [(40, 25), (140, 20), (320, 25), (60, 210), (330, 210)]:
                p.fillRect(cx, cy, 60, 40, QColor("#A84232"))
        elif base_id == 0x06: # Plaza Rosa
            p.fillRect(0, 0, w, h, QColor("#4E6839"))
            # Gran círculo empedrado
            p.setBrush(QBrush(QColor("#B85D5D")))
            p.setPen(QPen(QColor("#7A3333"), 3))
            p.drawEllipse(int(w * 0.2), int(h * 0.15), int(w * 0.6), int(h * 0.7))
        elif base_id == 0x01: # Playa
            p.fillRect(0, 0, w, int(h * 0.65), QColor("#D9BC7D")) # Arena
            p.fillRect(0, int(h * 0.65), w, int(h * 0.35), QColor("#2B629E")) # Mar
            p.fillRect(int(w * 0.45), int(h * 0.5), 35, 75, QColor("#6E472A")) # Muelle
        elif base_id == 0x03: # Bosque
            p.fillRect(0, 0, w, h, QColor("#2A5222"))
            p.fillRect(int(w * 0.35), int(h * 0.3), 70, 50, QColor("#704221")) # Cabaña Gotz
        elif base_id in (0x00, 0x08): # Colina Madre / Cima
            p.fillRect(0, 0, w, h, QColor("#595B52"))
            p.fillRect(int(w * 0.2), int(h * 0.3), int(w * 0.6), int(h * 0.4), QColor("#456832"))
            # Aguas termales / lago
            p.setBrush(QBrush(QColor("#387E9E")))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(int(w * 0.3), int(h * 0.45), 70, 50)
        else: # Interiores
            p.fillRect(0, 0, w, h, QColor("#221D1A"))
            p.fillRect(10, 10, w - 20, h - 20, QColor("#BA8E59")) # Piso de madera
            p.fillRect(20, 20, w - 40, 25, QColor("#664B30")) # Mostrador

        p.end()
        return QPixmap.fromImage(qim)


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
        self.setToolTip(f" {warp.name}\nID: {warp.warp_id} | Coords: ({warp.x}, {warp.y})")

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
    """Tarjeta interactiva que representa un mapa real de Mineral Town con gráficos en el macromapa."""
    def __init__(self, node: MapNode, graph: WorldGraph, on_moved_callback=None):
        self.node = node
        self.graph = graph
        self.on_moved_callback = on_moved_callback
        self.pins: Dict[str, WarpPinItem] = {}

        # 1. Obtener imagen real del mapa desde ROM o generador de Mineral Town
        self.pixmap: Optional[QPixmap] = MacroMapImageManager.get_map_pixmap(node.map_id)

        # 2. Calcular dimensiones proporcionales para preservar la escala espacial de Mineral Town
        if self.pixmap and not self.pixmap.isNull():
            orig_w = self.pixmap.width()
            orig_h = self.pixmap.height()
        else:
            orig_w = max(40, node.width) * 8
            orig_h = max(30, node.height) * 8

        # Factor de escala visual
        if orig_w > 900:  # Mapas masivos (Granja, Pueblo Norte, Pueblo Sur)
            scale = 0.35
        elif orig_w > 400:  # Mapas medianos (Plaza, Playa, Bosque, Colina Madre)
            scale = 0.40
        else:  # Mapas interiores o compactos
            scale = 0.45

        self.native_w = orig_w
        self.native_h = orig_h
        self.header_h = 24.0

        width = max(160.0, orig_w * scale)
        height = max(110.0, orig_h * scale + self.header_h)
        super().__init__(0, 0, width, height)

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
        h_body = self.rect().height() - self.header_h

        # Posicionar pines relativos al mapa real
        for warp in self.node.warps.values():
            pin = WarpPinItem(warp, self)
            
            # Normalizar coordenadas de la puerta respecto a las dimensiones nativas del mapa
            norm_x = (warp.x / max(1, self.native_w)) if self.native_w else 0.5
            norm_y = (warp.y / max(1, self.native_h)) if self.native_h else 0.5
            norm_x = max(0.04, min(0.96, norm_x))
            norm_y = max(0.04, min(0.96, norm_y))

            pin_x = norm_x * w_rect
            pin_y = self.header_h + norm_y * h_body
            pin.setPos(pin_x, pin_y)
            self.pins[warp.warp_id] = pin

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        is_sel = self.isSelected()
        border_color = QColor("#00E5FF" if is_sel else "#30363D")
        border_w = 2.5 if is_sel else 1.5

        # 1. Dibujar el mapa real de Mineral Town en el cuerpo
        body_rect = QRectF(rect.x(), rect.y() + self.header_h, rect.width(), rect.height() - self.header_h)
        if self.pixmap and not self.pixmap.isNull():
            painter.drawPixmap(body_rect.toRect(), self.pixmap)
        else:
            painter.setBrush(QBrush(QColor("#161B22")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(body_rect)

        # 2. Marco perimetral estético con esquinas redondeadas
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(border_color, border_w))
        painter.drawRoundedRect(rect, 6, 6)

        # 3. Encabezado translúcido estilo glassmorphism (no tapa el mapa)
        header_rect = QRectF(rect.x(), rect.y(), rect.width(), self.header_h)
        header_grad = QLinearGradient(header_rect.topLeft(), header_rect.bottomLeft())
        if is_sel:
            header_grad.setColorAt(0.0, QColor(30, 45, 74, 235))
            header_grad.setColorAt(1.0, QColor(18, 26, 44, 235))
        else:
            header_grad.setColorAt(0.0, QColor(22, 27, 34, 220))
            header_grad.setColorAt(1.0, QColor(13, 17, 23, 220))

        painter.setBrush(QBrush(header_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(header_rect, 6, 6)
        painter.drawRect(QRectF(rect.x(), rect.y() + self.header_h - 4, rect.width(), 4))

        # Texto de Encabezado: [ID] Nombre
        painter.setPen(QColor("#58A6FF" if not is_sel else "#79C0FF"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        title = f"[{self.node.map_id:02X}] {self.node.name}"
        painter.drawText(QRectF(rect.x() + 8, rect.y(), rect.width() - 16, self.header_h),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)

        # Indicador de warps en la esquina superior derecha
        dim_text = f"{len(self.node.warps)} Puertas"
        painter.setPen(QColor("#8B949E"))
        painter.setFont(QFont("Consolas", 7))
        painter.drawText(QRectF(rect.x(), rect.y(), rect.width() - 8, self.header_h),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, dim_text)

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
        h_body = rect.height() - self.header_h
        norm_x = max(0.0, min(1.0, p.x() / rect.width()))
        norm_y = max(0.0, min(1.0, (p.y() - self.header_h) / max(1.0, h_body)))
        tx = int(norm_x * self.native_w)
        ty = int(norm_y * self.native_h)

        name, ok = QInputDialog.getText(
            None, "Nueva Puerta/Warp",
            f"Mapa: {self.node.name}\nCoordenadas en el mapa: ({tx}, {ty})\nNombre de la Puerta:",
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
    """Línea de conexión interactiva entre dos puertas reales de Mineral Town (estilo camino/carretera)."""
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

        # Curva de Bézier suave que conecta naturalmente los mapas
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        ctrl1 = QPointF(p1.x() + dx * 0.5, p1.y())
        ctrl2 = QPointF(p1.x() + dx * 0.5, p2.y())
        path.cubicTo(ctrl1, ctrl2, p2)

        self.setPath(path)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.path() or self.path().isEmpty():
            return

        is_sel = self.isSelected()
        c_base = QColor("#00E5FF" if not is_sel else "#FFD600")

        # 1. Base ancha estilo camino / carretera que conecta las puertas reales
        road_pen = QPen(QColor(18, 26, 44, 210), 7.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(road_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.strokePath(self.path(), road_pen)

        # 2. Línea central luminosa indicadora de flujo
        line_pen = QPen(c_base, 2.5, Qt.PenStyle.SolidLine if self.conn.bidirectional else Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(line_pen)
        painter.strokePath(self.path(), line_pen)


class RouteOverlayItem(QGraphicsItem):
    """Capa de visualización de la ruta de un NPC sobre el Macromapa con soporte de rutas por todo el mundo."""
    def __init__(self, world_graph: Optional[WorldGraph] = None):
        super().__init__()
        self.world_graph = world_graph
        self.setZValue(20)
        self.waypoints_data: List[dict] = []
        self.path_points: List[Tuple[QPointF, str]] = []
        # Tramos A -> B orquestados (para modo por mapa o por NPC)
        self.orchestrated_segments: List[dict] = []
        # Rutas continuas por todo el mundo inter-mapa a través de warps
        self.world_paths: List[dict] = []
        self.highlighted_seg_id: Optional[str] = None

    def _map_point_to_scene(self, mid: int, tx: float, ty: float, node_items: Dict[int, MapNodeItem]) -> Optional[QPointF]:
        n_item = node_items.get(mid & 0xFF)
        if not n_item:
            return None
        w_rect = n_item.rect().width()
        h_rect = n_item.rect().height()
        mw = max(1, n_item.node.width * 16)
        mh = max(1, n_item.node.height * 16)
        nx = max(0.06, min(0.94, tx / mw))
        ny = max(0.20, min(0.94, ty / mh))
        return n_item.pos() + QPointF(nx * w_rect, ny * h_rect)

    def _get_warp_scene_point(self, mid: int, warp_id: Optional[str], fallback_x: float, fallback_y: float,
                              node_items: Dict[int, MapNodeItem]) -> Optional[QPointF]:
        n_item = node_items.get(mid & 0xFF)
        if not n_item:
            return None
        if warp_id and warp_id in n_item.pins:
            return n_item.pins[warp_id].scenePos()
        return self._map_point_to_scene(mid, fallback_x, fallback_y, node_items)

    def set_route(self, waypoints: List[dict], node_items: Dict[int, MapNodeItem]):
        self.orchestrated_segments.clear()
        self.world_paths.clear()
        self.waypoints_data = waypoints
        self.path_points.clear()

        for idx, wp in enumerate(waypoints):
            mid = wp.get("map_id", 0) & 0xFF
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

    def set_orchestrated_segments(self, segments: List[dict], node_items: Dict[int, MapNodeItem],
                                  highlight_id: Optional[str] = None,
                                  world_graph: Optional[WorldGraph] = None):
        """Configura los tramos orquestados A -> B con delays, velocidades y cálculo automático de rutas por todo el mundo."""
        self.path_points.clear()
        self.orchestrated_segments.clear()
        self.world_paths.clear()
        self.highlighted_seg_id = highlight_id
        if world_graph:
            self.world_graph = world_graph

        npc_palette = [
            "#00E5FF", "#76FF03", "#FFD600", "#FF1744", "#D500F9",
            "#FF6D00", "#00E676", "#2979FF", "#F50057", "#FF4081"
        ]

        for idx, seg in enumerate(segments):
            mid = seg.get("map_id", 0) & 0xFF
            n_item = node_items.get(mid)
            if not n_item:
                continue

            w_rect = n_item.rect().width()
            h_rect = n_item.rect().height()
            mw = max(1, n_item.node.width * 16)
            mh = max(1, n_item.node.height * 16)

            # Posición punto A
            nxa = max(0.08, min(0.92, seg.get("ax", 0) / mw))
            nya = max(0.22, min(0.92, seg.get("ay", 0) / mh))
            pt_a = n_item.pos() + QPointF(nxa * w_rect, nya * h_rect)

            # Posición punto B
            nxb = max(0.08, min(0.92, seg.get("bx", 0) / mw))
            nyb = max(0.22, min(0.92, seg.get("by", 0) / mh))
            pt_b = n_item.pos() + QPointF(nxb * w_rect, nyb * h_rect)

            color = npc_palette[seg.get("npc_id", 0) % len(npc_palette)]
            is_hl = (seg.get("id") == highlight_id)

            self.orchestrated_segments.append({
                "id": seg.get("id", str(idx)),
                "npc_name": seg.get("npc_name", "NPC"),
                "map_id": mid,
                "pt_a": pt_a,
                "pt_b": pt_b,
                "color": color,
                "speed": seg.get("speed_str", "1.0x"),
                "delay": seg.get("delay_str", "0m"),
                "time_str": seg.get("time_str", ""),
                "is_highlight": is_hl
            })

            # Trazar ruta inter-mapa por todo el mundo si este tramo o la transición viene de otro mapa
            steps = seg.get("world_path_steps")
            from_mid = None
            to_mid = mid

            # Si no hay steps explícitos, verificar si el segmento anterior estaba en otro mapa
            if not steps and idx > 0 and self.world_graph:
                prev_seg = segments[idx - 1]
                prev_mid = prev_seg.get("map_id", 0) & 0xFF
                if prev_mid != mid:
                    from_mid = prev_mid
                    pax, pay = prev_seg.get("bx", 0), prev_seg.get("by", 0)
                    pbx, pby = seg.get("ax", 0), seg.get("ay", 0)
                    steps, _ = self.world_graph.find_world_path(prev_mid, pax, pay, mid, pbx, pby)

            # Si se dispone de steps que cruzan entre mapas
            if steps:
                has_warps = any(st.get("type") == "warp" for st in steps)
                if has_warps:
                    visual_steps = []
                    total_world_dist = 0

                    for st in steps:
                        st_type = st.get("type")
                        if st_type == "walk":
                            smid = st.get("map_id", 0) & 0xFF
                            fx, fy = st.get("from", (0, 0))
                            tx, ty = st.get("to", (0, 0))
                            total_world_dist += abs(tx - fx) + abs(ty - fy)
                            p1 = self._map_point_to_scene(smid, fx, fy, node_items)
                            p2 = self._map_point_to_scene(smid, tx, ty, node_items)
                            if p1 and p2:
                                visual_steps.append({
                                    "type": "walk",
                                    "map_id": smid,
                                    "p1": p1,
                                    "p2": p2
                                })
                        elif st_type == "warp":
                            fm = st.get("from_map_id", 0) & 0xFF
                            tm = st.get("to_map_id", 0) & 0xFF
                            fcx, fcy = st.get("from_coords", (0, 0))
                            tcx, tcy = st.get("to_coords", (0, 0))
                            fw_id = st.get("from_warp")
                            tw_id = st.get("to_warp")

                            p_exit = self._get_warp_scene_point(fm, fw_id, fcx, fcy, node_items)
                            p_entry = self._get_warp_scene_point(tm, tw_id, tcx, tcy, node_items)
                            if p_exit and p_entry:
                                visual_steps.append({
                                    "type": "warp",
                                    "from_map": fm,
                                    "to_map": tm,
                                    "p_exit": p_exit,
                                    "p_entry": p_entry,
                                    "note": st.get("note", f"Warp {fm} -> {tm}"),
                                    "to_map_name": get_map_display_name(tm) if "get_map_display_name" in globals() else f"Mapa 0x{tm:02X}"
                                })

                    if visual_steps:
                        self.world_paths.append({
                            "seg_id": seg.get("id"),
                            "npc_name": seg.get("npc_name", "NPC"),
                            "color": color,
                            "is_highlight": is_hl,
                            "visual_steps": visual_steps,
                            "total_dist": total_world_dist
                        })

        self.prepareGeometryChange()
        self.update()

    def boundingRect(self) -> QRectF:
        all_pts: List[QPointF] = [p for p, _ in self.path_points]
        for s in self.orchestrated_segments:
            all_pts.extend([s["pt_a"], s["pt_b"]])

        for wp in self.world_paths:
            for vs in wp.get("visual_steps", []):
                if vs["type"] == "walk":
                    all_pts.extend([vs["p1"], vs["p2"]])
                elif vs["type"] == "warp":
                    all_pts.extend([vs["p_exit"], vs["p_entry"]])

        if not all_pts:
            return QRectF()
        rect = QRectF(all_pts[0], all_pts[0])
        for pt in all_pts:
            rect = rect.united(QRectF(pt.x() - 60, pt.y() - 60, 120, 120))
        return rect.adjusted(-100, -100, 100, 100)

    def _draw_directed_arrow(self, painter: QPainter, p1: QPointF, p2: QPointF, color: QColor, size: float = 8.0):
        """Dibuja una flecha direccional estética en el centro de un segmento."""
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        dist = math.hypot(dx, dy)
        if dist < 12:
            return

        mid = QPointF((p1.x() + p2.x()) / 2.0, (p1.y() + p2.y()) / 2.0)
        angle = math.atan2(dy, dx)

        arrow_head = QPolygonF()
        arrow_head.append(mid + QPointF(math.cos(angle) * size, math.sin(angle) * size))
        arrow_head.append(mid + QPointF(math.cos(angle + 2.5) * size, math.sin(angle + 2.5) * size))
        arrow_head.append(mid + QPointF(math.cos(angle - 2.5) * size, math.sin(angle - 2.5) * size))

        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor("#FFFFFF"), 1))
        painter.drawPolygon(arrow_head)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Modo por defecto: Hitos secuenciales de un solo NPC
        if self.path_points:
            if len(self.path_points) > 1:
                route_path = QPainterPath()
                route_path.moveTo(self.path_points[0][0])
                for pt, _ in self.path_points[1:]:
                    route_path.lineTo(pt)

                glow_pen = QPen(QColor(255, 64, 129, 90), 8)
                painter.setPen(glow_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.strokePath(route_path, glow_pen)

                route_pen = QPen(QColor("#FF4081"), 3, Qt.PenStyle.DashLine)
                painter.setPen(route_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.strokePath(route_path, route_pen)

            for idx, (pt, label) in enumerate(self.path_points):
                painter.setBrush(QBrush(QColor("#FF4081")))
                painter.setPen(QPen(QColor("#FFFFFF"), 2))
                painter.drawEllipse(pt, 12, 12)

                painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                painter.setPen(QColor("#FFFFFF"))
                painter.drawText(QRectF(pt.x() - 10, pt.y() - 10, 20, 20),
                                 Qt.AlignmentFlag.AlignCenter, str(idx + 1))

                painter.setBrush(QBrush(QColor(20, 20, 25, 220)))
                painter.setPen(QPen(QColor("#FF80AB"), 1))
                lbl_rect = QRectF(pt.x() - 40, pt.y() - 32, 80, 18)
                painter.drawRoundedRect(lbl_rect, 4, 4)
                painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                painter.setPen(QColor("#FFFFFF"))
                painter.drawText(lbl_rect, Qt.AlignmentFlag.AlignCenter, label)
                painter.setBrush(Qt.BrushStyle.NoBrush)

        # 2. Rutas Continuas por todo el Mundo a través de Warps (Líneas Globales)
        for wp in self.world_paths:
            c = QColor(wp["color"])
            is_hl = wp.get("is_highlight", False)
            for vs in wp.get("visual_steps", []):
                if vs["type"] == "walk":
                    p1 = vs["p1"]
                    p2 = vs["p2"]
                    # Halo resplandeciente
                    glow_p = QPen(QColor(c.red(), c.green(), c.blue(), 100 if is_hl else 55), 9 if is_hl else 6)
                    painter.setPen(glow_p)
                    painter.drawLine(p1, p2)
                    # Línea principal
                    main_p = QPen(c if is_hl else QColor(c.red(), c.green(), c.blue(), 190), 3 if is_hl else 2, Qt.PenStyle.DashLine)
                    painter.setPen(main_p)
                    painter.drawLine(p1, p2)
                    self._draw_directed_arrow(painter, p1, p2, c, size=7.0)

                elif vs["type"] == "warp":
                    p_exit = vs["p_exit"]
                    p_entry = vs["p_entry"]

                    # Curva de Bézier cúbica suave entre warps de mapas distintos
                    dx = p_entry.x() - p_exit.x()
                    ctrl1 = QPointF(p_exit.x() + dx * 0.5, p_exit.y())
                    ctrl2 = QPointF(p_exit.x() + dx * 0.5, p_entry.y())

                    b_path = QPainterPath()
                    b_path.moveTo(p_exit)
                    b_path.cubicTo(ctrl1, ctrl2, p_entry)

                    # Halo de energía cósmica / warp de gran intensidad
                    glow_warp = QPen(QColor(c.red(), c.green(), c.blue(), 130 if is_hl else 70), 12 if is_hl else 8)
                    painter.setPen(glow_warp)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.strokePath(b_path, glow_warp)

                    # Trazado central de neón
                    neon_warp = QPen(QColor("#FFFFFF" if is_hl else c.name()), 3.5 if is_hl else 2.5, Qt.PenStyle.SolidLine if is_hl else Qt.PenStyle.DashDotLine)
                    painter.setPen(neon_warp)
                    painter.strokePath(b_path, neon_warp)

                    # Portales circulares en los warps de salida y entrada
                    for port_pt, is_ent in [(p_exit, False), (p_entry, True)]:
                        painter.setBrush(QBrush(QColor("#00E5FF" if not is_ent else "#00E676")))
                        painter.setPen(QPen(QColor("#FFFFFF"), 2))
                        painter.drawEllipse(port_pt, 7, 7)
                        painter.setBrush(QBrush(QColor(13, 17, 23, 220)))
                        painter.drawEllipse(port_pt, 3, 3)

                    # Flecha en el centro de la curva Bézier calculada
                    t = 0.5
                    mid_curve = (b_path.pointAtPercent(t))
                    tangent_ang = b_path.angleAtPercent(t)
                    rad = math.radians(-tangent_ang)
                    arrow_sz = 9.0 if is_hl else 7.5
                    arr = QPolygonF()
                    arr.append(mid_curve + QPointF(math.cos(rad) * arrow_sz, math.sin(rad) * arrow_sz))
                    arr.append(mid_curve + QPointF(math.cos(rad + 2.5) * arrow_sz, math.sin(rad + 2.5) * arrow_sz))
                    arr.append(mid_curve + QPointF(math.cos(rad - 2.5) * arrow_sz, math.sin(rad - 2.5) * arrow_sz))
                    painter.setBrush(QBrush(QColor("#FFFFFF") if is_hl else c))
                    painter.setPen(QPen(QColor("#000000"), 1))
                    painter.drawPolygon(arr)

                    # Badge / Etiqueta de Cruce de Puerta Inter-Mapa
                    warp_tag = f"Cruce: {vs.get('to_map_name', 'Puerta')}"
                    tag_w = max(80, len(warp_tag) * 6 + 16)
                    tag_box = QRectF(mid_curve.x() - tag_w / 2, mid_curve.y() - 20, tag_w, 16)
                    painter.setBrush(QBrush(QColor(13, 17, 23, 235)))
                    painter.setPen(QPen(c if is_hl else QColor("#30363D"), 1.2))
                    painter.drawRoundedRect(tag_box, 4, 4)
                    painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                    painter.setPen(QColor("#FFFFFF"))
                    painter.drawText(tag_box, Qt.AlignmentFlag.AlignCenter, warp_tag)

        # 3. Modo Orquestador de Tramos A -> B Locales (Delays, Velocidades, Por Mapa o NPC)
        for seg in self.orchestrated_segments:
            pt_a = seg["pt_a"]
            pt_b = seg["pt_b"]
            c = QColor(seg["color"])
            is_hl = seg.get("is_highlight", False)

            # Línea de trayectoria A -> B
            line_w = 4.0 if is_hl else 2.5
            alpha = 255 if is_hl else 180
            pen_color = QColor(c.red(), c.green(), c.blue(), alpha)

            if is_hl:
                # Halo de resalto
                halo_pen = QPen(QColor(c.red(), c.green(), c.blue(), 100), 10)
                painter.setPen(halo_pen)
                painter.drawLine(pt_a, pt_b)

            painter.setPen(QPen(pen_color, line_w, Qt.PenStyle.SolidLine if is_hl else Qt.PenStyle.DashLine))
            painter.drawLine(pt_a, pt_b)

            # Punto A (Inicio)
            painter.setBrush(QBrush(QColor("#00E676")))
            painter.setPen(QPen(QColor("#FFFFFF"), 1.5))
            painter.drawEllipse(pt_a, 7, 7)
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.setPen(QColor("#000000"))
            painter.drawText(QRectF(pt_a.x() - 6, pt_a.y() - 6, 12, 12), Qt.AlignmentFlag.AlignCenter, "A")

            # Punto B (Llegada)
            painter.setBrush(QBrush(QColor("#FF1744")))
            painter.setPen(QPen(QColor("#FFFFFF"), 1.5))
            painter.drawEllipse(pt_b, 7, 7)
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(QRectF(pt_b.x() - 6, pt_b.y() - 6, 12, 12), Qt.AlignmentFlag.AlignCenter, "B")

            # Etiqueta de Orquestación en el centro del tramo (Velocidad, Delay, NPC)
            mid_pt = QPointF((pt_a.x() + pt_b.x()) / 2, (pt_a.y() + pt_b.y()) / 2)
            tag_text = f"{seg['npc_name']} | Vel:{seg['speed']} | Wait:{seg['delay']}"

            painter.setBrush(QBrush(QColor(13, 17, 23, 230)))
            painter.setPen(QPen(c if is_hl else QColor("#30363D"), 1.5 if is_hl else 1))
            tag_rect = QRectF(mid_pt.x() - 65, mid_pt.y() - 11, 130, 22)
            painter.drawRoundedRect(tag_rect, 5, 5)

            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold if is_hl else QFont.Weight.Normal))
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, tag_text)


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
        self.route_overlay = RouteOverlayItem(self.world_graph)
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

        # 3. Auto-organización geográfica si los mapas están amontonados en las coordenadas viejas
        farm_node = self.world_graph.get_node(0x02)
        if farm_node and farm_node.canvas_x == 400.0 and farm_node.canvas_y == 500.0:
            self.auto_layout_mineral_town(save_to_file=True)

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

    def set_active_orchestrated_segments(self, segments: List[dict], highlight_id: Optional[str] = None):
        """Dibuja los tramos orquestados A -> B con velocidades, delays y rutas mundiales continuas."""
        self.route_overlay.set_orchestrated_segments(segments, self.node_items, highlight_id, self.world_graph)

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

    def auto_layout_mineral_town(self, save_to_file: bool = True):
        """Organiza automáticamente todos los mapas en su geografía canónica de Mineral Town."""
        GEO_COORDS = {
            0x02: (850, 800),     # Granja del Jugador (Centro Sur)
            0x1D: (850, 1150),    # Casa de la Granja (Sur de la Granja)
            0x07: (850, 500),     # Pueblo Sur (Norte de la Granja)
            0x0A: (440, 500),     # Granja Avícola Lillia (Oeste de Pueblo Sur)
            0x0B: (260, 500),     # Granja Avícola P2
            0x29: (1380, 500),    # Granja Yodel Barley (Este de Pueblo Sur)
            0x2A: (1560, 500),    # Granja Yodel P2
            0x15: (850, 360),     # Posada Doug (Entre Pueblo Sur y Norte)
            0x16: (1030, 360),    # Posada Cocina
            0x17: (670, 360),     # Posada P2
            0x05: (850, 50),      # Pueblo Norte (Centro Norte)
            0x0F: (440, 50),      # Supermercado Jeff (Oeste de Pueblo Norte)
            0x10: (260, 50),      # Supermercado Trastienda
            0x13: (440, -120),    # Clínica Mineral (Noroeste de Pueblo Norte)
            0x14: (260, -120),    # Clínica P2
            0x1E: (440, 220),     # Casa Alcalde Thomas (Suroeste de Pueblo Norte)
            0x0E: (1380, 220),    # Casa de Ellen (Sureste de Pueblo Norte)
            0x26: (1380, -120),   # Herrería Saibara (Noreste de Pueblo Norte)
            0x18: (1380, 50),     # Biblioteca Mary (Este de Pueblo Norte)
            0x19: (1560, 50),     # Biblioteca P2
            0x0C: (850, -280),    # Iglesia Carter (Norte de Pueblo Norte)
            0x04: (850, -480),    # Jardín Trasero Iglesia
            0x06: (1500, 500),    # Plaza Rosa (Este de Pueblo Sur)
            0x1F: (1500, 220),    # Bodega Aja (Norte de Plaza Rosa)
            0x20: (1680, 220),    # Bodega Aja P2
            0x22: (1860, 220),    # Bodega Aja Cava
            0x01: (1500, 800),    # Playa Mineral (Sur de Plaza Rosa)
            0x0D: (1820, 800),    # Casa de Zack (Playa)
            0x24: (1820, 950),    # Chiringuito de Kai (Playa)
            0x03: (250, 800),     # Bosque de Gotz (Oeste de la Granja)
            0x28: (50, 800),      # Cabaña de Gotz
            0x00: (250, 420),     # Colina Madre / Cascada Diosa / Termales (Norte del Bosque)
            0x08: (250, 80),      # Cima de la Colina (Norte de Colina Madre)
        }

        for mid, pos in GEO_COORDS.items():
            node = self.world_graph.get_node(mid)
            if node:
                node.canvas_x = float(pos[0])
                node.canvas_y = float(pos[1])
                node_item = self.node_items.get(node.map_id)
                if node_item:
                    node_item.setPos(node.canvas_x, node.canvas_y)

        # Actualizar las líneas de conexión
        for conn_item in self.conn_items:
            conn_item.update_path()

        parent_w = self.parent()
        if save_to_file and parent_w and hasattr(parent_w, "default_graph_path"):
            try:
                self.world_graph.save_to_json(parent_w.default_graph_path)
            except Exception:
                pass
        self.update()
