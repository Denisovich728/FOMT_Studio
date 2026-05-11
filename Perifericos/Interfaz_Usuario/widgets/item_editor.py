# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.3.1)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, 
    QPushButton, QLabel, QMessageBox, QHeaderView, QComboBox,
    QTabWidget, QGroupBox, QTextEdit
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt
from Perifericos.Traducciones.i18n import tr

from Perifericos.Interfaz_Usuario.widgets.utils import NameEditDelegate

class ItemEditorWidget(QWidget):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.items = []
        self.lang = getattr(parent, 'current_lang', 'es') if parent else 'es'
        
        self.setup_ui()
        self.load_data()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        lang = self.lang
        
        # Toolbar superior
        toolbar = QHBoxLayout()
        self.lbl = QLabel(f"<h3>{tr('item_title', lang)}</h3>")
        toolbar.addWidget(self.lbl)
        toolbar.addStretch()
        
        self.btn_refresh = QPushButton(tr('btn_reload', lang))
        self.btn_refresh.clicked.connect(self.load_data)
        toolbar.addWidget(self.btn_refresh)
        
        self.btn_save_all = QPushButton(tr('btn_save_all', lang))
        self.btn_save_all.setStyleSheet("background-color: #2e7d32; color: white;")
        self.btn_save_all.clicked.connect(self.save_data)
        toolbar.addWidget(self.btn_save_all)
        
        layout.addLayout(toolbar)
        
        # Tab Widget para las 3 categorías
        self.tabs = QTabWidget()
        
        # 1. Herramientas
        self.table_tools = self._create_table()
        self.tabs.addTab(self.table_tools, tr("cat_tool", lang))
        
        # 2. Comestibles
        self.table_foods = self._create_table()
        self.tabs.addTab(self.table_foods, tr("cat_food", lang))
        
        # 3. Variados
        self.table_misc = self._create_table()
        self.tabs.addTab(self.table_misc, tr("cat_article", lang))
        
        layout.addWidget(self.tabs)
        
        # Panel de Edición de Descripción (Abajo)
        self.desc_group = QGroupBox(tr('desc_editor_title', lang))
        desc_layout = QVBoxLayout(self.desc_group)
        
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText(tr('desc_placeholder', lang))
        desc_layout.addWidget(self.desc_edit)
        
        self.btn_compile_desc = QPushButton(tr('btn_compile_desc', lang))
        self.btn_compile_desc.clicked.connect(self.compile_description)
        desc_layout.addWidget(self.btn_compile_desc)
        
        layout.addWidget(self.desc_group)
        
        # Conectar cambios de selección
        self.table_tools.selectionModel().selectionChanged.connect(self.on_selection_changed)
        self.table_foods.selectionModel().selectionChanged.connect(self.on_selection_changed)
        self.table_misc.selectionModel().selectionChanged.connect(self.on_selection_changed)

    def _create_table(self):
        table = QTableView()
        model = QStandardItemModel()
        table.setModel(model)
        table.setAlternatingRowColors(True)
        delegate = NameEditDelegate(self, max_limit=None)
        table.setItemDelegateForColumn(2, delegate)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        return table

    def load_data(self):
        if not self.project: return
        try:
            self.items = self.project.item_parser.scan_foods()
            self._populate_table(self.table_tools, "Herramienta")
            self._populate_table(self.table_foods, "Consumible/Comida")
            self._populate_table(self.table_misc, "Artículo")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Fallo al cargar items: {e}")

    def _populate_table(self, table, category):
        model = table.model()
        model.clear()
        lang = self.lang
        model.setHorizontalHeaderLabels([
            tr('col_class', lang), tr('col_id', lang), tr('col_name', lang), 
            tr('col_price_sell', lang), tr('col_price_buy', lang), tr('col_stamina', lang), tr('col_fatigue', lang)
        ])
        
        for i, itm in enumerate(self.items):
            if itm.category != category: continue
            
            stats = itm.read_stats(category)
            
            c_cat = QStandardItem(category)
            c_cat.setEditable(False)
            
            c_id = QStandardItem(stats.get('idx', '0x00'))
            c_id.setEditable(False)
            c_id.setData(itm, Qt.ItemDataRole.UserRole) # Guardar objeto completo
            
            c_name = QStandardItem(stats.get('Nombre', ''))
            
            c_price = QStandardItem(str(itm.price))
            c_buy = QStandardItem(str(itm.buy_price))
            c_stam = QStandardItem(str(itm.stamina))
            c_fat = QStandardItem(str(itm.fatigue))
            
            model.appendRow([c_cat, c_id, c_name, c_price, c_buy, c_stam, c_fat])

    def on_selection_changed(self):
        # Obtener el item seleccionado de la tabla activa
        current_table = self.tabs.currentWidget()
        indexes = current_table.selectionModel().selectedIndexes()
        if not indexes: return
        
        # El ID real está en la columna 1 (ID)
        row = indexes[0].row()
        item_obj = current_table.model().item(row, 1).data(Qt.ItemDataRole.UserRole)
        
        self.desc_edit.setText(item_obj.desc_str)
        lang = self.lang
        self.desc_group.setTitle(tr('desc_of', lang).format(name=item_obj.name_str))

    def compile_description(self):
        current_table = self.tabs.currentWidget()
        indexes = current_table.selectionModel().selectedIndexes()
        if not indexes: return
        
        row = indexes[0].row()
        item_obj = current_table.model().item(row, 1).data(Qt.ItemDataRole.UserRole)
        
        new_desc = self.desc_edit.toPlainText()
        try:
            item_obj.save_desc_in_place(new_desc)
            # Refrescar el objeto en la vista
            self.on_selection_changed()
            lang = self.lang
            QMessageBox.information(self, tr('success', lang), tr('msg_desc_success', lang).format(name=item_obj.name_str))
        except Exception as e:
            QMessageBox.critical(self, tr('error', lang), f"{tr('error', lang)}: {e}")

    def save_data(self):
        # Guardar nombres y stats básicos de todas las tablas
        total_cambios = 0
        for table in [self.table_tools, self.table_foods, self.table_misc]:
            model = table.model()
            for row in range(model.rowCount()):
                item_obj = model.item(row, 1).data(Qt.ItemDataRole.UserRole)
                new_name = model.item(row, 2).text()
                
                if new_name != item_obj.name_str:
                    item_obj.save_name_in_place(new_name)
                    total_cambios += 1
                
                # ... lógica de precios y stats ...
                
        lang = self.lang
        QMessageBox.information(self, tr('title_project_saved', lang), tr('msg_changes_applied', lang).format(count=total_cambios))
