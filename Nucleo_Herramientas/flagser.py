import os
import glob
import struct
from dataclasses import dataclass
from typing import List, Dict, Tuple, Set


@dataclass
class CustomFlagSpec:
    """Definición al milímetro de cada flag o variable nueva."""
    name: str
    mode: str           # "bit" (0..1), "u8" (0..255), "u16" (0..65535), "u32" (0..0xFFFFFFFF)
    ctx_offset: int     # Offset relativo a [ctx + 0x350]
    bit_index: int = 0  # Solo usado si mode == "bit" (0..7)


class FreeSpaceFinder:
    """Buscador de espacio libre alineado a 4 bytes en ROM GBA."""

    @staticmethod
    def find_block(
        rom: bytes,
        required_bytes: int,
        start_offset: int = 0x75B000,
        alignment: int = 4,
        safety_pad: int = 0x40,
        free_byte: int = 0xFF
    ) -> int:
        total_needed = required_bytes + (safety_pad * 2)
        target_pattern = bytes([free_byte]) * total_needed

        pos = (start_offset + alignment - 1) & ~(alignment - 1)
        while pos + total_needed <= len(rom):
            idx = rom.find(target_pattern, pos)
            if idx == -1:
                break
            usable_start = (idx + safety_pad + alignment - 1) & ~(alignment - 1)
            if usable_start + required_bytes + safety_pad <= len(rom):
                end_check = usable_start + required_bytes + safety_pad
                if all(b == free_byte for b in rom[idx:end_check]):
                    return usable_start
            pos = idx + alignment

        raise RuntimeError(
            f"FSF: No se encontró un bloque contiguo de {required_bytes} bytes "
            f"(+0x{safety_pad*2:X} pad) de 0x{free_byte:02X} a partir de 0x08{start_offset:06X}."
        )


class FOMTFlagInjector:
    """Motor de expansión incremental y milimétrica para FoMT (USA)."""

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

    # Pool verificado in-slot (cubierto por checksum nativo u32[0x3520])
    IN_SLOT_BYTES_RANGE = range(0x34AC, 0x34C4)  # 24 bytes contiguos limpios (0x34AC..0x34C3)
    IN_SLOT_BITS_POOL = [
        (0x215F, 7), (0x2163, 7), (0x2167, 7), (0x216B, 7),
        (0x216E, 7), (0x217B, 7), (0x2183, 7), (0x2187, 7),
        (0x219B, 7), (0x21A0, 7), (0x21A3, 7), (0x21A7, 7),
        (0x21C3, 7), (0x21B7, 6), (0x21B7, 7), (0x21BB, 6),
        (0x21BB, 7), (0x21BF, 6), (0x21BF, 7),
    ]

    def __init__(self, rom_path: str):
        self.rom_path = rom_path
        self.rom = bytearray(open(rom_path, "rb").read())

    def inspect_status(self) -> Dict:
        get_max, get_ptr = struct.unpack_from("<II", self.rom, self.GET_LIMIT_OFF)
        set_max, set_ptr = struct.unpack_from("<II", self.rom, self.SET_LIMIT_OFF)
        curr_get_count = get_max + 1
        curr_set_count = set_max + 1
        is_expanded = (get_ptr != self.GET_TABLE_ORIG or set_ptr != self.SET_TABLE_ORIG)

        existing_custom = []
        used_byte_offsets: Set[int] = set()
        used_bit_slots: Set[Tuple[int, int]] = set()

        if is_expanded:
            tbl_off = get_ptr - 0x08000000
            for fid in range(self.GET_COUNT_ORIG, curr_get_count):
                gh = struct.unpack_from("<I", self.rom, tbl_off + fid * 4)[0] - 0x08000000
                ins_0c = struct.unpack_from("<H", self.rom, gh + 0x0C)[0]
                ins_0e = struct.unpack_from("<H", self.rom, gh + 0x0E)[0]
                ins_10 = struct.unpack_from("<H", self.rom, gh + 0x10)[0]

                if ins_0e == 0x4B02:
                    # Handler u8/u16/u32 (28 bytes, pool en +0x14)
                    ctx_off = struct.unpack_from("<I", self.rom, gh + 0x14)[0]
                    if ins_0c == 0x7800:
                        mode, width = "u8", 1
                    elif ins_0c == 0x8800:
                        mode, width = "u16", 2
                    else:
                        mode, width = "u32", 4
                    for k in range(width):
                        used_byte_offsets.add(ctx_off + k)
                    existing_custom.append((fid, mode, ctx_off, None))
                else:
                    # Handler bit (32 bytes, pool en +0x18)
                    ctx_off = struct.unpack_from("<I", self.rom, gh + 0x18)[0]
                    bit_idx = ((ins_0e >> 6) & 0x1F) if (ins_0e & 0xF800) == 0x0800 else 0
                    used_bit_slots.add((ctx_off, bit_idx))
                    existing_custom.append((fid, "bit", ctx_off, bit_idx))

        free_bytes = [o for o in self.IN_SLOT_BYTES_RANGE if o not in used_byte_offsets]
        free_bits = [b for b in self.IN_SLOT_BITS_POOL if b not in used_bit_slots]

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
        }

    # --- Compiladores Thumb ---
    @classmethod
    def _build_word_get(cls, ctx_off: int, mode: str) -> bytes:
        # 28 bytes (0x1C), 4-byte aligned
        ldr_op = {"u8": "00 78", "u16": "00 88", "u32": "00 68"}[mode]
        code = bytes.fromhex(
            f"d4 21 89 00 50 18 00 68 02 4a 80 18 {ldr_op} 02 4b 18 47 00 00"
        )
        return code + struct.pack("<II", ctx_off, cls.GET_EPILOGUE)

    @classmethod
    def _build_word_set(cls, ctx_off: int, mode: str) -> bytes:
        # 28 bytes (0x1C), 4-byte aligned
        str_op = {"u8": "06 70", "u16": "06 80", "u32": "06 60"}[mode]
        code = bytes.fromhex(
            f"d4 20 80 00 38 18 00 68 02 4a 80 18 {str_op} 02 4b 18 47 00 00"
        )
        return code + struct.pack("<II", ctx_off, cls.SET_EPILOGUE)

    @classmethod
    def _build_bit_get(cls, ctx_off: int, bit: int) -> bytes:
        # 32 bytes (0x20), 4-byte aligned
        lsr_ins = (0x0800 | (bit << 6)).to_bytes(2, "little") if bit > 0 else b"\x00\x00"
        code = (
            bytes.fromhex("d4 21 89 00 50 18 00 68 03 4a 80 18 00 78")
            + lsr_ins
            + bytes.fromhex("01 21 08 40 01 4b 18 47")
        )
        return code + struct.pack("<II", ctx_off, cls.GET_EPILOGUE)

    @classmethod
    def _build_bit_set(cls, ctx_off: int, bit: int) -> bytes:
        # 40 bytes (0x28), 4-byte aligned
        mask = 1 << bit
        code = bytes.fromhex(
            "d4 20 80 00 38 18 00 68 05 4a 82 18 10 78 "
            f"{mask:02x} 21 88 43 00 2e 00 d0 08 43 10 70 02 4b 18 47 00 00"
        )
        return code + struct.pack("<II", ctx_off, cls.SET_EPILOGUE)

    def inject(
        self,
        specs: List[CustomFlagSpec],
        fsf_start: int = 0x75B000,
        safety_pad: int = 0x40
    ) -> Tuple[int, List[Dict]]:
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
                    raise ValueError(f"{sp.name}: u32 requiere offset múltiplo de 4 (alineado a 4B), recibido 0x{sp.ctx_offset:04X}")
                gh = self._build_word_get(sp.ctx_offset, sp.mode)
                sh = self._build_word_set(sp.ctx_offset, sp.mode)
            elif sp.mode == "bit":
                if not (0 <= sp.bit_index <= 7):
                    raise ValueError(f"bit_index inválido ({sp.bit_index}) en {sp.name}")
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
            self.rom,
            required_bytes=total_payload,
            start_offset=fsf_start,
            alignment=4,
            safety_pad=safety_pad,
            free_byte=0xFF
        )

        get_tbl_off = alloc_off
        set_tbl_off = get_tbl_off + new_get_count * 4
        cursor = set_tbl_off + new_set_count * 4

        self.rom[get_tbl_off : get_tbl_off + base_get_count * 4] = (
            self.rom[curr_get_off : curr_get_off + base_get_count * 4]
        )
        self.rom[set_tbl_off : set_tbl_off + base_set_count * 4] = (
            self.rom[curr_set_off : curr_set_off + base_set_count * 4]
        )

        manifest = []
        for i, (sp, gh, sh) in enumerate(compiled_pairs):
            gh_off = cursor
            self.rom[gh_off : gh_off + len(gh)] = gh
            cursor += len(gh)

            sh_off = cursor
            self.rom[sh_off : sh_off + len(sh)] = sh
            cursor += len(sh)

            struct.pack_into("<I", self.rom, get_tbl_off + (base_get_count + i) * 4, 0x08000000 + gh_off)
            struct.pack_into("<I", self.rom, set_tbl_off + (base_set_count + i) * 4, 0x08000000 + sh_off)

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

        struct.pack_into("<II", self.rom, self.GET_LIMIT_OFF, new_get_count - 1, 0x08000000 + get_tbl_off)
        struct.pack_into("<II", self.rom, self.SET_LIMIT_OFF, new_set_count - 1, 0x08000000 + set_tbl_off)

        if status["is_expanded"]:
            old_tables_bytes = (base_get_count + base_set_count) * 4
            self.rom[curr_get_off : curr_get_off + old_tables_bytes] = b"\xFF" * old_tables_bytes

        return alloc_off, manifest

    def save(self, out_path: str):
        open(out_path, "wb").write(self.rom)


# ==============================================================================
# INTERFAZ DE CONSOLA INTERACTIVA CON AUDITORÍA DE CAPACIDAD Y TAMAÑO AL MILÍMETRO
# ==============================================================================
def scan_gba_roms(base_dir: str = ".") -> List[str]:
    roms = sorted(glob.glob(os.path.join(base_dir, "**", "*.gba"), recursive=True))
    return [os.path.relpath(r, base_dir) for r in roms]


def allocate_from_free(free_bytes: List[int], free_bits: List[Tuple[int, int]], mode: str) -> Tuple[int, int]:
    """Asigna y consume automáticamente el siguiente offset/bit alineado disponible."""
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


def main():
    print("=== FOMT STUDIO :: CONFIGURADOR MILIMÉTRICO DE FLAGS (FlagTensorNode) ===")
    roms = scan_gba_roms(".")
    if not roms:
        print("[!] No se encontraron archivos .gba en el directorio actual.")
        return

    print("\nROMs .gba disponibles:")
    for idx, r in enumerate(roms):
        size_mb = os.path.getsize(r) / (1024 * 1024)
        st = FOMTFlagInjector(r).inspect_status()
        tag = f"[EXPANDIDA: +{st['custom_count']} flags @ 0x{st['get_ptr']:08X}]" if st["is_expanded"] else "[BASE / VIRGEN]"
        print(f"  [{idx}] {r} ({size_mb:.2f} MB) {tag}")

    sel = int(input("\nSelecciona el índice de la ROM a auditar/parchar: ").strip())
    rom_in = roms[sel]
    injector = FOMTFlagInjector(rom_in)
    st = injector.inspect_status()

    print("\n--- AUDITORÍA DE MEMORIA Y LÍMITES REALES (IN-SLOT / CHECKSUM NATIVO) ---")
    print(f"Rango de IDs actual       : 0x000 .. 0x{st['get_max']:03X} ({st['get_count']} flags totales, techo despachador = 0xFFFF)")
    if st["existing_custom"]:
        print("Flags custom ya activas   :")
        for fid, mode, off, bit in st["existing_custom"]:
            b_str = f" bit {bit}" if mode == "bit" else ""
            print(f"  * 0x{fid:03X} ({fid}) -> [{mode:3s}] [ctx+0x350]+0x{off:04X}{b_str}")

    fb = st["free_bytes"]
    fbit = st["free_bits"]
    even_u16 = [o for o in fb if o % 2 == 0 and (o + 1) in fb]
    aligned_u32 = [o for o in fb if o % 4 == 0 and all((o + k) in fb for k in range(4))]

    print("\nCapacidad libre disponible AHORA MISMO sin hooks de Save:")
    print(f"  1) Banco Principal (1-bit booleanos) : {len(fbit)} bits libres -> {[f'0x{o:04X}[{b}]' for o, b in fbit]}")
    print(f"  2) Cola Libre Slot 1 (0x34AC..0x34C3): {len(fb)} bytes libres -> {[hex(o) for o in fb]}")
    print(f"     -> Caben hasta {len(fb)} contadores u8 (0..255)")
    print(f"     -> O hasta {len(even_u16)} bitmasks u16 (0..0xFFFF, alineados a 2B: {[hex(o) for o in even_u16]})")
    print(f"     -> O hasta {len(aligned_u32)} enteros u32 (alineados a 4B: {[hex(o) for o in aligned_u32]})")
    print("  3) Techo Cola Muerta SRAM (0x6B00+)   : 5,376 bytes (requiere 3 hooks Save/Load si excedes la Cola Libre)")

    n_new = int(input("\n¿Cuántas flags nuevas deseas configurar una por una? (0 para salir): ").strip() or "0")
    if n_new <= 0:
        return

    fsf_raw = input("Offset inicial FSF en ROM (Enter = 0x75B000): ").strip()
    fsf_start = int(fsf_raw, 16) if fsf_raw else 0x75B000

    free_bytes_work = list(fb)
    free_bits_work = list(fbit)
    specs: List[CustomFlagSpec] = []

    print("\nDefine cada flag (tamaños válidos: bit | u8 | u16 | u32):")
    for i in range(n_new):
        next_id = st["get_count"] + i
        name = input(f"  [{i+1}/{n_new}] ID 0x{next_id:03X} - Nombre simbólico (Enter = Custom_0x{next_id:03X}): ").strip()
        if not name:
            name = f"Custom_0x{next_id:03X}"
        mode = input(f"  [{i+1}/{n_new}] ID 0x{next_id:03X} - Tamaño [bit / u8 / u16 / u32] (Enter = u8): ").strip().lower() or "u8"
        off, bit = allocate_from_free(free_bytes_work, free_bits_work, mode)
        specs.append(CustomFlagSpec(name=name, mode=mode, ctx_offset=off, bit_index=bit))
        print(f"      -> Asignado: {mode} en [ctx+0x350]+0x{off:04X}" + (f" bit {bit}" if mode == "bit" else ""))

    alloc_off, manifest = injector.inject(specs, fsf_start=fsf_start, safety_pad=0x40)

    base_name, ext = os.path.splitext(rom_in)
    rom_out = f"{base_name}_FlagsPlus{ext}"
    injector.save(rom_out)

    print(f"\n[OK] Bloque inyectado en ROM: 0x08{alloc_off:06X}")
    print(f"[OK] ROM generada: {rom_out}\n")
    print("ID Hex | ID Dec | Nombre             | Tipo | [ctx+0x350] | Rango/Bit | SRAM1  | EWRAM1")
    print("-" * 92)
    for m in manifest:
        print(
            f"{m['hex']}  | {m['id']:6d} | {m['name']:18s} | {m['mode']:4s} | "
            f"{m['ctx_off']:11s} | {m['bit']:9s} | {m['sram1']} | {m['ewram1']}"
        )


if __name__ == "__main__":
    main()