"""
FoMT Studio - Editor de Cultivos
Widget PyQt6 para editar semillas, cosechas y datos de crecimiento.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QGroupBox, QSpinBox, QComboBox,
    QPushButton, QMessageBox, QSplitter, QAbstractItemView, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from Nucleos_Positronicos.Nucleo_de_Items.cultivos import (
    CropParser, CROP_NAMES, SEED_NAMES, SEASON_NAMES
)


SEASON_LIST = [
    ("🌸 Primavera", 0b0001),
    ("☀️ Verano",    0b0010),
    ("🍂 Otoño",     0b0100),
    ("❄️ Invierno",  0b1000),
    ("🌸☀️ Primavera/Verano", 0b0011),
    ("☀️🍂 Verano/Otoño",    0b0110),
    ("🌸🍂 Primavera/Otoño", 0b0101),
    ("🌸☀️🍂 Prim/Ver/Otoño",0b0111),
]


class CropEditorWidget(QWidget):
    """Editor principal de cultivos de FoMT."""

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.parser = CropParser(project)
        self._selected_crop = None
        self._selected_seed = None
        self._selected_harvest = None
        self._init_ui()
        self._populate_crops()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)

        # Header
        hdr = QLabel("🌱 Editor de Cultivos")
        hdr.setStyleSheet("font-size: 16px; font-weight: bold; color: #4EC94E; padding: 4px;")
        main_layout.addWidget(hdr)

        # Splitter: list left, detail right
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter, stretch=1)

        # Left: crop table
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel("Cultivos disponibles:")
        lbl.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(lbl)

        self.crop_table = QTableWidget(0, 6)
        self.crop_table.setHorizontalHeaderLabels([
            "Cultivo", "Estación", "Días", "Renace", "P.Semilla", "P.Cosecha"
        ])
        self.crop_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.crop_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.crop_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.crop_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.crop_table.currentCellChanged.connect(lambda r, c, pr, pc: self._on_crop_selected(r))
        self.crop_table.setStyleSheet("""
            QTableWidget { gridline-color: #3a3a3a; }
            QTableWidget::item:selected { background-color: #2a6e2a; }
        """)
        left_layout.addWidget(self.crop_table)
        splitter.addWidget(left)

        # Right: detail editor with tabs
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)

        self.detail_tabs = QTabWidget()
        right_layout.addWidget(self.detail_tabs)

        # Tab 1: Growth data
        growth_tab = QWidget()
        self._build_growth_tab(growth_tab)
        self.detail_tabs.addTab(growth_tab, "📈 Crecimiento")

        # Tab 2: Seed item
        seed_tab = QWidget()
        self._build_seed_tab(seed_tab)
        self.detail_tabs.addTab(seed_tab, "🌰 Semilla")

        # Tab 3: Harvest item
        harvest_tab = QWidget()
        self._build_harvest_tab(harvest_tab)
        self.detail_tabs.addTab(harvest_tab, "🥕 Cosecha")

        splitter.addWidget(right)
        splitter.setSizes([350, 500])

        # Bottom bar
        btn_bar = QHBoxLayout()
        self.btn_save = QPushButton("💾 Guardar Cambios al Proyecto")
        self.btn_save.setStyleSheet("QPushButton { background-color: #2a6e2a; color: white; padding: 6px 12px; font-weight: bold; border-radius: 4px; }"
                                    "QPushButton:hover { background-color: #3a9e3a; }")
        self.btn_save.clicked.connect(self._save_all)
        btn_bar.addStretch()
        btn_bar.addWidget(self.btn_save)
        main_layout.addLayout(btn_bar)

    def _build_growth_tab(self, parent):
        layout = QVBoxLayout(parent)

        # Season selector
        season_box = QGroupBox("🌍 Estación de Crecimiento")
        season_layout = QHBoxLayout(season_box)
        self.season_combo = QComboBox()
        for label, mask in SEASON_LIST:
            self.season_combo.addItem(label, mask)
        season_layout.addWidget(self.season_combo)
        layout.addWidget(season_box)

        # Stage days editor
        stages_box = QGroupBox("📆 Días por Etapa")
        stages_layout = QVBoxLayout(stages_box)

        note = QLabel("Cada fila es un día de transición entre etapas.\nEl total de días determina cuánto tarda en madurar.")
        note.setStyleSheet("color: #aaa; font-size: 11px;")
        stages_layout.addWidget(note)

        self.stage_spins = []
        self.stages_inner = QWidget()
        self.stages_inner_layout = QVBoxLayout(self.stages_inner)
        self.stages_inner_layout.setSpacing(4)
        stages_layout.addWidget(self.stages_inner)
        layout.addWidget(stages_box)

        # Regen info
        regen_box = QGroupBox("🔄 Renacimiento")
        regen_layout = QHBoxLayout(regen_box)
        self.regen_label = QLabel("Este cultivo NO renace al cosechar.")
        self.regen_label.setStyleSheet("color: #ccc;")
        regen_layout.addWidget(self.regen_label)
        layout.addWidget(regen_box)

        layout.addStretch()

        note_ro = QLabel("⚠️ La modificación de etapas requiere Ghidra para localizar\nla tabla binaria de crecimiento. Los datos se leen del texto de ayuda.")
        note_ro.setStyleSheet("color: #e8a838; font-size: 11px; padding: 4px;")
        layout.addWidget(note_ro)

    def _build_seed_tab(self, parent):
        layout = QVBoxLayout(parent)

        info_box = QGroupBox("🌰 Datos de Semilla")
        info_layout = QVBoxLayout(info_box)

        self.seed_name_label = QLabel("—")
        self.seed_name_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        info_layout.addWidget(self.seed_name_label)

        self.seed_desc_label = QLabel("—")
        self.seed_desc_label.setWordWrap(True)
        self.seed_desc_label.setStyleSheet("color: #aaa;")
        info_layout.addWidget(self.seed_desc_label)

        price_row = QHBoxLayout()
        price_row.addWidget(QLabel("Precio de compra (G):"))
        self.seed_price_spin = QSpinBox()
        self.seed_price_spin.setRange(1, 99999)
        self.seed_price_spin.setSingleStep(10)
        self.seed_price_spin.setStyleSheet("QSpinBox { padding: 4px; min-width: 80px; }")
        price_row.addWidget(self.seed_price_spin)
        price_row.addStretch()
        info_layout.addLayout(price_row)

        self.seed_offset_label = QLabel("Offset ROM: —")
        self.seed_offset_label.setStyleSheet("color: #666; font-size: 10px;")
        info_layout.addWidget(self.seed_offset_label)

        layout.addWidget(info_box)
        layout.addStretch()

    def _build_harvest_tab(self, parent):
        layout = QVBoxLayout(parent)

        info_box = QGroupBox("🥕 Datos de Cosecha")
        info_layout = QVBoxLayout(info_box)

        self.harvest_name_label = QLabel("—")
        self.harvest_name_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        info_layout.addWidget(self.harvest_name_label)

        self.harvest_desc_label = QLabel("—")
        self.harvest_desc_label.setWordWrap(True)
        self.harvest_desc_label.setStyleSheet("color: #aaa;")
        info_layout.addWidget(self.harvest_desc_label)

        price_row = QHBoxLayout()
        price_row.addWidget(QLabel("Precio de venta (G):"))
        self.harvest_price_spin = QSpinBox()
        self.harvest_price_spin.setRange(1, 99999)
        self.harvest_price_spin.setSingleStep(10)
        self.harvest_price_spin.setStyleSheet("QSpinBox { padding: 4px; min-width: 80px; }")
        price_row.addWidget(self.harvest_price_spin)
        price_row.addStretch()
        info_layout.addLayout(price_row)

        count_row = QHBoxLayout()
        count_row.addWidget(QLabel("Cantidad por cosecha:"))
        self.harvest_count_spin = QSpinBox()
        self.harvest_count_spin.setRange(1, 9)
        self.harvest_count_spin.setStyleSheet("QSpinBox { padding: 4px; min-width: 60px; }")
        count_row.addWidget(self.harvest_count_spin)
        count_row.addStretch()
        info_layout.addLayout(count_row)

        self.harvest_offset_label = QLabel("Offset ROM: —")
        self.harvest_offset_label.setStyleSheet("color: #666; font-size: 10px;")
        info_layout.addWidget(self.harvest_offset_label)

        layout.addWidget(info_box)
        layout.addStretch()

    def _populate_crops(self):
        """Llena la tabla con todos los cultivos."""
        rows = self.parser.get_all_for_display()
        self.crop_table.setRowCount(len(rows))

        SEASON_EMOJI = {
            "Spring": "🌸", "Summer": "☀️", "Fall": "🍂", "Winter": "❄️",
        }

        for i, row in enumerate(rows):
            items = [
                row["Cultivo"],
                row["Estación"],
                str(row["Días Totales"]) + "d",
                "✔" if row["Renace"] == "Sí" else "—",
                str(row["Precio Semilla"]) + "G",
                str(row["Precio Cosecha"]) + "G",
            ]
            for j, val in enumerate(items):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if j == 3 and val == "✔":
                    item.setForeground(QColor("#4EC94E"))
                self.crop_table.setItem(i, j, item)

        if self.crop_table.rowCount() > 0:
            self.crop_table.selectRow(0)

    def _on_crop_selected(self, row):
        if row < 0 or row >= len(self.parser.crops):
            return
        crop = self.parser.crops[row]
        self._selected_crop = crop
        self._selected_seed = crop.seed
        self._selected_harvest = crop.harvest

        # Growth tab
        # Season
        mask = crop.season_mask
        for i in range(self.season_combo.count()):
            if self.season_combo.itemData(i) == mask:
                self.season_combo.setCurrentIndex(i)
                break

        # Stages
        for spin in self.stage_spins:
            spin.deleteLater()
        self.stage_spins.clear()

        for j in range(self.stages_inner_layout.count()):
            w = self.stages_inner_layout.itemAt(j)
            if w and w.widget():
                w.widget().deleteLater()

        for si, days in enumerate(crop.stage_days):
            row_w = QWidget()
            row_l = QHBoxLayout(row_w)
            row_l.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(f"Etapa {si+1} → {si+2}:")
            lbl.setMinimumWidth(90)
            spin = QSpinBox()
            spin.setRange(1, 30)
            spin.setValue(days)
            spin.setStyleSheet("QSpinBox { padding: 2px; }")
            row_l.addWidget(lbl)
            row_l.addWidget(spin)
            row_l.addStretch()
            self.stages_inner_layout.addWidget(row_w)
            self.stage_spins.append(spin)

        if crop.regrows:
            self.regen_label.setText(f"✔ Renace al cosechar (vuelve a la etapa {crop.regen_to + 1})")
            self.regen_label.setStyleSheet("color: #4EC94E;")
        else:
            self.regen_label.setText("✘ No renace. Solo se cosecha una vez.")
            self.regen_label.setStyleSheet("color: #e05050;")

        # Seed tab
        if crop.seed:
            self.seed_name_label.setText(crop.seed.name)
            self.seed_desc_label.setText(crop.seed.desc[:120])
            self.seed_price_spin.setValue(crop.seed.buy_price)
            self.seed_offset_label.setText(f"Offset ROM: 0x{crop.seed.offset:06X}")
        else:
            self.seed_name_label.setText("(semilla no encontrada)")
            self.seed_desc_label.setText("")

        # Harvest tab
        if crop.harvest:
            self.harvest_name_label.setText(crop.harvest.name)
            self.harvest_desc_label.setText(crop.harvest.desc[:120])
            self.harvest_price_spin.setValue(crop.harvest.sell_price)
            self.harvest_count_spin.setValue(crop.harvest.harvest_count)
            self.harvest_offset_label.setText(f"Offset ROM: 0x{crop.harvest.offset:06X}")
        else:
            self.harvest_name_label.setText("(cosecha no encontrada)")
            self.harvest_desc_label.setText("")

    def _save_all(self):
        """Guarda los cambios en el buffer del proyecto."""
        if not self._selected_crop:
            return

        changed = []

        # Save seed price
        if self._selected_seed:
            new_price = self.seed_price_spin.value()
            if new_price != self._selected_seed.buy_price:
                self.parser.save_seed_buy_price(self._selected_seed, new_price)
                changed.append(f"Precio semilla {self._selected_seed.name}: {new_price}G")

        # Save harvest price + count
        if self._selected_harvest:
            new_sell = self.harvest_price_spin.value()
            new_count = self.harvest_count_spin.value()
            if new_sell != self._selected_harvest.sell_price:
                self.parser.save_harvest_sell_price(self._selected_harvest, new_sell)
                changed.append(f"Precio cosecha {self._selected_harvest.name}: {new_sell}G")
            if new_count != self._selected_harvest.harvest_count:
                self.parser.save_harvest_count(self._selected_harvest, new_count)
                changed.append(f"Cantidad cosecha {self._selected_harvest.name}: {new_count}")

        if changed:
            self._populate_crops()  # Refresh table
            QMessageBox.information(
                self, "Cambios Guardados",
                "✅ Los siguientes cambios han sido aplicados al buffer del proyecto:\n\n"
                + "\n".join(f"• {c}" for c in changed)
                + "\n\nUsa Archivo → Compilar ROM para aplicar definitivamente."
            )
        else:
            QMessageBox.information(self, "Sin Cambios", "No se detectaron cambios para guardar.")
