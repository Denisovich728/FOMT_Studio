# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.3.4)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
import os
import numpy as np
import struct
import math
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
                             QPushButton, QLabel, QSlider, QFrame,
                             QComboBox, QGroupBox, QListWidgetItem,
                             QTextEdit, QSplitter, QButtonGroup)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QRect, QIODevice, QUrl
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QPen, QFont
# Removed QMediaPlayer imports to rely on native winsound
from Perifericos.Traducciones.i18n import tr



class RetroBitVisualizer(QFrame):
    """Visualizador estilo 8-bit / Matrix (Bloques de Píxeles)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(120)
        self.levels = np.zeros(32)  # 32 columnas de bloques
        self.peaks = np.zeros(32)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._decay)
        self.timer.start(50)  # 20 FPS para ese feeling retro

    def _decay(self):
        self.levels *= 0.85
        for i in range(32):
            if self.levels[i] < self.peaks[i]:
                self.peaks[i] -= 0.05
            if self.peaks[i] < 0:
                self.peaks[i] = 0
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

                if r < val:
                    if r < 10:
                        color = QColor(0, 255, 100)
                    elif r < 14:
                        color = QColor(255, 255, 0)
                    else:
                        color = QColor(255, 50, 50)
                    painter.fillRect(rect, color)

                if r == peak_row and r > 0:
                    painter.fillRect(rect, QColor(255, 255, 255))


# ═══════════════════════════════════════════════════════════════════════
# PANEL DE INFORMACIÓN DETALLADA DE CANCIÓN
# ═══════════════════════════════════════════════════════════════════════

class SongInfoPanel(QFrame):
    """Panel lateral que muestra metadata detallada de la canción seleccionada."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(280)
        self.setStyleSheet("""
            SongInfoPanel {
                background: #0D0D12;
                border: 1px solid #2A2A35;
                border-radius: 6px;
            }
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        # Título
        title = QLabel("SONG INFO")
        title.setStyleSheet("color: #00FF96; font-size: 13px; font-weight: bold; letter-spacing: 2px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #2A2A35;")
        layout.addWidget(sep)

        # Campos de información
        self.lbl_id = self._make_field("ID:")
        self.lbl_category = self._make_field("Category:")
        self.lbl_offset = self._make_field("ROM Offset:")
        self.lbl_tracks = self._make_field("Tracks:")
        self.lbl_voicegroup = self._make_field("Voicegroup:")
        self.lbl_unused = self._make_field("Status:")

        layout.addWidget(self.lbl_id)
        layout.addWidget(self.lbl_category)
        layout.addWidget(self.lbl_offset)
        layout.addWidget(self.lbl_tracks)
        layout.addWidget(self.lbl_voicegroup)
        layout.addWidget(self.lbl_unused)

        # Separador
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #2A2A35;")
        layout.addWidget(sep2)

        # Sección: Dónde se usa
        used_title = QLabel("USED BY")
        used_title.setStyleSheet("color: #FFD700; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(used_title)

        self.used_by_list = QLabel("—")
        self.used_by_list.setWordWrap(True)
        self.used_by_list.setStyleSheet("color: #AAAAAA; font-size: 11px; font-family: 'Consolas';")
        layout.addWidget(self.used_by_list)

        # Separador
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setStyleSheet("color: #2A2A35;")
        layout.addWidget(sep3)

        # Sección: BGM ARM Offsets
        arm_title = QLabel("ARM CODE OFFSETS")
        arm_title.setStyleSheet("color: #FF6B35; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(arm_title)

        self.arm_offsets_label = QLabel("—")
        self.arm_offsets_label.setWordWrap(True)
        self.arm_offsets_label.setStyleSheet("color: #AAAAAA; font-size: 10px; font-family: 'Consolas';")
        layout.addWidget(self.arm_offsets_label)

        layout.addStretch()

    def _make_field(self, label_text):
        lbl = QLabel(f"{label_text} —")
        lbl.setStyleSheet("color: #CCCCCC; font-size: 11px; font-family: 'Consolas';")
        return lbl

    def update_info(self, song, sappy_engine):
        """Actualiza todo el panel con los datos de la canción seleccionada."""
        sid = song["id"]
        cat = song.get("category", "UNKNOWN")
        cat_label = sappy_engine.get_category_label(cat)
        cat_color = sappy_engine.get_category_color_hex(cat)

        self.lbl_id.setText(f"ID: 0x{sid:02X} (dec: {sid})")
        self.lbl_category.setText(f"Category: {cat_label}")
        self.lbl_category.setStyleSheet(f"color: {cat_color}; font-size: 11px; font-family: 'Consolas'; font-weight: bold;")
        self.lbl_offset.setText(f"ROM Offset: 0x{song['offset']:06X}")
        self.lbl_tracks.setText(f"Tracks: {song['tracks_count']}")
        self.lbl_voicegroup.setText(f"Voicegroup: 0x{song['voicegroup_ptr']:06X}")

        if song.get("is_unused"):
            self.lbl_unused.setText("Status: ⚠ UNUSED / RARE")
            self.lbl_unused.setStyleSheet("color: #FF6B35; font-size: 11px; font-weight: bold;")
        else:
            self.lbl_unused.setText("Status: ✓ In Use")
            self.lbl_unused.setStyleSheet("color: #00FF96; font-size: 11px;")

        # Used by
        used = song.get("used_by", [])
        if used:
            self.used_by_list.setText("\n".join(f"• {loc}" for loc in used))
        else:
            self.used_by_list.setText("— No BGM assignment found")

        # ARM offsets que referencian este song ID
        arm_refs = []
        for assignment in sappy_engine.bgm_assignments:
            if assignment["current_song_id"] == sid:
                off = assignment["rom_offset"]
                loc = assignment["location"]
                arm_refs.append(f"0x{off + 0x08000000:08X} ({loc})")

        if arm_refs:
            self.arm_offsets_label.setText("\n".join(arm_refs))
        else:
            self.arm_offsets_label.setText("— No ARM references")

    def clear_info(self):
        self.lbl_id.setText("ID: —")
        self.lbl_category.setText("Category: —")
        self.lbl_category.setStyleSheet("color: #CCCCCC; font-size: 11px; font-family: 'Consolas';")
        self.lbl_offset.setText("ROM Offset: —")
        self.lbl_tracks.setText("Tracks: —")
        self.lbl_voicegroup.setText("Voicegroup: —")
        self.lbl_unused.setText("Status: —")
        self.lbl_unused.setStyleSheet("color: #CCCCCC; font-size: 11px;")
        self.used_by_list.setText("—")
        self.arm_offsets_label.setText("—")


# ═══════════════════════════════════════════════════════════════════════
# BGM ASSIGNMENTS TABLE
# ═══════════════════════════════════════════════════════════════════════

class BGMAssignmentsPanel(QFrame):
    """Panel colapsable que muestra la tabla de asignaciones BGM leídas de la ROM."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            BGMAssignmentsPanel {
                background: #0D0D12;
                border: 1px solid #2A2A35;
                border-radius: 4px;
            }
        """)
        self._collapsed = True
        self._build_ui()

    def _build_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 4, 8, 4)
        self.main_layout.setSpacing(2)

        # Toggle button
        self.toggle_btn = QPushButton("▶ BGM Assignments (ROM)")
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #FFD700;
                font-size: 11px; font-weight: bold;
                text-align: left; border: none; padding: 4px;
            }
            QPushButton:hover { color: #FFFFFF; }
        """)
        self.toggle_btn.clicked.connect(self._toggle)
        self.main_layout.addWidget(self.toggle_btn)

        # Content (hidden by default)
        self.content_frame = QFrame()
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(4, 0, 4, 4)
        self.content_layout.setSpacing(1)
        self.content_frame.setVisible(False)
        self.main_layout.addWidget(self.content_frame)

    def _toggle(self):
        self._collapsed = not self._collapsed
        self.content_frame.setVisible(not self._collapsed)
        arrow = "▼" if not self._collapsed else "▶"
        self.toggle_btn.setText(f"{arrow} BGM Assignments (ROM)")

    def populate(self, assignments, sound_names):
        """Llena la tabla con las asignaciones BGM."""
        # Limpiar contenido previo
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for a in assignments:
            sid = a["current_song_id"]
            s_name = sound_names.get(str(sid), f"Song {sid}")
            mod_tag = " ✏️" if a["is_modified"] else ""
            color = "#FF6B35" if a["is_modified"] else "#888888"

            text = f"0x{a['rom_offset'] + 0x08000000:08X}  {a['location']:<22s}  → [{sid:02X}] {s_name}{mod_tag}"
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {color}; font-size: 10px; font-family: 'Consolas';")
            self.content_layout.addWidget(lbl)


# ═══════════════════════════════════════════════════════════════════════
# VISOR DE SONIDO PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════

class SappyAudioViewer(QWidget):
    """Componente principal del Visor de Sonido con categorización RE."""
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.sound_names = self.load_sound_names()
        self.current_filter = "ALL"

        # Eliminado QMediaPlayer. Usaremos winsound nativo de forma exclusiva.
        self.audio_phase = 0
        self.is_playing = False
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
        layout.setSpacing(8)

        # ── Título y Cabecera ──
        header = QLabel("🎵 Explorador de Audio Sappy (GBA M4A Engine)")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #00FF96;")
        layout.addWidget(header)

        # ── Filtros por categoría ──
        filter_layout = QHBoxLayout()
        filter_label = QLabel("Filter:")
        filter_label.setStyleSheet("color: #888888; font-size: 11px;")
        filter_layout.addWidget(filter_label)

        self.filter_buttons = {}
        filter_defs = [
            ("ALL",     "All",              "#FFFFFF"),
            ("BGM",     "🎵 BGM",           "#00FF96"),
            ("AMBIENT", "🌧 Ambient",       "#FFD700"),
            ("UNUSED",  "⚠ Unused/Rare",   "#FF6B35"),
            ("SFX",     "🔊 SFX",           "#888888"),
            ("TITLE",   "🎬 Title",         "#00BFFF"),
        ]

        for cat_key, cat_label, cat_color in filter_defs:
            btn = QPushButton(cat_label)
            btn.setCheckable(True)
            btn.setChecked(cat_key == "ALL")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: #1A1A1E; color: {cat_color};
                    border: 1px solid #333; border-radius: 4px;
                    padding: 4px 10px; font-size: 11px;
                }}
                QPushButton:checked {{
                    background: {cat_color}; color: #000000;
                    font-weight: bold;
                }}
                QPushButton:hover {{ border-color: {cat_color}; }}
            """)
            btn.clicked.connect(lambda checked, k=cat_key: self._on_filter(k))
            filter_layout.addWidget(btn)
            self.filter_buttons[cat_key] = btn

        filter_layout.addStretch()

        # Song count
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #555555; font-size: 11px;")
        filter_layout.addWidget(self.count_label)

        layout.addLayout(filter_layout)

        # ── Área Principal (Lista + Visualizador + Info Panel) ──
        main_h = QHBoxLayout()

        # 1. Lista de Canciones (con colores por categoría)
        self.song_list = QListWidget()
        self.song_list.setFixedWidth(300)
        self.song_list.setStyleSheet("""
            QListWidget {
                background: #0D0D12; color: white;
                border: 1px solid #2A2A35; border-radius: 4px;
                font-family: 'Consolas'; font-size: 11px;
            }
            QListWidget::item { padding: 3px 6px; border-bottom: 1px solid #1A1A1E; }
            QListWidget::item:selected { background: #1A3A2A; border-left: 3px solid #00FF96; }
            QListWidget::item:hover { background: #151520; }
        """)
        self.populate_songs()
        main_h.addWidget(self.song_list)

        # 2. Panel de Visualización Central
        vis_panel = QVBoxLayout()
        self.retro_vis = RetroBitVisualizer()
        vis_panel.addWidget(self.retro_vis)

        # Waveform label
        self.waveform_label = QLabel("Waveform Monitor (8-bit)")
        self.waveform_label.setStyleSheet("color: #333333; font-size: 10px;")
        vis_panel.addWidget(self.waveform_label)

        # Info Pista (Now Playing)
        self.track_info_label = QLabel("No Track Selected")
        self.track_info_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.track_info_label.setStyleSheet("color: #666666; font-family: 'Consolas'; font-size: 11px;")
        vis_panel.addWidget(self.track_info_label)

        # Controles de reproducción
        ctrl_layout = QHBoxLayout()
        self.btn_play = QPushButton("▶ PLAY")
        self.btn_stop = QPushButton("■ STOP")
        self.btn_export = QPushButton("💾 EXPORT MIDI/SF2")
        self.btn_play.setStyleSheet("""
            QPushButton {
                background: #00FF96; color: black; font-weight: bold;
                padding: 10px 20px; border-radius: 4px; font-size: 12px;
            }
            QPushButton:hover { background: #33FFB0; }
            QPushButton:disabled { background: #333333; color: #666666; }
        """)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background: #FF3232; color: white; font-weight: bold;
                padding: 10px 20px; border-radius: 4px; font-size: 12px;
            }
            QPushButton:hover { background: #FF5555; }
        """)
        self.btn_export.setStyleSheet("""
            QPushButton {
                background: #00BFFF; color: black; font-weight: bold;
                padding: 10px 20px; border-radius: 4px; font-size: 12px;
            }
            QPushButton:hover { background: #33CCFF; }
        """)
        ctrl_layout.addWidget(self.btn_play)
        ctrl_layout.addWidget(self.btn_stop)
        ctrl_layout.addWidget(self.btn_export)

        # Speed control
        speed_layout = QHBoxLayout()
        speed_label = QLabel("Speed")
        speed_label.setStyleSheet("color: #888888; font-size: 11px;")
        self.speed_combo = QComboBox()
        self.speed_combo.addItems([f"{x:.2f}x" for x in np.arange(0.25, 4.25, 0.25)])
        self.speed_combo.setCurrentText("1.00x")
        self.speed_combo.setStyleSheet("""
            QComboBox {
                background: #1A1A1E; color: white; border: 1px solid #333;
                padding: 4px; border-radius: 3px;
            }
        """)
        speed_layout.addWidget(speed_label)
        speed_layout.addWidget(self.speed_combo)
        ctrl_layout.addLayout(speed_layout)

        vis_panel.addLayout(ctrl_layout)

        # Seek bar
        self.seek_bar = QSlider(Qt.Orientation.Horizontal)
        self.seek_bar.setRange(0, 1000)
        self.seek_bar.setStyleSheet("""
            QSlider::groove:horizontal { background: #1A1A1E; height: 6px; border-radius: 3px; }
            QSlider::handle:horizontal {
                background: #00FF96; width: 14px; height: 14px;
                margin: -4px 0; border-radius: 7px;
            }
            QSlider::sub-page:horizontal { background: #00FF96; border-radius: 3px; }
        """)
        self.seek_bar.sliderMoved.connect(self.on_seek)
        vis_panel.addWidget(self.seek_bar)

        # BGM Assignments Panel (colapsable)
        self.bgm_panel = BGMAssignmentsPanel()
        vis_panel.addWidget(self.bgm_panel)

        # Populate BGM assignments si están disponibles
        if hasattr(self.project, 'sappy_engine') and self.project.sappy_engine.bgm_assignments:
            self.bgm_panel.populate(self.project.sappy_engine.bgm_assignments, self.sound_names)

        main_h.addLayout(vis_panel)

        # 3. Panel de Información (derecha)
        self.info_panel = SongInfoPanel()
        main_h.addWidget(self.info_panel)

        layout.addLayout(main_h)

        # ── Connects ──
        self.btn_play.clicked.connect(self.on_play)
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_export.clicked.connect(self.on_export_data)
        self.song_list.currentRowChanged.connect(self.on_song_selected)
        self.speed_combo.currentIndexChanged.connect(self._update_timer_speed)

    # ═══════════════════════════════════════════════════════════════════
    # FILTROS
    # ═══════════════════════════════════════════════════════════════════

    def _on_filter(self, category):
        """Cambia el filtro activo y repobla la lista."""
        self.current_filter = category
        # Actualizar estado checked de los botones
        for key, btn in self.filter_buttons.items():
            btn.setChecked(key == category)
        self.populate_songs()

    def _update_timer_speed(self):
        if hasattr(self, 'play_timer') and self.play_timer.isActive():
            speed_val = float(self.speed_combo.currentText().replace("x", ""))
            self.play_timer.setInterval(int(100 / speed_val))

    # ═══════════════════════════════════════════════════════════════════
    # LISTA DE CANCIONES
    # ═══════════════════════════════════════════════════════════════════

    def populate_songs(self):
        """Poblar la lista con canciones, coloreadas por categoría."""
        self.song_list.clear()

        if not hasattr(self.project, 'songs'):
            return

        sappy = self.project.sappy_engine
        visible_count = 0

        for song in self.project.songs:
            cat = song.get("category", "UNKNOWN")

            # Aplicar filtro
            if self.current_filter != "ALL" and cat != self.current_filter:
                continue

            s_id = str(song['id'])
            s_name = self.sound_names.get(s_id, f"Track {s_id}")
            cat_icon = {
                "BGM": "🎵", "AMBIENT": "🌧", "UNUSED": "⚠",
                "SFX": "🔊", "TITLE": "🎬", "UNKNOWN": "❓",
            }.get(cat, "")

            item_text = f"[{int(s_id):03d}] {cat_icon} {s_name}"
            item = QListWidgetItem(item_text)

            # Color por categoría
            cat_color = sappy.get_category_color_hex(cat)
            item.setForeground(QColor(cat_color))

            # Fondo sutilmente tintado para unused
            if cat == "UNUSED":
                item.setBackground(QColor(255, 107, 53, 25))

            # Guardar referencia al song data
            item.setData(Qt.ItemDataRole.UserRole, song['id'])

            self.song_list.addItem(item)
            visible_count += 1

        self.count_label.setText(f"{visible_count} / {len(self.project.songs)} songs")

    # ═══════════════════════════════════════════════════════════════════
    # SELECCIÓN Y REPRODUCCIÓN
    # ═══════════════════════════════════════════════════════════════════

    def _get_selected_song(self):
        """Obtiene el song dict del item seleccionado."""
        item = self.song_list.currentItem()
        if not item:
            return None
        song_id = item.data(Qt.ItemDataRole.UserRole)
        if song_id is None:
            return None
        return self.project.sappy_engine.get_song_by_id(song_id)

    def on_song_selected(self, index):
        if index < 0:
            self.info_panel.clear_info()
            return

        song = self._get_selected_song()
        if not song:
            return

        s_id = str(song['id'])
        s_name = self.sound_names.get(s_id, f"Track {s_id}")

        cat_color = self.project.sappy_engine.get_category_color_hex(song.get("category", "UNKNOWN"))
        self.track_info_label.setText(f"Track: [{int(s_id):03d}] {s_name} (Ready)")
        self.track_info_label.setStyleSheet(f"color: {cat_color}; font-family: 'Consolas'; font-size: 11px;")

        # Actualizar panel de info
        self.info_panel.update_info(song, self.project.sappy_engine)

    def on_play(self):
        song = self._get_selected_song()
        if not song:
            return

        if self.is_playing:
            self.on_stop()

        self.btn_play.setText("PREPARING...")
        self.btn_play.setEnabled(False)
        self.btn_stop.setEnabled(False)
        
        # Temp build folder
        import os, tempfile
        out_wav = os.path.join(tempfile.gettempdir(), "fomt_preview.wav")
        
        import threading
        def _bg_prep():
            success = self.project.sappy_engine.preview_song_natively(song, out_wav)
            # Call back to main thread
            from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
            QMetaObject.invokeMethod(self, "_on_play_ready", Qt.ConnectionType.QueuedConnection, 
                                     Q_ARG(bool, success), Q_ARG(str, out_wav))
                                     
        threading.Thread(target=_bg_prep).start()

    @pyqtSlot(bool, str)
    def _on_play_ready(self, success, wav_path):
        self.btn_play.setText("▶ PLAY")
        self.btn_play.setEnabled(True)
        self.btn_stop.setEnabled(True)
        
        if not success:
            print("No se pudo generar la preview usando Fluidsynth/GBA-Mus-Ripper.")
            return
            
        self.is_playing = True
        
        # Reproducción nativa exclusiva con winsound (Garantiza que no haya locks ni problemas de codecs)
        import sys
        if sys.platform == 'win32':
            import winsound
            import os
            try:
                norm_path = os.path.normpath(wav_path)
                winsound.PlaySound(norm_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            except Exception as e:
                print(f"Error reproduciendo con winsound: {e}")

        current_text = self.track_info_label.text().replace("(Ready)", "(Playing)")
        self.track_info_label.setText(current_text)
        self.track_info_label.setStyleSheet("color: #00FF96; font-weight: bold; font-family: 'Consolas'; font-size: 11px;")
        
        # Fake retro visuals since we are piping to QMediaPlayer natively
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self._fake_visuals)
        self.play_timer.start(50)

    def _fake_visuals(self):
        if not self.is_playing: return
        # Random visuals synced loosely to music existence
        import random
        v_data = bytes([random.randint(0, 255) for _ in range(32)])
        self.retro_vis.update_from_data(v_data)

    def on_position_changed(self, pos):
        if not self.seek_bar.isSliderDown():
            self.seek_bar.setValue(pos)

    def on_duration_changed(self, duration):
        self.seek_bar.setRange(0, duration)

    def on_seek(self, pos):
        pass # Seeking no soportado en winsound básico

    def on_stop(self):
        self.is_playing = False
        
        import sys
        if sys.platform == 'win32':
            import winsound
            try:
                winsound.PlaySound(None, 0)
            except:
                pass

        if hasattr(self, 'play_timer'):
            self.play_timer.stop()
        self.btn_play.setEnabled(True)
        self.seek_bar.setValue(0)
        
        # Reset visualizer
        self.retro_vis.update_from_data(bytes([0]*32))

        current_text = self.track_info_label.text().replace("(Playing)", "(Ready)")
        self.track_info_label.setText(current_text)
        self.track_info_label.setStyleSheet("color: #888888; font-family: 'Consolas'; font-size: 11px;")
        print("Cerrando sesión de audio...")
        
    def on_export_data(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        out_dir = QFileDialog.getExistingDirectory(self, "Select Export Directory")
        if not out_dir: return
        
        try:
            self.btn_export.setText("EXPORTING (PLEASE WAIT)...")
            self.btn_export.setEnabled(False)
            import threading
            def bg_task():
                count = self.project.sappy_engine.export_all_via_ripper(out_dir)
                print(f"Exported successfully to {out_dir}")
                # Reset button
                self.btn_export.setText("💾 EXPORT MIDI/SF2")
                self.btn_export.setEnabled(True)
            threading.Thread(target=bg_task).start()
        except Exception as e:
            print(f"Export Error: {e}")
            self.btn_export.setText("💾 EXPORT MIDI/SF2")
            self.btn_export.setEnabled(True)
