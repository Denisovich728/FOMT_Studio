import struct
import argparse
import os
import sys
from PIL import Image, ImageDraw

def gba_to_rgb(color):
    r = (color & 0x1F) * 8
    g = ((color >> 5) & 0x1F) * 8
    b = ((color >> 10) & 0x1F) * 8
    return (r, g, b)

class FoMTSpriteExtractor:
    def __init__(self, rom_path, tile_base, pal_base, oam_geom_base):
        with open(rom_path, 'rb') as f:
            self.rom = f.read()
            
        self.tile_base = tile_base
        self.pal_base = pal_base
        self.oam_geom_base = oam_geom_base

    def get_anim_info(self, anim_id):
        entry_base = 0x58BA2C + anim_id * 4
        graphic_id, script_offset = struct.unpack('<HH', self.rom[entry_base:entry_base+4])
        return graphic_id, script_offset

    def read_script(self, script_offset):
        script_rom = 0x663208 + script_offset * 4
        frames = []
        i = 0
        while True:
            base = script_rom + i * 4
            if base + 4 > len(self.rom): break
            frame_id, delay = struct.unpack('<HH', self.rom[base:base+4])
            if frame_id == 0xFFFF:
                break
            frames.append({'frame_id': frame_id, 'delay': delay})
            if frame_id == 0 and delay == 0 and i > 4: # safety bailout
                break
            i += 1
        return frames

    def get_frame_entry(self, frame_id):
        fe_base = 0x58E20C + frame_id * 16
        fe = struct.unpack('<8H', self.rom[fe_base:fe_base+16])
        return {
            'oam_piece_count': fe[0],
            'oam_geom_idx': fe[1],
            'r6_param': fe[2],
            'tile_offset': fe[3],
            'r5_param': fe[4],
            'pal_idx': fe[5],
            'r8_param': fe[6],
            'flip_param': fe[7]
        }

    def decode_4bpp_tile(self, data):
        pixels = []
        for b in data:
            pixels.append(b & 0xF)
            pixels.append(b >> 4)
        return pixels

    def get_palette(self, pal_idx):
        pal_addr = self.pal_base + pal_idx * 32
        pal_rom = pal_addr - 0x08000000
        if pal_rom < 0 or pal_rom + 32 > len(self.rom):
            return [(0,0,0,255)] * 16
        
        pal_data = self.rom[pal_rom:pal_rom+32]
        colors = []
        for i in range(16):
            c = struct.unpack('<H', pal_data[i*2:i*2+2])[0]
            rgb = gba_to_rgb(c)
            # Make color 0 transparent
            if i == 0:
                colors.append((0, 0, 0, 0))
            else:
                colors.append((rgb[0], rgb[1], rgb[2], 255))
        return colors

    def get_oam_geometry(self, oam_geom_idx, count):
        oam_addr = self.oam_geom_base + oam_geom_idx * 8
        oam_rom = oam_addr - 0x08000000
        pieces = []
        
        for i in range(count):
            base = oam_rom + i * 8
            if base + 8 > len(self.rom): break
            # Heuristic parsing for pieces. 
            # We will use the pure python math as fallback if Unicorn isn't used.
            x, y, w, h = struct.unpack('<4h', self.rom[base:base+8])
            # Assuming simple mapping for now until we emulate the true OAM compiler
            # Let's extract raw bytes and see
            raw = struct.unpack('<4H', self.rom[base:base+8])
            
            # Decoded GBA OAM attributes
            attr0 = raw[0]
            attr1 = raw[1]
            attr2 = raw[2]
            
            # This logic mimics GBA OAM compiler behavior
            y_off = attr0 & 0xFF
            if y_off >= 128: y_off -= 256
            
            x_off = attr1 & 0x1FF
            if x_off >= 256: x_off -= 512
            
            shape = (attr0 >> 14) & 3
            size = (attr1 >> 14) & 3
            
            # Shape mapping
            w_px, h_px = 8, 8
            if shape == 0: # Square
                w_px = [8, 16, 32, 64][size]
                h_px = w_px
            elif shape == 1: # Horizontal
                w_px = [16, 32, 32, 64][size]
                h_px = [8, 8, 16, 32][size]
            elif shape == 2: # Vertical
                w_px = [8, 8, 16, 32][size]
                h_px = [16, 32, 32, 64][size]
            
            tile_off = attr2 & 0x3FF
            
            pieces.append({
                'x': x_off, 'y': y_off, 'w': w_px, 'h': h_px, 
                'tile_off': tile_off, 'attr0': attr0, 'attr1': attr1, 'attr2': attr2
            })
            
        return pieces

    def render_frame(self, frame_id):
        fe = self.get_frame_entry(frame_id)
        
        pieces = self.get_oam_geometry(fe['oam_geom_idx'], fe['oam_piece_count'])
        palette = self.get_palette(fe['pal_idx'])
        
        # Base tile offset for this frame
        base_tile_addr = self.tile_base + fe['tile_offset'] * 32
        base_tile_rom = base_tile_addr - 0x08000000
        
        # Create a large enough canvas
        canvas = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
        center_x, center_y = 128, 128
        
        for piece in pieces:
            # We assume piece tile offset is relative to frame base tile offset
            # Or is it absolute? The draw routine sets `r4 = tile_base + fe[3]*32`.
            # Then the OAM compiler uses r4 + piece['tile_off']*32.
            piece_tile_rom = base_tile_rom + piece['tile_off'] * 32
            
            w_tiles = piece['w'] // 8
            h_tiles = piece['h'] // 8
            
            img_piece = Image.new('RGBA', (piece['w'], piece['h']), (0,0,0,0))
            
            for ty in range(h_tiles):
                for tx in range(w_tiles):
                    tile_rom = piece_tile_rom + (ty * w_tiles + tx) * 32
                    if tile_rom < 0 or tile_rom + 32 > len(self.rom): continue
                    
                    tile_data = self.rom[tile_rom : tile_rom + 32]
                    pixels = self.decode_4bpp_tile(tile_data)
                    
                    for py in range(8):
                        for px in range(8):
                            c_idx = pixels[py * 8 + px]
                            if c_idx != 0:
                                img_piece.putpixel((tx*8 + px, ty*8 + py), palette[c_idx])
                                
            # Blit onto canvas
            canvas.alpha_composite(img_piece, (center_x + piece['x'], center_y + piece['y']))
            
        # Crop canvas to content
        bbox = canvas.getbbox()
        if bbox:
            canvas = canvas.crop((bbox[0]-4, bbox[1]-4, bbox[2]+4, bbox[3]+4))
        
        return canvas

    def dump_animation(self, anim_id, out_dir):
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
            
        graphic_id, script_offset = self.get_anim_info(anim_id)
        print(f"Animation 0x{anim_id:04X}: Graphic ID = {graphic_id}")
        
        frames = self.read_script(script_offset)
        print(f"Found {len(frames)} frames")
        
        images = []
        durations = []
        
        for i, frame in enumerate(frames):
            img = self.render_frame(frame['frame_id'])
            # Delay is typically in standard GBA frames (1/60th sec).
            # If it's a different unit, we can adjust.
            dur_ms = frame['delay'] * (1000 // 60)
            if dur_ms == 0: dur_ms = 100
            
            img_path = os.path.join(out_dir, f"frame_{i:02d}.png")
            img.save(img_path)
            images.append(img)
            durations.append(dur_ms)
            
        if images:
            gif_path = os.path.join(out_dir, f"anim_{anim_id:04X}.gif")
            images[0].save(
                gif_path, 
                save_all=True, 
                append_images=images[1:], 
                duration=durations, 
                loop=0,
                disposal=2
            )
            print(f"Saved GIF to {gif_path}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--rom', required=True)
    parser.add_argument('--anim-id', type=lambda x: int(x, 16), required=True)
    parser.add_argument('--tile-base', type=lambda x: int(x, 16), required=True)
    parser.add_argument('--pal-base', type=lambda x: int(x, 16), required=True)
    parser.add_argument('--oam-geom-base', type=lambda x: int(x, 16), required=True)
    parser.add_argument('--out', default='dump')
    
    args = parser.parse_args()
    
    extractor = FoMTSpriteExtractor(args.rom, args.tile_base, args.pal_base, args.oam_geom_base)
    extractor.dump_animation(args.anim_id, args.out)
