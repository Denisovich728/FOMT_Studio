import struct
import os
import csv
from PIL import Image

ROM_PATH = r"j:\Repositorios\fomt_studio\Harvest Moon - Friends of Mineral Town.gba"
CSV_PATH = r"j:\Repositorios\fomt_studio\Banco_de_Datos\Cilixes\fomt\Fomt_Portraits.csv" # If it exists, else we'll iterate 0-255
OUTPUT_DIR = r"j:\Repositorios\fomt_studio\portraits_dump"

def read_hword(rom, addr):
    return struct.unpack('<H', rom[addr-0x08000000:addr-0x08000000+2])[0]

def read_word(rom, addr):
    return struct.unpack('<I', rom[addr-0x08000000:addr-0x08000000+4])[0]

def decode_4bpp_tile(rom, addr):
    pixels = []
    # 4bpp tile = 8x8 pixels = 32 bytes
    for i in range(32):
        byte = rom[addr-0x08000000+i]
        pixels.append(byte & 0x0F)
        pixels.append((byte >> 4) & 0x0F)
    return pixels

def decode_palette(rom, addr):
    colors = []
    for i in range(16):
        c = read_hword(rom, addr + i*2)
        r = (c & 0x1F) * 8
        g = ((c >> 5) & 0x1F) * 8
        b = ((c >> 10) & 0x1F) * 8
        colors.append((r, g, b, 255 if i > 0 else 0)) # Color 0 is transparent
    return colors

# OAM dimensions (Shape, Size) -> (Width, Height)
OAM_DIMS = {
    (0, 0): (8, 8),   (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64),
    (1, 0): (16, 8),  (1, 1): (32, 8),  (1, 2): (32, 16), (1, 3): (64, 32),
    (2, 0): (8, 16),  (2, 1): (8, 32),  (2, 2): (16, 32), (2, 3): (32, 64)
}

def get_bundle_headers(rom):
    # Firma de la función que lee el bundle de portraits
    # 70 B5 46 46 40 B4 8E B0 80 46 0D 1C 20 20 52 F7 C9 FC 06 1C 0D 49 68 46
    signature = bytes.fromhex('70B5464640B48EB080460D1C202052F7C9FC061C0D496846')
    idx = rom.find(signature)
    
    header_addr = 0x0052D984 # Default to vanilla if not found
    
    if idx != -1:
        # La instrucción ldr r1, [pc, #0x34] está en idx + 0x14
        pc_val = (idx + 0x14 + 4) & ~3
        pool_addr = pc_val + 0x34
        
        if pool_addr + 4 <= len(rom):
            p = struct.unpack_from('<I', rom, pool_addr)[0]
            if 0x08000000 <= p < 0x09FFFFFF:
                header_addr = p & 0x01FFFFFF

    counts = []
    ptrs = []
    r1 = header_addr

    # --- Auto-Recovery de payload corrupto anterior ---
    is_buggy_payload = False
    if header_addr == 0x007D0000:
        first_val = struct.unpack_from('<I', rom, header_addr)[0]
        if first_val == 0x00000001 or first_val == 0x00010001:
            is_buggy_payload = True
            buggy_counts_addr = 0x0852D984 - 0x08000000
            for _ in range(5):
                counts.append(struct.unpack_from('<H', rom, buggy_counts_addr)[0])
                buggy_counts_addr += 8
            counts.append(0)  # Table 6 count dummy
            curr_data_ptr = header_addr
            for i, shift in enumerate([2, 4, 3, 5, 5, 3]):
                ptrs.append(curr_data_ptr + 0x08000000)
                curr_data_ptr += counts[i] * (1 << shift)

    if not is_buggy_payload:
        for shift in [2, 4, 3, 5, 5, 3]:
            cnt = struct.unpack_from('<I', rom, r1)[0]
            counts.append(cnt)
            r1 += 4
            ptrs.append(r1 + 0x08000000)
            r1 += cnt * (1 << shift)

    return counts, ptrs

def dump_single(rom, portrait_id, name, output_dir, counts, ptrs):
    if portrait_id >= counts[0]:
        return False

    idx = read_hword(rom, ptrs[0] + portrait_id * 4 + 2)
    if idx >= counts[1]:
        return False

    struct_base = ptrs[1] + idx * 16
    f0 = read_hword(rom, struct_base)
    f2 = read_hword(rom, struct_base + 2)
    f6 = read_hword(rom, struct_base + 6)
    fA = read_hword(rom, struct_base + 0xA)

    ptr_OAM = ptrs[2] + f2 * 8
    ptr_GFX = ptrs[3] + f6 * 32
    ptr_PAL = ptrs[4] + fA * 32

    # Read Palette
    palette = decode_palette(rom, ptr_PAL)

    # Read OAM
    oam_entries = []
    num_oam_entries = f0 # usually f0 holds the count of OAM structs

    min_x = 999
    min_y = 999
    max_x = -999
    max_y = -999

    for i in range(num_oam_entries):
        attr0 = read_hword(rom, ptr_OAM + i*8)
        attr1 = read_hword(rom, ptr_OAM + i*8 + 2)
        attr2 = read_hword(rom, ptr_OAM + i*8 + 4)

        y = attr0 & 0xFF
        if y > 127: y -= 256
        shape = (attr0 >> 14) & 3

        x = attr1 & 0x1FF
        if x > 255: x -= 512
        size = (attr1 >> 14) & 3

        tile_idx = attr2 & 0x3FF

        w, h = OAM_DIMS.get((shape, size), (8, 8))
        oam_entries.append({'x': x, 'y': y, 'w': w, 'h': h, 'tile': tile_idx})

        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x + w)
        max_y = max(max_y, y + h)

    if len(oam_entries) == 0:
        return False

    # Create Image
    img_w = max_x - min_x
    img_h = max_y - min_y
    if img_w <= 0 or img_h <= 0 or img_w > 512 or img_h > 512:
        return False

    img = Image.new('P', (img_w, img_h), 0)
    
    # Flatten palette for PIL: [r,g,b, r,g,b, ...]
    flat_palette = []
    for c in palette:
        flat_palette.extend([c[0], c[1], c[2]])
    # Pad to 256 colors
    flat_palette.extend([0] * (768 - len(flat_palette)))
    img.putpalette(flat_palette)

    # Draw OAMs
    for oam in oam_entries:
        dest_x = oam['x'] - min_x
        dest_y = oam['y'] - min_y
        tiles_w = oam['w'] // 8
        tiles_h = oam['h'] // 8

        for ty in range(tiles_h):
            for tx in range(tiles_w):
                current_tile_idx = oam['tile'] + (ty * tiles_w) + tx
                tile_addr = ptr_GFX + current_tile_idx * 32
                pixels = decode_4bpp_tile(rom, tile_addr)

                for py in range(8):
                    for px in range(8):
                        color_idx = pixels[py*8 + px]
                        if color_idx != 0: # not transparent
                            img.putpixel((dest_x + tx*8 + px, dest_y + ty*8 + py), color_idx)

    safe_name = "".join([c for c in name if c.isalpha() or c.isdigit() or c=='_']).strip()
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    out_path = os.path.join(output_dir, f"{portrait_id:02X}_{safe_name}.png")
    img.save(out_path, transparency=0)
    return out_path

def dump_all(rom_path, csv_path, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(rom_path, 'rb') as f:
        rom = f.read()

    counts, ptrs = get_bundle_headers(rom)

    # Dictionary of IDs to names
    ids_to_dump = {}
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader) # skip header
            for row in reader:
                if len(row) >= 2:
                    try:
                        val = int(row[1].strip(), 16)
                        ids_to_dump[val] = row[0].strip()
                    except ValueError:
                        pass
    except Exception as e:
        print(f"Could not read CSV: {e}, iterating 0 to 200.")
        ids_to_dump = {i: f"Portrait_{i:02X}" for i in range(200)}

    for portrait_id, name in ids_to_dump.items():
        dump_single(rom, portrait_id, name, output_dir, counts, ptrs)

def main():
    dump_all(ROM_PATH, CSV_PATH, OUTPUT_DIR)

if __name__ == '__main__':
    main()
