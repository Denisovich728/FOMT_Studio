import sys
import os

root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from PyQt6.QtWidgets import QApplication
from Perifericos.Interfaz_Usuario.app import FoMTStudioApp

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = FoMTStudioApp()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
