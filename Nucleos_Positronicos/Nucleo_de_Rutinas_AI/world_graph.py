# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.7.0)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
"""
world_graph.py
══════════════════════════════════════════════════════════════════
Topología del Mundo Macro-Map para cálculo de Rutinas NPC.
Modela mapas individuales como nodos y puertas/warps como aristas.
Permite edición interactiva por el usuario y cálculo de trayectorias
con algoritmo A* / Dijkstra generando vectores nativos GBA.
"""

import json
import os
import math
import heapq
from typing import Dict, List, Optional, Tuple, Any

# Direcciones nativas FoMT GBA:
# 0: Abajo (+Y)
# 1: Arriba (-Y)
# 2: Izquierda (-X)
# 3: Derecha (+X)
# 4: Frente / Sentado / Especial
DIR_DOWN = 0
DIR_UP = 1
DIR_LEFT = 2
DIR_RIGHT = 3
DIR_FACE = 4


class WarpPoint:
    """Representa un punto de warp o puerta dentro de un mapa específico."""
    def __init__(self, warp_id: str, name: str, x: int, y: int):
        self.warp_id = str(warp_id)
        self.name = name
        self.x = int(x)  # Coordenada en píxeles del mapa
        self.y = int(y)

    def to_dict(self) -> dict:
        return {
            "warp_id": self.warp_id,
            "name": self.name,
            "x": self.x,
            "y": self.y
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'WarpPoint':
        return cls(
            warp_id=data.get("warp_id", "w0"),
            name=data.get("name", "Puerta"),
            x=data.get("x", 0),
            y=data.get("y", 0)
        )


class WarpConnection:
    """Representa un enlace/conexión entre dos warps de dos mapas."""
    def __init__(self, conn_id: str, from_map_id: int, from_warp_id: str,
                 to_map_id: int, to_warp_id: str, bidirectional: bool = True, note: str = ""):
        self.conn_id = str(conn_id)
        self.from_map_id = int(from_map_id)
        self.from_warp_id = str(from_warp_id)
        self.to_map_id = int(to_map_id)
        self.to_warp_id = str(to_warp_id)
        self.bidirectional = bool(bidirectional)
        self.note = note

    def to_dict(self) -> dict:
        return {
            "conn_id": self.conn_id,
            "from_map_id": self.from_map_id,
            "from_warp_id": self.from_warp_id,
            "to_map_id": self.to_map_id,
            "to_warp_id": self.to_warp_id,
            "bidirectional": self.bidirectional,
            "note": self.note
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'WarpConnection':
        return cls(
            conn_id=data.get("conn_id", "c0"),
            from_map_id=data.get("from_map_id", 0),
            from_warp_id=data.get("from_warp_id", ""),
            to_map_id=data.get("to_map_id", 0),
            to_warp_id=data.get("to_warp_id", ""),
            bidirectional=data.get("bidirectional", True),
            note=data.get("note", "")
        )


class MapNode:
    """Nodo en el Macromapa que representa un mapa del juego."""
    def __init__(self, map_id: int, name: str, canvas_x: float = 0, canvas_y: float = 0,
                 width: int = 40, height: int = 40):
        self.map_id = int(map_id)
        self.name = name
        self.canvas_x = float(canvas_x)  # Posición en el macromapa visual
        self.canvas_y = float(canvas_y)
        self.width = int(width)          # Dimensiones del mapa en bloques/tiles
        self.height = int(height)
        self.warps: Dict[str, WarpPoint] = {}

    def add_warp(self, warp: WarpPoint):
        self.warps[warp.warp_id] = warp

    def get_warp(self, warp_id: str) -> Optional[WarpPoint]:
        return self.warps.get(warp_id)

    def to_dict(self) -> dict:
        return {
            "map_id": self.map_id,
            "name": self.name,
            "canvas_x": self.canvas_x,
            "canvas_y": self.canvas_y,
            "width": self.width,
            "height": self.height,
            "warps": [w.to_dict() for w in self.warps.values()]
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'MapNode':
        node = cls(
            map_id=data.get("map_id", 0),
            name=data.get("name", "Mapa"),
            canvas_x=data.get("canvas_x", 0.0),
            canvas_y=data.get("canvas_y", 0.0),
            width=data.get("width", 40),
            height=data.get("height", 40)
        )
        for w_data in data.get("warps", []):
            warp = WarpPoint.from_dict(w_data)
            node.add_warp(warp)
        return node


class WorldGraph:
    """Grafo macroscópico del mundo de FoMT con pathfinder A*."""
    def __init__(self):
        self.nodes: Dict[int, MapNode] = {}
        self.connections: List[WarpConnection] = []

    def get_node(self, map_id: int) -> Optional[MapNode]:
        # Normalizar ID (admite raw GBA e index directo)
        if map_id in self.nodes:
            return self.nodes[map_id]
        # Probar máscara baja si es raw
        low_id = map_id & 0xFF
        if low_id in self.nodes:
            return self.nodes[low_id]
        return None

    def add_node(self, node: MapNode):
        self.nodes[node.map_id] = node

    def add_connection(self, conn: WarpConnection):
        self.connections.append(conn)

    def remove_connection(self, conn_id: str):
        self.connections = [c for c in self.connections if c.conn_id != conn_id]

    def to_dict(self) -> dict:
        return {
            "version": "1.0",
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "connections": [c.to_dict() for c in self.connections]
        }

    def save_to_json(self, file_path: str):
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load_from_json(cls, file_path: str) -> 'WorldGraph':
        graph = cls()
        if not os.path.exists(file_path):
            graph.init_default_topology()
            graph.save_to_json(file_path)
            return graph

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for n_data in data.get("nodes", []):
                node = MapNode.from_dict(n_data)
                graph.add_node(node)
            for c_data in data.get("connections", []):
                conn = WarpConnection.from_dict(c_data)
                graph.add_connection(conn)
            if not graph.nodes:
                graph.init_default_topology()
        except Exception as e:
            print(f"[WorldGraph] Error leyendo {file_path}: {e}. Iniciando defaults.")
            graph.init_default_topology()
        return graph

    def init_default_topology(self):
        """Inicializa una topología por defecto con los mapas principales de Mineral Town."""
        self.nodes.clear()
        self.connections.clear()

        # Configuración inicial espacial tipo Google Maps / Macromapa
        # Coordenadas canvas para un layout armónico y ordenado
        default_maps = [
            # ID, Nombre, CanvasX, CanvasY, Ancho, Alto, Warps[(id, name, x, y)]
            (0x02, "Farm (Granja)", 400, 500, 80, 80, [
                ("to_town", "Salida Norte hacia Pueblo Sur", 400, 32),
                ("to_forest", "Salida Oeste hacia Bosque", 32, 400),
                ("to_house", "Puerta de la Casa", 360, 240),
                ("to_barn", "Puerta del Establo", 200, 200),
                ("to_coop", "Puerta del Gallinero", 500, 200),
            ]),
            (0x07, "South_Side_Town (Pueblo Sur)", 400, 250, 70, 50, [
                ("to_farm", "Entrada Sur desde Granja", 350, 380),
                ("to_north", "Camino Norte hacia Pueblo Norte", 350, 20),
                ("to_square", "Camino Este hacia Plaza Rosa", 540, 200),
                ("to_poultry", "Granja Avícola (Gallinas)", 180, 300),
                ("to_barley", "Granja Yodel (Vacas)", 480, 320),
                ("to_inn", "Taberna de Doug (Entrada Sur)", 300, 80),
            ]),
            (0x05, "North_Side_Town (Pueblo Norte)", 400, 50, 70, 50, [
                ("to_south", "Camino Sur hacia Pueblo Sur", 350, 380),
                ("to_supermarket", "Supermercado Jeff", 180, 160),
                ("to_clinic", "Clínica Mineral", 280, 160),
                ("to_mayor", "Casa del Alcalde Thomas", 100, 280),
                ("to_ellen", "Casa de Ellen", 480, 280),
                ("to_library", "Biblioteca de Mary", 560, 160),
            ]),
            (0x06, "Rose_Square (Plaza Rosa)", 700, 250, 60, 50, [
                ("to_south", "Salida Oeste hacia Pueblo Sur", 30, 250),
                ("to_beach", "Camino Sur hacia Playa", 250, 380),
            ]),
            (0x01, "Mineral_Beach (Playa Mineral)", 700, 500, 70, 60, [
                ("to_square", "Salida Norte hacia Plaza", 350, 20),
                ("to_zack", "Casa de Zack", 120, 200),
                ("to_kai", "Restaurante de Kai", 400, 200),
            ]),
            (0x03, "Forest (Bosque)", 100, 500, 70, 70, [
                ("to_farm", "Salida Este hacia Granja", 540, 350),
                ("to_gotz", "Cabaña de Gotz (Carpintero)", 200, 250),
                ("to_mountain", "Camino hacia Montaña", 100, 100),
            ]),
            (0x00, "Mothers_Hill (Colina Madre)", 100, 250, 80, 80, [
                ("to_forest", "Camino Sur hacia Bosque", 400, 600),
                ("to_peak", "Cima de la Colina", 400, 40),
                ("to_hotsprings", "Aguas Termales & Diosa", 250, 300),
                ("to_mine", "Entrada a Mina", 150, 350),
            ]),
            (0x0C, "Church (Iglesia)", 400, -120, 40, 35, [
                ("exit", "Puerta de Salida", 160, 260),
                ("to_behind", "Puerta Trasera", 160, 40),
            ]),
            (0x0F, "Jeff_Shop / Supermarket", 160, -80, 45, 40, [
                ("exit", "Puerta Principal", 180, 280),
                ("to_back", "Puerta a Trastienda", 80, 60),
            ]),
            (0x13, "Mineral_Clinic (Clínica)", 280, -80, 40, 35, [
                ("exit", "Puerta Principal", 160, 260),
            ]),
            (0x15, "Doug_Inn (Posada / Bar)", 600, 50, 50, 45, [
                ("exit", "Puerta Principal", 200, 300),
                ("to_floor2", "Escaleras Planta Alta", 100, 60),
            ]),
            (0x18, "Mary_Library (Biblioteca)", 720, -80, 45, 40, [
                ("exit", "Puerta Principal", 160, 280),
                ("to_floor2", "Escaleras Planta Alta", 80, 60),
            ]),
            (0x0A, "Poultry_Farm_House (Casa Gallinas)", 160, 250, 40, 35, [
                ("exit", "Puerta Principal", 160, 260),
            ]),
        ]

        for mid, name, cx, cy, w, h, warps in default_maps:
            node = MapNode(mid, name, cx, cy, w, h)
            for wid, wname, wx, wy in warps:
                node.add_warp(WarpPoint(wid, wname, wx, wy))
            self.add_node(node)

        # Conexiones canónicas iniciales
        default_conns = [
            ("c_farm_south", 0x02, "to_town", 0x07, "to_farm", True, "Camino Granja <-> Pueblo Sur"),
            ("c_south_north", 0x07, "to_north", 0x05, "to_south", True, "Camino Pueblo Sur <-> Pueblo Norte"),
            ("c_south_square", 0x07, "to_square", 0x06, "to_south", True, "Pueblo Sur <-> Plaza Rosa"),
            ("c_square_beach", 0x06, "to_beach", 0x01, "to_square", True, "Plaza Rosa <-> Playa"),
            ("c_farm_forest", 0x02, "to_forest", 0x03, "to_farm", True, "Granja <-> Bosque"),
            ("c_forest_hill", 0x03, "to_mountain", 0x00, "to_forest", True, "Bosque <-> Colina Madre"),
            ("c_north_super", 0x05, "to_supermarket", 0x0F, "exit", True, "Pueblo Norte <-> Supermercado"),
            ("c_north_clinic", 0x05, "to_clinic", 0x13, "exit", True, "Pueblo Norte <-> Clínica"),
            ("c_north_lib", 0x05, "to_library", 0x18, "exit", True, "Pueblo Norte <-> Biblioteca"),
            ("c_south_poultry", 0x07, "to_poultry", 0x0A, "exit", True, "Pueblo Sur <-> Granja Avícola"),
            ("c_south_inn", 0x07, "to_inn", 0x15, "exit", True, "Pueblo Sur <-> Posada"),
        ]

        for cid, f_m, f_w, t_m, t_w, bidir, note in default_conns:
            self.add_connection(WarpConnection(cid, f_m, f_w, t_m, t_w, bidir, note))

    def find_world_path(self, start_map_id: int, start_x: int, start_y: int,
                        target_map_id: int, target_x: int, target_y: int) -> Tuple[List[dict], List[Tuple[int, int]]]:
        """
        Calcula la ruta completa a través del grafo de macromapa.
        Retorna:
          - steps: lista estructurada de pasos [walk, warp, walk...]
          - vectors: lista de vectores (distancia, dirección) para la ROM GBA.
        """
        # Normalización de mapa IDs
        start_node = self.get_node(start_map_id)
        target_node = self.get_node(target_map_id)

        if not start_node or not target_node:
            # Caso simple: mismo mapa o mapas sin nodo en grafo
            vecs = self.compute_rectilinear_vectors(start_x, start_y, target_x, target_y)
            step = {
                "type": "walk",
                "map_id": start_map_id,
                "from": (start_x, start_y),
                "to": (target_x, target_y),
                "vectors": vecs
            }
            return [step], vecs

        # Si el inicio y destino son en el mismo mapa:
        if start_node.map_id == target_node.map_id:
            vecs = self.compute_rectilinear_vectors(start_x, start_y, target_x, target_y)
            step = {
                "type": "walk",
                "map_id": start_node.map_id,
                "from": (start_x, start_y),
                "to": (target_x, target_y),
                "vectors": vecs
            }
            return [step], vecs

        # A* / Dijkstra entre mapas a través de Warps
        # Estado: (costo_acumulado, mapa_actual, x_actual, y_actual, camino)
        # camino es lista de tuplas: (tipo, from_map, to_map, from_warp, to_warp)
        adj: Dict[int, List[WarpConnection]] = {}
        for conn in self.connections:
            adj.setdefault(conn.from_map_id, []).append(conn)
            if conn.bidirectional:
                # Invertida
                rev_conn = WarpConnection(
                    conn.conn_id + "_rev", conn.to_map_id, conn.to_warp_id,
                    conn.from_map_id, conn.from_warp_id, True, conn.note
                )
                adj.setdefault(conn.to_map_id, []).append(rev_conn)

        queue = [(0, start_node.map_id, start_x, start_y, [])]
        visited_maps = set()
        best_path = None

        while queue:
            cost, curr_m, cx, cy, path = heapq.heappop(queue)

            if curr_m == target_node.map_id:
                best_path = (path, cx, cy)
                break

            if curr_m in visited_maps:
                continue
            visited_maps.add(curr_m)

            node_obj = self.get_node(curr_m)
            if not node_obj:
                continue

            for conn in adj.get(curr_m, []):
                next_m = conn.to_map_id
                if next_m in visited_maps:
                    continue

                w_from = node_obj.get_warp(conn.from_warp_id)
                next_node = self.get_node(next_m)
                w_to = next_node.get_warp(conn.to_warp_id) if next_node else None

                if not w_from or not w_to:
                    continue

                # Distancia caminada dentro del mapa hasta el warp
                dist_walk = abs(cx - w_from.x) + abs(cy - w_from.y)
                # Penalización por transición de mapa (100 px equivalentes)
                step_cost = dist_walk + 100
                new_path = path + [(conn, (cx, cy), (w_from.x, w_from.y), (w_to.x, w_to.y))]
                heapq.heappush(queue, (cost + step_cost, next_m, w_to.x, w_to.y, new_path))

        steps = []
        all_vectors = []

        if not best_path:
            # No hay camino entre mapas en el grafo; caminata directa de fallback
            vecs = self.compute_rectilinear_vectors(start_x, start_y, target_x, target_y)
            return [{
                "type": "walk", "map_id": start_map_id,
                "from": (start_x, start_y), "to": (target_x, target_y),
                "vectors": vecs
            }], vecs

        path_elements, final_x, final_y = best_path

        # Construir secuencia de pasos detallada
        for conn, (from_pos_x, from_pos_y), (warp_exit_x, warp_exit_y), (warp_entry_x, warp_entry_y) in path_elements:
            # 1. Caminar hasta el warp del mapa origen
            walk_vecs = self.compute_rectilinear_vectors(from_pos_x, from_pos_y, warp_exit_x, warp_exit_y)
            steps.append({
                "type": "walk",
                "map_id": conn.from_map_id,
                "from": (from_pos_x, from_pos_y),
                "to": (warp_exit_x, warp_exit_y),
                "vectors": walk_vecs
            })
            all_vectors.extend(walk_vecs)

            # 2. Paso de Warp / Cruce de umbral
            steps.append({
                "type": "warp",
                "from_map_id": conn.from_map_id,
                "to_map_id": conn.to_map_id,
                "from_warp": conn.from_warp_id,
                "to_warp": conn.to_warp_id,
                "from_coords": (warp_exit_x, warp_exit_y),
                "to_coords": (warp_entry_x, warp_entry_y),
                "note": conn.note
            })

        # 3. Caminar desde el último warp de entrada hasta el destino final
        final_walk_vecs = self.compute_rectilinear_vectors(final_x, final_y, target_x, target_y)
        steps.append({
            "type": "walk",
            "map_id": target_node.map_id,
            "from": (final_x, final_y),
            "to": (target_x, target_y),
            "vectors": final_walk_vecs
        })
        all_vectors.extend(final_walk_vecs)

        # Terminador de vectores para el motor de FoMT
        if not all_vectors or all_vectors[-1] != (0, 0):
            all_vectors.append((0, 0))

        return steps, all_vectors

    @staticmethod
    def compute_rectilinear_vectors(x1: int, y1: int, x2: int, y2: int) -> List[Tuple[int, int]]:
        """
        Calcula vectores GBA ortogonales (rectilíneos) entre dos puntos.
        Formato: (distancia_pixels, direccion_code)
        """
        dx = x2 - x1
        dy = y2 - y1
        vectors = []

        # Movimiento horizontal primero
        if dx != 0:
            dist = abs(dx)
            direction = DIR_RIGHT if dx > 0 else DIR_LEFT
            vectors.append((dist, direction))

        # Movimiento vertical después
        if dy != 0:
            dist = abs(dy)
            direction = DIR_DOWN if dy > 0 else DIR_UP
            vectors.append((dist, direction))

        return vectors
