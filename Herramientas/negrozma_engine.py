import struct
import os
from PIL import Image

class NegrozmaEngine:
    def __init__(self, rom_path=None, rom_data=None):
        self.rom_path = rom_path
        if rom_data is not None:
            self.rom = bytearray(rom_data)
        elif rom_path is not None:
            with open(rom_path, 'rb') as f:
                self.rom = bytearray(f.read())
        else:
            raise ValueError("Debes proveer rom_path o rom_data")

        # Las tablas maestras extraídas de la memoria
        self.OAM_ARRAY_BASE = 0x08599E20

    def get_rom_address(self, pointer):
        if pointer >= 0x08000000:
            return pointer - 0x08000000
        return pointer

    def parse_frame_struct(self, frame_array_ptr, frame_index):
        offset = self.get_rom_address(frame_array_ptr) + (frame_index * 16)
        frame_data = self.rom[offset : offset + 16]
        fields = struct.unpack('<HHHHHHHH', frame_data)
        return {
            "oam_count": fields[0],
            "oam_offset": fields[1],
            "gfx_size_tiles": fields[2],
            "gfx_offset_tiles": fields[3],
            "pal_offset": fields[5],
        }

    def resolve_graphics_pointers(self, gfx_base_ptr, pal_base_ptr, frame_struct):
        final_gfx_ptr = gfx_base_ptr + (frame_struct["gfx_offset_tiles"] * 32)
        final_pal_ptr = pal_base_ptr + (frame_struct["pal_offset"] * 32)
        return final_gfx_ptr, final_pal_ptr

    def extract_palette(self, pal_ptr):
        offset = self.get_rom_address(pal_ptr)
        pal_data = self.rom[offset : offset + 32]
        colors = []
        for i in range(16):
            c = struct.unpack_from('<H', pal_data, i*2)[0]
            r = (c & 0x1F) << 3
            g = ((c >> 5) & 0x1F) << 3
            b = ((c >> 10) & 0x1F) << 3
            colors.append((r, g, b, 255 if i > 0 else 0))
        return colors

    def extract_tiles(self, gfx_ptr, num_tiles):
        offset = self.get_rom_address(gfx_ptr)
        gfx_data = self.rom[offset : offset + (num_tiles * 32)]
        tiles = []
        for t in range(num_tiles):
            tile_pixels = []
            for y in range(8):
                for x in range(4): # 4 bytes por fila (8 pixels a 4bpp)
                    byte = gfx_data[t*32 + y*4 + x]
                    tile_pixels.append(byte & 0x0F)
                    tile_pixels.append(byte >> 4)
            tiles.append(tile_pixels)
        return tiles

    def parse_oam(self, oam_count, oam_offset):
        offset = self.get_rom_address(self.OAM_ARRAY_BASE) + (oam_offset * 8)
        oam_entries = []
        for i in range(oam_count):
            oam_data = self.rom[offset + i*8 : offset + i*8 + 8]
            attr0, attr1, attr2, attr3 = struct.unpack('<hhhh', oam_data)
            
            y = attr0 & 0xFF
            if y > 127: y -= 256 # 8-bit signed
            
            shape = (attr0 >> 14) & 3
            
            x = attr1 & 0x1FF
            if x > 255: x -= 512 # 9-bit signed
            
            size = (attr1 >> 14) & 3
            tile_idx = attr2 & 0x3FF
            h_flip = (attr1 >> 12) & 1
            v_flip = (attr1 >> 13) & 1
            
            # Dimensiones
            w, h = 8, 8
            if shape == 0: # Square
                if size == 1: w, h = 16, 16
                elif size == 2: w, h = 32, 32
                elif size == 3: w, h = 64, 64
            elif shape == 1: # Horizontal
                if size == 0: w, h = 16, 8
                elif size == 1: w, h = 32, 8
                elif size == 2: w, h = 32, 16
                elif size == 3: w, h = 64, 32
            elif shape == 2: # Vertical
                if size == 0: w, h = 8, 16
                elif size == 1: w, h = 8, 32
                elif size == 2: w, h = 16, 32
                elif size == 3: w, h = 32, 64
                
            oam_entries.append({
                "x": x, "y": y, "w": w, "h": h,
                "tile_idx": tile_idx,
                "h_flip": h_flip, "v_flip": v_flip
            })
        return oam_entries

    def compose_sprite(self, tiles, palette, oam_entries):
        # Lienzo base de 256x256 para evitar recortes en sprites gigantes (caballos, etc)
        canvas_w, canvas_h = 256, 256
        # El origen X,Y es el centro del canvas
        origin_x, origin_y = 128, 128
        
        img = Image.new('RGBA', (canvas_w, canvas_h), (0,0,0,0))
        pixels = img.load()
        
        for oam in oam_entries:
            w_tiles = oam["w"] // 8
            h_tiles = oam["h"] // 8
            start_tile = oam["tile_idx"]
            
            for ty in range(h_tiles):
                for tx in range(w_tiles):
                    # Asumiendo 1D tile mapping
                    tile_id = start_tile + (ty * w_tiles) + tx
                    if tile_id >= len(tiles):
                        continue
                        
                    tile = tiles[tile_id]
                    
                    for py in range(8):
                        for px in range(8):
                            color_idx = tile[py * 8 + px]
                            if color_idx == 0: continue # Transparente
                            
                            # Aplicar flips en todo el sprite, no solo por tile
                            flip_tx = (w_tiles - 1 - tx) if oam["h_flip"] else tx
                            flip_ty = (h_tiles - 1 - ty) if oam["v_flip"] else ty
                            
                            draw_x = (flip_tx * 8) + (7 - px if oam["h_flip"] else px)
                            draw_y = (flip_ty * 8) + (7 - py if oam["v_flip"] else py)
                            
                            final_x = origin_x + oam["x"] + draw_x
                            final_y = origin_y + oam["y"] + draw_y
                            
                            if 0 <= final_x < canvas_w and 0 <= final_y < canvas_h:
                                pixels[final_x, final_y] = palette[color_idx]
        return img

    def parse_animation_script(self, anim_id):
        anim_table_base = 0x0858BA2C
        offset = self.get_rom_address(anim_table_base) + (anim_id * 4)
        pointer = struct.unpack_from('<I', self.rom, offset)[0]
        
        frame_count = pointer & 0xFFFF
        script_offset = pointer >> 16
        
        script_addr = 0x08663208 + (script_offset * 4)
        script_rom_offset = self.get_rom_address(script_addr)
        
        script_entries = []
        for i in range(frame_count):
            frame_index, wait_frames = struct.unpack_from('<HH', self.rom, script_rom_offset + (i * 4))
            script_entries.append({
                "frame_index": frame_index,
                "wait_frames": wait_frames
            })
            
        return script_entries

    def export_animation(self, anim_id, frame_array_ptr, gfx_base_ptr, pal_base_ptr, out_dir, basename):
        script = self.parse_animation_script(anim_id)
        
        frames = []
        durations = []
        
        for entry in script:
            frame = self.parse_frame_struct(frame_array_ptr, entry["frame_index"])
            final_gfx, final_pal = self.resolve_graphics_pointers(gfx_base_ptr, pal_base_ptr, frame)
            
            palette = self.extract_palette(final_pal)
            tiles = self.extract_tiles(final_gfx, frame["gfx_size_tiles"])
            oam_entries = self.parse_oam(frame["oam_count"], frame["oam_offset"])
            
            img = self.compose_sprite(tiles, palette, oam_entries)
            frames.append(img)
            
            # GBA is ~59.7 FPS. Each wait_frame is ~16.74 ms.
            # If wait_frames is 0 (shouldn't happen in a proper wait command, but just in case), default to 16ms
            wait_frames = max(1, entry["wait_frames"])
            durations.append(int(wait_frames * 16.74))
            
        # 1. Guardar GIF animado
        gif_path = os.path.join(out_dir, f"{basename}.gif")
        if frames:
            frames[0].save(
                gif_path,
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                loop=0,
                disposal=2, # Clear transparent background
                transparency=0
            )
            print(f"Animación {hex(anim_id)} exportada como GIF en: {gif_path}")
            
        # 2. Guardar Sprite Sheet Horizontal
        if frames:
            w, h = frames[0].size
            spritesheet = Image.new('RGBA', (w * len(frames), h), (0,0,0,0))
            for i, f in enumerate(frames):
                spritesheet.paste(f, (i * w, 0))
                
            sheet_path = os.path.join(out_dir, f"{basename}_sheet.png")
            spritesheet.save(sheet_path)
            print(f"Animación {hex(anim_id)} exportada como Sprite Sheet en: {sheet_path}")

    def dump_composed_frame(self, frame_array_ptr, gfx_base_ptr, pal_base_ptr, frame_index, out_path):
        frame = self.parse_frame_struct(frame_array_ptr, frame_index)
        final_gfx, final_pal = self.resolve_graphics_pointers(gfx_base_ptr, pal_base_ptr, frame)
        
        palette = self.extract_palette(final_pal)
        tiles = self.extract_tiles(final_gfx, frame["gfx_size_tiles"])
        oam_entries = self.parse_oam(frame["oam_count"], frame["oam_offset"])
        
        img = self.compose_sprite(tiles, palette, oam_entries)
        img.save(out_path)
        print(f"Frame compuesto {frame_index} dumpeado en {out_path}!")

    def batch_export_all_animations(self, csv_path, out_dir):
        import csv
        
        FRAME_ARRAY_PTR = 0x0858E20C
        GFX_BASE = 0x085A33FC
        PAL_BASE = 0x08661DC0
        
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
            
        print(f"Iniciando extracción masiva de {csv_path} hacia {out_dir}")
        count = 0
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("Animation_Name")
                anim_id_str = row.get("Animation_ID")
                if not name or not anim_id_str: continue
                
                try:
                    anim_id = int(anim_id_str, 16) if anim_id_str.startswith('0x') else int(anim_id_str)
                    self.export_animation(anim_id, FRAME_ARRAY_PTR, GFX_BASE, PAL_BASE, out_dir, name)
                    count += 1
                except Exception as e:
                    print(f"Skipping {name} ({anim_id_str}) due to error: {e}")
                    
        print(f"Extracción finalizada. {count} animaciones procesadas.")

    def _closest_color(self, r, g, b, palette):
        best_dist = float('inf')
        best_idx = 0
        for i, (pr, pg, pb, pa) in enumerate(palette):
            if i == 0: continue # Transparente reservado
            dist = (r - pr)**2 + (g - pg)**2 + (b - pb)**2
            if dist < best_dist:
                best_dist = dist
                best_idx = i
        return best_idx

    def reinject_animation_sheet(self, anim_id, sheet_path):
        """
        Lee un spritesheet PNG editado y reinyecta sus gráficos a la ROM
        basándose en los OAMs originales de la animación.
        """
        FRAME_ARRAY_PTR = 0x0858E20C
        GFX_BASE = 0x085A33FC
        PAL_BASE = 0x08661DC0
        
        sheet = Image.open(sheet_path).convert('RGBA')
        script = self.parse_animation_script(anim_id)
        
        reinjected_frames = set()
        
        for i, entry in enumerate(script):
            frame_index = entry["frame_index"]
            if frame_index in reinjected_frames:
                continue # Evitar reinyectar el mismo frame repetido en la animación
                
            box = (i * 256, 0, (i + 1) * 256, 256)
            try:
                frame_img = sheet.crop(box)
            except Exception as e:
                print(f"⚠️ El sheet no tiene suficientes frames para la animación. {e}")
                break
                
            self._reinject_single_frame(frame_img, frame_index, FRAME_ARRAY_PTR, GFX_BASE, PAL_BASE)
            reinjected_frames.add(frame_index)
            print(f"✅ Frame {frame_index} reinyectado correctamente.")

    def _reinject_single_frame(self, frame_img, frame_index, frame_array_ptr, gfx_base_ptr, pal_base_ptr):
        frame = self.parse_frame_struct(frame_array_ptr, frame_index)
        final_gfx, final_pal = self.resolve_graphics_pointers(gfx_base_ptr, pal_base_ptr, frame)
        
        palette = self.extract_palette(final_pal)
        tiles = self.extract_tiles(final_gfx, frame["gfx_size_tiles"])
        oam_entries = self.parse_oam(frame["oam_count"], frame["oam_offset"])
        
        origin_x, origin_y = 128, 128
        
        # Iterar los OAMs y leer los pixeles correspondientes de frame_img
        for oam in oam_entries:
            w_tiles = oam["w"] // 8
            h_tiles = oam["h"] // 8
            start_tile = oam["tile_idx"]
            
            for ty in range(h_tiles):
                for tx in range(w_tiles):
                    tile_id = start_tile + (ty * w_tiles) + tx
                    if tile_id >= len(tiles):
                        continue
                        
                    new_tile = [0] * 64
                    for py in range(8):
                        for px in range(8):
                            flip_tx = (w_tiles - 1 - tx) if oam["h_flip"] else tx
                            flip_ty = (h_tiles - 1 - ty) if oam["v_flip"] else ty
                            
                            draw_x = (flip_tx * 8) + (7 - px if oam["h_flip"] else px)
                            draw_y = (flip_ty * 8) + (7 - py if oam["v_flip"] else py)
                            
                            final_x = origin_x + oam["x"] + draw_x
                            final_y = origin_y + oam["y"] + draw_y
                            
                            if 0 <= final_x < 256 and 0 <= final_y < 256:
                                r, g, b, a = frame_img.getpixel((final_x, final_y))
                                if a < 128:
                                    new_tile[py * 8 + px] = 0
                                else:
                                    # Encontrar índice de color más cercano en paleta
                                    new_tile[py * 8 + px] = self._closest_color(r, g, b, palette)
                            else:
                                new_tile[py * 8 + px] = 0
                                
                    tiles[tile_id] = new_tile
                    
        # Empacar los tiles nuevamente a 4bpp
        packed = bytearray()
        for t in tiles:
            for y in range(8):
                for x in range(0, 8, 2):
                    idx1 = t[y * 8 + x]
                    idx2 = t[y * 8 + x + 1]
                    byte = (idx1 & 0x0F) | ((idx2 & 0x0F) << 4)
                    packed.append(byte)
                    
        # Escribir a la memoria virtual de la ROM
        offset = self.get_rom_address(final_gfx)
        self.rom[offset : offset + len(packed)] = packed

    def save_rom(self, out_path=None):
        path = out_path if out_path else self.rom_path
        with open(path, 'wb') as f:
            f.write(self.rom)
        print(f"ROM guardada en {path}")

if __name__ == "__main__":
    rom_path = r"j:\scratch\Harvest Moon - Friends of Mineral Town.gba"
    engine = NegrozmaEngine(rom_path)
    
    FRAME_ARRAY_PTR = 0x0858E20C
    GFX_BASE = 0x085A33FC
    PAL_BASE = 0x08661DC0
    
    print("=== Negrozma Sprites Engine v2.0 (Animation Interpreter) ===")
    
    out_dir = r"C:\Users\Denis\.gemini\antigravity-ide\brain\c5e367b5-58c5-4d66-9173-0df464e12e3b"
    
    # Animaciones a probar: 
    # Popuri Caminando = 0x233
    # Popuri Parada = 0x22F
    # Popuri Hands Middle = 0x237
    animations_to_test = {
        "Popuri_Walking": 0x233,
        "Popuri_Stop": 0x22F,
        "Popuri_Hands_Middle": 0x237
    }
    
    for name, anim_id in animations_to_test.items():
        try:
            engine.export_animation(anim_id, FRAME_ARRAY_PTR, GFX_BASE, PAL_BASE, out_dir, name)
        except Exception as e:
            print(f"Error procesando animación {name}: {e}")
