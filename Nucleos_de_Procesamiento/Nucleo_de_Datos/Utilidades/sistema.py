import os
import platform
import subprocess
import multiprocessing

def get_safe_worker_count():
    """
    Calcula el número óptimo de hilos de trabajo basado en la arquitectura del CPU.
    Sigue las reglas de la v3.4.4:
    - Máximo 50% de la capacidad lógica total.
    - AMD: 50% de los hilos (para no saturar SMT).
    - Intel Hybrid (P-cores/E-cores): 50% de los hilos para priorizar P-cores.
    """
    logical_cores = multiprocessing.cpu_count() or 1
    
    # Intentar detectar el fabricante del procesador
    is_amd = False
    try:
        if platform.system() == "Windows":
            # Usar wmic para una detección precisa en Windows
            proc_info = subprocess.check_output("wmic cpu get Name", shell=True).decode().lower()
            if "amd" in proc_info:
                is_amd = True
        else:
            # Fallback para otros sistemas
            is_amd = "amd" in platform.processor().lower()
    except:
        # Si falla la detección, asumimos el modo seguro del 50%
        pass
        
    if is_amd:
        # En AMD limitamos al 50% estrictamente para evitar latencias de SMT
        workers = max(1, logical_cores // 2)
    else:
        # En Intel (u otros), el 50% suele cubrir los P-cores sin tocar excesivamente los E-cores
        workers = max(1, logical_cores // 2)
        
    return workers
