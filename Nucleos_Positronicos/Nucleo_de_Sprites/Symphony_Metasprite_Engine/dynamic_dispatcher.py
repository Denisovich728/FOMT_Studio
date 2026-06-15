import os
import csv
import struct
import json
from PIL import Image

# Dynamic Pointer Table matching Entity Prefix to Memory Assets
DYNAMIC_POINTER_TABLE = {
    "Karen": {
        "gfx_base": 0x0862329C,
        "pal_base": 0x08662AC0,
        "oam_base": 0x086661BF,
    },
    # Future entity bases can be appended here.
}

OAM_DIMS = {
    (0,0):(8,8),(0,1):(16,16),(0,2):(32,32),(0,3):(64,64),
    (1,0):(16,8),(1,1):(32,8),(1,2):(32,16),(1,3):(64,32),
    (2,0):(8,16),(2,1):(8,32),(2,2):(16,32),(2,3):(32,64),
}

class SymphonyDynamicDispatcher:
    """
    Replicates the FoMT GBA Sprite Dispatcher Logic.
    Resolves graphics and metasprite geometry using absolute memory references
    (dynamic pointer table) instead of current-address mathematical displacements.
    """
    def __init__(self, rom_path):
        with open(rom_path, 'rb') as f:
            self.rom = f.read()

    def get_anim_info(self, anim_id):
        script_table = 0x58BA2C
        offset = script_table + anim_id * 4
        if offset + 4 > len(self.rom):
            return None, None
        graphic_id, script_offset = struct.unpack_from('<HH', self.rom, offset)
        script_base = 0x08663208
        script_addr = script_base + (script_offset * 4)
        return graphic_id, script_addr

    def decode_pal(self, pal_addr):
        pal = []
        off = pal_addr - 0x08000000
        for i in range(16):
            c = struct.unpack_from('<H', self.rom, off + i*2)[0]
            r = (c & 0x1F) << 3
            g = ((c >> 5) & 0x1F) << 3
            b = ((c >> 10) & 0x1F) << 3
            a = 0 if i == 0 else 255
            pal.append((r, g, b, a))
        return pal

    def decode_tile(self, addr):
        off = addr - 0x08000000
        px = []
        for byte in self.rom[off:off+32]:
            px.append(byte & 0x0F)
            px.append((byte >> 4) & 0x0F)
        return px

    def render_sub_sprite(self, pal, gfx_base, start_tile, w_tiles, h_tiles):
        img = Image.new('RGBA', (w_tiles*8, h_tiles*8), (0,0,0,0))
        t = start_tile
        for ty in range(h_tiles):
            for tx in range(w_tiles):
                addr = gfx_base + t*32
                if addr - 0x08000000 + 32 <= len(self.rom):
                    px = self.decode_tile(addr)
                    for y in range(8):
                        for x in range(8):
                            idx = px[y*8+x]
                            if idx > 0:
                                img.putpixel((tx*8+x, ty*8+y), pal[idx])
                t += 1
        return img

    def parse_script(self, script_addr):
        offset = script_addr - 0x08000000
        frames = []
        
        while offset < len(self.rom):
            b0 = self.rom[offset]
            offset += 1
            
            if b0 == 0xBD:
                break
                
            if 0x80 <= b0 < 0xCF:
                frame_idx = b0 - 0x80
                delay = self.rom[offset] if offset < len(self.rom) else 0
                offset += 1
                frames.append({
                    'cmd': b0,
                    'type': 'direct',
                    'frame_idx': frame_idx,
                    'delay': delay
                })
            elif b0 >= 0xCF:
                # OAM argument lookup
                arg1 = self.rom[offset]
                arg2 = self.rom[offset+1]
                offset += 2
                
                if arg1 > 0x80:
                    break
                    
                frames.append({
                    'cmd': b0,
                    'type': 'metasprite',
                    'arg1': arg1,
                    'arg2': arg2,
                    'delay': 0
                })
            else:
                if frames:
                    frames[-1]['delay'] += b0
                else:
                    frames.append({
                        'cmd': b0,
                        'type': 'wait_only',
                        'delay': b0
                    })
        return frames

    def get_oam_entry(self, oam_base, arg1):
        oam_off = oam_base - 0x08000000 + arg1 * 12
        if oam_off + 12 > len(self.rom):
            return None
        
        b0 = self.rom[oam_off]
        y = struct.unpack_from('b', self.rom, oam_off+1)[0]
        x = struct.unpack_from('b', self.rom, oam_off+2)[0]
        w4 = struct.unpack_from('<I', self.rom, oam_off+4)[0]
        w8 = struct.unpack_from('<I', self.rom, oam_off+8)[0]
        
        shape = (b0 >> 6) & 3
        size = (w4 >> 14) & 3
        tile_offset = w8
        
        return {
            'shape': shape,
            'size': size,
            'x': x,
            'y': y,
            'tile_offset': tile_offset,
            'w4': w4,
            'w8': w8
        }

    def dump_animation(self, anim_id, anim_name, config, out_dir):
        gfx_base = config['gfx_base']
        pal_base = config['pal_base']
        oam_base = config['oam_base']

        graphic_id, script_addr = self.get_anim_info(anim_id)
        if not script_addr:
            return

        print(f"[{anim_name}] Dumping ID 0x{anim_id:03X} -> Script at 0x{script_addr:08X}")
        frames_meta = self.parse_script(script_addr)
        pal = self.decode_pal(pal_base)

        os.makedirs(out_dir, exist_ok=True)
        images = []
        durations = []
        
        ANCHOR_X = 64
        ANCHOR_Y = 64

        for i, frame in enumerate(frames_meta):
            canvas = Image.new('RGBA', (128, 128), (0,0,0,0))
            if frame['type'] == 'metasprite':
                arg1 = frame['arg1']
                oam = self.get_oam_entry(oam_base, arg1)
                if oam:
                    dims = OAM_DIMS.get((oam['shape'], oam['size']), (8,8))
                    w_tiles = dims[0] // 8
                    h_tiles = dims[1] // 8
                    
                    start_tile = 0 
                    tile_img = self.render_sub_sprite(pal, gfx_base, start_tile, w_tiles, h_tiles)
                    
                    dest_x = ANCHOR_X + oam['x']
                    dest_y = ANCHOR_Y + oam['y']
                    canvas.paste(tile_img, (dest_x, dest_y), tile_img)
            elif frame['type'] == 'direct':
                tile_img = self.render_sub_sprite(pal, gfx_base, frame['frame_idx']*32, 8, 8)
                canvas.paste(tile_img, (ANCHOR_X - 32, ANCHOR_Y - 32), tile_img)
                
            images.append(canvas)
            dur_ms = max(20, frame['delay'] * 16.6)
            durations.append(dur_ms)
            
            canvas.save(os.path.join(out_dir, f"{anim_name}_{i:03d}.png"))
            
        if images:
            sheet_w = 128 * len(images)
            sheet_h = 128
            spritesheet = Image.new('RGBA', (sheet_w, sheet_h), (0,0,0,0))
            for i, img in enumerate(images):
                spritesheet.paste(img, (i*128, 0))
            spritesheet.save(os.path.join(out_dir, f"{anim_name}_sheet.png"))
            
            out_gif = os.path.join(out_dir, f"{anim_name}.gif")
            images[0].save(out_gif, save_all=True, append_images=images[1:], duration=durations, loop=0, disposal=2)

def extract_all_cascade(rom_path, csv_path, out_dir):
    dispatcher = SymphonyDynamicDispatcher(rom_path)
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader) 
        for row in reader:
            if not row or len(row) < 2: continue
            anim_name = row[0]
            anim_id_str = row[1].strip()
            if not anim_id_str.startswith('0x'): continue
            anim_id = int(anim_id_str, 16)
            
            config = None
            for prefix, cfg in DYNAMIC_POINTER_TABLE.items():
                if anim_name.startswith(prefix):
                    config = cfg
                    break
                    
            if config:
                dispatcher.dump_animation(anim_id, anim_name, config, os.path.join(out_dir, anim_name))

if __name__ == '__main__':
    ROM_PATH = r"j:\scratch\Harvest Moon - Friends of Mineral Town.gba"
    CSV_PATH = r"j:\Repositorios\fomt_studio\Banco_de_Datos\Cilixes\fomt\Fomt_Animations.csv"
    OUT_DIR = r"j:\Repositorios\fomt_studio\output\cascade_sprites"
    
    extract_all_cascade(ROM_PATH, CSV_PATH, OUT_DIR)
