# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.8.0)
# Núcleo de Rutinas AI: Navegación & Pathfinding por Tiles Caminables
# ============================================================
"""
tile_pathfinder.py
══════════════════════════════════════════════════════════════
Motor de navegación ortogonal A* (AWSD) sobre el grid de colisiones
de Harvest Moon: FoMT.
- Garantiza movimiento estrictamente Manhattan (Arriba, Abajo, Izquierda, Derecha).
- Respeta muros, ríos, vallas, árboles y zonas no transitables.
- Convierte rutas de tiles a coordenadas de píxeles exactas y pasos GBA.
"""

import os
import struct
import heapq
from typing import Optional, List, Tuple, Dict, Any

from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.fomt_map_names import (
    get_map_header_id_for_event_map, unpack_fomt_map_id
)


class TilePathfinder:
    """Buscador de rutas A* ortogonal sobre la matriz de colisión de Mineral Town."""

    def __init__(self, project=None, rom_data: Optional[bytes] = None):
        self.project = project
        self.rom_data = rom_data
        self._map_grids_cache: Dict[int, Dict[str, Any]] = {}

    def _ensure_rom_data(self) -> Optional[bytes]:
        if self.rom_data:
            return self.rom_data

        if self.project:
            if getattr(self.project, "virtual_rom", None):
                self.rom_data = bytes(self.project.virtual_rom)
                return self.rom_data
            elif getattr(self.project, "base_rom_data", None):
                self.rom_data = self.project.base_rom_data
                return self.rom_data
            elif getattr(self.project, "base_rom_path", None) and os.path.exists(self.project.base_rom_path):
                try:
                    with open(self.project.base_rom_path, "rb") as f:
                        self.rom_data = f.read()
                        return self.rom_data
                except Exception:
                    pass

        # Solo se permite ROM del proyecto autorizado
        pass

        return None

    def get_map_grid(self, map_id: int) -> Optional[Dict[str, Any]]:
        """Obtiene la cuadrícula de colisiones y dimensiones del mapa."""
        base_id, _ = unpack_fomt_map_id(map_id)
        if base_id in self._map_grids_cache:
            return self._map_grids_cache[base_id]

        rom = self._ensure_rom_data()
        if not rom:
            return None

        map_parser = getattr(self.project, "map_parser", None) if self.project else None
        if not map_parser:
            try:
                from Nucleos_Positronicos.Nucleo_de_Mapas.mapas import MapParser
                class _StandaloneProj:
                    def __init__(self, rdata):
                        self.virtual_rom = bytearray(rdata)
                        self.base_rom_data = rdata
                proj = self.project if self.project else _StandaloneProj(rom)
                map_parser = MapParser(proj)
                map_parser.scan_maps()
                if self.project:
                    self.project.map_parser = map_parser
            except Exception as e:
                print(f"[TilePathfinder] Error inicializando MapParser: {e}")
                return None

        header_id = get_map_header_id_for_event_map(base_id)
        if header_id is None:
            header_id = base_id

        mh = map_parser.get_map_by_id(header_id)
        if not mh:
            return None

        try:
            from Nucleos_Positronicos.Nucleo_de_Mapas.fomt_mapdata import FomtMapRenderer
            renderer = FomtMapRenderer(rom)
            renderer.load_map(mh)

            if not renderer.collision_map:
                return None

            col_bytes, dict_bytes = renderer.get_effective_collision() if hasattr(renderer, 'get_effective_collision') else (renderer.collision_map, renderer.behavior_dict)
            grid_info = {
                "base_id": base_id,
                "header_id": header_id,
                "width": renderer.width,
                "height": renderer.height,
                "pixel_w": renderer.width * 8,
                "pixel_h": renderer.height * 8,
                "collision_map": col_bytes,
                "behavior_dict": dict_bytes
            }
            self._map_grids_cache[base_id] = grid_info
            return grid_info
        except Exception as e:
            print(f"[TilePathfinder] Error cargando colisión para mapa {base_id}: {e}")
            return None

    def is_tile_walkable(self, grid: Dict[str, Any], tx: int, ty: int) -> bool:
        """Determina si un tile (8x8) es transitable por peatones."""
        w, h = grid["width"], grid["height"]
        if not (0 <= tx < w and 0 <= ty < h):
            return False

        col = grid["collision_map"]
        idx = ty * w + tx
        if idx >= len(col):
            return False

        val = col[idx]
        bdict = grid.get("behavior_dict")
        if bdict and val * 4 + 1 < len(bdict):
            behavior = struct.unpack_from('<H', bdict, val * 4)[0]
        else:
            behavior = 0

        # Bit 0 de behavior indica solidez (1 = sólido / no caminable)
        return not bool(behavior & 1)

    def snap_to_walkable(self, grid: Dict[str, Any], px: int, py: int, max_radius: int = 12) -> Tuple[int, int]:
        """Ajusta un punto en píxeles al centro del tile caminable más cercano si está en colisión."""
        w, h = grid["width"], grid["height"]
        tx = min(w - 1, max(0, px // 8))
        ty = min(h - 1, max(0, py // 8))

        if self.is_tile_walkable(grid, tx, ty):
            return tx, ty

        # Búsqueda en espiral del tile caminable más próximo
        for r in range(1, max_radius + 1):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if abs(dx) == r or abs(dy) == r:
                        nx, ny = tx + dx, ty + dy
                        if self.is_tile_walkable(grid, nx, ny):
                            return nx, ny

        return tx, ty

    def find_orthogonal_path(
        self,
        map_id: int,
        start_x: int,
        start_y: int,
        target_x: int,
        target_y: int
    ) -> List[Tuple[int, int]]:
        """
        Encuentra una ruta estrictamente ortogonal (AWSD) que sigue los caminos transitables.
        Retorna la lista completa de nodos clave en píxeles: [(x0, y0), (x1, y1), ..., (x_dest, y_dest)].
        """
        grid = self.get_map_grid(map_id)
        if not grid:
            # Fallback ortogonal Manhattan L-Shape / Z-Shape si no hay datos de colisión
            return self._fallback_manhattan_path(start_x, start_y, target_x, target_y)

        stx, sty = self.snap_to_walkable(grid, start_x, start_y)
        ttx, tty = self.snap_to_walkable(grid, target_x, target_y)

        if (stx, sty) == (ttx, tty):
            return [(start_x, start_y), (target_x, target_y)]

        # Algoritmo A* estrictamente 4-direccional (Arriba, Abajo, Izquierda, Derecha)
        open_set = []
        heapq.heappush(open_set, (0, 0, stx, sty, None))
        came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
        cost_so_far: Dict[Tuple[int, int], float] = {(stx, sty): 0.0}

        reached = False
        while open_set:
            _, cost, cx, cy, last_dir = heapq.heappop(open_set)
            if (cx, cy) == (ttx, tty):
                reached = True
                break

            # 4 direcciones estrictas (AWSD)
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = cx + dx, cy + dy
                if self.is_tile_walkable(grid, nx, ny):
                    # Penalización ligera por giro (0.08) para priorizar pasillos rectos continuos
                    turn_pen = 0.08 if (last_dir and (dx, dy) != last_dir) else 0.0
                    new_cost = cost + 1.0 + turn_pen
                    if (nx, ny) not in cost_so_far or new_cost < cost_so_far[(nx, ny)]:
                        cost_so_far[(nx, ny)] = new_cost
                        priority = new_cost + (abs(nx - ttx) + abs(ny - tty))
                        heapq.heappush(open_set, (priority, new_cost, nx, ny, (dx, dy)))
                        came_from[(nx, ny)] = (cx, cy)

        if not reached:
            # Si no hay camino continuo sin obstáculos, generar fallback Manhattan
            return self._fallback_manhattan_path(start_x, start_y, target_x, target_y)

        # Reconstruir camino de tiles
        curr = (ttx, tty)
        tile_path = []
        while curr in came_from:
            tile_path.append(curr)
            curr = came_from[curr]
        tile_path.append((stx, sty))
        tile_path.reverse()

        # Comprimir pasos colineales en nodos de giro ortogonales
        compressed_tiles = [tile_path[0]]
        for i in range(1, len(tile_path) - 1):
            p_prev = tile_path[i - 1]
            p_curr = tile_path[i]
            p_next = tile_path[i + 1]
            d1 = (p_curr[0] - p_prev[0], p_curr[1] - p_prev[1])
            d2 = (p_next[0] - p_curr[0], p_next[1] - p_curr[1])
            if d1 != d2:
                compressed_tiles.append(p_curr)
        compressed_tiles.append(tile_path[-1])

        # Convertir a píxeles exactos manteniendo estricta ortogonalidad
        pixel_nodes = [(start_x, start_y)]
        curr_px, curr_py = start_x, start_y

        for i in range(1, len(compressed_tiles)):
            t = compressed_tiles[i]
            target_px = t[0] * 8 + 4
            target_py = t[1] * 8 + 4

            if i == len(compressed_tiles) - 1:
                target_px = target_x
                target_py = target_y

            # Ajustar paso ortogonal: o bien X cambia, o bien Y cambia
            if target_px != curr_px and target_py != curr_py:
                # Si ambos difieren por el inicio/fin, añadir paso intermedio L
                pixel_nodes.append((target_px, curr_py))
                curr_px = target_px

            pixel_nodes.append((target_px, target_py))
            curr_px, curr_py = target_px, target_py

        return pixel_nodes

    def _fallback_manhattan_path(self, ax: int, ay: int, bx: int, by: int) -> List[Tuple[int, int]]:
        """Genera un trazado ortogonal en L (AWSD) garantizando cero diagonales."""
        if ax == bx or ay == by:
            return [(ax, ay), (bx, by)]
        # Movimiento en L: primero horizontal hasta bx, luego vertical hasta by
        return [(ax, ay), (bx, ay), (bx, by)]

    @staticmethod
    def nodes_to_path_steps(nodes: List[Tuple[int, int]]) -> List[Dict[str, Any]]:
        """
        Convierte una secuencia ortogonal de nodos [(x0, y0), (x1, y1), ...] en la
        estructura de pasos GBA (PathPointA / PathPointB).
        """
        steps = []
        for i in range(1, len(nodes)):
            prev_pt = nodes[i - 1]
            curr_pt = nodes[i]

            dx = curr_pt[0] - prev_pt[0]
            dy = curr_pt[1] - prev_pt[1]

            if dy != 0:
                steps.append({
                    "is_y": True,
                    "coord": curr_pt[1],
                    "dist": abs(dy),
                    "facing": 0 if dy > 0 else 1  # 0=Abajo, 1=Arriba
                })
            elif dx != 0:
                steps.append({
                    "is_y": False,
                    "coord": curr_pt[0],
                    "dist": abs(dx),
                    "facing": 3 if dx > 0 else 2  # 3=Derecha, 2=Izquierda
                })

        return steps
