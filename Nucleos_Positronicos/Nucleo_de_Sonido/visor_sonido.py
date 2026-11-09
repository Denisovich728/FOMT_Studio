# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v4.0.0)
# "The Greatest Show - Final Release"
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
from Consola_de_Comando.i18n import tr
from Consola_de_Comando.i18n import t as _t
from Consola_de_Comando.themes import color, colors

# Categorias de cancion que entrega SappyEngine -> clave de texto en i18n.json
CATEGORY_KEYS = {
    "BGM": "aud_cat_bgm",
    "AMBIENT": "aud_cat_ambient",
    "UNUSED": "aud_cat_unused",
    "SFX": "aud_cat_sfx",
    "TITLE": "aud_cat_title",
    "UNKNOWN": "aud_cat_unknown",
}


def category_label(category):
    return _t(CATEGORY_KEYS.get(category, "aud_cat_unknown"))


def _section_title(text):
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(f"color: {color('muted')}; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
    return lbl


def _separator():
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setStyleSheet(f"color: {color('border')};")
    return sep


class RetroBitVisualizer(QFrame):
    """Visualizador estilo 8-bit (bloques de pixeles) con los colores del tema activo."""
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
        # Los colores se leen en cada repintado, asi el medidor sigue al tema activo.
        tk = colors()
        painter = QPainter(self)
        w, h = self.width(), self.height()

        painter.fillRect(self.rect(), QColor(tk["surface_alt"]))

        cols = 32
        rows = 16
        col_w = w / cols
        row_h = h / rows

        # Cuadricula de fondo
        painter.setPen(QPen(QColor(tk["border"]), 1))
        for c in range(cols + 1):
            x = int(c * col_w)
            painter.drawLine(x, 0, x, h)
        for r in range(rows + 1):
            y = int(r * row_h)
            painter.drawLine(0, y, w, y)

        low, mid, high, peak = (QColor(tk["success"]), QColor(tk["warning"]),
                                QColor(tk["danger"]), QColor(tk["text"]))
        for c in range(cols):
            val = int(self.levels[c] * rows)
            peak_row = int(self.peaks[c] * rows)

            for r in range(rows):
                rect = QRect(int(c * col_w + 1), int(h - (r + 1) * row_h + 1),
                             int(col_w - 2), int(row_h - 2))

                if r < val:
                    painter.fillRect(rect, low if r < 10 else (mid if r < 14 else high))

                if r == peak_row and r > 0:
                    painter.fillRect(rect, peak)


# ═══════════════════════════════════════════════════════════════════════
# PANEL DE INFORMACIÓN DETALLADA DE CANCIÓN
# ═══════════════════════════════════════════════════════════════════════

class SongInfoPanel(QFrame):
    """Panel lateral que muestra metadata detallada de la canción seleccionada."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(280)
        self.setStyleSheet(f"""
            SongInfoPanel {{
                background: {color('surface')};
                border: 1px solid {color('border')};
                border-radius: 6px;
            }}
            SongInfoPanel QLabel {{ background: transparent; }}
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        layout.addWidget(_section_title(_t("aud_info_title")))
        layout.addWidget(_separator())

        # Campos de información
        self.lbl_id = self._make_field()
        self.lbl_category = self._make_field()
        self.lbl_offset = self._make_field()
        self.lbl_tracks = self._make_field()
        self.lbl_voicegroup = self._make_field()
        self.lbl_unused = self._make_field()
        for lbl in (self.lbl_id, self.lbl_category, self.lbl_offset,
                    self.lbl_tracks, self.lbl_voicegroup, self.lbl_unused):
            layout.addWidget(lbl)

        layout.addWidget(_separator())

        # Sección: Dónde se usa
        layout.addWidget(_section_title(_t("aud_used_by")))
        self.used_by_list = QLabel("—")
        self.used_by_list.setWordWrap(True)
        self.used_by_list.setStyleSheet(f"color: {color('text')}; font-size: 11px; font-family: 'Consolas';")
        layout.addWidget(self.used_by_list)

        layout.addWidget(_separator())

        # Sección: BGM ARM Offsets
        layout.addWidget(_section_title(_t("aud_arm_offsets")))
        self.arm_offsets_label = QLabel("—")
        self.arm_offsets_label.setWordWrap(True)
        self.arm_offsets_label.setStyleSheet(f"color: {color('text')}; font-size: 11px; font-family: 'Consolas';")
        layout.addWidget(self.arm_offsets_label)

        layout.addStretch()
        self.clear_info()

    def _make_field(self):
        lbl = QLabel()
        lbl.setStyleSheet(f"color: {color('text')}; font-size: 11px; font-family: 'Consolas';")
        return lbl

    @staticmethod
    def _field(key, value):
        return f"{_t(key)}: {value}"

    def update_info(self, song, sappy_engine):
        """Actualiza todo el panel con los datos de la canción seleccionada."""
        sid = song["id"]
        cat = song.get("category", "UNKNOWN")

        self.lbl_id.setText(self._field("aud_f_id", f"0x{sid:02X} ({sid})"))
        self.lbl_category.setText(self._field("aud_f_category", category_label(cat)))
        self.lbl_offset.setText(self._field("aud_f_offset", f"0x{song['offset']:06X}"))
        self.lbl_tracks.setText(self._field("aud_f_tracks", song['tracks_count']))
        self.lbl_voicegroup.setText(self._field("aud_f_voicegroup", f"0x{song['voicegroup_ptr']:06X}"))

        if song.get("is_unused"):
            self.lbl_unused.setText(self._field("aud_f_status", _t("aud_status_unused")))
            self.lbl_unused.setStyleSheet(f"color: {color('warning')}; font-size: 11px; font-weight: bold;")
        else:
            self.lbl_unused.setText(self._field("aud_f_status", _t("aud_status_in_use")))
            self.lbl_unused.setStyleSheet(f"color: {color('success')}; font-size: 11px;")

        # Used by
        used = song.get("used_by", [])
        if used:
            self.used_by_list.setText("\n".join(f"- {loc}" for loc in used))
        else:
            self.used_by_list.setText(_t("aud_no_bgm_assignment"))

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
            self.arm_offsets_label.setText(_t("aud_no_arm_refs"))

    def clear_info(self):
        for lbl, key in ((self.lbl_id, "aud_f_id"), (self.lbl_category, "aud_f_category"),
                         (self.lbl_offset, "aud_f_offset"), (self.lbl_tracks, "aud_f_tracks"),
                         (self.lbl_voicegroup, "aud_f_voicegroup"), (self.lbl_unused, "aud_f_status")):
            lbl.setText(self._field(key, "—"))
        self.lbl_unused.setStyleSheet(f"color: {color('text')}; font-size: 11px;")
        self.used_by_list.setText("—")
        self.arm_offsets_label.setText("—")


# ═══════════════════════════════════════════════════════════════════════
# BGM ASSIGNMENTS TABLE
# ═══════════════════════════════════════════════════════════════════════

class BGMAssignmentsPanel(QFrame):
    """Panel colapsable que muestra la tabla de asignaciones BGM leídas de la ROM."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            BGMAssignmentsPanel {{
                background: {color('surface')};
                border: 1px solid {color('border')};
                border-radius: 4px;
            }}
            BGMAssignmentsPanel QFrame, BGMAssignmentsPanel QLabel {{ background: transparent; }}
        """)
        self._collapsed = True
        self._build_ui()

    def _build_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 4, 8, 4)
        self.main_layout.setSpacing(2)

        # Toggle button
        self.toggle_btn = QPushButton(_t("aud_bgm_show"))
        self.toggle_btn.setProperty("variant", "ghost")
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
        self.toggle_btn.setText(_t("aud_bgm_show" if self._collapsed else "aud_bgm_hide"))

    def populate(self, assignments, sound_names):
        """Llena la tabla con las asignaciones BGM."""
        # Limpiar contenido previo
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for a in assignments:
            sid = a["current_song_id"]
            s_name = sound_names.get(str(sid), _t("aud_song_fallback", id=sid))
            mod_tag = f" ({_t('aud_modified')})" if a["is_modified"] else ""
            fg = color("warning") if a["is_modified"] else color("muted")

            text = f"0x{a['rom_offset'] + 0x08000000:08X}  {a['location']:<22s}  -> [{sid:02X}] {s_name}{mod_tag}"
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {fg}; font-size: 11px; font-family: 'Consolas';")
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
        self._track_base = ""
        self.init_ui()

    def load_sound_names(self):
        import json
        import csv
        import os
        from Banco_de_Datos.Utilidades.rutas import get_resource_path

        names = {}
        # Cargar nombres desde el nuevo CSV (prioridad)
        csv_path = get_resource_path("Banco_de_Datos/Listas_de_Nombres/canciones_offsets.csv")
        if os.path.exists(csv_path):
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        names[str(row['ID'])] = row['Name']
            except Exception as e:
                print(f"Error leyendo CSV de canciones: {e}")

        # Cargar fallback (json viejo)
        path = get_resource_path("Banco_de_Datos/Listas_de_Nombres/sonidos.json")
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    json_names = json.load(f)
                    for k, v in json_names.items():
                        if k not in names:
                            names[k] = v
            except:
                pass
        return names

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ── Título y Cabecera ──
        header_row = QHBoxLayout()
        header = QLabel(_t("aud_title"))
        header.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {color('text')};")
        header_row.addWidget(header)
        header_row.addStretch()
        engine_lbl = QLabel(_t("aud_engine"))
        engine_lbl.setStyleSheet(f"color: {color('muted')}; font-size: 12px;")
        header_row.addWidget(engine_lbl)
        layout.addLayout(header_row)

        # ── Filtros por categoría ──
        filter_layout = QHBoxLayout()
        filter_label = QLabel(_t("aud_filter"))
        filter_label.setStyleSheet(f"color: {color('muted')}; font-size: 12px;")
        filter_layout.addWidget(filter_label)

        self.filter_buttons = {}
        filter_defs = [
            ("ALL", "aud_filter_all"),
            ("BGM", "aud_cat_bgm"),
            ("AMBIENT", "aud_cat_ambient"),
            ("UNUSED", "aud_cat_unused"),
            ("SFX", "aud_cat_sfx"),
            ("TITLE", "aud_cat_title"),
        ]

        for cat_key, label_key in filter_defs:
            btn = QPushButton(_t(label_key))
            btn.setCheckable(True)
            btn.setChecked(cat_key == "ALL")
            btn.clicked.connect(lambda checked, k=cat_key: self._on_filter(k))
            filter_layout.addWidget(btn)
            self.filter_buttons[cat_key] = btn

        filter_layout.addStretch()

        # Song count
        self.count_label = QLabel("")
        self.count_label.setStyleSheet(f"color: {color('muted')}; font-size: 12px;")
        filter_layout.addWidget(self.count_label)

        layout.addLayout(filter_layout)

        # ── Área Principal (Lista + Visualizador + Info Panel) ──
        main_h = QHBoxLayout()

        # 1. Lista de Canciones
        self.song_list = QListWidget()
        self.song_list.setFixedWidth(300)
        self.song_list.setStyleSheet(f"""
            QListWidget {{ font-family: 'Consolas'; font-size: 12px; }}
            QListWidget::item {{ padding: 4px 6px; border-bottom: 1px solid {color('surface_alt')}; }}
            QListWidget::item:selected {{ background: {color('surface_alt')}; color: {color('text')}; border-left: 3px solid {color('accent')}; }}
        """)
        self.populate_songs()
        main_h.addWidget(self.song_list)

        # 2. Panel de Visualización Central
        vis_panel = QVBoxLayout()
        self.retro_vis = RetroBitVisualizer()
        vis_panel.addWidget(self.retro_vis, 1)  # el medidor ocupa el espacio libre

        # Waveform label
        self.waveform_label = QLabel(_t("aud_waveform"))
        self.waveform_label.setStyleSheet(f"color: {color('muted')}; font-size: 11px;")
        vis_panel.addWidget(self.waveform_label)

        # Info Pista (Now Playing)
        self.track_info_label = QLabel(_t("aud_no_track"))
        self.track_info_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.track_info_label.setStyleSheet(f"color: {color('muted')}; font-family: 'Consolas'; font-size: 12px;")
        vis_panel.addWidget(self.track_info_label)

        # Controles de reproducción
        ctrl_layout = QHBoxLayout()
        self.btn_play = QPushButton(_t("aud_play"))
        self.btn_stop = QPushButton(_t("aud_stop"))
        self.btn_export = QPushButton(_t("aud_export"))
        self.btn_import = QPushButton(_t("aud_import"))
        self.btn_play.setProperty("variant", "primary")
        self.btn_stop.setProperty("variant", "danger")
        self.btn_export.setProperty("variant", "secondary")
        self.btn_import.setProperty("variant", "secondary")
        ctrl_layout.addWidget(self.btn_play)
        ctrl_layout.addWidget(self.btn_stop)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.btn_export)
        ctrl_layout.addWidget(self.btn_import)

        # Speed control
        speed_layout = QHBoxLayout()
        speed_label = QLabel(_t("aud_speed"))
        speed_label.setStyleSheet(f"color: {color('muted')}; font-size: 12px;")
        self.speed_combo = QComboBox()
        self.speed_combo.addItems([f"{x:.2f}x" for x in np.arange(0.25, 4.25, 0.25)])
        self.speed_combo.setCurrentText("1.00x")
        speed_layout.addWidget(speed_label)
        speed_layout.addWidget(self.speed_combo)
        ctrl_layout.addLayout(speed_layout)

        vis_panel.addLayout(ctrl_layout)

        # Seek bar
        self.seek_bar = QSlider(Qt.Orientation.Horizontal)
        self.seek_bar.setRange(0, 1000)
        self.seek_bar.setStyleSheet(f"""
            QSlider::groove:horizontal {{ background: {color('surface_alt')}; height: 6px; border-radius: 3px; }}
            QSlider::handle:horizontal {{
                background: {color('accent')}; width: 14px; height: 14px;
                margin: -4px 0; border-radius: 7px;
            }}
            QSlider::sub-page:horizontal {{ background: {color('accent')}; border-radius: 3px; }}
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
        self.btn_import.clicked.connect(self.on_import_data)
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
        """Poblar la lista con canciones; las no usadas se marcan con el color de aviso."""
        self.song_list.clear()

        if not hasattr(self.project, 'songs'):
            return

        visible_count = 0
        warning = QColor(color("warning"))

        for song in self.project.songs:
            cat = song.get("category", "UNKNOWN")

            # Aplicar filtro
            if self.current_filter != "ALL" and cat != self.current_filter:
                continue

            s_id = str(song['id'])
            s_name = self.sound_names.get(s_id, _t("aud_track_fallback", id=s_id))

            item = QListWidgetItem(f"[{int(s_id):03d}] {s_name}")
            item.setToolTip(category_label(cat))
            if cat == "UNUSED":
                item.setForeground(warning)

            # Guardar referencia al song data
            item.setData(Qt.ItemDataRole.UserRole, song['id'])

            self.song_list.addItem(item)
            visible_count += 1

        self.count_label.setText(_t("aud_count", n=visible_count, total=len(self.project.songs)))

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

    def _set_track_status(self, status_key, fg_token, bold=False):
        """Muestra la pista seleccionada con su estado (lista / reproduciendo)."""
        if not self._track_base:
            return
        self.track_info_label.setText(f"{self._track_base} ({_t(status_key)})")
        weight = "font-weight: bold; " if bold else ""
        self.track_info_label.setStyleSheet(f"color: {color(fg_token)}; {weight}font-family: 'Consolas'; font-size: 12px;")

    def on_song_selected(self, index):
        if index < 0:
            self.info_panel.clear_info()
            return

        song = self._get_selected_song()
        if not song:
            return

        s_id = str(song['id'])
        s_name = self.sound_names.get(s_id, _t("aud_track_fallback", id=s_id))

        self._track_base = _t("aud_track", id=f"{int(s_id):03d}", name=s_name)
        self._set_track_status("aud_ready", "text")

        # Actualizar panel de info
        self.info_panel.update_info(song, self.project.sappy_engine)

    def on_play(self):
        song = self._get_selected_song()
        if not song:
            return

        if self.is_playing:
            self.on_stop()

        self.btn_play.setText(_t("aud_preparing"))
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
        self.btn_play.setText(_t("aud_play"))
        self.btn_play.setEnabled(True)
        self.btn_stop.setEnabled(True)

        if not success:
            print("No se pudo generar la preview usando Fluidsynth/GBA-Mus-Ripper.")
            return

        self.is_playing = True

        # Cargar datos WAV a memoria para sincronizar el visualizador
        import wave, time, os
        try:
            with wave.open(wav_path, 'rb') as w:
                self.wav_framerate = w.getframerate()
                self.wav_channels = w.getnchannels()
                self.wav_sampwidth = w.getsampwidth()
                self.wav_data = w.readframes(w.getnframes())
            self.playback_start_time = time.time()
        except Exception as e:
            print(f"Error cargando WAV a memoria: {e}")
            self.wav_data = None

        # Reproducción nativa exclusiva con winsound (Garantiza que no haya locks ni problemas de codecs)
        import sys
        if sys.platform == 'win32':
            import winsound
            try:
                norm_path = os.path.normpath(wav_path)
                winsound.PlaySound(norm_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            except Exception as e:
                print(f"Error reproduciendo con winsound: {e}")

        self._set_track_status("aud_playing", "accent", bold=True)

        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self._sync_visuals)
        self.play_timer.start(50)

    def _sync_visuals(self):
        if not self.is_playing: return

        if not hasattr(self, 'wav_data') or not self.wav_data:
            # Fallback a visuales aleatorios si falló la carga
            import random
            v_data = bytes([random.randint(0, 255) for _ in range(32)])
            self.retro_vis.update_from_data(v_data)
            return

        import time
        import numpy as np

        elapsed = time.time() - self.playback_start_time
        frame_idx = int(elapsed * self.wav_framerate)
        byte_idx = frame_idx * self.wav_channels * self.wav_sampwidth

        # Leer ~50ms
        chunk_frames = int(0.05 * self.wav_framerate)
        chunk_bytes = chunk_frames * self.wav_channels * self.wav_sampwidth

        if byte_idx + chunk_bytes > len(self.wav_data):
            # Final de pista (detener reproducción visual)
            self.on_stop()
            return

        chunk = self.wav_data[byte_idx : byte_idx + chunk_bytes]
        if not chunk: return

        if self.wav_sampwidth == 2:
            arr = np.frombuffer(chunk, dtype=np.int16)
        else:
            arr = np.frombuffer(chunk, dtype=np.int8)

        if self.wav_channels == 2:
            arr = arr[::2]

        arr = np.abs(arr)
        bars = 32
        if len(arr) < bars: return

        bin_size = len(arr) // bars
        v_data = bytearray(32)
        for i in range(bars):
            val = np.mean(arr[i*bin_size : (i+1)*bin_size])
            if self.wav_sampwidth == 2:
                norm = int((val / 32768.0) * 255)
            else:
                norm = int((val / 128.0) * 255)
            v_data[i] = max(0, min(255, norm))

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

        self._set_track_status("aud_ready", "text")
        print("Cerrando sesión de audio...")

    def on_export_data(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        import subprocess

        song = self._get_selected_song()
        if not song:
            QMessageBox.warning(self, _t("aud_export"), _t("aud_select_to_export"))
            return

        out_dir = QFileDialog.getExistingDirectory(self, _t("aud_dlg_export_dir"))
        if not out_dir: return

        try:
            self.btn_export.setText(_t("aud_exporting"))
            self.btn_export.setEnabled(False)

            import threading
            def bg_task():
                try:
                    from Banco_de_Datos.Utilidades.rutas import get_resource_path
                    ripper_dir = get_resource_path(os.path.join("Nucleos_Positronicos", "Nucleo_de_Sonido", "gba-mus-ripper"))
                    song_ripper = os.path.join(ripper_dir, "song_ripper.exe")
                    sf2_ripper = os.path.join(ripper_dir, "sound_font_ripper.exe")
                    rom_path = self.project.base_rom_path

                    s_addr = hex(song['offset'])
                    vg_addr = hex(song['voicegroup_ptr'])

                    s_id = song['id']
                    mid_file = os.path.join(out_dir, f"song_{s_id:03d}.mid")
                    sf2_file = os.path.join(out_dir, f"song_{s_id:03d}.sf2")

                    subprocess.run([song_ripper, rom_path, mid_file, s_addr], cwd=ripper_dir, capture_output=True)
                    subprocess.run([sf2_ripper, rom_path, sf2_file, vg_addr], cwd=ripper_dir, capture_output=True)

                    print(f"Exported song {s_id} successfully to {out_dir}")
                except Exception as e:
                    print(f"Export task error: {e}")
                finally:
                    # Reset button
                    self.btn_export.setText(_t("aud_export"))
                    self.btn_export.setEnabled(True)

            threading.Thread(target=bg_task).start()
        except Exception as e:
            print(f"Export Error: {e}")
            self.btn_export.setText(_t("aud_export"))
            self.btn_export.setEnabled(True)

    def on_import_data(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from Nucleos_Positronicos.Nucleo_de_Sonido.midi_compiler import MidiToSappyCompiler

        song = self._get_selected_song()
        if not song:
            QMessageBox.warning(self, _t("aud_import"), _t("aud_select_to_import"))
            return

        midi_path, _ = QFileDialog.getOpenFileName(self, _t("aud_dlg_import_midi"), "", _t("aud_filter_midi"))
        if not midi_path: return

        try:
            self.btn_import.setText(_t("aud_importing"))
            self.btn_import.setEnabled(False)

            compiler = MidiToSappyCompiler(self.project)
            success, msg = compiler.inject_midi(midi_path, song['id'])

            if success:
                QMessageBox.information(self, _t("msg_success"), _t("aud_import_ok", msg=msg))
                # Refresh ROM data and songs
                self.project.sappy_engine.scan_songs()
                self.populate_songs()
            else:
                QMessageBox.warning(self, _t("msg_warning"), _t("aud_import_failed", msg=msg))

        except Exception as e:
            QMessageBox.critical(self, _t("msg_error"), _t("aud_import_error", err=e))
        finally:
            self.btn_import.setText(_t("aud_import"))
            self.btn_import.setEnabled(True)
