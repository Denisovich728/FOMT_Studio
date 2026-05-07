from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QTextEdit, QLineEdit,
    QPushButton, QLabel, QSplitter, QListWidget, QListWidgetItem,
    QCompleter, QCheckBox, QApplication
)
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QFontDatabase, QPainter, QTextFormat, QTextCursor
from PyQt6.QtCore import Qt, QRect, QSize, QStringListModel, QThread, pyqtSignal, QSortFilterProxyModel

from Perifericos.Interfaz_Usuario.themes import get_highlighter_colors
from Perifericos.Traducciones.i18n import tr

import re
import json
import os
import sys
from Nucleos_de_Procesamiento.Nucleo_de_Datos.Utilidades.rutas import get_resource_path, get_data_path

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self):
        return QSize(self.code_editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.code_editor.line_number_area_paint_event(event)

class CodeEditor(QPlainTextEdit):
    scriptClicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setMouseTracking(True)
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

    def mouseMoveEvent(self, event):
        """Muestra un preview del mensaje al pasar el mouse sobre un ID de mensaje."""
        cursor = self.cursorForPosition(event.pos())
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        word = cursor.selectedText()
        
        # Hyperlink detection for scripts
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.KeyboardModifier.ControlModifier:
            line = cursor.block().text()
            # Detectar si estamos sobre el argumento de Call, Jump o Execute_Script
            script_match = re.search(r'(?:Call|Jump|Execute_Script|Execute_Movement)\s*\(\s*"?([a-zA-Z0-9_]+)"?', line)
            if script_match:
                # Verificar si el cursor está dentro del rango del nombre del script
                start_idx = line.find(script_match.group(1))
                end_idx = start_idx + len(script_match.group(1))
                pos_in_line = cursor.positionInBlock()
                
                if start_idx <= pos_in_line <= end_idx:
                    self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
                    from PyQt6.QtWidgets import QToolTip
                    QToolTip.showText(self.mapToGlobal(event.pos()), f"<b>Seguir a:</b> {script_match.group(1)}<br><small>Ctrl + Click para abrir</small>", self)
                    return
        
        self.viewport().setCursor(Qt.CursorShape.IBeamCursor)

        if word.startswith("0x") or word.isdigit() or word.startswith("MESSAGE_"):
            # Buscar si el ID corresponde a un MESSAGE_X definido arriba
            msg_id = None
            if word.startswith("MESSAGE_"):
                msg_id = word.replace("MESSAGE_", "")
            else:
                # Ver si está dentro de una llamada a Talk/Print Message
                line = cursor.block().text()
                if "Message" in line or "Talk" in line or "Print" in line:
                    msg_id = word
            
            if msg_id:
                content = self.find_message_content(msg_id)
                if content:
                    from PyQt6.QtWidgets import QToolTip
                    QToolTip.showText(self.mapToGlobal(event.pos()), f"<b>Contenido del Mensaje:</b><br>{content}", self)
                    return
        
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            modifiers = event.modifiers()
            if modifiers == Qt.KeyboardModifier.ControlModifier:
                cursor = self.cursorForPosition(event.pos())
                line = cursor.block().text()
                script_match = re.search(r'(?:Call|Jump|Execute_Script|Execute_Movement)\s*\(\s*"?([a-zA-Z0-9_]+)"?', line)
                if script_match:
                    start_idx = line.find(script_match.group(1))
                    end_idx = start_idx + len(script_match.group(1))
                    pos_in_line = cursor.positionInBlock()
                    
                    if start_idx <= pos_in_line <= end_idx:
                        self.scriptClicked.emit(script_match.group(1))
                        return
        
        super().mousePressEvent(event)

    def find_message_content(self, msg_id):
        """Busca la definición de MESSAGE_X en el texto del editor."""
        text = self.toPlainText()
        # Limpiar prefijo 0x si existe para normalizar
        search_id = msg_id.replace("0x", "").lstrip("0")
        if not search_id: search_id = "0"
        
        import re
        # Buscar const MESSAGE_X = "..."
        # Soportamos tanto decimal como hex en la definición
        pattern = re.compile(rf'const\s+MESSAGE_(?:0x)?0*{search_id}\b\s*=\s*"(.*?)(?<!\\)"', re.IGNORECASE | re.DOTALL)
        match = pattern.search(text)
        if match:
            return match.group(1).replace("\\n", "<br>").replace("\\BRK", "<hr>").replace("\\WAIT_CLICK", " 🖱️")
        return None

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
        elif item_type in ("item", "food", "tool", "npc", "candidate", "anim"):
            # Insertar con comillas automáticamente si no las tiene ya
            current_text = tc.block().text()
            cursor_pos = tc.positionInBlock()
            
            # Ver si ya hay una comilla antes o después para evitar duplicados
            has_quote_before = cursor_pos > 0 and current_text[cursor_pos-1] == '"'
            # (El prefijo ya fue borrado, así que miramos justo antes)
            
            inserted_text = f'"{completion}"'
            if has_quote_before:
                inserted_text = f'{completion}"' # Solo cerrar si ya se abrió manual
            
            tc.insertText(inserted_text)
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
        if self._completer and self._completer.popup().isVisible():
            if e.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Tab, Qt.Key.Key_Escape, Qt.Key.Key_Backtab):
                e.ignore()
                return

        # Auto-identación básica
        if e.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            cursor = self.textCursor()
            line = cursor.block().text()
            indent = ""
            for char in line:
                if char.isspace(): indent += char
                else: break
            
            # Si la línea termina en '{', añadir un nivel más
            if line.strip().endswith("{"):
                indent += "    "
                
            super().keyPressEvent(e)
            self.insertPlainText(indent)
            return

        # Atajo manual: Ctrl + Espacio para autocompletado
        isManualTrigger = (e.modifiers() & Qt.KeyboardModifier.ControlModifier) and e.key() == Qt.Key.Key_Space
        
        if not isManualTrigger:
            super().keyPressEvent(e)

        if not self._completer:
            return

        completionPrefix = self.textUnderCursor()
        
        if not isManualTrigger and (not e.text() or len(completionPrefix) < 1):
            self._completer.popup().hide()
            return

        # Actualizar contexto según la línea
        line_text = self.textCursor().block().text()
        self.update_completer_context(line_text)

        # Detección de contexto y filtrado dinámico
        tc = self.textCursor()
        # Capturamos la línea hasta la posición del cursor
        tc.movePosition(QTextCursor.MoveOperation.StartOfLine, QTextCursor.MoveMode.KeepAnchor)
        line_text = tc.selectedText()
        
        self.update_completer_context(line_text)

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
        
        proxy = self._completer.model()
        if not isinstance(proxy, QSortFilterProxyModel): return

        # Reset filter
        filter_type = None
        
        # Give_Item( ...
        if re.search(r'Give_Item\(\s*[^,)]*$', line_text):
            filter_type = "item"
        # Funciones de entidades y personajes que toman un NPC ID como primer argumento
        elif re.search(r'(Set_Name_Window|Give_Friendship_Points|Free_Event_Entity|Set_Entity_Position|Get_Entity_X|Get_Entity_Y|Set_Entity_Facing|Get_Entity_Facing|Despawn_Entity|Is_NPC_Birthday|Chek_Friendship_Points|Has_NPC_Talked_Today|Has_NPC_Talked_Today_2|Kill_NPC|Execute_Movement|Hide_Entity|GetEntityLocation|Wait_For_Animation|Has_Met_NPC|Has_Spoken_To_NPC_Today|Routine_State_Override)\(\s*[^,)]*$', line_text):
            filter_type = "npc"
        # SetEntityAnim(entity, anim)
        elif re.search(r'SetEntityAnim\(\s*[^,)]*$', line_text):
            filter_type = "npc"
        elif re.search(r'SetEntityAnim\(\s*[^,)]+\s*,\s*[^,)]*$', line_text):
            filter_type = "anim"
        # Warp_Player(Farm, ...
        elif re.search(r'Warp_Player\(\s*[^,)]*$', line_text):
            filter_type = "map"
        # Set_Hearth_Anim( ...
        elif re.search(r'(Set_Hearth_Anim|Give_Love_Points|Chek_Love_Points)\(\s*[^,)]*$', line_text):
            filter_type = "candidate"
        # Give_Food( ...
        elif re.search(r'Give_Food\(\s*[^,)]*$', line_text):
            filter_type = "food"
        # Give_Tool, Give_Tool_TBox, Give_Tool_Inventory, Animation_Tool_Give, Take_Tool
        # En FOMT, las semillas y otros variados se usan como herramientas, así que mostramos ambos.
        elif re.search(r'(Give_Tool(?:_TBox|_Inventory)?|An?imation_Tool_Give|Take_Tool|Check_Equped_Tool|Check_Tool_Inventory_Space|Check_Tool_TBox_Space)\(\s*[^,)]*$', line_text):
            filter_type = "tool|item"
        # Set_Portrait( ...
        elif re.search(r'Set_Portrait\(\s*[^,)]*$', line_text):
            filter_type = "portrait"
        # Comparaciones con GetEntityLocation (que devuelve un Map ID)
        elif re.search(r'GetEntityLocation\(.*?\)\s*(==|!=|<=|>=|<|>)\s*[^,)]*$', line_text):
            filter_type = "map"
        
        if filter_type:
            # Filtramos el modelo para que solo muestre el tipo detectado
            # Usamos un rol personalizado (UserRole) para el filtrado por tipo
            proxy.setFilterRole(Qt.ItemDataRole.UserRole)
            proxy.setFilterRegularExpression(filter_type)
        else:
            # Modo general: Comandos y palabras clave
            # IMPORTANTE: Si no hay paréntesis abierto, mostramos comandos y KWs.
            # Si hay un paréntesis abierto pero no es uno de los especiales, quizá nada o todo.
            if "(" in line_text and not line_text.endswith("("):
                 # Estamos dentro de argumentos de una función genérica
                 proxy.setFilterFixedString("___NONE___") # Ocultar todo si no es especial? 
                 # O mejor dejamos que muestre todo por si acaso.
            else:
                # Mostrar comandos y keywords por defecto
                proxy.setFilterRole(Qt.ItemDataRole.UserRole)
                # Filtro complejo: "cmd|kw" (Regex)
                proxy.setFilterRegularExpression("cmd|kw")

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
        
        # Propagar señal del editor
        self.editor.scriptClicked.connect(self.on_script_clicked)

    def on_script_clicked(self, script_ref):
        # Intentar determinar si es un ID o un nombre
        main_window = self.window()
        if hasattr(main_window, 'open_script_by_ref'):
            main_window.open_script_by_ref(script_ref)
        
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
        
        # Atajo Ctrl+S para compilar el script actual
        from PyQt6.QtGui import QShortcut, QKeySequence
        self.compile_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        self.compile_shortcut.activated.connect(self.on_compile_clicked)

        # Barra de Búsqueda Global (Buscar texto en todos los eventos)
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar texto en todos los eventos...")
        self.search_input.returnPressed.connect(self.on_global_search)
        
        self.btn_search = QPushButton("🔍")
        self.btn_search.setFixedWidth(40)
        self.btn_search.clicked.connect(self.on_global_search)
        
        self.check_only_messages = QCheckBox("Solo en mensajes")
        self.check_only_messages.setToolTip("Busca el texto solo dentro de los bloques 'const MESSAGE_X = \"...\"'")
        
        self.btn_clear_search = QPushButton("❌")
        self.btn_clear_search.setFixedWidth(40)
        self.btn_clear_search.setToolTip("Limpiar resultados de búsqueda y mostrar todos los eventos")
        self.btn_clear_search.clicked.connect(self.on_clear_search)
        self.btn_clear_search.setEnabled(False)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.btn_search)
        search_layout.addWidget(self.btn_clear_search)
        search_layout.addWidget(self.check_only_messages)
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
        knowledge_path = get_resource_path("fomt_knowledge.json")
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
        lib_path = get_data_path(lib_name)
        
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

        # 3. Palabras clave y estructuras
        keywords = ["if", "else", "for", "while", "do", "switch", "case", "default", "var", "const", "script", "exit"]
        for kw in keywords:
            q_item = QStandardItem(kw)
            q_item.setData("kw", Qt.ItemDataRole.UserRole)
            q_item.setData(kw, Qt.ItemDataRole.EditRole)
            self.completer_model.appendRow(q_item)
            
        # [ELIMINADO TEMPORALMENTE] IDs de retratos (User requested removal until mapping is done)
        # if "ids" in knowledge_data and "portraits" in knowledge_data["ids"]:
        #     ...
        
        # 4. Añadir nombres de ítems al autocompletado
        if self.project.item_parser:
            try:
                items = self.project.item_parser.scan_foods()
                for itm in items:
                    if itm.category == "Artículo":
                        tag = "item"
                    elif itm.category == "Consumible/Comida":
                        tag = "food"
                    elif itm.category == "Herramienta":
                        tag = "tool"
                    else:
                        continue
                        
                    # Limpiar nombre igual que en el compilador para consistencia
                    name = itm.name_str.replace('\n', ' ').strip('\x00').strip()
                    if not name: name = f"Unknown_{itm.index}"
                    
                    if name and name != "Desconocido":
                        # Mostrar el ID real (el que usa el juego en scripts) en el texto de la lista
                        real_id = getattr(itm, 'real_id', itm.index)
                        display_text = f"{name} (0x{real_id:02X})"
                        
                        q_item = QStandardItem(display_text)
                        q_item.setData(tag, Qt.ItemDataRole.UserRole)
                        q_item.setData(name, Qt.ItemDataRole.EditRole) # Insertamos solo el nombre
                        
                        q_item.setToolTip(f"ID Real: {real_id} (0x{real_id:04X})\nÍndice Tabla: {itm.index}\nCategoría: {itm.category}")
                        self.completer_model.appendRow(q_item)
            except: pass

        # 5. Añadir nombres de personajes (NPCs y Candidatas)
        if self.project.npc_parser:
            try:
                npcs = self.project.npc_parser.scan_npcs()
                for npc in npcs:
                    name = npc.name_str.strip('\x00')
                    if name:
                        completion_text = name # Sin comillas en el modelo
                        
                        # Item general de NPC (ID 1-based y hex)
                        real_id = npc.index + 1
                        q_item = QStandardItem(completion_text)
                        q_item.setData("npc", Qt.ItemDataRole.UserRole)
                        q_item.setData(completion_text, Qt.ItemDataRole.EditRole)
                        q_item.setToolTip(f"ID: {real_id} (0x{real_id:02X})\nRol: {npc.get_translated_role()}")
                        self.completer_model.appendRow(q_item)
                        
                        # Si es candidata, añadir otro item oculto o duplicado para el filtro de candidatas
                        if npc.is_candidate:
                            cand_item = QStandardItem(completion_text)
                            cand_item.setData("candidate", Qt.ItemDataRole.UserRole)
                            cand_item.setData(completion_text, Qt.ItemDataRole.EditRole)
                            cand_item.setToolTip(f"ID: {real_id} (0x{real_id:02X})\n[CANDIDATA A MATRIMONIO]")
                            self.completer_model.appendRow(cand_item)
            except: pass
            
        # 6. Añadir retratos (Portraits) desde el mapeo externo
        if self.project.super_lib and self.project.super_lib.portrait_map:
            for name, val in self.project.super_lib.portrait_map.items():
                q_item = QStandardItem(name)
                q_item.setData("portrait", Qt.ItemDataRole.UserRole)
                q_item.setData(name, Qt.ItemDataRole.EditRole)
                q_item.setToolTip(f"Portrait ID: 0x{val:02X} ({val})")
                self.completer_model.appendRow(q_item)
                
        # 7. Añadir nombres de mapas
        if self.project.super_lib and self.project.super_lib.map_map:
            for name, val in self.project.super_lib.map_map.items():
                q_item = QStandardItem(name)
                q_item.setData("map", Qt.ItemDataRole.UserRole)
                q_item.setData(name, Qt.ItemDataRole.EditRole)
                q_item.setToolTip(f"Map ID: 0x{val:02X} ({val})")
                self.completer_model.appendRow(q_item)

        # 8. Añadir nombres de animaciones
        if self.project.super_lib and self.project.super_lib.anim_map:
            for name, val in self.project.super_lib.anim_map.items():
                q_item = QStandardItem(name)
                q_item.setData("anim", Qt.ItemDataRole.UserRole)
                q_item.setData(name, Qt.ItemDataRole.EditRole)
                q_item.setToolTip(f"Animation ID: 0x{val:03X} ({val})")
                self.completer_model.appendRow(q_item)
        
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.completer_model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        
        completer = QCompleter(self.proxy_model, self)
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
            # FIX: Mantener el tamaño máximo si se escribe in-place para no perder el padding FF
            if new_offset == old_offset:
                self.project.event_parser.scanned_sizes[self.current_event_id] = max(old_size, len(new_data))
            else:
                self.project.event_parser.scanned_sizes[self.current_event_id] = len(new_data)
            mode_prefix = "Event"
        else:
            # MapScripts o scripts por offset
            if old_offset:
                self.project.event_parser.scanned_sizes[old_offset] = max(old_size, len(new_data))
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
            
            # FIX: Actualizar el tamaño escaneado para el nuevo offset si hubo repunteo
            if new_offset == old_offset:
                self.project.event_parser.scanned_sizes[old_offset] = max(old_size, len(new_data))
            else:
                self.project.event_parser.scanned_sizes[new_offset] = len(new_data)
                
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
        
        only_messages = self.check_only_messages.isChecked()
        count = self.project.event_parser.get_event_count()
        event_ids = list(range(1, count + 1))
        
        from PyQt6.QtWidgets import QProgressDialog
        self.search_progress = QProgressDialog("Buscando en eventos (Multi-thread)...", "Cancelar", 0, len(event_ids), self)
        self.search_progress.setWindowModality(Qt.WindowModality.WindowModal)
        
        self.worker = SearchWorker(query, self.project, event_ids, only_messages)
        self.worker.progress.connect(self.search_progress.setValue)
        self.worker.finished.connect(self.on_search_finished)
        self.search_progress.canceled.connect(self.worker.stop)
        
        self.worker.start()

    def on_search_finished(self, results):
        self.search_progress.close()
        if results:
            self.btn_clear_search.setEnabled(True)
            # Llamar al padre (App) para filtrar el árbol izquierdo
            main_window = self.window()
            if hasattr(main_window, 'filter_events'):
                main_window.filter_events(results)
            
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Resultados de Búsqueda", f"Se encontró '{self.search_input.text()}' en {len(results)} eventos.\n\nLos resultados se han filtrado en el explorador de la izquierda.")
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Búsqueda", "No se encontraron coincidencias.")

    def on_clear_search(self):
        """Limpia el filtro de búsqueda y restaura la lista de eventos completa."""
        self.search_input.clear()
        self.btn_clear_search.setEnabled(False)
        main_window = self.window()
        if hasattr(main_window, 'clear_event_filter'):
            main_window.clear_event_filter()

class SearchWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(list)
    
    def __init__(self, query, project, event_ids, only_messages=False):
        super().__init__()
        self.query = query.lower()
        self.project = project
        self.event_ids = event_ids
        self.only_messages = only_messages
        self._is_running = True
        
    def stop(self):
        self._is_running = False
        
    def run(self):
        results = []
        # Búsqueda por fragmentos (Case Insensitive)
        pattern_str = re.escape(self.query)
        search_pattern = re.compile(pattern_str, re.IGNORECASE)
        # Regex para extraer el contenido de los mensajes (soporta comillas escapadas \")
        msg_pattern = re.compile(r'const\s+MESSAGE_\d+\s*=\s*"(.*?)(?<!\\)"', re.DOTALL)
        
        for i, eid in enumerate(self.event_ids):
            if not self._is_running: break
            if i % 10 == 0: self.progress.emit(i)
            
            try:
                code, _ = self.project.event_parser.decompile_to_ui(eid)
                
                if self.only_messages:
                    # Extraemos todos los textos de los bloques const MESSAGE
                    messages_text = []
                    for match in msg_pattern.finditer(code):
                        messages_text.append(match.group(1))
                    
                    combined_messages = "\n".join(messages_text)
                    if search_pattern.search(combined_messages):
                        results.append(eid)
                else:
                    # Búsqueda en todo el código (incluye comandos, nombres decorados, etc.)
                    if search_pattern.search(code):
                        results.append(eid)
            except: continue
            
        self.finished.emit(results)
