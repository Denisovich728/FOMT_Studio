import os
import struct
from PIL import Image

class MetaspriteVM:
    def __init__(self, rom_path):
        with open(rom_path, 'rb') as f:
            self.rom = f.read()
            
    def parse_script(self, addr):
        offset = addr - 0x08000000
        frames = []
        last_cmd = None
        
        while True:
            b0 = self.rom[offset]
            offset += 1
            
            if b0 == 0xBD:
                break
                
            cmd = b0
            args = []
            
            if b0 < 0x80:
                # Inherit last command
                cmd = last_cmd
                args.append(b0)
                args.append(self.rom[offset])
                offset += 1
            elif 0x80 <= b0 <= 0xB0:
                # Wait command
                delay = self.get_wait_frames(b0)
                if frames:
                    frames[-1]['delay'] += delay
                continue
            elif b0 == 0xB3:
                # Jump command (infinite loop)
                # Next 4 bytes are the pointer
                pointer_bytes = self.rom[offset:offset+4]
                jump_addr = struct.unpack('<I', pointer_bytes)[0]
                print(f"Encountered loop jump to 0x{jump_addr:08X}")
                break # We stop here since we completed one cycle
            elif 0xB1 <= b0 <= 0xCE:
                # Other Logic commands
                last_cmd = b0
                continue
            elif b0 >= 0xCF:
                # Draw command
                args.append(self.rom[offset])
                offset += 1
                args.append(self.rom[offset])
                offset += 1
                last_cmd = b0
                
            if cmd >= 0xCF:
                frames.append({
                    'cmd': cmd,
                    'arg1': args[0],
                    'arg2': args[1],
                    'delay': 0
                })
                
        return frames

    def get_wait_frames(self, cmd):
        # Look up wait frames from LUT at 0x08139CFC
        lut_offset = 0x08139CFC - 0x08000000
        idx = cmd - 0x80
        return self.rom[lut_offset + idx]

class SpriteRenderer:
    def __init__(self, rom_data, palette_addr):
        self.rom = rom_data
        
        # Load 16 colors from ROM (BGR555 format)
        self.palette = []
        pal_data = self.rom[palette_addr : palette_addr + 32]
        for i in range(16):
            c = struct.unpack_from('<H', pal_data, i*2)[0]
            r = (c & 0x1F) * 8
            g = ((c >> 5) & 0x1F) * 8
            b = ((c >> 10) & 0x1F) * 8
            self.palette.extend([r, g, b])
            
    def decode_tile_4bpp(self, offset):
        tile = []
        for y in range(8):
            row = []
            for x in range(4):
                byte = self.rom[offset + y * 4 + x]
                row.append(byte & 0x0F)
                row.append((byte >> 4) & 0x0F)
            tile.append(row)
        return tile

    def render_part(self, tile_index, width_tiles, height_tiles):
        img = Image.new('P', (width_tiles * 8, height_tiles * 8))
        img.putpalette(self.palette)
        pixels = img.load()
        
        current_tile = tile_index
        for ty in range(height_tiles):
            for tx in range(width_tiles):
                tile_offset = current_tile * 32
                tile_pixels = self.decode_tile_4bpp(tile_offset)
                
                for y in range(8):
                    for x in range(8):
                        pixels[tx * 8 + x, ty * 8 + y] = tile_pixels[y][x]
                
                current_tile += 1
        return img

    def assemble_frame(self, graphics_base, frame_idx):
        # User discovered layout: 16x16 (4 tiles) and 8x16 (2 tiles) = 6 tiles total
        base_tile_addr = graphics_base + (frame_idx * 6 * 32)
        
        # Part 1: 16x16 (2x2 tiles)
        part1 = self.render_part(base_tile_addr // 32, 2, 2)
        
        # Part 2: 8x16 (1x2 tiles)
        part2 = self.render_part((base_tile_addr + 4 * 32) // 32, 1, 2)
        
        # Combine onto a 16x32 canvas (character is 16 wide, 32 tall)
        # The 8x16 legs are centered under the 16x16 body
        canvas = Image.new('P', (16, 32))
        canvas.putpalette(self.palette)
        canvas.paste(part1, (0, 0))
        canvas.paste(part2, (4, 16)) # Centered horizontally
        
        # Make transparent color 0
        canvas.info['transparency'] = 0
        return canvas

def extract_animation(rom_path, script_addr, graphics_addr, palette_addr, output_dir, anim_name):
    print(f"Extracting '{anim_name}' from 0x{script_addr:08X}...")
    
    vm = MetaspriteVM(rom_path)
    frames_meta = vm.parse_script(script_addr)
    
    renderer = SpriteRenderer(vm.rom, palette_addr - 0x08000000)
    
    os.makedirs(output_dir, exist_ok=True)
    images = []
    durations = []
    
    # We map each unique drawing command to a sequential frame graphic
    # If the script re-uses a frame, we re-use the image
    unique_draws = []
    
    for meta in frames_meta:
        # Create a signature for the frame's appearance
        sig = (meta['cmd'], meta['arg1'])
        
        if sig not in unique_draws:
            unique_draws.append(sig)
            
        frame_idx = unique_draws.index(sig)
        
        img = renderer.assemble_frame(graphics_addr - 0x08000000, frame_idx)
        images.append(img)
        
        # GBA runs at ~60fps, so 1 frame = ~16.6ms
        durations.append(meta['delay'] * 16.6)
        
        img.save(os.path.join(output_dir, f"{anim_name}_{len(images)-1:03d}.png"))
        
    # Save GIF
    gif_path = os.path.join(output_dir, f"{anim_name}.gif")
    if images:
        images[0].save(
            gif_path,
            save_all=True,
            append_images=images[1:],
            duration=durations,
            loop=0,
            transparency=0,
            disposal=2 # clear frame before next
        )
        print(f"Successfully generated GIF: {gif_path}")
        print(f"Total frames: {len(images)}")
    else:
        print("No drawing frames found in script!")

if __name__ == "__main__":
    ROM = r"j:\scratch\Harvest Moon - Friends of Mineral Town.gba"
    OUT = r"j:\Repositorios\fomt_studio\output\karen"
    
    # Karen walk down animation
    KAREN_SCRIPT = 0x082A368E
    KAREN_GRAPHICS = 0x0862329C
    KAREN_PALETTE = 0x08662AC0
    
    extract_animation(ROM, KAREN_SCRIPT, KAREN_GRAPHICS, KAREN_PALETTE, OUT, "karen_walk_down")
