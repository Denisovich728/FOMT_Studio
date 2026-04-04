import struct
import os

class SappyParser:
    """
    Motor nativo para procesar el motor de sonido M4A (Sappy) de GBA.
    Localización: Nucleos_de_Procesamiento/Nucleo_de_Sonido/motor_sappy.py
    """
    SONG_TABLE_OFFSET = 0x13ABF0  # Offset estándar para FoMT (Stan/Mary)
    
    def __init__(self, proyecto):
        self.proyecto = proyecto
        self.songs = []
        
    def scan_songs(self):
        """Escanea la tabla de canciones y extrae los encabezados básicos."""
        self.songs = []
        offset = self.SONG_TABLE_OFFSET
        
        # Escaneamos hasta encontrar un puntero inválido o llegar al límite razonable
        # FoMT suele tener unas 150-200 entradas entre música y SFX.
        for i in range(256):
            entry_ptr = self.read_rom_ptr(offset + (i * 8))
            if entry_ptr == 0 or entry_ptr > len(self.proyecto.base_rom_data):
                break
                
            song_info = self.parse_song_header(entry_ptr, i)
            if song_info:
                self.songs.append(song_info)
                
        return self.songs

    def parse_song_header(self, header_offset, song_id):
        """Lee el encabezado de una canción (Pistas, Voicegroup, etc)."""
        data = self.proyecto.read_rom(header_offset, 12 + (16 * 4)) # Buffer para hasta 16 pistas
        if not data: return None
        
        num_tracks = data[0]
        if num_tracks == 0 or num_tracks > 16: return None
        
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
            "name": f"Song_{song_id:03d}"
        }

    def read_rom_ptr(self, offset):
        """Lee un puntero de GBA (Little Endian, mask 0x08000000)."""
        data = self.proyecto.read_rom(offset, 4)
        if len(data) < 4: return 0
        val = struct.unpack("<I", data)[0]
        if val & 0x08000000:
            return val & 0x1FFFFFF
        return 0

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
                if not cmd_byte: break
                cmd = cmd_byte[0]
                pc += 1
                
                if cmd < 0x80: # NOTA
                    velocity = proyecto.read_rom(pc, 1)[0]
                    pc += 1
                    events.append({"type": "note", "val": cmd, "vel": velocity})
                elif 0x80 <= cmd <= 0xB0: # WAIT
                    events.append({"type": "wait", "ticks": cmd - 0x80 if cmd > 0x80 else 1})
                elif cmd == TrackDecoder.CMD_FINE:
                    playing = False
                elif cmd in CMD_PARAMS:
                    # Comandos con parámetros (Tempo, Voice, Vol, etc)
                    p_count = CMD_PARAMS[cmd]
                    params = proyecto.read_rom(pc, p_count)
                    
                    if cmd == TrackDecoder.CMD_TEMPO:
                        events.append({"type": "tempo", "bpm": params[0] * 2})
                    
                    pc += p_count
                elif 0xD0 <= cmd <= 0xFF:
                    # Comandos extendidos (a veces usados para notas con duración fija)
                    pc += 1 # Generalmente 1 byte de vel
                
                if pc - track_offset > 10000: # Safety
                    break
            except:
                break
                
        return events

    @staticmethod
    def note_to_hz(note):
        """Convierte una nota MIDI (0-127) a frecuencia Hz."""
        return 440.0 * (2.0 ** ((note - 69) / 12.0))
