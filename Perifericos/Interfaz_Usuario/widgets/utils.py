# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.6.5)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
from PyQt6.QtWidgets import QStyledItemDelegate, QLineEdit, QLabel, QVBoxLayout, QWidget, QToolTip
from PyQt6.QtCore import Qt, QPoint, QTimer

class NameEditDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, max_limit=10):
        super().__init__(parent)
        self.bubble = None
        self.max_limit = max_limit

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        
        # Si max_limit es None o 0, no forzar maxLength pero la burbuja mostrará el conteo
        if self.max_limit:
            editor.setMaxLength(self.max_limit)
        
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
        
        limit_val = self.max_limit or 50 # Default para visualización si no hay límite
        self._update_bubble(editor.text(), limit_val, editor)
        self.bubble.show()
        
        editor.textChanged.connect(lambda t: self._update_bubble(t, limit_val, editor))
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
