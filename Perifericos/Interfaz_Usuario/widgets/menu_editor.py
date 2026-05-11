# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.3.4)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
    QTableWidgetItem, QPushButton, QLabel, QHeaderView,
    QLineEdit, QMessageBox
)
from PyQt6.QtCore import Qt
import struct

class MenuEditorWidget(QWidget):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.menu_definitions = []
        self._scan_all_machine_tables()
        self._init_ui()
        self.refresh_list()

    def _scan_all_machine_tables(self):
        """Lista Limpia SlipSpace: Solo menús y tablas de texto verificadas."""
        import struct
        self.menu_definitions = []
        
        # 1. BLOQUE: DIARIO / SAVE / LOAD (Paso 4 bytes)
        # Basado en HxD: 0xE8704...
        save_labels = ["Diary", "Save", "Load", "Empty", "Data 1", "Data 2", "Buttons", "1", "2", "Clock", "On", "Off", "On (2)", "Off (2)", "Portrait", "On (3)", "Off (3)"]
        for i in range(18):
            off = 0xE8704 + (i * 4)
            label = save_labels[i] if i < len(save_labels) else f"Extra: {i}"
            self.menu_definitions.append((off, f"Save: {label}", "Menú Diario / Save"))
            
        # 2. BLOQUE: SISTEMA / AYUDA (Paso 8 bytes)
        for i in range(25):
            off = 0x003F30 + (i * 8)
            self.menu_definitions.append((off, f"Help: Slot {i}", "Sistema / Ayuda"))
            
        # 2.1 BLOQUE: ALERTAS DE CARGA/GUARDADO (NUEVO)
        save_alerts = [
            (0x00409C, "Save Failed"), (0x0041D8, "Load Failed"), 
            (0x004834, "Load?"), (0x004894, "Overwrite?"),
            (0x004860, "No Data Message")
        ]
        for off, label in save_alerts:
            self.menu_definitions.append((off, label, "Sistema / Alertas Save"))
            
        # 3. BLOQUE: NAMING Y PROPIEDADES (Paso 4/8 bytes)
        # Basado en HxD: 0x4EE8, 0x4EEC, 0x4EF0, 0x4EF4, 0x4EF8...
        naming_labels = ["Your", "Farm's", "Dog's", "Name Question", "Birthday Question"]
        for i, label in enumerate(naming_labels):
            off = 0x004EE8 + (i * 4)
            self.menu_definitions.append((off, f"Naming: {label}", "Sistema / Naming"))
            
        # El resto del bloque parece seguir a paso 8 después de los básicos
        for i in range(8):
            off = 0x004F00 + (i * 8)
            self.menu_definitions.append((off, f"Property: {i}", "Sistema / Propiedades"))
            
        # Puntero suelto del teclado/naming
        self.menu_definitions.append((0x005F18, "Naming UI: Name/End", "Sistema / Naming"))
        
        # Preguntas de Confirmación Naming
        confirm_naming = [
            (0x0054B8, "Label: Your Name"), (0x0054BC, "Label: Your Birthday"),
            (0x0054C0, "Label: Farm Name"), (0x0054C4, "Label: Dog Name"),
            (0x005904, "Question: Is this OK?"), (0x005908, "Yes (OK)"), (0x00590C, "No (OK)"),
            (0x007028, "Question: Name correct?"), (0x00702C, "Yes (Correct)"), (0x007030, "No (Correct)")
        ]
        for off, label in confirm_naming:
            self.menu_definitions.append((off, label, "Sistema / Naming"))
            
        # 7. BLOQUE: RESUMEN GRANJA / ANIMALES (NUEVO)
        farm_summary = [
            (0x0600A8, "Label: Property"), (0x060878, "Label: G (Gold)"),
            (0x062FB0, "Label: Healthy"), (0x06313C, "Label: Unhappy"),
            (0x063388, "Season: Spring"), (0x0634A4, "Season: Summer"),
            (0x0635C0, "Season: Fall"), (0x0636DC, "Season: Winter"),
            (0x0637F4, "Label: yr"), (0x064384, "Header: Chickens"),
            (0x064458, "Header: Cattle"), (0x064568, "Header: Sheep"),
            (0x0646BC, "Header: Sprites"), (0x0646CC, "Label: D (Days)"),
            (0x064824, "Label: left"), (0x064948, "Label: work"), (0x064A6C, "Label: N/A")
        ]
        for off, label in farm_summary:
            self.menu_definitions.append((off, label, "Sistema / Resumen Granja"))

        # 10. BLOQUE: CALENDARIO / HUD SEASONS (NUEVO)
        calendar_seasons = [
            (0x0E3FA8, "Season: Spring (Alt)"), (0x0E3FD8, "Season: Summer (Alt)"),
            (0x0E3FDC, "Season: Fall (Alt)"), (0x0E4010, "Season: Winter (Alt)")
        ]
        for off, label in calendar_seasons:
            self.menu_definitions.append((off, label, "HUD / Tiempo"))

        # 8. BLOQUE: REPORTE DE GANANCIAS (NUEVO)
        earnings_report = [
            (0x066578, "Title: Earnings Report"), (0x06658C, "Label: D (Days)"),
            (0x066774, "Label: G (Gold)"), (0x0668A4, "Symbol: +"), (0x0669DC, "Symbol: -"),
            (0x066B0C, "Season: Spring"), (0x066C28, "Season: Summer"),
            (0x066D48, "Season: Fall"), (0x066E68, "Season: Winter"),
            (0x066F9C, "Label: Year"), (0x0670D8, "Label: Income"), (0x067210, "Label: Expenses")
        ]
        for off, label in earnings_report:
            self.menu_definitions.append((off, label, "Sistema / Reporte Ganancias"))

        # 9. BLOQUE: MEJORAS DE HERRAMIENTAS (NUEVO)
        upgrades = [
            (0x0683FC, "Label: Tool Lev"), (0x068410, "Label: Shop"), (0x068568, "Label: Upgrade?")
        ]
        for off, label in upgrades:
            self.menu_definitions.append((off, label, "Sistema / Tiendas"))

        # 4. BLOQUE: OPCIONES DE TIENDA (Paso 4 bytes)
        for i in range(15):
            off = 0x0FD9B4 + (i * 4)
            self.menu_definitions.append((off, f"Shop: {i}", "Sistema / Tiendas"))

        # 5. BLOQUE: MENÚ PAUSA / UI (NUEVO)
        # Basado en el mapeo de HxD: 0xF1A34, 0xF1A38...
        menu_labels = ["Diary", "Rucksack", "World Map", "Earnings", "Farm Degree", "Memo", "Tutorial"]
        for i, label in enumerate(menu_labels):
            off = 0x0F1A34 + (i * 4)
            self.menu_definitions.append((off, f"UI: {label}", "Sistema / Menú Pausa"))

        # 6. BLOQUE: CONTROLES / AYUDA SISTEMA (NUEVO)
        # Basado en HxD: 0x3F60, 0x3F68, 0x3F70, 0x3F78, 0x3F90
        help_offs = [0x3F60, 0x3F68, 0x3F70, 0x3F78, 0x3F90]
        for i, off in enumerate(help_offs):
            self.menu_definitions.append((off, f"Help Text: {i}", "Sistema / Ayuda Controles"))

        # 5. BLOQUE: HUD / TIEMPO
        for i in range(6):
            off = 0x003B24 + (i * 4)
            self.menu_definitions.append((off, f"HUD: {i}", "HUD / Tiempo"))

        print(f"✅ Lista Limpia: {len(self.menu_definitions)} punteros verificados.")

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Editor de Textos de Sistema y Motor (SlipSpace Dynamic)</b>"))
        layout.addWidget(QLabel("<i>Maneja punteros de tabla y punteros directos de motor. Los cambios son globales.</i>"))

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Ptr Offset", "Categoría", "Función", "Real Addr", "Texto (Ilimitado)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        # Panel de Acciones (Fijado abajo)
        actions_panel = QHBoxLayout()
        
        btn_save = QPushButton("🚀 REPUNTEAR Y SINCRONIZAR TODO")
        btn_save.setFixedHeight(45)
        btn_save.setStyleSheet("background-color: #2ECC71; color: white; font-weight: bold; border-radius: 5px;")
        btn_save.clicked.connect(self.save_all)
        
        btn_inject = QPushButton("📜 INYECTAR SCRIPT")
        btn_inject.setFixedHeight(45)
        btn_inject.setStyleSheet("background-color: #3498DB; color: white; font-weight: bold; border-radius: 5px;")
        btn_inject.clicked.connect(self.inject_script_at_cursor)
        
        actions_panel.addWidget(btn_save)
        actions_panel.addWidget(btn_inject)
        layout.addLayout(actions_panel)

    def inject_script_at_cursor(self):
        """Abre el Script IDE para el puntero seleccionado."""
        row = self.table.currentRow()
        if row == -1:
            QMessageBox.warning(self, "Error", "Selecciona una fila primero.")
            return
            
        ptr_off, label, _ = self.menu_definitions[row]
        # Abrir el IDE de scripts para esta dirección
        main_win = self.window()
        if hasattr(main_win, 'open_script_at'):
            main_win.open_script_at(ptr_off, f"Script_{label}")

    def refresh_list(self):
        from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.objetos import ItemParser
        self.table.setRowCount(len(self.menu_definitions))
        self.original_texts = []
        for i, (ptr_off, label, category) in enumerate(self.menu_definitions):
            # Leer el puntero
            # Lógica de Lectura SlipSpace: Puntero vs Tabla de Sistema
            ptr_bytes = self.project.virtual_rom[ptr_off : ptr_off + 4]
            if len(ptr_bytes) < 4: continue
            
            gba_addr = struct.unpack("<I", ptr_bytes)[0]
            
            # Si el puntero es inválido, mostramos el error pero no rompemos la lista
            if not (0x08000000 <= gba_addr <= 0x09000000):
                self.table.setItem(i, 0, QTableWidgetItem(f"0x{ptr_off:06X}"))
                self.table.setItem(i, 1, QTableWidgetItem(category))
                self.table.setItem(i, 2, QTableWidgetItem(label))
                self.table.setItem(i, 3, QTableWidgetItem(f"Invalid Ptr: 0x{gba_addr:08X}"))
                self.original_texts.append("")
                continue
                
            real_off = gba_addr & 0x1FFFFFF
            
            # Leer el texto usando el ItemParser (que ya tiene la lógica robusta de 00)
            temp_parser = ItemParser(self.project)
            text = temp_parser.read_string(gba_addr)
            
            self.original_texts.append(text)
            self.table.setItem(i, 0, QTableWidgetItem(f"0x{ptr_off:06X}"))
            self.table.setItem(i, 1, QTableWidgetItem(category))
            self.table.setItem(i, 2, QTableWidgetItem(label))
            self.table.setItem(i, 3, QTableWidgetItem(f"0x{real_off:06X}"))
            
            line_edit = QLineEdit(text)
            self.table.setCellWidget(i, 4, line_edit)

    def save_all(self):
        from Nucleos_de_Procesamiento.Nucleo_de_Datos.gestor_memoria import MemoryManager
        from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.objetos import ItemParser
        
        manager = MemoryManager(self.project)
        parser = ItemParser(self.project)
        count = 0
        
        for i in range(self.table.rowCount()):
            new_text = self.table.cellWidget(i, 4).text()
            if new_text == self.original_texts[i]:
                continue
                
            ptr_off, label, category = self.menu_definitions[i]
            
            # Obtener datos del puntero actual
            ptr_bytes = self.project.virtual_rom[ptr_off : ptr_off + 4]
            gba_addr = struct.unpack("<I", ptr_bytes)[0]
            
            # Determinar límite quirúrgico (siguiente puntero en la tabla)
            step = 8 if any(x in category for x in ["Sistema", "Animals"]) else 4
            next_ptr_off = ptr_off + step
            
            cleaning_limit = 0
            if next_ptr_off + 4 <= len(self.project.virtual_rom):
                next_ptr_bytes = self.project.virtual_rom[next_ptr_off : next_ptr_off + 4]
                next_gba = struct.unpack("<I", next_ptr_bytes)[0]
                if 0x08000000 <= next_gba <= 0x09000000:
                    cleaning_limit = next_gba & 0x1FFFFFF
            
            # Convertir texto a bytes (soporta [0D], [n])
            new_data = parser.write_string(new_text)
            
            # EJECUTAR REPUNTEO Y LIMPIEZA
            success, new_gba = manager.repoint_and_write(ptr_off, new_data, cleaning_limit)
            
            if success:
                count += 1
                self.original_texts[i] = new_text
                # Actualizar UI con la nueva dirección real
                self.table.setItem(i, 3, QTableWidgetItem(f"0x{new_gba & 0x1FFFFFF:06X}"))
                
        if count > 0:
            QMessageBox.information(self, "Sincronización Exitosa", f"Se han repunteado {count} textos con alineación estricta.")
            self.project.save_rom()
            self.refresh_list()
        else:
            QMessageBox.warning(self, "Sin Cambios", "No se detectaron modificaciones en los textos.")
