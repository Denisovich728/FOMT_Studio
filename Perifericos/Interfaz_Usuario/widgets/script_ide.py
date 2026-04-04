from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QTextEdit,
    QPushButton, QLabel, QSplitter, QListWidget, QListWidgetItem
)
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QFontDatabase, QPainter, QTextFormat
from PyQt6.QtCore import Qt, QRect, QSize

from Perifericos.Interfaz_Usuario.themes import get_highlighter_colors
from Perifericos.Traducciones.i18n import tr

import re

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
            line_color = QColor(Qt.GlobalColor.darkGreen).lighter(160)
            # Adaptar según el tema si es posible, pero por ahora algo sutil
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        self.setExtraSelections(extra_selections)

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        # Fondo del margen (ligeramente distinto al fondo del editor)
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
            "PlaySound", "GiveItem", "HasItem", "IncVar", "DecVar"
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
        
        toolbar.addWidget(self.lbl_title)
        toolbar.addStretch()
        toolbar.addWidget(self.btn_compile)
        
        layout.addLayout(toolbar)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # Uso de CodeEditor (QPlainTextEdit personalizado)
        self.editor = CodeEditor()
        
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(11)
        self.editor.setFont(font)
        
        self.highlighter = FoMTHighlighter(self.editor.document())
        self.highlighter.update_colors("light")
        
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
        
        # En una versión real, aquí compilaríamos el texto de vuelta a bytecode (o usaríamos un assembler)
        # Como simulación inteligente de repunteo:
        code = self.editor.toPlainText()
        
        # Obtenemos info del evento actual
        hint, old_offset = self.project.event_parser.get_event_name_and_offset(self.current_event_id)
        
        # Fake compilation (Simulamos que los bytes son proporcionales al texto)
        new_data = code.encode('windows-1252', errors='replace')
        
        # Calculamos el tamaño original (SI existe el evento en la ROM)
        old_size = 0
        if old_offset:
            # Para la simulación, asumimos que sabemos el tamaño original (ej. guardado en el parser)
            # En la vida real, leeríamos el chunk RIFF o el bytecode hasta el exit 0x0B
            old_size = self.project.event_parser.get_last_scanned_size(self.current_event_id)
            
        # Llamamos al MemoryManager inteligente
        new_offset = self.project.memory.re_point_master_event(
            self.current_event_id, old_offset, old_size, new_data
        )
        
        from PyQt6.QtWidgets import QMessageBox
        lang = self.lang
        
        status_msg = "In-Place Edit (Memoria Optimizada)" if new_offset == old_offset else "Re-pointed (Free Space Allocated)"
        
        QMessageBox.information(
            self, 
            tr('msg_memory_manager', lang),
            f"{tr('msg_simulation', lang)}\n\n"
            f"Mode: {status_msg}\n"
            f"Offset: 0x{new_offset:08X}\n"
            f"Original Size: {old_size} bytes\n"
            f"New Size: {len(new_data)} bytes"
        )
