
from PyQt6.QtWidgets import QStyledItemDelegate, QLineEdit, QLabel, QVBoxLayout, QWidget, QToolTip
from PyQt6.QtCore import Qt, QPoint, QTimer

class NameEditDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.bubble = None

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        # Obtener max_len guardado en los metadatos del item
        max_len = index.data(Qt.ItemDataRole.UserRole + 2) or 20
        editor.setMaxLength(max_len)
        
        # Estilo del editor para que resalte
        editor.setStyleSheet("border: 2px solid #00FF41; background-color: #000000; color: #00FF41;")
        
        # Crear la burbuja flotante
        self.bubble = QLabel(parent.window())
        self.bubble.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.bubble.setStyleSheet("""
            background-color: #000000; 
            color: #00FF41; 
            border: 1px solid #00FF41; 
            padding: 2px 5px; 
            font-weight: bold;
            font-size: 10px;
            border-radius: 5px;
        """)
        self.bubble.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        self._update_bubble(editor.text(), max_len, editor)
        self.bubble.show()
        
        editor.textChanged.connect(lambda t: self._update_bubble(t, max_len, editor))
        editor.destroyed.connect(self._hide_bubble)
        
        return editor

    def _update_bubble(self, text, max_len, editor):
        if not self.bubble: return
        count = len(text.encode('windows-1252', errors='ignore'))
        self.bubble.setText(f"{count}/{max_len}")
        
        # Posicionar burbuja sobre el editor
        pos = editor.mapToGlobal(QPoint(editor.width() // 2 - self.bubble.width() // 2, -25))
        self.bubble.move(pos)
        
        if count >= max_len:
            self.bubble.setStyleSheet(self.bubble.styleSheet() + "color: #FF0000; border-color: #FF0000;")
        else:
            self.bubble.setStyleSheet(self.bubble.styleSheet() + "color: #00FF41; border-color: #00FF41;")

    def _hide_bubble(self):
        if self.bubble:
            self.bubble.hide()
            self.bubble.deleteLater()
            self.bubble = None

    def setModelData(self, editor, model, index):
        self._hide_bubble()
        super().setModelData(editor, model, index)
