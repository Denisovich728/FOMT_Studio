# ============================================================
# FOMT Studio - Escáner Cross-ROM FoMT (A4NE) -> MFoMT (BFGE)
# Mapea automáticamente punteros, tablas, sprites, paletas,
# textos UI y fuente 1bpp desde FoMT hacia MFoMT.
# ============================================================
import os
import csv
import re
import struct
from typing import Dict, List, Optional, Tuple


def _read_cstr(rom: bytes, off: int, max_len: int = 128) -> bytes:
    if off < 0 or off >= len(rom):
        return b""
    end = rom.find(b"\x00", off, min(len(rom), off + max_len))
    if end == -1:
        return b""
    return rom[off:end]


def find_masked_signature(haystack: bytes, needle: bytes) -> int:
    """
    Busca `needle` en `haystack` ignorando los punteros GBA 0x08xxxxxx
    (bytes alineados a 4 cuyo byte alto es 0x08).
    """
    n = len(needle)
    if n < 12:
        return haystack.find(needle)

    # Identificar segmentos no-puntero para anclar busqueda rapida
    mask = [True] * n
    for i in range(0, n - 3, 4):
        val = struct.unpack_from("<I", needle, i)[0]
        if 0x08000000 <= val < 0x09000000:
            mask[i] = mask[i + 1] = mask[i + 2] = mask[i + 3] = False

    # Buscar bloque contiguo mas largo con mask=True
    best_s, best_l = 0, 0
    cur_s, cur_l = 0, 0
    for i, m in enumerate(mask):
        if m:
            if cur_l == 0:
                cur_s = i
            cur_l += 1
            if cur_l > best_l:
                best_s, best_l = cur_s, cur_l
        else:
            cur_l = 0

    if best_l < 6:
        return -1

    anchor = needle[best_s : best_s + best_l]
    pos = 0
    while True:
        idx = haystack.find(anchor, pos)
        if idx == -1:
            return -1
        cand = idx - best_s
        if cand >= 0 and cand + n <= len(haystack):
            ok = True
            for i in range(n):
                if mask[i]:
                    if haystack[cand + i] != needle[i]:
                        ok = False
                        break
                elif i % 4 == 3:
                    val = struct.unpack_from("<I", haystack, cand + i - 3)[0]
                    if not (0x08000000 <= val < 0x0A000000):
                        ok = False
                        break
            if ok:
                return cand
        pos = idx + 1


def find_all_4byte_refs(rom: bytes, target_off: int) -> List[int]:
    ptr_bytes = struct.pack("<I", 0x08000000 | target_off)
    refs = []
    pos = 0
    while True:
        idx = rom.find(ptr_bytes, pos)
        if idx == -1:
            break
        if idx % 4 == 0:
            refs.append(idx)
        pos = idx + 1
    return refs


def map_font_and_lut(fomt: bytes, mfomt: bytes) -> Dict[str, Optional[int]]:
    font_sig = fomt[0x4F90CC : 0x4F90CC + 128]
    m_font = mfomt.find(font_sig)
    lut_sig = fomt[0x4FA7A0 : 0x4FA7A0 + 256]
    m_lut = mfomt.find(lut_sig, m_font if m_font != -1 else 0)
    return {
        "FONT_1BYTE_BASE": m_font if m_font != -1 else None,
        "LUT_1BYTE_BASE": m_lut if m_lut != -1 else None,
    }


def map_sprite_csv(fomt: bytes, mfomt: bytes, src_csv: str, dst_csv: str) -> Tuple[int, int]:
    with open(src_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    out_rows = []
    matched = 0
    total = 0

    for r in rows:
        name = r.get("Nombre", "")
        off_hex = (r.get("Offset_LE") or "").replace(" ", "")
        pal_hex = (r.get("Paleta_LE") or "").replace(" ", "")
        if len(off_hex) != 8 or len(pal_hex) != 8:
            out_rows.append([name, r.get("Offset_LE", ""), r.get("Paleta_LE", "")])
            continue

        total += 1
        off = struct.unpack("<I", bytes.fromhex(off_hex))[0]
        pal = struct.unpack("<I", bytes.fromhex(pal_hex))[0]

        # Buscar sprite
        m_off = -1
        for sig_len in (64, 32, 16):
            if off + sig_len <= len(fomt):
                sig = fomt[off : off + sig_len]
                idx = mfomt.find(sig)
                if idx != -1:
                    m_off = idx
                    break
        if m_off == -1 and off + 32 <= len(fomt):
            m_off = find_masked_signature(mfomt, fomt[off : off + 32])

        # Buscar paleta (32 bytes = 16 colores)
        m_pal = -1
        if pal + 32 <= len(fomt):
            m_pal = mfomt.find(fomt[pal : pal + 32])
        if m_pal == -1 and pal + 16 <= len(fomt):
            m_pal = mfomt.find(fomt[pal : pal + 16])

        if m_off != -1 and m_pal != -1:
            matched += 1
            new_off_le = " ".join(f"{b:02X}" for b in struct.pack("<I", m_off))
            new_pal_le = " ".join(f"{b:02X}" for b in struct.pack("<I", m_pal))
            out_rows.append([name, new_off_le, new_pal_le])
        else:
            out_rows.append([name, r.get("Offset_LE", ""), r.get("Paleta_LE", "")])

    with open(dst_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Nombre", "Offset_LE", "Paleta_LE"])
        w.writerows(out_rows)

    return matched, total


def map_ui_text_pointers(fomt: bytes, mfomt: bytes, src_csv: str, dst_csv: str) -> Tuple[int, int]:
    """
    Mapea Fomt_Ui_text_pointers.csv encontrando el string apuntado en FoMT,
    buscandolo en MFoMT y resolviendo el puntero en la tabla correspondiente
    (usando contigüidad de tabla para desambiguar textos cortos como On/Off/1/2).
    """
    with open(src_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Pre-calcular candidatos de referencias en MFoMT para cada fila
    entries = []
    for r in rows:
        ptr_off = int(r["PointerOffset"], 16)
        ptr_val = struct.unpack_from("<I", fomt, ptr_off)[0]
        refs = []
        if 0x08000000 <= ptr_val < 0x09000000:
            str_off = ptr_val & 0x01FFFFFF
            cstr = _read_cstr(fomt, str_off)
            if len(cstr) >= 1:
                needle = cstr + b"\x00"
                pos = 0
                # Limitar a 30 apariciones del string para no explotar en "1"/"On"
                while len(refs) < 30:
                    idx = mfomt.find(needle, pos)
                    if idx == -1:
                        break
                    # Verificar inicio de string (byte anterior 0x00 o inicio)
                    if idx == 0 or mfomt[idx - 1] == 0x00:
                        refs.extend(find_all_4byte_refs(mfomt, idx))
                    pos = idx + 1
        entries.append((ptr_off, r["Label"], r["Category"], sorted(set(refs))))

    # Resolver usando delta local de filas vecinas contiguas
    resolved: Dict[int, int] = {}
    # Paso 1: filas con referencia unica
    for i, (poff, lbl, cat, refs) in enumerate(entries):
        if len(refs) == 1:
            resolved[i] = refs[0]

    # Paso 2: propagar por contigüidad (si ptr_off[i] - ptr_off[j] == 4, buscar ref[j] + 4 en refs[i])
    changed = True
    while changed:
        changed = False
        for i, (poff, lbl, cat, refs) in enumerate(entries):
            if i in resolved or not refs:
                continue
            for j, r_off in list(resolved.items()):
                diff = poff - entries[j][0]
                if -64 <= diff <= 64 and (r_off + diff) in refs:
                    resolved[i] = r_off + diff
                    changed = True
                    break

    out_rows = []
    for i, (poff, lbl, cat, refs) in enumerate(entries):
        if i in resolved:
            out_rows.append([f"0x{resolved[i]:X}", lbl, cat])
        elif refs:
            out_rows.append([f"0x{refs[0]:X}", lbl, cat])
        else:
            out_rows.append([f"0x{poff:X}", lbl, cat])

    with open(dst_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["PointerOffset", "Label", "Category"])
        w.writerows(out_rows)

    return len(resolved), len(entries)


def map_extraction_pointers(fomt: bytes, mfomt: bytes, src_csv: str, dst_csv: str) -> Dict[str, Tuple[int, int]]:
    """
    Mapea las tablas maestras de Fomt_Punteros de extraccion.csv hacia MFoMT:
      - PunterosScript (tabla maestra de eventos)
      - npcs (tabla de NPCs)
      - Herramientas, Comestibles, Variados (buscando punteros a nombres de items)
    """
    results: Dict[str, Tuple[int, int]] = {}

    # 1. PunterosScript: detectar secuencia larga de punteros 0x08xxxxxx a 'RIFF'
    ev_start, best_cnt = 0, 0
    i = 0x080000
    while i < min(len(mfomt), 0x250000):
        cnt = 0
        j = i
        while j + 4 <= len(mfomt):
            pv = struct.unpack_from("<I", mfomt, j)[0]
            if 0x08000000 <= pv < 0x09000000:
                off = pv & 0x01FFFFFF
                if off + 4 <= len(mfomt) and mfomt[off : off + 4] == b"RIFF":
                    cnt += 1
                    j += 4
                    continue
            break
        if cnt > best_cnt:
            best_cnt = cnt
            ev_start = i
        i = (j + 4) if cnt > 0 else (i + 4)
    if best_cnt >= 500:
        results["PunterosScript"] = (ev_start, ev_start + best_cnt * 4 - 1)

    # 2. npcs: stride 8 bytes, bytes 4..8 son flags
    npc_orig = 0x104260
    npc_pat0 = fomt[npc_orig + 4 : npc_orig + 8]
    pos = 0
    npc_start = -1
    while True:
        idx = mfomt.find(npc_pat0, pos)
        if idx == -1:
            break
        cand = idx - 4
        if all(mfomt[cand + k * 8 + 4 : cand + k * 8 + 8] == fomt[npc_orig + k * 8 + 4 : npc_orig + k * 8 + 8] for k in range(1, 6)):
            npc_start = cand
            break
        pos = idx + 1
    if npc_start != -1:
        results["npcs"] = (npc_start, npc_start + (0x1043AF - 0x104260))

    # 3. Herramientas, Comestibles, Variados: buscar por nombre de item ancla o firma con mascara
    anchor_items = {
        "Herramientas": (b"Iron Sickle\x00", 0),
        "Comestibles": (b"Turnip\x00", 0),
        "Variados": (b"Toy Flower\x00", -48),  # Toy Flower es entrada #4 (4 * 12 = 48 bytes despues del inicio)
    }
    with open(src_csv, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            t = row["type"]
            if t in ("Herramientas", "Comestibles", "Variados"):
                ini = int(row["ofsetini"], 16)
                fin = int(row["ofsetfin"], 16)
                size = fin - ini
                m_ini = -1
                if t in anchor_items:
                    needle, delta_off = anchor_items[t]
                    str_off = mfomt.find(needle)
                    if str_off != -1:
                        refs = find_all_4byte_refs(mfomt, str_off)
                        if refs:
                            m_ini = refs[0] + delta_off
                if m_ini == -1:
                    m_ini = find_masked_signature(mfomt, fomt[ini : ini + 64])
                if m_ini != -1:
                    results[t] = (m_ini, m_ini + size)

    with open(dst_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["type", "ofsetini", "ofsetfin"])
        for t in ("PunterosScript", "npcs", "Herramientas", "Comestibles", "Variados"):
            if t in results:
                s, e = results[t]
                w.writerow([t, f"0x{s:06X}", f"0x{e:06X}"])

    return results


def map_out_of_event_strings(
    fomt: bytes,
    mfomt: bytes,
    src_csv: str,
    dst_csv: str,
    ev_table_start: int = 0x1014C0,
    ev_table_end: int = 0x102ADB,
) -> Tuple[int, int]:
    """
    Mapea strings_fuera_de_eventos.csv de FoMT hacia MFoMT omitiendo
    la tabla de eventos y bloques RIFF de eventos para evitar cruces.
    """
    if not os.path.isfile(src_csv):
        return 0, 0

    # Construir rangos de bloques RIFF de eventos en MFoMT para excluirlos
    ev_ranges: List[Tuple[int, int]] = [(ev_table_start, ev_table_end + 1)]
    for p in range(ev_table_start, ev_table_end + 1, 4):
        pv = struct.unpack_from("<I", mfomt, p)[0]
        if 0x08000000 <= pv < 0x09000000:
            off = pv & 0x01FFFFFF
            if off + 8 <= len(mfomt) and mfomt[off : off + 4] == b"RIFF":
                rlen = struct.unpack_from("<I", mfomt, off + 4)[0]
                ev_ranges.append((off, off + 8 + rlen))

    def _in_event(pos: int) -> bool:
        for s, e in ev_ranges:
            if s <= pos < e:
                return True
        return False

    with open(src_csv, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    out_rows = []
    matched = 0
    for r in rows:
        f_off = int(r["offset_string"], 16)
        f_end = int(r["offset_fin"], 16)
        raw_bytes = fomt[f_off:f_end] + b"\x00"
        m_off = -1
        m_ptr = ""

        # Buscar fuera de bloques de eventos
        pos = 0
        candidates = []
        while len(candidates) < 20:
            idx = mfomt.find(raw_bytes, pos)
            if idx == -1:
                break
            if (idx == 0 or mfomt[idx - 1] == 0x00) and not _in_event(idx):
                candidates.append(idx)
            pos = idx + 1

        if len(candidates) == 1:
            m_off = candidates[0]
            refs = [ref for ref in find_all_4byte_refs(mfomt, m_off) if not _in_event(ref)]
            if refs:
                m_ptr = f"0x{refs[0]:x}"
        elif candidates:
            # Preferir candidato con referencia 4-byte fuera de eventos
            for c in candidates:
                refs = [ref for ref in find_all_4byte_refs(mfomt, c) if not _in_event(ref)]
                if refs:
                    m_off = c
                    m_ptr = f"0x{refs[0]:x}"
                    break
            if m_off == -1:
                m_off = candidates[0]

        if m_off != -1:
            matched += 1
            m_end = m_off + (f_end - f_off)
            out_rows.append([
                f"0x{m_off:x}",
                f"0x{m_end:x}",
                r["longitud"],
                r["n_punteros"],
                m_ptr or r["primer_puntero_en"],
                r["confianza"],
                r["texto"],
            ])

    with open(dst_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["offset_string", "offset_fin", "longitud", "n_punteros", "primer_puntero_en", "confianza", "texto"])
        w.writerows(out_rows)

    return matched, len(rows)


def run_full_scan_and_export(fomt_path: str, mfomt_path: str, cilixes_dir: str) -> Dict[str, object]:
    with open(fomt_path, "rb") as f:
        fomt = f.read()
    with open(mfomt_path, "rb") as f:
        mfomt = f.read()

    fomt_dir = os.path.join(cilixes_dir, "fomt")
    mfomt_dir = os.path.join(cilixes_dir, "Mfomt")
    os.makedirs(mfomt_dir, exist_ok=True)

    report: Dict[str, object] = {}
    report["font"] = map_font_and_lut(fomt, mfomt)

    sp_m, sp_t = map_sprite_csv(
        fomt, mfomt,
        os.path.join(fomt_dir, "Fomt_Sprite_data.csv"),
        os.path.join(mfomt_dir, "MFomt_Sprite_data.csv"),
    )
    report["sprites"] = f"{sp_m}/{sp_t}"

    ui_m, ui_t = map_ui_text_pointers(
        fomt, mfomt,
        os.path.join(fomt_dir, "Fomt_Ui_text_pointers.csv"),
        os.path.join(mfomt_dir, "MFomt_Ui_text_pointers.csv"),
    )
    report["ui_text"] = f"{ui_m}/{ui_t}"

    ext = map_extraction_pointers(
        fomt, mfomt,
        os.path.join(fomt_dir, "Fomt_Punteros de extraccion.csv"),
        os.path.join(mfomt_dir, "MFomt_Punteros de extraccion.csv"),
    )
    report["extraction_tables"] = {k: (hex(v[0]), hex(v[1])) for k, v in ext.items()}

    ev_s, ev_e = ext.get("PunterosScript", (0x1014C0, 0x102ADB))
    root_dir = os.path.dirname(os.path.dirname(cilixes_dir))
    str_csv = os.path.join(root_dir, "strings_fuera_de_eventos.csv")
    if os.path.isfile(str_csv):
        s_m, s_t = map_out_of_event_strings(
            fomt, mfomt, str_csv,
            os.path.join(mfomt_dir, "MFomt_strings_fuera_de_eventos.csv"),
            ev_table_start=ev_s, ev_table_end=ev_e,
        )
        report["out_of_event_strings"] = f"{s_m}/{s_t}"

    # Copiar CSVs simbolicos compartidos (Portraits, Mapas, Flags, Emotes, Animations) si no existen
    import shutil
    shared_csvs = [
        ("Fomt_Portraits.csv", "MFomt_Portraits.csv"),
        ("Fomt_Mapas.csv", "MFomt_Mapas.csv"),
        ("Fomt_Flags.csv", "MFomt_Flags.csv"),
        ("Fomt_Emotes.csv", "MFomt_Emotes.csv"),
        ("Fomt_Animations.csv", "MFomt_Animations.csv"),
        ("Fomt_Animations_Base.csv", "MFomt_Animations_Base.csv"),
    ]
    copied = []
    for src_name, dst_name in shared_csvs:
        src_p = os.path.join(fomt_dir, src_name)
        dst_p = os.path.join(mfomt_dir, dst_name)
        if os.path.isfile(src_p) and not os.path.isfile(dst_p):
            shutil.copy2(src_p, dst_p)
            copied.append(dst_name)
    report["copied_symbolic_csvs"] = copied
    return report


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fomt_rom = r"J:\Laboratorio\Repositorios\fomt virgen.gba"
    mfomt_rom = r"J:\Laboratorio\Repositorios\MFOMT VIRGEN.gba"
    cilixes = os.path.join(root, "Banco_de_Datos", "Cilixes")
    rep = run_full_scan_and_export(fomt_rom, mfomt_rom, cilixes)
    for k, v in rep.items():
        print(f"{k}: {v}")

