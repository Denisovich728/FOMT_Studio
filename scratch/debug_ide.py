
import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# Setup paths
sys.path.append(os.getcwd())

from Perifericos.Interfaz_Usuario.widgets.script_ide import ScriptIDEWidget

class MockProject:
    def __init__(self):
        self.is_mfomt = False
        self.item_parser = None

def debug_ide():
    app = QApplication(sys.argv)
    project = MockProject()
    ide = ScriptIDEWidget(project)
    
    completer = ide.editor.completer()
    if not completer:
        print("FAIL: No completer set on editor")
        return
    
    model = completer.model()
    print(f"Model row count: {model.rowCount()}")
    
    for i in range(min(10, model.rowCount())):
        print(f"Row {i}: {model.index(i, 0).data(Qt.ItemDataRole.DisplayRole)}")

if __name__ == "__main__":
    debug_ide()
