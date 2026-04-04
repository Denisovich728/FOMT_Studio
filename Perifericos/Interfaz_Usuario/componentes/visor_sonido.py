import os
import numpy as np
import struct
import math
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                             QPushButton, QLabel, QSlider, QFrame)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRect, QIODevice
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QPen
from PyQt6.QtMultimedia import QAudioOutput, QAudioFormat, QAudioSink
from Perifericos.Traducciones.i18n import tr

class RetroBitVisualizer(QFrame):
    """Visualizador estilo 8-bit / Matrix (Bloques de Píxeles)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(120)
        self.levels = np.zeros(32) # 32 columnas de bloques
        self.peaks = np.zeros(32)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._decay)
        self.timer.start(50) # 20 FPS para ese feeling retro
        
    def _decay(self):
        self.levels *= 0.85
        for i in range(32):
            if self.levels[i] < self.peaks[i]:
                self.peaks[i] -= 0.05
            if self.peaks[i] < 0: self.peaks[i] = 0
        self.update()

    def update_from_data(self, data):
        """Simula picos de audio a partir de datos crudos."""
        raw = np.frombuffer(data[:32], dtype=np.int8) / 128.0
        self.levels = np.abs(raw)
        for i in range(32):
            if self.levels[i] > self.peaks[i]:
                self.peaks[i] = self.levels[i]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        w, h = self.width(), self.height()
        
        # Fondo Negro Puro (Retro)
        painter.fillRect(self.rect(), QColor(0, 0, 0))
        
        cols = 32
        rows = 16
        col_w = w / cols
        row_h = h / rows
        
        # Dibujar Cuadrícula de Fondo (Sutil)
        painter.setPen(QPen(QColor(40, 40, 40), 1))
        for c in range(cols + 1):
            x = int(c * col_w)
            painter.drawLine(x, 0, x, h)
        for r in range(rows + 1):
            y = int(r * row_h)
            painter.drawLine(0, y, w, y)
        
        for c in range(cols):
            val = int(self.levels[c] * rows)
            peak_row = int(self.peaks[c] * rows)
            
            for r in range(rows):
                rect = QRect(int(c * col_w + 1), int(h - (r + 1) * row_h + 1), 
                             int(col_w - 2), int(row_h - 2))
                
                # Color según la altura (Verde -> Amarillo -> Rojo)
                if r < val:
                    if r < 10: color = QColor(0, 255, 100)
                    elif r < 14: color = QColor(255, 255, 0)
                    else: color = QColor(255, 50, 50)
                    painter.fillRect(rect, color)
                
                # Dibujar el pico (punto flotante)
                if r == peak_row and r > 0:
                    painter.fillRect(rect, QColor(255, 255, 255))

class SappyAudioViewer(QWidget):
    """Componente principal del Visor de Sonido."""
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.sound_names = self.load_sound_names()
        
        # Audio Engine (Push Mode Stereo)
        self.audio_format = QAudioFormat()
        self.audio_format.setSampleRate(44100)
        self.audio_format.setChannelCount(2) # Estéreo
        self.audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        
        self.audio_sink = QAudioSink(self.audio_format, self)
        self.audio_device = self.audio_sink.start() # Modo PUSH
        
        self.audio_phase = 0
        self.init_ui()

    def load_sound_names(self):
        import json
        path = "Nucleos_de_Procesamiento/Listas_de_Nombres/sonidos.json"
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Título y Cabecera
        header = QLabel("Explorador de Audio Sappy (GBA Engine)")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #00FF96;")
        layout.addWidget(header)
        
        # Área Principal (Visualizador y Lista)
        main_h = QHBoxLayout()
        
        # 1. Lista de Canciones
        self.song_list = QListWidget()
        self.song_list.setFixedWidth(250)
        self.song_list.setStyleSheet("""
            QListWidget { background: #1A1A1E; color: white; border: 1px solid #333; }
            QListWidget::item:selected { background: #00FF96; color: black; }
        """)
        self.populate_songs()
        main_h.addWidget(self.song_list)
        
        # 2. Panel de Visualización
        vis_panel = QVBoxLayout()
        self.retro_vis = RetroBitVisualizer()
        vis_panel.addWidget(self.retro_vis)
        
        # Monitor Waveform
        self.waveform_label = QLabel("Waveform Monitor (8-bit)")
        self.waveform_label.setStyleSheet("color: #444444; font-size: 10px;")
        vis_panel.addWidget(self.waveform_label)
        
        # Info Pista
        self.track_info_label = QLabel("No Track Selected")
        self.track_info_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.track_info_label.setStyleSheet("color: #666666; font-family: 'Consolas'; font-size: 11px;")
        vis_panel.addWidget(self.track_info_label)
        
        # Controles
        ctrl_layout = QHBoxLayout()
        self.btn_play = QPushButton("▶ PLAY")
        self.btn_stop = QPushButton("■ STOP")
        self.btn_play.setStyleSheet("background: #00FF96; color: black; font-weight: bold; padding: 10px;")
        self.btn_stop.setStyleSheet("background: #FF3232; color: white; font-weight: bold; padding: 10px;")
        ctrl_layout.addWidget(self.btn_play)
        ctrl_layout.addWidget(self.btn_stop)
        
        # Tempo y Velocidad
        ctrl_extras = QVBoxLayout()
        speed_layout = QHBoxLayout()
        speed_label = QLabel("Speed")
        from PyQt6.QtWidgets import QComboBox
        self.speed_combo = QComboBox()
        self.speed_combo.addItems([f"{x:.2f}x" for x in np.arange(0.25, 4.25, 0.25)])
        self.speed_combo.setCurrentText("1.00x")
        speed_layout.addWidget(speed_label)
        speed_layout.addWidget(self.speed_combo)
        ctrl_extras.addLayout(speed_layout)
        ctrl_layout.addLayout(ctrl_extras)
        vis_panel.addLayout(ctrl_layout)
        
        # Barra
        self.seek_bar = QSlider(Qt.Orientation.Horizontal)
        self.seek_bar.setRange(0, 1000)
        vis_panel.addWidget(self.seek_bar)
        
        main_h.addLayout(vis_panel)
        layout.addLayout(main_h)
        
        # Connects
        self.btn_play.clicked.connect(self.on_play)
        self.btn_stop.clicked.connect(self.on_stop)
        self.song_list.currentRowChanged.connect(self.on_song_selected)
        self.seek_bar.sliderMoved.connect(self.on_seek)
        self.speed_combo.currentIndexChanged.connect(self._update_timer_speed)
    
    def _update_timer_speed(self):
        if hasattr(self, 'play_timer') and self.play_timer.isActive():
            speed_val = float(self.speed_combo.currentText().replace("x", ""))
            self.play_timer.setInterval(int(100 / speed_val))

    def populate_songs(self):
        self.song_list.clear()
        if hasattr(self.project, 'songs'):
            for song in self.project.songs:
                s_id = str(song['id'])
                s_name = self.sound_names.get(s_id, f"Track {s_id}")
                self.song_list.addItem(f"[{int(s_id):03d}] {s_name}")
                
    def on_song_selected(self, index):
        if index < 0 or index >= len(self.project.songs): return
        song = self.project.songs[index]
        s_id = str(song['id'])
        s_name = self.sound_names.get(s_id, f"Track {s_id}")
        self.track_info_label.setText(f"Track: [{int(s_id):03d}] {s_name} (Ready)")
        self.track_info_label.setStyleSheet("color: #888888;")

    def on_play(self):
        idx = self.song_list.currentRow()
        if idx < 0 or idx >= len(self.project.songs): return
        
        song = self.project.songs[idx]
        from Nucleos_de_Procesamiento.Nucleo_de_Sonido.motor_sappy import TrackDecoder
        
        # Decodificar pista principal (0)
        if song.get('track_pointers'):
            self.current_events = TrackDecoder.decode_track(self.project, song['track_pointers'][0])
        else:
            self.current_events = []
            
        self.event_ptr = 0
        self.wait_ticks = 0
        self.current_freq = 440.0
        self.note_amplitude = 0
        self.is_playing = True
        
        print(f"Reproduciendo track GBA {song['id']} (Events: {len(self.current_events)})...")
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self._update_playback)
        
        current_text = self.track_info_label.text().replace("(Ready)", "(Playing)")
        self.track_info_label.setText(current_text)
        self.track_info_label.setStyleSheet("color: #00FF96; font-weight: bold;")
        
        speed_val = float(self.speed_combo.currentText().replace("x", ""))
        self.play_timer.start(int(100 / speed_val))
        self.btn_play.setEnabled(False)

    def _update_playback(self):
        if not self.is_playing: return

        # 1. Procesar Eventos Sappy
        from Nucleos_de_Procesamiento.Nucleo_de_Sonido.motor_sappy import TrackDecoder
        
        while self.event_ptr < len(self.current_events) and self.wait_ticks <= 0:
            ev = self.current_events[self.event_ptr]
            self.event_ptr += 1
            
            if ev['type'] == 'note':
                self.current_freq = TrackDecoder.note_to_hz(ev['val'])
                # Simular ataque de nota (amplitud)
                self.note_amplitude = (ev.get('vel', 100) / 127.0) * 0.4
            elif ev['type'] == 'wait':
                # Sappy ticks a nuestro ciclo. Un tick Sappy suele ser rápido.
                # Ajustamos la escala para que la música no vaya a 20 FPS.
                self.wait_ticks = ev['ticks']
                break
        
        self.wait_ticks -= 1
        # Decaimiento simple de la nota si estamos esperando
        if self.wait_ticks > 0:
            self.note_amplitude *= 0.9 
        
        # 2. Mover Barra
        new_val = self.seek_bar.value() + 1
        if new_val > 1000 or self.event_ptr >= len(self.current_events): 
            self.on_stop()
            return
        self.seek_bar.setValue(new_val)
        
        # 3. Sonido y Visualización (Real)
        samples_count = 2000
        
        # Visualización basada en la amplitud de la nota
        v_level = int(self.note_amplitude * 255)
        v_data = bytes([v_level for _ in range(32)])
        self.retro_vis.update_from_data(v_data)
        
        audio_chunk = bytearray()
        for _ in range(samples_count):
            sample = 15000 if math.sin(self.audio_phase * 2 * math.pi) > 0 else -15000
            val = int(sample * self.note_amplitude)
            le_val = struct.pack("<h", val)
            audio_chunk.extend(le_val)
            audio_chunk.extend(le_val)
            
            self.audio_phase += self.current_freq / 44100.0
            if self.audio_phase >= 1.0: self.audio_phase -= 1.0
            
        if self.audio_device:
            self.audio_device.write(bytes(audio_chunk))

    def on_seek(self, pos):
        pass

    def on_stop(self):
        self.is_playing = False
        if hasattr(self, 'play_timer'):
            self.play_timer.stop()
        self.btn_play.setEnabled(True)
        self.seek_bar.setValue(0)
        
        current_text = self.track_info_label.text().replace("(Playing)", "(Ready)")
        self.track_info_label.setText(current_text)
        self.track_info_label.setStyleSheet("color: #888888;")
        print("Cerrando sesión de audio...")
