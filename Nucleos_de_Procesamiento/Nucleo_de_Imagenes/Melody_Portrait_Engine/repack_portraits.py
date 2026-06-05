import struct
import os
import sys
import shutil
from PIL import Image

sys.path.append(r'j:\Repositorios\fomt_studio')
from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.Melody_Portrait_Engine.engine import MelodyPortraitEngine

ROM_PATH     = r"j:\Repositorios\fomt_studio\Harvest Moon - Friends of Mineral Town.gba"
OUT_ROM_PATH = r"j:\Repositorios\fomt_studio\Harvest Moon - Friends of Mineral Town_Repacked.gba"

# ─────────────────────────────────────────────────────────────────────────────
# ROM helpers
# ─────────────────────────────────────────────────────────────────────────────

def read_hword(rom, addr):
    return struct.unpack('<H', rom[addr:addr+2])[0]

def read_word(rom, addr):
    return struct.unpack('<I', rom[addr:addr+4])[0]

def write_hword(rom, addr, val):
    struct.pack_into('<H', rom, addr, val)

def write_word(rom, addr, val):
    struct.pack_into('<I', rom, addr, val)


# ─────────────────────────────────────────────────────────────────────────────
# Cargar tablas maestras (auto-detecta ROM vanilla o expandida)
# ─────────────────────────────────────────────────────────────────────────────

def _load_tables(rom):
    """
    Lee el bloque maestro de datos de portraits desde la ROM.
    Soporta ROM nativa (0x0852D984) y ROMs ya expandidas (0x007D0000).
    Devuelve (counts, ptrs, tables, header_addr, is_buggy_payload).
    tables = [t1, t2, t3, t4, t5, t6, t7]
    """
    header_addr = struct.unpack('<I', rom[0xadc7c:0xadc7c+4])[0] - 0x08000000
    counts = []
    ptrs   = []
    r1     = header_addr

    # --- Auto-Recovery de payload corrupto anterior ---
    is_buggy_payload = False
    if header_addr == 0x007D0000:
        first_val = struct.unpack('<I', rom[header_addr:header_addr+4])[0]
        if first_val == 0x00000001 or first_val == 0x00010001:
            is_buggy_payload = True
            print("DETECTADO PAYLOAD CORRUPTO ANTERIOR! Iniciando auto-recuperación...")
            buggy_counts_addr = 0x0852D984 - 0x08000000
            for _ in range(5):
                counts.append(struct.unpack('<H', rom[buggy_counts_addr:buggy_counts_addr+2])[0])
                buggy_counts_addr += 8
            counts.append(0)  # Table 6 count
            curr_data_ptr = header_addr
            for i, shift in enumerate([2, 4, 3, 5, 5, 3]):
                ptrs.append(curr_data_ptr)
                curr_data_ptr += counts[i] * (1 << shift)

    if not is_buggy_payload:
        for shift in [2, 4, 3, 5, 5, 3, 2]:
            cnt = struct.unpack('<I', rom[r1:r1+4])[0]
            counts.append(cnt)
            r1 += 4
            ptrs.append(r1)
            r1 += cnt * (1 << shift)

    t1 = bytearray(rom[ptrs[0]:ptrs[0] + counts[0] * 4])
    t2 = bytearray(rom[ptrs[1]:ptrs[1] + counts[1] * 16])
    t3 = bytearray(rom[ptrs[2]:ptrs[2] + counts[2] * 8])
    t4 = bytearray(rom[ptrs[3]:ptrs[3] + counts[3] * 32])
    t5 = bytearray(rom[ptrs[4]:ptrs[4] + counts[4] * 32])

    if is_buggy_payload:
        t6_addr      = 0x0858b720 - 0x08000000
        t6_cnt       = struct.unpack('<I', rom[t6_addr:t6_addr+4])[0]
        t6           = bytearray(rom[t6_addr+4:t6_addr+4 + t6_cnt * 8])
        t7_addr      = t6_addr + 4 + t6_cnt * 8
        t7_cnt       = struct.unpack('<I', rom[t7_addr:t7_addr+4])[0]
        t7           = bytearray(rom[t7_addr+4:t7_addr+4 + t7_cnt * 4])
        counts[5]    = t6_cnt
        counts.append(t7_cnt)
    else:
        t6 = bytearray(rom[ptrs[5]:ptrs[5] + counts[5] * 8])
        t7 = bytearray(rom[ptrs[6]:ptrs[6] + counts[6] * 4])

    return counts, ptrs, [t1, t2, t3, t4, t5, t6, t7], header_addr, is_buggy_payload


def _flush_tables(rom, tables, counts, save_path=None):
    """
    Escribe las tablas en el espacio libre 0x007D0000 y parchea los 3 punteros ASM.

    El payload incluye T4 completa (tiles vanilla ~362KB + nuevos), por lo que
    la ROM se extiende mas alla de los 8MB originales cuando hay portraits expandidos.
    Esto es normal — el bytearray crece segun sea necesario.

    Emite advertencia solo si metadata+tiles_nuevos supera el 80%% de los 192KB
    del espacio 0x7D0000-0x800000 (como referencia para el usuario).
    """
    NEW_BASE    = 0x007D0000
    REF_SPACE   = 0x800000 - NEW_BASE   # 196,608 bytes de referencia
    WARN_THRESH = int(REF_SPACE * 0.80)

    payload = bytearray()
    for i, t_data in enumerate(tables):
        payload += struct.pack('<I', counts[i])
        payload += t_data

    # Advertencia basada solo en metadata + tiles nuevos (excluye T4 vanilla)
    vanilla_t4_count = _get_vanilla_t4_count(rom)
    t4_new_bytes     = max(0, len(tables[3]) - vanilla_t4_count * 32)
    meta_sz = sum(4 + len(t) for i, t in enumerate(tables) if i != 3) + 4 + t4_new_bytes
    if meta_sz > WARN_THRESH:
        pct = meta_sz / REF_SPACE * 100
        print(f"[WARNING] Metadata+tiles_nuevos: {meta_sz:,}B ({pct:.0f}%% de {REF_SPACE:,}B). "
              f"Considera resetear la ROM base pronto.")

    # Extender el bytearray si el payload supera el tamano actual de la ROM
    needed = NEW_BASE + len(payload)
    if needed > len(rom):
        rom += bytearray(needed - len(rom))

    rom[NEW_BASE:NEW_BASE + len(payload)] = payload

    ptr_bytes = struct.pack('<I', NEW_BASE + 0x08000000)
    rom[0xadc7c:0xadc7c+4] = ptr_bytes
    rom[0xadd00:0xadd00+4] = ptr_bytes
    rom[0xadd3c:0xadd3c+4] = ptr_bytes

    if save_path:
        with open(save_path, 'wb') as f:
            f.write(rom)
        print(f"ROM guardada en {save_path} ({len(rom):,} bytes)")


# ─────────────────────────────────────────────────────────────────────────────────
# _get_vanilla_t4_count — detecta dinámicamente el count de T4 en la ROM vanilla
# ─────────────────────────────────────────────────────────────────────────────────

def _get_vanilla_t4_count(rom):
    """
    Lee el count de T4 (GFX tiles) desde la posicion VANILLA fija 0x0852D984,
    que siempre esta presente en la ROM independientemente de si ya fue expandida.
    Esto permite detectar si f6 de un portrait esta en la zona expandida (> vanilla count).
    """
    VANILLA_HEADER = 0x0852D984 - 0x08000000
    r1 = VANILLA_HEADER
    for shift in [2, 4, 3]:   # T1, T2, T3
        cnt = struct.unpack('<I', rom[r1:r1+4])[0]
        r1 += 4 + cnt * (1 << shift)
    # Ahora r1 apunta al count de T4
    return struct.unpack('<I', rom[r1:r1+4])[0]


# ─────────────────────────────────────────────────────────────────────────────────
# _validate_tables — Table Integrity Guard
# Verifica que ningún índice de T2 apunte fuera de rango en T3/T4/T5
# y que el payload no desborde el espacio en 0x007D0000.
# ─────────────────────────────────────────────────────────────────────────────────

def _validate_tables(tables, counts):
    """
    Table Integrity Guard: verifica la coherencia de todas las tablas antes
    de hacer el flush a la ROM. Lanza AssertionError si detecta algun problema.

    No valida el tamaño absoluto del payload (T4 es grande y se acepta que
    la ROM pueda crecer). Solo valida coherencia de indices entre tablas.
    """
    t1, t2, t3, t4, t5, t6, t7 = tables

    # 1. Coherencia de longitudes de tablas vs counts
    assert len(t3) == counts[2] * 8,  f"[INTEGRITY] T3 size mismatch: {len(t3)} != {counts[2]*8}"
    assert len(t4) == counts[3] * 32, f"[INTEGRITY] T4 size mismatch: {len(t4)} != {counts[3]*32}"
    assert len(t5) == counts[4] * 32, f"[INTEGRITY] T5 size mismatch: {len(t5)} != {counts[4]*32}"

    # 2. T2: todos los indices apuntan a rangos validos en T3, T4, T5
    for iidx in range(counts[1]):
        base = iidx * 16
        if base + 16 > len(t2):
            break
        f0_v = read_hword(t2, base)
        f2_v = read_hword(t2, base + 2)
        f4_v = read_hword(t2, base + 4)
        f6_v = read_hword(t2, base + 6)
        fA_v = read_hword(t2, base + 10)

        assert f2_v + f0_v <= counts[2], (
            f"[INTEGRITY] T2[{iidx}] OAM fuera de T3: "
            f"f2={f2_v}+f0={f0_v}={f2_v+f0_v} > count={counts[2]}"
        )
        assert f6_v + f4_v <= counts[3], (
            f"[INTEGRITY] T2[{iidx}] GFX fuera de T4: "
            f"f6={f6_v}+f4={f4_v}={f6_v+f4_v} > count={counts[3]}"
        )
        assert fA_v < counts[4], (
            f"[INTEGRITY] T2[{iidx}] Paleta fuera de T5: "
            f"fA={fA_v} >= count={counts[4]}"
        )

    payload_sz = sum(4 + len(t) for t in tables)
    print(f"[Integrity] OK — {counts[2]} OAMs / {counts[3]} tiles / {counts[4]} paletas. "
          f"Payload total: {payload_sz:,}B")


# ─────────────────────────────────────────────────────────────────────────────
# _parse_oams — Lee los OAMs originales del portrait y calcula el bounding box
# ─────────────────────────────────────────────────────────────────────────────

def _parse_oams(table3, table2, engine, f0, f2):
    OAM_DIMS = engine.OAM_DIMS
    oam_offset = f2 * 8
    oams = []
    for i in range(f0):
        a0, a1, a2 = struct.unpack('<HHH', table3[oam_offset:oam_offset+6])
        y = a0 & 0xFF
        if y > 127: y -= 256
        shape = (a0 >> 14) & 3
        x = a1 & 0x1FF
        if x > 255: x -= 512
        size = (a1 >> 14) & 3
        tile = a2 & 0x3FF
        w, h = OAM_DIMS.get((shape, size), (8, 8))
        oams.append({'x': x, 'y': y, 'w': w, 'h': h, 'tile': tile})
        oam_offset += 8
    return oams


def _bounding_box(oams):
    min_x = min(o['x'] for o in oams)
    min_y = min(o['y'] for o in oams)
    max_x = max(o['x'] + o['w'] for o in oams)
    max_y = max(o['y'] + o['h'] for o in oams)
    return min_x, min_y, max_x, max_y


# ─────────────────────────────────────────────────────────────────────────────
# _encode_custom_palette — Convierte lista (r,g,b)×16 → bytearray GBA BGR555
# ─────────────────────────────────────────────────────────────────────────────

def _encode_custom_palette(custom_palette):
    data = bytearray(32)
    for i, (cr, cg, cb) in enumerate(custom_palette):
        r5 = (cr >> 3) & 0x1F
        g5 = (cg >> 3) & 0x1F
        b5 = (cb >> 3) & 0x1F
        c16 = r5 | (g5 << 5) | (b5 << 10)
        struct.pack_into('<H', data, i * 2, c16)
    return data


# ─────────────────────────────────────────────────────────────────────────────
# repack_vanilla — Modo Vainilla (retoca píxeles, conserva OAMs y metadata)
#
# USO: el PNG tiene exactamente el mismo layout de sprites que el original
#      (mismo tamaño, misma distribución de tiles). Solo cambian los píxeles.
#      Ideal para retoques rápidos en el mismo portrait.
# ─────────────────────────────────────────────────────────────────────────────

def repack_vanilla(target_portrait_hex, input_png_path, rom_data=None, custom_palette=None, fork_palette=False):
    """
    Reinyecta píxeles en los tiles existentes SIN tocar la metadata OAM.
    El PNG debe caber dentro del bounding box OAM original.
    """
    rom = bytearray(rom_data) if rom_data else bytearray(open(ROM_PATH, 'rb').read())
    engine = MelodyPortraitEngine(None)
    img    = Image.open(input_png_path).convert("RGBA")

    counts, ptrs, tables, header_addr, _ = _load_tables(rom)
    t1, t2, t3, t4, t5, t6, t7 = tables

    internal_idx = struct.unpack('<H', t1[target_portrait_hex*4+2 : target_portrait_hex*4+4])[0]
    if internal_idx >= counts[1]:
        raise ValueError(f"Índice interno inválido: {internal_idx}")

    meta = internal_idx * 16
    f0  = struct.unpack('<H', t2[meta:meta+2])[0]
    f2  = struct.unpack('<H', t2[meta+2:meta+4])[0]
    f4  = struct.unpack('<H', t2[meta+4:meta+6])[0]
    f6  = struct.unpack('<H', t2[meta+6:meta+8])[0]
    fA  = struct.unpack('<H', t2[meta+10:meta+12])[0]

    oams = _parse_oams(t3, t2, engine, f0, f2)
    if not oams:
        raise ValueError("No se encontraron OAMs para este portrait.")

    min_x, min_y, max_x, max_y = _bounding_box(oams)
    orig_w = max_x - min_x
    orig_h = max_y - min_y

    if img.width > orig_w or img.height > orig_h:
        raise ValueError(
            f"El PNG ({img.width}×{img.height}) es más grande que el bounding box "
            f"OAM original ({orig_w}×{orig_h}).\n"
            "Usa repack_expansion() para portraits nuevos o más grandes."
        )

    # --- Paleta ---
    pal_offset = fA * 32
    if custom_palette and len(custom_palette) == 16:
        pal_data = _encode_custom_palette(custom_palette)
        if fork_palette:
            new_pal_idx = counts[4]
            t5 += pal_data
            counts[4] += 1
            fA = new_pal_idx
            struct.pack_into('<H', t2, meta+10, fA)
        else:
            t5[pal_offset:pal_offset+32] = pal_data
        colors = list(custom_palette)
    else:
        pal_data = t5[pal_offset:pal_offset+32]
        colors = []
        for i in range(16):
            c16 = struct.unpack('<H', pal_data[i*2:i*2+2])[0]
            colors.append(((c16 & 0x1F) << 3, ((c16 >> 5) & 0x1F) << 3, ((c16 >> 10) & 0x1F) << 3))

    pixels = img.load()

    def get_idx(r, g, b, a):
        if a < 128:
            return 0
        best, dist = 0, 999999
        for i, c in enumerate(colors):
            if i == 0:
                continue
            d = (r-c[0])**2 + (g-c[1])**2 + (b-c[2])**2
            if d < dist:
                dist, best = d, i
        return best

    gfx_buffer = bytearray(f4 * 32)
    for oam in oams:
        ox = oam['x'] - min_x
        oy = oam['y'] - min_y
        w, h = oam['w'], oam['h']
        t_start = oam['tile']
        for ty in range(h // 8):
            for tx in range(w // 8):
                t_idx = t_start + (ty * (w // 8)) + tx
                if t_idx >= f4:
                    continue
                for py in range(8):
                    for px in range(0, 8, 2):
                        cx, cy = ox + tx*8 + px, oy + ty*8 + py
                        idx1 = get_idx(*pixels[cx, cy]) if cx < img.width and cy < img.height else 0
                        idx2 = get_idx(*pixels[cx+1, cy]) if cx+1 < img.width and cy < img.height else 0
                        boff = (t_idx * 32) + (py * 4) + (px // 2)
                        gfx_buffer[boff] = (idx2 << 4) | idx1

    gfx_byte_start = f6 * 32
    t4[gfx_byte_start:gfx_byte_start + len(gfx_buffer)] = gfx_buffer

    print(f"[Vanilla] Portrait {target_portrait_hex:02X}: GFX actualizado in-place. OAMs intactos.")
    tables = [t1, t2, t3, t4, t5, t6, t7]
    _flush_tables(rom, tables, counts, OUT_ROM_PATH if rom_data is None else None)
    return rom


# ─────────────────────────────────────────────────────────────────────────────
# repack_expansion — Modo Expansión (portrait nuevo, más grande o diferente)
#
# USO: cualquier portrait que sea distinto al original en tamaño, forma o layout.
#      Recalcula TODOS los OAMs, tiles y metadata desde cero para el portrait.
#      Siempre actualiza f0 (OAM count) en la metadata → SIN recorte.
# ─────────────────────────────────────────────────────────────────────────────

def repack_expansion(target_portrait_hex, input_png_path, rom_data=None, custom_palette=None, fork_palette=False):
    """
    Reinyecta un portrait completamente nuevo en la ROM.
    Recalcula OAMs (Natsume-style smart slicer), GFX y metadata.

    Modos de escritura:
      - PRIMERA INYECCION: fork-and-append al final de T3/T4/T5.
      - OVERWRITE IN-PLACE: si el portrait ya fue expandido antes y los nuevos
        tiles caben en el slot anterior (new_tiles <= old_f4), sobreescribe
        en-place sin crecer T4. Esto evita la acumulacion de datos huerfanos.
      - ORPHAN + APPEND: si el portrait crece demasiado para su slot anterior,
        se appendea al final y el slot viejo queda sin referencias (huerfano).
    """
    rom    = bytearray(rom_data) if rom_data else bytearray(open(ROM_PATH, 'rb').read())
    engine = MelodyPortraitEngine(None)
    img    = Image.open(input_png_path).convert("RGBA")

    counts, ptrs, tables, header_addr, _ = _load_tables(rom)
    t1, t2, t3, t4, t5, t6, t7 = tables

    internal_idx = struct.unpack('<H', t1[target_portrait_hex*4+2 : target_portrait_hex*4+4])[0]
    if internal_idx >= counts[1]:
        raise ValueError(f"Indice interno invalido: {internal_idx}")

    meta = internal_idx * 16
    f0   = struct.unpack('<H', t2[meta:meta+2])[0]
    f2   = struct.unpack('<H', t2[meta+2:meta+4])[0]
    f4   = struct.unpack('<H', t2[meta+4:meta+6])[0]   # tiles actuales del portrait
    f6   = struct.unpack('<H', t2[meta+6:meta+8])[0]   # inicio GFX actual en T4

    # Leer OAMs originales para obtener el anchor (min_x, min_y)
    oams = _parse_oams(t3, t2, engine, f0, f2)
    if not oams:
        raise ValueError("No se encontraron OAMs para este portrait.")

    min_x, min_y, _, _ = _bounding_box(oams)
    print(f"[Expansion] Portrait {target_portrait_hex:02X}: anchor=({min_x},{min_y}), "
          f"PNG={img.width}x{img.height}px")

    # ── Smart Slicer (Natsume-style): omite OAMs 100%% transparentes ──
    slices = engine.calculate_slices_smart(img, img.width, img.height,
                                           anchor_x=min_x,
                                           anchor_y=0)
    print(f"[Expansion] Smart slicer: {len(slices)} OAMs generados "
          f"(vs {len(oams)} originales). anchor=({min_x},0)")

    # ── GFX y Paleta ──
    if custom_palette and len(custom_palette) == 16:
        new_gfx, _ = engine.encode_4bpp(img, slices, custom_palette=custom_palette, respect_indices=True)
        new_pal    = _encode_custom_palette(custom_palette)
    else:
        new_gfx, new_pal = engine.encode_4bpp(img, slices, respect_indices=True)

    new_oam_data    = engine.generate_oam_data(slices)
    new_tiles_count = len(new_gfx) // 32
    new_oam_count   = len(new_oam_data) // 8

    print(f"[Expansion] new_oam_count={new_oam_count}, new_tiles_count={new_tiles_count}")

    # ── Portrait Slot Manager: overwrite in-place vs fork-and-append ──
    vanilla_t4_count = _get_vanilla_t4_count(rom)
    is_already_expanded = (f6 >= vanilla_t4_count)

    if is_already_expanded and new_tiles_count <= f4:
        # OVERWRITE IN-PLACE: los tiles caben en el slot anterior
        # T4 no crece, se sobreescribe en la posicion existente.
        old_gfx_off = f6 * 32
        t4[old_gfx_off : old_gfx_off + new_tiles_count * 32] = new_gfx
        # Rellenar con ceros los tiles sobrantes del slot anterior (si new < old)
        if new_tiles_count < f4:
            zero_start = old_gfx_off + new_tiles_count * 32
            zero_end   = old_gfx_off + f4 * 32
            t4[zero_start:zero_end] = bytes(zero_end - zero_start)
        new_gfx_start = f6
        print(f"[Expansion] OVERWRITE IN-PLACE: slot f6={f6}, "
              f"{new_tiles_count}/{f4} tiles usados.")

        # OAMs: sobreescribir en-place en T3 si caben
        old_oam_off = f2 * 8
        if new_oam_count <= f0:
            t3[old_oam_off : old_oam_off + new_oam_count * 8] = new_oam_data
            new_oam_start = f2
            print(f"[Expansion] OAMs overwrite in-place: slot f2={f2}, "
                  f"{new_oam_count}/{f0} OAMs usados.")
        else:
            # Mas OAMs que antes: appendear
            new_oam_start = counts[2]
            t3 += new_oam_data
            print(f"[Expansion] OAMs append: {new_oam_count} OAMs (antes {f0}).")

        # Paleta: sobreescribir en-place o fork
        old_fA = struct.unpack('<H', t2[meta+10:meta+12])[0]
        new_counts = list(counts)
        if custom_palette and fork_palette:
            new_pal_idx = new_counts[4]
            t5 += new_pal
            new_counts[4] += 1
            print(f"[Expansion] Paleta FORK: nueva paleta agregada en índice {new_pal_idx}.")
        else:
            pal_off = old_fA * 32
            if custom_palette:
                t5[pal_off:pal_off+32] = new_pal
            new_pal_idx = old_fA
            print(f"[Expansion] Paleta overwrite in-place: fA={old_fA}.")

        if new_oam_count > f0:
            new_counts[2] += new_oam_count
        # T4 y T5 no cambian de count (in-place)

    else:
        # FORK-AND-APPEND: primera inyeccion, o portrait que crece mas alla del slot
        if is_already_expanded:
            print(f"[Expansion] ORPHAN+APPEND: portrait ya expandido pero crece "
                  f"({new_tiles_count} > slot={f4}). Slot anterior f6={f6} queda huerfano.")
        else:
            print(f"[Expansion] FORK-AND-APPEND: primera inyeccion del portrait.")

        new_oam_start = counts[2]
        t3 += new_oam_data

        new_gfx_start = counts[3]
        t4 += new_gfx

        new_counts = list(counts)
        
        old_fA = struct.unpack('<H', t2[meta+10:meta+12])[0]
        if not fork_palette and custom_palette:
            pal_off = old_fA * 32
            t5[pal_off:pal_off+32] = new_pal
            new_pal_idx = old_fA
        else:
            new_pal_idx = new_counts[4]
            t5 += new_pal
            new_counts[4] += 1

        new_counts[2] += new_oam_count
        new_counts[3] += new_tiles_count

    # ── Actualizar metadata T2 ──
    m_off = internal_idx * 16
    struct.pack_into('<H', t2, m_off,    new_oam_count)    # f0: OAM count
    struct.pack_into('<H', t2, m_off+2,  new_oam_start)    # f2: OAM start
    struct.pack_into('<H', t2, m_off+4,  new_tiles_count)  # f4: Tiles count
    struct.pack_into('<H', t2, m_off+6,  new_gfx_start)    # f6: GFX start
    struct.pack_into('<H', t2, m_off+10, new_pal_idx)       # fA: Palette index

    print(f"[Expansion] Metadata: f0={new_oam_count}, f2={new_oam_start}, "
          f"f4={new_tiles_count}, f6={new_gfx_start}, fA={new_pal_idx}")

    # ── Table Integrity Guard ──
    tables = [t1, t2, t3, t4, t5, t6, t7]
    _validate_tables(tables, new_counts)

    _flush_tables(rom, tables, new_counts, OUT_ROM_PATH if rom_data is None else None)
    print(f"[Expansion] Repack completo para portrait {target_portrait_hex:02X}.")
    return rom


# ─────────────────────────────────────────────────────────────────────────────
# repack — Punto de entrada unificado (mantiene compatibilidad con la UI)
#
# Decide automáticamente el modo correcto:
#   - Si force_expansion=True  → siempre Expansión (nuevo portrait)
#   - Si force_expansion=False → compara tamaño PNG vs bounding box OAM:
#       • PNG cabe (mismo tamaño o menor) → Vanilla (retoque rápido)
#       • PNG no cabe (más grande)        → Expansión (nuevo portrait)
#
# NOTA: El bounding box se calcula sobre los OAMs CON sombra, lo que puede
#       hacer que orig_w/orig_h sean más grandes que el área visible. Por eso,
#       la UI siempre pasa force_expansion=True cuando el usuario importa un
#       portrait distinto al original.
# ─────────────────────────────────────────────────────────────────────────────

def repack(target_portrait_hex, input_png_path, rom_data=None,
           force_expansion=True, custom_palette=None, fork_palette=False):
    """
    Punto de entrada unificado para la UI.

    Args:
        target_portrait_hex:  Índice del portrait (int).
        input_png_path:       Ruta al PNG de entrada.
        rom_data:             bytearray de la ROM (opcional).
        force_expansion:      True  → Expansión siempre (default, seguro para nuevos portraits).
                              False → Auto-detect (Vanilla si cabe, Expansión si no).
        custom_palette:       Lista de 16 tuplas (r,g,b) o None.
        fork_palette:         True  → Crea una nueva entrada en la paleta.
    """
    if force_expansion:
        return repack_expansion(target_portrait_hex, input_png_path, rom_data, custom_palette, fork_palette)

    # Auto-detect: necesitamos leer el bounding box
    rom = bytearray(rom_data) if rom_data else bytearray(open(ROM_PATH, 'rb').read())
    engine = MelodyPortraitEngine(None)
    img    = Image.open(input_png_path)

    counts, ptrs, tables, header_addr, _ = _load_tables(rom)
    t1, t2, t3, _, _, _, _ = tables

    internal_idx = struct.unpack('<H', t1[target_portrait_hex*4+2 : target_portrait_hex*4+4])[0]
    if internal_idx >= counts[1]:
        return repack_expansion(target_portrait_hex, input_png_path, rom_data, custom_palette, fork_palette)

    meta = internal_idx * 16
    f0   = struct.unpack('<H', t2[meta:meta+2])[0]
    f2   = struct.unpack('<H', t2[meta+2:meta+4])[0]
    oams = _parse_oams(t3, t2, engine, f0, f2)

    if not oams:
        return repack_expansion(target_portrait_hex, input_png_path, rom_data, custom_palette, fork_palette)

    min_x, min_y, max_x, max_y = _bounding_box(oams)
    orig_w = max_x - min_x
    orig_h = max_y - min_y

    if img.width <= orig_w and img.height <= orig_h:
        print(f"[Auto] PNG ({img.width}×{img.height}) cabe en bbox original ({orig_w}×{orig_h}) → Vanilla")
        return repack_vanilla(target_portrait_hex, input_png_path, rom_data, custom_palette, fork_palette)
    else:
        print(f"[Auto] PNG ({img.width}×{img.height}) > bbox original ({orig_w}×{orig_h}) → Expansion")
        return repack_expansion(target_portrait_hex, input_png_path, rom_data, custom_palette, fork_palette)


if __name__ == '__main__':
    pass
