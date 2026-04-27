import sys
import os
import subprocess
import multiprocessing

root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from PyQt6.QtWidgets import QApplication
from Perifericos.Interfaz_Usuario.app import FoMTStudioApp

def main():
    # Soporte para multiprocesamiento en versiones congeladas (EXE)
    multiprocessing.freeze_support()
    
    # Evitar bucle infinito en versión compilada:
    # Si detectamos argumentos del monitor, ejecutamos el monitor y salimos.
    if len(sys.argv) > 1 and ("monitor.py" in sys.argv[1] or "--pid" in sys.argv):
        from Perifericos.Gestor_Errores.monitor import main as monitor_main
        # Ajustar sys.argv para que argparse en monitor.py funcione correctamente
        if "monitor.py" in sys.argv[1]:
            sys.argv.pop(1)
        monitor_main()
        return

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Iniciar Monitor de Errores Externo (Si no es una instancia de depuración directa)
    root_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(root_dir, "fomt_studio_error.log")
    monitor_script = os.path.join(root_dir, "Perifericos", "Gestor_Errores", "monitor.py")
    
    try:
        # Lanzamos el monitor pasando nuestro PID actual
        p = subprocess.Popen(
            [sys.executable, monitor_script, "--pid", str(os.getpid()), "--log", log_path],
            stdin=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        # Redirigir el stderr de Python directamente al stdin del monitor
        sys.stderr = os.fdopen(p.stdin.fileno(), 'w', buffering=1)
    except Exception as e:
        print(f"No se pudo iniciar el monitor de errores: {e}")

    window = FoMTStudioApp()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
