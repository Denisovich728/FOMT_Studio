# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.6.5)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
import struct
import os
import sys
from Nucleos_de_Procesamiento.Nucleo_de_Datos.Utilidades.rutas import get_resource_path
import wave
import math
class SappyParser:
    """
    Motor nativo para procesar el motor de sonido M4A (Sappy) de GBA.
    Integra offsets de ingeniería inversa del HM FoMT (US) para localizar,
    categorizar y etiquetar correctamente las canciones y SFX.

    Fuente de offsets: TCRF / comunidad de RE de Harvest Moon FoMT.
    """
    # ─────────────────────────────────────────────────────────────────────
    # OFFSETS DE ASIGNACIÓN BGM (código ARM del FoMT US)
    # Cada entrada: rom_offset → (location_name, default_song_id)
    # El byte del song ID se lee como: data[offset+0] del halfword LE
    # ─────────────────────────────────────────────────────────────────────
    FOMT_US_BGM_OFFSETS = {
        0x0001DB12: ("Spring Farm Theme",   0x01),
        0x0001DB16: ("Summer Farm Theme",   0x02),
        0x0001DB1A: ("Autumn Farm Theme",   0x03),
        0x0001DB1E: ("Winter Farm Theme",   0x04),
        0x0001D9D0: ("Rain Noise",          0x0A),
        0x0001D9DE: ("Storm / Blizzard",    0x0B),
        0x0001DB22: ("Sea Noise (Beach)",   0x0C),
        0x0001DB38: ("Town Theme",          0x0D),
        0x0001DB3C: ("Night Noises",        0x0E),
    }

    # ─────────────────────────────────────────────────────────────────────
    # CATEGORÍAS DE SONG IDS CONOCIDOS (FoMT US)
    # ─────────────────────────────────────────────────────────────────────
    FOMT_US_SONG_CATEGORIES = {
        # BGM normales (usados durante gameplay)
        0x01: "BGM",   # Spring Farm
        0x02: "BGM",   # Summer Farm
        0x03: "BGM",   # Autumn Farm
        0x04: "BGM",   # Winter Farm
        0x05: "BGM",   # Mining
        0x06: "BGM",   # Festival
        0x07: "BGM",   # General / Misc
        0x09: "BGM",   # General / Misc
        0x0D: "BGM",   # Town
        0x0F: "BGM",   # Misc
        0x10: "BGM",   # Misc
        0x11: "BGM",   # Misc

        # Ambient / Noise
        0x0A: "AMBIENT",  # Rain
        0x0B: "AMBIENT",  # Storm / Blizzard
        0x0C: "AMBIENT",  # Sea
        0x0E: "AMBIENT",  # Night

        # Unused / Rare Cutscene — los interesantes para el modder
        0x08: "UNUSED",
        0x12: "UNUSED",
        0x13: "UNUSED",
        0x14: "UNUSED",
        0x15: "UNUSED",
        0x16: "UNUSED",
        0x17: "UNUSED",
        0x18: "UNUSED",
        0x19: "UNUSED",
        0x1A: "UNUSED",
    }

    # Título / Intro no son realmente BGM de gameplay
    SPECIAL_IDS = {
        0x00: "TITLE",
    }

    def __init__(self, proyecto):
        self.proyecto = proyecto
        self.songs = []
        self.bgm_assignments = []  # Resultado de scan_bgm_assignments()

    @property
    def is_mfomt(self):
        return getattr(self.proyecto, 'is_mfomt', False)

    @property
    def song_table_offset(self):
        return 0x13ABF0 if not self.is_mfomt else 0x144FF4

    # ═══════════════════════════════════════════════════════════════════
    # ESCANEO DE TABLA SAPPY (genérico)
    # ═══════════════════════════════════════════════════════════════════

    def scan_songs(self):
        """Escanea la tabla de canciones y extrae los encabezados básicos."""
        self.songs = []
        offset = self.song_table_offset

        for i in range(256):
            entry_ptr = self.read_rom_ptr(offset + (i * 8))
            if entry_ptr == 0 or entry_ptr > len(self.proyecto.base_rom_data):
                break

            song_info = self.parse_song_header(entry_ptr, i)
            if song_info:
                self.songs.append(song_info)

        # Enriquecer con categorías y asignaciones BGM
        self._enrich_songs()

        return self.songs

    def parse_song_header(self, header_offset, song_id):
        """Lee el encabezado de una canción (Pistas, Voicegroup, etc)."""
        data = self.proyecto.read_rom(header_offset, 12 + (16 * 4))
        if not data:
            return None

        num_tracks = data[0]
        if num_tracks == 0 or num_tracks > 16:
            return None

        voicegroup_ptr = struct.unpack("<I", data[4:8])[0] & 0x1FFFFFF

        tracks = []
        for i in range(num_tracks):
            t_ptr = struct.unpack("<I", data[8 + (i*4) : 12 + (i*4)])[0] & 0x1FFFFFF
            tracks.append(t_ptr)

        return {
            "id": song_id,
            "offset": header_offset,
            "tracks_count": num_tracks,
            "voicegroup_ptr": voicegroup_ptr,
            "track_pointers": tracks,
            "name": f"Song_{song_id:03d}",
            # Campos enriquecidos (se llenan en _enrich_songs)
            "category": "UNKNOWN",
            "used_by": [],
            "is_unused": False,
        }

    # ═══════════════════════════════════════════════════════════════════
    # LECTURA DE ASIGNACIONES BGM DESDE CÓDIGO ARM
    # ═══════════════════════════════════════════════════════════════════

    def read_bgm_assignment(self, rom_offset):
        """
        Lee el song ID asignado en un offset de código ARM.
        El patrón en ROM es un halfword LE: 0xXX20 donde XX es el song ID.
        Leemos el halfword y extraemos el byte alto como song ID.
        """
        data = self.proyecto.read_rom(rom_offset, 2)
        if len(data) < 2:
            return None
        hw = struct.unpack("<H", data)[0]
        # El patrón es 0xXX20 — el byte bajo es 0x20 (mov opcode fragment)
        # y el byte alto es el song ID
        if (hw & 0x00FF) == 0x20:
            return (hw >> 8) & 0xFF
        # Fallback: intentar leer el byte alto directamente
        return data[0]

    def scan_bgm_assignments(self):
        """
        Recorre la memoria entre 0x1D900 y 0x1DC00 buscando instrucciones
        mov r0, #SongID (0xXX20). Mantiene los nombres conocidos y agrega los
        nuevos encontrados dinámicamente.
        """
        self.bgm_assignments = []
        
        start_offset = 0x0001D900
        end_offset = 0x0001DC00
        
        # Primero poblamos los conocidos para facilitar lookup
        known_locations = {k: v[0] for k, v in self.FOMT_US_BGM_OFFSETS.items()}
        known_defaults = {k: v[1] for k, v in self.FOMT_US_BGM_OFFSETS.items()}

        for rom_offset in range(start_offset, end_offset, 2):
            data = self.proyecto.read_rom(rom_offset, 2)
            if len(data) < 2: continue
            
            hw = struct.unpack("<H", data)[0]
            if (hw & 0x00FF) == 0x20:  # mov r0, #XX
                song_id = (hw >> 8) & 0xFF
                
                # Ignorar si el song_id es absurdo (muy grande)
                if song_id > 0xA0 and song_id != 0xFF:
                    continue
                    
                loc_name = known_locations.get(rom_offset, f"Discovered_BGM_{rom_offset:X}")
                default_id = known_defaults.get(rom_offset, song_id)
                
                self.bgm_assignments.append({
                    "rom_offset": rom_offset,
                    "location": loc_name,
                    "default_song_id": default_id,
                    "current_song_id": song_id,
                    "is_modified": song_id != default_id,
                })

        return self.bgm_assignments

    # ═══════════════════════════════════════════════════════════════════
    # ENRIQUECIMIENTO DE METADATOS
    # ═══════════════════════════════════════════════════════════════════

    def _enrich_songs(self):
        """
        Enriquece cada canción escaneada con categoría, locations que la
        usan, y flag de unused. Usa los diccionarios RE y las asignaciones
        BGM leídas de la ROM.
        """
        # Primero escanear asignaciones actuales
        self.scan_bgm_assignments()

        # Construir mapa inverso: song_id → [locations que lo usan]
        usage_map = {}
        for assignment in self.bgm_assignments:
            sid = assignment["current_song_id"]
            if sid not in usage_map:
                usage_map[sid] = []
            usage_map[sid].append(assignment["location"])

        # Enriquecer cada canción
        for song in self.songs:
            sid = song["id"]

            # Categoría
            if sid in self.SPECIAL_IDS:
                song["category"] = self.SPECIAL_IDS[sid]
            elif sid in self.FOMT_US_SONG_CATEGORIES:
                song["category"] = self.FOMT_US_SONG_CATEGORIES[sid]
            elif sid > 0x1A:
                song["category"] = "SFX"
            else:
                song["category"] = "UNKNOWN"

            # Locations que lo usan
            song["used_by"] = usage_map.get(sid, [])

            # Flag unused
            song["is_unused"] = song["category"] == "UNUSED"

    # ═══════════════════════════════════════════════════════════════════
    # UTILIDADES
    # ═══════════════════════════════════════════════════════════════════

    def read_rom_ptr(self, offset):
        """Lee un puntero de GBA (Little Endian, mask 0x08000000)."""
        data = self.proyecto.read_rom(offset, 4)
        if len(data) < 4:
            return 0
        val = struct.unpack("<I", data)[0]
        if val & 0x08000000:
            return val & 0x1FFFFFF
        return 0

    def get_song_by_id(self, song_id):
        """Busca una canción por su ID en la lista escaneada."""
        for song in self.songs:
            if song["id"] == song_id:
                return song
        return None

    def get_songs_by_category(self, category):
        """Filtra canciones por categoría."""
        return [s for s in self.songs if s["category"] == category]

    def get_category_label(self, category):
        """Retorna un label legible para la categoría."""
        labels = {
            "BGM":     "🎵 BGM",
            "AMBIENT": "🌧 Ambient",
            "UNUSED":  "⚠ Unused / Rare",
            "SFX":     "🔊 SFX",
            "TITLE":   "🎬 Title / Intro",
            "UNKNOWN": "❓ Unknown",
        }
        return labels.get(category, category)

    def get_category_color_hex(self, category):
        """Retorna un color hex para la categoría (para la UI)."""
        colors = {
            "BGM":     "#00FF96",  # Verde
            "AMBIENT": "#FFD700",  # Dorado
            "UNUSED":  "#FF6B35",  # Naranja
            "SFX":     "#888888",  # Gris
            "TITLE":   "#00BFFF",  # Cyan
            "UNKNOWN": "#555555",  # Gris oscuro
        }
        return colors.get(category, "#FFFFFF")

    # ═══════════════════════════════════════════════════════════════════
    # EXPORTADOR VIA GBA-MUS-RIPPER
    # ═══════════════════════════════════════════════════════════════════
    
    def export_all_via_ripper(self, export_dir):
        """Exporta usando gba-mus-ripper (.mid y .sf2)."""
        import subprocess
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)
            
        ripper_dir = get_resource_path("gba-mus-ripper")
        ripper_exe = os.path.join(ripper_dir, "gba_mus_ripper.exe")
            
        rom_path = self.proyecto.base_rom_path
        
        # gba_mus_ripper expects the output dir as -o "C:\path"
        cmd = [ripper_exe, rom_path, "-o", export_dir]
        
        # Some games might need manual song table address if heuristic fails. 
        # But FoMT is usually detected. If not, we could pass it.
        
        try:
            result = subprocess.run(cmd, cwd=ripper_dir, capture_output=True, text=True)
            print("GBA-MUS-RIPPER OUTPUT:", result.stdout)
            if result.stderr:
                print("GBA-MUS-RIPPER ERRORS:", result.stderr)
        except Exception as e:
            print(f"Error llamando a gba-mus-ripper: {e}")
            
        return len(self.songs)

    # ═══════════════════════════════════════════════════════════════════
    # REPRODUCTOR NATIVO CON FLUIDSYNTH
    # ═══════════════════════════════════════════════════════════════════
    
    def preview_song_natively(self, song, out_wav_path):
        """Usa song_ripper + sound_font_ripper + fluidsynth para generar un test_play.wav"""
        import subprocess
        
        # Paths
        ripper_dir = get_resource_path("gba-mus-ripper")
        fluid_dir = get_resource_path(os.path.join("fluidsynth_bin", "bin"))
            
        song_ripper = os.path.join(ripper_dir, "song_ripper.exe")
        sf2_ripper = os.path.join(ripper_dir, "sound_font_ripper.exe")
        fluidsynth = os.path.join(fluid_dir, "fluidsynth.exe")
        
        rom_path = self.proyecto.base_rom_path
        
        temp_dir = os.path.join(os.path.dirname(out_wav_path))
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
            
        mid_file = os.path.join(temp_dir, "temp_play.mid")
        sf2_file = os.path.join(temp_dir, "temp_play.sf2")
        
        # Limpiar
        for f in [mid_file, sf2_file, out_wav_path]:
            if os.path.exists(f): 
                try: os.remove(f)
                except: pass

        # 1. Extraer MIDI aisladamente
        s_addr = hex(song['offset'])
        res1 = subprocess.run([song_ripper, rom_path, mid_file, s_addr], cwd=ripper_dir, capture_output=True, text=True)
        print(f"[song_ripper OUT] {res1.stdout}")
        print(f"[song_ripper ERR] {res1.stderr}")
        
        # 2. Extraer SF2 aisladamente
        vg_addr = hex(song['voicegroup_ptr'])
        res2 = subprocess.run([sf2_ripper, rom_path, sf2_file, vg_addr], cwd=ripper_dir, capture_output=True, text=True)
        print(f"[sf2_ripper OUT] {res2.stdout}")
        print(f"[sf2_ripper ERR] {res2.stderr}")
        
        print(f"Mid file exists? {os.path.exists(mid_file)}")
        print(f"SF2 file exists? {os.path.exists(sf2_file)}")
        
        # 3. Renderizar WAV usando Fluidsynth
        if os.path.exists(mid_file) and os.path.exists(sf2_file):
            res3 = subprocess.run([fluidsynth, "-F", out_wav_path, "-r", "44100", "-g", "5.0", sf2_file, mid_file],
                           cwd=fluid_dir, capture_output=True, text=True)
            if res3.returncode != 0:
                print(f"[fluidsynth ERROR] {res3.stderr}\n{res3.stdout}")
                           
        return os.path.exists(out_wav_path)
            

class TrackDecoder:
    """Decodifica el flujo de bytes de una pista Sappy a eventos de tiempo."""

    # Comandos Sappy Comunes (Bytecodes)
    CMD_WAIT = 0x80      # 0x80 - 0xB0 are wait commands (slen)
    CMD_FINE = 0xB1      # End of track
    CMD_GOTO = 0xB2      # Jump / Loop
    CMD_PATT = 0xB3      # Pattern (Call)
    CMD_PEND = 0xB4      # Pattern End (Return)
    CMD_TEMPO = 0xBB     # Change Tempo
    CMD_VOICE = 0xBD     # Change Instrument (Voicegroup Index)
    CMD_VOL = 0xBE       # Volume
    CMD_PAN = 0xBF       # Panning

    @staticmethod
    def decode_track(proyecto, track_offset):
        events = []
        pc = track_offset
        playing = True

        # Mapa de parámetros por comando Sappy
        CMD_PARAMS = {
            0xB2: 4, 0xB3: 4, 0xB5: 1, 0xB9: 3, 0xBA: 1,
            0xBB: 1, 0xBC: 1, 0xBD: 1, 0xBE: 1, 0xBF: 1,
            0xC0: 1, 0xC1: 1, 0xC2: 1, 0xC4: 1, 0xC5: 1, 0xC8: 1
        }

        while playing:
            try:
                cmd_byte = proyecto.read_rom(pc, 1)
                if not cmd_byte:
                    break
                cmd = cmd_byte[0]
                pc += 1

                if cmd < 0x80:  # NOTA
                    velocity = proyecto.read_rom(pc, 1)[0]
                    pc += 1
                    events.append({"type": "note", "val": cmd, "vel": velocity})
                elif 0x80 <= cmd <= 0xB0:  # WAIT
                    events.append({"type": "wait", "ticks": cmd - 0x80 if cmd > 0x80 else 1})
                elif cmd == TrackDecoder.CMD_FINE:
                    playing = False
                elif cmd in CMD_PARAMS:
                    p_count = CMD_PARAMS[cmd]
                    params = proyecto.read_rom(pc, p_count)

                    if cmd == TrackDecoder.CMD_TEMPO:
                        events.append({"type": "tempo", "bpm": params[0] * 2})

                    pc += p_count
                elif 0xD0 <= cmd <= 0xFF:
                    pc += 1  # Generalmente 1 byte de vel

                if pc - track_offset > 10000:  # Safety
                    break
            except:
                break

        return events

    @staticmethod
    def note_to_hz(note):
        """Convierte una nota MIDI (0-127) a frecuencia Hz."""
        return 440.0 * (2.0 ** ((note - 69) / 12.0))
