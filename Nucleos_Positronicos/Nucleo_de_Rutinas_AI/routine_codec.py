# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.7.0)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
"""
routine_codec.py
══════════════════════════════════════════════════════════════════
Decodificador, Compilador y Reinyector de Rutinas NPC en ROM GBA.
Gestiona la tabla maestra en 0x3D9A4, la jerarquía de horarios,
estructuras de acciones y vectores de movimiento en ROM.
"""

import struct
from typing import Dict, List, Optional, Tuple, Any

# Dirección base de la Master Table de NPCs en FoMT (32 punteros)
MASTER_NPC_TABLE_ROM = 0x3D9A4
NPC_COUNT = 32

# Mapeo canónico de nombres de NPCs de Mineral Town por ID (0..31)
NPC_NAMES = {
    0: "Mary (Biblioteca)",
    1: "Ann (Posada)",
    2: "Popuri (Granja Avícola)",
    3: "Elli (Clínica)",
    4: "Karen (Supermercado)",
    5: "Rick (Granja Avícola)",
    6: "Cliff (Posada)",
    7: "Doctor (Clínica)",
    8: "Gray (Herrería)",
    9: "Kai (Playa)",
    10: "Goddess (Diosa)",
    11: "Won (Comerciante)",
    12: "Thomas (Alcalde)",
    13: "Harris (Policía)",
    14: "Ellen (Abuela)",
    15: "Jeff (Supermercado)",
    16: "Sasha (Supermercado)",
    17: "Lillia (Granja Avícola)",
    18: "Carter (Iglesia)",
    19: "Duke (Bodega Aja)",
    20: "Manna (Bodega Aja)",
    21: "Doug (Posada)",
    22: "Basil (Botánico)",
    23: "Anna (Casa de Basil)",
    24: "Saibara (Herrero)",
    25: "Gotz (Carpintero)",
    26: "Barley (Granja Yodel)",
    27: "May (Granja Yodel)",
    28: "Stu (Casa de Ellen)",
    29: "Van (Vendedor)",
    30: "Lou (Cocinera)",
    31: "Gourmet (Juez)",
}


class RoutineWaypoint:
    """Hito o acción individual en la línea temporal de un horario."""
    def __init__(self, time_val: int = 0, spawn_dir: int = 0, spawn_x: int = 0,
                 spawn_y: int = 0, map_id: int = 0,
                 x_vectors: Optional[List[Tuple[int, int]]] = None,
                 y_vectors: Optional[List[Tuple[int, int]]] = None,
                 action_rom_ptr: int = 0):
        self.time_val = int(time_val)  # Minutos del día o código condicional
        self.spawn_dir = int(spawn_dir)  # 0=Abajo, 1=Arriba, 2=Izq, 3=Der, 4=Frente
        self.spawn_x = int(spawn_x)      # Coordenada X en píxeles
        self.spawn_y = int(spawn_y)      # Coordenada Y en píxeles
        self.map_id = int(map_id)        # ID de mapa
        self.x_vectors = list(x_vectors) if x_vectors else []
        self.y_vectors = list(y_vectors) if y_vectors else []
        self.action_rom_ptr = int(action_rom_ptr)

    def time_to_str(self) -> str:
        hours = self.time_val // 60
        mins = self.time_val % 60
        return f"{hours:02d}:{mins:02d} ({self.time_val}m)"

    def to_dict(self) -> dict:
        return {
            "time_val": self.time_val,
            "spawn_dir": self.spawn_dir,
            "spawn_x": self.spawn_x,
            "spawn_y": self.spawn_y,
            "map_id": self.map_id,
            "x_vectors": self.x_vectors,
            "y_vectors": self.y_vectors
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'RoutineWaypoint':
        return cls(
            time_val=data.get("time_val", 0),
            spawn_dir=data.get("spawn_dir", 0),
            spawn_x=data.get("spawn_x", 0),
            spawn_y=data.get("spawn_y", 0),
            map_id=data.get("map_id", 0),
            x_vectors=[tuple(v) for v in data.get("x_vectors", [])],
            y_vectors=[tuple(v) for v in data.get("y_vectors", [])]
        )


class NPCSchedule:
    """Horario de un NPC para una condición específica (Día, Clima, etc.)."""
    def __init__(self, schedule_id: int, header_rom_ptr: int = 0):
        self.schedule_id = int(schedule_id)
        self.header_rom_ptr = int(header_rom_ptr)
        self.timeline_rom_ptr = 0
        self.waypoints: List[RoutineWaypoint] = []
        self.label = f"Horario #{schedule_id}"

    def to_dict(self) -> dict:
        return {
            "schedule_id": self.schedule_id,
            "label": self.label,
            "waypoints": [w.to_dict() for w in self.waypoints]
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'NPCSchedule':
        sched = cls(schedule_id=data.get("schedule_id", 0))
        sched.label = data.get("label", f"Horario #{sched.schedule_id}")
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
        """Decodifica un NPC específico desde la ROM."""
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

            sched = NPCSchedule(s_idx, s_ptr)
            actions_count, timeline_ptr = struct.unpack_from('<II', rom_data, s_off)
            sched.timeline_rom_ptr = timeline_ptr
            timeline_off = cls.gba_to_off(timeline_ptr)

            if timeline_off and 0 < actions_count < 200:
                for a_idx in range(actions_count):
                    t_entry_off = timeline_off + a_idx * 8
                    if t_entry_off + 8 > len(rom_data):
                        break
                    time_val, act_ptr = struct.unpack_from('<II', rom_data, t_entry_off)
                    act_off = cls.gba_to_off(act_ptr)
                    if not act_off or act_off + 16 > len(rom_data):
                        continue

                    x_vec_ptr, spawn_dir, spawn_x, spawn_y, map_id, y_vec_ptr = struct.unpack_from(
                        '<IHHHHI', rom_data, act_off
                    )

                    x_vecs = cls._read_vectors(rom_data, x_vec_ptr)
                    y_vecs = cls._read_vectors(rom_data, y_vec_ptr)

                    wp = RoutineWaypoint(
                        time_val=time_val,
                        spawn_dir=spawn_dir,
                        spawn_x=spawn_x,
                        spawn_y=spawn_y,
                        map_id=map_id,
                        x_vectors=x_vecs,
                        y_vectors=y_vecs,
                        action_rom_ptr=act_ptr
                    )
                    sched.waypoints.append(wp)

            npc_data.schedules.append(sched)

        return npc_data

    @classmethod
    def _read_vectors(cls, rom_data: bytes, vec_ptr: int) -> List[Tuple[int, int]]:
        """Lee la secuencia de pares (distancia, dirección) terminada en (0, 0)."""
        off = cls.gba_to_off(vec_ptr)
        if not off:
            return []
        vectors = []
        curr = off
        while curr + 4 <= len(rom_data):
            dist, count = struct.unpack_from('<HH', rom_data, curr)
            if dist == 0 and count == 0:
                break
            vectors.append((dist, count))
            curr += 4
            if len(vectors) > 64:  # Límite de seguridad
                break
        return vectors

    @classmethod
    def compile_npc(cls, npc_data: NPCData, base_freespace_offset: int) -> Tuple[bytes, int]:
        """
        Compila toda la jerarquía de un NPC en un solo bloque binario continuo
        re-enlazando todos los punteros relativos a base_freespace_offset.
        Retorna:
          - buffer compilado (bytes)
          - nuevo puntero GBA a la estructura maestra del NPC
        """
        # 1. Empaquetar vectores
        # 2. Empaquetar Action Structs
        # 3. Empaquetar Timelines
        # 4. Empaquetar Schedule Headers
        # 5. Empaquetar Schedules Array
        # 6. Empaquetar NPC Master Struct
        buf = bytearray()

        def append_aligned(data: bytes, align: int = 4) -> int:
            nonlocal buf
            rem = len(buf) % align
            if rem != 0:
                buf.extend(b'\x00' * (align - rem))
            off = len(buf)
            buf.extend(data)
            return off

        # Mapeo de vectores -> offset
        vec_cache: Dict[Tuple, int] = {}

        def get_or_write_vectors(vec_list: List[Tuple[int, int]]) -> int:
            if not vec_list:
                return 0
            tup = tuple(vec_list)
            if tup in vec_cache:
                return vec_cache[tup]
            raw_v = bytearray()
            for d, c in vec_list:
                raw_v.extend(struct.pack('<HH', d & 0xFFFF, c & 0xFFFF))
            raw_v.extend(struct.pack('<HH', 0, 0))  # Terminador
            v_off = append_aligned(bytes(raw_v), 4)
            vec_cache[tup] = v_off
            return v_off

        # Pre-procesar todos los waypoints para escribir vectores y action structs
        sched_header_offsets = []

        for sched in npc_data.schedules:
            if not sched or not sched.waypoints:
                sched_header_offsets.append(None)
                continue

            action_offsets = []
            for wp in sched.waypoints:
                x_v_off = get_or_write_vectors(wp.x_vectors)
                y_v_off = get_or_write_vectors(wp.y_vectors)

                x_ptr = cls.off_to_gba(base_freespace_offset + x_v_off) if x_v_off else 0
                y_ptr = cls.off_to_gba(base_freespace_offset + y_v_off) if y_v_off else 0

                act_raw = struct.pack(
                    '<IHHHHI',
                    x_ptr,
                    wp.spawn_dir & 0xFFFF,
                    wp.spawn_x & 0xFFFF,
                    wp.spawn_y & 0xFFFF,
                    wp.map_id & 0xFFFF,
                    y_ptr
                )
                a_off = append_aligned(act_raw, 4)
                action_offsets.append(a_off)

            # Escribir timeline array (time, action_ptr)
            timeline_raw = bytearray()
            for wp, a_off in zip(sched.waypoints, action_offsets):
                act_ptr = cls.off_to_gba(base_freespace_offset + a_off)
                timeline_raw.extend(struct.pack('<II', wp.time_val & 0xFFFFFFFF, act_ptr))

            tl_off = append_aligned(bytes(timeline_raw), 4)
            tl_ptr = cls.off_to_gba(base_freespace_offset + tl_off)

            # Escribir Schedule Header (count, timeline_ptr)
            header_raw = struct.pack('<II', len(sched.waypoints), tl_ptr)
            hdr_off = append_aligned(header_raw, 4)
            sched_header_offsets.append(hdr_off)

        # Escribir Schedule Pointers Array
        sched_arr_raw = bytearray()
        for hdr_off in sched_header_offsets:
            if hdr_off is not None:
                sched_arr_raw.extend(struct.pack('<I', cls.off_to_gba(base_freespace_offset + hdr_off)))
            else:
                sched_arr_raw.extend(struct.pack('<I', 0))

        sched_arr_off = append_aligned(bytes(sched_arr_raw), 4)
        sched_arr_ptr = cls.off_to_gba(base_freespace_offset + sched_arr_off)

        # Escribir NPC Master Struct (evaluator_func, sched_count, sched_arr_ptr)
        npc_master_raw = struct.pack(
            '<III',
            npc_data.evaluator_func & 0xFFFFFFFF,
            len(npc_data.schedules),
            sched_arr_ptr
        )
        master_struct_off = append_aligned(npc_master_raw, 4)
        new_master_struct_ptr = cls.off_to_gba(base_freespace_offset + master_struct_off)

        return bytes(buf), new_master_struct_ptr

    @classmethod
    def reinject_npc_to_project(cls, project, npc_id: int, npc_data: NPCData,
                                force_repoint: bool = True) -> Tuple[bool, str]:
        """
        Inyecta o repuntea la rutina de un NPC dentro del proyecto activo de FoMT Studio.
        Escribe en la memoria virtual y actualiza el puntero de la Master Table.
        """
        if not project or not project.base_rom_data:
            return False, "No hay una ROM cargada en el proyecto activo."

        try:
            # Reservar espacio libre usando next_free_space del proyecto o gestor_memoria
            target_free_off = getattr(project, "next_free_space", 0x75C254)
            target_free_off = (target_free_off + 3) & ~3  # Alinear a 4

            compiled_blob, new_struct_ptr = cls.compile_npc(npc_data, target_free_off)
            blob_len = len(compiled_blob)

            # Escribir parche de datos en la ROM virtual
            project.write_patch(target_free_off, compiled_blob)

            # Actualizar Master Table en 0x3D9A4 + npc_id * 4
            master_entry_off = MASTER_NPC_TABLE_ROM + npc_id * 4
            ptr_bytes = struct.pack('<I', new_struct_ptr)
            project.write_patch(master_entry_off, ptr_bytes)

            # Avanzar el puntero de espacio libre del proyecto
            project.next_free_space = (target_free_off + blob_len + 15) & ~3

            # Guardar cambios en el proyecto
            if hasattr(project, "save"):
                project.save()

            msg = (
                f"✅ Rutina de {npc_data.name} inyectada con éxito!\n"
                f"• Bloque: 0x{target_free_off:06X} - 0x{target_free_off + blob_len:06X} ({blob_len} bytes)\n"
                f"• Puntero Maestro: 0x{master_entry_off:06X} -> 0x{new_struct_ptr:08X}\n"
                f"• Horarios configurados: {len([s for s in npc_data.schedules if s])}"
            )
            return True, msg
        except Exception as e:
            return False, f"Excepción durante la inyección de la rutina: {str(e)}"
