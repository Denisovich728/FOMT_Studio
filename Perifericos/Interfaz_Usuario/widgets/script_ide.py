from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QTextEdit, QLineEdit,
    QPushButton, QLabel, QSplitter, QListWidget, QListWidgetItem,
    QCompleter
)
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QFontDatabase, QPainter, QTextFormat, QTextCursor
from PyQt6.QtCore import Qt, QRect, QSize, QStringListModel, QThread, pyqtSignal

from Perifericos.Interfaz_Usuario.themes import get_highlighter_colors
from Perifericos.Traducciones.i18n import tr

import re
import json
import os

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self):
        return QSize(self.code_editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.code_editor.line_number_area_paint_event(event)

class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_number_area = LineNumberArea(self)

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.update_line_number_area_width(0)
        self._completer = None

    def setCompleter(self, completer):
        if self._completer:
            self._completer.activated.disconnect()
        self._completer = completer
        if not self._completer:
            return
        self._completer.setWidget(self)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.activated.connect(self.insertCompletion)

    def completer(self):
        return self._completer

    def insertCompletion(self, completion):
        if self._completer.widget() is not self:
            return
        tc = self.textCursor()
        prefix = self._completer.completionPrefix()
        tc.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, len(prefix))
        
        # Lógica de Snippets (Plantillas)
        snippets = {
            "if": "if () {\n    \n}",
            "for": "for (var i = 0; i < 10; ++i) {\n    \n}",
            "switch": "switch () {\n    case 0:\n        break;\n}",
            "script": "script ID Name {\n    \n}"
        }
        
        # Obtener el tipo de sugerencia y los argumentos desde el modelo
        index = self._completer.completionModel().index(self._completer.popup().currentIndex().row(), 0)
        item_type = index.data(Qt.ItemDataRole.UserRole)
        args_hint = index.data(Qt.ItemDataRole.UserRole + 1) or ""
        
        if completion in snippets:
            tc.insertText(snippets[completion])
            if completion in ("if", "switch"):
                tc.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, len(snippets[completion]) - 4)
        elif item_type == "cmd": 
            # Es un comando de la librería, añadimos estructura de función con pistas de argumentos
            full_text = f"{completion}({args_hint})"
            tc.insertText(full_text)
            
            # Seleccionar los argumentos para que el usuario pueda escribir encima inmediatamente
            if args_hint:
                # El cursor está al final del texto insertado. 
                # Retrocedemos la longitud de args_hint + 1 (el paréntesis de cierre)
                tc.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, 1)
                tc.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, len(args_hint))
        else:
            # Palabra clave, ID de retrato o texto normal
            tc.insertText(completion)
            
        self.setTextCursor(tc)

    def textUnderCursor(self):
        tc = self.textCursor()
        # Mover el cursor al final de la palabra actual considerando guiones bajos
        # No usamos WordUnderCursor directamente porque a veces corta en el '_'
        pos = tc.position()
        tc.movePosition(QTextCursor.MoveOperation.StartOfWord, QTextCursor.MoveMode.KeepAnchor)
        word = tc.selectedText()
        
        # Si la palabra antes del cursor tiene un guion bajo, intentar capturar más
        # (Heurística simple para comandos tipo Set_Flag)
        full_tc = self.textCursor()
        full_tc.movePosition(QTextCursor.MoveOperation.StartOfLine, QTextCursor.MoveMode.KeepAnchor)
        line = full_tc.selectedText()
        
        # Encontrar la palabra que termina en la posición actual
        match = re.search(r'([a-zA-Z0-9_]+)$', line)
        if match:
            return match.group(1)
            
        return word

    def focusInEvent(self, e):
        if self._completer:
            self._completer.setWidget(self)
        super().focusInEvent(e)

    def keyPressEvent(self, e):
        if self._completer and self._completer.popup() and self._completer.popup().isVisible():
            # Aceptar sugerencia con Tab o Enter
            if e.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Tab):
                self._completer.activated.emit(self._completer.popup().currentIndex().data(Qt.ItemDataRole.EditRole))
                self._completer.popup().hide()
                return
            # Cerrar con Escape
            elif e.key() == Qt.Key.Key_Escape:
                self._completer.popup().hide()
                return

        # Atajo manual: Ctrl + Espacio
        isManualTrigger = (e.modifiers() & Qt.KeyboardModifier.ControlModifier) and e.key() == Qt.Key.Key_Space
        
        if not isManualTrigger:
            super().keyPressEvent(e)

        if not self._completer:
            return

        # No disparar si se presionan modificadores solos
        ctrlOrShift = e.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        if not isManualTrigger and ctrlOrShift and not e.text():
            return

        # Detección de contexto
        tc = self.textCursor()
        tc.movePosition(QTextCursor.MoveOperation.StartOfLine, QTextCursor.MoveMode.KeepAnchor)
        line_text = tc.selectedText()
        
        completionPrefix = self.textUnderCursor()

        # Si no hay prefijo o se presionó una tecla de borrado, ocultar y salir
        if not isManualTrigger and (not completionPrefix or e.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete)):
            self._completer.popup().hide()
            return

        # Actualizar el prefijo y disparar
        if completionPrefix != self._completer.completionPrefix():
            self._completer.setCompletionPrefix(completionPrefix)
            self._completer.popup().setCurrentIndex(self._completer.completionModel().index(0, 0))

        cr = self.cursorRect()
        cr.setWidth(self._completer.popup().sizeHintForColumn(0)
                    + self._completer.popup().verticalScrollBar().sizeHint().width())
        self._completer.complete(cr)

    def update_completer_context(self, line_text):
        """Ajusta el filtro del completer según lo que se esté escribiendo."""
        if not self._completer: return
        
        # Si la línea termina en Give_Item( o similar con una comilla abierta
        if re.search(r'Give_Item\(\s*"[^"]*$', line_text):
            # Solo mostrar ítems (los que empiezan por ")
            # NOTA: En un sistema real usaríamos un ProxyModel, aquí usaremos el prefijo
            pass 
        elif re.search(r'ChangePortrait\(\s*[^,]*$', line_text):
            # Solo mostrar retratos
            pass

    def line_number_area_width(self):
        digits = 1
        max_v = max(1, self.blockCount())
        while max_v >= 10:
            max_v //= 10
            digits += 1
        space = 3 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def highlight_current_line(self):
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            # Verde matriz muy sutil (transparencia alta) para que no brille
            # sobre el fondo negro pero marque la línea.
            line_color = QColor(0, 255, 0, 15) 
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        self.setExtraSelections(extra_selections)

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#1e1e1e").lighter(120))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor("#858585"))
                painter.drawText(0, top, self.line_number_area.width() - 2, self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

class FoMTHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.highlighting_rules = []

    def update_colors(self, theme_name):
        colors = get_highlighter_colors(theme_name)
        self.highlighting_rules = []
        
        command_format = QTextCharFormat()
        command_format.setForeground(QColor(colors["command"]))
        command_format.setFontWeight(QFont.Weight.Bold)
        commands = [
            "Call", "Jump", "Exit", "End", "Branch", "Option", 
            "Message", "TalkMessage", "FacePlayer", "SetEntity", 
            "PlaySound", "GiveItem", "HasItem", "IncVar", "DecVar",
            "ChangePortrait"
        ]
        for cmd in commands:
            pattern = re.compile(rf"\b{cmd}\b")
            self.highlighting_rules.append((pattern, command_format))
            
        var_format = QTextCharFormat()
        var_format.setForeground(QColor(colors["variable"]))
        var_pattern = re.compile(r"\bvar_\d+\b|\bunk_\w+\b|\bflag_\d+\b")
        self.highlighting_rules.append((var_pattern, var_format))
        
        string_format = QTextCharFormat()
        string_format.setForeground(QColor(colors["string"]))
        string_pattern = re.compile(r"\".*?\"")
        self.highlighting_rules.append((string_pattern, string_format))
        
        num_format = QTextCharFormat()
        num_format.setForeground(QColor(colors["number"]))
        num_pattern = re.compile(r"\b0x[A-Fa-f0-9]+\b|\b\d+\b")
        self.highlighting_rules.append((num_pattern, num_format))
        
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor(colors["comment"]))
        comment_format.setFontItalic(True)
        comment_pattern = re.compile(r"//[^\n]*")
        self.highlighting_rules.append((comment_pattern, comment_format))
        
        self.rehighlight()

    def highlightBlock(self, text):
        for pattern, fmt in self.highlighting_rules:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)


class ScriptIDEWidget(QWidget):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.current_event_id = None
        self.lang = getattr(parent, 'current_lang', 'es') if parent else 'es'
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        lang = self.lang
        
        toolbar = QHBoxLayout()
        self.lbl_title = QLabel(f"<h3>{tr('ide_title', lang)}</h3>")
        
        self.btn_compile = QPushButton(tr('btn_compile_script', lang))
        self.btn_compile.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold;")
        self.btn_compile.clicked.connect(self.on_compile_clicked)

        self.btn_debug_toggle = QPushButton(tr('btn_debug_mode', lang))
        self.btn_debug_toggle.setStyleSheet("background-color: #1976d2; color: white; font-weight: bold;")
        self.btn_debug_toggle.clicked.connect(self.on_debug_toggle_clicked)
        
        toolbar.addWidget(self.lbl_title)
        toolbar.addStretch()
        toolbar.addWidget(self.btn_debug_toggle)
        toolbar.addWidget(self.btn_compile)
        
        layout.addLayout(toolbar)

        # Barra de Búsqueda Global (Buscar texto en todos los eventos)
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar texto en todos los eventos...")
        self.search_input.returnPressed.connect(self.on_global_search)
        
        self.btn_search = QPushButton("🔍")
        self.btn_search.setFixedWidth(40)
        self.btn_search.clicked.connect(self.on_global_search)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.btn_search)
        layout.addLayout(search_layout)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # Uso de CodeEditor (QPlainTextEdit personalizado)
        self.editor = CodeEditor()
        
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(11)
        self.editor.setFont(font)
        
        self.highlighter = FoMTHighlighter(self.editor.document())
        self.highlighter.update_colors("light")
        
        # Cargar diccionario de conocimientos
        knowledge_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "fomt_knowledge.json")
        knowledge_data = {}
        if os.path.exists(knowledge_path):
            try:
                with open(knowledge_path, "r", encoding="utf-8") as f:
                    knowledge_data = json.load(f)
            except Exception as e:
                print(f"Error cargando diccionario: {e}")

        # Configurar Intellisense
        from PyQt6.QtGui import QStandardItemModel, QStandardItem
        self.completer_model = QStandardItemModel(self)
        
        # 1. Cargar Opcodes Dinámicos desde lib_*.csv
        lib_name = "lib_mfomt.csv" if self.project.is_mfomt else "lib_fomt.csv"
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        lib_path = os.path.join(root_dir, "Nucleos_de_Procesamiento", "data", lib_name)
        
        if os.path.exists(lib_path):
            import csv
            try:
                with open(lib_path, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    for i, row in enumerate(reader):
                        if i == 0 or len(row) < 4: continue
                        kind, h_id, d_id, name = row[0:4]
                        if name:
                            q_item = QStandardItem(name)
                            args = row[4] if len(row) > 4 else ""
                            # Formatear argumentos para que se vean bien
                            args_display = f"({args})" if args else "()"
                            q_item.setToolTip(f"{kind.upper()} | ID: {h_id}\nEstructura: {name}{args_display}")
                            # Marcar como comando y guardar argumentos
                            q_item.setData("cmd", Qt.ItemDataRole.UserRole) 
                            q_item.setData(args, Qt.ItemDataRole.UserRole + 1)
                            # También guardar el nombre en el rol de edición para el filtrado
                            q_item.setData(name, Qt.ItemDataRole.EditRole)
                            self.completer_model.appendRow(q_item)
            except Exception as e:
                print(f"Error cargando librería de comandos: {e}")

        # 2. Palabras clave y estructuras
        keywords = ["if", "else", "for", "while", "do", "switch", "case", "default", "var", "const", "script", "exit"]
        for kw in keywords:
            q_item = QStandardItem(kw)
            q_item.setData("kw", Qt.ItemDataRole.UserRole)
            q_item.setData(kw, Qt.ItemDataRole.EditRole)
            self.completer_model.appendRow(q_item)
            
        # 3. Añadir IDs de retratos al autocompletado
        if "ids" in knowledge_data and "portraits" in knowledge_data["ids"]:
            for char, states in knowledge_data["ids"]["portraits"].items():
                for state, val in states.items():
                    portrait_name = f"{char}_{state}"
                    q_item = QStandardItem(portrait_name)
                    q_item.setData(portrait_name, Qt.ItemDataRole.EditRole)
                    self.completer_model.appendRow(q_item)
        
        # 4. Añadir nombres de ítems al autocompletado (para Give_Item)
        if self.project.item_parser:
            try:
                items = self.project.item_parser.scan_foods()
                for itm in items:
                    name = itm.name_str.strip('\x00')
                    if name and name != "Desconocido":
                        completion_text = f'"{name}"'
                        q_item = QStandardItem(completion_text)
                        q_item.setData(f'Ítem: {name} (0x{itm.index:02X})', Qt.ItemDataRole.DisplayRole)
                        q_item.setData(completion_text, Qt.ItemDataRole.EditRole)
                        q_item.setToolTip(f"ID Hex: 0x{itm.index:02X}")
                        self.completer_model.appendRow(q_item)
            except: pass
        
        completer = QCompleter(self.completer_model, self)
        completer.setCompletionRole(Qt.ItemDataRole.EditRole)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains) # Búsqueda flexible
        completer.setWrapAround(False)
        self.editor.setCompleter(completer)
        
        self.editor.setPlainText("// Load a script to start editing...")
        
        splitter.addWidget(self.editor)
        
    def load_event(self, event_id):
        self.current_event_id = event_id
        code, stmts = self.project.event_parser.decompile_to_ui(event_id)
        self.editor.setPlainText(code)

    def load_rom_script(self, offset):
        """Carga y descompila un script desde un offset arbitrario (usado por Mapas)."""
        self.current_event_id = None
        code, stmts = self.project.event_parser.decompile_from_offset(offset, hint="MapScript")
        self.editor.setPlainText(code)
        
    def on_compile_clicked(self):
        if self.current_event_id is None: return
        
        code = self.editor.toPlainText()
        
        # Obtenemos info del evento actual
        hint, old_offset = self.project.event_parser.get_event_name_and_offset(self.current_event_id)
        
        # Tamaño original (SI existe el evento en la ROM)
        old_size = 0
        if old_offset:
            key = self.current_event_id if self.current_event_id is not None else old_offset
            old_size = self.project.event_parser.get_last_scanned_size(key)

        # Compilación real usando el motor SlipSpace_Engine
        try:
            new_data = self.project.event_parser.compile_text_to_bytecode(code, old_size=old_size)
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error de Compilación", f"No se pudo compilar el script:\n{e}")
            return
            
        # Llamamos al MemoryManager inteligente
        if self.current_event_id is not None:
            new_offset = self.project.memory.re_point_master_event(
                self.current_event_id, old_offset, old_size, new_data
            )
            mode_prefix = "Event"
        else:
            # Si no hay event_id, asumimos que es el script del mapa actual (o el último cargado)
            # Para la v1.5, intentamos obtener el map_id del MapEditor si está activo
            map_id = 0 # Fallback
            if self.project.map_parser.maps:
                # Heurística: buscar qué mapa tiene este script offset
                for m in self.project.map_parser.maps:
                    if (m.p_script & 0x01FFFFFF) == old_offset:
                        map_id = m.map_id
                        break
            
            new_offset = self.project.memory.re_point_map_script(
                map_id, old_offset, old_size, new_data
            )
            mode_prefix = f"Map {map_id} (Room)"
        
        from PyQt6.QtWidgets import QMessageBox
        lang = self.lang
        
        status_msg = "Edición In-Place (Espacio Original)" if new_offset == old_offset else "Escritura en Espacio Libre (Repunteo)"
        status_msg = f"[{mode_prefix}] {status_msg}"
        
        QMessageBox.information(
            self, 
            "Compilación y Repunteo Exitoso",
            f"El script ha sido procesado e inyectado en la ROM.\\n\\n"
            f"Modo: {status_msg}\\n"
            f"Offset Actual: 0x{new_offset:08X}\\n"
            f"Tamaño Original: {old_size} bytes\\n"
            f"Tamaño Nuevo: {len(new_data)} bytes"
        )

    def on_debug_toggle_clicked(self):
        # Lógica para alternar el modo debug (Calendario -> Script 0x080E)
        success, state = self.project.memory.toggle_debug_mode()
        
        from PyQt6.QtWidgets import QMessageBox
        lang = self.lang
        
        if success:
            msg = "Activado" if state else "Desactivado"
            QMessageBox.information(self, tr('btn_debug_mode', lang), f"Modo Debug {msg} correctamente.")
        else:
            QMessageBox.warning(self, tr('btn_debug_mode', lang), "No se pudo encontrar el script del calendario en la ROM.")

    def on_global_search(self):
        """Busca una cadena de texto en todos los eventos de la ROM usando hilos."""
        query = self.search_input.text().strip()
        if not query: return
        
        event_ids = list(self.project.event_parser.scanned_sizes.keys())
        
        from PyQt6.QtWidgets import QProgressDialog
        self.search_progress = QProgressDialog("Buscando en eventos (Multi-thread)...", "Cancelar", 0, len(event_ids), self)
        self.search_progress.setWindowModality(Qt.WindowModality.WindowModal)
        
        self.worker = SearchWorker(query, self.project, event_ids)
        self.worker.progress.connect(self.search_progress.setValue)
        self.worker.finished.connect(self.on_search_finished)
        self.search_progress.canceled.connect(self.worker.stop)
        
        self.worker.start()

    def on_search_finished(self, results):
        self.search_progress.close()
        if results:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Resultados de Búsqueda", f"Se encontró '{self.search_input.text()}' en {len(results)} eventos.\n\nIDs: {results[:15]}...")
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Búsqueda", "No se encontraron coincidencias.")

class SearchWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(list)
    
    def __init__(self, query, project, event_ids):
        super().__init__()
        self.query = query.lower()
        self.project = project
        self.event_ids = event_ids
        self._is_running = True
        
    def stop(self):
        self._is_running = False
        
    def run(self):
        results = []
        total = len(self.event_ids)
        
        for i, eid in enumerate(self.event_ids):
            if not self._is_running: break
            if i % 10 == 0: self.progress.emit(i)
            
            # OPTIMIZACIÓN: Pre-filtro Binario (Saltar si no tiene bloque STR)
            hint, offset = self.project.event_parser.get_event_name_and_offset(eid)
            if offset:
                # Escaneo rápido de los primeros 128 bytes
                header = self.project.read_rom(offset, 128)
                if b'STR ' not in header:
                    # El usuario pidió saltar si no tiene mensajes (const message)
                    continue
            
            # Decompilación y búsqueda
            try:
                code, _ = self.project.event_parser.decompile_to_ui(eid)
                if self.query in code.lower():
                    results.append(eid)
            except: continue
            
        self.finished.emit(results)
