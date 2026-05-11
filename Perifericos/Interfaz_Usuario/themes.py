# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.0.0)
# "The Imposibility Update"
# Desarrollado por: Denisovich728
# ============================================================

def get_forerunner_theme():
    return """
        QMainWindow, QDialog { background-color: #050B15; color: #00E5FF; }
        QWidget { background-color: #050B15; color: #00E5FF; font-family: 'Consolas', 'Segoe UI', sans-serif; }
        
        QSplitter::handle { background-color: #003B4F; }
        
        QMenuBar { background-color: #050B15; color: #00E5FF; border-bottom: 2px solid #00E5FF; }
        QMenu { background-color: #050B15; color: #00E5FF; border: 1px solid #00E5FF; }
        QMenu::item:selected { background-color: rgba(0, 229, 255, 0.2); }
        
        QTabWidget::pane { border: 1px solid #00E5FF; background-color: rgba(0, 229, 255, 0.05); }
        QTabBar::tab { background: #0A192F; color: #00B8D4; border: 1px solid #003B4F; padding: 10px 15px; margin-right: 2px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
        QTabBar::tab:selected { background: rgba(0, 229, 255, 0.1); color: #00E5FF; border-bottom: 2px solid #00E5FF; font-weight: bold; }
        
        QTableView { background-color: #0A192F; color: #00E5FF; gridline-color: #003B4F; border: 1px solid #00E5FF; selection-background-color: rgba(0, 229, 255, 0.2); }
        QHeaderView::section { background-color: #050B15; color: #00B8D4; padding: 4px; border: 1px solid #003B4F; }
        
        QTreeView { background-color: #050B15; color: #00E5FF; border: none; selection-background-color: rgba(0, 229, 255, 0.2); }
        
        QPushButton { background-color: transparent; color: #00E5FF; border: 1px solid #00E5FF; padding: 8px; border-radius: 2px; text-transform: uppercase; letter-spacing: 1px; }
        QPushButton:hover { background-color: rgba(0, 229, 255, 0.1); border-color: #00F2FF; }
        QPushButton:pressed { background-color: rgba(0, 229, 255, 0.3); }
        
        QLineEdit, QTextEdit, QPlainTextEdit { background-color: rgba(0, 229, 255, 0.05); color: #00E5FF; border: 1px solid #003B4F; selection-background-color: #003B4F; }
        
        QStatusBar { background-color: #050B15; color: #00E5FF; border-top: 1px solid #00E5FF; }
        
        QScrollBar:vertical { border: none; background: #050B15; width: 10px; margin: 0px; }
        QScrollBar::handle:vertical { background: #00E5FF; min-height: 20px; border-radius: 5px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    """

def get_matrix_theme():
    return """
        QMainWindow, QDialog { background-color: #000000; color: #00FF41; }
        QWidget { background-color: #000000; color: #00FF41; font-family: 'Consolas', 'Courier New', monospace; }
        
        QSplitter::handle { background-color: #003B00; }
        
        QMenuBar { background-color: #000000; color: #00FF41; border-bottom: 1px solid #003B00; }
        QMenu { background-color: #000000; color: #00FF41; border: 1px solid #00FF41; }
        QMenu::item:selected { background-color: #003B00; }
        
        QTabWidget::pane { border: 1px solid #00FF41; top: -1px; }
        QTabBar::tab { background: #001000; color: #00FF41; border: 1px solid #003B00; padding: 10px; margin-right: 2px; }
        QTabBar::tab:selected { background: #003B00; border-bottom: 2px solid #00FF41; }
        
        QTableView { background-color: #000000; color: #00FF41; gridline-color: #003B00; border: 1px solid #00FF41; selection-background-color: #003B00; }
        QHeaderView::section { background-color: #001000; color: #00FF41; padding: 4px; border: 1px solid #003B00; }
        
        QTreeView { background-color: #000000; color: #00FF41; border: 1px solid #003B00; selection-background-color: #003B00; }
        
        QPushButton { background-color: #000000; color: #00FF41; border: 2px solid #00FF41; padding: 6px; border-radius: 4px; font-weight: bold; }
        QPushButton:hover { background-color: #001A00; border-color: #00FF8C; }
        QPushButton:pressed { background-color: #003B00; }
        
        QLineEdit, QTextEdit, QPlainTextEdit { background-color: #050505; color: #00FF41; border: 1px solid #003B00; selection-background-color: #003B00; }
        QScrollBar:vertical { background: #000000; width: 12px; }
        QScrollBar::handle:vertical { background: #003B00; min-height: 20px; }
        
        QComboBox { background-color: #000000; color: #00FF41; border: 1px solid #00FF41; padding: 4px; }
        QComboBox QAbstractItemView { background-color: #000000; color: #00FF41; selection-background-color: #003B00; }
        
        QStatusBar { background-color: #001000; color: #00FF41; border-top: 1px solid #003B00; }
    """

def get_dark_theme():
    return """
        QMainWindow, QDialog { background-color: #1e1e1e; color: #d4d4d4; }
        QWidget { background-color: #1e1e1e; color: #d4d4d4; font-family: 'Segoe UI', Arial, sans-serif; }
        
        QSplitter::handle { background-color: #333333; }
        
        QMenuBar { background-color: #252526; color: #cccccc; }
        QMenu { background-color: #252526; color: #cccccc; border: 1px solid #454545; }
        QMenu::item:selected { background-color: #094771; }
        
        QTabWidget::pane { border: 1px solid #333333; }
        QTabBar::tab { background: #2d2d2d; color: #969696; padding: 8px 12px; }
        QTabBar::tab:selected { background: #1e1e1e; color: #ffffff; border-bottom: 2px solid #007acc; }
        
        QTableView { background-color: #252526; color: #cccccc; gridline-color: #333333; border: 1px solid #333333; selection-background-color: #264f78; }
        QHeaderView::section { background-color: #2d2d2d; color: #cccccc; border: 1px solid #333333; }
        
        QTreeView { background-color: #252526; color: #cccccc; border: none; }
        
        QPushButton { background-color: #333333; color: #ffffff; border: none; padding: 6px 12px; border-radius: 2px; }
        QPushButton:hover { background-color: #404040; }
        QPushButton:pressed { background-color: #007acc; }
        
        QLineEdit, QTextEdit, QPlainTextEdit { background-color: #3c3c3c; color: #cccccc; border: 1px solid #3c3c3c; }
        QStatusBar { background-color: #007acc; color: #ffffff; }
    """

def get_light_theme():
    return """
        QMainWindow, QDialog { background-color: #f3f3f3; color: #000000; }
        QWidget { background-color: #ffffff; color: #000000; font-family: 'Segoe UI', Arial, sans-serif; }
        
        QMenuBar { background-color: #f3f3f3; color: #333333; }
        QMenu { background-color: #ffffff; color: #333333; border: 1px solid #cccccc; }
        
        QTabWidget::pane { border: 1px solid #cccccc; }
        QTabBar::tab { background: #e1e1e1; color: #333333; padding: 8px 12px; }
        QTabBar::tab:selected { background: #ffffff; border-bottom: 2px solid #007acc; }
        
        QTableView { 
            background-color: #ffffff; 
            color: #333333; 
            gridline-color: #f0f0f0; 
            selection-background-color: #e5f3ff; 
            alternate-background-color: #f9fbff;
        }
        QHeaderView::section { background-color: #f3f3f3; color: #333333; border: 1px solid #cccccc; }
        
        QPushButton { background-color: #e1e1e1; color: #333333; border: 1px solid #cccccc; padding: 6px 12px; }
        QPushButton:hover { background-color: #d1d1d1; }
        
        QStatusBar { background-color: #007acc; color: #ffffff; }
    """

def get_highlighter_colors(theme_name):
    if theme_name == "matrix":
        return {
            "command": "#00FF41",
            "variable": "#008F11",
            "string": "#00FF8C",
            "number": "#00A300",
            "comment": "#003B00"
        }
    elif theme_name == "dark":
        return {
            "command": "#569CD6",
            "variable": "#9CDCFE",
            "string": "#CE9178",
            "number": "#B5CEA8",
            "comment": "#6A9955"
        }
    elif theme_name == "forerunner":
        return {
            "command": "#00E5FF",
            "variable": "#00B8D4",
            "string": "#80DEEA",
            "number": "#B2EBF2",
            "comment": "#006064"
        }
    else: # Light
        return {
            "command": "#0000FF",
            "variable": "#001080",
            "string": "#A31515",
            "number": "#098658",
            "comment": "#008000"
        }
