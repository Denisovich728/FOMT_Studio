from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, 
    QPushButton, QLabel, QMessageBox, QHeaderView, QComboBox
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
        
        # Toolbar
        toolbar = QHBoxLayout()
        self.lbl = QLabel(f"<h3>{tr('item_title', lang)}</h3>")
        
        self.combo_filter = QComboBox()
        # Categorías traducidas
        self.combo_filter.addItem(tr("cat_all", lang), None)
        self.combo_filter.addItem(tr("cat_tool", lang), "Herramienta")
        self.combo_filter.addItem(tr("cat_food", lang), "Consumible/Comida")
        self.combo_filter.addItem(tr("cat_article", lang), "Artículo/Semilla")
        self.combo_filter.currentTextChanged.connect(self.filter_data)
        
        self.btn_refresh = QPushButton(tr('btn_reload', lang))
        self.btn_refresh.clicked.connect(self.load_data)
        
        self.btn_save = QPushButton(tr('btn_validate', lang))
        self.btn_save.setStyleSheet("background-color: #2e7d32; color: white;")
        self.btn_save.clicked.connect(self.save_data)
        
        toolbar.addWidget(self.lbl)
        toolbar.addWidget(self.combo_filter)
        toolbar.addStretch()
        toolbar.addWidget(self.btn_refresh)
        toolbar.addWidget(self.btn_save)
        
        layout.addLayout(toolbar)
        
        # Tabla Spreadsheet
        self.table = QTableView()
        self.model = QStandardItemModel()
        self.table.setModel(self.model)
        
        # Opciones visuales
        self.table.setAlternatingRowColors(True)
        # Asignar delegado para conteo de nombres
        self.delegate = NameEditDelegate(self)
        self.table.setItemDelegateForColumn(2, self.delegate)
        
        layout.addWidget(self.table)
        
    def load_data(self):
        if not self.project: return
        lang = self.lang
        try:
            self.items = self.project.item_parser.scan_foods() 
            self.filter_data()
        except Exception as e:
            QMessageBox.warning(self, tr("err_fatal", lang), f"{tr('err_item_scan', lang)}\n{e}")

    def filter_data(self):
        lang = self.lang
        self.model.clear()
        self.model.setHorizontalHeaderLabels([
            tr('col_class', lang), tr('col_id', lang), tr('col_name', lang), 
            tr('col_sell', lang), tr('col_buy', lang), 
            tr('col_stamina', lang), tr('col_fatigue', lang), tr('col_icon', lang)
        ])
        
        # Obtener el data (key interno) del combo
        idx = self.combo_filter.currentIndex()
        filtro = self.combo_filter.itemData(idx)
        
        for i, itm in enumerate(self.items):
            if filtro and itm.category != filtro:
                continue
                
            stats = getattr(itm, "read_stats", lambda c: {})(itm.category)
            
            # Mapeo de categorías para mostrar traducidas
            cat_map = {
                "Herramienta": tr("cat_tool", lang),
                "Consumible/Comida": tr("cat_food", lang),
                "Artículo/Semilla": tr("cat_article", lang)
            }
            c_cat = QStandardItem(cat_map.get(itm.category, itm.category))
            c_cat.setEditable(False)
            
            c_id = QStandardItem(f"[{stats.get('ID', 0):03d}]")
            c_id.setEditable(False)
            c_id.setData(i, Qt.ItemDataRole.UserRole) # ID REAL en la lista self.items (hidden data)
            
            clean_name = stats.get('Nombre', '').strip('\x00')
            c_name = QStandardItem(clean_name)
            # ¡Habilitar edición de nombre!
            c_name.setEditable(True)
            c_name.setData(stats.get('max_len', 10), Qt.ItemDataRole.UserRole + 2) # Guardar limite para el delegado
            
            # Solo artículos y comidas cruzaron con product_info para tener precios:
            price = stats.get('Preción (G)', 0)
            c_price = QStandardItem(str(price))
            c_price.setEditable(True) # Permitir editar precio de venta
            if itm.category == "Herramienta":
                c_price.setEditable(False)
                c_price.setText("-")
                
            buy_price = stats.get('Precio Compra (G)', 0)
            c_buy_price = QStandardItem(str(buy_price) if buy_price > 0 else "-")
            c_buy_price.setEditable(True if buy_price > 0 else False) # Editables si la tienda los vende
                            
            stamina = stats.get('Stamina', 0)
            c_stamina = QStandardItem(str(stamina))
            if itm.category != "Consumible/Comida": 
                c_stamina.setEditable(False)
                c_stamina.setText("-")
                
            fatigue = stats.get('Fatigue', 0)
            c_fatigue = QStandardItem(str(fatigue))
            if itm.category != "Consumible/Comida": 
                c_fatigue.setEditable(False)
                c_fatigue.setText("-")
                
            c_icon = QStandardItem(str(stats.get('Icono ID', 0)))
            c_icon.setEditable(False)
            
            self.model.appendRow([c_cat, c_id, c_name, c_price, c_buy_price, c_stamina, c_fatigue, c_icon])

    def save_data(self):
        if not self.project or not self.items: return
        
        cambios = 0
        for row in range(self.model.rowCount()):
            idx = self.model.item(row, 1).data(Qt.ItemDataRole.UserRole)
            item = self.items[idx]
            
            # Reflejar cambios de Nombre (En lugar)
            new_name = self.model.item(row, 2).text()
            if new_name != item.name_str.strip('\x00'):
                item.save_name_in_place(new_name)
                cambios += 1
                
            # Reflejar precio de Venta
            try:
                new_price = int(self.model.item(row, 3).text())
                if new_price != item.price and item.product_offset:
                    item.save_sell_price(new_price)
                    cambios += 1
            except ValueError: pass
            
            # Reflejar precio de Compra
            try:
                new_buy = int(self.model.item(row, 4).text())
                if new_buy != item.buy_price and item.buy_price > 0:
                    item.save_buy_price(new_buy)
                    cambios += 1
            except ValueError: pass
            
            if item.category == "Consumible/Comida":
                try:
                    s = int(self.model.item(row, 5).text())
                    f = int(self.model.item(row, 6).text())
                    if s != item.stamina or f != item.fatigue:
                        item.save_stats(s, f, item.price)
                        cambios += 1
                except ValueError: pass
                
        lang = getattr(self.window(), 'current_lang', 'es')
        msg = tr('msg_items_saved', lang)
        trans = tr('msg_items_trans', lang).format(count=cambios)
        QMessageBox.information(self, tr('btn_validate', lang), f"{msg}\n{trans}")

