import os
import csv
import struct
from PIL import Image

# ═══════════════════════════════════════════════════════════════════
#  SYMPHONY METASPRITE ENGINE - EXTRACTOR CANÓNICO FoMT GBA
#  Bases maestras verificadas en ROM limpia:
#  - SPRITE_TILES_BASE = 0x085A33FC (Todos los tiles 4bpp de personajes)
#  - SPRITE_PAL_BASE   = 0x08661DC0 (Tabla maestra de paletas BGR555)
#  - FRAME_ARRAY_BASE  = 0x0858E20C (16 bytes por FrameStruct)
#  - OAM_ARRAY_BASE    = 0x08599E20 (8 bytes por OAM nativo GBA)
#  - ANIM_TABLE_BASE   = 0x0858BA2C (Header de animaciones)
#  - SCRIPT_BASE       = 0x08663208 (Scripts secuenciales de frames)
# ═══════════════════════════════════════════════════════════════════

SPRITE_TILES_BASE = 0x5A33FC
SPRITE_PAL_BASE = 0x661DC0
FRAME_ARRAY_BASE = 0x58E20C
OAM_ARRAY_BASE = 0x599E20
ANIM_TABLE_BASE = 0x58BA2C
SCRIPT_BASE = 0x663208

OAM_DIMS = {
    (0,0):(8,8),(0,1):(16,16),(0,2):(32,32),(0,3):(64,64),
    (1,0):(16,8),(1,1):(32,8),(1,2):(32,16),(1,3):(64,32),
    (2,0):(8,16),(2,1):(8,32),(2,2):(16,32),(2,3):(32,64)
}

class SymphonyExtractor:
    def __init__(self, rom_path, anim_csv_path):
        with open(rom_path, 'rb') as f:
            self.rom = f.read()
        self.animations = self._load_animations(anim_csv_path)

    def _load_animations(self, csv_path):
        anims = []
        if not os.path.exists(csv_path): return anims
        with open(csv_path, 'r', encoding='utf-8') as f:
            r = csv.reader(f)
            next(r)
            for row in r:
                if row and len(row) > 1 and row[1].strip():
                    name = row[0].strip()
                    anim_id = int(row[1], 16)
                    anims.append((anim_id, name))
        return anims

    def decode_palette(self, pal_idx):
        pal = []
        off = SPRITE_PAL_BASE + pal_idx * 32
        for i in range(16):
            if off + i*2 + 2 <= len(self.rom):
                c = struct.unpack_from('<H', self.rom, off + i*2)[0]
                r = (c & 0x1F) << 3
                g = ((c >> 5) & 0x1F) << 3
                b = ((c >> 10) & 0x1F) << 3
                pal.append((r, g, b, 255 if i > 0 else 0))
            else:
                pal.append((0, 0, 0, 0))
        return pal

    def decode_tile(self, tile_idx):
        off = SPRITE_TILES_BASE + tile_idx * 32
        px = []
        for y in range(8):
            for x in range(4):
                if off + y*4 + x < len(self.rom):
                    b = self.rom[off + y*4 + x]
                    px.append(b & 0x0F)
                    px.append(b >> 4)
                else:
                    px.extend([0, 0])
        return px

    def render_frame(self, frame_idx):
        frame_off = FRAME_ARRAY_BASE + frame_idx * 16
        if frame_off + 16 > len(self.rom):
            return None

        fields = struct.unpack_from('<HHHHHHHH', self.rom, frame_off)
        oam_count = fields[0]
        oam_offset = fields[1]
        gfx_off_tiles = fields[3]
        pal_idx = fields[5]

        if oam_count == 0 or oam_count > 64:
            return None

        pal = self.decode_palette(pal_idx)
        canvas = Image.new('RGBA', (64, 64), (0,0,0,0))
        origin_x, origin_y = 32, 48

        for p_i in range(oam_count):
            part_off = OAM_ARRAY_BASE + (oam_offset + p_i) * 8
            if part_off + 8 > len(self.rom): continue

            attr0, attr1, attr2, attr3 = struct.unpack_from('<hhhh', self.rom, part_off)
            y = attr0 & 0xFF
            if y > 127: y -= 256
            shape = (attr0 >> 14) & 3

            x = attr1 & 0x1FF
            if x > 255: x -= 512
            size = (attr1 >> 14) & 3
            h_flip = (attr1 >> 12) & 1
            v_flip = (attr1 >> 13) & 1
            tile_rel = attr2 & 0x3FF

            final_tile = gfx_off_tiles + tile_rel
            w, h = OAM_DIMS.get((shape, size), (8,8))
            w_tiles = w // 8
            h_tiles = h // 8

            sub = Image.new('RGBA', (w, h), (0,0,0,0))
            sub_pix = sub.load()

            t = 0
            for ty in range(h_tiles):
                for tx in range(w_tiles):
                    pixels = self.decode_tile(final_tile + t)
                    for py in range(8):
                        for px in range(8):
                            c_idx = pixels[py*8 + px]
                            if c_idx > 0:
                                sub_pix[tx*8 + px, ty*8 + py] = pal[c_idx]
                    t += 1

            if h_flip: sub = sub.transpose(Image.FLIP_LEFT_RIGHT)
            if v_flip: sub = sub.transpose(Image.FLIP_TOP_BOTTOM)

            canvas.paste(sub, (origin_x + x, origin_y + y), sub)

        return canvas

    def extract_animation(self, anim_id, name, out_dir_gifs, out_dir_sheets):
        anim_off = ANIM_TABLE_BASE + anim_id * 4
        if anim_off + 4 > len(self.rom):
            return False

        val = struct.unpack_from('<I', self.rom, anim_off)[0]
        frame_count = val & 0xFFFF
        script_offset = val >> 16
        script_off = SCRIPT_BASE + script_offset * 4

        if script_off >= len(self.rom) or frame_count == 0 or frame_count > 128:
            return False

        frames = []
        durations = []
        unique_frames = []
        seen = set()

        for i in range(frame_count):
            if script_off + i*4 + 4 > len(self.rom): break
            f_idx, wait_f = struct.unpack_from('<HH', self.rom, script_off + i * 4)
            canvas = self.render_frame(f_idx)
            if canvas:
                frames.append(canvas)
                durations.append(max(20, int(wait_f * 16.6)))
                h_b = canvas.tobytes()
                if h_b not in seen:
                    seen.add(h_b)
                    unique_frames.append(canvas)

        if not frames:
            return False

        os.makedirs(out_dir_gifs, exist_ok=True)
        os.makedirs(out_dir_sheets, exist_ok=True)

        clean_name = "".join(c if c not in '\\/:*?"<>|' else '_' for c in name)
        gif_path = os.path.join(out_dir_gifs, f'{clean_name}.gif')
        frames[0].save(gif_path, save_all=True, append_images=frames[1:], duration=durations, loop=0, disposal=2)

        # Spritesheet
        if unique_frames:
            cols = min(8, len(unique_frames))
            rows = (len(unique_frames) + cols - 1) // cols
            sheet = Image.new('RGBA', (cols * 64, rows * 64), (0,0,0,0))
            for idx_f, f_img in enumerate(unique_frames):
                cx = (idx_f % cols) * 64
                cy = (idx_f // cols) * 64
                sheet.paste(f_img, (cx, cy))
            sheet_path = os.path.join(out_dir_sheets, f'{clean_name}_sheet.png')
            sheet.save(sheet_path)

        return True

    def extract_all(self, out_dir_gifs, out_dir_sheets):
        count = 0
        for anim_id, name in self.animations:
            if self.extract_animation(anim_id, name, out_dir_gifs, out_dir_sheets):
                count += 1
        return count

if __name__ == '__main__':
    ROM_PATH = r'J:\Laboratorio\Repositorios\fomt virgen.gba'
    ANIM_CSV = r'J:\Laboratorio\FOMT_Studio\Banco_de_Datos\Cilixes\fomt\Fomt_Animations.csv'
    OUT_GIFS = r'J:\Laboratorio\Dumps\Symphony_Metasprites_Canon\gifs'
    OUT_SHEETS = r'J:\Laboratorio\Dumps\Symphony_Metasprites_Canon\sheets'

    extractor = SymphonyExtractor(ROM_PATH, ANIM_CSV)
    total = extractor.extract_all(OUT_GIFS, OUT_SHEETS)
    print(f'SymphonyExtractor: {total} animaciones canónicas extraídas exitosamente.')
