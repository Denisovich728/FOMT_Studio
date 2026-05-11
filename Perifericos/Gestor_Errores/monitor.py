# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.1.0)
# "The Imposibility Update"
# Desarrollado por: Denisovich728
# ============================================================
import sys
import os
import time
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True, help="Parent process ID to monitor")
    parser.add_argument("--log", type=str, required=True, help="Path to the error log file")
    args = parser.parse_args()

    # Si el archivo no existe, lo inicializamos con el estado PENDIENTE
    # Si ya existe y está vacío o no tiene el tag, lo preparamos.
    # Pero lo ideal es escribir el tag solo si capturamos algo.
    
    captured_data = []
    
    try:
        # Bucle de lectura de stdin (redireccionado desde stderr del padre)
        # sys.stdin.read() bloqueará hasta que el pipe se cierre (cuando el padre muera o cierre stderr)
        for line in sys.stdin:
            if line:
                captured_data.append(line)
                # Opcional: escribir en tiempo real? No, mejor al final para asegurar el header.
    except EOFError:
        pass
    except Exception as e:
        # Si el monitor falla, intentamos dejar rastro
        with open("monitor_debug.txt", "a") as f:
            f.write(f"Monitor Error: {str(e)}\n")

    # Si capturamos algo, lo guardamos con el tag PENDING
    if captured_data:
        # Formatear el log
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_content = [
            "[STATUS: PENDING]\n",
            f"=== FoMT Studio Crash Report - {timestamp} ===\n",
            "".join(captured_data),
            "\n" + "="*40 + "\n"
        ]
        
        # Escribir al archivo (append para no borrar logs previos si los hubiera, 
        # aunque la lógica de la app buscará el primero PENDING)
        with open(args.log, "a", encoding="utf-8") as f:
            f.writelines(log_content)

    # El monitor se cierra solo al terminar la lectura o si se detecta que el proceso padre murió
    # (aunque sys.stdin suele cerrarse automáticamente si el proceso padre muere)

if __name__ == "__main__":
    main()