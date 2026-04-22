import sys
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import QMetaObject, Qt, Q_ARG, pyqtSlot

app = QApplication(sys.argv)

class Test(QWidget):
    @pyqtSlot(bool, str)
    def _on_play_ready(self, s, w):
        print('CALLED:', s, w)
        app.quit()
        
    def run(self):
        import threading
        def bg():
            print("Background thread running")
            QMetaObject.invokeMethod(self, '_on_play_ready', Qt.ConnectionType.QueuedConnection, Q_ARG(bool, True), Q_ARG(str, 'test'))
        threading.Thread(target=bg).start()

t = Test()
t.run()
app.exec()
