import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QPushButton, QComboBox, QSpinBox, QFileDialog, QMessageBox
)
from Banco_de_Datos.Gestor_Saves import GestorSaves


class SaveEditorDialog(QDialog):
    """Editor de partidas guardadas (.sav) para FoMT y MFoMT."""

    def __init__(self, project=None, parent=None):
        super().__init__(parent)
        self.project = project
        default_ver = "mfomt" if (project and getattr(project, "is_mfomt", False)) else "fomt"
        self.gestor = GestorSaves(version=default_ver, slot=0)

        self.setWindowTitle("Editor de Partidas (.sav) - FoMT / MFoMT")
        self.setModal(True)
        self.resize(520, 560)

        layout = QVBoxLayout(self)

        # --- Archivo, Versión y Slot ---
        top_group = QGroupBox("Archivo y Perfil")
        top_form = QFormLayout(top_group)

        file_row = QHBoxLayout()
        self.lbl_file = QLabel("Ningún archivo .sav cargado")
        self.btn_open = QPushButton("Abrir .sav...")
        self.btn_open.clicked.connect(self._open_save)
        file_row.addWidget(self.lbl_file, 1)
        file_row.addWidget(self.btn_open)
        top_form.addRow("Archivo:", file_row)

        self.cmb_version = QComboBox()
        self.cmb_version.addItem("FoMT (Harvest Moon: Friends of Mineral Town)", "fomt")
        self.cmb_version.addItem("MFoMT (More Friends of Mineral Town)", "mfomt")
        self.cmb_version.setCurrentIndex(1 if default_ver == "mfomt" else 0)
        self.cmb_version.currentIndexChanged.connect(self._on_profile_changed)
        top_form.addRow("Versión:", self.cmb_version)

        self.cmb_slot = QComboBox()
        self.cmb_slot.addItem("Slot 1 (Principal)", 0)
        self.cmb_slot.addItem("Slot 2 (Secundario)", 1)
        self.cmb_slot.currentIndexChanged.connect(self._on_profile_changed)
        top_form.addRow("Slot:", self.cmb_slot)

        layout.addWidget(top_group)

        # --- Datos de Granja y Jugador ---
        player_group = QGroupBox("Jugador y Granja")
        player_form = QFormLayout(player_group)

        self.spin_gold = QSpinBox()
        self.spin_gold.setRange(0, 999999999)
        player_form.addRow("Oro (G):", self.spin_gold)

        self.spin_lumber = QSpinBox()
        self.spin_lumber.setRange(0, 9999)
        player_form.addRow("Madera (Lumber):", self.spin_lumber)

        self.spin_stamina = QSpinBox()
        self.spin_stamina.setRange(0, 255)
        player_form.addRow("Stamina:", self.spin_stamina)

        self.spin_fatigue = QSpinBox()
        self.spin_fatigue.setRange(0, 255)
        player_form.addRow("Fatiga:", self.spin_fatigue)

        self.cmb_rucksack = QComboBox()
        self.cmb_rucksack.addItems(["Nivel 0 (Pequeña)", "Nivel 1 (Mediana)", "Nivel 2 (Grande)"])
        player_form.addRow("Mochila:", self.cmb_rucksack)

        self.cmb_house = QComboBox()
        self.cmb_house.addItems(["Nivel 0 (Inicial)", "Nivel 1 (Ampliación 1)", "Nivel 2 (Ampliación 2)"])
        player_form.addRow("Casa:", self.cmb_house)

        layout.addWidget(player_group)

        # --- Calendario y Clima ---
        cal_group = QGroupBox("Calendario y Clima")
        cal_form = QFormLayout(cal_group)

        self.spin_year = QSpinBox()
        self.spin_year.setRange(1, 999)
        cal_form.addRow("Año:", self.spin_year)

        self.cmb_season = QComboBox()
        self.cmb_season.addItems(["Primavera", "Verano", "Otoño", "Invierno"])
        cal_form.addRow("Estación:", self.cmb_season)

        self.spin_day = QSpinBox()
        self.spin_day.setRange(1, 30)
        cal_form.addRow("Día:", self.spin_day)

        self.cmb_weather = QComboBox()
        self.cmb_weather.addItems(["Soleado", "Lluvioso", "Nevado", "Tifón / Tormenta", "Ventisca"])
        cal_form.addRow("Clima:", self.cmb_weather)

        layout.addWidget(cal_group)

        # --- Experiencia de Herramientas ---
        tools_group = QGroupBox("Experiencia de Herramientas (0 - 65535)")
        tools_form = QFormLayout(tools_group)
        self.tool_spins = []
        for idx, t_name in enumerate(GestorSaves.TOOL_NAMES):
            sp = QSpinBox()
            sp.setRange(0, 65535)
            self.tool_spins.append(sp)
            tools_form.addRow(t_name + ":", sp)
        layout.addWidget(tools_group)

        # --- Botones ---
        btns = QHBoxLayout()
        self.btn_save = QPushButton("Guardar .sav")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save_current)
        self.btn_save_as = QPushButton("Guardar como...")
        self.btn_save_as.setEnabled(False)
        self.btn_save_as.clicked.connect(self._save_as)
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(self.btn_save)
        btns.addWidget(self.btn_save_as)
        btns.addWidget(btn_close)
        layout.addLayout(btns)

    def _open_save(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo .sav", "", "GBA Save Files (*.sav *.sgm);;All Files (*)"
        )
        if not path:
            return
        if not self.gestor.load_save(path):
            QMessageBox.warning(self, "Error", "No se pudo leer el archivo .sav.")
            return
        self.lbl_file.setText(f"{os.path.basename(path)} ({len(self.gestor.save_data)} bytes)")
        self.btn_save.setEnabled(True)
        self.btn_save_as.setEnabled(True)
        self._refresh_fields()

    def _on_profile_changed(self):
        self.gestor.set_version(self.cmb_version.currentData())
        self.gestor.set_slot(self.cmb_slot.currentData())
        if self.gestor.save_data:
            self._refresh_fields()

    def _refresh_fields(self):
        self.spin_gold.setValue(min(999999999, self.gestor.get_player_gold()))
        self.spin_lumber.setValue(min(9999, self.gestor.get_lumber()))
        self.spin_stamina.setValue(self.gestor.get_player_stamina())
        self.spin_fatigue.setValue(self.gestor.get_player_fatigue())
        self.cmb_rucksack.setCurrentIndex(min(2, max(0, self.gestor.get_rucksack_level())))
        self.cmb_house.setCurrentIndex(min(2, max(0, self.gestor.get_house_size())))
        self.spin_year.setValue(max(1, min(999, self.gestor.get_year())))
        self.cmb_season.setCurrentIndex(min(3, max(0, self.gestor.get_season())))
        self.spin_day.setValue(max(1, min(30, self.gestor.get_day())))
        self.cmb_weather.setCurrentIndex(min(4, max(0, self.gestor.get_weather())))
        for idx, sp in enumerate(self.tool_spins):
            sp.setValue(self.gestor.get_tool_exp(idx))

    def _apply_fields(self):
        self.gestor.set_player_gold(self.spin_gold.value())
        self.gestor.set_lumber(self.spin_lumber.value())
        self.gestor.set_player_stamina(self.spin_stamina.value())
        self.gestor.set_player_fatigue(self.spin_fatigue.value())
        self.gestor.set_rucksack_level(self.cmb_rucksack.currentIndex())
        self.gestor.set_house_size(self.cmb_house.currentIndex())
        self.gestor.set_year(self.spin_year.value())
        self.gestor.set_season(self.cmb_season.currentIndex())
        self.gestor.set_day(self.spin_day.value())
        self.gestor.set_weather(self.cmb_weather.currentIndex())
        for idx, sp in enumerate(self.tool_spins):
            self.gestor.set_tool_exp(idx, sp.value())

    def _save_current(self):
        self._apply_fields()
        if self.gestor.save_save():
            QMessageBox.information(self, "Guardado", f"Partida guardada en:\n{self.gestor.filepath}")
        else:
            QMessageBox.warning(self, "Error", "No se pudo guardar el archivo .sav.")

    def _save_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar .sav como", self.gestor.filepath or "partida.sav", "GBA Save Files (*.sav);;All Files (*)"
        )
        if not path:
            return
        self._apply_fields()
        if self.gestor.save_save(path):
            self.lbl_file.setText(f"{os.path.basename(path)} ({len(self.gestor.save_data)} bytes)")
            QMessageBox.information(self, "Guardado", f"Partida guardada en:\n{path}")
        else:
            QMessageBox.warning(self, "Error", "No se pudo guardar el archivo .sav.")

