# ============================================================
# FOMT Studio - Suite de Ingenieria Inversa
# Inyector Masivo de Textos ESP y Reempaquetador de Eventos
# Desarrollado por: Denisovich728
# ============================================================
import os
import re
import sys
import struct
from typing import Dict, List, Tuple, Optional

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from Banco_de_Datos.parche_n import aplicar_parche_n
from Nucleos_Positronicos.Nucleo_de_Scripts.SlipSpace_Script_Engine.bytecode.decoder import decode_script
from Nucleos_Positronicos.Nucleo_de_Scripts.SlipSpace_Script_Engine.bytecode.encoder import encode_script
from Nucleos_Positronicos.Nucleo_de_Scripts.SlipSpace_Script_Engine.compiler.lexer import Lexer, TokenType


# Regex para extraer const MESSAGE_X = "..."; de los txt antiguos
_CONST_MSG_RE = re.compile(r'const\s+MESSAGE_(\d+)\s*=\s*"(.*)"\s*;', re.MULTILINE)

# Tokens indivisibles dentro de los strings de FoMT
_TOKEN_RE = re.compile(
    r'(\\xFF.|\\x[0-9A-Fa-f]{2}|\{[A-Z0-9_]+\}|\\"|\\\\|\\[nrbwt])'
)

# Ancho visual estimado (en caracteres) para tags dinamicos de RAM
_TAG_WIDTHS = {
    "{PLAYER}": 12,
    "{HORSE}": 12,
    "{VALUE1}": 12,
    "{VALUE2}": 12,
    "{VALUE4}": 12,
    "{VALUE8}": 12,
    "{VALUE9}": 12,
    "{BREAK}": 0,
    "{BREAK2}": 0,
}


def _token_visual_width(tok: str) -> int:
    if tok in _TAG_WIDTHS:
        return _TAG_WIDTHS[tok]
    if tok.startswith(r"\xFF"):
        # \xFF! (nombre jugador), \xFF% (animal), \xFF) etc.: reservar 12 chars
        return 12
    if tok.startswith(r"\x"):
        return 1
    if tok in (r'\"', r"\\"):
        return 1
    if tok in (r"\n", r"\r", r"\b", r"\w"):
        return 0
    if tok == r"\t":
        return 4
    return len(tok)


def _split_atomic_words(text: str) -> List[str]:
    """
    Divide un parrafo en palabras sin partir escapes (\xFF!, {VALUE9}, \", etc.).
    """
    # Primero colapsar espacios/saltos en espacios simples preservando escapes
    cleaned = text.replace("\\r\\n", " ").replace("\\n", " ").replace("\\r", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return []

    words: List[str] = []
    for raw_word in cleaned.split(" "):
        if raw_word:
            words.append(raw_word)
    return words


def _word_visual_width(word: str) -> int:
    width = 0
    pos = 0
    for m in _TOKEN_RE.finditer(word):
        if m.start() > pos:
            width += m.start() - pos
        width += _token_visual_width(m.group(0))
        pos = m.end()
    if pos < len(word):
        width += len(word) - pos
    return width


def wrap_fomt_message(raw_msg_str: str, max_line_len: int = 28, lines_per_box: int = 3) -> str:
    r"""
    Normaliza un mensaje antiguo de scripts (esp) a la sintaxis actual de
    SlipSpace_Script_Engine (\n, \b, \w, \xFF., {VALUE9}, etc.):
      - Emite \n cada <= max_line_len caracteres sin cortar palabras.
      - Cada lines_per_box (3) lineas emite \b\w si el texto continua.
      - Conserva \b al final si el mensaje original terminaba en \BRK / \b.
    """
    if not raw_msg_str:
        return raw_msg_str

    # Normalizar marcadores viejos a \b y \w
    s = raw_msg_str
    s = s.replace(r"\BRK\WAIT_CLICK", r"\b\w")
    s = s.replace(r"\BRK\WAIT CLICK", r"\b\w")
    s = s.replace(r"\BRK", r"\b")
    s = s.replace(r"\WAIT_CLICK", r"\w")
    s = s.replace(r"\WAIT CLICK", r"\w")
    s = s.replace(r"\r\n", r"\n")

    # Detectar si el mensaje termina en \b (o \b con espacios)
    s_rstrip = s.rstrip()
    ends_with_brk = s_rstrip.endswith(r"\b")
    if ends_with_brk:
        s_rstrip = s_rstrip[:-2].rstrip()

    # Separar por cajas explicitas (\b\w o \w)
    explicit_boxes = re.split(r"(?:\\b)?\\w", s_rstrip)

    formatted_boxes: List[str] = []
    for box in explicit_boxes:
        # Limpiar \b sueltos dentro de la caja (los \b viejos de salto cada 3 lineas)
        box_clean = box.replace(r"\b", " ")
        words = _split_atomic_words(box_clean)
        if not words:
            continue

        lines: List[str] = []
        current_line: List[str] = []
        current_width = 0

        for w in words:
            w_width = _word_visual_width(w)
            if not current_line:
                current_line.append(w)
                current_width = w_width
            elif current_width + 1 + w_width <= max_line_len:
                current_line.append(w)
                current_width += 1 + w_width
            else:
                lines.append(" ".join(current_line))
                current_line = [w]
                current_width = w_width

        if current_line:
            lines.append(" ".join(current_line))

        # Agrupar cada 3 lineas en sub-cajas unidas por \b\w
        sub_boxes: List[str] = []
        for i in range(0, len(lines), lines_per_box):
            chunk = lines[i : i + lines_per_box]
            sub_boxes.append(r"\n".join(chunk))

        formatted_boxes.append(r"\b\w".join(sub_boxes))

    result = r"\b\w".join(formatted_boxes)
    if ends_with_brk and result:
        result += r"\b"
    return result


def compile_message_bytes(formatted_msg: str) -> bytes:
    r"""
    Compila el string formateado usando el Lexer oficial de SlipSpace_Script_Engine
    para aplicar CHARMAP_ES (\xC4..\xDD, \xAD..\xAE), \n (0D 0A), \b (05), \w (0C),
    \xFF. y tags {PLAYER}/{VALUE9}.
    """
    lx = Lexer('"' + formatted_msg + '"')
    tok = lx.next_token()
    if tok.type != TokenType.STRING_LIT:
        raise ValueError(f"Expected STRING_LIT, got {tok.type}")
    return tok.value


def parse_esp_script_messages(txt_path: str) -> Dict[int, str]:
    """Extrae el diccionario {msg_idx: raw_msg_str} de un archivo de scripts (esp)."""
    with open(txt_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    msgs: Dict[int, str] = {}
    for m in _CONST_MSG_RE.finditer(content):
        msgs[int(m.group(1))] = m.group(2)
    return msgs


def _merge_intervals(intervals: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    if not intervals:
        return []
    sorted_iv = sorted(intervals)
    merged: List[Tuple[int, int]] = [sorted_iv[0]]
    for start, end in sorted_iv[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def _scan_large_ff_regions(rom: bytearray, min_start: int = 0x75C254, min_size: int = 64) -> List[Tuple[int, int]]:
    """Escanea regiones contiguas de 0xFF desde min_start hasta el final de la ROM."""
    regions: List[Tuple[int, int]] = []
    n = len(rom)
    i = min_start
    while i < n:
        if rom[i] == 0xFF:
            start = i
            while i < n and rom[i] == 0xFF:
                i += 1
            if i - start >= min_size:
                regions.append((start, i))
        else:
            i += 1
    return regions


# Regiones protegidas que NUNCA deben ser wipeadas ni sobrescritas por eventos
# (ej. Event 1328 solapa sus ultimos 8 bytes de ceros con el glifo 0x20 en 0x4F90CC)
_PROTECTED_RANGES: List[Tuple[int, int]] = [
    (0x4F90CC, 0x4FB000),  # Fuente 1bpp + LUT
    (0x0E89E0, 0x0E8A00),  # Teclado Naming Screen
    (0x117B40, 0x117B60),  # Iconos ñ/Ñ Naming Screen
    (0x13AA20, 0x13AA40),  # Firmas N_MODE / CILIXES
    (0x75A5A0, 0x75C600),  # HUD/Dias + Splash
]


def _subtract_protected(intervals: List[Tuple[int, int]], protected: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    result = list(intervals)
    for p_start, p_end in protected:
        next_res: List[Tuple[int, int]] = []
        for s, e in result:
            if e <= p_start or s >= p_end:
                next_res.append((s, e))
            else:
                if s < p_start:
                    next_res.append((s, p_start))
                if e > p_end:
                    next_res.append((p_end, e))
        result = next_res
    return result


def inject_esp_scripts_and_repack(
    project,
    esp_dir: str,
    apply_n_patch: bool = True,
    max_line_len: int = 28,
    lines_per_box: int = 3,
    wipe_existing_events: bool = True,
) -> Dict[str, object]:
    r"""
    Flujo completo:
      1. Parchea la ROM con el parche de la Ñ (aplicar_parche_n).
      2. Lee todos los eventos RIFF de la ROM y sus traducciones en esp_dir.
      3. Reformatea cada const MESSAGE_X (<=28 chars/linea, \b\w cada 3 lineas),
         reemplaza los strings en el script decodificado y re-codifica el RIFF.
      4. Hace wipe (0xFF) de los bloques originales de eventos en virtual_rom.
      5. Ordena los eventos compilados del mas grande al mas chico y los acomoda
         en todos los espacios libres 0xFF (incluidos los del wipeo), repunteando
         la tabla maestra de eventos.
    """
    table_off = project.super_lib.table_offset
    event_limit = project.super_lib.event_limit
    rom = project.virtual_rom

    # 1. Leer todos los eventos y detectar punteros unicos (o compartidos)
    # off -> list of event_ids
    off_to_eids: Dict[int, List[int]] = {}
    orig_blocks: List[Tuple[int, int]] = []

    for eid in range(1, event_limit + 1):
        ptr_off = table_off + ((eid - 1) * 4)
        ptr_val = struct.unpack_from("<I", rom, ptr_off)[0]
        if ptr_val < 0x08000000 or ptr_val >= 0x09000000:
            continue
        off = ptr_val & 0x01FFFFFF
        if off + 8 > len(rom) or rom[off : off + 4] != b"RIFF":
            if off + 4 <= len(rom) and rom[off : off + 4] == b"\xFF\xFF\xFF\xFF":
                # Evento vacio original (ej. Event 355): anular puntero para no apuntar dentro de otro evento reempaquetado
                struct.pack_into("<I", rom, ptr_off, 0)
            continue
        off_to_eids.setdefault(off, []).append(eid)

    # 2. Procesar cada evento unico: decodificar, formatear e inyectar strings ESP, re-codificar
    compiled_items: List[Tuple[int, List[int], bytes]] = []  # (orig_off, [eids], new_riff_bytes)
    total_orig_bytes = 0
    total_new_bytes = 0
    translated_msgs_count = 0
    events_updated = 0

    for orig_off, eids in off_to_eids.items():
        riff_len = struct.unpack_from("<I", rom, orig_off + 4)[0]
        total_len = riff_len + 8
        raw_orig = bytes(rom[orig_off : orig_off + total_len])
        total_orig_bytes += total_len

        # Incluir cualquier padding 0xFF inmediato posterior del evento original
        pad_end = orig_off + total_len
        while pad_end < len(rom) and rom[pad_end] == 0xFF:
            pad_end += 1
        orig_blocks.append((orig_off, pad_end))

        scr = decode_script(raw_orig)

        # Usar el primer event_id asociado para buscar su .txt en esp_dir
        # (si hubiese varios, buscar el primero que tenga archivo)
        esp_msgs: Dict[int, str] = {}
        for eid in eids:
            cand = os.path.join(esp_dir, f"evento_{eid:04d}.txt")
            if os.path.isfile(cand):
                esp_msgs = parse_esp_script_messages(cand)
                if esp_msgs:
                    break

        if esp_msgs:
            events_updated += 1
            for idx, raw_s in esp_msgs.items():
                if 0 <= idx < len(scr.strings):
                    wrapped = wrap_fomt_message(raw_s, max_line_len=max_line_len, lines_per_box=lines_per_box)
                    scr.strings[idx] = compile_message_bytes(wrapped)
                    translated_msgs_count += 1

        new_bin = encode_script(scr, target_size=0)
        total_new_bytes += len(new_bin)
        compiled_items.append((orig_off, eids, new_bin))

    # 3. Excluir regiones protegidas (fuente, LUT, HUD, etc.) y wipear bloques originales
    safe_blocks = _subtract_protected(_merge_intervals(orig_blocks), _PROTECTED_RANGES)
    if wipe_existing_events:
        for b_start, b_end in safe_blocks:
            rom[b_start:b_end] = b"\xFF" * (b_end - b_start)

    # 4. Construir mapa de huecos libres 0xFF (bloques wipeados + cola libre >= 0x75C600)
    free_regions = list(safe_blocks)
    free_regions.extend(_scan_large_ff_regions(rom, min_start=0x75C600, min_size=64))
    free_regions = _subtract_protected(_merge_intervals(free_regions), _PROTECTED_RANGES)

    # Convertir a lista mutable de huecos alineados a 4 bytes: [[aligned_start, end], ...]
    free_slots: List[List[int]] = []
    for s, e in free_regions:
        aligned_s = (s + 3) & ~3
        if aligned_s < e:
            free_slots.append([aligned_s, e])

    # 5. Ordenar eventos del mas grande al mas chico (First-Fit Decreasing)
    compiled_items.sort(key=lambda item: len(item[2]), reverse=True)

    repacked_in_wiped = 0
    repacked_in_tail = 0
    appended_end = 0

    for _, eids, new_bin in compiled_items:
        needed = len(new_bin)
        aligned_needed = (needed + 3) & ~3
        placed_off: Optional[int] = None

        for slot in free_slots:
            s_start, s_end = slot
            if s_end - s_start >= needed:
                placed_off = s_start
                next_s = (s_start + aligned_needed + 3) & ~3
                slot[0] = min(next_s, s_end)
                break

        if placed_off is None:
            # Si no cupo en ningun hueco existente, extender la ROM al final (alineado a 4 bytes)
            cur_len = len(rom)
            placed_off = (cur_len + 3) & ~3
            if placed_off > cur_len:
                rom.extend(b"\xFF" * (placed_off - cur_len))
            rom.extend(b"\xFF" * aligned_needed)
            appended_end += 1
        elif placed_off >= 0x75C254:
            repacked_in_tail += 1
        else:
            repacked_in_wiped += 1

        # Escribir el evento compilado y actualizar todos los punteros que apuntaban a el
        rom[placed_off : placed_off + needed] = new_bin
        ptr_val = 0x08000000 | placed_off
        for eid in eids:
            ptr_off = table_off + ((eid - 1) * 4)
            struct.pack_into("<I", rom, ptr_off, ptr_val)

    # Sincronizar base_rom_data si existe
    if hasattr(project, "base_rom_data") and project.base_rom_data is not None:
        project.base_rom_data = bytes(rom)

    # 6. Aplicar parche de la Ñ al final para garantizar fuente, teclado y HUD intactos
    if apply_n_patch:
        aplicar_parche_n(project)
        if hasattr(project, "base_rom_data") and project.base_rom_data is not None:
            project.base_rom_data = bytes(project.virtual_rom)

    return {
        "events_total": len(compiled_items),
        "events_updated": events_updated,
        "messages_translated": translated_msgs_count,
        "total_orig_bytes": total_orig_bytes,
        "total_new_bytes": total_new_bytes,
        "repacked_in_wiped": repacked_in_wiped,
        "repacked_in_tail": repacked_in_tail,
        "appended_end": appended_end,
        "final_rom_size": len(rom),
    }


if __name__ == "__main__":
    import argparse
    import sys

    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

    from Banco_de_Datos.proyecto import FoMTProject

    parser = argparse.ArgumentParser(description="Inyector de textos ESP y reempaquetador de eventos FoMT")
    parser.add_argument("target", help="Ruta al archivo .fsp o .gba")
    parser.add_argument(
        "--esp-dir",
        default=os.path.join(root_dir, "scripts (esp)", "scripts (esp)"),
        help="Carpeta con los evento_XXXX.txt traducidos",
    )
    parser.add_argument("--out-gba", help="Ruta opcional para exportar la ROM .gba resultante")
    parser.add_argument("--no-n-patch", action="store_true", help="Omitir aplicacion del parche de la Ñ")
    args = parser.parse_args()

    proj = FoMTProject()
    if args.target.lower().endswith(".fsp"):
        proj.load(args.target)
    else:
        proj.open_rom_session(args.target)
    proj.step_2_scan_events()

    res = inject_esp_scripts_and_repack(
        proj,
        args.esp_dir,
        apply_n_patch=not args.no_n_patch,
    )
    for k, v in res.items():
        print(f"{k}: {v}")

    if args.out_gba:
        with open(args.out_gba, "wb") as f_out:
            f_out.write(proj.virtual_rom)
        print(f"ROM exportada en: {args.out_gba}")

