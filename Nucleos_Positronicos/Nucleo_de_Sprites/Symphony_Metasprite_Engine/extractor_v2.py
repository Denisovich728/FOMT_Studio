import struct
import csv
import os
import math
from PIL import Image

ROM = b''
pointers = {}
animations = []

OAM_DIMS = {
    (0,0):(8,8),(0,1):(16,16),(0,2):(32,32),(0,3):(64,64),
    (1,0):(16,8),(1,1):(32,8),(1,2):(32,16),(1,3):(64,32),
    (2,0):(8,16),(2,1):(8,32),(2,2):(16,32),(2,3):(32,64),
}

def decode_pal(addr):
    pal = []
    off = addr - 0x08000000
    for i in range(16):
        c = struct.unpack_from('<H', ROM, off + i*2)[0]
        r = (c & 0x1F) << 3
        g = ((c >> 5) & 0x1F) << 3
        b = ((c >> 10) & 0x1F) << 3
        a = 0 if i == 0 else 255
        pal.append((r, g, b, a))
    return pal

def decode_tile(addr):
    off = addr - 0x08000000
    px = []
    for byte in ROM[off:off+32]:
        px.append(byte & 0x0F)
        px.append((byte >> 4) & 0x0F)
    return px

def render_sub_sprite(pal, gfx_base, start_tile, w_tiles, h_tiles):
    img = Image.new('RGBA', (w_tiles*8, h_tiles*8), (0,0,0,0))
    t = start_tile
    for ty in range(h_tiles):
        for tx in range(w_tiles):
            off = gfx_base + t*32
            if off - 0x08000000 >= len(ROM): break
            px = decode_tile(off)
            for y in range(8):
                for x in range(8):
                    idx = px[y*8+x]
                    if idx > 0:
                        img.putpixel((tx*8+x, ty*8+y), pal[idx])
            t += 1
    return img

def parse_oam_template(oam_base, arg1):
    off = oam_base - 0x08000000 + arg1 * 12
    if off < 0 or off + 12 > len(ROM): return None
    attr0, attr1, attr2 = struct.unpack_from('<hhh', ROM, off)
    y = attr0 & 0xFF
    if y > 127: y -= 256
    shape = (attr0 >> 14) & 3
    x = attr1 & 0x1FF
    if x > 255: x -= 512
    size = (attr1 >> 14) & 3
    tile_idx = attr2 & 0x3FF
    return x, y, shape, size, tile_idx

def get_script_commands(script_addr):
    off = script_addr - 0x08000000
    cmds = []
    last_cmd = None
    count = 0
    while off < len(ROM) and count < 1000:
        count += 1
        b0 = ROM[off]; off += 1
        if b0 == 0xBD: break
        if b0 < 0x80:
            arg1 = b0; arg2 = ROM[off] if off < len(ROM) else 0; off += 1
            cmds.append({'type': 'draw', 'cmd': last_cmd, 'arg1': arg1, 'arg2': arg2})
        elif 0x80 <= b0 <= 0xB0:
            cmds.append({'type': 'wait', 'frames': b0 - 0x80})
        elif 0xB1 <= b0 <= 0xCE:
            last_cmd = b0
        elif b0 >= 0xCF:
            arg1 = ROM[off]; off += 1
            arg2 = ROM[off]; off += 1
            cmds.append({'type': 'draw', 'cmd': b0, 'arg1': arg1, 'arg2': arg2})
            last_cmd = b0
    return cmds

def get_gfx_pal_for_anim(anim_name):
    if "Weeding" in anim_name: anim_name = anim_name.replace("Weeding", "Wedding")
    if "Wedding" in anim_name:
        for k in pointers:
            if "Wedding" in k and anim_name.split('_')[0] in k: return pointers[k]
    if "Baby" in anim_name:
        for k in pointers:
            if "Baby" in k and anim_name.split('_')[0] in k: return pointers[k]
    if "Sleeping" in anim_name:
        for k in pointers:
            if "Sleeping" in k and anim_name.split('_')[0] in k: return pointers[k]
            
    char_name = anim_name.split('_')[0]
    if f"{char_name}-Daily" in pointers: return pointers[f"{char_name}-Daily"]
    if char_name in pointers: return pointers[char_name]
    return None

if __name__ == "__main__":
    ROM_PATH = r'j:\scratch\Harvest Moon - Friends of Mineral Town.gba'
    if os.path.exists(ROM_PATH):
        with open(ROM_PATH, 'rb') as f:
            ROM = f.read()
    else:
        print(f"[!] ROM not found at {ROM_PATH}. Extractor will fail on run.")
        ROM = b''

    sprite_csv = r'j:\Repositorios\fomt_studio\Banco_de_Datos\Cilixes\fomt\Fomt_Sprite_data.csv'
    if os.path.exists(sprite_csv):
        with open(sprite_csv, 'r') as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                if len(row) >= 3 and row[1].strip():
                    name = row[0].strip()
                    if ' ' in row[1]:
                        b = bytes([int(x, 16) for x in row[1].split()])
                        gfx = struct.unpack('<I', b)[0]
                        bp = bytes([int(x, 16) for x in row[2].split()])
                        pal = struct.unpack('<I', bp)[0]
                    else:
                        gfx = int(row[1], 16) | 0x08000000
                        pal = int(row[2], 16) | 0x08000000
                    pointers[name] = (gfx, pal)

    anim_csv = r'j:\Repositorios\fomt_studio\Banco_de_Datos\Cilixes\fomt\Fomt_Animations.csv'
    if os.path.exists(anim_csv):
        with open(anim_csv, 'r') as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                name = row[0]
                if len(row) > 1 and row[1].strip():
                    anim_id = int(row[1], 16)
                    animations.append((anim_id, name))

    out_dir_gifs = r'j:\Repositorios\fomt_studio\scratch\all_gifs'
    out_dir_sheets = r'j:\Repositorios\fomt_studio\scratch\all_sheets'
    os.makedirs(out_dir_gifs, exist_ok=True)
    os.makedirs(out_dir_sheets, exist_ok=True)

    oam_base = 0x0813B28C

    print(f"Extracting {len(animations)} animations...")
    success_count = 0

    for anim_id, name in animations:
        ptrs = get_gfx_pal_for_anim(name)
        if not ptrs: continue
        gfx_base, pal_base = ptrs
        if not (0x08000000 <= gfx_base < 0x09000000) or not (0x08000000 <= pal_base < 0x09000000):
            continue
        
        anim_data = ROM[0x58BA2C + anim_id * 4 : 0x58BA2C + anim_id * 4 + 4]
        if len(anim_data) < 4: continue
        offset_hi = struct.unpack_from('<H', anim_data, 2)[0]
        script_addr = 0x08663208 + (offset_hi * 4)
        if script_addr == 0 or script_addr < 0x08000000: continue
            
        pal = decode_pal(pal_base)
        cmds = get_script_commands(script_addr)
        
        frames = []
        unique_frames = []
        seen_hashes = set()
        
        current_frame_img = None
        bg = Image.new('RGBA', (64, 64), (50, 50, 50, 255))
        transparent_canvas = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        
        for c in cmds:
            if c['type'] == 'draw':
                if current_frame_img is None:
                    current_frame_img = bg.copy()
                    current_transparent = transparent_canvas.copy()
                    
                res = parse_oam_template(oam_base, c['arg1'])
                if not res: continue
                x, y, shape, size, tile_idx = res
                
                w, h = OAM_DIMS.get((shape, size), (8,8))
                
                try:
                    sub = render_sub_sprite(pal, gfx_base, tile_idx, w//8, h//8)
                except Exception:
                    continue
                
                dest_x = 32 + x
                dest_y = 64 + y - h
                
                current_frame_img.paste(sub, (dest_x, dest_y), sub)
                current_transparent.paste(sub, (dest_x, dest_y), sub)
                
            elif c['type'] == 'wait':
                if current_frame_img:
                    frames.append(current_frame_img)
                    img_hash = current_transparent.tobytes()
                    if img_hash not in seen_hashes:
                        seen_hashes.add(img_hash)
                        unique_frames.append(current_transparent)
                    current_frame_img = None
                    
        if frames:
            gif_path = os.path.join(out_dir_gifs, f"{name}.gif")
            frames[0].save(gif_path, save_all=True, append_images=frames[1:], duration=100, loop=0)
            
            if unique_frames:
                cols = min(8, len(unique_frames))
                rows = math.ceil(len(unique_frames) / cols)
                sheet = Image.new('RGBA', (cols * 64, rows * 64), (0,0,0,0))
                for i, f in enumerate(unique_frames):
                    cx = (i % cols) * 64
                    cy = (i // cols) * 64
                    sheet.paste(f, (cx, cy))
                sheet_path = os.path.join(out_dir_sheets, f"{name}_sheet.png")
                sheet.save(sheet_path)
                
            success_count += 1
            if success_count % 50 == 0:
                print(f"  Processed {success_count} animations...")

    print(f"Successfully processed {success_count} animations!")
