# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v4.0.0)
# "The Greatest Show - Final Release"
# Desarrollado por: Denisovich728
# ============================================================
"""
item_editor.py - Editor Canonico de Items, Iconos y Atributos FoMT GBA
Integra los 344 items con extraccion en tiempo real de iconos OAM/4bpp,
edicion de nombres, descripciones multilineas, Graphic IDs, Stamina, Fatiga,
precios y tiers.
"""

from typing import Optional, List, Dict, Any
from PIL import Image

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView,
    QPushButton, QLabel, QMessageBox, QHeaderView, QComboBox,
    QTabWidget, QGroupBox, QTextEdit, QLineEdit, QSpinBox,
    QCheckBox, QFrame, QSplitter, QAbstractItemView, QFileDialog
)
from PyQt6.QtGui import (
    QStandardItemModel, QStandardItem, QPixmap, QIcon,
    QPainter, QColor
)
from PyQt6.QtCore import Qt, QSize

from Consola_de_Comando.i18n import tr
from Consola_de_Comando.i18n import t as _t
from Consola_de_Comando.utils import NameEditDelegate
from Nucleos_Positronicos.Nucleo_de_Items.objetos import BaseItem, ToolItem, FoodItem, MiscItem


# ============================================================
#  WIDGET PREVIEW DE ICONO CON PATRON CHECKERBOARD
# ============================================================

class CheckerboardIconLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(64, 64)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background: #0E0E14; border: 1px solid #2A2A38; border-radius: 4px;")
        self._pixmap = None
        self._pattern = self._create_pattern()

    def _create_pattern(self) -> QPixmap:
        pm = QPixmap(16, 16)
        p = QPainter(pm)
        c1 = QColor(18, 18, 24)
        c2 = QColor(28, 28, 38)
        p.fillRect(0, 0, 8, 8, c1)
        p.fillRect(8, 8, 8, 8, c1)
        p.fillRect(8, 0, 8, 8, c2)
        p.fillRect(0, 8, 8, 8, c2)
        p.end()
        return pm

    def set_pixmap(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawTiledPixmap(self.rect(), self._pattern)
        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                48, 48,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            p.drawPixmap(x, y, scaled)
        p.end()


# ============================================================
#  PANEL DE INSPECCION Y EDICION DETALLADA
# ============================================================

class ItemInspectorPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_item: Optional[BaseItem] = None
        self.setFixedWidth(340)
        self.setStyleSheet("""
            ItemInspectorPanel {
                background: #0A0A10;
                border: 1px solid #1F1F2C;
                border-radius: 6px;
            }
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        title = QLabel(_t("itm_inspector"))
        title.setStyleSheet("color: #00FF96; font-size: 12px; font-weight: bold; letter-spacing: 2px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine); sep.setStyleSheet("color: #1F1F2C;")
        layout.addWidget(sep)

        # Cabecera con Icono y datos basicos
        header_row = QHBoxLayout()
        self.lbl_icon = CheckerboardIconLabel()
        header_row.addWidget(self.lbl_icon)

        v_info = QVBoxLayout()
        self.lbl_header_name = QLabel(_t("itm_select"))
        self.lbl_header_name.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 13px;")
        v_info.addWidget(self.lbl_header_name)

        self.lbl_header_id = QLabel(_t("itm_id_empty"))
        self.lbl_header_id.setStyleSheet("color: #777788; font-family: 'Consolas'; font-size: 11px;")
        v_info.addWidget(self.lbl_header_id)

        self.lbl_category = QLabel(_t("itm_category_empty"))
        self.lbl_category.setStyleSheet("color: #00BFFF; font-size: 11px;")
        v_info.addWidget(self.lbl_category)

        header_row.addLayout(v_info)
        layout.addLayout(header_row)

        # Botones de Modding Gráfico (Importar / Exportar Icono)
        icon_btn_row = QHBoxLayout()
        self.btn_export_icon = QPushButton(_t("itm_btn_export_png"))
        self.btn_export_icon.setStyleSheet("background: #1F3A5F; color: #89B4FA; font-weight: bold; font-size: 10px; padding: 4px;")
        self.btn_export_icon.clicked.connect(self._on_export_icon_clicked)
        icon_btn_row.addWidget(self.btn_export_icon)

        self.btn_import_icon = QPushButton(_t("itm_btn_reinject_png"))
        self.btn_import_icon.setStyleSheet("background: #5F1F3A; color: #FF89B4; font-weight: bold; font-size: 10px; padding: 4px;")
        self.btn_import_icon.clicked.connect(self._on_import_icon_clicked)
        icon_btn_row.addWidget(self.btn_import_icon)
        layout.addLayout(icon_btn_row)

        # Campos editables
        form_frame = QFrame()
        form_layout = QVBoxLayout(form_frame)
        form_layout.setContentsMargins(0, 4, 0, 4)
        form_layout.setSpacing(6)

        # 1. Nombre
        form_layout.addWidget(QLabel(_t("itm_name_rom"), styleSheet="color: #888899; font-size: 10px;"))
        self.txt_name = QLineEdit()
        self.txt_name.setStyleSheet("background: #14141E; color: white; border: 1px solid #2A2A38; padding: 4px; border-radius: 3px;")
        form_layout.addWidget(self.txt_name)

        # 2. Graphic ID
        gid_row = QHBoxLayout()
        gid_row.addWidget(QLabel(_t("itm_graphic_id"), styleSheet="color: #888899; font-size: 10px;"))
        self.spn_gid = QSpinBox()
        self.spn_gid.setRange(0, 600)
        self.spn_gid.setStyleSheet("background: #14141E; color: #FFD700; border: 1px solid #2A2A38; padding: 2px;")
        self.spn_gid.valueChanged.connect(self._on_gid_changed)
        gid_row.addWidget(self.spn_gid)
        form_layout.addLayout(gid_row)

        # 3. Parametros Comida (Stamina y Fatiga)
        self.food_group = QGroupBox(_t("itm_grp_food"))
        self.food_group.setStyleSheet("QGroupBox { color: #00FF96; font-size: 10px; font-weight: bold; border: 1px solid #1F1F2C; margin-top: 6px; padding-top: 8px; }")
        fg_layout = QHBoxLayout(self.food_group)

        fg_layout.addWidget(QLabel(_t("itm_stamina"), styleSheet="color: #CCCCCC; font-size: 10px;"))
        self.spn_stamina = QSpinBox()
        self.spn_stamina.setRange(-128, 127)
        self.spn_stamina.setStyleSheet("background: #14141E; color: #00FF96; border: 1px solid #2A2A38; padding: 2px;")
        fg_layout.addWidget(self.spn_stamina)

        fg_layout.addWidget(QLabel(_t("itm_fatigue"), styleSheet="color: #CCCCCC; font-size: 10px;"))
        self.spn_fatigue = QSpinBox()
        self.spn_fatigue.setRange(-128, 127)
        self.spn_fatigue.setStyleSheet("background: #14141E; color: #FF7777; border: 1px solid #2A2A38; padding: 2px;")
        fg_layout.addWidget(self.spn_fatigue)

        self.chk_drink = QCheckBox(_t("itm_drink"))
        self.chk_drink.setStyleSheet("color: #00BFFF; font-size: 10px;")
        fg_layout.addWidget(self.chk_drink)

        form_layout.addWidget(self.food_group)

        # 4. Parametros Herramienta (Tier / Nivel)
        self.tool_group = QGroupBox(_t("itm_grp_tool"))
        self.tool_group.setStyleSheet("QGroupBox { color: #00BFFF; font-size: 10px; font-weight: bold; border: 1px solid #1F1F2C; margin-top: 6px; padding-top: 8px; }")
        tg_layout = QHBoxLayout(self.tool_group)
        tg_layout.addWidget(QLabel(_t("itm_tier"), styleSheet="color: #CCCCCC; font-size: 10px;"))
        self.combo_tier = QComboBox()
        self.combo_tier.addItems([_t("itm_tier_iron_normal"), _t("itm_tier_copper"), _t("itm_tier_silver"), _t("itm_tier_gold"), "Mystrile", _t("itm_tier_cursed"), _t("itm_tier_blessed"), _t("itm_tier_mythic")])
        self.combo_tier.setStyleSheet("background: #14141E; color: white; padding: 2px 6px; font-size: 10px;")
        tg_layout.addWidget(self.combo_tier)
        form_layout.addWidget(self.tool_group)

        # 5. Precios
        price_row = QHBoxLayout()
        price_row.addWidget(QLabel(_t("itm_sell"), styleSheet="color: #888899; font-size: 10px;"))
        self.spn_sell = QSpinBox()
        self.spn_sell.setRange(0, 999999)
        self.spn_sell.setStyleSheet("background: #14141E; color: white; border: 1px solid #2A2A38; padding: 2px;")
        price_row.addWidget(self.spn_sell)

        price_row.addWidget(QLabel(_t("itm_buy"), styleSheet="color: #888899; font-size: 10px;"))
        self.spn_buy = QSpinBox()
        self.spn_buy.setRange(0, 999999)
        self.spn_buy.setStyleSheet("background: #14141E; color: white; border: 1px solid #2A2A38; padding: 2px;")
        price_row.addWidget(self.spn_buy)
        form_layout.addLayout(price_row)

        # 6. Descripcion multilineal
        form_layout.addWidget(QLabel(_t("itm_desc_rom"), styleSheet="color: #888899; font-size: 10px;"))
        self.txt_desc = QTextEdit()
        self.txt_desc.setFixedHeight(70)
        self.txt_desc.setStyleSheet("background: #14141E; color: white; border: 1px solid #2A2A38; font-family: 'Consolas'; font-size: 11px;")
        form_layout.addWidget(self.txt_desc)

        layout.addWidget(form_frame)

        self.lbl_feedback = QLabel("")
        self.lbl_feedback.setStyleSheet("color: #00FF96; font-size: 10px; font-weight: bold;")
        self.lbl_feedback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_feedback)

        # Boton Aplicar Cambios
        self.btn_apply = QPushButton(_t("itm_btn_apply"))
        self.btn_apply.setStyleSheet("""
            QPushButton { background: #00FF96; color: black; font-weight: bold; padding: 8px; border-radius: 4px; font-size: 11px; }
            QPushButton:hover { background: #33FFB0; }
        """)
        self.btn_apply.clicked.connect(self._on_apply_clicked)
        layout.addWidget(self.btn_apply)

        layout.addStretch()

    def load_item(self, item: Optional[BaseItem]):
        self.current_item = item
        if not item:
            self.lbl_header_name.setText(_t("itm_select"))
            self.lbl_header_id.setText(_t("itm_id_empty"))
            self.lbl_category.setText(_t("itm_category_empty"))
            self.lbl_icon.set_pixmap(QPixmap())
            self.txt_name.clear()
            self.spn_gid.setValue(0)
            self.txt_desc.clear()
            self.spn_stamina.setValue(0)
            self.spn_fatigue.setValue(0)
            self.chk_drink.setChecked(False)
            self.spn_sell.setValue(0)
            self.spn_buy.setValue(0)
            return

        self.lbl_header_name.setText(item.name_str)
        self.lbl_header_id.setText(_t("itm_id", id=f"0x{item.index:02X}", idx=item.index, gid=item.global_id))
        self.lbl_category.setText(_t("itm_category", cat=item.category))

        pix = item.get_icon_pixmap(scale=3)
        self.lbl_icon.set_pixmap(pix)

        self.txt_name.setText(item.name_str)
        self.spn_gid.blockSignals(True)
        self.spn_gid.setValue(item.graphic_id)
        self.spn_gid.blockSignals(False)

        self.txt_desc.setPlainText(item.desc_str)
        self.spn_sell.setValue(item.price)
        self.spn_buy.setValue(item.buy_price)

        # Mostrar/ocultar paneles segun categoria
        is_food = (item.category == "Consumible/Comida")
        is_tool = (item.category == "Herramienta")

        self.food_group.setVisible(is_food)
        self.tool_group.setVisible(is_tool)

        if is_food:
            self.spn_stamina.setValue(item.stamina)
            self.spn_fatigue.setValue(item.fatigue)
            self.chk_drink.setChecked(item.is_drink)

        if is_tool:
            tier_idx = min(7, max(0, item.tier_or_flags & 7))
            self.combo_tier.setCurrentIndex(tier_idx)

    def _on_gid_changed(self, val: int):
        if not self.current_item or not self.current_item.parser:
            return
        pix = self.current_item.parser.icon_engine.extract_icon_pixmap(val, scale=3)
        self.lbl_icon.set_pixmap(pix)

    def _on_apply_clicked(self):
        if not self.current_item:
            return

        item = self.current_item
        new_name = self.txt_name.text().strip()
        new_desc = self.txt_desc.toPlainText().strip()
        new_gid = self.spn_gid.value()
        new_sell = self.spn_sell.value()
        new_buy = self.spn_buy.value()

        # Guardar en memoria y ROM
        if new_name != item.name_str:
            item.save_name_in_place(new_name)

        if new_desc != item.desc_str:
            item.save_desc_in_place(new_desc)

        if new_gid != item.graphic_id:
            item.save_graphic_id(new_gid)

        if new_sell != item.price:
            item.save_sell_price(new_sell)

        if new_buy != item.buy_price:
            item.save_buy_price(new_buy)

        if isinstance(item, FoodItem):
            item.save_food_stats(
                self.spn_stamina.value(),
                self.spn_fatigue.value(),
                self.chk_drink.isChecked(),
                new_gid
            )
        elif isinstance(item, ToolItem):
            item.save_tier(self.combo_tier.currentIndex())

        # Refrescar cabecera
        self.load_item(item)
        self.lbl_feedback.setText(_t("itm_saved_feedback", name=item.name_str))
        if self.isVisible():
            QMessageBox.information(self, _t("itm_updated_title"), _t("itm_updated", name=item.name_str))

    def _on_export_icon_clicked(self):
        if not self.current_item or not self.current_item.parser or not self.current_item.parser.icon_engine:
            QMessageBox.warning(self, _t("itm_export_icon_title"), _t("itm_need_icon_item"))
            return

        eng = self.current_item.parser.icon_engine
        pil_img = eng.extract_icon_pil(self.current_item.graphic_id)
        if not pil_img:
            QMessageBox.warning(self, _t("itm_export_icon_title"), _t("itm_icon_extract_failed", gid=self.current_item.graphic_id))
            return

        default_name = f"Item_{self.current_item.index:03d}_{self.current_item.name_str.replace(' ', '_')}_GID{self.current_item.graphic_id}.png"
        path, _ = QFileDialog.getSaveFileName(self, _t("itm_dlg_export_icon"), default_name, _t("itm_filter_png"))
        if not path:
            return

        try:
            pil_img.save(path)
            QMessageBox.information(self, _t("itm_export_ok_title"), _t("itm_icon_saved", path=path))
        except Exception as e:
            QMessageBox.critical(self, _t("itm_export_error_title"), _t("itm_image_save_error", err=e))

    def _on_import_icon_clicked(self):
        if not self.current_item or not self.current_item.parser or not self.current_item.parser.icon_engine:
            QMessageBox.warning(self, _t("itm_reinject_title"), _t("itm_need_icon_item"))
            return

        path, _ = QFileDialog.getOpenFileName(self, _t("itm_dlg_select_icon"), "", _t("itm_filter_png_all"))
        if not path:
            return

        try:
            from PIL import Image
            import_img = Image.open(path)
            project = getattr(self.current_item.parser, 'project', None)
            eng = self.current_item.parser.icon_engine

            success = eng.inject_icon_pil(self.current_item.graphic_id, import_img, project=project)
            if success:
                # Recargar visualización
                self.load_item(self.current_item)
                # Notificar a la tabla del editor si está presente para refrescar iconos
                parent_widget = self.parent()
                while parent_widget and not isinstance(parent_widget, ItemEditorWidget):
                    parent_widget = parent_widget.parent()
                if parent_widget and hasattr(parent_widget, 'filter_data'):
                    parent_widget.filter_data()

                QMessageBox.information(self, _t("itm_reinject_ok_title"),
                    _t("itm_reinject_ok", gid=self.current_item.graphic_id, name=self.current_item.name_str))
            else:
                QMessageBox.warning(self, _t("itm_inject_error_title"), _t("itm_inject_failed"))
        except Exception as e:
            QMessageBox.critical(self, _t("itm_inject_fail_title"), _t("itm_image_process_error", err=e))


# ============================================================
#  EDITOR PRINCIPAL DE ITEMS
# ============================================================

class ItemEditorWidget(QWidget):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.items: List[BaseItem] = []
        self._current_table_items: List[BaseItem] = []

        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Toolbar superior
        toolbar = QHBoxLayout()
        title = QLabel(_t("itm_editor_title"))
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #00FF96; letter-spacing: 1px;")
        toolbar.addWidget(title)
        toolbar.addStretch()

        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText(_t("itm_filter_placeholder"))
        self.txt_filter.setFixedWidth(240)
        self.txt_filter.setStyleSheet("""
            QLineEdit { background: #0E0E14; color: #00E5FF; border: 1px solid #2A2A38; border-radius: 4px; padding: 4px 8px; font-size: 11px; }
            QLineEdit:focus { border-color: #00FF96; }
        """)
        self.txt_filter.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self.txt_filter)

        self.btn_refresh = QPushButton(_t("itm_btn_reload"))
        self.btn_refresh.setStyleSheet("background: #1A1A26; color: white; border: 1px solid #333348; padding: 5px 12px; border-radius: 4px; font-size: 11px;")
        self.btn_refresh.clicked.connect(self.load_data)
        toolbar.addWidget(self.btn_refresh)

        self.btn_save_all = QPushButton(_t("itm_btn_save_rom"))
        self.btn_save_all.setStyleSheet("background: #2e7d32; color: white; font-weight: bold; padding: 5px 14px; border-radius: 4px; font-size: 11px;")
        self.btn_save_all.clicked.connect(self.save_all_to_rom)
        toolbar.addWidget(self.btn_save_all)

        layout.addLayout(toolbar)

        # Splitter Central
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background-color: #1F1F2C; }")

        # Tab Widget para las 3 categorias
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #1F1F2C; background: #0A0A10; }
            QTabBar::tab { background: #12121A; color: #888899; padding: 6px 16px; border: 1px solid #1F1F2C; }
            QTabBar::tab:selected { background: #1E1E2C; color: #00FF96; font-weight: bold; border-bottom: 2px solid #00FF96; }
        """)

        # 1. Herramientas
        self.table_tools = self._create_table()
        self.tabs.addTab(self.table_tools, _t("itm_tab_tools"))

        # 2. Comestibles
        self.table_foods = self._create_table()
        self.tabs.addTab(self.table_foods, _t("itm_tab_foods"))

        # 3. Variados
        self.table_misc = self._create_table()
        self.tabs.addTab(self.table_misc, _t("itm_tab_misc"))

        self.tabs.currentChanged.connect(self._on_tab_changed)
        splitter.addWidget(self.tabs)

        # Panel de Inspeccion a la derecha
        self.inspector = ItemInspectorPanel()
        splitter.addWidget(self.inspector)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        layout.addWidget(splitter, 1)

        # Conectar selecciones de tabla
        self.table_tools.selectionModel().selectionChanged.connect(self._on_row_selected)
        self.table_foods.selectionModel().selectionChanged.connect(self._on_row_selected)
        self.table_misc.selectionModel().selectionChanged.connect(self._on_row_selected)

    def _create_table(self) -> QTableView:
        table = QTableView()
        model = QStandardItemModel()
        table.setModel(model)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setStyleSheet("""
            QTableView {
                background: #09090F; color: #FFFFFF;
                gridline-color: #1A1A26; border: none;
                font-family: 'Consolas'; font-size: 11px;
            }
            QTableView::item { padding: 4px; }
            QTableView::item:selected { background: #163328; color: #00FF96; }
            QHeaderView::section {
                background: #12121A; color: #888899;
                padding: 4px; border: 1px solid #1F1F2C; font-weight: bold;
            }
        """)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.verticalHeader().setDefaultSectionSize(28)
        return table

    def load_data(self):
        if not self.project:
            return
        try:
            self.items = self.project.item_parser.scan_items()
            self._populate_category_tables()
        except Exception as e:
            QMessageBox.warning(self, _t("msg_error"), _t("itm_load_error", err=e))

    def _populate_category_tables(self):
        self._populate_table(self.table_tools, "Herramienta")
        self._populate_table(self.table_foods, "Consumible/Comida")
        self._populate_table(self.table_misc, "Artículo")

    def _populate_table(self, table: QTableView, category: str):
        model = table.model()
        model.clear()

        query = self.txt_filter.text().strip().lower()

        if category == "Consumible/Comida":
            headers = [_t("itm_col_icon"), "ID", _t("itm_col_name"), "Graphic ID", _t("itm_col_stamina"), _t("itm_col_fatigue"), _t("itm_drink"), _t("itm_col_sell"), _t("itm_col_buy")]
        elif category == "Herramienta":
            headers = [_t("itm_col_icon"), "ID", _t("itm_col_name"), "Graphic ID", _t("itm_col_tier"), _t("itm_col_sell"), _t("itm_col_buy")]
        else:
            headers = [_t("itm_col_icon"), "ID", _t("itm_col_name"), "Graphic ID", "Flags", _t("itm_col_sell"), _t("itm_col_buy")]

        model.setHorizontalHeaderLabels(headers)

        tier_names = [_t("itm_tier_iron"), _t("itm_tier_copper"), _t("itm_tier_silver"), _t("itm_tier_gold"), "Mystrile", _t("itm_tier_cursed"), _t("itm_tier_blessed"), _t("itm_tier_mythic")]

        for itm in self.items:
            if itm.category != category:
                continue

            if query:
                hex_id = f"0x{itm.index:02x}"
                if query not in itm.name_str.lower() and query not in hex_id:
                    continue

            # 1. Icono real renderizado desde ROM
            c_icon = QStandardItem()
            pix = itm.get_icon_pixmap(scale=1)
            if not pix.isNull():
                c_icon.setIcon(QIcon(pix))
            c_icon.setEditable(False)
            c_icon.setData(itm, Qt.ItemDataRole.UserRole)

            # 2. ID
            c_id = QStandardItem(f"0x{itm.index:02X}")
            c_id.setEditable(False)

            # 3. Nombre
            c_name = QStandardItem(itm.name_str)
            c_name.setEditable(False)

            # 4. Graphic ID
            c_gid = QStandardItem(str(itm.graphic_id))
            c_gid.setEditable(False)

            row_items = [c_icon, c_id, c_name, c_gid]

            if category == "Consumible/Comida":
                c_stam = QStandardItem(str(itm.stamina))
                c_fat = QStandardItem(str(itm.fatigue))
                c_drk = QStandardItem("Si" if itm.is_drink else "No")
                row_items.extend([c_stam, c_fat, c_drk])
            elif category == "Herramienta":
                t_idx = min(7, max(0, itm.tier_or_flags & 7))
                c_tier = QStandardItem(tier_names[t_idx])
                row_items.append(c_tier)
            else:
                c_flg = QStandardItem(f"0x{itm.tier_or_flags:04X}")
                row_items.append(c_flg)

            c_sell = QStandardItem(f"{itm.price} G")
            c_buy = QStandardItem(f"{itm.buy_price} G" if itm.buy_price > 0 else "--")
            row_items.extend([c_sell, c_buy])

            model.appendRow(row_items)

        # Ajustar anchos
        table.setColumnWidth(0, 48)
        table.setColumnWidth(1, 55)
        table.setColumnWidth(2, 170)
        table.setColumnWidth(3, 80)

    def _apply_filter(self, text: str):
        self._populate_category_tables()

    def _on_tab_changed(self, idx: int):
        current_table = self.tabs.currentWidget()
        if isinstance(current_table, QTableView):
            self._on_row_selected()

    def _on_row_selected(self):
        current_table = self.tabs.currentWidget()
        if not isinstance(current_table, QTableView):
            return

        indexes = current_table.selectionModel().selectedIndexes()
        if not indexes:
            return

        row = indexes[0].row()
        item_obj = current_table.model().item(row, 0).data(Qt.ItemDataRole.UserRole)
        self.inspector.load_item(item_obj)

    def save_all_to_rom(self):
        if not self.project:
            return
        try:
            self.project.save_rom()
            QMessageBox.information(self, _t("itm_saved_all_title"), _t("itm_saved_all"))
        except Exception as e:
            QMessageBox.critical(self, _t("itm_save_error_title"), _t("itm_rom_save_error", err=e))
