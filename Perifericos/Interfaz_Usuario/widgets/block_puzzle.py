import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGraphicsView, QGraphicsScene, 
    QGraphicsItem, QGraphicsPathItem, QGraphicsTextItem, QGraphicsRectItem,
    QFrame, QLabel, QScrollArea, QListWidget, QListWidgetItem, QGraphicsProxyWidget,
    QLineEdit, QComboBox, QPushButton
)
from PyQt6.QtGui import (
    QPainter, QPainterPath, QColor, QBrush, QPen, QFont, QLinearGradient, QAction
)
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal

class BlockType:
    COMMAND = "command"
    CONDITION = "condition"
    MESSAGE = "message"
    FLOW = "flow"
    SETTER = "setter"
    LOOP = "loop"
    IF = "if"
    ELSE = "else"

class PuzzleBlock(QGraphicsPathItem):
    def __init__(self, block_type, label, parent=None):
        super().__init__(parent)
        self.block_type = block_type
        self.label_text = label
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        
        self.width = 220
        self.height = 45
        self.nub_size = 12
        self.is_container = block_type in (BlockType.LOOP, BlockType.IF, BlockType.ELSE)
        self.inner_height = 40 if self.is_container else 0
        
        # Logic links
        self.next_block = None
        self.prev_block = None
        self.first_child = None
        self.label = QGraphicsTextItem(self.label_text, self)
        self.label.setDefaultTextColor(Qt.GlobalColor.white)
        self.label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.label.setPos(10, 8)
        
        # Colors based on type (Premium Palette)
        colors = {
            BlockType.COMMAND: QColor("#4A90E2"), # Blue
            BlockType.CONDITION: QColor("#9B51E0"), # Purple
            BlockType.MESSAGE: QColor("#27AE60"), # Green
            BlockType.FLOW: QColor("#F2C94C"), # Yellow/Orange
            BlockType.SETTER: QColor("#E67E22")  # Orange
        }
        self.base_color = colors.get(self.block_type, QColor("#95A5A6"))
        
        # Add Input Field if needed
        if self.block_type in (BlockType.MESSAGE, BlockType.COMMAND, BlockType.SETTER):
            self.input_proxy = QGraphicsProxyWidget(self)
            self.input_field = QLineEdit()
            self.input_field.setPlaceholderText("...")
            self.input_field.setFixedWidth(100)
            self.input_field.setStyleSheet("""
                QLineEdit { 
                    background: rgba(255, 255, 255, 0.2); 
                    border: 1px solid rgba(0,0,0,0.3); 
                    border-radius: 4px; 
                    color: white; 
                    font-size: 10px;
                    padding: 2px;
                }
            """)
            self.input_proxy.setWidget(self.input_field)
            self.input_proxy.setPos(90, 10)
        
        self.update_path()


    def get_snap_points(self):
        """Returns the top and bottom snap points in scene coordinates."""
        top_snap = self.mapToScene(QPointF(25, 0))
        bottom_snap = self.mapToScene(QPointF(25, self.height))
        return top_snap, bottom_snap

    def update_path(self):
        path = QPainterPath()
        w, h = self.width, self.height
        n = self.nub_size
        
        # Start top-left
        path.moveTo(0, 0)
        
        # Top nub (indent)
        path.lineTo(15, 0)
        path.lineTo(20, n/2)
        path.lineTo(30, n/2)
        path.lineTo(35, 0)
        
        path.lineTo(w - 5, 0)
        path.arcTo(w-10, 0, 10, 10, 90, -90)
        
        path.lineTo(w, h + self.inner_height + 5)
        path.arcTo(w-10, h + self.inner_height, 10, 10, 0, -90)
        
        # Bottom nub (outdent)
        path.lineTo(35 + (20 if self.is_container else 0), h + self.inner_height)
        path.lineTo(30 + (20 if self.is_container else 0), h + self.inner_height + n/2)
        path.lineTo(20 + (20 if self.is_container else 0), h + self.inner_height + n/2)
        path.lineTo(15 + (20 if self.is_container else 0), h + self.inner_height)
        
        if self.is_container:
            # Special C-shape for blocks inside
            # Inner bottom
            path.lineTo(35, h + self.inner_height)
            path.lineTo(35, h)
            # Inner top snap (indent)
            path.lineTo(35, h)
            path.lineTo(30, h - n/2)
            path.lineTo(20, h - n/2)
            path.lineTo(15, h)
            path.lineTo(15, h + self.inner_height)

        path.lineTo(5, h + self.inner_height)
        path.arcTo(0, h + self.inner_height - 10, 10, 10, 270, -90)
        
        path.closeSubpath()
        self.setPath(path)
        
        # Gradient
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, self.base_color.lighter(110))
        grad.setColorAt(1, self.base_color.darker(110))
        self.setBrush(QBrush(grad))
        self.setPen(QPen(self.base_color.darker(150), 1.5))

    def paint(self, painter, option, widget):
        if self.isSelected():
            self.setPen(QPen(Qt.GlobalColor.white, 2, Qt.PenStyle.DashLine))
        else:
            self.setPen(QPen(self.base_color.darker(150), 1.5))
        super().paint(painter, option, widget)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            new_pos = value
            # Find nearby blocks for snapping
            top_snap, _ = self.get_snap_points()
            
            for item in self.scene().items():
                if item != self and isinstance(item, PuzzleBlock):
                    _, other_bottom_snap = item.get_snap_points()
                    
                    dist = (top_snap - other_bottom_snap).manhattanLength()
                    if dist < 15:
                        # Snap! Calculate offset to align top_snap with other_bottom_snap
                        snap_pos = other_bottom_snap - QPointF(25, 0)
                        return snap_pos
                        
        return super().itemChange(change, value)

class BlockCanvas(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(0, 0, 5000, 5000)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setAcceptDrops(True)
        self.setBackgroundBrush(QBrush(QColor("#1e1e1e"))) # Dark background
        
        # Draw grid
        self.grid_size = 20
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-block-type"):
            event.acceptProposedAction()
            
    def dragMoveEvent(self, event):
        event.acceptProposedAction()
        
    def dropEvent(self, event):
        data = event.mimeData().data("application/x-block-type").data().decode()
        label = event.mimeData().text()
        pos = self.mapToScene(event.position().toPoint())
        
        block = PuzzleBlock(data, label)
        block.setPos(pos)
        self.scene.addItem(block)
        event.acceptProposedAction()

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        pen = QPen(QColor("#2d2d2d"), 0.5)
        painter.setPen(pen)
        
        left = int(rect.left()) - (int(rect.left()) % self.grid_size)
        top = int(rect.top()) - (int(rect.top()) % self.grid_size)
        
        for x in range(left, int(rect.right()), self.grid_size):
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
        for y in range(top, int(rect.bottom()), self.grid_size):
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)

class BlockPuzzleEditor(QWidget):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.setup_ui()
        
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Sidebar for blocks
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(220)
        self.sidebar.setStyleSheet("background-color: #252526; border-right: 1px solid #333;")
        side_layout = QVBoxLayout(self.sidebar)
        
        self.toolbox = QListWidget()
        self.toolbox.setDragEnabled(True)
        self.toolbox.setStyleSheet("""
            QListWidget { background: transparent; border: none; }
            QListWidget::item { padding: 12px; color: #eee; border-bottom: 1px solid #333; font-weight: bold; }
            QListWidget::item:hover { background: #37373d; border-left: 4px solid #4A90E2; }
        """)
        self.toolbox.startDrag = self.start_toolbox_drag
        
        self.add_toolbox_item("Mensaje 💬", BlockType.MESSAGE)
        self.add_toolbox_item("Caminar 🏃", BlockType.COMMAND)
        self.add_toolbox_item("Condición If ❓", BlockType.CONDITION)
        self.add_toolbox_item("Ir a Etiqueta 🚩", BlockType.FLOW)
        self.add_toolbox_item("Definir Variable ⚙️", BlockType.SETTER)
        
        side_layout.addWidget(QLabel("<b>🧩 BLOQUES</b>", styleSheet="color: #4A90E2; padding: 10px; font-size: 14px;"))
        side_layout.addWidget(self.toolbox)
        
        side_layout.addStretch()
        
        self.btn_compile = QPushButton("Generar Script 🛠️")
        self.btn_compile.setStyleSheet("""
            QPushButton {
                background: #4A90E2;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
                margin: 10px;
            }
            QPushButton:hover { background: #357ABD; }
        """)
        self.btn_compile.clicked.connect(self.compile_logic)
        side_layout.addWidget(self.btn_compile)
        
        # Main Canvas
        self.canvas = BlockCanvas()
        
        layout.addWidget(self.sidebar)
        layout.addWidget(self.canvas)
        
    def start_toolbox_drag(self, supportedActions):
        item = self.toolbox.currentItem()
        if not item: return
        
        from PyQt6.QtCore import QMimeData
        from PyQt6.QtGui import QDrag
        
        mime = QMimeData()
        mime.setData("application/x-block-type", item.data(Qt.ItemDataRole.UserRole).encode())
        mime.setText(item.text())
        
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)

    def add_toolbox_item(self, text, type):
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, type)
        self.toolbox.addItem(item)

    def get_facing_text(self, val):
        mapping = {0: "Down 👇", 1: "Up 👆", 2: "Left 👈", 3: "Right 👉"}
        try: 
            v = int(val, 0) if isinstance(val, str) else int(val)
            return mapping.get(v, str(val))
        except: 
            return str(val)
        
    def load_event(self, event_id):
        """Analyzes an event and converts its AST to blocks."""
        code, stmts = self.project.event_parser.decompile_to_ui(event_id)
        self.canvas.scene.clear()
        
        y_offset = 50
        for stmt in stmts:
            y_offset = self._create_blocks_from_stmt(stmt, 50, y_offset)
            
    def _create_blocks_from_stmt(self, stmt, x, y):
        from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine import ast as SS_AST
        
        block = None
        if isinstance(stmt, SS_AST.StmtMessage):
            block = self.create_block(BlockType.MESSAGE, "Mensaje 💬")
            block.input_field.setText(stmt.text.decode('shift-jis', errors='ignore'))
        elif isinstance(stmt, SS_AST.StmtCall):
            func = stmt.invoke.func
            args = stmt.invoke.args
            
            # Decoration for Facing/Direction
            if func == "SetEntityFacing":
                facing = self._eval_arg(args[1])
                block = self.create_block(BlockType.COMMAND, f"Mirar {self.get_facing_text(facing)}")
                block.input_field.setText(str(self._eval_arg(args[0]))) # Name
            elif func == "SetEntityPosition":
                facing = self._eval_arg(args[3])
                block = self.create_block(BlockType.COMMAND, f"Set Pos (Mirando {self.get_facing_text(facing)})")
                block.input_field.setText(f"{self._eval_arg(args[0])}, {self._eval_arg(args[1])}, {self._eval_arg(args[2])}")
            elif func == "Execute_Vector":
                block = self.create_block(BlockType.COMMAND, "Mover a Vector 📍")
                block.input_field.setText(f"{self._eval_arg(args[1])}, {self._eval_arg(args[2])}")
            elif func == "Execute_Move":
                block = self.create_block(BlockType.COMMAND, "Hacer movimiento 🏃")
            elif func == "Make_Delay":
                val = self._eval_arg(args[0])
                block = self.create_block(BlockType.COMMAND, "Esperar ⏳")
                block.input_field.setText(str(val))
            else:
                block = self.create_block(BlockType.COMMAND, func)
                block.input_field.setText(", ".join([str(self._eval_arg(a)) for a in args]))
        
        if block:
            block.setPos(x, y)
            return y + block.height + 5
        return y

    def _eval_arg(self, arg):
        from Nucleos_de_Procesamiento.Nucleo_de_Eventos.SlipSpace_Script_Engine import ast as SS_AST
        if isinstance(arg, SS_AST.ExprInt): return arg.value
        if isinstance(arg, SS_AST.ExprStr): return arg.value.decode('shift-jis', errors='ignore')
        if isinstance(arg, (SS_AST.ExprOpAdd, SS_AST.ExprOpMul, SS_AST.ExprOpSub, SS_AST.ExprOpDiv)):
            # Handle composed expressions like (0x3C * 2)
            try:
                # Use a dummy const access
                class Dummy: 
                    def lookup_const(self, n): return None
                res = SS_AST.eval_expr(arg, Dummy())
                if res: return res.value
            except: pass
        return str(arg)

    def compile_logic(self):
        """Traverses the blocks and generates SlipSpace code."""
        # Find the top-most block (the one with no block above its top snap)
        all_blocks = [i for i in self.canvas.scene.items() if isinstance(i, PuzzleBlock)]
        if not all_blocks: return
        
        # Simple heuristic: sort by Y position for now
        sorted_blocks = sorted(all_blocks, key=lambda b: b.y())
        
        code = "// Script generado por Bloques\n"
        for b in sorted_blocks:
            input_val = b.input_field.text() if hasattr(b, 'input_field') else ""
            if b.block_type == BlockType.MESSAGE:
                code += f"Talk(Player, \"{input_val}\");\n"
            elif b.block_type == BlockType.COMMAND:
                code += f"{input_val};\n"
            elif b.block_type == BlockType.SETTER:
                code += f"var_0 = {input_val};\n"
            else:
                code += f"// {b.label_text}\n"
                
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Script Generado", code)

    def create_block(self, type, label):
        block = PuzzleBlock(type, label)
        self.canvas.scene.addItem(block)
        return block

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = BlockPuzzleEditor(None)
    window.showMaximized()
    
    # Add some test blocks
    b1 = window.create_block(BlockType.MESSAGE, "Talk(Player, 'Hello!')")
    b1.setPos(300, 100)
    
    b2 = window.create_block(BlockType.COMMAND, "WalkTo(NPC_01, 10, 12)")
    b2.setPos(300, 140)
    
    sys.exit(app.exec())
