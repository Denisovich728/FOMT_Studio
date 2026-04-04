import sys
import os

print("--- DEBUG IMPORT TRACE ---")
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    print("Importing Perifericos...")
    import Perifericos
    print(f"Perifericos loaded from: {Perifericos.__file__ if hasattr(Perifericos, '__file__') else 'Namespace'}")

    print("Importing Perifericos.Interfaz_Usuario...")
    import Perifericos.Interfaz_Usuario
    print(f"UI loaded from: {Perifericos.Interfaz_Usuario.__file__ if hasattr(Perifericos.Interfaz_Usuario, '__file__') else 'Namespace'}")

    print("Importing Perifericos.Interfaz_Usuario.app...")
    import Perifericos.Interfaz_Usuario.app
    print("Success!")
except Exception as e:
    print(f"FAILED: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
