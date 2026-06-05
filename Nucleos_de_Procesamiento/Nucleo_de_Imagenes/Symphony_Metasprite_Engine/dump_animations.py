import os
import struct
import json
from PIL import Image

class SymphonyDumper:
    def __init__(self, rom_path):
        with open(rom_path, 'rb') as f:
            self.rom = f.read()

    def decode_tile_4bpp(self, offset):
        tile = []
        for y in range(8):
            row = []
            for x in range(4):
                if offset + y * 4 + x < len(self.rom):
                    byte = self.rom[offset + y * 4 + x]
                    row.append(byte & 0x0F)
                    row.append((byte >> 4) & 0x0F)
                else:
                    row.extend([0, 0])
            tile.append(row)
        return tile

    def load_palette(self, palette_addr):
        palette = []
        pal_data = self.rom[palette_addr : palette_addr + 32]
        for i in range(16):
            if i * 2 + 1 < len(pal_data):
                c = struct.unpack_from('<H', pal_data, i*2)[0]
                r = (c & 0x1F) * 8
                g = ((c >> 5) & 0x1F) * 8
                b = ((c >> 10) & 0x1F) * 8
                palette.extend([r, g, b])
            else:
                palette.extend([0, 0, 0])
        return palette

    def get_script_pointer(self, anim_id):
        script_table = 0x58BA2C
        script_base = 0x663208
        offset_hi = struct.unpack('<H', self.rom[script_table + anim_id * 4 + 2 : script_table + anim_id * 4 + 4])[0]
        return script_base + (offset_hi * 4) + 0x08000000

    def get_graphic_id(self, anim_id):
        script_table = 0x58BA2C
        graphic_id = struct.unpack('<H', self.rom[script_table + anim_id * 4 : script_table + anim_id * 4 + 2])[0]
        return graphic_id

    def parse_oam_math(self, arg1, arg2):
        r6 = self.rom[0x139C14 + arg1]
        lower = r6 & 15
        upper = r6 >> 4
        
        r0_lower = (lower * 2) + arg2
        r0_upper = (upper * 2) + arg2
        
        attr1 = struct.unpack('<H', self.rom[0x139C98 + r0_lower : 0x139C98 + r0_lower + 2])[0]
        attr0 = struct.unpack('<H', self.rom[0x139C98 + r0_upper : 0x139C98 + r0_upper + 2])[0]
        
        y = attr0 & 0xFF
        if y > 127: y -= 256
        shape = (attr0 >> 14) & 3
        
        x = attr1 & 0x1FF
        if x > 255: x -= 512
        size = (attr1 >> 14) & 3
        
        return {
            'x': x,
            'y': y,
            'shape': shape,
            'size': size,
            'attr0': attr0,
            'attr1': attr1
        }

    def parse_script(self, script_addr):
        offset = script_addr - 0x08000000
        frames = []
        
        while offset < len(self.rom):
            b0 = self.rom[offset]
            offset += 1
            
            if b0 == 0xBD: # End of script
                break
                
            # Direct frame draws (0x80 - 0xCF)
            if 0x80 <= b0 < 0xCF:
                # Direct frame draws map to a fixed frame index
                frame_idx = b0 - 0x80
                delay = self.rom[offset] if offset < len(self.rom) else 0
                offset += 1
                frames.append({
                    'cmd': b0,
                    'type': 'direct',
                    'frame_idx': frame_idx,
                    'delay': delay
                })
            # Metasprite draws (>= 0xCF)
            elif b0 >= 0xCF:
                arg1 = self.rom[offset]
                arg2 = self.rom[offset+1]
                offset += 2
                
                # Failsafe for invalid pointers
                if arg1 > 0x80:
                    break
                    
                oam_data = self.parse_oam_math(arg1, arg2)
                frames.append({
                    'cmd': b0,
                    'type': 'metasprite',
                    'arg1': arg1,
                    'arg2': arg2,
                    'oam': oam_data,
                    'delay': 0 # Wait commands come as separate bytes < 0x80 usually
                })
            # Wait delays (< 0x80)
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

    def parse_oams(self, oam_addr, count=10):
        oams = []
        offset = oam_addr - 0x08000000
        for i in range(count):
            if offset + 12 > len(self.rom): break
            chunk = self.rom[offset:offset+12]
            attr0, attr1, attr2, p3, b4, b5, b6, b7 = struct.unpack('<HHHHBBBB', chunk)
            
            y = attr0 & 0xFF
            if y > 127: y -= 256
            shape = (attr0 >> 14) & 3
            x = attr1 & 0x1FF
            if x > 255: x -= 512
            size = (attr1 >> 14) & 3
            tile = attr2 & 0x3FF
            
            # If shape and size are 0 and y == 0 and x == 0 and tile == 0, it might be an empty/end OAM
            # But let's export it.
            if y == -256 or x == -512:
                pass # Sanity check bounds
                
            oams.append({
                'x': x, 'y': y, 'shape': shape, 'size': size, 'tile': tile,
                'attr0': attr0, 'attr1': attr1, 'attr2': attr2
            })
            offset += 12
        return oams

    def render_oam(self, graphics_addr, oam, palette, tile_offset=0):
        OAM_DIMS = {
            (0, 0): (8, 8),   (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64),
            (1, 0): (16, 8),  (1, 1): (32, 8),  (1, 2): (32, 16), (1, 3): (64, 32),
            (2, 0): (8, 16),  (2, 1): (8, 32),  (2, 2): (16, 32), (2, 3): (32, 64)
        }
        
        shape = oam['shape']
        size = oam['size']
        if (shape, size) not in OAM_DIMS:
            return None
            
        w, h = OAM_DIMS[(shape, size)]
        img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        pixels = img.load()
        
        # We don't have attr2 statically, so we simulate reading tiles sequentially or offset
        start_tile = tile_offset
        
        tiles_w = w // 8
        tiles_h = h // 8
        
        offset = graphics_addr - 0x08000000 + (start_tile * 32)
        
        for ty in range(tiles_h):
            for tx in range(tiles_w):
                if offset >= len(self.rom): break
                t_pixels = self.decode_tile_4bpp(offset)
                for py in range(8):
                    for px in range(8):
                        color_idx = t_pixels[py][px]
                        if color_idx > 0: # 0 is transparent
                            r = palette[color_idx*3]
                            g = palette[color_idx*3+1]
                            b = palette[color_idx*3+2]
                            pixels[tx*8 + px, ty*8 + py] = (r, g, b, 255)
                offset += 32
                
        return img

    def dump_raw_tilesheet(self, graphics_addr, palette, out_dir, anim_name, max_tiles=100):
        img_w = 8 * 8
        img_h = ((max_tiles + 7) // 8) * 8
        if img_h == 0: img_h = 8
        img = Image.new('P', (img_w, img_h), 0)
        img.putpalette(palette)
        pixels = img.load()
        
        offset = graphics_addr - 0x08000000
        for i in range(max_tiles):
            if offset >= len(self.rom): break
            tx = (i % 8) * 8
            ty = (i // 8) * 8
            t_pixels = self.decode_tile_4bpp(offset)
            for py in range(8):
                for px in range(8):
                    pixels[tx + px, ty + py] = t_pixels[py][px]
            offset += 32
            
        img.save(os.path.join(out_dir, f"{anim_name}_raw_tiles.png"))

    def dump_animation(self, anim_id, graphics_addr, palette_addr, out_dir, anim_name):
        script_addr = self.get_script_pointer(anim_id)
        graphic_id = self.get_graphic_id(anim_id)
        
        print(f"[{anim_name}] Dumping ID {hex(anim_id)} (Graphic ID: {graphic_id}) -> Script at 0x{script_addr:08X}")
        os.makedirs(out_dir, exist_ok=True)
        
        frames_meta = self.parse_script(script_addr)
        palette = self.load_palette(palette_addr - 0x08000000)
        
        self.dump_raw_tilesheet(graphics_addr, palette, out_dir, anim_name, max_tiles=6 * len(frames_meta))
        
        # Render GIF
        images = []
        for i, frame in enumerate(frames_meta):
            canvas = Image.new('RGBA', (128, 128), (0,0,0,0))
            if frame['type'] == 'metasprite':
                oam = frame['oam']
                # Draw the OAM using simulated sequential tiles
                img = self.render_oam(graphics_addr, oam, palette, tile_offset=(i*4) % 100) # Fake tile progression
                if img:
                    # Apply X/Y offsets to center (64, 64)
                    paste_x = 64 + oam['x']
                    paste_y = 64 + oam['y']
                    canvas.paste(img, (paste_x, paste_y), img)
            elif frame['type'] == 'direct':
                # Direct frames just draw a big 64x64 generic OAM
                oam = {'shape': 0, 'size': 3, 'x': -32, 'y': -32}
                img = self.render_oam(graphics_addr, oam, palette, tile_offset=frame['frame_idx']*32)
                if img:
                    canvas.paste(img, (64 - 32, 64 - 32), img)
                    
            images.append(canvas)
            
        if images:
            out_gif = os.path.join(out_dir, f"{anim_name}.gif")
            images[0].save(out_gif, save_all=True, append_images=images[1:], duration=100, loop=0, disposal=2)
            print(f"[{anim_name}] Rendered GIF to {out_gif}")
        
        metadata = {
            'anim_name': anim_name,
            'id': hex(anim_id),
            'graphic_id': graphic_id,
            'script_addr': hex(script_addr),
            'graphics_addr': hex(graphics_addr),
            'palette_addr': hex(palette_addr),
            'frames': frames_meta
        }
        
        with open(os.path.join(out_dir, f"{anim_name}_meta.json"), 'w') as f:
            json.dump(metadata, f, indent=4)

if __name__ == '__main__':
    ROM_PATH = r"j:\scratch\Harvest Moon - Friends of Mineral Town.gba"
    KAREN_GRAPHICS = 0x0862329C
    KAREN_PALETTE = 0x08662AC0
    
    dumper = SymphonyDumper(ROM_PATH)
    dumper.dump_animation(0x10, KAREN_GRAPHICS, KAREN_PALETTE, "j:/scratch/symphony_dump", "Bee_Test_ID_0x10")
    dumper.dump_animation(0x232, KAREN_GRAPHICS, KAREN_PALETTE, "j:/scratch/symphony_dump", "Popuri_Test_ID_0x232")
    dumper.dump_animation(0x87F, KAREN_GRAPHICS, KAREN_PALETTE, "j:/scratch/symphony_dump", "Monkey_Relax_ID_0x87F")

