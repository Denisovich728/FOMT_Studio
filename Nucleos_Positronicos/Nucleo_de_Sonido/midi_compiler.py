import mido
import struct
import os

class MidiToSappyCompiler:
    """
    Compilador nativo en Python Puro.
    Convierte archivos MIDI estándar (.mid) a bytecodes del motor Sappy (GBA).
    """

    def __init__(self, proyecto):
        self.proyecto = proyecto

    def find_free_space(self, size, start_offset=0x700000):
        """Busca espacio libre (lleno de 0xFF) en la ROM."""
        rom_data = self.proyecto.base_rom_data
        search_pattern = b'\xFF' * size
        idx = rom_data.find(search_pattern, start_offset)
        if idx != -1:
            # Alinear a 4 bytes
            rem = idx % 4
            if rem != 0:
                idx += (4 - rem)
            return idx
        return -1

    def compile_midi_to_sappy(self, midi_path):
        """
        Lee el MIDI y genera los bytecodes Sappy para cada pista.
        Retorna: lista de bytes por pista.
        """
        mid = mido.MidiFile(midi_path)
        tracks_bytecodes = []

        # Ticks por negra (PPQN). Sappy usa normalmente 24.
        ticks_per_beat = mid.ticks_per_beat
        scale_factor = 24.0 / ticks_per_beat if ticks_per_beat != 0 else 1.0

        for track in mid.tracks:
            bytecode = bytearray()
            current_velocity = 0x64 # Default
            
            for msg in track:
                # Procesar delays (Delta time)
                delta_ticks = int(msg.time * scale_factor)
                while delta_ticks > 0:
                    wait_amt = min(delta_ticks, 48)  # Máximo comando de wait (0xB0 = 48? Usaremos comandos simples)
                    if wait_amt <= 0: break
                    # Comando wait en Sappy: 0x80 + wait_amt (Aproximación simple para 1-48)
                    bytecode.append(0x80 + wait_amt)
                    delta_ticks -= wait_amt

                if msg.type == 'note_on' and msg.velocity > 0:
                    # Comando nota (0x00 - 0x7F)
                    note = max(0, min(127, msg.note))
                    vel = max(0, min(127, msg.velocity))
                    
                    bytecode.append(note)
                    # Emitir nota y velocidad explícita.
                    bytecode.append(vel)
                    
                elif msg.type == 'set_tempo':
                    # BPM
                    bpm = mido.tempo2bpm(msg.tempo)
                    sappy_bpm = int(bpm / 2) # Sappy usa BPM / 2
                    bytecode.append(0xBB) # Comando Tempo
                    bytecode.append(sappy_bpm)
            
            # End of Track
            bytecode.append(0xB1)
            tracks_bytecodes.append(bytecode)
            
        return tracks_bytecodes

    def inject_midi(self, midi_path, song_id, voicegroup_ptr=None):
        """
        Compila el MIDI, busca espacio, inyecta y actualiza la tabla.
        """
        tracks_bytecodes = self.compile_midi_to_sappy(midi_path)
        if not tracks_bytecodes:
            return False, "El MIDI no tiene pistas válidas."
            
        # Calcular tamaño total necesario: Header (12) + Pistas
        header_size = 12 + (len(tracks_bytecodes) * 4)
        tracks_size = sum(len(t) for t in tracks_bytecodes)
        total_size = header_size + tracks_size
        
        # 1. Buscar espacio libre
        free_offset = self.find_free_space(total_size + 16, start_offset=0x700000)
        if free_offset == -1:
            return False, "No hay espacio libre suficiente en la ROM (FF)."
            
        print(f"Inyectando MIDI en offset: 0x{free_offset:08X}")
        
        # 2. Obtener puntero al voicegroup original de la canción
        sappy = self.proyecto.sappy_engine
        original_song = sappy.get_song_by_id(song_id)
        if not original_song:
            return False, "Song ID no encontrado."
            
        vg_ptr = voicegroup_ptr if voicegroup_ptr else original_song.get('voicegroup_ptr', 0)
        
        # 3. Escribir pistas y recopilar sus punteros
        current_write_offset = free_offset + header_size
        track_pointers = []
        
        with open(self.proyecto.base_rom_path, 'r+b') as f:
            for tb in tracks_bytecodes:
                track_pointers.append(current_write_offset)
                f.seek(current_write_offset)
                f.write(tb)
                current_write_offset += len(tb)
                
            # 4. Escribir el Song Header
            f.seek(free_offset)
            f.write(struct.pack("<B", len(tracks_bytecodes)))
            f.write(b'\x00\x00\x00') # Priority, Reverb, etc.
            f.write(struct.pack("<I", vg_ptr | 0x08000000)) # Voicegroup
            
            for tptr in track_pointers:
                f.write(struct.pack("<I", tptr | 0x08000000))
                
            # 5. Repuntear en la Tabla Maestra
            # La tabla de Sappy está en sappy.song_table_offset
            table_offset = sappy.song_table_offset
            entry_offset = table_offset + (song_id * 8)
            
            f.seek(entry_offset)
            f.write(struct.pack("<I", free_offset | 0x08000000))
            
        # Refrescar la ROM cargada en memoria
        with open(self.proyecto.base_rom_path, 'rb') as f:
            self.proyecto.base_rom_data = f.read()
            
        return True, f"Inyectado exitosamente en 0x{free_offset:08X}."
