from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QLabel, QComboBox, QSpinBox, QMessageBox
)
from PyQt6.QtCore import Qt
from Nucleos_Positronicos.Nucleo_de_Tiendas.shop_codec import ShopCodec, ShopItemEntry


class ShopEditorDialog(QDialog):
    """Editor de tiendas nativas (inventario y precios) para FoMT y MFoMT."""

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.catalog = ShopCodec.load_item_catalog()
        self.shops = ShopCodec.load_shops(project)
        self.current_shop = None

        self.setWindowTitle("Editor de Tiendas - FoMT / MFoMT")
        self.setModal(True)
        self.resize(840, 520)

        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)

        # Lista de tiendas a la izquierda
        self.list_shops = QListWidget()
        for sh in self.shops:
            self.list_shops.addItem(f"{sh.name} (0x{sh.offset:06X})")
        self.list_shops.currentRowChanged.connect(self._on_shop_selected)
        splitter.addWidget(self.list_shops)

        # Tabla derecha
        right_w = QVBoxLayout()
        from PyQt6.QtWidgets import QWidget
        right_container = QWidget()
        right_container.setLayout(right_w)

        self.lbl_shop_info = QLabel("Selecciona una tienda")
        self.lbl_shop_info.setStyleSheet("font-weight: bold;")
        right_w.addWidget(self.lbl_shop_info)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Slot", "Item ID", "Artículo", "Precio (G)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        right_w.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        self.btn_save = QPushButton("Aplicar Cambios en ROM (.fsp)")
        self.btn_save.clicked.connect(self._save_current_shop)
        self.btn_reload = QPushButton("Recargar desde ROM")
        self.btn_reload.clicked.connect(self._reload_shops)
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_reload)
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(btn_close)
        right_w.addLayout(btn_row)

        splitter.addWidget(right_container)
        splitter.setSizes([270, 570])

        if self.shops:
            self.list_shops.setCurrentRow(0)

    def _reload_shops(self):
        curr = self.list_shops.currentRow()
        self.shops = ShopCodec.load_shops(self.project)
        if 0 <= curr < len(self.shops):
            self._on_shop_selected(curr)

    def _on_shop_selected(self, row: int):
        if row < 0 or row >= len(self.shops):
            return
        sh = self.shops[row]
        self.current_shop = sh
        self.lbl_shop_info.setText(
            f"{sh.name} | Offset ROM: 0x{sh.offset:06X} | Categoría: {sh.category} | {sh.count} artículos"
        )

        cat_items = self.catalog.get(sh.category, {})
        self.table.setRowCount(len(sh.entries))

        for r, entry in enumerate(sh.entries):
            slot_item = QTableWidgetItem(str(entry.slot_idx))
            slot_item.setFlags(slot_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 0, slot_item)

            spin_id = QSpinBox()
            spin_id.setRange(0, 500)
            spin_id.setValue(entry.item_id)
            self.table.setCellWidget(r, 1, spin_id)

            cmb_item = QComboBox()
            for iid, iname in sorted(cat_items.items()):
                cmb_item.addItem(f"[{iid:03d}] {iname}", iid)
            idx_match = cmb_item.findData(entry.item_id)
            if idx_match >= 0:
                cmb_item.setCurrentIndex(idx_match)
            else:
                cmb_item.addItem(f"[{entry.item_id:03d}] Item #{entry.item_id}", entry.item_id)
                cmb_item.setCurrentIndex(cmb_item.count() - 1)

            def _make_sync(sp, cm):
                def _on_cmb(idx):
                    val = cm.itemData(idx)
                    if val is not None and sp.value() != val:
                        sp.blockSignals(True)
                        sp.setValue(int(val))
                        sp.blockSignals(False)

                def _on_sp(val):
                    m = cm.findData(val)
                    if m >= 0 and cm.currentIndex() != m:
                        cm.blockSignals(True)
                        cm.setCurrentIndex(m)
                        cm.blockSignals(False)

                cm.currentIndexChanged.connect(_on_cmb)
                sp.valueChanged.connect(_on_sp)

            _make_sync(spin_id, cmb_item)
            self.table.setCellWidget(r, 2, cmb_item)

            spin_price = QSpinBox()
            spin_price.setRange(0, 9999999)
            spin_price.setValue(entry.price)
            self.table.setCellWidget(r, 3, spin_price)

    def _save_current_shop(self):
        if not self.current_shop:
            return
        new_entries = []
        for r in range(self.table.rowCount()):
            spin_id = self.table.cellWidget(r, 1)
            spin_price = self.table.cellWidget(r, 3)
            new_entries.append(ShopItemEntry(
                slot_idx=r,
                item_id=spin_id.value(),
                price=spin_price.value(),
            ))
        self.current_shop.entries = new_entries
        ok, msg = ShopCodec.save_shop(self.project, self.current_shop)
        if ok:
            QMessageBox.information(self, "Tienda Actualizada", msg)
        else:
            QMessageBox.warning(self, "Error", msg)

