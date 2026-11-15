# ============================================================
# FOMT Studio - Suite de Ingenieria Inversa
# MemoryExtendEngine - Motor de Expansion de Flags y Memoria In-Slot
# ============================================================
"""
memory_extend_engine.py
------------------------------------------------------------
Modulo de expansion incremental y milimetrica de flags y variables de
memoria para Harvest Moon: Friends of Mineral Town (GBA USA).
Relocaliza las tablas de despacho GET (0x045934) y SET (0x049034),
compila handlers Thumb dedicados y mapea memoria in-slot segura
cubierta por el checksum nativo u32[0x3520].
"""

import os
import csv
import glob
import struct
from dataclasses import dataclass
from typing import List, Dict, Tuple, Set, Optional, Any, Union

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QComboBox, QSpinBox, QCheckBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QSplitter, QWidget, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

from Consola_de_Comando.i18n import tr
from Banco_de_Datos.Utilidades.rutas import get_data_path


@dataclass
class CustomFlagSpec:
    """Definicion de flag o variable de memoria expandida."""
    name: str
    mode: str           # "bit" (0..1), "u8" (0..255), "u16" (0..65535), "u32" (0..0xFFFFFFFF)
    ctx_offset: int     # Offset relativo a [ctx + 0x350]
    bit_index: int = 0  # Solo usado si mode == "bit" (0..7)

    @property
    def width_bytes(self) -> int:
        return {"bit": 0, "u8": 1, "u16": 2, "u32": 4}.get(self.mode, 1)

    @property
    def alignment(self) -> int:
        return {"bit": 1, "u8": 1, "u16": 2, "u32": 4}.get(self.mode, 1)

    @property
    def type_value(self) -> str:
        return "binary" if self.mode == "bit" else "state"


class FreeSpaceFinder:
    """Buscador de espacio libre alineado a 4 bytes en ROM GBA."""

    @staticmethod
    def find_block(
        rom: Union[bytes, bytearray],
        required_bytes: int,
        start_offset: int = 0x75B000,
        alignment: int = 4,
        safety_pad: int = 0x40,
        free_byte: int = 0xFF
    ) -> int:
        total_needed = required_bytes + (safety_pad * 2)
        target_pattern = bytes([free_byte]) * total_needed

        pos = (start_offset + alignment - 1) & ~(alignment - 1)
        rom_len = len(rom)
        while pos + total_needed <= rom_len:
            idx = rom.find(target_pattern, pos)
            if idx == -1:
                break
            usable_start = (idx + safety_pad + alignment - 1) & ~(alignment - 1)
            if usable_start + required_bytes + safety_pad <= rom_len:
                end_check = usable_start + required_bytes + safety_pad
                if all(b == free_byte for b in rom[idx:end_check]):
                    return usable_start
            pos = idx + alignment

        raise RuntimeError(
            f"FreeSpaceFinder: No se encontro un bloque contiguo de {required_bytes} bytes "
            f"(+0x{safety_pad*2:X} pad) de 0x{free_byte:02X} a partir de 0x08{start_offset:06X}."
        )


class MemoryExtendEngine:
    """
    Motor central de expansion de memoria y flags para FoMT.
    Soporta inyeccion en caliente sobre proyectos activos (virtual_rom)
    o archivos .gba en disco.
    """

    GET_LIMIT_OFF  = 0x04592C
    GET_PTR_OFF    = 0x045930
    GET_TABLE_ORIG = 0x08045934
    GET_COUNT_ORIG = 590  # IDs 0x000..0x24D

    SET_LIMIT_OFF  = 0x04902C
    SET_PTR_OFF    = 0x049030
    SET_TABLE_ORIG = 0x08049034
    SET_COUNT_ORIG = 562  # IDs 0x01C..0x24D

    GET_EPILOGUE = 0x08048FEF  # Thumb bit = 1
    SET_EPILOGUE = 0x0804DA2D  # Thumb bit = 1

    # Pool seguro in-slot cubierto por checksum nativo u32[0x3520]
    IN_SLOT_BYTES_RANGE = range(0x34AC, 0x34C4)  # 24 bytes contiguos limpios (0x34AC..0x34C3)
    IN_SLOT_BITS_POOL = [
        (0x215F, 7), (0x2163, 7), (0x2167, 7), (0x216B, 7),
        (0x216E, 7), (0x217B, 7), (0x2183, 7), (0x2187, 7),
        (0x219B, 7), (0x21A0, 7), (0x21A3, 7), (0x21A7, 7),
        (0x21C3, 7), (0x21B7, 6), (0x21B7, 7), (0x21BB, 6),
        (0x21BB, 7), (0x21BF, 6), (0x21BF, 7),
    ]

    def __init__(self, target: Any = None):
        self.project = None
        self.rom_path = None
        self.rom: Optional[bytearray] = None
        self.set_target(target)

    def set_target(self, target: Any):
        if target is None:
            self.project = None
            self.rom_path = None
            self.rom = None
            return

        if hasattr(target, 'virtual_rom'):
            self.project = target
            self.rom_path = getattr(target, 'base_rom_path', None)
            self.rom = target.virtual_rom
        elif isinstance(target, (bytes, bytearray)):
            self.project = None
            self.rom_path = None
            self.rom = bytearray(target)
        elif isinstance(target, str) and os.path.isfile(target):
            self.project = None
            self.rom_path = target
            self.rom = bytearray(open(target, "rb").read())
        else:
            raise ValueError(f"Target no valido para MemoryExtendEngine: {type(target)}")

    def get_rom_bytes(self) -> bytearray:
        if self.project is not None and hasattr(self.project, 'virtual_rom'):
            return self.project.virtual_rom
        if self.rom is not None:
            return self.rom
        raise RuntimeError("No hay ROM cargada en MemoryExtendEngine.")

    def inspect_status(self) -> Dict[str, Any]:
        """Audita la ROM y determina el estado de despacho y capacidad libre in-slot."""
        rom = self.get_rom_bytes()
        get_max, get_ptr = struct.unpack_from("<II", rom, self.GET_LIMIT_OFF)
        set_max, set_ptr = struct.unpack_from("<II", rom, self.SET_LIMIT_OFF)
        curr_get_count = get_max + 1
        curr_set_count = set_max + 1
        is_expanded = (get_ptr != self.GET_TABLE_ORIG or set_ptr != self.SET_TABLE_ORIG)

        existing_custom = []
        used_byte_offsets: Set[int] = set()
        used_bit_slots: Set[Tuple[int, int]] = set()

        if is_expanded:
            tbl_off = get_ptr - 0x08000000
            for fid in range(self.GET_COUNT_ORIG, curr_get_count):
                gh = struct.unpack_from("<I", rom, tbl_off + fid * 4)[0] - 0x08000000
                ins_0c = struct.unpack_from("<H", rom, gh + 0x0C)[0]
                ins_0e = struct.unpack_from("<H", rom, gh + 0x0E)[0]

                if ins_0e == 0x4B02:
                    # Handler u8/u16/u32 (28 bytes, literal pool en +0x14)
                    ctx_off = struct.unpack_from("<I", rom, gh + 0x14)[0]
                    if ins_0c == 0x7800:
                        mode, width = "u8", 1
                    elif ins_0c == 0x8800:
                        mode, width = "u16", 2
                    else:
                        mode, width = "u32", 4
                    for k in range(width):
                        used_byte_offsets.add(ctx_off + k)
                    existing_custom.append({
                        "id": fid,
                        "hex": f"0x{fid:03X}",
                        "mode": mode,
                        "ctx_off": ctx_off,
                        "bit": None,
                        "sram1": f"0x{0x002C + ctx_off:04X}",
                        "ewram1": f"0x{0x020025D8 + ctx_off:08X}",
                        "get_rom": f"0x08{gh:06X}"
                    })
                else:
                    # Handler bit (32 bytes, literal pool en +0x18)
                    ctx_off = struct.unpack_from("<I", rom, gh + 0x18)[0]
                    bit_idx = ((ins_0e >> 6) & 0x1F) if (ins_0e & 0xF800) == 0x0800 else 0
                    used_bit_slots.add((ctx_off, bit_idx))
                    existing_custom.append({
                        "id": fid,
                        "hex": f"0x{fid:03X}",
                        "mode": "bit",
                        "ctx_off": ctx_off,
                        "bit": bit_idx,
                        "sram1": f"0x{0x002C + ctx_off:04X}",
                        "ewram1": f"0x{0x020025D8 + ctx_off:08X}",
                        "get_rom": f"0x08{gh:06X}"
                    })

        free_bytes = [o for o in self.IN_SLOT_BYTES_RANGE if o not in used_byte_offsets]
        free_bits = [b for b in self.IN_SLOT_BITS_POOL if b not in used_bit_slots]

        even_u16 = [o for o in free_bytes if o % 2 == 0 and (o + 1) in free_bytes]
        aligned_u32 = [o for o in free_bytes if o % 4 == 0 and all((o + k) in free_bytes for k in range(4))]

        return {
            "get_max": get_max,
            "get_ptr": get_ptr,
            "get_count": curr_get_count,
            "set_max": set_max,
            "set_ptr": set_ptr,
            "set_count": curr_set_count,
            "custom_count": curr_get_count - self.GET_COUNT_ORIG,
            "is_expanded": is_expanded,
            "existing_custom": existing_custom,
            "free_bytes": free_bytes,
            "free_bits": free_bits,
            "capacity": {
                "free_bits_count": len(free_bits),
                "free_bytes_count": len(free_bytes),
                "max_u8": len(free_bytes),
                "max_u16": len(even_u16),
                "max_u32": len(aligned_u32),
                "even_u16_offsets": even_u16,
                "aligned_u32_offsets": aligned_u32
            }
        }

    # --- Compiladores de Bytecode Thumb ---
    @classmethod
    def _build_word_get(cls, ctx_off: int, mode: str) -> bytes:
        # 28 bytes (0x1C), alineado a 4 bytes
        ldr_op = {"u8": "00 78", "u16": "00 88", "u32": "00 68"}[mode]
        code = bytes.fromhex(
            f"d4 21 89 00 50 18 00 68 02 4a 80 18 {ldr_op} 02 4b 18 47 00 00"
        )
        return code + struct.pack("<II", ctx_off, cls.GET_EPILOGUE)

    @classmethod
    def _build_word_set(cls, ctx_off: int, mode: str) -> bytes:
        # 28 bytes (0x1C), alineado a 4 bytes
        str_op = {"u8": "06 70", "u16": "06 80", "u32": "06 60"}[mode]
        code = bytes.fromhex(
            f"d4 20 80 00 38 18 00 68 02 4a 80 18 {str_op} 02 4b 18 47 00 00"
        )
        return code + struct.pack("<II", ctx_off, cls.SET_EPILOGUE)

    @classmethod
    def _build_bit_get(cls, ctx_off: int, bit: int) -> bytes:
        # 32 bytes (0x20), alineado a 4 bytes
        lsr_ins = (0x0800 | (bit << 6)).to_bytes(2, "little") if bit > 0 else b"\x00\x00"
        code = (
            bytes.fromhex("d4 21 89 00 50 18 00 68 03 4a 80 18 00 78")
            + lsr_ins
            + bytes.fromhex("01 21 08 40 01 4b 18 47")
        )
        return code + struct.pack("<II", ctx_off, cls.GET_EPILOGUE)

    @classmethod
    def _build_bit_set(cls, ctx_off: int, bit: int) -> bytes:
        # 40 bytes (0x28), alineado a 4 bytes
        mask = 1 << bit
        code = bytes.fromhex(
            "d4 20 80 00 38 18 00 68 05 4a 82 18 10 78 "
            f"{mask:02x} 21 88 43 00 2e 00 d0 08 43 10 70 02 4b 18 47 00 00"
        )
        return code + struct.pack("<II", ctx_off, cls.SET_EPILOGUE)

    @staticmethod
    def allocate_from_free(
        free_bytes: List[int],
        free_bits: List[Tuple[int, int]],
        mode: str
    ) -> Tuple[int, int]:
        """Asigna y consume automaticamente el siguiente offset/bit alineado disponible."""
        if mode == "bit":
            if not free_bits:
                raise RuntimeError("Sin bits libres disponibles en el banco principal (0x215E..0x21CF).")
            return free_bits.pop(0)

        width = {"u8": 1, "u16": 2, "u32": 4}[mode]
        align = width
        free_set = set(free_bytes)
        for off in free_bytes:
            if off % align == 0 and all((off + k) in free_set for k in range(width)):
                for k in range(width):
                    free_bytes.remove(off + k)
                return off, 0

        raise RuntimeError(f"Sin bloque contiguo alineado a {align}B de {width} bytes libre en 0x34AC..0x34C3.")

    def inject(
        self,
        specs: List[CustomFlagSpec],
        fsf_start: int = 0x75B000,
        safety_pad: int = 0x40,
        sync_csv: bool = True
    ) -> Tuple[int, List[Dict]]:
        """
        Ejecuta la expansion en ROM:
        - Relocaliza las tablas GET y SET.
        - Compila los handlers Thumb.
        - Actualiza los punteros y limites maestros.
        - Sincroniza Fomt_Flags.csv.
        """
        rom = self.get_rom_bytes()
        status = self.inspect_status()
        base_get_count = status["get_count"]
        base_set_count = status["set_count"]
        curr_get_off   = status["get_ptr"] - 0x08000000
        curr_set_off   = status["set_ptr"] - 0x08000000

        compiled_pairs = []
        for sp in specs:
            if sp.mode in ("u8", "u16", "u32"):
                if sp.mode == "u16" and (sp.ctx_offset % 2 != 0):
                    raise ValueError(f"{sp.name}: u16 requiere offset par (alineado a 2B), recibido 0x{sp.ctx_offset:04X}")
                if sp.mode == "u32" and (sp.ctx_offset % 4 != 0):
                    raise ValueError(f"{sp.name}: u32 requiere offset multiplo de 4 (alineado a 4B), recibido 0x{sp.ctx_offset:04X}")
                gh = self._build_word_get(sp.ctx_offset, sp.mode)
                sh = self._build_word_set(sp.ctx_offset, sp.mode)
            elif sp.mode == "bit":
                if not (0 <= sp.bit_index <= 7):
                    raise ValueError(f"bit_index invalido ({sp.bit_index}) en {sp.name}")
                gh = self._build_bit_get(sp.ctx_offset, sp.bit_index)
                sh = self._build_bit_set(sp.ctx_offset, sp.bit_index)
            else:
                raise ValueError(f"Modo desconocido '{sp.mode}' en {sp.name}")
            compiled_pairs.append((sp, gh, sh))

        n = len(specs)
        new_get_count = base_get_count + n
        new_set_count = base_set_count + n

        tables_size = (new_get_count + new_set_count) * 4
        handlers_size = sum(len(gh) + len(sh) for _, gh, sh in compiled_pairs)
        total_payload = tables_size + handlers_size

        alloc_off = FreeSpaceFinder.find_block(
            rom,
            required_bytes=total_payload,
            start_offset=fsf_start,
            alignment=4,
            safety_pad=safety_pad,
            free_byte=0xFF
        )

        get_tbl_off = alloc_off
        set_tbl_off = get_tbl_off + new_get_count * 4
        cursor = set_tbl_off + new_set_count * 4

        # Copiar tablas existentes
        rom[get_tbl_off : get_tbl_off + base_get_count * 4] = (
            rom[curr_get_off : curr_get_off + base_get_count * 4]
        )
        rom[set_tbl_off : set_tbl_off + base_set_count * 4] = (
            rom[curr_set_off : curr_set_off + base_set_count * 4]
        )

        manifest = []
        for i, (sp, gh, sh) in enumerate(compiled_pairs):
            gh_off = cursor
            rom[gh_off : gh_off + len(gh)] = gh
            cursor += len(gh)

            sh_off = cursor
            rom[sh_off : sh_off + len(sh)] = sh
            cursor += len(sh)

            struct.pack_into("<I", rom, get_tbl_off + (base_get_count + i) * 4, 0x08000000 + gh_off)
            struct.pack_into("<I", rom, set_tbl_off + (base_set_count + i) * 4, 0x08000000 + sh_off)

            fid = base_get_count + i
            manifest.append({
                "id": fid,
                "hex": f"0x{fid:03X}",
                "name": sp.name,
                "mode": sp.mode,
                "ctx_off": f"0x{sp.ctx_offset:04X}",
                "bit": str(sp.bit_index) if sp.mode == "bit" else ("0..7" if sp.mode == "u8" else ("0..15" if sp.mode == "u16" else "0..31")),
                "sram1": f"0x{0x002C + sp.ctx_offset:04X}",
                "ewram1": f"0x{0x020025D8 + sp.ctx_offset:08X}",
                "get_rom": f"0x08{gh_off:06X}",
                "set_rom": f"0x08{sh_off:06X}",
            })

        # Actualizar punteros y limites en el codigo maestro del juego
        struct.pack_into("<II", rom, self.GET_LIMIT_OFF, new_get_count - 1, 0x08000000 + get_tbl_off)
        struct.pack_into("<II", rom, self.SET_LIMIT_OFF, new_set_count - 1, 0x08000000 + set_tbl_off)

        # Si ya estaba expandida antes, liberar la tabla anterior con 0xFF
        if status["is_expanded"]:
            old_tables_bytes = (base_get_count + base_set_count) * 4
            rom[curr_get_off : curr_get_off + old_tables_bytes] = b"\xFF" * old_tables_bytes

        # Si estamos integrados con un proyecto de FOMT Studio, registrar el parche
        if self.project is not None:
            if hasattr(self.project, 'write_patch'):
                # Registrar escritura de la tabla y handlers
                self.project.write_patch(alloc_off, bytes(rom[alloc_off:cursor]))
                self.project.write_patch(self.GET_LIMIT_OFF, bytes(rom[self.GET_LIMIT_OFF : self.GET_LIMIT_OFF + 8]))
                self.project.write_patch(self.SET_LIMIT_OFF, bytes(rom[self.SET_LIMIT_OFF : self.SET_LIMIT_OFF + 8]))
                if status["is_expanded"]:
                    self.project.write_patch(curr_get_off, b"\xFF" * old_tables_bytes)

        # Sincronizar Fomt_Flags.csv para autocompletado y descompilacion inmediata
        if sync_csv:
            self.sync_flags_to_csv(manifest)

        return alloc_off, manifest

    def sync_flags_to_csv(self, manifest: List[Dict], csv_path: Optional[str] = None):
        """Agrega las flags recien inyectadas a Fomt_Flags.csv para el IDE y eventos."""
        target_csv = csv_path
        if not target_csv:
            if self.project and hasattr(self.project, "get_csv_path"):
                prefix = "MFomt_" if getattr(self.project, "is_mfomt", False) else "Fomt_"
                target_csv = self.project.get_csv_path(f"{prefix}Flags.csv")
            else:
                target_csv = get_data_path("fomt", "Fomt_Flags.csv")

        if not os.path.isfile(target_csv):
            # Intentar fallback local
            target_csv = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "Banco_de_Datos", "Cilixes", "fomt", "Fomt_Flags.csv"
            )

        if not os.path.isfile(target_csv):
            return

        existing_ids = set()
        rows = []
        with open(target_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, ["flag_id", "Flag_name", "type_value"])
            for r in reader:
                if len(r) >= 2:
                    existing_ids.add(r[0].strip().lower())
                    rows.append(r)

        modified = False
        for m in manifest:
            fid_hex = m["hex"].lower()
            if fid_hex not in existing_ids:
                type_val = "binary" if m["mode"] == "bit" else "state"
                rows.append([m["hex"], m["name"], type_val])
                existing_ids.add(fid_hex)
                modified = True

        if modified:
            with open(target_csv, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerows(rows)

    def save(self, out_path: str):
        rom = self.get_rom_bytes()
        with open(out_path, "wb") as f:
            f.write(rom)


# ==============================================================================
# DIALOGO VISUAL EN FOMT STUDIO (MemoryExtendDialog)
# ==============================================================================
class MemoryExtendDialog(QDialog):
    """
    Panel interactivo integrado en FOMT Studio para auditar e inyectar
    flags expandidas en la ROM del proyecto.
    """

    def __init__(self, parent=None, project=None):
        super().__init__(parent)
        self.project = project
        self.lang = getattr(parent, "current_lang", "es") if parent else "es"
        self.engine = MemoryExtendEngine(project)
        self.pending_specs: List[CustomFlagSpec] = []
        self._setup_ui()
        self.refresh_status()

    def _setup_ui(self):
        self.setWindowTitle(tr("mem_ext_title", self.lang))
        self.resize(950, 700)
        self.setStyleSheet("""
            QDialog {
                background-color: #0D1117;
                color: #C9D1D9;
            }
            QGroupBox {
                font-weight: bold;
                color: #58A6FF;
                border: 1px solid #30363D;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 12px;
                background-color: #161B22;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QLabel {
                color: #C9D1D9;
            }
            QLineEdit, QComboBox, QSpinBox {
                background-color: #0D1117;
                color: #FFFFFF;
                border: 1px solid #30363D;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                border-color: #58A6FF;
            }
            QTableWidget {
                background-color: #0D1117;
                color: #C9D1D9;
                border: 1px solid #30363D;
                gridline-color: #21262D;
                border-radius: 4px;
            }
            QHeaderView::section {
                background-color: #21262D;
                color: #58A6FF;
                font-weight: bold;
                border: 1px solid #30363D;
                padding: 4px;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # 1. Grupo de Estado y Capacidad
        grp_status = QGroupBox(tr("mem_ext_status_label", self.lang))
        lay_status = QVBoxLayout(grp_status)

        self.lbl_rom_state = QLabel("Estado ROM: Auditing...")
        self.lbl_rom_state.setStyleSheet("font-weight: bold; font-size: 12px; color: #58A6FF;")
        self.lbl_capacity_bits = QLabel("Bits Libres: ...")
        self.lbl_capacity_bytes = QLabel("Bytes Libres: ...")
        self.lbl_capacity_vars = QLabel("Capacidad: ...")
        self.lbl_capacity_vars.setStyleSheet("color: #3FB950; font-size: 11px;")

        lay_status.addWidget(self.lbl_rom_state)
        row_cap = QHBoxLayout()
        row_cap.addWidget(self.lbl_capacity_bits)
        row_cap.addWidget(self.lbl_capacity_bytes)
        row_cap.addWidget(self.lbl_capacity_vars)
        lay_status.addLayout(row_cap)
        main_layout.addWidget(grp_status)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # 2. Tabla de Flags Custom ya activas en ROM
        grp_existing = QGroupBox(tr("mem_ext_custom_flags", self.lang))
        lay_existing = QVBoxLayout(grp_existing)
        self.tbl_existing = QTableWidget()
        self.tbl_existing.setColumnCount(7)
        self.tbl_existing.setHorizontalHeaderLabels([
            "ID Hex", "Modo", "Offset [ctx+0x350]", "Bit", "SRAM Slot1", "EWRAM", "Handler ROM"
        ])
        self.tbl_existing.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_existing.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        lay_existing.addWidget(self.tbl_existing)
        splitter.addWidget(grp_existing)

        # 3. Formulario para añadir nueva flag
        grp_add = QGroupBox(tr("mem_ext_add_title", self.lang))
        lay_add = QVBoxLayout(grp_add)

        form_row = QHBoxLayout()
        form_row.addWidget(QLabel("Nombre:"))
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("Ej: Evento_Nuevo_Popuri")
        form_row.addWidget(self.edit_name, 2)

        form_row.addWidget(QLabel("Modo / Tipo:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItem("bit (Booleano 0..1)", "bit")
        self.combo_mode.addItem("u8 (Byte 0..255)", "u8")
        self.combo_mode.addItem("u16 (Entero 16-bit)", "u16")
        self.combo_mode.addItem("u32 (Entero 32-bit)", "u32")
        self.combo_mode.currentIndexChanged.connect(self._on_mode_changed)
        form_row.addWidget(self.combo_mode, 1)

        self.chk_auto = QCheckBox("Auto-asignar in-slot")
        self.chk_auto.setChecked(True)
        self.chk_auto.toggled.connect(self._on_auto_toggled)
        form_row.addWidget(self.chk_auto)

        form_row.addWidget(QLabel("Offset (Hex):"))
        self.edit_manual_off = QLineEdit("0x34AC")
        self.edit_manual_off.setEnabled(False)
        self.edit_manual_off.setMaximumWidth(80)
        form_row.addWidget(self.edit_manual_off)

        form_row.addWidget(QLabel("Bit (0..7):"))
        self.spin_manual_bit = QSpinBox()
        self.spin_manual_bit.setRange(0, 7)
        self.spin_manual_bit.setEnabled(False)
        self.spin_manual_bit.setMaximumWidth(60)
        form_row.addWidget(self.spin_manual_bit)

        self.btn_add_queue = QPushButton("Añadir a la Cola")
        self.btn_add_queue.setStyleSheet("""
            QPushButton {
                background-color: #21262D;
                color: #58A6FF;
                border: 1px solid #30363D;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #30363D;
                border-color: #58A6FF;
            }
        """)
        self.btn_add_queue.clicked.connect(self._on_add_to_queue)
        form_row.addWidget(self.btn_add_queue)
        lay_add.addLayout(form_row)

        # 4. Tabla de cola pendiente
        lay_add.addWidget(QLabel(tr("mem_ext_queue_title", self.lang) + ":"))
        self.tbl_queue = QTableWidget()
        self.tbl_queue.setColumnCount(5)
        self.tbl_queue.setHorizontalHeaderLabels(["ID Estimado", "Nombre", "Tipo", "Offset Relativo", "Bit"])
        self.tbl_queue.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_queue.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        lay_add.addWidget(self.tbl_queue)

        btn_queue_row = QHBoxLayout()
        self.btn_del_queue = QPushButton("Eliminar de la Cola")
        self.btn_del_queue.clicked.connect(self._on_remove_from_queue)
        self.btn_clear_queue = QPushButton("Limpiar Cola")
        self.btn_clear_queue.clicked.connect(self._on_clear_queue)
        btn_queue_row.addWidget(self.btn_del_queue)
        btn_queue_row.addWidget(self.btn_clear_queue)
        btn_queue_row.addStretch()
        lay_add.addLayout(btn_queue_row)

        splitter.addWidget(grp_add)
        main_layout.addWidget(splitter, 1)

        # 5. Barra Inferior con Botón de Inyección
        bottom_row = QHBoxLayout()
        self.lbl_summary_notice = QLabel("Límite estricto in-slot: 19 bits booleanos y 24 bytes contiguos.")
        self.lbl_summary_notice.setStyleSheet("color: #8B949E; font-size: 11px;")
        bottom_row.addWidget(self.lbl_summary_notice)
        bottom_row.addStretch()

        self.btn_inject = QPushButton(tr("mem_ext_inject_btn", self.lang))
        self.btn_inject.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 12px;
                border-radius: 6px;
                padding: 8px 18px;
            }
            QPushButton:hover {
                background-color: #2EA043;
            }
        """)
        self.btn_inject.clicked.connect(self._on_inject_clicked)
        bottom_row.addWidget(self.btn_inject)

        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #21262D;
                color: #C9D1D9;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #30363D;
            }
        """)
        bottom_row.addWidget(btn_close)

        main_layout.addLayout(bottom_row)

    def _on_mode_changed(self):
        mode = self.combo_mode.currentData()
        self.spin_manual_bit.setEnabled(not self.chk_auto.isChecked() and mode == "bit")

    def _on_auto_toggled(self, checked: bool):
        mode = self.combo_mode.currentData()
        self.edit_manual_off.setEnabled(not checked)
        self.spin_manual_bit.setEnabled(not checked and mode == "bit")

    def refresh_status(self):
        """Actualiza el estado de la ROM y métricas in-slot."""
        try:
            st = self.engine.inspect_status()
        except Exception as e:
            self.lbl_rom_state.setText(f"Error al auditar ROM: {e}")
            return

        tag = f"EXPANDIDA (+{st['custom_count']} flags @ 0x{st['get_ptr']:08X})" if st["is_expanded"] else "BASE / VIRGEN (0x000..0x24D)"
        self.lbl_rom_state.setText(f"Estado ROM: {tag} | IDs: 0x000..0x{st['get_max']:03X} ({st['get_count']} flags)")

        cap = st["capacity"]
        self.lbl_capacity_bits.setText(f"Bits Libres: {cap['free_bits_count']} / {len(MemoryExtendEngine.IN_SLOT_BITS_POOL)}")
        self.lbl_capacity_bytes.setText(f"Bytes Libres: {cap['free_bytes_count']} / {len(MemoryExtendEngine.IN_SLOT_BYTES_RANGE)}")
        self.lbl_capacity_vars.setText(f"Disponibles: u8={cap['max_u8']} | u16={cap['max_u16']} | u32={cap['max_u32']}")

        # Llenar tabla de flags existentes
        existing = st["existing_custom"]
        self.tbl_existing.setRowCount(len(existing))
        for r, item in enumerate(existing):
            self.tbl_existing.setItem(r, 0, QTableWidgetItem(item["hex"]))
            self.tbl_existing.setItem(r, 1, QTableWidgetItem(item["mode"]))
            self.tbl_existing.setItem(r, 2, QTableWidgetItem(f"0x{item['ctx_off']:04X}"))
            bit_str = str(item["bit"]) if item["bit"] is not None else "-"
            self.tbl_existing.setItem(r, 3, QTableWidgetItem(bit_str))
            self.tbl_existing.setItem(r, 4, QTableWidgetItem(item["sram1"]))
            self.tbl_existing.setItem(r, 5, QTableWidgetItem(item["ewram1"]))
            self.tbl_existing.setItem(r, 6, QTableWidgetItem(item["get_rom"]))

    def _on_add_to_queue(self):
        name = self.edit_name.text().strip()
        mode = self.combo_mode.currentData()

        if not name:
            QMessageBox.warning(self, "Aviso", "Por favor introduce un nombre simbólico para la flag.")
            return

        # Comprobar nombre duplicado en cola
        if any(sp.name == name for sp in self.pending_specs):
            QMessageBox.warning(self, "Aviso", f"Ya existe una flag con el nombre '{name}' en la cola.")
            return

        st = self.engine.inspect_status()
        # Copiar listas de libres descontando las que ya están en la cola
        used_queue_bytes = set()
        used_queue_bits = set()
        for sp in self.pending_specs:
            if sp.mode == "bit":
                used_queue_bits.add((sp.ctx_offset, sp.bit_index))
            else:
                w = sp.width_bytes
                for k in range(w):
                    used_queue_bytes.add(sp.ctx_offset + k)

        free_bytes = [o for o in st["free_bytes"] if o not in used_queue_bytes]
        free_bits = [b for b in st["free_bits"] if b not in used_queue_bits]

        if self.chk_auto.isChecked():
            try:
                off, bit = MemoryExtendEngine.allocate_from_free(free_bytes, free_bits, mode)
            except RuntimeError as err:
                QMessageBox.critical(self, "Capacidad Excedida", str(err))
                return
        else:
            try:
                off = int(self.edit_manual_off.text().strip(), 16)
            except ValueError:
                QMessageBox.warning(self, "Error", "Offset manual no válido.")
                return
            bit = self.spin_manual_bit.value() if mode == "bit" else 0

        spec = CustomFlagSpec(name=name, mode=mode, ctx_offset=off, bit_index=bit)
        self.pending_specs.append(spec)
        self.edit_name.clear()
        self._refresh_queue_table()

    def _refresh_queue_table(self):
        st = self.engine.inspect_status()
        base_id = st["get_count"]
        self.tbl_queue.setRowCount(len(self.pending_specs))
        for r, sp in enumerate(self.pending_specs):
            fid = base_id + r
            self.tbl_queue.setItem(r, 0, QTableWidgetItem(f"0x{fid:03X} ({fid})"))
            self.tbl_queue.setItem(r, 1, QTableWidgetItem(sp.name))
            self.tbl_queue.setItem(r, 2, QTableWidgetItem(sp.mode))
            self.tbl_queue.setItem(r, 3, QTableWidgetItem(f"0x{sp.ctx_offset:04X}"))
            bit_str = str(sp.bit_index) if sp.mode == "bit" else "-"
            self.tbl_queue.setItem(r, 4, QTableWidgetItem(bit_str))

    def _on_remove_from_queue(self):
        row = self.tbl_queue.currentRow()
        if 0 <= row < len(self.pending_specs):
            self.pending_specs.pop(row)
            self._refresh_queue_table()

    def _on_clear_queue(self):
        self.pending_specs.clear()
        self._refresh_queue_table()

    def _on_inject_clicked(self):
        if not self.pending_specs:
            QMessageBox.information(self, "Aviso", "No hay flags en la cola para inyectar.")
            return

        count = len(self.pending_specs)
        reply = QMessageBox.question(
            self,
            "Confirmar Inyección",
            f"¿Deseas inyectar {count} flags/variables en la ROM virtual del proyecto?\n"
            f"Se relocalizarán las tablas de despacho GET y SET a espacio libre contiguo.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            alloc_off, manifest = self.engine.inject(self.pending_specs, sync_csv=True)
            self.pending_specs.clear()
            self._refresh_queue_table()
            self.refresh_status()

            summary_lines = [
                f"Bloque inyectado en ROM: 0x08{alloc_off:06X}",
                f"Nuevas flags añadidas: {len(manifest)}",
                "",
                "Detalle de IDs asignados:"
            ]
            for m in manifest:
                summary_lines.append(f"  * {m['hex']} ({m['id']}): {m['name']} [{m['mode']}] -> [ctx+0x350]+{m['ctx_off']}")

            summary_lines.append("\nSincronizado con Fomt_Flags.csv para autocompletado y descompilación en el IDE.")
            QMessageBox.information(self, "Inyección Exitosa", "\n".join(summary_lines))

        except Exception as e:
            QMessageBox.critical(self, "Error de Inyección", str(e))


# ==============================================================================
# ENLACE CLI STANDALONE (Mantiene compatibilidad directa con flagser.py)
# ==============================================================================
def main():
    print("=== FOMT STUDIO :: MemoryExtendEngine (CLI) ===")
    roms = sorted(glob.glob(os.path.join(".", "**", "*.gba"), recursive=True))
    if not roms:
        print("No se encontraron archivos .gba en el directorio actual.")
        return

    print("\nROMs .gba detectadas:")
    for idx, r in enumerate(roms):
        st = MemoryExtendEngine(r).inspect_status()
        tag = f"[EXPANDIDA: +{st['custom_count']} flags @ 0x{st['get_ptr']:08X}]" if st["is_expanded"] else "[BASE / VIRGEN]"
        print(f"  [{idx}] {r} {tag}")

    sel_str = input("\nSelecciona el indice de la ROM (0..N): ").strip()
    if not sel_str.isdigit():
        return
    rom_in = roms[int(sel_str)]

    engine = MemoryExtendEngine(rom_in)
    st = engine.inspect_status()
    print(f"\nRango actual: 0x000..0x{st['get_max']:03X} ({st['get_count']} flags totales)")
    print(f"Bits libres in-slot: {st['capacity']['free_bits_count']}")
    print(f"Bytes libres in-slot: {st['capacity']['free_bytes_count']}")

    n_new = int(input("\n¿Cuantas flags nuevas deseas configurar? (0 para salir): ").strip() or "0")
    if n_new <= 0:
        return

    free_bytes_work = list(st["free_bytes"])
    free_bits_work = list(st["free_bits"])
    specs: List[CustomFlagSpec] = []

    for i in range(n_new):
        next_id = st["get_count"] + i
        name = input(f"  [{i+1}/{n_new}] ID 0x{next_id:03X} - Nombre: ").strip() or f"Custom_0x{next_id:03X}"
        mode = input(f"  [{i+1}/{n_new}] ID 0x{next_id:03X} - Tipo [bit/u8/u16/u32] (Enter=u8): ").strip().lower() or "u8"
        off, bit = MemoryExtendEngine.allocate_from_free(free_bytes_work, free_bits_work, mode)
        specs.append(CustomFlagSpec(name=name, mode=mode, ctx_offset=off, bit_index=bit))
        print(f"      -> Asignado: {mode} en [ctx+0x350]+0x{off:04X}" + (f" bit {bit}" if mode == "bit" else ""))

    alloc_off, manifest = engine.inject(specs, sync_csv=True)
    base_name, ext = os.path.splitext(rom_in)
    rom_out = f"{base_name}_FlagsPlus{ext}"
    engine.save(rom_out)

    print(f"\nInyeccion completada en 0x08{alloc_off:06X}")
    print(f"ROM guardada en: {rom_out}")


if __name__ == "__main__":
    main()

