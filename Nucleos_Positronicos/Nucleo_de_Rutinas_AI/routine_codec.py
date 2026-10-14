# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.8.0)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
"""
routine_codec.py
══════════════════════════════════════════════════════════════════
Decodificador, Compilador y Reinyector de Rutinas NPC en ROM GBA.
Gestiona la tabla maestra en 0x3D9A4, la jerarquía de horarios,
estructuras de acciones PathInfo, PathPointA/B y secuencias de
movimiento ortogonal AWSD.
"""

import struct
from typing import Dict, List, Optional, Tuple, Any

from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.fomt_map_names import (
    get_map_display_name, unpack_fomt_map_id
)
from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.npc_schedule_conditions import (
    get_schedule_condition_info
)

# Dirección base de la Master Table de NPCs en FoMT (32 punteros)
MASTER_NPC_TABLE_ROM = 0x3D9A4
NPC_COUNT = 32

# Mapeo canónico de nombres de NPCs de Mineral Town por ID (0..31)
NPC_NAMES = {
    0: "Lillia (Granja Avícola)",
    1: "Rick (Granja Avícola)",
    2: "Popuri (Granja Avícola)",
    3: "Harris (Policía)",
    4: "Barley (Granja Yodel)",
    5: "Saibara (Herrero)",
    6: "Gray (Aprendiz de Herrero)",
    7: "Duke (Bodega Aja)",
    8: "Manna (Bodega Aja)",
    9: "Basil (Botánico)",
    10: "Anna (Esposa de Basil)",
    11: "Mary (Biblioteca)",
    12: "Thomas (Alcalde)",
    13: "Kano (Fotógrafo)",
    14: "Ellen (Abuela)",
    15: "Stu (Nieto de Ellen)",
    16: "Jeff (Supermercado)",
    17: "Sasha (Supermercado)",
    18: "Karen (Supermercado)",
    19: "Doctor (Clínica)",
    20: "Elli (Enfermera de la Clínica)",
    21: "Carter (Pastor de la Iglesia)",
    22: "Cliff (Posada / Bodega)",
    23: "Doug (Posadero)",
    24: "Ann (Posada de Doug)",
    25: "Kai (Chiringuito de Playa)",
    26: "Gotz (Carpintero)",
    27: "Zack (Comprador de la Playa)",
    28: "Won (Vendedor Ambulante)",
    29: "Van (Comerciante Viajero)",
    30: "Lou (Cocinera Viajera)",
    31: "Gourmet / Diosa (Eventos Especiales)",
}


class RoutineWaypoint:
    """Hito o acción individual en la línea temporal de un horario."""

    def __init__(self, time_val: int = 0, spawn_dir: int = 0, spawn_x: int = 0,
                 spawn_y: int = 0, dest_x: Optional[int] = None, dest_y: Optional[int] = None,
                 map_id: int = 0, point_type_select: int = 0,
                 path_nodes: Optional[List[Tuple[int, int]]] = None,
                 raw_points: Optional[List[dict]] = None,
                 x_vectors: Optional[List[Tuple[int, int]]] = None,
                 y_vectors: Optional[List[Tuple[int, int]]] = None,
                 action_rom_ptr: int = 0,
                 raw_bytes: Optional[bytes] = None):
        self.time_val = int(time_val)  # Minutos del día desde las 06:00
        self.spawn_dir = int(spawn_dir)  # facing_start: 0=Abajo, 1=Arriba, 2=Izq, 3=Der
        self.spawn_x = int(spawn_x)      # Coordenada X inicial en píxeles
        self.spawn_y = int(spawn_y)      # Coordenada Y inicial en píxeles
        self.dest_x = int(dest_x) if dest_x is not None else int(spawn_x)
        self.dest_y = int(dest_y) if dest_y is not None else int(spawn_y)
        self.map_id = int(map_id) & 0x3FF  # ID de mapa canónico (10 bits)
        self.point_type_select = int(point_type_select) & 1

        # Nodos ortogonales de giro AWSD: [(x0, y0), (x1, y1), ...]
        if path_nodes:
            self.path_nodes = list(path_nodes)
        else:
            self.path_nodes = [(self.spawn_x, self.spawn_y)]
            if (self.dest_x, self.dest_y) != (self.spawn_x, self.spawn_y):
                self.path_nodes.append((self.dest_x, self.dest_y))

        self.raw_points = list(raw_points) if raw_points else []
        self._x_vectors = list(x_vectors) if x_vectors else None
        self._y_vectors = list(y_vectors) if y_vectors else None
        self.action_rom_ptr = int(action_rom_ptr)
        self.raw_bytes = bytes(raw_bytes) if raw_bytes else None
        self.is_edited = False

    @property
    def map_name(self) -> str:
        return get_map_display_name(self.map_id)

    @property
    def x_vectors(self) -> List[Tuple[int, int]]:
        """Devuelve pares (dist, dir) derivados de los nodos ortogonales AWSD."""
        if self._x_vectors is not None:
            return self._x_vectors
        vecs = []
        for i in range(1, len(self.path_nodes)):
            px, py = self.path_nodes[i - 1]
            cx, cy = self.path_nodes[i]
            dx, dy = cx - px, cy - py
            if dy > 0:
                vecs.append((dy, 0))  # 0=Abajo
            elif dy < 0:
                vecs.append((abs(dy), 1))  # 1=Arriba
            elif dx < 0:
                vecs.append((abs(dx), 2))  # 2=Izquierda
            elif dx > 0:
                vecs.append((dx, 3))  # 3=Derecha
        if not vecs or vecs[-1] != (0, 0):
            vecs.append((0, 0))
        return vecs

    @x_vectors.setter
    def x_vectors(self, val: List[Tuple[int, int]]):
        self._x_vectors = val

    @property
    def y_vectors(self) -> List[Tuple[int, int]]:
        return self._y_vectors if self._y_vectors is not None else []

    @y_vectors.setter
    def y_vectors(self, val: List[Tuple[int, int]]):
        self._y_vectors = val

    def time_to_str(self) -> str:
        total_m = (6 * 60 + self.time_val) % 1440
        hours = total_m // 60
        mins = total_m % 60
        return f"{hours:02d}:{mins:02d} (+{self.time_val}m)"

    def to_dict(self) -> dict:
        return {
            "time_val": self.time_val,
            "spawn_dir": self.spawn_dir,
            "spawn_x": self.spawn_x,
            "spawn_y": self.spawn_y,
            "dest_x": self.dest_x,
            "dest_y": self.dest_y,
            "map_id": self.map_id,
            "map_name": self.map_name,
            "point_type_select": self.point_type_select,
            "path_nodes": self.path_nodes,
            "raw_points": self.raw_points
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'RoutineWaypoint':
        p_nodes = [tuple(p) for p in data.get("path_nodes", [])] if data.get("path_nodes") else None
        return cls(
            time_val=data.get("time_val", 0),
            spawn_dir=data.get("spawn_dir", 0),
            spawn_x=data.get("spawn_x", 0),
            spawn_y=data.get("spawn_y", 0),
            dest_x=data.get("dest_x"),
            dest_y=data.get("dest_y"),
            map_id=data.get("map_id", 0),
            point_type_select=data.get("point_type_select", 0),
            path_nodes=p_nodes,
            raw_points=data.get("raw_points", []),
            x_vectors=[tuple(v) for v in data.get("x_vectors", [])] if "x_vectors" in data else None
        )


class NPCSchedule:
    """Horario de un NPC para una condición específica (Día, Clima, etc.)."""
    def __init__(self, schedule_id: int, header_rom_ptr: int = 0, npc_id: int = 0):
        self.schedule_id = int(schedule_id)
        self.npc_id = int(npc_id)
        self.header_rom_ptr = int(header_rom_ptr)
        self.timeline_rom_ptr = 0
        self.waypoints: List[RoutineWaypoint] = []
        self.label = f"Horario #{schedule_id}"
        self.condition_info: Dict[str, Any] = {}

    def update_condition_info(self):
        self.condition_info = get_schedule_condition_info(self.npc_id, self.schedule_id, self.waypoints)
        self.label = f"Horario #{self.schedule_id}: {self.condition_info.get('short', '')}"

    def to_dict(self) -> dict:
        return {
            "schedule_id": self.schedule_id,
            "label": self.label,
            "condition": self.condition_info,
            "waypoints": [w.to_dict() for w in self.waypoints]
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'NPCSchedule':
        sched = cls(schedule_id=data.get("schedule_id", 0))
        sched.label = data.get("label", f"Horario #{sched.schedule_id}")
        sched.condition_info = data.get("condition", {})
        for w_data in data.get("waypoints", []):
            sched.waypoints.append(RoutineWaypoint.from_dict(w_data))
        return sched


class NPCData:
    """Estructura completa de rutinas de un NPC."""
    def __init__(self, npc_id: int, name: str = "", evaluator_func: int = 0):
        self.npc_id = int(npc_id)
        self.name = name or NPC_NAMES.get(npc_id, f"NPC_{npc_id}")
        self.evaluator_func = int(evaluator_func)
        self.struct_rom_ptr = 0
        self.schedules_array_ptr = 0
        self.schedules: List[Optional[NPCSchedule]] = []

    def to_dict(self) -> dict:
        return {
            "npc_id": self.npc_id,
            "name": self.name,
            "evaluator_func": f"0x{self.evaluator_func:08X}",
            "schedules": [s.to_dict() if s else None for s in self.schedules]
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'NPCData':
        eval_str = data.get("evaluator_func", "0")
        eval_fn = int(eval_str, 16) if '0x' in str(eval_str).lower() else int(eval_str)
        npc = cls(npc_id=data.get("npc_id", 0), name=data.get("name", ""), evaluator_func=eval_fn)
        for s_data in data.get("schedules", []):
            if s_data:
                npc.schedules.append(NPCSchedule.from_dict(s_data))
            else:
                npc.schedules.append(None)
        return npc


class RoutineCodec:
    """Motor de decodificación y re-inyección en ROM para rutinas de NPCs."""

    @staticmethod
    def gba_to_off(ptr: int) -> Optional[int]:
        if 0x08000000 <= ptr < 0x0A000000:
            return ptr & 0x01FFFFFF
        return None

    @staticmethod
    def off_to_gba(offset: int) -> int:
        return (offset & 0x01FFFFFF) | 0x08000000

    @classmethod
    def decode_all(cls, rom_data: bytes) -> Dict[int, NPCData]:
        """Decodifica los 32 NPCs desde el binario de la ROM."""
        result = {}
        for npc_id in range(NPC_COUNT):
            npc_obj = cls.decode_single_npc(rom_data, npc_id)
            if npc_obj:
                result[npc_id] = npc_obj
        return result

    @classmethod
    def decode_single_npc(cls, rom_data: bytes, npc_id: int) -> Optional[NPCData]:
        """Decodifica un NPC específico desde la ROM respetando la estructura canónica."""
        if not rom_data or len(rom_data) < MASTER_NPC_TABLE_ROM + (npc_id + 1) * 4:
            return None

        # Puntero en Master Table
        ptr_loc = MASTER_NPC_TABLE_ROM + npc_id * 4
        npc_ptr = struct.unpack_from('<I', rom_data, ptr_loc)[0]
        npc_off = cls.gba_to_off(npc_ptr)
        if not npc_off or npc_off + 12 > len(rom_data):
            return None

        eval_fn, sched_count, sched_arr_ptr = struct.unpack_from('<III', rom_data, npc_off)
        npc_name = NPC_NAMES.get(npc_id, f"NPC_{npc_id}")
        npc_data = NPCData(npc_id, npc_name, eval_fn)
        npc_data.struct_rom_ptr = npc_ptr
        npc_data.schedules_array_ptr = sched_arr_ptr

        sched_arr_off = cls.gba_to_off(sched_arr_ptr)
        if not sched_arr_off:
            return npc_data

        for s_idx in range(sched_count):
            if sched_arr_off + (s_idx + 1) * 4 > len(rom_data):
                npc_data.schedules.append(None)
                continue

            s_ptr = struct.unpack_from('<I', rom_data, sched_arr_off + s_idx * 4)[0]
            s_off = cls.gba_to_off(s_ptr)
            if not s_off or s_off + 8 > len(rom_data):
                npc_data.schedules.append(None)
                continue

            sched = NPCSchedule(s_idx, s_ptr, npc_id)
            # Schedule struct: u16 num_time_entries, u16 padding, ScheduleEntry *time_entries
            num_entries = struct.unpack_from('<H', rom_data, s_off)[0]
            entries_ptr = struct.unpack_from('<I', rom_data, s_off + 4)[0]
            sched.timeline_rom_ptr = entries_ptr
            entries_off = cls.gba_to_off(entries_ptr)

            if entries_off and 0 < num_entries < 256:
                for e_idx in range(num_entries):
                    t_entry_off = entries_off + e_idx * 8
                    if t_entry_off + 8 > len(rom_data):
                        break
                    # ScheduleEntry struct: u16 time, u16 padding, PathInfo *path
                    time_val = struct.unpack_from('<H', rom_data, t_entry_off)[0]
                    path_ptr = struct.unpack_from('<I', rom_data, t_entry_off + 4)[0]
                    path_off = cls.gba_to_off(path_ptr)
                    if not path_off or path_off + 12 > len(rom_data):
                        continue

                    # PathInfo struct (12 bytes):
                    # points_ptr (u32), num_points (u16), x_start (i16), y_start (i16), half_0A (u16)
                    points_ptr, num_pts, x_start, y_start, half_0A = struct.unpack_from(
                        '<IHhhH', rom_data, path_off
                    )
                    location_start = half_0A & 0x3FF
                    facing_start = (half_0A >> 10) & 3
                    pt_type = (half_0A >> 12) & 1

                    pts_off = cls.gba_to_off(points_ptr)
                    curr_x, curr_y = x_start, y_start
                    path_nodes = [(curr_x, curr_y)]
                    raw_pts = []
                    raw_bytes = None

                    if pts_off and 0 < num_pts < 256 and pts_off + num_pts * 8 <= len(rom_data):
                        raw_bytes = rom_data[pts_off : pts_off + num_pts * 8]
                        for p in range(num_pts):
                            pt_addr = pts_off + p * 8
                            if pt_type == 0:
                                # PathPointA: u16 instant, i16 coord, u32 hi (hi & 1 is is_y)
                                instant, coord, hi = struct.unpack_from('<HhI', rom_data, pt_addr)
                                is_y = bool(hi & 1)
                                raw_pts.append({
                                    "instant": instant,
                                    "coord": coord,
                                    "is_y": is_y,
                                    "hi": hi
                                })
                            else:
                                # PathPointB: u16 coord, u16 speed, u16 delay, u16 flags
                                coord, speed, delay, flags = struct.unpack_from('<4H', rom_data, pt_addr)
                                is_y = bool(flags & 4)
                                facing_pt = flags & 3
                                raw_pts.append({
                                    "coord": coord,
                                    "speed": speed,
                                    "delay": delay,
                                    "is_y": is_y,
                                    "facing": facing_pt,
                                    "flags": flags
                                })

                            if is_y:
                                curr_y = coord
                            else:
                                curr_x = coord
                            path_nodes.append((curr_x, curr_y))

                    wp = RoutineWaypoint(
                        time_val=time_val,
                        spawn_dir=facing_start,
                        spawn_x=x_start,
                        spawn_y=y_start,
                        dest_x=curr_x,
                        dest_y=curr_y,
                        map_id=location_start,
                        point_type_select=pt_type,
                        path_nodes=path_nodes,
                        raw_points=raw_pts,
                        action_rom_ptr=path_ptr,
                        raw_bytes=raw_bytes
                    )
                    sched.waypoints.append(wp)

            sched.update_condition_info()
            npc_data.schedules.append(sched)

        return npc_data

    @classmethod
    def compile_npc(cls, npc_data: NPCData, base_freespace_offset: int) -> Tuple[bytes, int]:
        """
        Compila la jerarquía completa de un NPC siguiendo la especificación nativa GBA:
        Offset 0: NPC Master Struct (evaluator_func, sched_count, sched_arr_ptr)
        Offset 12: Schedule Pointers Array (sched_ptr_0, sched_ptr_1...)
        Seguido de: Schedule Headers, Timeline Arrays, PathInfo structs y PathPoints.
        Retorna:
          - buffer compilado (bytes)
          - nuevo puntero GBA a la estructura maestra del NPC (base_freespace_offset + 0)
        """
        buf = bytearray()

        def append_aligned(data: bytes, align: int = 4) -> int:
            nonlocal buf
            rem = len(buf) % align
            if rem != 0:
                buf.extend(b'\x00' * (align - rem))
            off = len(buf)
            buf.extend(data)
            return off

        # 1. Reservar espacio al frente para el Master Struct (12 bytes)
        master_struct_off = append_aligned(b'\x00' * 12, 4)

        # 2. Reservar espacio inmediatamente después para el Schedule Pointers Array
        sched_count = len(npc_data.schedules)
        sched_arr_off = append_aligned(b'\x00' * (sched_count * 4), 4)

        # Caché de deduplicación de PathInfo y PathPoints
        path_cache: Dict[Tuple, int] = {}
        sched_header_offsets = []

        for sched in npc_data.schedules:
            if not sched or not sched.waypoints:
                sched_header_offsets.append(None)
                continue

            entry_path_offsets = []
            for wp in sched.waypoints:
                pts_tuple = tuple(wp.path_nodes) if wp.path_nodes else ()
                cache_key = (wp.map_id, wp.spawn_dir, wp.spawn_x, wp.spawn_y, wp.point_type_select, pts_tuple)

                if cache_key in path_cache:
                    entry_path_offsets.append(path_cache[cache_key])
                    continue

                # Compilar puntos si hay movimiento
                points_blob = bytearray()
                num_points = 0
                if wp.raw_bytes and not getattr(wp, 'is_edited', False):
                    points_blob.extend(wp.raw_bytes)
                    num_points = len(wp.raw_bytes) // 8
                elif wp.path_nodes and len(wp.path_nodes) > 1:
                    num_points = len(wp.path_nodes) - 1
                    curr_instant = 0
                    for step_idx in range(1, len(wp.path_nodes)):
                        p_prev = wp.path_nodes[step_idx - 1]
                        p_curr = wp.path_nodes[step_idx]
                        dy = p_curr[1] - p_prev[1]
                        dx = p_curr[0] - p_prev[0]
                        seg_dist = abs(dy) if dy != 0 else abs(dx)
                        step_ticks = max(1, int(round(seg_dist / 24.0)))
                        curr_instant += step_ticks

                        if wp.point_type_select == 0:
                            # PathPointA: u16 instant, i16 coord, u32 hi (hi & 1 is is_y)
                            if dy != 0:
                                coord = p_curr[1]
                                hi = 1
                            else:
                                coord = p_curr[0]
                                hi = 0
                            points_blob.extend(struct.pack('<HhI', curr_instant & 0xFFFF, coord, hi))
                        else:
                            # PathPointB (type 1): u16 coord, u16 speed, u16 delay, u16 flags
                            # Flags: bit 2 (0x04) = is_y; bits 0-1 = facing (0=Abajo, 1=Arriba, 2=Izquierda, 3=Derecha)
                            if dy != 0:
                                coord = p_curr[1]
                                flags = 4 if dy > 0 else 5  # 4 = Abajo, 5 = Arriba
                            else:
                                coord = p_curr[0]
                                flags = 3 if dx > 0 else 2  # 3 = Derecha, 2 = Izquierda
                            points_blob.extend(struct.pack('<4H', coord & 0xFFFF, 2, 120, flags))

                pts_off = append_aligned(bytes(points_blob), 4) if points_blob else 0
                pts_ptr = cls.off_to_gba(base_freespace_offset + pts_off) if pts_off else 0

                half_0A = (wp.map_id & 0x3FF) | ((wp.spawn_dir & 3) << 10) | ((wp.point_type_select & 1) << 12)
                path_raw = struct.pack(
                    '<IHhhH',
                    pts_ptr,
                    num_points & 0xFFFF,
                    wp.spawn_x,
                    wp.spawn_y,
                    half_0A & 0xFFFF
                )
                p_off = append_aligned(path_raw, 4)
                path_cache[cache_key] = p_off
                entry_path_offsets.append(p_off)

            # Escribir ScheduleEntry array
            entries_blob = bytearray()
            for wp, p_off in zip(sched.waypoints, entry_path_offsets):
                path_ptr = cls.off_to_gba(base_freespace_offset + p_off)
                entries_blob.extend(struct.pack('<H2xI', wp.time_val & 0xFFFF, path_ptr))

            entries_off = append_aligned(bytes(entries_blob), 4)
            entries_ptr = cls.off_to_gba(base_freespace_offset + entries_off)

            # Escribir Schedule header
            sched_hdr_raw = struct.pack('<H2xI', len(sched.waypoints) & 0xFFFF, entries_ptr)
            hdr_off = append_aligned(sched_hdr_raw, 4)
            sched_header_offsets.append(hdr_off)

        # Rellenar Schedule Pointers Array
        for s_idx, hdr_off in enumerate(sched_header_offsets):
            s_ptr = cls.off_to_gba(base_freespace_offset + hdr_off) if hdr_off is not None else 0
            struct.pack_into('<I', buf, sched_arr_off + s_idx * 4, s_ptr)

        # Rellenar NPC Master Struct en el offset 0
        sched_arr_ptr = cls.off_to_gba(base_freespace_offset + sched_arr_off)
        struct.pack_into(
            '<III',
            buf,
            0,
            npc_data.evaluator_func & 0xFFFFFFFF,
            sched_count,
            sched_arr_ptr
        )

        new_master_struct_ptr = cls.off_to_gba(base_freespace_offset)
        return bytes(buf), new_master_struct_ptr

    @classmethod
    def get_npc_original_span(cls, rom_data: bytes, npc_id: int) -> Tuple[Optional[int], int]:
        """Calcula el offset inicial y el tamaño en bytes que ocupa la rutina actual del NPC en la ROM."""
        if not rom_data or len(rom_data) < MASTER_NPC_TABLE_ROM + (npc_id + 1) * 4:
            return None, 0

        p_master = struct.unpack_from('<I', rom_data, MASTER_NPC_TABLE_ROM + npc_id * 4)[0]
        off_m = cls.gba_to_off(p_master)
        if not off_m or off_m + 12 > len(rom_data):
            return None, 0

        offsets = [(off_m, 12)]
        eval_fn, num_sched, sched_arr_ptr = struct.unpack_from('<III', rom_data, off_m)
        s_arr_off = cls.gba_to_off(sched_arr_ptr)
        if s_arr_off and s_arr_off + num_sched * 4 <= len(rom_data):
            offsets.append((s_arr_off, num_sched * 4))
            for s_idx in range(num_sched):
                s_ptr = struct.unpack_from('<I', rom_data, s_arr_off + s_idx * 4)[0]
                s_off = cls.gba_to_off(s_ptr)
                if not s_off or s_off + 8 > len(rom_data):
                    continue
                offsets.append((s_off, 8))
                num_entries = struct.unpack_from('<H', rom_data, s_off)[0]
                ent_ptr = struct.unpack_from('<I', rom_data, s_off + 4)[0]
                ent_off = cls.gba_to_off(ent_ptr)
                if not ent_off or ent_off + num_entries * 8 > len(rom_data):
                    continue
                offsets.append((ent_off, num_entries * 8))
                for e_idx in range(num_entries):
                    p_ptr = struct.unpack_from('<I', rom_data, ent_off + e_idx * 8 + 4)[0]
                    p_off = cls.gba_to_off(p_ptr)
                    if not p_off or p_off + 12 > len(rom_data):
                        continue
                    offsets.append((p_off, 12))
                    pts_ptr, num_pts, xs, ys, h0a = struct.unpack_from('<IHhhH', rom_data, p_off)
                    pts_off = cls.gba_to_off(pts_ptr)
                    if pts_off and num_pts > 0 and pts_off + num_pts * 8 <= len(rom_data):
                        offsets.append((pts_off, num_pts * 8))

        min_o = min(o for o, sz in offsets)
        max_o = max(o + sz for o, sz in offsets)
        span = (max_o - min_o + 3) & ~3
        return min_o, span

    @classmethod
    def find_first_aligned_freespace(cls, rom_data: bytes, req_len: int, align: int = 4, start_search: int = 0x700000) -> int:
        """Encuentra el primer agujero continuo de bytes 0xFF con alineación dada."""
        curr = (start_search + align - 1) & ~(align - 1)
        chunk_len = min(req_len, 64)
        target_match = b'\xFF' * chunk_len
        r_len = len(rom_data)

        while curr + req_len <= r_len:
            idx = rom_data.find(target_match, curr)
            if idx == -1:
                break
            cand = (idx + align - 1) & ~(align - 1)
            if cand + req_len <= r_len and rom_data[cand : cand + req_len] == b'\xFF' * req_len:
                return cand
            curr = cand + align

        return (r_len + align - 1) & ~(align - 1)

    @classmethod
    def reinject_npc_to_project(cls, project, npc_id: int, npc_data: NPCData,
                                force_repoint: bool = False) -> Tuple[bool, str]:
        """
        Inyecta la rutina de un NPC verificando si cabe en su espacio original o
        repunteando al primer agujero de 0xFF disponible y alineado a 4 bytes.
        Si se repuntea, actualiza todas las referencias de la ROM (tabla maestra y literal pool de entity_manager)
        y preserva un stub de seguridad en el bloque viejo para prevenir saltos a FFFFFFFE.
        """
        if not project:
            return False, "No hay proyecto activo."

        rom_bytes = None
        if getattr(project, "virtual_rom", None):
            rom_bytes = bytes(project.virtual_rom)
        elif getattr(project, "base_rom_data", None):
            rom_bytes = project.base_rom_data

        if not rom_bytes:
            return False, "No hay una ROM cargada en el proyecto activo."

        try:
            # 1. Medir espacio original del NPC
            orig_off, orig_span = cls.get_npc_original_span(rom_bytes, npc_id)

            # 2. Medir tamaño requerido por la nueva rutina
            test_blob, _ = cls.compile_npc(npc_data, 0)
            required_len = len(test_blob)

            in_place = False
            target_off = None

            # 3. Decidir si cabe en su espacio original o requiere repunteo
            if orig_off is not None and required_len <= orig_span and not force_repoint:
                in_place = True
                target_off = orig_off
            else:
                target_off = cls.find_first_aligned_freespace(rom_bytes, required_len, align=4, start_search=0x700000)

            # 4. Compilar con el offset definitivo (Master Struct queda en target_off + 0)
            compiled_blob, new_struct_ptr = cls.compile_npc(npc_data, target_off)
            blob_len = len(compiled_blob)

            # 5. Escribir rutina
            project.write_patch(target_off, compiled_blob)

            # 6. Si cupo in-place y sobró espacio, rellenar el remanente original con 0xFF
            if in_place and blob_len < orig_span:
                rem_len = orig_span - blob_len
                project.write_patch(target_off + blob_len, b'\xFF' * rem_len)

            # 7. Si se repunteó a un bloque nuevo:
            if not in_place and orig_off is not None and orig_off != target_off:
                # Stub de seguridad en los primeros 12 bytes del offset viejo
                # para que jamás se desreferencie 0xFFFFFFFF
                safe_stub = struct.pack(
                    '<III',
                    npc_data.evaluator_func & 0xFFFFFFFF,
                    len(npc_data.schedules),
                    cls.off_to_gba(target_off + 12)
                )
                project.write_patch(orig_off, safe_stub)
                if orig_span > 12:
                    project.write_patch(orig_off + 12, b'\xFF' * (orig_span - 12))

            # 8. Repuntear TODAS las referencias de la ROM a la estructura maestra de este NPC
            # (Incluye 0x3D9A4 + npc_id*4 y el literal pool de entity_manager.c en 0x35xxx)
            old_ptr = cls.off_to_gba(orig_off) if orig_off is not None else None
            old_ptr_bytes = struct.pack('<I', old_ptr) if old_ptr is not None else None
            new_ptr_bytes = struct.pack('<I', new_struct_ptr)

            patched_count = 0
            if old_ptr_bytes:
                pos = 0
                while True:
                    idx = rom_bytes.find(old_ptr_bytes, pos)
                    if idx == -1:
                        break
                    project.write_patch(idx, new_ptr_bytes)
                    patched_count += 1
                    pos = idx + 4

            # Asegurar la entrada en MASTER_NPC_TABLE_ROM
            master_entry_off = MASTER_NPC_TABLE_ROM + npc_id * 4
            project.write_patch(master_entry_off, new_ptr_bytes)

            # 9. Actualizar puntero de freespace del proyecto si se usó freespace
            if not in_place:
                project.next_free_space = (target_off + blob_len + 15) & ~3

            # 10. Persistir cambios
            if hasattr(project, "save"):
                project.save()

            if in_place:
                msg = (
                    f"✅ Rutina de {npc_data.name} inyectada IN-PLACE (sin repunteo)!\n"
                    f"• Ubicación: 0x{target_off:06X} - 0x{target_off + blob_len:06X} ({blob_len} de {orig_span} bytes usados)\n"
                    f"• Remanente ({orig_span - blob_len} bytes) rellenado con 0xFF\n"
                    f"• Puntero Maestro: 0x{master_entry_off:06X} -> 0x{new_struct_ptr:08X}"
                )
            else:
                msg = (
                    f"✅ Rutina de {npc_data.name} REPUNTEADA exitosamente!\n"
                    f"• Nuevo Bloque libre (0xFF): 0x{target_off:06X} - 0x{target_off + blob_len:06X} ({blob_len} bytes)\n"
                    f"• Punteros actualizados en ROM ({patched_count} referencias repunteadas): -> 0x{new_struct_ptr:08X}\n"
                    f"• Stub de seguridad en 0x{orig_off:06X} (eval_fn preservada) y resto ({orig_span - 12} bytes) liberado con 0xFF."
                )

            return True, msg
        except Exception as e:
            return False, f"Excepción durante la inyección de la rutina: {str(e)}"

